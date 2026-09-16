# SR-48-64-LOWLR protocol

## Question

The low-learning-rate local window from accepted step 35 to 48 passed. Can the
same diagnostic branch continue from the clean accepted-step-48 checkpoint to
accepted step 64?

## Fixed input

- Source run: `evidence/server_resource_v1/step36_48_low_lr_window`
- Clean restart point: rolling checkpoint at
  `phase=before_H`, `accepted_steps=48`, `current_time_layer=48`.
- Do not continue failed checkpoints or modify SR-64.

## Frozen diagnostic configuration

- Continue until `accepted_steps=64`, i.e. at most 16 new full steps.
- `lr=1e-4`, `max_inner=60000`, `tol=1e-5`, `tol_mode=rel`.
- Adam only, no LBFGS.
- Print inner-fit progress every 500 Adam updates and one row after each full
  accepted or failed physical step.

## Interpretation

This is a local mixed-history diagnostic, not a formal from-zero 64-step gate.
If it reaches 64 and field metrics remain healthy, it justifies registering a
clean low-learning-rate 64 run from step 0. It still does not unlock 128, 1024,
or 8192 by itself.

