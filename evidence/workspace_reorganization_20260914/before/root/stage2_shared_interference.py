"""Measure whether the shared DCO is damaged by alternating H then E fitting."""
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
    ch0=s.yee_curl_H();h_before=rel_loss(s,s.H,ch0)
    ih,lh,th,ph,mh=s.inner_train(s.H,ch0);h_after_h=rel_loss(s,s.H,ch0)
    for k in range(3):ch0[k][:mh[0],:mh[1],:mh[2]]=ph[k]
    ke=s.dt/fdtd.EPS0
    for k in range(3):
        if k==0:s.E[0][:,1:-1,1:-1]+=ke*ch0[k]
        elif k==1:s.E[1][1:-1,:,1:-1]+=ke*ch0[k]
        else:s.E[2][1:-1,1:-1,:]+=ke*ch0[k]
    ce=s.yee_curl_E();e_before=rel_loss(s,s.E,ce)
    ie,le,te,pe,me=s.inner_train(s.E,ce);e_after=rel_loss(s,s.E,ce)
    h_after_e=rel_loss(s,s.H,ch0)
    result=dict(device=dev,initial_H=h_before,after_H_training=h_after_h,before_E=e_before,after_E_training=e_after,H_after_E=h_after_e,
                H_iters=ih,E_iters=ie,H_loss=lh,E_loss=le,H_degradation_ratio=h_after_e/max(h_after_h,1e-30))
    p=Path(a.out);p.parent.mkdir(exist_ok=True,parents=True);p.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
