"""Warm-start a DCO on fields actually seen in the PEC cavity.

This is an explicit diagnostic extension, not a paper claim: the paper only
describes free-space plane-wave pretraining.  It tests whether the long-run
drift comes from a distribution shift between those waves and staggered Yee
cavity fields.  We collect FDTD states and exact Yee curls, crop/pad each
component to the DCO's common n^3 interface, and fine-tune the pretrained DCO.
"""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

import argparse, json, time
import numpy as np
import torch
import dco as D
import fdtd

def collect(n, ns, fmax, warmup=20):
    cav = fdtd.PECCavity(side=50e-3, n=n, dt=3.075e-12)
    # Skip the source's near-zero leading edge.  With physical SI units H is
    # still ~1e-6 there, so input-derived normalisation would amplify curl-H
    # targets by orders of magnitude and make the adaptation meaningless.
    warmup = 45
    src = fdtd.source_waveform(ns + warmup, cav.dt, f_max=fmax, mode="hard")
    E, C, DD = [], [], []
    for t in range(ns + warmup):
        cav.step(src_value=float(src[t]), src_idx=(n//2, n//2, n//2), src_mode="hard")
        if t < warmup:
            continue
        curl_e = fdtd.curl_E(cav.Ex,cav.Ey,cav.Ez,cav.dx,cav.dy,cav.dz)
        curl_h = fdtd.curl_H(cav.Hx,cav.Hy,cav.Hz,cav.dx,cav.dy,cav.dz)
        for field, curl in (([cav.Ex, cav.Ey, cav.Ez], curl_e),
                            ([cav.Hx, cav.Hy, cav.Hz], curl_h)):
            x = np.stack([q[:n,:n,:n] for q in field]).astype("float32")
            y = np.zeros((3,n,n,n), dtype="float32")
            for k,q in enumerate(curl):
                sh = tuple(min(n, z) for z in q.shape)
                y[k,:sh[0],:sh[1],:sh[2]] = q[:sh[0],:sh[1],:sh[2]]
            E.append(x); C.append(y); DD.append([cav.dx*1e3]*3)
    return np.stack(E), np.stack(C), np.asarray(DD, dtype="float32")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--n",type=int,default=31); ap.add_argument("--snapshots",type=int,default=80)
    ap.add_argument("--epochs",type=int,default=30); ap.add_argument("--batch",type=int,default=8); ap.add_argument("--lr",type=float,default=3e-4)
    ap.add_argument("--init",default="dco_lr1e3_300.pt"); ap.add_argument("--out",default="dco_cavity_adapt.pt")
    a=ap.parse_args(); dev=torch.device("cuda" if torch.cuda.is_available() else "cpu"); t0=time.time()
    E,C,Dmm=collect(a.n,a.snapshots,15e9); np.savez("evidence/cavity_adapt_data.npz",E=E,C=C,D=Dmm,n=a.n)
    ck=torch.load(a.init,map_location=dev,weights_only=False); net=D.DCO(levels=ck["levels"],base=ck["base"],head=ck.get("head","direct")).to(dev); net.load_state_dict(ck["state"])
    opt=torch.optim.Adam(net.parameters(),lr=a.lr); sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,T_max=a.epochs,eta_min=a.lr*.02)
    Xt=torch.from_numpy(E).to(dev); Ct=torch.from_numpy(C).to(dev); Dt=torch.from_numpy(Dmm).to(dev); N=len(Xt); hist=[]
    for ep in range(1,a.epochs+1):
        perm=torch.randperm(N,device=dev); run=0.
        net.train()
        for i in range(0,N,a.batch):
            j=perm[i:i+a.batch]; eh,ch,_,Lc=D.normalise(Xt[j],Ct[j],Dt[j],ck.get("norm","rms"))
            q=2**(ck["levels"]-1); npad=((a.n+q-1)//q)*q; pad=npad-a.n
            if pad: eh=torch.nn.functional.pad(eh,(0,pad)*3,mode="replicate")
            coords=D.make_coords((npad,)*3,Dmm[j[0]],ck.get("coords","cellsize"),device=dev).expand(len(j),-1,-1,-1,-1)
            pred=net(eh,coords,D.d_rel_of(Dt[j],Lc))[:,:,:a.n,:a.n,:a.n]
            loss=((pred-ch).pow(2).flatten(1).mean(1)/(ch.pow(2).flatten(1).mean(1).clamp_min(1e-20))).mean(); opt.zero_grad(set_to_none=True); loss.backward(); opt.step(); run+=float(loss)*len(j)
        sched.step(); hist.append(run/N)
        if ep==1 or ep%5==0: print(f"ep {ep:3d} loss {hist[-1]:.3e}  {time.time()-t0:.1f}s")
    torch.save({"state":net.state_dict(),"levels":ck["levels"],"base":ck["base"],"coords":ck.get("coords","cellsize"),"norm":ck.get("norm","rms"),"head":ck.get("head","direct"),"epoch":a.epochs,"target":"cavity-adapt"},a.out)
    with open(a.out.replace('.pt','_hist.json'),'w') as f: json.dump({"loss":hist,"snapshots":a.snapshots},f)
    print("saved",a.out,"seconds",time.time()-t0)
if __name__=='__main__': main()
