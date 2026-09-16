"""Shared read-only evidence for v4 review figures and claims."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_review():
    return json.loads((ROOT / 'evidence/gpt6_plan_v4_review/audit.json').read_text(encoding='utf-8'))


def contract_checks(data):
    g = data['g0_counterexamples']
    sequence = data['recorder_crash']['sequence_ids']
    c = data['component_objective_stop']
    return {
        'reject_missing_rows': g['one_row_only']['status'] == 'FAIL',
        'reject_bad_numbers': g['bad_numbers_good_labels']['status'] == 'FAIL',
        'unique_recovery_sequence': len(sequence) == len(set(sequence)),
        'reject_terminal_resume': data['terminal_resume']['rejected'],
        'physical_R_is_stop_rule': not c['passed'] and c['physical_R'] >= 1e-4,
        'double_reference_at_measurement': data['reference_measurement_dtype']['comparison_reference'] == 'torch.float64',
    }
