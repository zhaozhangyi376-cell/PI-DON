# SR-64-LOWLR-RANDOM protocol

## Question

Under the clean low-learning-rate strict online recipe, can a randomly initialized
DCO complete the same 64-step field gate, and at what cost?

## Why this is needed

`SR-64-LOWLR-CLEAN` shows the pretrained DCO can pass a clean 64-step field gate
with `lr=1e-4` and `tol=1e-5`. This diagnostic measures whether that result
depends on the pretrained checkpoint or whether online re-fitting alone is
sufficient.

## Frozen configuration

- Start from `init=random`; do not use failed weights.
- `lr=1e-4`
- `tol=1e-5`
- `target_steps=64`
- `per_fit_cap=60000`
- `overall_adam_cap=1000000`
- strict stop remains enabled.
- Output: `evidence/server_resource_v1/random_low_lr64`

## Interpretation

Delivery PASS means the diagnostic writes complete evidence. Scientific
interpretation is comparative only:

- If random fails before 64 or costs much more than pretrained, this supports a
  practical pretraining benefit under the clean strict recipe.
- If random passes with similar or lower cost, the claimed pretraining benefit
  remains unsupported for this branch.

This task does not authorize 128/1024/8192. It must preserve all failure
evidence and must not change registered field gates.
