# SR-36E-BUDGET protocol

## Question

Can the SR-64 first failing physical step, step 36, pass the same strict
`tol=1e-5` residual gate if the per-half-step Adam budget is increased before
the run begins?

## Fixed evidence input

- Source run: `evidence/server_resource_v1/strict64_probe`
- Clean restart point: the rolling checkpoint whose state is
  `phase=before_H`, `accepted_steps=35`, `current_time_layer=35`.
- The terminal failed checkpoint and `failure_raw_000036_attempt_1.pt` are
  preserved as old failure evidence and are not continued.

## Frozen diagnostic configuration

- Initial network lineage: inherited from SR-64 checkpoint.
- Threshold: `tol=1e-5`, `tol_mode=rel`.
- Optimizer: Adam with `lr=3e-4`; no LBFGS.
- New per-fit cap: `30000` Adam updates, registered before any update.
- Target: exactly one physical step, from accepted step 35 to accepted step 36.

## Success criterion

Delivery PASS means the diagnostic script completed and wrote summary, report,
manifest, steps log, and checkpoint or failure raw evidence.

Scientific diagnostic PASS means the replayed step 36 full transaction is
accepted under the unchanged residual threshold. This does not unlock 64, 128,
1024, or 8192; it only supports the explanation that the SR-64 failure point
was budget-sensitive.

## Failure handling

If step 36 still fails under the registered 30000 cap, stop this branch, keep
the new failure现场, and do not widen the cap inside the same action. The next
independent task should inspect the loss trace and decide whether the failure
looks like target-scale/representation/optimizer-state behavior.

