# SR-MICRO4 protocol

Date: 2026-09-15.

## Question

Given that SR-E1-BUDGET showed the identical first `E_pending` target can reach the strict `1e-5` residual gate in 3769 Adam updates, can the same old `dco_lr1e3_300.pt` initialization complete a tiny strict online trajectory of 4 full steps when each half-step is allowed a pre-registered 9000 Adam cap?

## Frozen configuration

- Initial checkpoint: `assets/models/dco_lr1e3_300.pt`.
- Online solver: existing `pidon_solve`/`server_short_tol_probe` path.
- Device: CUDA on the GV100 server.
- Residual gate: relative target residual `tol=1e-5`.
- Learning rate: `3e-4`.
- Target steps: `4`.
- Micro field gate: evaluate the accepted state at step 4.
- Per-fit cap: `9000` Adam updates.
- Overall cap: `72000` Adam updates.
- Output directory: `evidence/server_resource_v1/micro4_strict_probe`.
- This task must run through `lab_log.py run` and a registered harness action.

## Success criteria

Delivery is `PASS` only if the script writes `summary.json`, `REPORT.md`, `manifest.json`, JSONL rows, checkpoints, and failure现场 if applicable.

Scientific result for this task is `PASS_MICRO` only if:

- 4 complete steps are accepted under the frozen residual gate.
- The step-4 micro field gate passes: global weighted relative L2 <= 5%, valid six-component nMAE <= 1%, weak-reference absolute gates pass, and fixed source amplitude error <= 1e-3.

This is not a 64/128/1024/8192 gate. A `PASS_MICRO` result only authorizes a separately registered 8-16 step probe. A failure stops this branch and preserves the failure现场.

## Non-goals

- Do not resume or overwrite `short_tol_probe_r2`.
- Do not use exact Yee controls as DCO performance.
- Do not modify thresholds after seeing results.
- Do not start 64, 128, 1024, or 8192 from this action.
