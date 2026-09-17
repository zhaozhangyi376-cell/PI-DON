from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from project_paths import PROJECT_DIR, configure

configure()

PAYLOAD = [
    "docs/plans/2026-09-16-paper-tol128-diagnostic-protocol.md",
    "scripts/experiments/server_short_tol_probe.py",
    "tools/server_paper_tol128_queue.py",
    "tests/test_first_e_budget_probe.py",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    out = PROJECT_DIR / "evidence/server_resource_v1/server_paper_tol128_bundle.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    manifest = {"schema": "pidon-server-paper-tol128-bundle-v1", "payload": {}}
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in PAYLOAD:
            path = PROJECT_DIR / rel
            digest = sha256(path)
            manifest["payload"][rel] = digest
            archive.write(path, f"payload/{rel}")
        archive.writestr("package_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        archive.writestr("install_server_paper_tol128.py", INSTALL)
    print(json.dumps({"zip": str(out), "sha256": sha256(out), "files": len(PAYLOAD)}, ensure_ascii=False))


INSTALL = r'''
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path(__file__).resolve().parent / "package_manifest.json"

with zipfile.ZipFile(Path(__file__).resolve().parents[1] / "server_paper_tol128_bundle.zip") as zf:
    for name in zf.namelist():
        if not name.startswith("payload/") or name.endswith("/"):
            continue
        rel = Path(name).relative_to("payload")
        dest = ROOT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(name) as src, dest.open("wb") as out:
            shutil.copyfileobj(src, out)
print("Installed SR-128-PAPER-TOL-DIAG payload. Backup: none")
print(subprocess.run([sys.executable, "-m", "unittest", "tests.test_first_e_budget_probe", "-v"], cwd=ROOT, text=True).returncode)
raise SystemExit(subprocess.run([sys.executable, "run.py", "server_paper_tol128_queue"], cwd=ROOT).returncode)
'''

if __name__ == "__main__":
    main()


