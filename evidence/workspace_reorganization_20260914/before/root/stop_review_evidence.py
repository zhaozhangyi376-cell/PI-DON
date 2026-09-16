"""Shared source for v3 review claims, report, and evidence figure."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent / 'evidence/gpt6_plan_v3_review'


def load_review():
    return (json.loads((ROOT/'audit.json').read_text(encoding='utf-8')),
            json.loads((ROOT/'reference_alignment_corrected.json').read_text(encoding='utf-8')),
            json.loads((ROOT/'h_layout.json').read_text(encoding='utf-8')))


def engineering_status():
    a, _, _ = load_review()
    failed = [name for name, row in a['contract_probes'].items()
              if isinstance(row, dict) and row.get('contract_pass') is False]
    return ('FAIL' if failed else 'INCOMPLETE'), failed


def g1_development_status(tasks, required=(43,96)):
    """A partial candidate cannot pass; failed measured tasks remain failures."""
    seen = [row.get('step') for row in tasks]
    for row in tasks:
        for key in ('fit_H','fit_E'):
            fit = row.get(key)
            if fit and (not fit.get('passed') or fit.get('stop_reason') == 'nonfinite'):
                return 'FAIL'
    if sorted(seen) != sorted(required):
        return 'INCOMPLETE'
    for row in tasks:
        if row.get('phase') != 'completed':
            return 'INCOMPLETE'
        for key in ('fit_H','fit_E'):
            fit = row.get(key)
            if not fit:
                return 'INCOMPLETE'
            r = fit.get('residual_ratio')
            if r is None or not (0 <= r < 1e-4) or fit.get('n_updates',501) > 500:
                return 'FAIL'
        value = row.get('fixed_amplitude_error')
        if value is None or not (0 <= value <= 1e-3):
            return 'FAIL'
    # This function certifies only development rows. Validation and G0 are
    # distinct requirements; caller may not promote this to full G1.
    return 'PASS'
