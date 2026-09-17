# Briefing and Paper-Explicit Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use $superpower-subagents (recommended) or $superpower-executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking via update_plan.

**Goal:** Produce auditable operator/PEC evidence, a detailed editable briefing deck, and an isolated paper-explicit phase-1 reference with a server-ready training bundle.

**Architecture:** Keep current evidence read-only in the main project, generate new zero-update diagnostics in a fresh evidence directory, and place the independent reference implementation under `_01`. Build all briefing figures from saved evidence or deterministic scripts and assemble them into an editable PPTX.

**Tech Stack:** Python 3.11, PyTorch, NumPy, Matplotlib, unittest, PptxGenJS, PowerShell.

---

### Task 1: Register and freeze the work

**Files:**
- Modify: `project/plan.json`
- Modify: `PLAN.md`
- Modify: `STATUS.md`
- Create: `docs/plans/2026-09-17-fixed-operator-and-pec-protocol.md`

- [ ] Add independent tasks `BRIEF-OP`, `BRIEF-PEC`, `BRIEF-DECK`, and `PAPER01-S1` without reopening failed second-stage tasks.
- [ ] Freeze zero-update inputs, output directories, model identities, and diagnostic-only interpretation.
- [ ] Run `py -3.11 run.py project_harness check`; expected PASS.

### Task 2: Build the fixed-weight operator audit with TDD

**Files:**
- Create: `tests/test_briefing_operator_audit.py`
- Create: `scripts/analysis/briefing_operator_audit.py`
- Create: `evidence/briefing_20260917/operator_audit/*`

- [ ] Write tests that require deterministic test specifications, spatially varying coordinate channels, unchanged model hashes, zero updates, and 3x4 field panels.
- [ ] Run `py -3.11 -m unittest tests.test_briefing_operator_audit -v`; expected failure because the module is absent.
- [ ] Implement deterministic forward-only comparison for old DCO, S1R, and seeded random architecture; read existing SR-COMPARE rows rather than repeat unavailable evidence.
- [ ] Pre-register `BRIEF-OP`, run it through `lab_log`, and finish the action with the raw JSON, manifest, report, and figures.
- [ ] Re-run the focused test and verify output hashes and `parameter_updates=0`.

### Task 3: Build the PEC audit with TDD

**Files:**
- Create: `tests/test_briefing_pec_audit.py`
- Create: `scripts/analysis/briefing_pec_audit.py`
- Create: `evidence/briefing_20260917/pec_audit/*`

- [ ] Write tests for tangential E masks on all six faces, curl-E insertion support, and a toy gradient comparison before implementation.
- [ ] Run the focused test; expected failure because the audit module is absent.
- [ ] Implement a CPU-only audit that imports production `Solver`, records actual slices, computes the gradient-support demonstration, and renders boundary diagrams.
- [ ] Pre-register `BRIEF-PEC`, run via `lab_log`, finish the action, and verify no production source changed.

### Task 4: Create the independent `_01` reference with TDD

**Files:**
- Create: `_01/README.md`
- Create: `_01/paper_contract.json`
- Create: `_01/src/paper01/model.py`
- Create: `_01/src/paper01/data.py`
- Create: `_01/src/paper01/metrics.py`
- Create: `_01/src/paper01/runner.py`
- Create: `_01/train_phase1.py`
- Create: `_01/tests/test_contract.py`
- Create: `_01/tests/test_data.py`
- Create: `_01/tests/test_model.py`
- Create: `_01/tests/test_runner.py`

- [ ] Write tests requiring explicit/derived/assumed classification, actual varying coordinates, `k dot E0=0`, analytic curl consistency, component-local normalization, four-level shape preservation, constant Adam learning rate, and fresh output refusal.
- [ ] Run `_01` tests and observe expected import failures.
- [ ] Implement the smallest modules satisfying those tests. Keep all unresolved paper details visible in `paper_contract.json`.
- [ ] Run CPU smoke with 8 samples, grid 8, one update, and a new temporary evidence directory; expect a complete manifest and finite loss.
- [ ] Run all `_01` tests and record exact command/output.

### Task 5: Prepare the server bundle

**Files:**
- Create: `tools/build_paper01_server_bundle.py`
- Create: `_01/server/install.ps1`
- Create: `_01/server/run_preflight.ps1`
- Create: `_01/server/run_full.ps1`
- Create: `paper01_server_bundle.zip`

- [ ] Write a bundle test that rejects old `.pt` files, old evidence, and absolute local paths.
- [ ] Run the bundle test and observe failure before the builder exists.
- [ ] Implement the builder and PowerShell scripts. The preflight performs five updates; the full command uses 32^3/1000/1000 epochs/effective batch32/constant1e-4.
- [ ] Build and inspect the ZIP file list and hashes.

### Task 6: Generate detailed figures and PPTX

**Files:**
- Create: `汇报素材/素材索引.md`
- Create: `汇报素材/generated/*.png`
- Create: `汇报素材/build_pidon_briefing.js`
- Create: `汇报素材/PI-DON复现阶段汇报_20260917.pptx`

- [ ] Inventory every existing image and mark keep/context-only/replace with a scientific reason.
- [ ] Generate diagrams for Maxwell-to-Yee flow, DCO tensor flow, U-Net dimensions, phase-1 sample construction, normalization, Algorithm 1 half-steps, PEC degrees of freedom, metrics, and evidence decision tree.
- [ ] Generate result charts only from audited JSON/JSONL.
- [ ] Build a 25+ slide editable deck with one visual per slide and source footers.
- [ ] Extract text with markitdown, render all slides, inspect a thumbnail sheet, fix at least one discovered visual issue, then re-render affected slides.

### Task 7: Final verification and handoff

**Files:**
- Modify: `PLAN.md`
- Modify: `STATUS.md`
- Create: `evidence/briefing_20260917/FINAL_REPORT.md`

- [ ] Run focused tests, `_01` tests, project harness check, and `git diff --check`.
- [ ] Record what is complete, what is diagnostic, what remains NOT_RUN, and the exact server commands.
- [ ] Do not mark the paper mechanism reproduced until the returned 1000-epoch evidence is ingested and independently audited.
