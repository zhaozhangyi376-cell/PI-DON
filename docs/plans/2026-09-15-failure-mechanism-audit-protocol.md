# SR-FAIL-AUDIT Protocol

## Purpose

Answer why the current stage-2 mechanism is blocked after the server resource batch:

- Old M2 arms can complete 128 residual-accepted steps under `tol=1e-4`, but fail field gates.
- Server `TOL1E5-P` fails at the first `E_pending` candidate under `tol=1e-5`.

This is a read-only diagnostic task. It must not perform parameter updates, start a new trajectory, resume old failed weights, or unlock `64/128/1024/8192`.

## Frozen Inputs

- `evidence/direct_mechanism_v1/runs/A_P/summary.json`
- `evidence/direct_mechanism_v1/runs/A_P/steps.jsonl`
- `evidence/direct_mechanism_v1/runs/B_R/summary.json`
- `evidence/direct_mechanism_v1/runs/B_R/steps.jsonl`
- `evidence/direct_mechanism_v1/runs/B_P/summary.json`
- `evidence/direct_mechanism_v1/runs/B_P/steps.jsonl`
- `evidence/direct_mechanism_v1/benefit/B_R2/summary.json`
- `evidence/direct_mechanism_v1/benefit/B_R2/steps.jsonl`
- `evidence/server_resource_v1/imports/server_batch2_return_r2_full_20260915T141612Z/short_tol_probe_r2/summary.json`
- `evidence/server_resource_v1/imports/server_batch2_return_r2_full_20260915T141612Z/short_tol_probe_r2/steps.jsonl`

## Required Outputs

Write new evidence under:

`evidence/server_resource_v1/failure_mechanism_audit/`

Required files:

- `audit.json`: machine-readable comparison and conclusion.
- `failure_compare.csv`: compact table for presentation.
- `residual_vs_field.png`: residual and field timeline plot.
- `REPORT.md`: Chinese explanation, separating strict scores from diagnostics.
- `manifest.json`: action id, lab run id, source hashes and protocol hash.

## Decision Rules

The audit may classify causes as:

- `interface_recording_unlikely`: the compared first E target has matching target scale and loss identity between old M2 and `TOL1E5-P`.
- `optimization_or_expression_limit`: the same first E target improves below `1e-4` but stalls above `1e-5` after the frozen per-fit cap.
- `propagation_field_accumulation`: old residual-accepted trajectories later cross field/probe gates.
- `incomplete`: required rows or identities are missing.

## Constraints

- New Adam updates: exactly `0`.
- New LBFGS closures: exactly `0`.
- Do not revise old PASS/FAIL status.
- Do not change thresholds after reading results.
- Do not count exact Yee or diagnostic controls as DCO results.
- Do not start `64/128/1024/8192` from this audit.

