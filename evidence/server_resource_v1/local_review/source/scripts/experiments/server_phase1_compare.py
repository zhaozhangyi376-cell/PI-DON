"""Zero-update server audit and matched evaluation of three existing DCOs."""
from __future__ import annotations

import argparse
import gc
import json
import os
import time

import numpy as np
import torch

from project_paths import PROJECT_DIR, configure
configure()
import dco as D
import phase1_full_run as F
from pidon_recording import atomic_json_save
from server_local_review import file_identity, new_output, read_json, read_rows

S1R = PROJECT_DIR / 'evidence/direct_mechanism_v2/s1r_phase1_server'
MODELS = (('old_paper32', PROJECT_DIR / 'assets/models/dco_paper32.pt'),
          ('old_lr1e3', PROJECT_DIR / 'assets/models/dco_lr1e3_300.pt'),
          ('S1R_best', S1R / 'best.pt'))


def audit_s1r():
    result = {'checks': {}, 'files': {}, 'missing': [],
              'resume_certified': False, 'additional_updates_authorized': False,
              'resume_reason': 'budget finished; independent shuffle RNG not certified'}
    checks = result['checks']
    required = ('history.jsonl', 'summary.json', 'audit.json', 'manifest.json', 'best.pt', 'last.pt',
                'train_dev_specs.json', 'blind_specs.json', 'S1_REPORT.md')
    for name in required:
        path = S1R / name
        if path.exists():
            result['files'][name] = file_identity(path)
        else:
            result['missing'].append(str(path))
    if result['missing']:
        result['status'] = 'INCOMPLETE'
        return result
    summary, history = read_json(S1R / 'summary.json'), read_rows(S1R / 'history.jsonl')
    checks['1000_continuous_epochs'] = [r['epoch'] for r in history] == list(range(1, 1001))
    checks['25_updates_each_epoch'] = all(r['updates'] == r['epoch']*25 for r in history)
    checks['summary_terminal_counts'] = summary['updates'] == 25000 and summary['epochs_completed'] == 1000
    checks['summary_matches_audit'] = read_json(S1R / 'audit.json')['summary'] == summary
    stage_path = S1R.parent / 'stage_status.json'
    if stage_path.exists():
        result['files']['stage_status'] = file_identity(stage_path)
        stage = read_json(stage_path).get('S1', {})
        checks['stage_matches_summary'] = all(stage.get(k) == summary.get(k) for k in
                                             ('status', 'scientific_result', 'updates', 'epochs_completed', 'best'))
    else:
        result['missing'].append(str(stage_path))
    dev = [r for r in history if 'dev' in r]
    selected = min(dev, key=lambda r: (r['dev']['macro_nmae_mean'], r['epoch']))
    checks['best_dev_selection'] = selected['epoch'] == summary['best']['epoch']
    checkpoints = {}
    for name in ('best.pt', 'last.pt'):
        ck = torch.load(S1R / name, map_location='cpu', weights_only=False)
        steps = sorted({int(v['step']) for v in ck['optimizer']['state'].values() if 'step' in v})
        expected = summary['best']['updates'] if name == 'best.pt' else summary['updates']
        checks[name+'_updates'] = ck['updates'] == expected and steps == [expected]
        checkpoints[name] = {'epoch': ck['epoch'], 'updates': ck['updates'], 'optimizer_steps': steps,
                             'rng_fields': sorted(ck.get('rng', {})),
                             'shuffle_generator_saved': 'generator_state' in ck or 'shuffle_generator' in ck.get('rng', {}),
                             'fields': sorted(ck)}
        del ck
    result['checkpoints'] = checkpoints
    ledger = PROJECT_DIR / 'records/lab_runs.jsonl'
    entries = [r for r in read_rows(ledger) if str(r.get('id')) == str(summary['lab_run_id'])] if ledger.exists() else []
    checks['one_matching_lab_run'] = len(entries) == 1
    if len(entries) == 1:
        entry = entries[0]
        checks['lab_exit_0_and_action'] = entry['exit_code'] == 0 and summary['action_id'] in entry.get('argv', [])
        result['original_lab_identity'] = {'id': entry['id'], 'host': entry.get('env', {}).get('host'),
                                           'seconds': entry.get('seconds'), 'exit_code': entry['exit_code']}
        outputs = {x['path'].replace('\\', '/'): x for x in entry.get('outputs', [])}
        for name in ('best.pt', 'last.pt', 'summary.json'):
            rel = (S1R / name).relative_to(PROJECT_DIR).as_posix()
            checks['lab_hash_'+name] = rel in outputs and outputs[rel].get('sha256') == result['files'][name]['sha256']
    result['status'] = 'PASS' if all(checks.values()) and not result['missing'] else 'INCOMPLETE'
    return result


def require_metadata(ck):
    if ck.get('coords') != 'cellsize' or ck.get('norm') != 'rms' or ck.get('head', 'direct') != 'direct':
        raise ValueError('unsupported metadata; do not guess or change checkpoint normalization')
    if 'levels' not in ck or 'base' not in ck:
        raise ValueError('missing network metadata')


def evaluate_one(model_path, data_path, device, prediction_path):
    ck = torch.load(model_path, map_location='cpu', weights_only=False)
    require_metadata(ck)
    net = D.DCO(levels=ck['levels'], base=ck['base'], head='direct').to(device)
    net.load_state_dict(ck['state'])
    with np.load(data_path) as arrays:
        e, c, spacing = arrays['E'], arrays['C'], arrays['D']
    if len(e) != 16 or len(c) != 16 or not np.isfinite(e).all() or not np.isfinite(c).all():
        raise ValueError('expected 16 finite saved evaluation samples')
    start = time.perf_counter()
    pred = F.predict_batches(net, torch.from_numpy(e), torch.from_numpy(spacing), device, 1)
    metrics = F.metric_summary(pred, c)
    metrics['global_nmae_mean'] = float(np.mean([x['global_nmae'] for x in metrics['individual']]))
    metrics['per_sample_gate_count'] = sum(x['macro_nmae'] <= .01 for x in metrics['individual'])
    metrics['all_sample_gate_pass'] = metrics['per_sample_gate_count'] == 16
    metrics['inference_and_metrics_s'] = time.perf_counter()-start
    metrics['spacing_range_mm'] = [float(spacing.min()*1e3), float(spacing.max()*1e3)]
    metrics['spacing_outside_training_fraction'] = float(np.mean((spacing < .0003) | (spacing > .0008)))
    np.save(prediction_path, pred)
    return metrics


def run(args):
    out = new_output('phase1_compare', args.action_id)
    torch.set_num_threads(4)
    device = torch.device(args.device)
    result = {'status': 'INCOMPLETE', 'scientific_result': 'NOT_APPLICABLE', 'new_adam_updates': 0,
              'action_id': args.action_id, 'lab_run_id': os.environ.get('PIDON_LAB_RUN_ID'),
              'new_closures': 0, 'strict_scores': {}, 'diagnostic_scores': [], 'errors': [],
              'source_point': 'N/A_phase1', 'six_EM_components': 'N/A_phase1',
              'blind_label': 'previously exposed set; diagnostic reevaluation only'}
    start = time.perf_counter()
    try:
        result['s1r_audit'] = audit_s1r()
    except Exception as exc:
        result['s1r_audit'] = {'status': 'INCOMPLETE', 'error': repr(exc)}
    atomic_json_save(result, out / 'progress.json')
    original = read_json(S1R / 'summary.json') if (S1R / 'summary.json').exists() else {}
    for tag, model in MODELS:
        for shape in F.BLIND_SHAPES:
            key = 'x'.join(map(str, shape))
            data = S1R / f'blind_data/blind_{key}.npz'
            row = {'model': tag, 'grid': key, 'status': 'INCOMPLETE'}
            try:
                row['inputs'] = {'model': file_identity(model), 'data': file_identity(data)}
                atomic_json_save(row, out / f'{tag}_{key}_inputs.json')
                metrics = evaluate_one(model, data, device, out / f'{tag}_{key}_pred.npy')
                row.update(status='PASS', metrics=metrics)
                if tag == 'S1R_best' and key in original.get('blind_metrics', {}):
                    saved = original['blind_metrics'][key]
                    row['matches_original_summary'] = all(np.isclose(metrics[k], saved[k], rtol=1e-4, atol=1e-7)
                                                         for k in ('macro_nmae_mean', 'global_rel_l2_p90', 'macro_mre_eq5_mean'))
                    if not row['matches_original_summary']:
                        row['status'] = 'INCOMPLETE'
            except Exception as exc:
                row['status'] = 'RESOURCE_LIMIT' if 'out of memory' in str(exc).lower() else 'INCOMPLETE'
                row['error'] = repr(exc)
                result['errors'].append(row.copy())
            result['diagnostic_scores'].append(row)
            atomic_json_save(result, out / 'progress.json')
            gc.collect()
            if device.type == 'cuda':
                torch.cuda.empty_cache()
            print(tag, key, row['status'], flush=True)
    result['elapsed_s'] = time.perf_counter()-start
    result['status'] = 'PASS' if (result['s1r_audit']['status'] == 'PASS' and
                                all(r['status'] == 'PASS' for r in result['diagnostic_scores'])) else 'INCOMPLETE'
    result['recovery_eligible'] = False
    atomic_json_save(result, out / 'summary.json')
    lines = ['# 新旧DCO同题诊断', '', '同一保存输入、各自原始权重/归一化；0更新。以下PASS仅为重测执行完成。', '',
             '| 模型 | 网格 | 执行状态 | global nMAE | 宏nMAE | relL2 p90 | Eq5 MRE |', '|---|---|---|---:|---:|---:|---:|']
    for r in result['diagnostic_scores']:
        m = r.get('metrics', {})
        vals = [f'{m[k]:.6g}' if k in m else 'N/A' for k in ('global_nmae_mean', 'macro_nmae_mean', 'global_rel_l2_p90', 'macro_mre_eq5_mean')]
        lines.append('| '+' | '.join([r['model'], r['grid'], r['status'], *vals])+' |')
    lines += ['', '逐样本/分量、间距外推比例、预测、哈希和完整性检查见summary.json；本表不认证论文或长程PASS。']
    (out / 'REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'output': str(out)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--action-id', required=True)
    parser.add_argument('--device', choices=('cuda', 'cpu'), default='cuda')
    run(parser.parse_args())
