from __future__ import annotations

import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


INSTALLER = r'''from __future__ import annotations
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "payload" / "_01"
DEST = ROOT / "_01"
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
backup = ROOT / "evidence" / "paper01_deployment" / stamp
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

protocol_source = ROOT / "payload" / "docs" / "plans" / "2026-09-17-paper01-s1-r1-protocol.md"
protocol_target = ROOT / "docs" / "plans" / protocol_source.name
protocol_target.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(protocol_source, protocol_target)

plan_path = ROOT / "project" / "plan.json"
plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
if not any(task.get("id") == "PAPER01-S1" for task in plan["tasks"]):
    task = json.loads((ROOT / "paper01_task.json").read_text(encoding="utf-8"))
    plan["tasks"].append(task)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Installed PAPER01-S1 payload. Backup: {backup if backup.exists() else 'none'}")
'''


QUEUE = r'''from __future__ import annotations
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = Path(sys.executable)
OUTPUT = ROOT / "_01" / "evidence" / "paper01_s1_v1"
PROTOCOL = "docs/plans/2026-09-17-paper01-s1-r1-protocol.md"
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
    PYTHON, "run.py", "project_harness", "start", "PAPER01-S1",
    "--question", "Independent paper-explicit stage-one DCO reference training",
    "--expected", "Fresh 32^3 1000-sample four-level Adam run at constant lr 1e-4 and effective batch 32",
    "--success", "1000 equivalent epochs, 25000 updates, best/last checkpoints, metrics and audits are preserved",
    "--failure", "Preserve incomplete or failed evidence; do not resume with a reset budget and do not unlock long PI-DON runs",
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
    "PAPER01-S1 independent paper-explicit phase-one training",
    "--", PYTHON, "_01/train_phase1.py", "train",
    "--output", OUTPUT, "--device", "cuda", "--microbatch", "8",
    "--progress-every", "25", "--validation-every", "250",
]
result = call(command)
summary_path = OUTPUT / "summary.json"
if result.returncode == 0 and summary_path.is_file():
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    status = "PASS"
    text = (f"PAPER01-S1 engineering delivery complete; updates={summary['updates']}; "
            f"best_test_mse={summary['best_test_mse']}; scientific comparison remains pending audit")
else:
    status = "INCOMPLETE"
    text = f"PAPER01-S1 process exit {result.returncode}; preserve现场 and do not reset budget"

evidence = [PROTOCOL]
for name in (
    "manifest.json", "paper_contract.json", "sample_specs.json", "history.jsonl",
    "summary.json", "audit.json", "REPORT.md", "best.pt", "last.pt",
):
    path = OUTPUT / name
    if path.exists():
        evidence.append(path.relative_to(ROOT).as_posix())
finish = call([
    PYTHON, "run.py", "project_harness", "finish", action,
    "--status", status, "--evidence", *evidence, "--summary", text,
])

return_zip = ROOT / "server_paper01_return.zip"
with zipfile.ZipFile(return_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for path in evidence[1:]:
        source = ROOT / path
        if source.is_file():
            archive.write(source, path)
    for path in (ROOT / "records" / "lab_runs.jsonl", ROOT / "project" / "actions.jsonl", ROOT / "project" / "plan.json"):
        if path.is_file():
            archive.write(path, path.relative_to(ROOT).as_posix())
print(json.dumps({"status": status, "action": action, "return_zip": str(return_zip)}, ensure_ascii=False), flush=True)
raise SystemExit(result.returncode)
'''


PRE_FLIGHT = r'''$ErrorActionPreference = "Stop"
Set-Location H:\PI-DON
$env:PYTHONUTF8="1"
$PY="C:\Users\ZZY\.conda\envs\pidon311\python.exe"
& $PY .\install_paper01_server.py
& $PY .\_01\train_phase1.py preflight --output .\_01\evidence\paper01_preflight --device cuda
'''


FULL = r'''$ErrorActionPreference = "Stop"
Set-Location H:\PI-DON
$env:PYTHONUTF8="1"
$PY="C:\Users\ZZY\.conda\envs\pidon311\python.exe"
& $PY .\install_paper01_server.py
& $PY .\server_paper01_queue.py
'''


def build_bundle(output: Path) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    task = dict(next(task for task in json.loads((ROOT / "project" / "plan.json").read_text(encoding="utf-8"))["tasks"]
                     if task["id"] == "PAPER01-S1"))
    # The accepted R1 preflight lives on the local host. The server receives the
    # frozen source/protocol but not a fake copy of local evidence or task state.
    task["depends"] = []
    task["reason"] += "；本地R1预检已审核，服务器部署任务不声明跨主机机器依赖"
    include = [path for path in (ROOT / "_01").rglob("*")
               if path.is_file()
               and "__pycache__" not in path.parts
               and "evidence" not in path.parts
               and path.suffix != ".pt"]
    protocol = ROOT / "docs" / "plans" / "2026-09-17-paper01-s1-r1-protocol.md"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in include:
            archive.write(path, "payload/_01/" + path.relative_to(ROOT / "_01").as_posix())
        archive.write(protocol, "payload/docs/plans/" + protocol.name)
        archive.writestr("paper01_task.json", json.dumps(task, ensure_ascii=False, indent=2) + "\n")
        archive.writestr("install_paper01_server.py", INSTALLER)
        archive.writestr("server_paper01_queue.py", QUEUE)
        archive.writestr("run_paper01_preflight.ps1", PRE_FLIGHT)
        archive.writestr("run_paper01_full.ps1", FULL)
    return output


if __name__ == "__main__":
    destination = ROOT / "server_paper01_bundle.zip"
    print(build_bundle(destination))
