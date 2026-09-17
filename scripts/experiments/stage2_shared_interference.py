"""Measure whether the shared DCO is damaged by alternating H then E fitting."""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

import argparse,json
from pathlib import Path
import numpy as np, torch
import pidon_solve as S
import fdtd

def rel_loss(s,field,target):
    n=s.n;core=S.core_of(*field,n);m=tuple(min(t.shape[k] for t in target) for k in range(3));m=tuple(min(v,n) for v in m)
    tgt=torch.stack([t[:m[0],:m[1],:m[2]] for t in target])
    with torch.no_grad():p=s.predict(core)[:,:m[0],:m[1],:m[2]]
    return float(((p-tgt).pow(2).sum()/tgt.pow(2).sum().clamp_min(1e-30)).cpu())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='evidence/stage2_shared_interference.json');a=ap.parse_args();dev='cuda' if torch.cuda.is_available() else 'cpu'
    ns=dict(n=31,side=50e-3,dt=3.075e-12,init='dco_lr1e3_300.pt',coords='cellsize',norm='rms',levels=4,base=32,lr=1e-3,max_inner=200,tol=1e-4,tol_mode='rel',fmax=15e9)
    s=S.Solver(argparse.Namespace(**ns),dev);g=fdtd.source_waveform(3,s.dt,ns['fmax'],'gauss');s.step(float(g[0]))
    # E02: the three H residuals have to be measured against the SAME exact
    # curl-H target.  The previous version overwrote ch0 in place with the
    # network's own prediction before the E half-step, so the "after E" H
    # residual was measured against a different reference than the two before
    # it -- numerator, denominator and target all changed at once, and the
    # published H_degradation_ratio=831.6 was not a like-for-like comparison.
    ch_exact=s.yee_curl_H()
    ch_measure=[t.clone() for t in ch_exact]
    h_before=rel_loss(s,s.H,ch_measure)
    ih,lh,th,ph,mh=s.inner_train(s.H,ch_exact);h_after_h=rel_loss(s,s.H,ch_measure)
    # The E update consumes the PREDICTED curl-H; that insertion goes into its
    # own array so the measurement target above stays immutable.
    ch_update=[t.clone() for t in ch_exact]
    for k in range(3):ch_update[k][:mh[0],:mh[1],:mh[2]]=ph[k]
    kx,ky,kz=s.cav.e_coefficients()
    s.E[0][:,1:-1,1:-1]+=kx*ch_update[0]
    s.E[1][1:-1,:,1:-1]+=ky*ch_update[1]
    s.E[2][1:-1,1:-1,:]+=kz*ch_update[2]
    ce=s.yee_curl_E();e_before=rel_loss(s,s.E,ce)
    ie,le,te,pe,me=s.inner_train(s.E,ce);e_after=rel_loss(s,s.E,ce)
    h_after_e=rel_loss(s,s.H,ch_measure)
    legacy_h_after_e=rel_loss(s,s.H,ch_update)
    result=dict(device=dev,initial_H=h_before,after_H_training=h_after_h,before_E=e_before,after_E_training=e_after,H_after_E=h_after_e,
                H_iters=ih,E_iters=ie,H_loss=lh,E_loss=le,H_degradation_ratio=h_after_e/max(h_after_h,1e-30),
                h_measurement_target="exact_yee_curl_H_frozen_before_any_training",
                legacy_H_after_E_vs_predicted_target=legacy_h_after_e,
                legacy_H_degradation_ratio=legacy_h_after_e/max(h_after_h,1e-30),
                correction_note=("E02：旧版本在E半步前用网络预测原位覆盖了H的测量目标，"
                                 "因此旧 H_degradation_ratio=831.6 不是同一目标下的前后比较。"
                                 "本版本固定精确 curl-H 作为三次测量的共同目标，"
                                 "并另存按旧口径的数值以便对照。原 evidence 文件保持不变。"))
    p=Path(a.out);p.parent.mkdir(exist_ok=True,parents=True);p.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
