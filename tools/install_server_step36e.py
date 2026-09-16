"""Install the SR-36E-BUDGET payload and run its queue."""
from __future__ import annotations

import hashlib
import json
import py_compile
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path.cwd().resolve()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / "package_manifest.json").read_text(encoding="utf-8"))
    if not (ROOT / "run.py").exists() or not (ROOT / "project/plan.json").exists():
        raise SystemExit("Run this installer from the PI-DON project root.")
    backup = ROOT / "evidence/server_resource_v1" / (
        "step36e_deployment_backup_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    for rel, expected in manifest["payload"].items():
        src = here / "payload" / rel
        if sha256(src) != expected:
            raise SystemExit(f"Payload hash mismatch: {rel}")
        dest = ROOT / rel
        if dest.exists() and sha256(dest) != expected:
            backup_path = backup / rel
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, backup_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    print(f"Installed SR-36E-BUDGET payload. Backup: {backup if backup.exists() else 'none'}")
    py_compile.compile(str(ROOT / "scripts/experiments/server_step36e_budget_probe.py"), doraise=True)
    py_compile.compile(str(ROOT / "tools/server_step36e_queue.py"), doraise=True)
    return subprocess.run([sys.executable, "run.py", "server_step36e_queue"], cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())

