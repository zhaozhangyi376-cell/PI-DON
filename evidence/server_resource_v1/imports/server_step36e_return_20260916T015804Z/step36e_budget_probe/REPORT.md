# SR-36E-BUDGET step-36 diagnostic

This is a one-step diagnostic from the last clean SR-64 checkpoint, not a 64-step validation.

- Status: `FAIL`; scientific_result: `DIAGNOSTIC_FAIL_STEP36`
- Source checkpoint: `evidence/server_resource_v1/strict64_probe/checkpoint_A.pt`
- Source accepted steps: `35`
- Accepted steps after replay: `35`
- New Adam updates: `30056`
- Step-36 E residual: `3.368137945800008e-05`
- Step-36 E updates: `30000`
- E crosses 1e-4: `{'updates': 290, 'loss': 9.630664135329425e-05}`
- E crosses 1e-5: `None`
- Long run unlocked: `False`

The old SR-64 failure raw is preserved and is not continued as a formal trajectory.
