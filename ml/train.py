"""Run: python -m ml.train --data data/labeled --exercise squat --output data/models/squat"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from ml.preprocess import FEATURE_VERSION, load_records, record_features, tabular_features, grouped_split


def metrics(y, predicted, labels):
    all_labels = sorted(set(labels) | set(predicted) | set(y))
    return {"macro_f1": float(f1_score(y, predicted, labels=labels, average="macro", zero_division=0)),
            "per_class": classification_report(y, predicted, labels=all_labels, output_dict=True, zero_division=0),
            "confusion_matrix": confusion_matrix(y, predicted, labels=all_labels).tolist(), "labels": all_labels,
            "unknown_prediction_count": sum(p not in labels for p in predicted)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--exercise", required=True, choices=["squat", "pushup", "plank", "pullup"])
    parser.add_argument("--output", required=True)
    parser.add_argument("--export-onnx", action="store_true")
    parser.add_argument("--feature-set", choices=["full", "angles", "keypoints"], default="full")
    args = parser.parse_args()
    records = [r for r in load_records(args.data) if r["exercise"] == args.exercise]
    if not records:
        raise SystemExit("No labeled recordings found. Collect real participant recordings first.")
    sequences = [record_features(r, args.feature_set) for r in records]
    x = np.stack([tabular_features(s) for s in sequences])
    y = np.array([r["label"] for r in records])
    groups = np.array([r["participant_id"] for r in records])
    train, test = grouped_split(groups)
    if len(np.unique(y[train])) < 2:
        raise SystemExit("Training participants must supply at least two form classes.")
    labels = sorted(np.unique(y).tolist())
    model = HistGradientBoostingClassifier(max_iter=150, max_leaf_nodes=15, min_samples_leaf=5, random_state=42).fit(x[train], y[train])
    result = {"model": "baseline", "labels": model.classes_.tolist(), "exercise": args.exercise, "feature_version": FEATURE_VERSION, "feature_set": args.feature_set, "samples": len(records),
              "train_people": np.unique(groups[train]).tolist(), "test_people": np.unique(groups[test]).tolist(),
              "test": metrics(y[test], model.predict(x[test]), labels), "leave_one_person_out": []}
    if all(records[i].get("rule_label") for i in test):
        result["rule_baseline"] = metrics(y[test], [records[i]["rule_label"] for i in test], labels)
    else:
        result["rule_baseline"] = {"status": "unavailable", "reason": "Every held-out rep needs rule_label for a fair baseline comparison"}
    for person in np.unique(groups):
        tr, te = groups != person, groups == person
        if len(np.unique(y[tr])) < 2:
            result["leave_one_person_out"].append({"person": person, "status": "skipped: fewer than two training classes"})
            continue
        fold = HistGradientBoostingClassifier(max_iter=150, max_leaf_nodes=15, min_samples_leaf=5, random_state=42).fit(x[tr], y[tr])
        result["leave_one_person_out"].append({"person": person, **metrics(y[te], fold.predict(x[te]), labels)})
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    # Pickles are intentionally not loaded by the live app. ONNX is the deployment format.
    import joblib
    joblib.dump(model, output / "baseline.joblib")
    result["onnx"] = "not requested"
    if args.export_onnx:
        try:
            from skl2onnx import to_onnx
            converted = to_onnx(model, x[train[:1]], target_opset=17, options={id(model): {"zipmap": False}})
            (output / "baseline.onnx").write_bytes(converted.SerializeToString())
            result["onnx"] = "exported; runtime parity validation still required before live activation"
        except ImportError:
            result["onnx"] = "unavailable: install optional onnx and skl2onnx dependencies"
    (output / "evaluation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
