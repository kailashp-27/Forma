# Push-up label specification — side view, v1

Camera: fixed side view at approximately hip height, with shoulder, elbow,
wrist, hip and ankle visible. Keep the floor horizontal in the image. A rep
starts with elbow extension, reaches the configured bend threshold, and ends
at extension. The elbow angle is a depth proxy; the app does not measure chest
clearance above the floor.

| Label | Annotation decision |
| --- | --- |
| good | Full observable rep reaches configured 95° elbow bend and returns to 155° extension; shoulder–hip–ankle angle remains at least configured 155°. |
| body_alignment | Visible shoulder–hip–ankle angle falls below 155° during the rep, indicating a projected sag or pike. Label this combined class consistently; the baseline does not distinguish signed sag from pike. |
| depth | Observable cycle reverses before configured target elbow bend (95° initially). Counting threshold is more permissive than the form target; manually segment attempts that never start a cycle. |
| unobservable | Cropped/occluded joints or incorrect view prevent a reliable decision. |
| unlabeled | Awaiting review; excluded from training. |

Elbow flare is not observable reliably from this side view; do not add a flare
label without a separate front/oblique view protocol. Record wall/incline/knee
variations separately: applying standard push-up thresholds to a different
variation needs validation. Choose body_alignment before depth
for multi-fault annotation and retain all visible faults in flags. Review a
subset with two independent annotators before using labels as ground truth.
