"""Independent audit for the bounded mechanism experiment."""
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVID = ROOT / "evidence" / "mechanism_1h_v2"

def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def main() -> None:
    manifest = json.loads((EVID / "manifest.json").read_text(encoding="utf-8"))
    status = json.loads((EVID / "stage_status.json").read_text(encoding="utf-8"))
    arms = {}
    for arm, st in status["status"].items():
        d = EVID / "runs" / arm.replace("-", "_")
        rows_p = d / "steps.jsonl"
        rows = [json.loads(x) for x in rows_p.read_text(encoding="utf-8").splitlines()] if rows_p.exists() else []
        accepted = [r for r in rows if r.get("accepted")]
        threshold = 1e-4 if arm.startswith("S-") else (1e-3 if arm.startswith("X-") else None)
        violations = []
        if threshold is not None:
            for r in accepted:
                for fit in (r.get("fit_H") or {}, r.get("fit_E") or {}):
                    rr = fit.get("residual_ratio")
                    if rr is not None and rr >= threshold:
                        violations.append({"step": r.get("step"), "R": rr})
        last = accepted[-1] if accepted else (rows[-1] if rows else None)
        arms[arm] = {
            "status": st,
            "rows": len(rows),
            "accepted_steps": len(accepted),
            "actual_updates": sum((r.get("fit_H") or {}).get("n_updates", 0) + (r.get("fit_E") or {}).get("n_updates", 0) for r in rows),
            "threshold": threshold,
            "accepted_threshold_violations": violations,
            "last_residuals": {"H": (last.get("fit_H") or {}).get("residual_ratio") if last else None,
                               "E": (last.get("fit_E") or {}).get("residual_ratio") if last else None},
            "last_six_component_nmae": {k: v.get("nmae") for k, v in ((last.get("six_component_metrics") or {}).get("components") or {}).items()} if last else {},
            "source_probe_Ez": last.get("source_probe_Ez") if last else None,
            "source_outside_probes": last.get("source_outside_probes") if last else None,
            "steps_sha256": sha256(rows_p) if rows_p.exists() else None,
        }
    out = {"schema": "mechanism-1h-audit-v1", "experiment_id": manifest.get("experiment_id"),
           "started_at": status.get("started_at"), "training_deadline": status.get("training_deadline"),
           "final_deadline": status.get("deadline"), "arms": arms,
           "old_review_present": (ROOT / "evidence" / "mechanism_decision_v1_review" / "REVIEW.md").exists()}
    (EVID / "audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
