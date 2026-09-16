"""Cheap coordinate-interface probe for the stage-2 solver."""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

import argparse
import json
from pathlib import Path
import numpy as np
import torch
import pidon_solve as S
import fdtd
import dco as D


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--init',default='dco_lr1e3_300.pt');ap.add_argument('--n',type=int,default=31);ap.add_argument('--out',default='evidence/stage2_interface_probe.json');a=ap.parse_args()
    dev='cuda' if torch.cuda.is_available() else 'cpu'
    ns=dict(n=a.n,side=50e-3,dt=3.075e-12,init=a.init,coords='cellsize',norm='rms',levels=4,base=32,lr=1e-3,max_inner=1,tol=1e-4,tol_mode='rel',fmax=15e9)
    s=S.Solver(argparse.Namespace(**ns),dev)
    g=fdtd.source_waveform(3,s.dt,ns['fmax'],'gauss')
    s.step(float(g[0]))
    # Compare the same post-source state with three trunk-coordinate encodings.
    targets={'H':s.yee_curl_H(),'E':s.yee_curl_E()}
    out=[]
    for mode in ['cellsize','centered','abs']:
        s.coords=D.make_coords((s.np_,)*3,s.d_mm,mode,device=dev)
        for name,field,target in [('H',s.H,targets['H']),('E',s.E,targets['E'])]:
            core=S.core_of(*field,s.n)
            m=tuple(min(t.shape[k] for t in target) for k in range(3));m=tuple(min(v,s.n) for v in m)
            tgt=torch.stack([t[:m[0],:m[1],:m[2]] for t in target])
            with torch.no_grad():pred=s.predict(core)[:,:m[0],:m[1],:m[2]]
            den=tgt.pow(2).sum().clamp_min(1e-30)
            rel=float(((pred-tgt).pow(2).sum()/den).cpu())
            out.append(dict(mode=mode,target=name,relative_loss=rel,target_rms=float(tgt.pow(2).mean().sqrt().cpu()),pred_rms=float(pred.pow(2).mean().sqrt().cpu())))
    p=Path(a.out);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(dict(init=a.init,device=dev,n=a.n,rows=out),indent=2),encoding='utf-8')
    for r in out:print(f"{r['mode']:>8s} {r['target']} rel_loss={r['relative_loss']:.4e} pred_rms={r['pred_rms']:.3e} target_rms={r['target_rms']:.3e}")


if __name__=='__main__':main()
