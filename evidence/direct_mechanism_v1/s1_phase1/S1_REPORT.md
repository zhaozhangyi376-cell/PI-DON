# S1 Report - Interrupted Phase-1 Run

- Action: `A-20260914T102345-10b45e87`; audit lab_run_id: `288`
- Status: `INCOMPLETE`; scientific_result: `INCOMPLETE`.
- No source/probe metrics are applicable: this was phase-1 curl-operator training, not a time-domain source run.

## What Happened

- Planned: `1000` epochs / `25000` Adam updates.
- Last history row: epoch `937`, updates `23425`.
- Missing to planned run: `1575` updates.
- Best saved checkpoint: epoch `930`, updates `23250`.
- Best dev macro nMAE: `0.02194540502333757`.
- Best dev relL2 p90: `0.05491862156735433`.
- Best dev Eq.(5) MRE mean: `1.8043889096694798`.

## Judgment

- This is not a completed S1 training run and must not be used as the registered blind-test result.
- There is no `last.pt`, no terminal `summary.json`, and no blind migration evaluation.
- The latest epoch-937 model state is unavailable. The saved `best.pt` is dev-selected at epoch 930, so production resume is not certified.
- Restarting or resuming from `best.pt` would repeat updates and change the registered cost accounting; this audit therefore preserves the failure site instead of spending a new budget.

## Files

- Audit JSON: `evidence/direct_mechanism_v1/s1_phase1/interrupted_audit.json`
- History JSONL: `evidence/direct_mechanism_v1/s1_phase1/history.jsonl`
- Best checkpoint: `evidence/direct_mechanism_v1/s1_phase1/best.pt`
