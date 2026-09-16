"""Verify the registered short Algorithm-1 mechanism run from its JSON trace."""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

from pathlib import Path
import json
import numpy as np

PATH = Path('evidence/pidon_stage2_32_lr1e3_i200_postloss.json')


def read():
    j = json.loads(PATH.read_text(encoding='utf-8'))
    rows = j['rows']
    assert j['steps'] == 32 and len(rows) == 32
    keys = ['nmae', 'lossH', 'lossE', 'cum', 'itH', 'itE', 'probe_dut', 'probe_ref']
    assert all(k in r for r in rows for k in keys)
    assert all(np.isfinite([r[k] for k in keys if k not in ['itH', 'itE']]).all() for r in rows)
    assert all(0 <= r['itH'] <= 200 and 0 <= r['itE'] <= 200 for r in rows)
    nmae = np.array([r['nmae'] for r in rows])
    loss_h = np.array([r['lossH'] for r in rows])
    loss_e = np.array([r['lossE'] for r in rows])
    cum = np.array([r['cum'] for r in rows])
    return j, dict(
        finite=bool(np.isfinite(nmae).all() and np.isfinite(loss_h).all() and np.isfinite(loss_e).all()),
        max_nmae=float(nmae.max()), final_nmae=float(nmae[-1]), final_cum=float(cum[-1]),
        median_loss_h=float(np.median(loss_h[1:])), median_loss_e=float(np.median(loss_e[1:])),
        steps_hit_h=int(sum(r['itH'] < 200 and r['itH'] > 0 for r in rows)),
        steps_hit_e=int(sum(r['itE'] < 200 and r['itE'] > 0 for r in rows)),
        max_loss_e=float(loss_e.max()), max_cum=float(cum.max()))


def claims():
    j, f = read()
    return [
        ('M0', f['finite'] and len(j['rows']) == 32,
         f"32/32步有记录；字段和场值有限；dt/CFL={j['dt'] / 3.1062e-12:.4f}"),
        ('M1', sum(r['itH'] + r['itE'] for r in j['rows']) > 0,
        f"平均内层次数 H={np.mean([r['itH'] for r in j['rows']]):.1f}, E={np.mean([r['itE'] for r in j['rows']]):.1f}"),
        ('M2', f['final_nmae'] < 1e-3 and f['max_nmae'] < 1e-3,
         f"末步nMAE={f['final_nmae']:.3e}；全程最大={f['max_nmae']:.3e}"),
        ('M3', f['steps_hit_h'] + f['steps_hit_e'] >= 2 * 31,
         f"非零curl-H达到阈值{f['steps_hit_h']}/31，curl-E达到{f['steps_hit_e']}/32；最大curl-E loss={f['max_loss_e']:.2e}"),
    ]


if __name__ == '__main__':
    j, f = read()
    for cid, ok, val in claims():
        print(('PASS' if ok else 'FAIL'), cid, '|', val)
    print(json.dumps(f, ensure_ascii=False, indent=2))
