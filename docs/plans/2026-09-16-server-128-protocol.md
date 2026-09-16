# SR-128 protocol

Date: 2026-09-16.

## Question

If SR-64 passes the 64-step field gate, can the same strict online configuration continue to 128 full steps and pass the 128-step field gate?

## Frozen configuration

- Initial checkpoint: `assets/models/dco_lr1e3_300.pt`.
- Online solver: existing `pidon_solve`/`server_short_tol_probe` path.
- Device: CUDA on the GV100 server.
- Residual gate: relative target residual `tol=1e-5`.
- Learning rate: `3e-4`.
- Target steps: `128`, continuing past 64 only if the 64-step field gate passes.
- Per-fit cap: `9000` Adam updates.
- Overall cap: `320000` Adam updates.
- Output directory: `evidence/server_resource_v1/strict128_probe`.
- This task must run through `lab_log.py run` and a registered harness action.

## Success criteria

Delivery is `PASS` only if the script writes `summary.json`, `REPORT.md`, `manifest.json`, JSONL rows, checkpoints, and failure现场 if applicable.

Scientific result for this task is `PASS_128` only if:

- 128 complete steps are accepted under the frozen residual gate.
- The step-64 field gate passes.
- The step-128 field gate passes: global weighted relative L2 <= 5%, valid six-component nMAE <= 1%, weak-reference absolute gates pass, and fixed source amplitude error <= 1e-3.

This is not a 1024/8192 gate. A `PASS_128` result only authorizes a separately registered 1024-step probe after local audit. A failure or resource limit stops this branch and preserves the failure现场.

## Non-goals

- Do not resume or overwrite `strict64_probe`.
- Do not use exact Yee controls as DCO performance.
- Do not modify thresholds after seeing results.
- Do not start 1024 or 8192 from this action.
