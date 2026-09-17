# SR-128-PAPER-TOL-DIAG protocol

## Question
With the clean low-learning-rate setup, what happens if the per-half-step residual
threshold is the paper-like `1e-4` instead of the stricter `1e-5` used by the
clean64/clean128 branch?

## Why this is independent
`SR-128-LOWLR-CLEAN` completed 128 accepted steps but failed the registered
128 field gate due to Ex/Ey component nMAE. This diagnostic does not modify that
result. It runs a separately registered trajectory to measure speed/cost and
field drift under the looser residual threshold.

## Frozen configuration
- Start from the original DCO checkpoint, not from failed weights.
- `lr=1e-4`
- `tol=1e-4`
- `target_steps=128`
- `per_fit_cap=60000`
- `overall_adam_cap=1000000`
- strict stop remains enabled.
- Output: `evidence/server_resource_v1/paper_tol128_diag`

## Success and interpretation
Delivery PASS means the script completes and writes summary/report/manifest.
Scientific interpretation is diagnostic only:
- If 128 field gate fails, this supports that `1e-4` is too loose for our
  current implementation even if residual steps are accepted.
- If 128 field gate passes, it authorizes local audit and a separate discussion,
  but it still does not automatically authorize 1024/8192.

Do not change registered gates, do not delete failures, and do not count this as
a paper-level PASS without local review.
