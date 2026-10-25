# Verification — 23 October 2026

## Dataset readiness and Model Lab batch — 24 October 2026

- Dataset readiness excludes unfinished sessions, unreviewed/unusable/unobservable records, unsupported labels and unsupported views. It checks geometry through the existing preprocessing/audit pipeline, reports class/person collection gaps, and blocks invalid data or held-out-only classes.
- Automated coverage includes real baseline subprocess training, ONNX export/parity, immutable source/settings snapshots, single-job exclusion, cancellation, stage failures, interrupted restart recovery, bounded request options, report attachment headers, and withholding camera permission requests during active training. The complete check script passes **59 Python tests + 22 frontend tests**, TypeScript and production build.
- Browser checks used an isolated synthetic fixture database on port 8789: 24 examples across four fixture participant IDs and two labels. The UI displayed collection gaps, participant-label counts, train/test people, baseline/CNN/GRU histories, classifier/rule metrics, and confusion matrices. Baseline export/parity passed; one-epoch CNN and GRU experiments completed; a longer CNN run was cancelled through the dashboard. These synthetic scores do not measure exercise accuracy, and no fixture model was activated.
- After restarting the isolated server, histories and metrics remained available. The report endpoint returned HTTP 200 with an explicit JSON attachment filename and saved `artifacts/verification/model-lab-report.json`. The browser download-event automation timed out, so native browser save completion was not established by that harness. The endpoint and attachment were checked separately.
- Browser console checks found no errors or warnings. Screenshots: `artifacts/verification/dataset-readiness.png` and `artifacts/verification/model-lab-results.png`. Test data and model outputs remain under a separate preview directory in artifacts, outside the normal training database and live model configuration.
- Real participant collection and validation are still needed. Minimal readiness is a structural gate, not proof of enough data or classifier usefulness. Plank remains unsupported for classifier training until hold sequences can be recorded.

## Personal calibration and rep evidence batch — 24 October 2026

- `scripts/check.ps1`: **53 Python tests + 20 frontend tests pass**, including database migration without session loss, participant/variation isolation, rejection of unsuitable calibration evidence, immutable session snapshots, live start after profile disable, aligned frame annotations, contiguous event markers and legacy-record fallback. TypeScript and production build pass.
- Browser → API → SQLite checks used an isolated synthetic fixture database on port 8788: selected three reviewed reps, previewed thresholds (165° extension / 98° contraction for that fixture), saved the profile, observed it active, and restored defaults. These angles are fixture results, not suggested personal targets. The production training database received no synthetic calibration examples.
- Dataset Studio replay and Session History's Review action both displayed new frame evidence. Selecting the fixture's depth summary marker moved to frame 3/8 at 0.30 seconds and displayed the recorded 115° minimum against its saved 100° depth target. No browser console warnings or errors were captured.
- Screenshots: `artifacts/verification/personal-calibration.png` and `artifacts/verification/rep-form-review.png`. The test preview server was stopped afterward; the app on port 8765 uses the normal local database and updated code.
- These checks establish interface, storage, and rule-evidence behavior on controlled fixtures. Real-participant calibration usefulness and accuracy still require physical webcam comparison. Plank uses hold/alignment rules and has no repetition-range calibration. Historical reps cannot acquire frame evidence retroactively.

## Application story

The user selects an exercise and variation, explicitly starts the webcam, sends transient JPEG frames to the local pose engine, receives skeleton/rep/hold feedback, then ends the set and reviews SQLite history or labels keypoint records for training.

## Verified

| Check | Result | Evidence and scope |
| --- | --- | --- |
| Python regression suite | Pass | 45 unittest tests: 28 backend and 17 ML |
| Dynamic rep engine | Pass on synthetic poses | Twenty squat cycles count exactly; push-up/pull-up cycles, jitter, shallow attempts and dropout cases covered |
| Plank timing | Pass on synthetic poses | Standing, invalid alignment, tracking loss and time gaps do not accumulate valid hold time |
| Session and dataset persistence | Pass | Isolated SQLite databases verify records, manual labels, export, finish lifecycle and participant-isolated progression |
| Coach command lifecycle | Pass with scripted socket harness | Real coach coroutine receives start/demo/tick/stop/disconnect commands; no network transport involved |
| Data preparation | Pass | 32-frame resampling, aspect-correct angles, missing-joint rejection, invariance and participant split checks |
| Training pipeline | Pass on disposable synthetic data | Boosting fits and writes reports, LOPO and rule comparisons; test artifacts are removed afterward |
| CNN and GRU architecture smoke | Pass | Torch forwards map `[2,91,32]` to `[2,3]`; this does not measure accuracy |
| Frontend | Pass | Strict TypeScript and Vite production bundle compile successfully |
| Frontend behavior harness | Pass | 9 Node tests exercise the compiled hook and replay logic with mocked camera, sockets and React boundary; browser behavior is not established |
| Recorder review API | Pass | Metadata-only record lists omit sequences; selected-record endpoint preserves original keypoints; filters combine exercise, participant and label status |
| Quality analytics | Pass | Participant isolation, weighted quality, tempo, within-set slope, empty and single-rep cases covered with isolated SQLite data |
| Model activation checks | Pass with mocked ONNX session | Missing parity report, changed artifacts, invalid probabilities/normalization and exercise mismatch are rejected; actual ONNX execution now also passes on disposable fixtures (see the 24 October section) |
| Dataset audit | Pass | Duplicate exports rejected, unusable/unobservable examples excluded, malformed geometry and insufficient participant coverage reported |

## Not established

- **Real webcam and exercise accuracy:** no camera was opened automatically. Real pose inference was verified on the official public Ultralytics bus image and a single-person crop; physical exercise counting still needs the user.
- **Browser:** Previously rendered once, but browser reconnection was unstable. Interactive camera and complete browser flows remain unverified. Earlier transport limitations were revisited on port 8765; HTTP and WebSocket results are recorded below.
- **Physical accuracy, FPS and latency:** require a person performing the movements with this machine and camera. Twenty synthetic squats do not establish the 20-real-squat milestone.
- **Trained form model:** no real participant dataset, fitted production form classifier or held-out F1 result exists yet. Conversion parity was tested using disposable synthetic fixtures only; no synthetic classifier was activated.
- **Voice and camera lifecycle:** implemented, but browser permission, webcam light shutdown and spoken output need the physical acceptance checklist.

## Dependency recovery

Frontend dependencies were installed from compatible package copies already on the machine, then an offline lockfile was generated. The build uses exact React/Vite/TypeScript versions recorded in `frontend/package.json` and `package-lock.json`; other machines should use `npm ci`. On 24 October, network downloads succeeded. Python is now fully isolated (`include-system-site-packages=false`), all pose/training/export dependencies are installed, and `pip check` passes. `requirements-lock.txt` records tested versions; setup applies those constraints. Protobuf is constrained below version 7 for compatibility with the tree-model converter.

Use [HARDWARE-TESTING.md](HARDWARE-TESTING.md) for remaining acceptance work.

## Camera setup and workout plan batch — 24 October 2026

- `scripts/check.ps1`: 46 Python tests and 18 frontend tests pass, including setup privacy, camera setup-to-recording lifecycle, visibility/lighting heuristics, ordered workout targets, zero rest, final plank completion, pause during rest, and persistence failure. TypeScript and production build pass.
- Browser check on the served production UI: added a movement, reloaded, confirmed the movement persisted, then removed the test movement. No browser warning/error logs were captured. Preview: `artifacts/verification/workout-plans.png`.
- `scripts/verify_camera_setup.py --image artifacts/verification/single-person.jpg` used the actual local WebSocket and YOLO inference: setup acknowledged, 17 tracked keypoints returned, no rep completion/score/hold reported, stop acknowledged, and session data unchanged. The cold fixture request took approximately 14.9 seconds server-side on this run; this is not a sustained performance result.
- Workout controller and browser camera boundaries are tested with controlled fixtures. The new setup assistant and a complete workout still need a person exercising in front of the webcam. Camera angle confirmation is manual; brightness, framing and distance checks are heuristics. Workout plans persist in browser storage; active workout progress does not survive page reload. Saved sets remain in SQLite.

## Second implementation pass

The engine now requires consecutive threshold observations, retains its visible side through small confidence changes, resets on true side loss, and avoids counting plank recovery intervals. A completed frame reports the completed rep's score and flags rather than immediately showing a clean standing-frame score.

Frontend additions include saved-record review, keypoint replay, human labels and shortcuts, lightweight sequence loading, readable session summaries, and connection lifecycle handling. A connected preview uses the real rule engine with synthetic keypoints; offline preview animation has no fabricated rep or quality metrics. Nine frontend tests cover nonuniform replay timestamps, missing dependencies, start acknowledgement, aspect ratio, immediate camera release, finalization retries, disconnects, fatal inference errors, synthetic demo and stale socket isolation. These tests use mocked transport/camera boundaries; interactive/browser behavior still requires the previously blocked browser check.


## Port 8765 build

The main app now defaults to http://localhost:8765, with Vite development UI at port 8766. Both the built dashboard and `/api/health` returned HTTP 200. The launcher exports COACH_PORT so the selected HTTP and WebSocket origins agree. A live synthetic WebSocket start/frame/stop smoke check was run on the selected port. The production build and 45 Python plus 9 frontend tests pass. `Start-Forma.cmd` provides a double-click launcher and `scripts/start.ps1 -Port 8787` supports an alternative port. At this earlier checkpoint webcam analysis was blocked by missing dependencies; the 24 October repair below resolves the installation blocker.


## Full dependency installation — 24 October 2026

- All native imports pass: PyTorch, TorchVision, OpenCV, Ultralytics, ONNX, ONNX Runtime, sklearn and skl2onnx. `pip check` reports no broken requirements.
- Official YOLO11 nano pose weights are installed in models/yolo11n-pose.pt. Blank-frame rejection and public-image person detection passed; a single-person crop yielded 17 tracked keypoints.
- The live app on localhost:8765 accepted that image over its actual coaching WebSocket and returned tracking=true, 17 keypoints and pose_model_loaded=true. Only the uniquely created verification session was removed afterward; user sessions were untouched.
- Cold model load took about 6 seconds in this check. A warmed direct pose frame took about 25 ms; this single fixture is not an end-to-end webcam performance benchmark.
- Boosting, CNN and GRU ONNX exports and Python/ONNX parity checks passed on temporary synthetic fixtures, including artifact-gated adapter loading. These temporary model files were removed and no production form classifier was activated.
- 45 Python tests and 9 frontend tests passed, and the production dashboard build passed.
