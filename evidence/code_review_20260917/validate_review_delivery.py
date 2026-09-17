"""Validate review coverage and preserve a complete artifact manifest."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

from supplement_source_inventory import EXTENSIONS

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    coverage = read(OUT / args.coverage)
    allowed = {"FULL_SOURCE_READ", "FULL_TEMPLATE_DIFF", "CONTENT_MATCH_LF_NORMALIZED", "FULL_HISTORICAL_DELTA_REVIEW"}
    known = {}
    for row in coverage["files"]:
        if row["coverage"] == "REVIEW_TOOL":
            continue
        assert row["coverage"] in allowed, row
        assert sha(ROOT / row["path"]) == row["sha256"], row["path"]
        known[row["path"]] = row
    assert not coverage["changes_since_initial"]
    supplement = read(OUT / "supplementary_sources/index.json")
    for row in supplement["files"]:
        path = ROOT / row["path"]
        assert sha(path) == row["sha256"], row["path"]
        canonical = row["exact_lf_match"]
        if canonical:
            assert canonical in known, canonical
            assert path.read_bytes().replace(b"\r\n", b"\n") == (ROOT / canonical).read_bytes().replace(b"\r\n", b"\n")
            level = "CONTENT_MATCH_LF_NORMALIZED"
        elif row["path"].startswith("archive/legacy_commands/") and path.suffix == ".bat":
            level = "FULL_SOURCE_READ"
        else:
            assert row["diff_file"] in {"015_server_short_tol_probe.diff", "064_server_short_tol_probe.diff"}
            assert row["canonical"] in known
            level = "FULL_HISTORICAL_DELTA_REVIEW"
        known[row["path"]] = {**row, "coverage": level, "review_evidence": "supplementary_review.md"}
    current = set()
    for directory, folders, names in os.walk(ROOT):
        folders[:] = [n for n in folders if n not in {".git", "__pycache__", "node_modules", ".venv", "venv"}]
        for name in names:
            path = Path(directory) / name
            relative = path.relative_to(ROOT).as_posix()
            if path.suffix.lower() in EXTENSIONS and not relative.startswith("evidence/code_review_20260917/"):
                current.add(relative)
    assert current == set(known), {"unreviewed": sorted(current - set(known)), "missing": sorted(set(known) - current)}
    checks = read(OUT / "final_checks/checks.json")
    artifacts = [{"path": p.relative_to(OUT).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)}
                 for p in sorted(OUT.rglob("*")) if p.is_file() and "__pycache__" not in p.parts]
    diff = subprocess.run(["git", "diff", "--name-status"], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout
    result = {"captured_utc": datetime.now(timezone.utc).isoformat(), "review_delivery_complete": True,
              "scientific_certification": False, "production_fixes_applied": False,
              "coverage_counts": dict(Counter(r["coverage"] for r in known.values())),
              "project_source_files": len(known), "project_sources": list(known.values()),
              "existing_test_processes": checks, "all_existing_tests_pass": all(c["returncode"] == 0 for c in checks),
              "worktree_diff_at_delivery": diff,
              "scope_exclusions": ["third-party/runtime code", "packed ZIP contents not separately extracted",
                                   "Git object history", "CST binary databases and other generated numeric assets",
                                   "full retraining or rerunning all historical numerical results"],
              "artifact_manifest_excludes_self": True, "artifacts": artifacts}
    with (OUT / args.output).open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({k: result[k] for k in ("review_delivery_complete", "scientific_certification", "project_source_files", "coverage_counts", "all_existing_tests_pass")}, ensure_ascii=False))
    print(json.dumps(checks, ensure_ascii=False))


if __name__ == "__main__":
    main()
