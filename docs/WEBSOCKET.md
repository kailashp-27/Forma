# Local coach transport

HTTP requests are documented in `openapi.json` and live `/docs`. The dashboard uses the same origin as the local backend; Vite development proxies `/api` and `/ws` to port 8765.

For saved-data review, `/api/records?include_keypoints=false` returns lightweight summaries including `frame_count`; `/api/records/{id}` returns the chosen full record. List and dataset-export endpoints accept `exercise`, `participant_id` and `label_status` filters. `/api/analytics?participant_id=...` returns observed session/set quality and tempo trends. Neither rule scores nor their trends establish physiological fatigue.

Connect to `/ws/coach`. One socket owns one active set. Create an open HTTP session first, matching the exercise, participant and variation. Send:

For camera positioning before recording, send `{"type":"setup","exercise":"squat","view":"side"}` without creating a session. Wait for `started`, then send binary JPEG frames as usual. Responses include `setup:true`; pose tracking is available but counts, hold time, quality and rep completion are suppressed. Setup never writes sessions, sets or repetitions. Stop setup before starting a recorded set.

```json
{"type":"start","exercise":"squat","session_id":"returned-session-id","view":"side"}
```

Wait for `{"type":"started", ...}`. Send binary JPEG frames, at most 2 MB each and 1920×1080 pixels. Keep only one in-flight frame to avoid a queue. The server returns:

```json
{"type":"frame","keypoints":[],"features":{},"width":640,"height":360,"fps":0,"latency_ms":0,"state":"waiting","reps":0,"hold_seconds":0,"quality":null,"cue":"Move into view","flags":[],"tracking":false,"demo":false}
```

Keypoints use COCO17 order, normalized by image width and height, each `[x,y,confidence]`. Feature angles account for image aspect ratio. `quality:null` means no valid tracking. `fps` measures actual processed frame intervals, while `latency_ms` measures server frame processing, excluding camera capture and transport.

Completed repetitions include `rep_completed`, containing a stored record ID, timing, flags, heuristic quality and rule label. Full keypoint sequences stay in SQLite rather than being echoed into the UI. The HTTP records endpoint supplies them for annotation/export.

Send `{"type":"stop"}` and wait for `{"type":"stopped"}` before calling `POST /api/sessions/{id}/finish`. Disconnects close the active set as well. Demo mode uses `{"type":"demo","exercise":"squat"}` then `{"type":"tick"}`; it never creates real session or training records. The frontend's motion preview is an independent local illustration and likewise stores nothing.

Errors use `{"type":"error","message":"..."}`. Tracking loss is an ordinary frame with `tracking:false`, not a fatal error. Unapproved browser origins are rejected. The application is a loopback, single-machine tool, not an authenticated internet API.

## Counting calibration and rep review

`GET /api/calibrations?participant_id=...&exercise=squat&variation=Bodyweight%20squat` returns `{profiles,candidates}`. Candidates are up to 200 recent completed-session reps human-labeled `good`, matching both the session and record participant, variation, exercise, and side view. `POST /api/calibrations/preview` accepts `{participant_id,exercise,variation,record_ids}` (3–20 distinct IDs) and returns proposed counting thresholds with evidence. `POST /api/calibrations` accepts the same body, recomputes eligibility, disables previous profiles for that scope, and saves the new active profile. `POST /api/calibrations/{id}/disable` restores defaults for future sessions. Invalid evidence returns 422. Plank does not use range calibration.

New sessions snapshot the active calibration at creation. Live start uses that snapshot; profile changes never rewrite old sessions or change an existing set. Form scoring rules and depth targets remain the default configuration. Each new completed rep stores aligned `frame_annotations` (features, state, rule flags), `assessment_config`, and an optional `depth_marker_time`. These are available from full record/session endpoints; annotations are omitted from list summaries and live completion messages. Historical reps without annotations keep their rep-level flags and skeleton replay, without invented per-frame evidence.

## Model lab

`GET /api/dataset/readiness?exercise=squat` audits saved human labels from finished sessions, reports invalid sequences, excluded/unreviewed records, class/person coverage and collection gaps. Minimal training readiness is distinct from the collection goal of 150 examples and three participants per class. Invalid geometry and held-out-only classes block training.

`POST /api/training/runs` accepts `{exercise,model,feature_set,epochs,augment,export_onnx}`. Models are `baseline`, `cnn`, `gru`; temporal models use full features. Epochs are 1–200. It snapshots eligible records, checks readiness, and starts one local subprocess experiment (202); insufficient data returns 422 and an existing active job or live set returns 409. The request cannot specify commands or filesystem paths. `GET /api/training/runs` lists run metadata; `GET /api/training/runs/{id}` includes audit, evaluation, optional parity report, and a bounded log tail. `POST /api/training/runs/{id}/cancel` cancels an active experiment. `GET /api/training/runs/{id}/report` exports JSON evidence without raw keypoints. Unknown IDs return 404. Run IDs are generated UUID hex strings.

Run directories under the local database's `experiments` folder contain immutable input snapshots, audit, settings/status, logs and model outputs. Results persist across restarts; unfinished jobs are marked interrupted rather than resumed. Optional export is followed by conversion parity validation. Nothing in Model Lab activates a model for live coaching. Plank needs a sequence recorder before classifier training from the current database.
