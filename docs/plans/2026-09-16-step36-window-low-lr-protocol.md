# SR-36-48-LOWLR protocol

## Question

SR-36E-LOWLR showed that the first SR-64 failure point can pass when the
learning rate is lowered from `3e-4` to `1e-4`. Does that repair persist over a
small local continuation window, or does the trajectory fail immediately again?

## Fixed input

- Source run: `evidence/server_resource_v1/strict64_probe`
- Clean restart point: rolling checkpoint at
  `phase=before_H`, `accepted_steps=35`, `current_time_layer=35`.
- Do not continue any failed checkpoint or failure raw.

## Frozen diagnostic configuration

- Start from the clean step-35 checkpoint.
- Continue until `accepted_steps=48`, i.e. at most 13 new full steps.
- `lr=1e-4`, `max_inner=60000`, `tol=1e-5`, `tol_mode=rel`.
- Adam only, no LBFGS.
- Print inner-fit progress every 500 Adam updates and one row after each full
  accepted or failed physical step.

## Interpretation

This is a diagnostic continuation from a mixed learning-rate history, not a
paper-level strict 64/128 gate. Passing this window does not change SR-64, does
not certify a full trajectory, and does not unlock 1024/8192. It only justifies
registering a bounded low-learning-rate 64-step variant.

If this window fails, stop and inspect the new failure现场 rather than widening
the window.

