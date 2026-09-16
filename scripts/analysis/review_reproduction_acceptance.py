"""Read-only acceptance review; preserves all original execution artifacts."""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

import json
from datetime import datetime, timezone
from pathlib import Path

import g0_verifier
import night_evidence

ROOT = PROJECT_ROOT
NIGHT = ROOT / 'evidence/gpt6_plan_v4_night'
OUT = ROOT / 'evidence/2026-09-14_acceptance_review'


def main():
    OUT.mkdir(exist_ok=False)
    computed = night_evidence.compute(NIGHT)
    current_g0 = g0_verifier.verify(NIGHT / 'g0_after_head_integration', contract_run=202,
                                   n1_path=NIGHT / 'N1_contract_checks.json')
    p = NIGHT / 'acceptance.json'
    raw = json.loads(p.read_text(encoding='utf8'))
    result = {
        'schema': 'pidon-acceptance-review-v1',
        'reviewed_at_utc': datetime.now(timezone.utc).isoformat(),
        'parameter_updates_this_review': 0,
        'advancement': 'PAUSED_BY_USER',
        'numerical_evidence': computed,
        'current_G0_checker_result': current_g0['G0'],
        'current_G0_checker_checks': current_g0['required_g0_checks'],
        'acceptance_file': {
            'mtime_utc': datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
            'creation_time_utc_on_windows': datetime.fromtimestamp(p.stat().st_ctime, timezone.utc).isoformat(),
            'claimed_registered_before_n3': raw.get('registered_before_n3'),
            'review_status': 'UNSUPPORTED_FALSE_TIMING_CLAIM',
            'reason': 'night_init.py does not generate this file; its creation/mtime is after N3. The earlier plan contains the thresholds, so this is not evidence that thresholds were relaxed.',
        },
        'accepted_findings': [
            'The five registered historical asset hashes match.',
            'H43 and sequential E96 fail physical R<1e-4; H96 passes only its single H fit.',
            'No valid accepted DCO trajectory was produced; later branches are NOT_RUN.',
            'The current control verifier passes its recorded 28 checks, and the raw control evidence remains available.',
            'N5 two directional-derivative points and four sample gradient-finiteness checks are present; label provenance remains incomplete.',
        ],
        'execution_acceptance': 'PARTIAL_INCOMPLETE',
        'remaining_requirements': [
            {'id': 'A01', 'status': 'INCOMPLETE', 'finding': 'N0 acceptance file was created at night end, while its registered_before_n3 flag says otherwise.'},
            {'id': 'A02', 'status': 'INCOMPLETE', 'finding': 'Persistent night deadline/task checks are at task start, not at every production Adam/head-solve boundary as planned.'},
            {'id': 'A03', 'status': 'INCOMPLETE', 'finding': 'G0 C-id processing uses sets without duplicate rejection; M01-M05 all bind the same module-containing successful lab record rather than individual numerical test evidence.'},
            {'id': 'A04', 'status': 'INCOMPLETE', 'finding': 'N5 analytic example checks only z propagation; planned three-axis continuous/discrete verification and complete saved wave metadata are absent.'},
            {'id': 'A05', 'status': 'INCOMPLETE', 'finding': 'N5 third near-zero component absolute errors/projection changes are not output separately.'},
            {'id': 'A06', 'status': 'INCOMPLETE', 'finding': 'Per-stage peak RAM/VRAM and separate I/O resource records are missing; N0 registered only master plus four v3 assets, not an exhaustive v1/v2 asset hash inventory.'},
            {'id': 'A07', 'status': 'DEVIATION_PRESERVED', 'finding': 'Oracle-E parameter updates and diagnostic n=8 deviation are preserved/excluded; prior COMPLETE should not be read as full plan compliance.'},
        ],
        'scientific_status': {'G0_complete_certification': 'INCOMPLETE_ON_ACCEPTANCE_REVIEW',
                              'G1': 'FAIL', 'G2': 'NOT_RUN', 'G3': 'NOT_RUN',
                              'paper_reproduction': 'NOT_REPRODUCED'},
    }
    (OUT / 'acceptance_review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8')
    print(json.dumps({'out': str(OUT), 'execution_acceptance': result['execution_acceptance'],
                      'G1': 'FAIL', 'advancement': result['advancement']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
