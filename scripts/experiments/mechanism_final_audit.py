# -*- coding: utf-8 -*-
"""Write a small, read-only manifest for the bounded mechanism decision."""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import hashlib
import json
from pathlib import Path

import verify_claims as vc


ROOT = Path('evidence/mechanism_decision_v1')


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def main():
    data = vc.mechanism_decision_claims_data()
    files = [
        ROOT / 'protocol.json', ROOT / 'phase1_raw.json',
        ROOT / 'first_failure_diagnosis.json', ROOT / 'TASK_STATUS.md',
        ROOT / 'FINAL_ACCEPTANCE_REPORT.md', ROOT / 'EVIDENCE_MANIFEST.md',
        Path('RESULTS.md'), Path('STATUS.md'),
    ]
    missing = [str(p) for p in files if not p.exists()]
    if missing:
        raise FileNotFoundError(', '.join(missing))
    out = {
        'schema': 'pidon-mechanism-final-audit-v1',
        'read_only': True,
        'claims_data': data,
        'files_sha256': {str(p): sha256(p) for p in files},
        'reader_sha256': sha256(Path(__file__)),
    }
    (ROOT / 'final_evidence_audit.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({
        'protocol_sha256': data['protocol_sha256'],
        's1_cube32_pass': data['s1_cube32_pass'],
        'p_passed': data['p_passed'],
        'r_status': data['r_status'],
        'output': str(ROOT / 'final_evidence_audit.json'),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
