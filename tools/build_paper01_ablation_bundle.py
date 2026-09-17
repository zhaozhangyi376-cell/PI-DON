from __future__ import annotations

import json
import hashlib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "PAPER01-ABLATION-SMOKE"
PROTOCOL = "docs/plans/2026-09-17-paper01-ablation-smoke-protocol.md"


INSTALLER = r'''from __future__ import annotations
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

UPDATE = Path(__file__).resolve().parent
ROOT = UPDATE.parent
if not (ROOT / "run.py").is_file() or not (ROOT / "project" / "plan.json").is_file():
    raise SystemExit(f"PAPER01 ablation installer expected project root at {ROOT}, but run.py or project/plan.json is missing")
SOURCE = UPDATE / "payload" / "_01"
DEST = ROOT / "_01"
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
backup = ROOT / "evidence" / "paper01_ablation_deployment" / stamp
for source in SOURCE.rglob("*"):
    if not source.is_file():
        continue
    relative = source.relative_to(SOURCE)
    target = DEST / relative
    if target.exists():
        saved = backup / relative
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, saved)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)

protocol_source = UPDATE / "payload" / "docs" / "plans" / "2026-09-17-paper01-ablation-smoke-protocol.md"
protocol_target = ROOT / "docs" / "plans" / protocol_source.name
protocol_target.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(protocol_source, protocol_target)

plan_path = ROOT / "project" / "plan.json"
plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
task = json.loads((UPDATE / "paper01_ablation_task.json").read_text(encoding="utf-8"))
for existing in plan["tasks"]:
    if existing.get("id") == task["id"]:
        break
else:
    plan["tasks"].append(task)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Installed PAPER01 ablation payload. Backup: {backup if backup.exists() else 'none'}")
'''


QUEUE = r'''from __future__ import annotations
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

UPDATE = Path(__file__).resolve().parent
ROOT = UPDATE.parent
if not (ROOT / "run.py").is_file() or not (ROOT / "project" / "plan.json").is_file():
    raise SystemExit(f"PAPER01 ablation queue expected project root at {ROOT}, but run.py or project/plan.json is missing")
PYTHON = Path(sys.executable)
OUTPUT = ROOT / "_01" / "evidence" / "paper01_ablation_v1"
PROTOCOL = "docs/plans/2026-09-17-paper01-ablation-smoke-protocol.md"
TASK_ID = "PAPER01-ABLATION-SMOKE"
env = dict(os.environ)
env["PYTHONUTF8"] = "1"
env["PYTHONIOENCODING"] = "utf-8"


def call(args, capture=False):
    print(" ".join(map(str, args)), flush=True)
    return subprocess.run([str(v) for v in args], cwd=ROOT, env=env,
                          text=True, encoding="utf-8", errors="replace",
                          capture_output=capture)


check = call([PYTHON, "run.py", "project_harness", "check"])
check.check_returncode()
started = call([
    PYTHON, "run.py", "project_harness", "start", TASK_ID,
    "--question", "PAPER01 stage-one angle amplitude normalization short ablation",
    "--expected", "Run four fresh short-budget diagnostic variants to compare baseline, safer theta, capped Ez, and projected transverse amplitudes",
    "--success", "All four variants complete 2000 Adam updates with summaries, histories, reports, and checkpoints preserved",
    "--failure", "Preserve incomplete evidence; do not relabel PAPER01-S1 and do not unlock stage two or long runs",
    "--protocol", PROTOCOL,
], capture=True)
print(started.stdout, end="")
print(started.stderr, end="", file=sys.stderr)
started.check_returncode()
match = re.search(r"A-\d{8}T\d{6}-[0-9a-f]+", started.stdout)
if not match:
    raise RuntimeError("could not parse action id")
action = match.group(0)

command = [
    PYTHON, "lab_log.py", "run", "-m",
    "PAPER01-ABLATION-SMOKE angle amplitude normalization short ablation",
    "--", PYTHON, "_01/train_phase1_ablation.py",
    "--output", OUTPUT,
    "--device", "cuda",
    "--updates", "2000",
    "--samples", "1000",
    "--microbatch", "8",
    "--validation-every", "250",
    "--progress-every", "50",
    "--variants", "baseline", "theta_min_0p5", "ez_cap3", "projected_amp",
]
result = call(command)
summary_path = OUTPUT / "summary.json"
if result.returncode == 0 and summary_path.is_file():
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    status = "PASS"
    text = (
        f"PAPER01-ABLATION-SMOKE complete; variants={','.join(v['variant'] for v in summary['variants'])}; "
        f"updates={summary['parameter_updates']}; scientific_result=DIAGNOSTIC_ONLY; no long-run unlock."
    )
else:
    status = "INCOMPLETE"
    text = f"PAPER01-ABLATION-SMOKE process exit {result.returncode}; preserve现场 and do not reset budget"

evidence = [PROTOCOL]
if OUTPUT.exists():
    for source in sorted(OUTPUT.rglob("*")):
        if source.is_file():
            evidence.append(source.relative_to(ROOT).as_posix())
finish = call([
    PYTHON, "run.py", "project_harness", "finish", action,
    "--status", status, "--evidence", *evidence, "--summary", text,
])

return_zip = ROOT / "server_paper01_ablation_return.zip"
with zipfile.ZipFile(return_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for path in evidence[1:]:
        source = ROOT / path
        if source.is_file():
            archive.write(source, path)
    for path in (
        ROOT / "records" / "lab_runs.jsonl",
        ROOT / "project" / "actions.jsonl",
        ROOT / "project" / "plan.json",
    ):
        if path.is_file():
            archive.write(path, path.relative_to(ROOT).as_posix())
print(json.dumps({"status": status, "action": action, "return_zip": str(return_zip)}, ensure_ascii=False), flush=True)
raise SystemExit(result.returncode)
'''


RUN_PS1 = r'''$ErrorActionPreference = "Stop"
Set-Location H:\PI-DON
$env:PYTHONUTF8="1"
$PY="C:\Users\ZZY\.conda\envs\pidon311\python.exe"

& $PY .\server_paper01_ablation_update\install_paper01_ablation.py
& $PY .\server_paper01_ablation_update\server_paper01_ablation_queue.py
'''


def task_payload() -> dict:
    plan = json.loads((ROOT / "project" / "plan.json").read_text(encoding="utf-8"))
    task = dict(next(item for item in plan["tasks"] if item["id"] == TASK_ID))
    # The server may not yet have the locally reviewed PAPER01-DATA-AUDIT task.
    # The installer adds this task as a standalone diagnostic queue entry while
    # preserving the local protocol and action evidence in the return bundle.
    task["depends"] = []
    task["reason"] += "；服务器部署时不声明跨主机机器依赖，本地PAPER01-DATA-AUDIT已审核。"
    return task


def build_bundle(output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    include = [
        path for path in (ROOT / "_01").rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and "evidence" not in path.parts
        and path.suffix != ".pt"
    ]
    protocol = ROOT / PROTOCOL
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in include:
            archive.write(path, "payload/_01/" + path.relative_to(ROOT / "_01").as_posix())
        archive.write(protocol, "payload/docs/plans/" + protocol.name)
        archive.writestr("paper01_ablation_task.json", json.dumps(task_payload(), ensure_ascii=False, indent=2) + "\n")
        archive.writestr("install_paper01_ablation.py", INSTALLER)
        archive.writestr("server_paper01_ablation_queue.py", QUEUE)
        archive.writestr("run_paper01_ablation.ps1", RUN_PS1)
    digest = hashlib.sha256(output.read_bytes()).hexdigest().upper()
    sidecar_text = f"{digest}  {output.name}\n"
    output.with_suffix(output.suffix + ".sha256").write_text(sidecar_text, encoding="utf-8")
    output.with_suffix(".sha256").write_text(sidecar_text, encoding="utf-8")
    return output


if __name__ == "__main__":
    destination = ROOT / "server_paper01_ablation_bundle.zip"
    print(build_bundle(destination))
