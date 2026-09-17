"""Versioned review coverage; never treats syntax/tests as source review."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PARENT_FULL = """
lab_log.py
tools/project_harness.py
tools/build_paper01_ablation_bundle.py
tools/ingest_paper01_return.py
tools/review_dco_pretraining.py
scripts/experiments/server_compute_probe.py
scripts/experiments/phase1_full_run.py
scripts/experiments/phase1_full_run_s1r.py
tests/test_pidon_contract_v4.py
scripts/analysis/direct_m2_audit.py
scripts/analysis/direct_final_judgment.py
scripts/experiments/direct_m2_runner.py
scripts/experiments/direct_benefit_runner.py
scripts/experiments/direct_mechanism_runner.py
scripts/analysis/briefing_operator_audit.py
scripts/analysis/briefing_pec_audit.py
scripts/analysis/audit_paper01_data_contract.py
scripts/analysis/diagnose_paper01_s1.py
scripts/experiments/night_budget.py
scripts/experiments/night_fixed_state.py
scripts/experiments/n3_recover_continue.py
scripts/experiments/n3_h96_sequential_e.py
scripts/experiments/server_step36e_budget_probe.py
scripts/experiments/server_first_e_budget_probe.py
scripts/experiments/server_step36_window_probe.py
scripts/experiments/direct_m1_diagnosis.py
scripts/experiments/mechanism_hour_runner.py
scripts/analysis/audit_mechanism_hour.py
scripts/experiments/mechanism_final_audit.py
scripts/analysis/audit_mechanism_2h.py
scripts/experiments/night_runner.py
scripts/analysis/night_review_evidence.py
scripts/analysis/verify_night_review_delivery.py
scripts/experiments/g0_verifier.py
tests/test_night_budget.py
tests/test_direct_mechanism_m0.py
scripts/experiments/train_dco.py
_01/src/paper01/__init__.py
scripts/experiments/run_fdtd_cavity.py
scripts/experiments/stage2_fixed_state.py
scripts/experiments/stage2_interface_probe.py
scripts/experiments/stage2_shared_interference.py
scripts/experiments/mechanism_decision_init.py
scripts/experiments/mechanism_decision_runner.py
scripts/experiments/mechanism_decision_eval.py
scripts/experiments/mechanism_first_failure.py
scripts/experiments/mechanism_path_check.py
scripts/experiments/h_layout_candidate.py
scripts/experiments/r4_fixed_state.py
scripts/experiments/r4_p4a.py
scripts/experiments/r0_v2_audit.py
scripts/experiments/night_init.py
scripts/experiments/night_diagnostics.py
scripts/experiments/refine_night_storage_estimate.py
scripts/experiments/p5_audit.py
scripts/experiments/p5_ab_audit.py
scripts/experiments/server_phase1_compare.py
scripts/experiments/server_local_review.py
scripts/experiments/server_failure_mechanism_audit.py
scripts/analysis/verify_claims.py
""".split()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    initial = json.loads((OUT / "source_inventory.json").read_text(encoding="utf-8"))
    claims = {}
    for row in initial["files"]:
        if row["status"] == "SOURCE_READ" or row["path"] in PARENT_FULL:
            claims[row["path"]] = (row["sha256"], "FULL_SOURCE_READ", "parent review")
    for name in ("offline_review.md", "exploratory_review.md", "deployment_review.md", "presentation_review.md", "tests_review.md", "layout_review.md", "historical_analysis_review.md"):
        if not (OUT / name).exists():
            continue
        for line in (OUT / name).read_text(encoding="utf-8").splitlines():
            match = re.search(r"([\w/.-]+\.(?:py|js|ps1))`?\s*(?:\|[^\n]*?)?\s+`?([0-9a-f]{64})", line, re.I)
            if not match:
                continue
            path, sha = match.groups()
            if name == "deployment_review.md" and "/" not in path:
                path = "tools/" + path
            if name == "historical_analysis_review.md" and "/" not in path:
                path = "scripts/analysis/" + path
            level = "FULL_TEMPLATE_DIFF" if "与模板差异审查" in line else "FULL_SOURCE_READ"
            claims.setdefault(path, (sha.lower(), level, name))
    files, changes, known = [], [], {}
    for old in initial["files"]:
        rel = old["path"]
        path = ROOT / rel
        if not path.exists():
            changes.append({"path": rel, "kind": "missing_since_initial"})
            files.append({**old, "coverage": "MISSING_CURRENT"})
            continue
        raw = path.read_bytes()
        sha = digest(raw)
        if sha != old["sha256"]:
            changes.append({"path": rel, "kind": "changed_since_initial", "sha256": sha})
        status, evidence = "PENDING_REVIEW", None
        if rel.startswith("evidence/code_review_20260917/"):
            status = "REVIEW_TOOL"
        elif rel in claims:
            expected, level, report = claims[rel]
            if sha == expected:
                status, evidence = level, report
                known.setdefault(digest(raw.replace(b"\r\n", b"\n")), rel)
            else:
                status, evidence = "REVIEWED_VERSION_CHANGED", report
        elif old["status"] == "PARTIAL_READ":
            status = "PARTIAL_READ"
        files.append({"path": rel, "sha256": sha, "lines": len(raw.splitlines()),
                      "coverage": status, "review_evidence": evidence})
    for row in files:
        if row["coverage"] != "PENDING_REVIEW":
            continue
        raw = (ROOT / row["path"]).read_bytes()
        canonical = known.get(digest(raw.replace(b"\r\n", b"\n")))
        if canonical:
            row["coverage"] = "CONTENT_MATCH_LF_NORMALIZED"
            row["review_evidence"] = canonical
    index_path = OUT / "historical_deltas_v2/index.json"
    by_path = {row["path"]: row for row in files}
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        groups = {row["id"]: row for row in index["groups"]}
        for domain in ("core", "support"):
            claim_file = OUT / f"historical_{domain}_coverage.json"
            if not claim_file.exists():
                continue
            claim = json.loads(claim_file.read_text(encoding="utf-8"))
            assert claim["index_sha256"].lower() == digest(index_path.read_bytes())
            assert claim["coverage_mode"] == "FULL_DELTA_REVIEW"
            ids = claim["reviewed_group_ids"]
            assert len(ids) == len(set(ids)), "duplicate historical group claims"
            for group_id in ids:
                group = groups[group_id]
                assert group["partition"] == domain
                for member in group["members"]:
                    row = by_path[member["path"]]
                    assert row["sha256"] == member["sha256"]
                    raw = (ROOT / member["path"]).read_bytes()
                    assert digest(raw.replace(b"\r\n", b"\n")) == group["normalized_sha256"]
                    assert row["coverage"] == "PENDING_REVIEW"
                    row["coverage"] = "FULL_HISTORICAL_DELTA_REVIEW"
                    row["review_evidence"] = {"report": f"historical_{domain}_review.md", "group": group_id,
                                               "canonical": group["canonical"]}
    active = [r for r in files if not r["path"].startswith(("evidence/", "archive/"))]
    payload = {"captured_utc": datetime.now(timezone.utc).isoformat(),
               "not_a_scientific_pass": True, "coverage_is_not_bug_free": True,
               "notes": "Initial inventory universe; later review helpers are excluded. Content matches inherit static review only, not execution identity or scientific evidence.",
               "active_counts": dict(Counter(r["coverage"] for r in active)),
               "all_counts": dict(Counter(r["coverage"] for r in files)),
               "changes_since_initial": changes, "files": files}
    target = OUT / ("coverage_" + args.revision + ".json")
    with target.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print(json.dumps({k: payload[k] for k in ("active_counts", "all_counts", "changes_since_initial")}, ensure_ascii=False))
    print("PENDING ACTIVE:")
    for row in active:
        if row["coverage"] in {"PENDING_REVIEW", "PARTIAL_READ", "REVIEWED_VERSION_CHANGED"}:
            print(row["path"], row["lines"], row["coverage"])


if __name__ == "__main__":
    main()
