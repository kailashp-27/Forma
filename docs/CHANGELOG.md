# Implementation updates

## Saved-data review and reliability pass

- Dataset Studio reviews real saved reps after a session, replays their keypoints, filters by person/exercise/review status and supports human labeling or clearing labels.
- Record lists use summary metadata; full keypoints are fetched only for the selected rep.
- Session detail displays per-rep quality, duration, flags and a quality trend instead of raw JSON as the primary view.
- Participant-specific analytics summarize quality, tempo and within-set score trends. Declining quality is a heuristic and does not establish physiological fatigue.
- Connected motion previews use the actual rule engine with synthetic keypoints. Preview records never enter session history or datasets.
- Camera startup waits for the server's acceptance; failures release the camera and preserve already saved reps. Session finalization retries after disconnects.
- Rep thresholds require consecutive observations. Small confidence changes no longer switch body sides; true visibility loss resets the incomplete cycle.
- Plank timing excludes invalid-alignment recovery intervals. Completed rep scores remain visible on the completion frame.
- Dataset audit checks class/person coverage and geometry; duplicated recording IDs are rejected and unusable examples are excluded.
- ONNX parity tooling compares labels and all class probabilities on held-out people, then identifies exact artifacts by SHA-256. Live activation requires a matching passing report.

Validation: 45 Python tests and 9 frontend behavior tests pass, with actual trained ONNX execution, real webcam accuracy and browser interactions still pending.

## Local port update

Default application port is now 8765, with a matching WebSocket origin allowlist, configurable PowerShell launcher, double-click Windows launcher and development proxy on 8766. Production build, HTTP health/dashboard and synthetic WebSocket transport checks were run on the new port.

## Pose dependency repair — 24 October 2026

Installed all pose/training/export packages and official YOLO weights in a fully isolated Python environment. Added tested dependency constraints, native-import diagnostics and repeatable real-image, live-socket and ONNX conversion smoke checks. Fixed an incompatible Protobuf/converter combination by constraining Protobuf below version 7. Live image inference now returns 17 tracked joints. Real webcam/form accuracy still requires physical testing.
