# SR-128-LOWLR-CLEAN protocol

## Question

Clean low-lr64 passed the registered 64-step field gate. Can the same
low-learning-rate configuration continue as one clean trajectory from step 0
to 128 and pass the 128-step field gate?

## Fixed configuration

- Source checkpoint: `assets/models/dco_lr1e3_300.pt`
- `tol=1e-5`, `tol_mode=rel`
- `lr=1e-4`
- `max_inner=60000`
- `target_steps=128`
- Adam only, no LBFGS
- Overall Adam cap: `1000000`

## Success criterion

Delivery PASS means the clean trajectory reaches 128 accepted steps and writes
summary, report, manifest, steps, and checkpoint evidence. Scientific
`PASS_128` requires the registered 128-step field gate to pass.

## Boundary

This still does not authorize 1024/8192 until the returned 128 evidence is
audited locally and the next long-run task is separately registered.

