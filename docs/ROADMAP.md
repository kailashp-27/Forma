# Build milestones

The project is implemented as a local application. Completion of code is separate from validation with real exercise recordings.

1. Environment and form definitions: Windows scripts, exercise YAML, observable-label specifications.
2. Pose pipeline: browser webcam capture, local YOLO pose inference, confidence gates, smoothing, normalized features and overlay.
3. Baseline engine: configurable rep states, hold timing and rule cues; all four movements have configurations.
4. Data collection: keypoint-only rep records with participant identifiers and manual labels; export for training.
5. Temporal ML: fixed-length sequences, participant-separated evaluation, gradient boosting and optional temporal models. Real data and fitted weights remain required.
6. Coach: live metrics, one primary cue, speech option and rest timer. Hardware timing remains to be measured.
7. History and progression: SQLite persistence and conservative progression evidence from real saved sessions.
8. Acceptance: automated regression checks plus the physical checklist in HARDWARE-TESTING.md.

## Next real-world milestone

The camera setup assistant, browser-saved workout plans, personal counting calibration, detailed rep review, dataset readiness and Model Lab training dashboard are implemented. Model Lab snapshots reviewed data, runs local baseline/CNN/GRU experiments, compares held-out metrics with rules, and optionally validates ONNX conversion. It never activates a model automatically. Real webcam acceptance, real participant data collection and form-classifier accuracy evaluation remain pending. The remaining proposed product feature is personal progress goals.

Validate squat counting with one person, then collect multiple participants before training. Calibrate thresholds with a qualified reviewer. Do not report model accuracy or frame-rate targets as achieved until measured.
