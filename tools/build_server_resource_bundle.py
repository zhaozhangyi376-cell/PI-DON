"""Build a hash-checked additive deployment archive; no numerical experiments."""
from pathlib import Path
import hashlib
import json
import zipfile

from project_paths import PROJECT_DIR


def main():
    files = ['PLAN.md', 'STATUS.md', 'docs/plans/2026-09-15-server-resource-protocol.md',
             'docs/plans/2026-09-15-server-readback-addendum.md', 'docs/guides/SERVER_RESOURCE_START.md',
             'scripts/experiments/server_local_review.py', 'scripts/experiments/server_phase1_compare.py',
             'scripts/experiments/server_compute_probe.py', 'tools/server_resource_queue.py',
             'tests/test_server_resource.py']
    for folder in ('local_review', 'local_review_v2'):
        files += [p.relative_to(PROJECT_DIR).as_posix() for p in
                  sorted((PROJECT_DIR / f'evidence/server_resource_v1/{folder}').rglob('*')) if p.is_file()]
    hashes = {rel: hashlib.sha256((PROJECT_DIR / rel).read_bytes()).hexdigest() for rel in files}
    out = PROJECT_DIR / 'evidence/server_resource_v1/server_resource_bundle.zip'
    with zipfile.ZipFile(out, 'x', zipfile.ZIP_DEFLATED) as archive:
        for rel in files:
            archive.write(PROJECT_DIR / rel, 'payload/'+rel)
        archive.write(PROJECT_DIR / 'tools/install_server_resource.py', 'install_server_resource.py')
        archive.writestr('package_manifest.json', json.dumps({'files': hashes}, indent=2))
    print(out)
    print('SHA256', hashlib.sha256(out.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
