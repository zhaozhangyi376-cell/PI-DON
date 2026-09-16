"""Explicit reconstruction of paper Fig.5/6; not the author's undisclosed data.

All metric inputs are PHYSICAL fields/curls. Eq.(5) uses an exact-zero branch.
The three per-component metrics and their arithmetic means are reported;
legacy global nMAE is kept separately, never substituted for paper MRE.
"""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

import numpy as np

VERSION = 'paper-protocol-v1'
SHAPES = ((32,32,32), (64,64,64), (64,96,16), (32,64,16))
E_OFFSETS = ((.5,0,0), (0,.5,0), (0,0,.5))
H_OFFSETS = ((0,.5,.5), (.5,0,.5), (.5,.5,0))
PAPER_MRE = {'64x64x64': .0041, '64x96x16': .0038, '32x64x16': .0047}


def scalar_metrics(pred, true):
    p, t = np.asarray(pred, dtype=np.float64), np.asarray(true, dtype=np.float64)
    if p.shape != t.shape or not p.size or not np.isfinite(p).all() or not np.isfinite(t).all():
        raise ValueError('metrics need equal, nonempty, finite arrays')
    err = np.abs(p - t)
    nonzero = t != 0
    terms = np.abs(p).copy()
    np.divide(err, np.abs(t), out=terms, where=nonzero)
    peak, norm = float(np.max(np.abs(t))), float(np.linalg.norm(t.ravel()))
    near = nonzero & (np.abs(t) < .01 * peak)
    total = terms.sum()
    return dict(mre_eq5=float(terms.mean()), mae=float(err.mean()),
                nmae=float(err.mean()/peak) if peak else None,
                rel_l2=float(np.linalg.norm(err.ravel())/norm) if norm else None,
                max_abs_error=float(err.max()), true_max=peak,
                zero_fraction=float((~nonzero).mean()),
                near_zero_fraction=float(near.mean()),
                near_zero_mre_share=float(terms[near].sum()/total) if total else 0.)


def vector_metrics(pred, true):
    if np.shape(pred) != np.shape(true) or np.shape(true)[0] != 3:
        raise ValueError('expected a vector field with first dimension 3')
    cs = {name: scalar_metrics(pred[k], true[k]) for k,name in enumerate('xyz')}
    full = scalar_metrics(pred, true)
    return dict(components=cs,
                macro_mre_eq5=float(np.mean([v['mre_eq5'] for v in cs.values()])),
                macro_nmae=(float(np.mean([v['nmae'] for v in cs.values()]))
                            if all(v['nmae'] is not None for v in cs.values()) else None),
                global_nmae=full['nmae'], global_rel_l2=full['rel_l2'])


def wave_spec(seed):
    theta, phi = np.deg2rad([45.,60.])
    direction = np.array([np.cos(phi)*np.sin(theta), np.sin(phi)*np.sin(theta), np.cos(theta)])
    rng = np.random.default_rng(seed)
    amp = np.empty((20,3))
    amp[:,0] = rng.uniform(0,5,20)
    amp[:,1] = rng.uniform(0,5,20)
    amp[:,2] = -(direction[0]*amp[:,0] + direction[1]*amp[:,1])/direction[2]
    return dict(seed=int(seed), theta_deg=45., phi_deg=60.,
                k=np.linspace(.021,838.34,20).tolist(), direction=direction.tolist(),
                amplitude=amp.tolist(), phase_rad=[0.]*20)


def sample_wave(spec, shape, extent=.0192):
    """N cells over extent; sample each field component at its own Yee position.

    Assumptions: real part of Eq.(2), zero phases, U[0,5] amplitudes, L/N
    spacing and staggered fields. They are explicit because the exact Fig.5
    amplitude realization and complex representation are not disclosed.
    """
    shape = tuple(shape)
    h = np.array([extent/n for n in shape])
    xyz = np.meshgrid(*[np.arange(n)*d for n,d in zip(shape,h)], indexing='ij', sparse=True)
    e, c = np.zeros((3,*shape)), np.zeros((3,*shape))
    direction = np.asarray(spec['direction'])
    for k, amp in zip(spec['k'], spec['amplitude']):
        kv, amp = k*direction, np.asarray(amp)
        phase = sum(kv[j]*xyz[j] for j in range(3))
        cross = np.cross(kv, amp)
        for j in range(3):
            pe = phase + np.dot(kv*h, E_OFFSETS[j])
            pc = phase + np.dot(kv*h, H_OFFSETS[j])
            e[j] += amp[j]*np.cos(pe)
            c[j] -= cross[j]*np.sin(pc)
    return e, c, h
