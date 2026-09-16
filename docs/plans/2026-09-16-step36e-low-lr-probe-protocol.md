# SR-36E-LOWLR protocol

## Question

The SR-36E-BUDGET trace reached a best E residual of about `1.03e-5`,
slightly above the unchanged `1e-5` threshold, and showed late oscillation.
Can the same step-36 replay pass if the learning rate is lowered before any
new update?

## Fixed input

- Source run: `evidence/server_resource_v1/strict64_probe`
- Source checkpoint: clean rolling checkpoint at
  `phase=before_H`, `accepted_steps=35`, `current_time_layer=35`.
- Old SR-64 failure raw and SR-36E-BUDGET failure raw are preserved and not
  continued.

## Registered arms

Run at most two independent one-step diagnostics, both from the same clean
checkpoint:

1. `lr1e-4`, `max_inner=60000`
2. If the first arm fails, `lr5e-5`, `max_inner=60000`

Both keep `tol=1e-5`, `tol_mode=rel`, Adam only, no LBFGS.

## Interpretation

If an arm passes, the finding is diagnostic: the step-36 bottleneck is
learning-rate sensitive. It does not change the SR-64 result and does not
unlock 64/128/1024/8192.

If both arms fail, stop and inspect target scale, component residuals, and
representational limits instead of widening the same task again.

