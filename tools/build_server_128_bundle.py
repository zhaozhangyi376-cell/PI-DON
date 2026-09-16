"""Build the SR-128 server deployment zip."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from project_paths import PROJECT_DIR, configure


configure()


PAYLOAD = [
    "docs/plans/2026-09-16-server-128-protocol.md",
    "scripts/experiments/server_short_tol_probe.py",
    "scripts/experiments/server_failure_mechanism_audit.py",
    "tools/server_128_queue.py",
    "tools/install_server_128.py",
    "tests/test_first_e_budget_probe.py",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    out = PROJECT_DIR / "evidence/server_resource_v1/server_128_bundle.zip"
    if out.exists():
        out.unlink()
    manifest = {"schema": "pidon-server-128-bundle-v1", "payload": {}}
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in PAYLOAD:
            path = PROJECT_DIR / rel
            digest = sha256(path)
            manifest["payload"][rel] = digest
            archive.write(path, f"payload/{rel}")
        archive.writestr("package_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        archive.write(PROJECT_DIR / "tools/install_server_128.py", "install_server_128.py")
    print(json.dumps({"zip": str(out), "sha256": sha256(out), "files": len(PAYLOAD)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
