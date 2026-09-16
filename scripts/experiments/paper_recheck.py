"""Bounded G0/G1 milestone: validate physics baseline and re-evaluate old weights.

No training. Run with lab_log.py. Outputs are new and source/weight hashes are
recorded. Existing checkpoint normalization is preserved deliberately.
"""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import time
import unittest

import numpy as np
import torch
import dco as D
import fdtd
import paper_protocol as P


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def reference(arrays):
    # Explicit candidate: 31 intervals, paper dt, nearest central Ez Yee edge.
    cav = fdtd.PECCavity(n=31, side=.05, dt=3.075e-12)
    nsteps, src, probe = 8192, (15,15,15), (12,12,13)
    g, tau, t0 = fdtd.gaussian_pulse(nsteps, cav.dt, f_max=15e9)
    trace = np.empty(nsteps)
    slices, monitor = {}, []
    start = time.perf_counter()
    for i in range(nsteps):
        cav.step(src_value=g[i], src_idx=src, src_mode='hard')
        trace[i] = cav.Ez[probe]
        if i+1 in (300,600,900): slices[str(i+1)] = cav.Ez[:,:,13].copy()
        if (i+1) % 128 == 0:
            fields = (cav.Ex,cav.Ey,cav.Ez,cav.Hx,cav.Hy,cav.Hz)
            if not all(np.isfinite(a).all() for a in fields):
                raise RuntimeError(f'nonfinite FDTD state at step {i+1}')
            monitor.append([i+1,max(float(np.abs(a).max()) for a in fields[:3])])
    peaks, f, spectrum = fdtd.spectrum_peaks(trace, cav.dt, n_peaks=20)
    rows = []
    for mode, target in fdtd.analytic_modes().items():
        measured = min(peaks, key=lambda x: abs(x-target))
        rows.append(dict(mode=''.join(map(str,mode)), analytic_GHz=target/1e9,
                         measured_GHz=measured/1e9, error_pct=100*(measured-target)/target))
    arrays.update(fdtd_trace=trace, fdtd_source=g, fdtd_f=f[f<=15e9],
                  fdtd_spectrum=spectrum[f<=15e9], fdtd_monitor=np.array(monitor))
    for key,value in slices.items(): arrays['fdtd_slice_'+key] = value
    return dict(n_intervals=31, side_m=.05, dt_s=cav.dt, steps=nsteps,
                cfl_ratio=cav.dt/fdtd.cfl_dt(cav.dx,cav.dy,cav.dz,safety=1),
                source_idx=src, probe_idx=probe, source_type='hard Gaussian',
                source_tau_s=tau, source_t0_s=t0, fmax_Hz=15e9,
                spatial_convention='E/H Yee locations in fdtd.py; z slice index 13 is Ez at 13.5 dz',
                interpretation='31-interval candidate, not an author-confirmed grid convention',
                peak_method='Hann + 2^20 zero padding + parabolic peak fit; no added physical resolution',
                raw_fft_bin_Hz=1/(nsteps*cav.dt), modes=rows, finite=True,
                seconds=time.perf_counter()-start)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ckpts', nargs='+', default=['dco_paper32.pt','dco_lr1e3_300.pt'])
    ap.add_argument('--seeds', nargs='+', type=int, default=[0,1,2])
    ap.add_argument('--device', choices=['cuda','cpu'], default='cuda' if torch.cuda.is_available() else 'cpu')
    ap.add_argument('--out', default='evidence/paper_first_v1')
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)  # Never overwrite an earlier experiment.
    srcdir = out/'source'; srcdir.mkdir()
    files = ['paper_protocol.py','paper_recheck.py','test_paper_protocol.py','dco.py',
             'fdtd.py','verify_claims.py','lab_log.py']
    sources = {}
    for f in files:
        shutil.copy2(f, srcdir/f)
        sources[f] = sha256(f)
    try:
        commit = subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip()
    except subprocess.SubprocessError: commit = None
    manifest = dict(protocol=P.VERSION, sources=sources, commit=commit,
                    device=a.device, torch=torch.__version__, numpy=np.__version__,
                    checkpoint_paths=a.ckpts, seeds=a.seeds,
                    assumptions=['real part; zero phases; U[0,5] Ex/Ey amplitudes are a reconstruction',
                                 'same 20 k and amplitudes reused across all grids for each seed',
                                 'L=19.2 mm each axis, dx=L/N; each component at its Yee position',
                                 'seed 0/1/2 test amplitude sensitivity; not independent training runs',
                                 'checkpoint RMS/max and coords retained; no normalization with truth',
                                 'MRE exact-zero branch on physical curl, units field per metre',
                                 'all voxels including boundaries; report x/y/z and arithmetic mean',
                                 'paper Fig6 metric aggregation is ambiguous; x used as a stated gate, macro also reported'],
                    criteria=dict(analytic_tests='all pass',
                                  fdtd_modes='all five relative frequency errors <0.5%; finite 8192-step fields',
                                  dco_gate='at least one checkpoint has x-component Eq5 MRE <= Fig6 caption value on all three sizes and all seeds; conditional on stated reconstruction only'))
    dump(out/'manifest.json', manifest)
    # The suite now also checks the concrete generator consumed by this run.
    suite = unittest.defaultTestLoader.loadTestsFromName('test_paper_protocol')
    stream = io.StringIO()
    res = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    (out/'tests.txt').write_text(stream.getvalue(), encoding='utf-8')
    if not res.wasSuccessful(): raise RuntimeError(stream.getvalue())
    result = dict(protocol=P.VERSION, test_count=res.testsRun, tests_passed=True,
                  manifest_sha256=sha256(out/'manifest.json'), models=[], rows=[])
    arrays = {}
    print('G0: running independent source/probe FDTD reference (8192 steps)', flush=True)
    result['reference'] = reference(arrays)
    print('FDTD modes:', result['reference']['modes'], flush=True)
    cases = []
    for seed in a.seeds:
        spec = P.wave_spec(seed)
        manifest.setdefault('wave_specs', []).append(spec)
        for shape in P.SHAPES:
            size = 'x'.join(map(str,shape)); key=f's{seed}_{size}'
            e,c,h = P.sample_wave(spec, shape)
            # Saving the exact target and input used; no plot reconstruction from memory.
            arrays[key+'_E'], arrays[key+'_true'] = e, c
            cases.append((seed,size,key,e,c,h))
    dump(out/'manifest.json', manifest)
    result['manifest_sha256'] = sha256(out/'manifest.json')
    torch.set_num_threads(4)
    if a.device == 'cuda':
        torch.backends.cudnn.benchmark = False
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
    for ckpath in a.ckpts:
        before = sha256(ckpath)
        ck = torch.load(ckpath, map_location='cpu', weights_only=False)
        meta = {k:ck.get(k) for k in ['levels','base','grid','epoch','coords','norm','head','target','dirs']}
        if meta['coords'] is None or meta['norm'] is None:
            raise ValueError(f'{ckpath}: normalization/coordinate metadata is required')
        tag=Path(ckpath).stem
        print('checkpoint', tag, meta, flush=True)
        net = D.DCO(levels=ck['levels'], base=ck['base'], head=ck.get('head','direct'))
        net.load_state_dict(ck['state']); net.to(a.device).eval()
        del ck
        model = dict(tag=tag, path=ckpath, sha256=before, metadata=meta)
        result['models'].append(model)
        for seed,size,key,e,c,h in cases:
            start=time.perf_counter()
            x = torch.from_numpy(e).float()[None].to(a.device)
            dd = torch.tensor(h*1e3, dtype=torch.float32, device=a.device).view(1,3)
            coords=D.make_coords(e.shape[1:], (h*1e3).tolist(), meta['coords'], device=a.device)
            with torch.inference_mode():
                eh,_,scale,Lc = D.normalise(x,None,dd,meta['norm'])
                pred = D.denormalise(net(eh,coords,D.d_rel_of(dd,Lc)),scale,Lc)[0].cpu().numpy()
            if not np.isfinite(pred).all(): raise RuntimeError(f'nonfinite prediction {tag} {key}')
            arrays[tag+'_'+key+'_pred'] = pred
            metrics = P.vector_metrics(pred,c)
            row=dict(model=tag, seed=seed, size=size, array_key=key, spacing_m=h.tolist(),
                     metrics=metrics, seconds=time.perf_counter()-start)
            result['rows'].append(row)
            print(f'{tag} seed={seed} {size}: MRE x={metrics["components"]["x"]["mre_eq5"]:.5g}'
                  f' macro={metrics["macro_mre_eq5"]:.5g}  nMAE macro={metrics["macro_nmae"]:.5g}', flush=True)
            del x,coords,eh,pred
        model['sha256_after'] = sha256(ckpath)
        if before != model['sha256_after']: raise RuntimeError('checkpoint changed during evaluation')
        del net
        if a.device=='cuda': torch.cuda.empty_cache()
    np.savez_compressed(out/'arrays.npz', **arrays)
    result['arrays_sha256'] = sha256(out/'arrays.npz')
    dump(out/'summary.json', result)
    print('Saved',out,'No optimizer, no weight changes.',flush=True)


if __name__ == '__main__': main()
