# SR-36E-BUDGET step-36 diagnostic

This is a one-step diagnostic from the last clean SR-64 checkpoint, not a 64-step validation.

- Status: `PASS`; scientific_result: `DIAGNOSTIC_PASS_STEP36`
- Source checkpoint: `evidence/server_resource_v1/strict64_probe/checkpoint_A.pt`
- Source accepted steps: `35`
- Original lr / diagnostic lr: `0.0003` / `0.0001`
- Diagnostic max_inner: `60000`
- Accepted steps after replay: `36`
- New Adam updates: `5350`
- Step-36 E residual: `9.416872713326286e-06`
- Step-36 E updates: `5305`
- E crosses 1e-4: `{'updates': 410, 'loss': 9.99928088276647e-05}`
- E crosses 1e-5: `{'updates': 5305, 'loss': 9.41687267186353e-06}`
- Long run unlocked: `False`

The old SR-64 failure raw is preserved and is not continued as a formal trajectory.
