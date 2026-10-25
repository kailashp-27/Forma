# Forma — local movement coach

A webcam coaching application for squats, push-ups, planks and pull-ups. Charcoal surfaces, warm rust accents, live skeleton overlay, rep/hold tracking, spoken cues, session history, progression suggestions and a keypoint labeling workspace.

Saved repetitions can be reviewed and replayed in Dataset Studio after a workout. Session details show per-rep quality and tempo; participant-specific analytics track quality trends and within-set changes. These trends summarize the heuristic rule scores, not measured physiological fatigue.

The live baseline uses configurable rules. The pretrained YOLO model estimates joints; it is **not** a trained form-quality classifier. The repository includes the separate data collection and classifier training workflow. Real labeled participants are required before reporting ML results.

## Camera setup and workout plans

**Start camera** opens an unsaved setup preview. The assistant checks image brightness, required joints inside the frame, and approximate body size. Confirm that you are side-on to the camera, maintain usable tracking for three seconds, then select **Begin set** to record. Lighting and distance checks are heuristics; camera angle is confirmed manually. Setup frames never create training or session records.

In **Your workout plan**, choose movements, set counts, rep targets (or valid plank seconds) and rest seconds. The plan saves in this browser. Select **Start workout** and complete camera setup. Reaching each target ends and saves that set, runs its rest timer, and opens setup for the next set. The final target completes the workout. Pause saves existing reps; resume starts a fresh attempt at the current unfinished set. Pausing during rest resumes at the next set. Export a workout summary before closing it. Each recorded set is a separate entry in session history; workout progress itself lasts until page reload.

## Personal calibration and detailed rep review

**Personal counting calibration** in Live Coach uses 3–20 distinct reps labeled **Good form** by a reviewer in Dataset Studio. Examples must come from completed sessions matching the selected participant, exercise and variation, with a side view and valid pose sequences. Preview the proposed extension/contraction thresholds, then save the profile. It applies automatically to newly created sessions in that scope. **Restore defaults** disables it for future sessions; existing sessions retain their original profile snapshot. Calibration changes counting thresholds only: depth targets, form rules and quality scoring stay unchanged. Plank holds do not use rep-range calibration.

The estimator uses each rep's 10th/95th-percentile visible joint angles, then the median across examples, with fixed margins and range/consistency checks. This is an experimental camera calibration heuristic, not a validated assessment of mobility. Keep camera placement consistent, review results against manual counts, and restore defaults if counting becomes less reliable.

New completed reps store frame-aligned rule evidence and the thresholds used. In **Dataset Studio**, or **Session history → open session → Review**, replay the skeleton, scrub through the angle trace and select a rule marker to jump to its onset. Cue explanations show the relevant recorded angle/threshold. A depth marker is a whole-rep range summary placed at the nearest saved deepest frame. Older records retain their skeleton and summary flags but cannot show frame evidence that was never recorded. Plank sessions still store valid hold time rather than rep replays.

## Model Lab: readiness and training

Open **Model lab** in the sidebar. Dataset readiness counts reviewed labels by class and participant, identifies excluded or invalid recordings, and shows the proposed participant split. Collection goals are 150 reps and at least three people per class; these are separate from minimum structural training checks. At least three participants and two classes are needed. Invalid sequences and labels seen only in held-out people block training. Mark unsuitable recordings unusable in Dataset Studio, rather than silently ignoring their failures.

Choose gradient boosting (full, angles-only or keypoints-only features), a temporal CNN, or a GRU. Temporal jobs accept 1–200 epochs and optional training-only augmentation. Starting an experiment snapshots the reviewed database records into a unique run directory and launches the existing local ML tools with one compute thread. One experiment runs at a time; end camera sets before training. Camera startup is blocked while a job is active. Cancel stops the experiment process; failures and logs remain inspectable. Each stage has a 30-minute time limit.

Experiment history shows macro/per-class F1, confusion matrices, held-out participants, rule-baseline comparisons on the same test reps, and optional ONNX conversion parity. Export the JSON report for review. Training does **not** activate a model in Live Coach. Passing conversion parity does not establish real-world exercise accuracy.

Runs persist under `data/experiments/<run-id>/` by default (beside the selected SQLite database). Each directory contains `run.json`, `dataset.json`, `audit.json`, `training.log`, and a `model/` output folder. `COACH_TRAINING_DIR` can override the local run root. The source snapshot includes keypoints and labels, never camera images. Completed results survive app restarts; interrupted jobs are marked interrupted and must be retried as a new run. Plank classification remains unavailable until hold sequences can be collected.

## Run on Windows

Requires Python 3.11/3.12 and Node 20.19+ or 22.12+. The tested host uses Python 3.12 and Node 24. Install from the project root:

```powershell
.\scripts\setup.ps1
.\scripts\start.ps1
```

Open **http://127.0.0.1:8765**. The startup script serves the built dashboard and backend from one local address. Start the camera only when you are ready; the motion preview can be explored without a camera or pose weights.

If PowerShell blocks local scripts, run the individual commands below rather than changing your system execution policy:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c requirements-lock.txt -r requirements-ml.txt
cd frontend
npm.cmd ci
npm.cmd run build
cd ..
.\.venv\Scripts\python.exe scripts\download_model.py
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
```

The setup script installs the pose and training/export packages in an isolated environment, using the tested versions in `requirements-lock.txt`. Use `setup.ps1 -SkipFrontend` to repair Python dependencies and model weights while retaining an existing built dashboard.

The setup script uses project-local temporary files to accommodate restricted Windows temporary folders. `setup.ps1 -SkipPose` installs the core app without downloading YOLO; it supports dashboard/demo exploration but not real pose analysis.

Double-click `Start-Forma.cmd` to run the built app without PowerShell script-policy changes. The default port is 8765. For another port, use `.\scripts\start.ps1 -Port 8787`; its HTTP and WebSocket origins are configured together. Keep the launcher window open while training.

## Development

Run the backend as above. In another terminal:

```powershell
cd frontend
npm.cmd run dev
```

The development UI is at http://localhost:8766. Vite proxies `/api` and `/ws` to the local backend. Configuration lives in `configs/*.yaml`; metric thresholds, required joints, severity rules, targets and progression ladders are data-driven.

## Data and privacy

Camera images are transient and processed locally. SQLite stores completed rep keypoints, timing, rule flags and session metadata in `data/coach.sqlite3`. It does not store videos. Use stable pseudonymous participant identifiers and review manual labels before exporting data. Preview activity is illustrative and is never training or performance evidence.

The server binds to loopback. Keep it local: it has no multi-user authentication and is not configured as an internet service. `COACH_DB_PATH` selects a different local database, useful for isolated tests.

## Tests

```powershell
.\scripts\check.ps1
```

Or run Python tests with `python -m unittest discover -s tests -t . -v` and build the UI using `npm.cmd run build` from `frontend`. The actual checks and their results are documented in [docs/VERIFICATION.md](docs/VERIFICATION.md). Tests use synthetic poses to verify logic; they do not establish real exercise accuracy. Run `.\.venv\Scripts\python.exe scripts\doctor.py` to check local dependency and model readiness without opening a camera.

## Train with real recordings

Read [the exercise form specifications](docs/form-specs/) before labeling. Use Dataset Studio and export the reviewed records. Then follow [ml/README.md](ml/README.md) for participant-held-out gradient boosting, 1D-CNN/GRU candidates, metrics, feature ablations and optional ONNX export. The setup script includes the experiment packages. Manual repairs can use `pip install -c requirements-lock.txt -r requirements-ml.txt` in the virtual environment.

Run `python -m ml.audit --data data/labeled --exercise squat` before training to inspect data coverage and rejected recordings. After exporting a model, run `python -m ml.validate_onnx --model-dir <model-directory> --data data/labeled` to compare Python and ONNX predictions on held-out participants. Live activation requires its passing `onnx-validation.json` and matching artifact hashes.

Then opt into experimental live classification by setting `COACH_FORM_MODEL_DIR` to its directory (containing `evaluation.json`, the parity report and the ONNX artifact; temporal models also require `normalization.npz`) before starting the backend. `COACH_FORM_MIN_CONFIDENCE` defaults to `0.8`. Incompatible exercises, low confidence or inference failures fall back to rules. Rule scores remain explicit; classifier labels are experimental.

## Practical limits

- Current default configs use a side view. Knee valgus and elbow flare are not assessed from this view.
- Pull-up reps use elbow flexion/extension. Body keypoints cannot certify chin-over-bar clearance.
- Scores are rule heuristics, not validated measurements or clinical assessments.
- 25+ FPS and sub-100 ms latency are targets to measure on the actual machine, not guaranteed results.
- Plank progression uses aligned hold duration. Rep classifier collection is primarily for dynamic movements.
- Physical acceptance and real-data model evaluation remain necessary: [docs/HARDWARE-TESTING.md](docs/HARDWARE-TESTING.md).

## Layout

```text
backend/          FastAPI, pose features, smoothing, state engine, SQLite
frontend/         React + TypeScript dashboard
configs/          Exercise YAML definitions
ml/               Preprocessing, grouped evaluation, training, ONNX tooling
tests/            Regression tests with isolated data
docs/form-specs/  Label definitions and observability limits
scripts/          Windows setup, startup and checks
data/             Local session data (excluded from source packages)
models/           Downloaded pose weights (excluded from source packages)
```

YOLO11 documentation: https://docs.ultralytics.com/models/yolo11/ . Ultralytics code and weights use AGPL-3.0 or an Enterprise license; review their terms before distributing or commercializing a derived application: https://www.ultralytics.com/license .
