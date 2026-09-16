# SR-E1-BUDGET Protocol

## Purpose

Test one narrow hypothesis from `SR-FAIL-AUDIT`:

> The first `E_pending` target in `TOL1E5-P` may have failed `1e-5` because the per-fit Adam cap was too small, not because the target identity or scale was wrong.

This experiment is a fixed-state, first-half-step diagnostic. It is not a trajectory validation and cannot unlock `64/128/1024/8192`.

## Frozen Configuration

- Initial checkpoint: `assets/models/dco_lr1e3_300.pt`
- Grid and source assumptions: same as `server_short_tol_probe.py`
- Target: first physical `E_pending` target only
- Tolerance: `1e-5`
- Adam cap for this one `E` fit: `9000`
- H fit: expected zero-input, zero-update shortcut
- LBFGS closures: `0`
- Device: `cuda` on server if available
- Output directory: `evidence/server_resource_v1/first_e_budget_probe/`

## Success And Failure Meaning

- `PASS`: the first E target reaches `1e-5` within 9000 Adam. This supports a budget/optimizer bottleneck for the first strict half-step, but does not solve field accumulation.
- `FAIL`: the first E target still misses `1e-5` within 9000 Adam. This strengthens the optimization/expression-limit interpretation.
- `RESOURCE_LIMIT` or `INCOMPLETE`: keep现场; do not retry automatically.

## Constraints

- Do not resume the old `SR-SHORT-R2` failed weights.
- Do not alter old R2 evidence or thresholds.
- Do not run beyond the first accepted time layer.
- Do not start `64/128/1024/8192`.
- Record all updates under `lab_log`.

