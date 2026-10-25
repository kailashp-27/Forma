# Squat label specification — side view, v1

Camera: fixed side view, approximately hip height, full body in frame. Use the
same footwear/camera setup across a labeled set. A visible standing posture
starts the rep; the rep ends on return to standing. The configured knee-angle
thresholds are experimental image-space proxies, not individualized clinical
targets. Record the configuration version with evaluation results.

| Label | Annotation decision |
| --- | --- |
| good | Entire rep observable, controlled descent/ascent, configured knee-angle bottom reached, no flagged excessive torso lean. |
| torso_lean | Torso lean crosses configured 55° from vertical while the hip, shoulder, knee and ankle are confidently visible. Review the full sequence rather than a single noisy frame. |
| depth | Person completes a recognized cycle but reverses before the configured target knee angle (100° in the initial config). The engine's counting threshold is more permissive than the form target. Extremely shallow attempts that never trigger a cycle need manual segmentation. |
| unobservable | Occlusion, wrong view, cropped joints, multiple overlapping people, or pose ambiguity prevents a reliable decision. |
| unlabeled | Recording awaits human review; excluded from training. |

For multi-fault reps, choose the most severe visible label, documenting a fixed
priority before labeling. Keep secondary faults in flags. Do not label knee
valgus from this side view: that requires a separate front-view experiment and
its own visibility/threshold validation. A pose-only reviewer cannot infer
pain, loading safety, or a person's anatomical limits. Have a second reviewer
independently label a subset and resolve disagreements before training.
