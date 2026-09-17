# SR-128-LOWLR-RANDOM protocol

## Question

After `SR-64-LOWLR-RANDOM` passed the same 64-step field gate at lower cost than
the pretrained clean64 run, can random initialization also reach 128 complete
steps, and does it pass or fail the same 128-step field gate?

## Why this is the next bounded step

`SR-128-LOWLR-CLEAN` failed at 128 because Ex/Ey component nMAE exceeded 1% while
global Q stayed below 5%. `SR-64-LOWLR-RANDOM` shows that the 64-step success does
not require pretraining. This task separates two possibilities:

- the 128 Ex/Ey failure is a common propagation/normalization issue independent
  of initialization;
- or the random trajectory behaves differently enough to change the 128 field
  gate result.

## Frozen configuration

- Start from `init=random`; do not use failed weights.
- `lr=1e-4`
- `tol=1e-5`
- `target_steps=128`
- `per_fit_cap=60000`
- `overall_adam_cap=1000000`
- strict stop remains enabled.
- Output: `evidence/server_resource_v1/random_low_lr128`

## Interpretation

Delivery PASS means the diagnostic writes complete evidence. `PASS_128` requires
128 complete accepted steps and the registered 128-step field gate to pass.

Even if this passes, it only authorizes local audit and a new decision about
whether a separately registered 1024 probe is justified. It does not authorize
8192 directly. A FAIL or RESOURCE_LIMIT preserves the现场 and stops this branch.
