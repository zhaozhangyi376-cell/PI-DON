"""Install the second bounded server batch and run its queue."""
from __future__ import annotations

import hashlib
import json
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


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    here = Path(__file__).resolve().parent
    manifest = read_json(here / "package_manifest.json")
    if not (ROOT / "run.py").exists() or not (ROOT / "project/plan.json").exists():
        raise SystemExit("Run this installer from the PI-DON project root.")
    backup = ROOT / "evidence/server_resource_v1" / ("batch2_deployment_backup_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
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
    print(f"Installed batch2 payload. Backup: {backup if backup.exists() else 'none'}")
    subprocess.run([sys.executable, "run.py", "unittest", "-q", "test_server_resource"], cwd=ROOT, check=True)
    return subprocess.run([sys.executable, "run.py", "server_batch2_queue"], cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
