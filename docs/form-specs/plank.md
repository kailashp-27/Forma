# Plank label specification — side view, v1

Camera: fixed side view showing shoulders, hips and ankles. Place the camera
approximately perpendicular to the body rather than above the floor. A hold
starts only after the body is visible and aligned; time outside the valid
posture must not count. Export complete holds or fixed windows, keeping
windows from one person in the same split.

| Label | Annotation decision |
| --- | --- |
| good | Shoulder–hip–ankle projected angle stays at or above configured 165° while the person holds the selected plank variation. |
| body_alignment | Projected shoulder–hip–ankle angle falls below 165° with clearly visible joints. Includes sag and pike in one class. |
| unobservable | Shoulder, hip or ankle is cropped/occluded; pose confidence is low; view is incorrect. |
| unlabeled | Awaiting review; excluded from training. |

Do not infer neutral spinal loading from the 2D alignment score. A bent-knee
plank changes the geometry and needs variation-specific joints/thresholds;
the present ankle-based rules are intended for a straight-leg plank. The hold
timer is cumulative valid posture time, not proof of a continuous unbroken
hold. Mark interruptions when evaluating continuous-hold readiness. Annotate
short transitions separately from sustained alignment faults and agree on a
minimum duration before collecting data. Use a second reviewer on a subset.
