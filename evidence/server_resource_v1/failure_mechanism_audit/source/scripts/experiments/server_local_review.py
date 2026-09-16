"""Read-only diagnosis for the server-resource plan; never certifies propagation."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import time

import numpy as np

from project_paths import PROJECT_DIR, configure
configure()
from pidon_recording import atomic_json_save, sha256_file

ROOT = PROJECT_DIR
BASE = ROOT / 'evidence/server_resource_v1'
PROTOCOL = ROOT / 'docs/plans/2026-09-15-server-resource-protocol.md'
NAMES = ('Ex', 'Ey', 'Ez', 'Hx', 'Hy', 'Hz')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def read_rows(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8-sig').splitlines() if x.strip()]


def file_identity(path):
    path = Path(path)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha256_file(path)}


def new_output(name, action):
    out = BASE / name
    out.mkdir(parents=True, exist_ok=False)
    source = out / 'source'
    source.mkdir()
    hashes = {}
    for rel in ('scripts/experiments/server_local_review.py',
                'scripts/experiments/server_phase1_compare.py',
                'scripts/experiments/server_compute_probe.py',
                'scripts/experiments/server_short_tol_probe.py',
                'scripts/experiments/phase1_full_run.py', 'src/pidon/dco.py',
                'src/pidon/paper_protocol.py', 'src/pidon/pidon_contract.py',
                'src/pidon/pidon_solve.py', 'src/pidon/pidon_recording.py',
                'tools/server_resource_queue.py', 'tools/server_batch2_queue.py',
                'project_paths.py'):
        path = ROOT / rel
        if path.exists():
            dest = source / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            hashes[rel] = sha256_file(path)
    from project_harness import read_events, evidence_path
    starts = [e for e in read_events(ROOT) if e.get('event') == 'start' and e.get('action_id') == action]
    protocol = evidence_path(starts[0]['protocol'], ROOT) if len(starts) == 1 else PROTOCOL
    atomic_json_save({'action_id': action, 'lab_run_id': os.environ.get('PIDON_LAB_RUN_ID'),
                      'host': socket.gethostname(), 'source_hashes': hashes,
                      'protocol': file_identity(protocol)}, out / 'manifest.json')
    return out


def receipt_diagnosis(summary):
    grids = {}
    for grid, m in summary['blind_metrics'].items():
        individual = m['individual']
        macro = np.asarray([x['macro_nmae'] for x in individual], dtype=float)
        worst = int(np.argmax(macro))
        grids[grid] = {
            'macro_nmae_mean_recomputed': float(macro.mean()),
            'reported_mean_matches': bool(np.isclose(macro.mean(), m['macro_nmae_mean'], rtol=1e-10)),
            'worst_sample_index_zero_based': worst,
            'worst_sample_share_of_macro_sum': float(macro[worst] / macro.sum()),
            'sample_gate_pass_count': int((macro <= .01).sum()), 'samples': len(individual),
            'mean_gate_pass': bool(macro.mean() <= .01),
            'all_sample_gate_pass': bool((macro <= .01).all()),
            'relL2_p90': float(np.percentile([x['global_rel_l2'] for x in individual], 90)),
            'Eq5_MRE_mean': float(np.mean([x['macro_mre_eq5'] for x in individual])),
            'components': m['components'], 'individual': individual,
            'cell_size_range_mm': m.get('cell_size_range_mm'),
            'interpretation': 'summary arithmetic only; checkpoint predictions not locally verified',
        }
    return {'reported_status': summary['status'], 'reported_scientific_result': summary['scientific_result'],
            'reported_updates': summary['updates'], 'reported_elapsed_s': summary['elapsed_s'],
            'reported_action': summary['action_id'], 'reported_lab_run': summary['lab_run_id'],
            'grids': grids, 'recovery': 'UNVERIFIED; no local server checkpoint; budget exhausted',
            'source_probes': 'N/A_phase1_curl_operator'}


def cost_of_rows(rows):
    total = {'adam': 0, 'closures': 0, 'lbfgs_steps': 0, 'evaluations': 0}
    for row in rows:
        for phase in ('fit_H', 'fit_E'):
            fit = row.get(phase) or {}
            for key, field in (('adam', 'n_updates'), ('closures', 'n_closures'),
                               ('lbfgs_steps', 'n_lbfgs_steps'), ('evaluations', 'n_evals')):
                if field not in fit:
                    raise ValueError(f'missing cost {phase}.{field} at row {row.get("step")}')
                total[key] += int(fit[field])
    return total


def first_crossing(rows, field, threshold):
    for row in rows:
        metrics = row.get('six_component_metrics') or {}
        if field == 'nmae':
            values = [c['nmae'] for c in metrics.get('components', {}).values()
                      if not c['weak_reference'] and c.get('nmae') is not None]
            value = max(values) if values else None
        else:
            value = metrics.get(field)
        if value is not None and value > threshold:
            return {'accepted_steps': row['accepted_steps'], 'value': value}
    return None


def probe_metrics(rows):
    result = []
    for index in range(3):
        pairs = [(r['source_outside_probes'][index]['dut_Ez'],
                  r['source_outside_probes'][index]['ref_Ez']) for r in rows]
        arr = np.asarray(pairs, dtype=float)
        norm = np.linalg.norm(arr[:, 1])
        result.append({'index': index, 'cells': rows[-1]['source_outside_probes'][index]['cells'],
                       'ref_peak': float(np.abs(arr[:, 1]).max()),
                       'relative_l2': float(np.linalg.norm(arr[:, 0]-arr[:, 1])/norm) if norm else None,
                       'interpretation': 'observed window only; full-reference validity not certified'})
    return result


def checkpoint_metrics(path, row):
    import torch
    from pidon_contract import six_component_metrics
    ck = torch.load(path, map_location='cpu', weights_only=False)
    cfg = ck['frozen_config']
    h = cfg['side'] / cfg['n']
    ref = ck['reference']
    # The original _step_summary converts the float64 FDTD reference to DUT
    # dtype before metrics. Near-zero component denominators are sensitive.
    reference_e = [ref[k].to(dtype=ck['E'][i].dtype) for i, k in enumerate(NAMES[:3])]
    reference_h = [ref[k].to(dtype=ck['H'][i].dtype) for i, k in enumerate(NAMES[3:])]
    measured = six_component_metrics(ck['E'], ck['H'], reference_e,
                                     reference_h, (h, h, h),
                                     source_ez_index=(cfg['n']//2,)*3)
    saved = row['six_component_metrics']
    diffs = {}
    invalid = []
    for name in NAMES:
        for metric in ('absolute_mae', 'reference_max', 'nmae'):
            a, b = measured['components'][name][metric], saved['components'][name][metric]
            if b is None and metric == 'nmae' and measured['components'][name]['reference_max'] == 0:
                continue
            if b is None or not np.isfinite(a) or not np.isfinite(b):
                invalid.append(f'{name}.{metric}')
            else:
                diffs[f'{name}.{metric}'] = abs(a-b)
    return {'file': file_identity(path), 'accepted_steps': ck['accepted_steps'],
            'row_accepted_steps': row['accepted_steps'], 'max_abs_metric_difference': max(diffs.values()) if diffs else None,
            'invalid_metrics': invalid, 'consistent': not invalid and bool(diffs) and max(diffs.values()) <= 1e-8 and ck['accepted_steps'] == row['accepted_steps'],
            'reference_precision': 'matched_to_original_DUT_float32_before_metric',
            'six_components': measured, 'certification': 'readback_only_not_full_field_gate'}


def review_arm(path):
    summary = read_json(path / 'summary.json')
    rows = read_rows(path / 'steps.jsonl')
    accepted = [r for r in rows if r['accepted']]
    costs = cost_of_rows(rows)
    milestones = {}
    for n in (64, 128):
        checkpoint = path / f'snapshot_step_{n:04d}.pt'
        match = [r for r in accepted if r['accepted_steps'] == n]
        if checkpoint.exists() and match:
            milestones[str(n)] = checkpoint_metrics(checkpoint, match[0])
        else:
            milestones[str(n)] = {'status': 'NOT_AVAILABLE'}
    timeline = [{'accepted_steps': r['accepted_steps'],
                 'components': r['six_component_metrics']['components'],
                 'Q': r['six_component_metrics']['global_weighted_relative_l2'],
                 'A_fixed': r['six_component_metrics']['fixed_amplitude_error'],
                 'source_outside_probes': r['source_outside_probes']} for r in accepted]
    return {'arm': summary['arm'], 'original_status': summary['status'], 'accepted_steps': len(accepted),
            'count_consistent': len(accepted) == summary['accepted_steps'],
            'cost_from_all_rows_including_failures': costs,
            'cost_matches_summary': all(costs[k] == summary['budget'][k] for k in ('adam', 'closures', 'lbfgs_steps')),
            'first_observed_nmae_above_1pct': first_crossing(accepted, 'nmae', .01),
            'first_observed_Q_above_5pct': first_crossing(accepted, 'global_weighted_relative_l2', .05),
            'first_observed_A_above_1e3': first_crossing(accepted, 'fixed_amplitude_error', .001),
            'last_accepted_H_E': {k: accepted[-1][k] for k in ('fit_H', 'fit_E')},
            'failed_candidate_H_E': {k: rows[-1][k] for k in ('fit_H', 'fit_E')} if not rows[-1]['accepted'] else None,
            'six_components_last': accepted[-1]['six_component_metrics'],
            'source_point': accepted[-1]['source_probe_Ez'], 'probes': probe_metrics(accepted),
            'elapsed_s': summary['elapsed_s'], 'recovery': 'NOT_AUTHORIZED_original_field_or_fit_failure',
            'inputs': [file_identity(path / x) for x in ('summary.json', 'steps.jsonl')],
            'milestones': milestones, 'timeline': timeline}


def make_plot(result, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for arm in result['arms']:
        if 'timeline' not in arm:
            continue
        rows = arm['timeline']
        axes[0].plot([r['accepted_steps'] for r in rows], [r['Q']*100 for r in rows], label=arm['arm'])
        axes[1].plot([r['accepted_steps'] for r in rows], [r['A_fixed'] for r in rows], label=arm['arm'])
    axes[0].axhline(5, color='black', linestyle='--', linewidth=1)
    axes[1].axhline(.001, color='black', linestyle='--', linewidth=1)
    for ax, title in zip(axes, ('Observed-window Q (%)', 'Fixed amplitude error')):
        ax.set(xlabel='Accepted time steps', title=title)
        ax.legend(fontsize=8)
        ax.grid(alpha=.2)
    fig.suptitle('M2 read-only diagnosis; not full-duration field certification')
    fig.savefig(out / 'field_timeline.png', dpi=170)
    plt.close(fig)


def run(args):
    started = time.perf_counter()
    out = new_output(args.output_name, args.action_id)
    shutil.copy2(args.receipt, out / 'user_supplied_s1r_summary.json')
    result = {'action_id': args.action_id, 'lab_run_id': os.environ.get('PIDON_LAB_RUN_ID'),
              'new_adam_updates': 0, 'new_closures': 0, 'scientific_result': 'NOT_APPLICABLE',
              's1r': receipt_diagnosis(read_json(args.receipt)), 'arms': []}
    for rel in ('runs/A_R', 'runs/A_P', 'runs/B_R', 'runs/B_P', 'benefit/B_R2'):
        path = ROOT / 'evidence/direct_mechanism_v1' / rel
        try:
            result['arms'].append(review_arm(path))
        except Exception as exc:
            result['arms'].append({'arm': rel, 'status': 'INCOMPLETE', 'error': repr(exc)})
        print('reviewed', rel, flush=True)
    result['status'] = 'INCOMPLETE' if any('error' in r for r in result['arms']) else 'PASS'
    result['readback_consistent'] = all(m.get('consistent', False) for r in result['arms']
                                       for m in r.get('milestones', {}).values() if 'file' in m)
    if not result['readback_consistent']:
        result['status'] = 'INCOMPLETE'
    result['elapsed_s'] = time.perf_counter()-started
    result['limitations'] = [
        'S1R supplied summary only; remote hashes/checkpoints/ledger not locally verified.',
        'Original S1 plan says per-sample <=1%; code uses mean <=1%. Both reported; no old failure promoted.',
        'S1 checkpoint saver omits the independent shuffle generator state; true flag is not resume certification.',
        'M2 weak-reference flags use current reference peak, not the registered full-duration reference.',
        'Original M2 auditor omits Q and weak-component checks in field_gate_pass; negative evidence remains negative.',
        'M2 runner saves 64 snapshot but does not enforce its field gate before continuing to 128.',
    ]
    atomic_json_save(result, out / 'review.json')
    make_plot(result, out)
    lines = ['# 服务器资源首批：本地只读诊断', '',
             '新参数更新0次；下面是诊断，不是新增科学PASS。S1R数值来自用户原始摘要，服务器权重尚未本地读回。', '',
             '| S1R网格 | 宏nMAE | relL2 p90 | Eq5 MRE | 逐样本nMAE≤1% | 最差样本占宏误差总和 |',
             '|---|---:|---:|---:|---:|---:|']
    for grid, m in result['s1r']['grids'].items():
        lines.append(f"| {grid} | {m['macro_nmae_mean_recomputed']:.6f} | {m['relL2_p90']:.6f} | {m['Eq5_MRE_mean']:.6f} | {m['sample_gate_pass_count']}/{m['samples']} | {m['worst_sample_share_of_macro_sum']:.2%} |")
    lines += ['', '| 原在线臂 | 完整步 | Adam(含失败) | 首次当前Q>5%步 | 首次当前nMAE>1%步 | 成本一致 |', '|---|---:|---:|---|---|---|']
    for r in result['arms']:
        if 'error' in r:
            lines.append(f"| {r['arm']} | INCOMPLETE | | | | {r['error']} |")
            continue
        lines.append(f"| {r['arm']} | {r['accepted_steps']} | {r['cost_from_all_rows_including_failures']['adam']} | {r['first_observed_Q_above_5pct']} | {r['first_observed_nmae_above_1pct']} | {r['cost_matches_summary']} |")
    lines += ['', '## 解释和下一步', '',
              '较弱旋度分量会放大按分量峰值归一化的误差；保留该分量和绝对误差，不能删掉后宣称过门。',
              '完整训练已完成但盲测未过，需要同题比较旧新权重，不能从当前表断言新网络更差。',
              '在线误差曲线来自已保存逐步记录，64/128权重只读复算在JSON中；原场门FAIL保持。',
              '旧字段名mre_eq5_physical的严格零分支经E0/H0缩放，不能未经复核当物理单位Eq5。', '',
              '## 已发现的接口限制', ''] + ['- '+x for x in result['limitations']]
    (out / 'REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'output': str(out), 'new_updates': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--action-id', required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--output-name', choices=('local_review', 'local_review_v2'), default='local_review')
    run(parser.parse_args())
