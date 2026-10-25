# Camera and physical acceptance tests

## Hardware

A laptop webcam or USB camera, stable support, and adequate floor space are sufficient. A GPU is optional. Pull-ups require an existing securely mounted bar; this software does not certify mounting safety. No Arduino, wearable, or custom electronics are needed for this version.

Start with a side view. Keep the whole body visible, including wrists and ankles, and avoid strong backlighting. Choose the same camera view as the exercise configuration. Front-view squat valgus checks require a separate front-view recording; a side-view score must not imply they were checked.

## Tests requiring a person

These have not been established by synthetic data or automated tests. Record the actual results before making accuracy or performance claims.

### Collect a camera test report

Live Coach now includes **Camera test & calibration**. Start a real camera session, exercise with an independent manual tally, then end the session. Enter the observed rep count (or valid aligned plank seconds), add camera setup and cue observations, and choose **Export camera test JSON**. Download before starting another camera session or closing the page. Reports are browser downloads; they are not stored in the session database. Previews never contribute measurements.

The report identifies the session, exercise, variation and participant, includes the signed and absolute count/hold error, and records response count, duration, received FPS, tracking coverage, mean browser round-trip latency, mean server processing time, and P95 round-trip latency over the latest 600 responses. Browser round trip starts before JPEG encoding and ends when the response handler receives the result; camera sensor and display latency are excluded. Received FPS uses intervals between first and last responses. Stop acknowledgement time is included in the reported session duration. Run for at least 60 seconds; targets are displayed for comparison, not certified as achieved. Manual observations and notes require reviewer judgment.

| Test | Procedure | Target / observation |
| --- | --- | --- |
| Camera permission | Start Live Coach, allow camera, then end session | Camera light turns off after stop; permission rejection gives a useful message |
| Squat counting | Perform 20 controlled reps; compare a manual tally | At most one count error |
| Push-up counting | Perform 10 reps with full body visible | Compare manual count and low-confidence behavior |
| Plank timer | Hold a stable plank, break alignment, leave frame | Timer pauses for invalid or missing pose; no wall-clock catch-up |
| Tracking loss | Cover the camera mid-rep, uncover while bent | No phantom rep; restart from a complete start position |
| Frame boundaries | Walk partly out of frame | No trustworthy score from missing joints |
| Cue usefulness | Review one cue per rep with a knowledgeable coach | Verify labels and thresholds before collecting training data |
| Pull-up limitations | Test on a bar with body fully visible | Count extension/flexion; chin clearance remains unverified by body pose alone |
| Performance | Record FPS and frame processing latency for one minute | Target 25 FPS and <100 ms; actual result depends on hardware |
| Voice | Enable voice for one set, then stop | No overlapping queued cues or speech after stop |
| Persistence | Finish session, restart server, reopen History | Real saved reps remain; demo reps never appear |
| Privacy | Inspect project data after a set | SQLite/keypoints only; no raw image or video files |
| Setup assistant | Start camera; change lighting and framing; confirm side view | Begin set requires fresh, stable tracking and usable light; setup creates no history |
| Workout sequence | Choose two sets and two movements with a short rest | Each target ends a recorded set; rest advances to the next setup; final target completes workout |
| Workout pause | Pause during a set, then during rest | Current partial reps remain saved; resume retries unfinished set, or moves to next after rest |
| Counting calibration | Review and label at least three good reps, preview/save thresholds, create a new session | Profile matches participant and variation; compare counts to a manual tally; depth scores retain default rules |
| Restore defaults | Disable a calibration, create a new session, then reopen the old one | New session uses defaults; earlier session keeps its recorded calibration snapshot |
| Rep evidence | Record a rep with a naturally occurring flag, open its review and choose a marker | Replay jumps to the recorded event; explanation and angle trace match the stored rule; range markers remain rep summaries |

Use comfortable movements. Do not deliberately perform painful or unsafe form to manufacture negative labels; collect naturally occurring deviations or obtain supervised examples.

## Model acceptance

Use several participants. Keep every participant entirely within one split. Report class counts, per-class F1, confusion matrix, held-out participants, rule comparison, camera view and actual device latency. Synthetic examples validate code paths only; they are not exercise-quality evidence.
