# Pull-up label specification — experimental side view, v1

Camera: side view, showing wrists, elbows, shoulders and hips throughout the
cycle. Bars commonly occlude hands and face; use `unobservable` when confidence
is inadequate. The current engine measures elbow extension/bend, not strict
competition pull-up completion.

| Label | Annotation decision |
| --- | --- |
| good | Observable elbow-angle cycle from configured 155° extension to 65° bend and back, without the configured excessive torso-lean proxy. This means acceptable projected movement, not verified chin clearance. |
| torso_swing | Visible torso lean exceeds configured 30° from vertical. This is a proxy and may miss or misclassify kipping. |
| partial_extension | Manually reviewed attempt fails to return to extension. An incomplete cycle is not counted by the current rep engine. |
| unobservable | Bar occlusion or body cropping prevents reliable joint estimates. |
| unlabeled | Awaiting review; excluded from training. |

YOLO COCO17 has a nose keypoint but no chin keypoint or bar detector. Do not
label nose position as chin-over-bar ground truth. Strict chin-clearance
evaluation needs calibrated bar height and independent human annotation or a
dedicated chin/bar model. Hip swing/kipping also requires temporal motion
validation; static lean is only the baseline proxy. Choose torso_swing before
partial_extension for combined faults and preserve secondary flags. Have a
second reviewer label a subset. Keep pull-ups experimental until pose coverage
and false feedback rates are measured with real participants.
