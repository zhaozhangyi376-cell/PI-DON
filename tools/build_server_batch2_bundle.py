"""Build the second bounded server batch deployment zip."""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from project_paths import PROJECT_DIR, configure


configure()


PAYLOAD = [
    "docs/plans/2026-09-15-server-batch2-protocol.md",
    "docs/plans/2026-09-15-server-batch2-recorder-fix.md",
    "evidence/server_resource_v1/SR_DESIGN_REPORT.md",
    "scripts/experiments/server_short_tol_probe.py",
    "scripts/experiments/server_local_review.py",
    "tools/server_batch2_queue.py",
    "tools/install_server_batch2.py",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    out = PROJECT_DIR / "evidence/server_resource_v1/server_batch2_bundle.zip"
    manifest = {"schema": "pidon-server-batch2-bundle-v1", "payload": {}}
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in PAYLOAD:
            path = PROJECT_DIR / rel
            digest = sha256(path)
            manifest["payload"][rel] = digest
            zf.write(path, f"payload/{rel}")
        zf.writestr("package_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        zf.write(PROJECT_DIR / "tools/install_server_batch2.py", "install_server_batch2.py")
    print(json.dumps({"zip": str(out), "sha256": sha256(out), "files": len(PAYLOAD)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
