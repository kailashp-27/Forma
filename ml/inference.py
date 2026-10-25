"""Trusted local ONNX artifacts only; never load pickles in the live service."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from ml.preprocess import FEATURE_VERSION, record_features, tabular_features
from ml.artifacts import artifact_hashes


class OnnxFormClassifier:
    def __init__(self, directory, require_validation=True):
        self.directory = Path(directory)
        self.report = json.loads((self.directory / "evaluation.json").read_text(encoding="utf-8"))
        if self.report.get("feature_version") != FEATURE_VERSION:
            raise ValueError("Model feature version differs from the live feature extractor")
        self.kind = self.report.get("model", "baseline")
        if self.kind not in {"baseline", "cnn", "gru"}:
            raise ValueError("Unsupported model architecture")
        if require_validation:
            validation_path = self.directory / 'onnx-validation.json'
            if not validation_path.is_file():
                raise ValueError('Run python -m ml.validate_onnx before live activation')
            validation = json.loads(validation_path.read_text(encoding='utf-8'))
            if validation.get('status') != 'passed' or validation.get('samples', 0) < 1:
                raise ValueError('ONNX model has not passed parity validation')
            if validation.get('artifact_sha256') != artifact_hashes(self.directory, self.kind):
                raise ValueError('Model artifacts changed after parity validation; validate again')
        import onnxruntime as ort
        model_file = self.directory / f"{self.kind}.onnx"
        self.session = ort.InferenceSession(str(model_file), providers=["CPUExecutionProvider"])
        self.labels = self.report.get("labels", self.report.get("test", {}).get("labels", []))
        if not self.labels:
            raise ValueError("Model report requires explicit label order")
        self.mean = self.std = None
        if self.kind != "baseline":
            with np.load(self.directory / "normalization.npz", allow_pickle=False) as data:
                self.mean, self.std = data["mean"], data["std"]
            if (self.mean.shape != (91,) or self.std.shape != (91,) or
                    not np.isfinite(self.mean).all() or not np.isfinite(self.std).all() or np.any(self.std <= 0)):
                raise ValueError("Invalid model normalization")

    def predict_record(self, record):
        if self.report.get("exercise") not in {None, record.get("exercise")}:
            raise ValueError("Classifier exercise differs from recorded exercise")
        seq = record_features(record, self.report.get('feature_set', 'full') if self.kind == 'baseline' else 'full')
        if self.kind == "baseline":
            inputs = tabular_features(seq)[None].astype(np.float32)
        else:
            inputs = ((seq-self.mean)/self.std).T[None].astype(np.float32)
        outputs = self.session.run(None, {self.session.get_inputs()[0].name: inputs})
        if self.kind == "baseline":
            label = str(np.asarray(outputs[0]).reshape(-1)[0])
            probabilities = np.asarray(outputs[1], dtype=float)[0]
            confidence = float(np.max(probabilities))
        else:
            logits = np.asarray(outputs[0], dtype=float)[0]
            probabilities = np.exp(logits-np.max(logits))
            probabilities /= probabilities.sum()
            best = int(np.argmax(probabilities))
            label, confidence = self.labels[best], float(probabilities[best])
        if (label not in self.labels or not np.isfinite(confidence) or not 0 <= confidence <= 1 or
                len(probabilities) != len(self.labels) or not np.isfinite(probabilities).all() or
                np.any(probabilities < 0) or np.any(probabilities > 1) or
                not np.isclose(probabilities.sum(), 1, atol=.001)):
            raise ValueError("Invalid classifier prediction")
        return {"label": label, "confidence": confidence, "model": self.kind, "experimental": True,
                "probabilities": {label: float(value) for label, value in zip(self.labels, probabilities)}}
