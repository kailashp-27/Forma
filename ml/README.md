# Offline form quality experiments

The application's **Model Lab** now provides a local UI for dataset readiness and these training commands. It reads reviewed, finished-session records from SQLite, saves a fixed snapshot for each run, runs one experiment at a time, and displays stored metrics and logs. Optional ONNX export is followed by parity validation. No model is activated automatically. Command-line workflows below remain supported. Both baseline and temporal reports now compare saved rule labels on the same held-out reps when available.

No pretrained form-quality classifier or fabricated training data is included.
The live app initially uses configurable rules. YOLO's pose estimator is a
separate pretrained model and does not itself know exercise form quality.

## Record and label

1. Use the live coach recorder with a pseudonymous participant ID. Keep the full body visible in the specified side view. Current automatic sequence recording covers counted reps; plank holds are session summaries and need a separate sequence recorder before temporal training.
2. Complete a rep. Assign a label from the exercise form specification. Use `unobservable` if the camera cannot establish the label, and `unlabeled` until reviewed.
3. Export keypoints through `GET /api/dataset/export` and save the JSON as `data/labeled/reps.json`. Video is not required.
4. Collect several people per class. Aim for 150–200 usable reps per class. At least three participants are required by the scripts; more are needed for meaningful generalization.

Saved records can now be reviewed after a workout in Dataset Studio. Use the skeleton replay to check the label, rather than accepting the rule label automatically. Mark occluded or ambiguous reps `unobservable`/`unusable`; both are excluded from training. Each recording must occur only once across the supplied JSON/JSONL exports: duplicate record IDs are rejected.

Audit the reviewed export before training:

```powershell
python -m ml.audit --data data/labeled --exercise squat --output artifacts/dataset-audit.json
```

The audit checks geometry, class counts, participant coverage and the deterministic participant split. It exits with code 2 when minimal training conditions are unmet. Warnings about class coverage still need human attention even when the structural checks pass.

Each record has this shape:

```json
{"participant_id":"person-01","exercise":"squat","label":"good","keypoints":["T frames of 17 [x,y,confidence] joints"],"timestamps":["T increasing seconds"],"rule_label":"good","view":"side","aspect_ratio":1.3333333}
```

The strings inside the example arrays describe their structure; actual recordings contain numbers. Joint order is COCO17: nose, eyes, ears, shoulders, elbows, wrists, hips, knees, ankles. Coordinates are normalized to image width/height. Do not combine front and side views into one experiment without treating camera view as a controlled factor. Anonymous IDs must remain stable across sessions so that the same person cannot leak into both training and test sets.

## Baseline and validation

```powershell
python -m ml.train --data data/labeled --exercise squat --output data/models/squat/baseline
python -m ml.train --data data/labeled --exercise squat --feature-set angles --output data/models/squat/angles
python -m ml.train --data data/labeled --exercise squat --feature-set keypoints --output data/models/squat/keypoints
```

The full model uses 32-frame torso-normalized coordinates, six joint angles,
coordinate velocities, and visibility confidence. Image coordinates are corrected for recorded width/height aspect ratio before geometry is computed. Legacy records without aspect metadata assume 4:3; supply the true ratio before mixing camera resolutions. The boosting input combines
summary statistics and phase samples. All splits hold out whole people. The
report contains per-class F1, macro F1, a confusion matrix, and
leave-one-person-out folds. The saved rule label is evaluated on the same test
reps. Missing rule labels make the comparison explicitly unavailable.

`angles` and `keypoints` are feature ablations against the default `full`
representation. Their reports use the same fixed split. Do not repeatedly tune
on the held-out test people. Use additional training-person validation folds
when selecting thresholds, architectures, and augmentation settings. If some
classes occur only in held-out people, collect more people rather than quietly
moving their reps into training.

## Temporal candidates

```powershell
python -m ml.train_temporal --data data/labeled --exercise squat --model cnn --augment --output data/models/squat/cnn
python -m ml.train_temporal --data data/labeled --exercise squat --model gru --augment --output data/models/squat/gru
```

These optional PyTorch experiments use training-person normalization and
training-only mirroring, coordinate noise, and monotonic time warping. Fixed
rep length normalizes total duration, so add measured tempo features in a
future version if absolute speed should determine a label. They report a
held-out participant split; the boosting script additionally supplies LOPO.
An improvement on one small split is not evidence that a neural model is best.

## Optional ONNX export

Install `onnx`, `skl2onnx`, and `onnxruntime`; add `--export-onnx` to a training
command. Torch exports also need the installed torch ONNX support. CNN/GRU
ONNX inputs are `[batch,91,32]` (feature channels first), normalized using the
saved `normalization.npz`. The boosting ONNX input is the tabular feature vector.
Use the exact `feature_version` from the report and label order when loading.
Verify ONNX predictions against the Python model on held-out reps before
enabling live inference. No exported model is automatically activated by these
scripts. Only open trusted `.joblib`/`.pt` files; they are local experiment
artifacts, not a model upload interface.

Run the conversion parity check on your own trusted training outputs:

```powershell
python -m ml.validate_onnx --model-dir data/models/squat/baseline --data data/labeled
```

It uses only the report's held-out participants and compares predicted labels and all class probabilities against the Python reference. A passing `onnx-validation.json` records SHA-256 hashes of the exact ONNX, evaluation and normalization files. Live activation requires that report; changing any covered artifact invalidates it. This checks conversion consistency, not exercise form accuracy. Run model evaluation and physical acceptance separately. ONNX runtime parity was executed for boosting, CNN and GRU models on disposable synthetic fixtures after dependency installation. All passed, including the live adapter. This verifies conversion/code paths, not form accuracy; no synthetic model was installed as a production classifier.

Dependencies: numpy, scikit-learn, joblib; optional torch, onnx, skl2onnx,
onnxruntime. Unit checks: `python -m unittest discover -s tests/ml -v`.
