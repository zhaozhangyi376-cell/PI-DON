# M2 Report - Direct 128 Queue Audit

- Action: `A-20260914T065013-9957817a`; lab_run_id: `287`
- `Residual128 PASS` means all 128 accepted time steps met the per-half residual gate.
- `Field gate PASS` additionally requires the registered field/probe checks; none passed here.

| Arm | Status | Residual128 | Field gate | Accepted | Adam | Closures | H R | E R | Max nMAE | Probe L2 max |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| A-R | FAIL | False | False | 33 | 10228 | 1200 | 9.967961762888484e-05 | 9.965224787875114e-05 | 6.496533195140788e-05 | 0.4227322475142845 |
| A-P | PASS | True | False | 128 | 56680 | 0 | 8.691448396190442e-05 | 9.982332368004672e-05 | 0.051269250161268265 | 0.13181396607443344 |
| B-R | PASS | True | False | 128 | 38127 | 0 | 9.992266290590722e-05 | 9.968860361505215e-05 | 0.050785114883489905 | 0.11881909099078715 |
| B-P | PASS | True | False | 128 | 44630 | 0 | 9.841101172563177e-05 | 9.943979027191016e-05 | 0.049254241513757416 | 0.06415318986054504 |

## Interpretation

- A-R failed at 33 accepted steps; its failed E residual is far above the strict gate.
- A-P, B-R and B-P all reached 128 residual-accepted steps.
- All 128-step arms fail the field gate because effective component nMAE is about 4.8% to 5.1%, above the 1% gate; source-outside waveform errors are also not all within 5%.
- Therefore M2 produces useful mechanism/optimizer evidence but does not unlock 1024/8192.

## Files

- Audit JSON: `evidence/direct_mechanism_v1/m2_audit.json`
- Runs: `evidence/direct_mechanism_v1/runs`

