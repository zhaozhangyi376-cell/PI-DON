"""Isolated v3 audit. No production edits or formal model updates."""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

from pathlib import Path
from unittest.mock import patch
from collections import Counter
import copy
import json
import shutil
import subprocess
import torch

import g0_verifier
import pidon_recording as rec
import pidon_solve as sol
from pidon_exact_control import control_args, _reference_tensors
from test_pidon_contract_v3 import tiny_args

ROOT = PROJECT_ROOT
OUT = ROOT / 'evidence/gpt6_plan_v4_review'
OLD = ROOT / 'evidence/gpt6_plan_v3'


def main():
    torch.set_num_threads(2)
    torch.manual_seed(20260913)
    destination = OUT / 'audit.json'
    if destination.exists():
        raise FileExistsError(destination)
    snapshot = OUT / 'source_snapshot'
    snapshot.mkdir(exist_ok=False)
    for name in ('pidon_solve.py', 'pidon_contract.py', 'pidon_recording.py',
                 'pidon_exact_control.py', 'g0_verifier.py', 'h_layout_candidate.py',
                 'a1_contract_report.py', 'reference_cache.py', 'audit_night_v4.py'):
        shutil.copy2(ROOT / name, snapshot / name)
    (OUT / 'git_status.txt').write_text(subprocess.check_output(
        ['git', 'status', '--short'], cwd=ROOT, text=True, encoding='utf-8'), encoding='utf-8')
    (OUT / 'working_tree.diff').write_bytes(subprocess.check_output(['git', 'diff'], cwd=ROOT))
    findings = {}
    contract = json.loads((OLD / 'contract_test_results.json').read_text(encoding='utf-8'))
    ids = [row['test'] for row in contract['tests']]
    findings['test_inventory'] = {'reported': contract['observed']['tests_run'],
        'rows': len(ids), 'unique_ids': len(set(ids)),
        'duplicates': {key: count for key, count in Counter(ids).items() if count > 1}}
    exact = json.loads((OLD / 'A2_exact_control.json').read_text(encoding='utf-8'))['float64']
    truncated = copy.deepcopy(exact)
    truncated['rows'] = truncated['rows'][-1:]
    corrupted = copy.deepcopy(exact)
    corrupted['max_global_relative_l2'] = 1.0
    for row in corrupted['rows']:
        metrics = row.get('accepted_field_metrics') or {}
        metrics['global_relative_l2'] = 1.0
        for component in metrics.get('components', {}).values():
            component['nmae'] = 1.0
            component['relative_l2'] = 1.0
    findings['g0_counterexamples'] = {
        'one_row_only': g0_verifier.full_control('one_row_only', truncated, True),
        'bad_numbers_good_labels': g0_verifier.full_control('bad_numbers', corrupted, True),
        'expected': 'both must FAIL'}
    metadata = {'run_id': 'v4-isolated-recorder-crash', 'protocol_hash': 'v4-audit-only'}
    folder = OUT / 'jsonl_crash_counterexample'
    recorder = rec.RunRecorder(folder, metadata)
    try:
        with patch.object(rec, 'atomic_json_save', side_effect=OSError('injected metadata commit failure')):
            recorder.append({'kind': 'durable_line_before_metadata_crash'})
    except OSError:
        pass
    resumed = rec.RunRecorder(folder, metadata, mode='resume')
    tail = list(resumed.metadata['recovery_tail_sequence_ids'])
    resumed.append({'kind': 'after_resume'})
    rows = [json.loads(line) for line in (folder / 'steps.jsonl').read_text(encoding='utf-8').splitlines()]
    findings['recorder_crash'] = {'sequence_ids': [row['sequence_id'] for row in rows],
        'recognized_tail_before_append': tail, 'expected': 'unique increasing IDs and preserved tail'}
    args = tiny_args()
    initial = sol.Solver(args, 'cpu')
    initial.H = [torch.randn_like(part) for part in initial.H]
    initial.fit_progress['H'].update(stop_reason='nonfinite', resumable=False)
    state = initial.state_payload()
    reloaded = sol.Solver(args, 'cpu')
    try:
        reloaded.load_state_payload(state)
        fit = reloaded.inner_train(reloaded.H, reloaded.yee_curl_H(), 'H')
        findings['terminal_resume'] = {'rejected': False, 'actual_cpu_test_updates': fit.n_updates,
            'stop_reason': fit.stop_reason, 'expected': 'reject terminal state before update'}
    except ValueError as error:
        findings['terminal_resume'] = {'rejected': True, 'reason': str(error)}
    args = tiny_args()
    args.max_inner, args.component_rel, args.tol = 0, True, 1e-4
    example = sol.Solver(args, 'cpu')
    example.H = [torch.ones_like(part) for part in example.H]
    target = [torch.full((3, 3, 3), value) for value in (100., 1., 1.)]
    predicted = torch.stack([torch.full((3, 3, 3), value) for value in (101.5, 1., 1.)])
    with patch.object(example, 'predict', return_value=predicted):
        fit = example.inner_train(example.H, target, 'H')
    physical_r = sum(float((predicted[k] - target[k]).square().sum()) for k in range(3)) / sum(float(x.square().sum()) for x in target)
    findings['component_objective_stop'] = {'passed': fit.passed, 'physical_R': physical_r,
        'fit': fit.as_dict(), 'expected': 'R>=1e-4 must fail regardless of optimization objective'}
    f32solver = sol.Solver(control_args(torch.float32), 'cpu')
    ref = sol.fdtd.PECCavity(side=.05, n=31, dt=3.075e-12)
    tensors = _reference_tensors(ref, f32solver)
    findings['reference_measurement_dtype'] = {'numpy_reference': str(ref.Ex.dtype),
        'comparison_reference': str(tensors[0][0].dtype), 'expected': 'torch.float64'}
    development_path = next(OLD.rglob('A3_development.json'))
    development = json.loads(development_path.read_text(encoding='utf-8'))
    task_folder = development_path.parent
    old_rows = []
    for task in development['tasks']:
        for role, file_prefix, trace_name in (('H', 'H', 'fit_H_trace'), ('E', 'E_oracle', 'trace')):
            path = task_folder / f'{file_prefix}_step_{task["step"]:04d}.pt'
            state = torch.load(path, map_location='cpu', weights_only=False)
            prediction, target = state['prediction'], state['target']
            numerator = sum(float((p.double()-t.double()).square().sum()) for p,t in zip(prediction,target))
            denominator = sum(float(t.double().square().sum()) for t in target)
            components = []
            for p,t in zip(prediction,target):
                p,t = p.double(),t.double()
                interior = torch.zeros_like(t, dtype=torch.bool)
                interior[1:-1,1:-1,1:-1] = True
                diff = (p-t).square()
                ss = float(t.square().sum())
                components.append({'shape': list(t.shape), 'SSE': float(diff.sum()),
                    'target_ss': ss, 'R': float(diff.sum())/ss if ss else None,
                    'boundary_SSE_fraction': float(diff[~interior].sum()) / max(float(diff.sum()),1e-300),
                    'boundary_target_fraction': float(t[~interior].square().sum())/ss if ss else None})
            trace = task[trace_name] if role == 'H' else task['oracle_E'][trace_name]
            at400 = next((row['loss'] for row in trace if row['updates']==400),None)
            opt_steps = [int(row['step']) for row in state[f'opt_{role}']['state'].values() if 'step' in row]
            old_rows.append({'step': task['step'], 'role': role, 'path': str(path.relative_to(ROOT)),
                'sha256': rec.sha256_file(path), 'file_bytes': path.stat().st_size,
                'saved_parameter_R': state['saved_parameter_R'], 'R_saved_arrays_float64': numerator/denominator,
                'components': components, 'progress': state['fit_progress'][role],
                'optimizer_steps': sorted(set(opt_steps)), 'phase': state['phase'],
                'current_time_layer': state['current_time_layer'], 'extra_time_layer': state['time_layer'],
                'source_index': state['source_index'], 'loss_at_400': at400,
                'loss_at_500': trace[-1]['loss'],
                'last_100_relative_reduction': (at400-trace[-1]['loss'])/at400 if at400 else None})
    findings['historical_fits'] = old_rows
    findings['resources'] = {'disk_free_bytes': shutil.disk_usage(ROOT).free,
        'max_task_checkpoint_bytes': max(row['file_bytes'] for row in old_rows),
        '128_immutable_checkpoints_bytes': 128*max(row['file_bytes'] for row in old_rows)}
    findings['formal_dco_updates_this_audit'] = 0
    findings['source_hashes'] = {p.name:rec.sha256_file(p) for p in snapshot.iterdir()}
    findings['historical_G0_inputs_current_hash_match'] = {
        path: rec.sha256_file(ROOT/path)==sha for path,sha in json.loads((OLD/'G0.json').read_text(encoding='utf-8'))['inputs'].items()}
    destination.write_text(json.dumps(findings,ensure_ascii=False,indent=2,allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({'out': str(destination), 'findings': {key:value for key,value in findings.items()
        if key not in ('historical_fits','source_hashes','test_inventory')}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
