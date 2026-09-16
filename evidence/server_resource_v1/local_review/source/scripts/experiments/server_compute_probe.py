"""Bounded FP32 throughput probe, at most 15 scratch Adam updates."""
from __future__ import annotations

import argparse
import copy
import gc
import json
import os
import time

import numpy as np
import torch

from project_paths import configure
configure()
import dco as D
import phase1_full_run as F
from pidon_recording import atomic_json_save
from server_local_review import new_output, file_identity
from server_phase1_compare import S1R


def state_distance(a, b):
    error = denom = maximum = 0.0
    for key in a:
        x, y = a[key].double(), b[key].double()
        delta = x-y
        error += float((delta*delta).sum())
        denom += float((y*y).sum())
        maximum = max(maximum, float(delta.abs().max()))
    relative = (error/max(denom, 1e-30))**.5
    return {'relative_l2': relative, 'max_abs': maximum, 'pass': relative <= 1e-4 and maximum <= 1e-5}


def run(args):
    out = new_output('compute_probe', args.action_id)
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    result = {'status': 'INCOMPLETE', 'scientific_result': 'NOT_APPLICABLE', 'arms': [],
              'action_id': args.action_id, 'lab_run_id': os.environ.get('PIDON_LAB_RUN_ID'),
              'new_closures': 0, 'new_adam_updates': 0, 'total_cap': 15,
              'recovery_eligible': False, 'device': str(args.device), 'torch': str(torch.__version__)}
    try:
        if args.device == 'cuda' and not torch.cuda.is_available():
            raise RuntimeError('CUDA unavailable')
        data = S1R / 'train_dev_data.npz'
        result['input'] = file_identity(data)
        atomic_json_save(result, out / 'progress.json')
        with np.load(data) as saved:
            e = torch.from_numpy(saved['E'][:32].copy())
            c = torch.from_numpy(saved['C'][:32].copy())
            spacing = torch.from_numpy(saved['D'][:32].copy())
        if e.shape != (32, 3, 32, 32, 32):
            raise ValueError('unexpected training data shape')
        device = torch.device(args.device)
        torch.manual_seed(2026091507)
        initial = D.DCO(levels=4, base=32).state_dict()
        torch.save(initial, out / 'initial.pt')
        baseline = None
        start = time.perf_counter()
        for micro in (4, 8, 16):
            row = {'microbatch': micro, 'effective_batch': 32, 'updates': 0,
                   'status': 'INCOMPLETE', 'timings_s': [], 'losses': [], 'unknown_tail': False}
            net = optimizer = None
            attempted = False
            try:
                net = D.DCO(levels=4, base=32).to(device)
                net.load_state_dict(initial)
                optimizer = torch.optim.Adam(net.parameters(), lr=1e-4)
                if device.type == 'cuda':
                    torch.cuda.reset_peak_memory_stats()
                for step in range(5):
                    if device.type == 'cuda':
                        torch.cuda.synchronize()
                    t = time.perf_counter()
                    attempted = True
                    loss = F.train_microbatch(net, optimizer, e, c, spacing, torch.arange(32), micro, device)
                    row['updates'] += 1
                    attempted = False
                    if device.type == 'cuda':
                        torch.cuda.synchronize()
                    row['timings_s'].append(time.perf_counter()-t)
                    row['losses'].append(loss)
                    atomic_json_save(row, out / f'micro{micro}_heartbeat.json')
                    if not np.isfinite(loss):
                        raise ValueError('nonfinite loss')
                    if step == 0:
                        first = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
                        if micro == 4:
                            baseline = copy.deepcopy(first)
                        row['first_step_equivalence'] = state_distance(first, baseline) if baseline is not None else {'pass': False, 'reason': 'baseline unavailable'}
                row['median_timed_update_s'] = float(np.median(row['timings_s'][2:]))
                row['status'] = 'PASS'
            except Exception as exc:
                row['status'] = 'RESOURCE_LIMIT' if 'out of memory' in str(exc).lower() else 'INCOMPLETE'
                row['error'] = repr(exc)
                row['unknown_tail'] = attempted
            finally:
                if device.type == 'cuda':
                    row['peak_allocated_bytes'] = torch.cuda.max_memory_allocated()
                    row['peak_reserved_bytes'] = torch.cuda.max_memory_reserved()
                if net is not None:
                    torch.save({'state': net.state_dict(), 'optimizer': optimizer.state_dict() if optimizer else None,
                                'row': row, 'rng_cpu': torch.get_rng_state(),
                                'rng_cuda': torch.cuda.get_rng_state_all() if device.type == 'cuda' else None,
                                'production_resume_allowed': False}, out / f'micro{micro}_last.pt')
                result['arms'].append(row)
                result['new_adam_updates'] = sum(r['updates'] for r in result['arms'])
                atomic_json_save(result, out / 'progress.json')
                print('microbatch', micro, row['status'], 'committed', row['updates'], flush=True)
                del net, optimizer
                gc.collect()
                if device.type == 'cuda':
                    torch.cuda.empty_cache()
        qualified = [r for r in result['arms'] if r['status'] == 'PASS' and r['first_step_equivalence']['pass']]
        result['recommended_microbatch'] = min(qualified, key=lambda r: r['median_timed_update_s'])['microbatch'] if qualified else None
        result['unknown_tail'] = any(r['unknown_tail'] for r in result['arms'])
        result['elapsed_s'] = time.perf_counter()-start
        result['status'] = 'PASS' if qualified and not result['unknown_tail'] else 'INCOMPLETE'
    except Exception as exc:
        result['error'] = repr(exc)
        atomic_json_save(result, out / 'failure.json')
    atomic_json_save(result, out / 'summary.json')
    (out / 'REPORT.md').write_text('# GV100临时吞吐诊断\n\n仅工程测速；不计DCO或PI-DON成绩。\n\n```json\n'+json.dumps(result, ensure_ascii=False, indent=2)+'\n```\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'output': str(out), 'updates': result['new_adam_updates']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--action-id', required=True)
    parser.add_argument('--device', choices=('cuda', 'cpu'), default='cuda')
    run(parser.parse_args())
