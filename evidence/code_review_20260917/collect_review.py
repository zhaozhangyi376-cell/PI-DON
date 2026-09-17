"""Inventory source and collect existing tests without editing implementation."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
CORE_READ = {
    "src/pidon/fdtd.py", "src/pidon/dco.py", "src/pidon/gen_data.py",
    "src/pidon/pidon_solve.py", "src/pidon/pidon_contract.py",
    "src/pidon/pidon_recording.py", "src/pidon/reference_cache.py",
    "src/pidon/rollout.py", "src/pidon/paper_protocol.py",
    "src/pidon/head_lstsq.py", "src/pidon/exact_stencil.py",
    "_01/src/paper01/data.py", "_01/src/paper01/model.py",
    "_01/src/paper01/metrics.py", "_01/src/paper01/runner.py",
    "_01/src/paper01/ablation_data.py", "_01/train_phase1_ablation.py",
    "scripts/experiments/server_short_tol_probe.py", "project_paths.py", "run.py",
    "tools/ingest_paper01_theta_full_return.py", "tools/build_paper01_theta_full_bundle.py",
}
PARTIAL_READ = {
    "scripts/experiments/phase1_full_run.py", "tools/ingest_paper01_ablation_return.py",
    "tools/ingest_server_64_return.py", "lab_log.py",
    "scripts/analysis/diagnose_paper01_s1.py",
}


def write_once(name, value):
    path = OUT / name
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def inventory():
    records = []
    for directory, folders, names in os.walk(ROOT):
        folders[:] = [n for n in folders if n not in {
            ".git", "__pycache__", "node_modules", ".venv", "venv",
        }]
        for name in names:
            path = Path(directory) / name
            if path.suffix.lower() not in {".py", ".js", ".ps1", ".m", ".bas", ".vbs"}:
                continue
            rel = path.relative_to(ROOT).as_posix()
            raw = path.read_bytes()
            historical = rel.startswith(("evidence/", "archive/"))
            own = rel.startswith("evidence/code_review_20260917/")
            syntax_error = None
            if path.suffix == ".py":
                try:
                    ast.parse(raw, filename=rel)
                except (SyntaxError, ValueError) as exc:
                    syntax_error = str(exc)
            status = ("REVIEW_TOOL" if own else "HISTORICAL_SNAPSHOT" if historical
                      else "SOURCE_READ" if rel in CORE_READ else "PARTIAL_READ" if rel in PARTIAL_READ
                      else "PENDING_REVIEW")
            records.append({"path": rel, "sha256": hashlib.sha256(raw).hexdigest(),
                            "bytes": len(raw), "lines": len(raw.splitlines()),
                            "status": status, "syntax_error": syntax_error})
    write_once("source_inventory.json", {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "status_semantics": "SOURCE_READ means source inspected, not certified bug-free",
        "files": sorted(records, key=lambda r: r["path"]),
    })
    print(json.dumps({"files": len(records), "pending_active": sum(r["status"] == "PENDING_REVIEW" for r in records),
                      "syntax_errors": sum(r["syntax_error"] is not None for r in records)}), flush=True)


def checks():
    commands = {
        "root_tests": [sys.executable, "run.py", "unittest", "discover", "-s", "tests", "-v"],
        "paper01_tests": [sys.executable, "-m", "unittest", "discover", "-s", "_01/tests", "-v"],
        "harness_check": [sys.executable, "run.py", "project_harness", "check"],
    }
    results = []
    for name, command in commands.items():
        print(f"Running {name}", flush=True)
        env = {**os.environ, "PYTHONUTF8": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
        process = subprocess.run(command, cwd=ROOT, env=env, text=True, encoding="utf-8",
                                 errors="replace", capture_output=True, timeout=300)
        with (OUT / f"{name}.txt").open("x", encoding="utf-8") as handle:
            handle.write(process.stdout + "\n" + process.stderr)
        results.append({"name": name, "command": command, "returncode": process.returncode,
                        "output": f"{name}.txt"})
        print(json.dumps(results[-1]), flush=True)
        print("\n".join((process.stdout + process.stderr).splitlines()[-8:]), flush=True)
    write_once("checks.json", results)


if __name__ == "__main__":
    inventory()
    checks()
