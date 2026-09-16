# SR-MICRO16 protocol

Date: 2026-09-15.

## Question

SR-MICRO4 showed that the strict `tol=1e-5` online scheme can complete 4 full steps with a 9000 Adam cap per half-step. Can the same fixed configuration remain stable through 16 full steps?

## Frozen configuration

- Initial checkpoint: `assets/models/dco_lr1e3_300.pt`.
- Online solver: existing `pidon_solve`/`server_short_tol_probe` path.
- Device: CUDA on the GV100 server.
- Residual gate: relative target residual `tol=1e-5`.
- Learning rate: `3e-4`.
- Target steps: `16`.
- Micro field gate: evaluate the accepted state at step 16.
- Per-fit cap: `9000` Adam updates.
- Overall cap: `288000` Adam updates.
- Output directory: `evidence/server_resource_v1/micro16_strict_probe`.
- This task must run through `lab_log.py run` and a registered harness action.

## Success criteria

Delivery is `PASS` only if the script writes `summary.json`, `REPORT.md`, `manifest.json`, JSONL rows, checkpoints, and failure现场 if applicable.

Scientific result for this task is `PASS_MICRO` only if:

- 16 complete steps are accepted under the frozen residual gate.
- The step-16 micro field gate passes: global weighted relative L2 <= 5%, valid six-component nMAE <= 1%, weak-reference absolute gates pass, and fixed source amplitude error <= 1e-3.

This is not a 64/128/1024/8192 gate. A `PASS_MICRO` result only authorizes a separately registered 32 or 64 step probe after local audit. A failure stops this branch and preserves the failure现场.

## Non-goals

- Do not resume or overwrite `micro4_strict_probe`.
- Do not use exact Yee controls as DCO performance.
- Do not modify thresholds after seeing results.
- Do not start 64, 128, 1024, or 8192 from this action.
