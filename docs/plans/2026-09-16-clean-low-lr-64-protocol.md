# SR-64-LOWLR-CLEAN protocol

## Question

The mixed-history low-learning-rate diagnostics crossed the original SR-64
failure point and reached accepted step 64 with healthy field metrics. Can the
same low-learning-rate setting reach 64 from step 0 as one clean trajectory?

## Fixed configuration

- Source checkpoint: `assets/models/dco_lr1e3_300.pt`
- `tol=1e-5`, `tol_mode=rel`
- `lr=1e-4`
- `max_inner=60000`
- `target_steps=64`
- Adam only, no LBFGS
- Overall Adam cap: `500000`

## Success criterion

Delivery PASS means the clean trajectory reaches 64 accepted steps and writes
summary, report, manifest, steps, and checkpoint evidence. Scientific `PASS_64`
requires the registered 64-step field gate to pass; otherwise the action is a
delivery FAIL or scientific FAIL according to the saved summary.

## Boundary

This is the first clean low-learning-rate 64 candidate. It does not unlock
128/1024/8192 unless the 64 field gate passes and the returned evidence is
locally audited.

