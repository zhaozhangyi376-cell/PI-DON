"""Audit an interrupted S1 phase-1 run without doing more training."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import torch

from project_paths import PROJECT_DIR, configure
configure()

from pidon_recording import atomic_json_save, sha256_file


ROOT = PROJECT_DIR
OUT = ROOT / "evidence" / "direct_mechanism_v1" / "s1_phase1"
STAGE = ROOT / "evidence" / "direct_mechanism_v1" / "stage_status.json"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return display(value)
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def write_json(path: Path, data: dict[str, Any]) -> None:
    atomic_json_save(data, path)


def lab_run_ids() -> dict[str, Any]:
    path = ROOT / "records" / "lab_runs.jsonl"
    if not path.exists():
        return {"max_recorded_id": None, "contains_s1_phase1": False}
    rows = read_jsonl(path)
    contains = [
        row.get("id") for row in rows
        if "phase1_full_run.py" in str(row.get("cmd", ""))
        or "S1 complete phase-1" in str(row.get("note", ""))
    ]
    return {
        "max_recorded_id": max([int(row.get("id", 0)) for row in rows], default=0),
        "contains_s1_phase1": bool(contains),
        "s1_lab_run_ids": contains,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action-id", required=True)
    args = parser.parse_args()

    history = read_jsonl(OUT / "history.jsonl")
    last_history = history[-1] if history else None
    validation_rows = [row for row in history if "dev" in row]
    best_from_history = None
    if validation_rows:
        best_from_history = min(validation_rows, key=lambda row: row["dev"]["macro_nmae_mean"])

    best_path = OUT / "best.pt"
    best_checkpoint = None
    if best_path.exists():
        ckpt = torch.load(best_path, map_location="cpu", weights_only=False)
        best_checkpoint = {
            "epoch": ckpt.get("epoch"),
            "updates": ckpt.get("updates"),
            "best": ckpt.get("best"),
            "microbatch": ckpt.get("microbatch"),
            "history_len_in_checkpoint": len(ckpt.get("hist", [])),
            "sha256": sha256_file(best_path),
            "bytes": best_path.stat().st_size,
        }

    files = {}
    for name in (
        "manifest.json", "preflight.json", "train_dev_data.npz",
        "train_dev_specs.json", "blind_specs.json", "history.jsonl",
        "best.pt", "last.pt", "summary.json", "audit.json",
    ):
        path = OUT / name
        files[name] = {
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else None,
            "sha256": sha256_file(path) if path.exists() and path.stat().st_size < 400 * 1024 * 1024 else None,
        }

    completed = bool((OUT / "summary.json").exists() and (OUT / "last.pt").exists())
    interrupted = not completed
    planned_updates = 25_000
    last_updates = int(last_history.get("updates", 0)) if last_history else 0
    missing_updates = max(0, planned_updates - last_updates)
    audit = {
        "schema": "pidon-s1-interrupted-audit-v1",
        "action_id": args.action_id,
        "audit_lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
        "status": "INCOMPLETE" if interrupted else "PASS",
        "scientific_result": "INCOMPLETE" if interrupted else "SEE_SUMMARY",
        "reason": "training_process_not_live_and_no_terminal_summary_or_last_checkpoint" if interrupted else "terminal_outputs_present",
        "planned_epochs": 1000,
        "planned_updates": planned_updates,
        "history_rows": len(history),
        "last_history": last_history,
        "validation_rows": len(validation_rows),
        "best_from_history": best_from_history,
        "best_checkpoint": best_checkpoint,
        "missing_updates_to_planned": missing_updates,
        "has_terminal_summary": (OUT / "summary.json").exists(),
        "has_last_checkpoint": (OUT / "last.pt").exists(),
        "has_blind_data": (OUT / "blind_data").exists(),
        "lab_ledger": lab_run_ids(),
        "recovery_assessment": {
            "production_resume_eligible": False,
            "reason": (
                "latest model/optimizer/RNG state at epoch 937 was not saved; "
                "best.pt is a dev-selected checkpoint at epoch 930 and resuming "
                "from it would repeat updates and exceed the registered 25000-update S1 budget"
            ),
        },
        "files": files,
    }
    write_json(OUT / "interrupted_audit.json", jsonable(audit))

    lines = [
        "# S1 Report - Interrupted Phase-1 Run",
        "",
        f"- Action: `{args.action_id}`; audit lab_run_id: `{os.environ.get('PIDON_LAB_RUN_ID')}`",
        "- Status: `INCOMPLETE`; scientific_result: `INCOMPLETE`.",
        "- No source/probe metrics are applicable: this was phase-1 curl-operator training, not a time-domain source run.",
        "",
        "## What Happened",
        "",
        f"- Planned: `1000` epochs / `{planned_updates}` Adam updates.",
        f"- Last history row: epoch `{last_history.get('epoch') if last_history else None}`, updates `{last_updates}`.",
        f"- Missing to planned run: `{missing_updates}` updates.",
        f"- Best saved checkpoint: epoch `{(best_checkpoint or {}).get('epoch')}`, updates `{(best_checkpoint or {}).get('updates')}`.",
        f"- Best dev macro nMAE: `{((best_checkpoint or {}).get('best') or {}).get('dev_macro_nmae')}`.",
        f"- Best dev relL2 p90: `{((best_checkpoint or {}).get('best') or {}).get('dev_global_rel_l2_p90')}`.",
        f"- Best dev Eq.(5) MRE mean: `{((best_checkpoint or {}).get('best') or {}).get('dev_macro_mre_eq5_mean')}`.",
        "",
        "## Judgment",
        "",
        "- This is not a completed S1 training run and must not be used as the registered blind-test result.",
        "- There is no `last.pt`, no terminal `summary.json`, and no blind migration evaluation.",
        "- The latest epoch-937 model state is unavailable. The saved `best.pt` is dev-selected at epoch 930, so production resume is not certified.",
        "- Restarting or resuming from `best.pt` would repeat updates and change the registered cost accounting; this audit therefore preserves the failure site instead of spending a new budget.",
        "",
        "## Files",
        "",
        f"- Audit JSON: `{display(OUT / 'interrupted_audit.json')}`",
        f"- History JSONL: `{display(OUT / 'history.jsonl')}`",
        f"- Best checkpoint: `{display(OUT / 'best.pt')}`",
        "",
    ]
    (OUT / "S1_REPORT.md").write_text("\n".join(lines), encoding="utf-8")

    if STAGE.exists():
        stage = json.loads(STAGE.read_text(encoding="utf-8"))
    else:
        stage = {"schema": "direct-mechanism-stage-status-v1"}
    stage["S1"] = {
        "schema": "pidon-s1-interrupted-audit-v1",
        "status": "INCOMPLETE",
        "scientific_result": "INCOMPLETE",
        "reason": audit["reason"],
        "planned_updates": planned_updates,
        "last_recorded_updates": last_updates,
        "best_checkpoint": best_checkpoint,
        "recovery_eligible": False,
        "report": display(OUT / "S1_REPORT.md"),
        "audit": display(OUT / "interrupted_audit.json"),
    }
    write_json(STAGE, stage)
    print(json.dumps({
        "status": audit["status"],
        "scientific_result": audit["scientific_result"],
        "last_epoch": last_history.get("epoch") if last_history else None,
        "last_updates": last_updates,
        "best_checkpoint": best_checkpoint,
        "recovery_eligible": False,
        "report": display(OUT / "S1_REPORT.md"),
        "audit": display(OUT / "interrupted_audit.json"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
