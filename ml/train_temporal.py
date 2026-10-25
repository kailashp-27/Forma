"""Optional torch experiments: python -m ml.train_temporal --help.

Use training/validation people to select models; reserve the exported test people
for final comparison. This script reports a single fixed-seed held-out split;
it does not claim model superiority from that one split.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
from ml.preprocess import load_records, temporal_features, grouped_split, augment, FEATURE_VERSION


def make_model(kind, channels, classes):
    import torch
    from torch import nn
    if kind == "cnn":
        return nn.Sequential(nn.Conv1d(channels, 48, 3, padding=1), nn.ReLU(), nn.Conv1d(48, 64, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Linear(64, classes))
    class GRUClassifier(nn.Module):
        def __init__(self):
            super().__init__()
            self.gru = nn.GRU(channels, 64, batch_first=True)
            self.head = nn.Linear(64, classes)
        def forward(self, values):
            _, hidden = self.gru(values.transpose(1, 2))
            return self.head(hidden[-1])
    return GRUClassifier()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--exercise", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", choices=["cnn", "gru"], default="cnn")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--augment", action="store_true")
    parser.add_argument("--export-onnx", action="store_true")
    args = parser.parse_args()
    if args.epochs < 1:
        parser.error("--epochs must be positive")
    import torch
    from ml.train import metrics
    torch.manual_seed(42)
    rng = np.random.default_rng(42)
    records = [r for r in load_records(args.data) if r["exercise"] == args.exercise]
    if not records:
        raise SystemExit("No labeled records. Collect real participants first.")
    groups = np.array([r["participant_id"] for r in records])
    train, test = grouped_split(groups)
    labels = sorted({r["label"] for r in records})
    if len({records[i]["label"] for i in train}) < 2:
        raise SystemExit("Training participants must supply at least two form classes.")
    seq = [temporal_features(r["keypoints"], timestamps=r.get("timestamps"), aspect_ratio=r.get("aspect_ratio",4/3)) for r in records]
    y = np.array([labels.index(r["label"]) for r in records])
    # Fit normalization on training people only.
    mean = np.concatenate([seq[i] for i in train]).mean(0)
    std = np.maximum(np.concatenate([seq[i] for i in train]).std(0), .001)
    model = make_model(args.model, seq[0].shape[1], len(labels))
    optimizer = torch.optim.Adam(model.parameters(), lr=.001)
    loss_fn = torch.nn.CrossEntropyLoss()
    for _ in range(args.epochs):
        model.train()
        shuffled = rng.permutation(train)
        for batch_start in range(0, len(train), 32):
            indexes = shuffled[batch_start:batch_start+32]
            samples = [temporal_features(augment(records[i]["keypoints"], rng), aspect_ratio=records[i].get("aspect_ratio",4/3)) if args.augment else seq[i] for i in indexes]
            x = torch.tensor(((np.stack(samples)-mean)/std).transpose(0,2,1), dtype=torch.float32)
            optimizer.zero_grad()
            loss_fn(model(x), torch.tensor(y[indexes], dtype=torch.long)).backward()
            optimizer.step()
    model.eval()
    xt = torch.tensor(((np.stack([seq[i] for i in test])-mean)/std).transpose(0,2,1), dtype=torch.float32)
    with torch.no_grad():
        predicted = model(xt).argmax(1).numpy()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output / f"{args.model}.pt")
    np.savez(output / "normalization.npz", mean=mean, std=std)
    report = {"model": args.model, "exercise": args.exercise, "feature_version": FEATURE_VERSION, "labels": labels,
              "samples": len(records),
              "train_people": np.unique(groups[train]).tolist(), "test_people": np.unique(groups[test]).tolist(),
              "test": metrics([labels[i] for i in y[test]], [labels[i] for i in predicted], labels),
              "onnx": "not requested", "augmentation": args.augment}
    if all(records[i].get('rule_label') for i in test):
        report['rule_baseline']=metrics([records[i]['label'] for i in test],[records[i]['rule_label'] for i in test],labels)
    else:
        report['rule_baseline']={'status':'unavailable','reason':'Every held-out rep needs rule_label for a fair baseline comparison'}
    if args.export_onnx:
        try:
            torch.onnx.export(model, xt[:1], str(output / f"{args.model}.onnx"), input_names=["features"], output_names=["logits"], dynamic_axes={"features": {0:"batch"}, "logits":{0:"batch"}}, opset_version=17, dynamo=False)
            report["onnx"] = "exported; input normalization is in normalization.npz; validate parity before activation"
        except ImportError:
            report["onnx"] = "unavailable: install optional onnx dependencies"
    (output / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
