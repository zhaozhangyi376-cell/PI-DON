"""Install a reviewed payload with backups, then start the bounded server queue."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    package = Path(__file__).resolve().parent
    root = Path.cwd().resolve()
    if not (root / 'run.py').is_file() or not (root / 'project/plan.json').is_file():
        raise SystemExit('First change directory to H:\\PI-DON.')
    manifest = json.loads((package / 'package_manifest.json').read_text(encoding='utf-8'))
    for rel, expected in manifest['files'].items():
        source = (package / 'payload' / rel).resolve()
        source.relative_to((package / 'payload').resolve())
        (root / rel).resolve().relative_to(root)
        if digest(source) != expected:
            raise SystemExit('Package hash mismatch: '+rel)
        if rel in ('project/plan.json', 'project/actions.jsonl') or rel.startswith('records/'):
            raise SystemExit('Package must not overwrite server ledger: '+rel)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    backup = root / 'evidence/server_resource_v1' / ('deployment_backup_'+stamp)
    for rel in manifest['files']:
        source, target = package / 'payload' / rel, root / rel
        if target.exists():
            if digest(source) == digest(target):
                continue
            if rel.startswith('evidence/'):
                raise SystemExit('Existing evidence differs; refusing overwrite: '+rel)
            saved = backup / rel
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    checks = subprocess.run([sys.executable, 'run.py', 'unittest', '-q', 'test_server_resource'], cwd=root)
    if checks.returncode:
        raise SystemExit('Package tests failed. No experiments started.')
    raise SystemExit(subprocess.run([sys.executable, 'run.py', 'server_resource_queue', 'run'], cwd=root).returncode)


if __name__ == '__main__':
    main()
