"""Factorial frozen-weight diagnosis; not a paper replication or training run.

Shape, spacing and input normalization extent are separate experimental factors.
Only the same physical central 8^3 Yee samples are scored across shapes.
"""
import argparse
import copy
import io
import json
from pathlib import Path
import shutil
import time
import unittest

import numpy as np
import torch
import dco as D
import gen_data as G
import paper_protocol as P
from paper_recheck import sha256, dump

VERSION = 'grid-diagnosis-v1'
SPACINGS = {'iso06': [.6,.6,.6], 'iso03': [.3,.3,.3],
            'aniso_A': [.3,.2,1.2], 'aniso_B': [.6,.3,1.2]}
ANCHOR = np.array([.0096]*3)
ROI = 8


def sample(spec, shape, h, origin):
    h=np.asarray(h); shape=tuple(shape); origin=np.asarray(origin)
    xyz=np.meshgrid(*[origin[k]+np.arange(n)*h[k] for k,n in enumerate(shape)],
                    indexing='ij',sparse=True)
    e,c=np.zeros((3,*shape)),np.zeros((3,*shape))
    for kv,amp in zip(spec['vectors'],spec['amplitude']):
        kv,amp=np.asarray(kv),np.asarray(amp)
        phase=sum(kv[k]*xyz[k] for k in range(3))
        cross=np.cross(kv,amp)
        for k in range(3):
            e[k]+=amp[k]*np.cos(phase+np.dot(kv*h,P.E_OFFSETS[k]))
            c[k]-=cross[k]*np.sin(phase+np.dot(kv*h,P.H_OFFSETS[k]))
    return e,c


def spec_for(seed):
    s=P.wave_spec(seed)
    return dict(s,vectors=(np.asarray(s['k'])[:,None]*np.asarray(s['direction'])).tolist())


def roi(a):
    return a[(slice(None),)+tuple(slice(n//2-ROI//2,n//2+ROI//2) for n in a.shape[1:])].copy()


def relmax(a,b):
    return float(np.max(np.abs(a-b))/max(float(np.max(np.abs(b))),1e-30))


def validation():
    checks={}
    spec=spec_for(0)
    for shape in P.SHAPES:
        e,c,h=P.sample_wave(P.wave_spec(0),shape)
        e2,c2=sample(spec,shape,h,np.zeros(3))
        checks['paper_sampler_'+str(shape)]=max(relmax(e2,e),relmax(c2,c))
    # Replay the existing generator's exact random draw order. Independent
    # coordinate construction then checks that train and evaluation align.
    rng=np.random.default_rng(43)
    nw=int(rng.integers(4,17)); ks=rng.uniform(1,G.K_MAX,nw)
    kh=np.repeat(G._draw_khat(rng)[None],nw,axis=0)
    amps=np.empty((nw,3)); amps[:,0]=rng.uniform(0,G.AMP_MAX,nw)
    amps[:,1]=rng.uniform(0,G.AMP_MAX,nw)
    amps[:,2]=-(kh[:,0]*amps[:,0]+kh[:,1]*amps[:,1])/kh[:,2]
    h=np.array([.00031,.00057,.00079])
    eg,cg=G.one_sample(np.random.default_rng(43),(16,24,32),h)
    er,cr=sample(dict(vectors=ks[:,None]*kh,amplitude=amps),(16,24,32),h,[0,0,0])
    checks['training_sampler']=max(relmax(er,eg),relmax(cr,cg))
    for norm in ['max','rms']:
        x=torch.from_numpy(eg).float()[None]; y=torch.from_numpy(cg).float()[None]
        dd=torch.tensor(h*1e3).float()[None]
        eh,ch,a,Lc=D.normalise(x,y,dd,norm)
        checks['roundtrip_'+norm]=relmax(D.denormalise(ch,a,Lc).numpy(),y.numpy())
        checks['drel_'+norm]=relmax(D.d_rel_of(dd,Lc).numpy(),(h/np.cbrt(np.prod(h)))[None])
    coords=D.make_coords((16,24,32),(h*1e3).tolist(),'cellsize').numpy()
    checks['coordinate_units']=relmax(coords,np.broadcast_to((h*1e3).reshape(1,3,1,1,1),coords.shape))
    for name,value in checks.items():
        bound=2e-6 if name.startswith(('roundtrip','drel','coordinate')) else 1e-10
        if value>bound: raise AssertionError(f'{name}: {value}>{bound}')
    return checks


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',default='evidence/grid_diagnosis_v1')
    ap.add_argument('--device',default='cuda' if torch.cuda.is_available() else 'cpu')
    args=ap.parse_args(); out=Path(args.out); out.mkdir(parents=True,exist_ok=False)
    source=out/'source'; source.mkdir()
    files=['diagnose_grid.py','paper_protocol.py','paper_recheck.py','gen_data.py',
           'dco.py','test_paper_protocol.py','fdtd.py','lab_log.py']
    hashes={}
    for name in files:
        shutil.copy2(name,source/name); hashes[name]=sha256(name)
    specs=[spec_for(s) for s in [0,1,2]]
    manifest=dict(version=VERSION,source_hashes=hashes,device=args.device,
                  torch=torch.__version__,numpy=np.__version__,wave_specs=specs,
                  shapes=P.SHAPES,spacings_mm=SPACINGS,anchor_m=ANCHOR.tolist(),roi=ROI,
                  scales=['natural: RMS over current full input',
                          'fixed32: RMS over the centered 32^3 input, reused across shapes'],
                  criteria=dict(D0='sampler/ROI match <=1e-10; normalization and units <=2e-6; nine existing tests pass; 192 predictions finite and weights unchanged',
                                D1='both Fig6 noncubic spacings contain coordinates outside generator interval [0.3,0.8] mm; separately inspect available dataset',
                                D2='at iso06 fixed32 scale: in each of six model/seed pairs at least one noncubic shape differs from 32^3 prediction by relative L2 >1e-3 on the exact common ROI',
                                D3='at 32^3 natural scale: in each of six model/seed pairs at least one anisotropic spacing has macro nMAE >2 times iso06'),
                  limitations=['diagnostic centered windows, not the original Fig6 test',
                               'same spacing comparison fixes input/target ROI, physical position, normalization and pooling alignment; outside ROI context and boundary distance change',
                               'spacing comparison also changes physical sample locations and spatial frequency per cell; it cannot isolate trunk encoding from branch response',
                               'fixed32 is a diagnostic intervention; natural preserves the checkpoint input normalization',
                               'seed range is amplitude sensitivity, not confidence intervals or independent training runs'])
    dump(out/'manifest.json',manifest)  # Criteria fixed before numerical work.
    checks=validation()
    stream=io.StringIO()
    suite=unittest.defaultTestLoader.loadTestsFromName('test_paper_protocol')
    res=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (out/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
    if not res.wasSuccessful(): raise RuntimeError(stream.getvalue())
    result=dict(version=VERSION,checks=checks,tests_passed=True,test_count=res.testsRun,
                manifest_sha256=sha256(out/'manifest.json'),models=[],rows=[],datasets=[])
    arrays={}
    data_path=Path('data_32.npz')
    if data_path.exists():
        with np.load(data_path,allow_pickle=False) as z:
            dd=z['D'].astype(float)*1e3
            arrays['available_data32_spacing_mm']=dd
            result['datasets'].append(dict(path=str(data_path),sha256=sha256(data_path),
                                           n=int(z['n']),samples=len(dd),
                                           dirs=str(z['dirs']) if 'dirs' in z else None,
                                           min_mm=dd.min(axis=0).tolist(),max_mm=dd.max(axis=0).tolist(),
                                           identity_note='available local dataset; only checkpoint config/log can associate it to a training run'))
    torch.set_num_threads(4)
    if args.device=='cuda':
        torch.backends.cudnn.benchmark=False
        torch.backends.cudnn.allow_tf32=False
        torch.backends.cuda.matmul.allow_tf32=False
    start=time.perf_counter()
    for path in ['dco_paper32.pt','dco_lr1e3_300.pt']:
        before=sha256(path);ck=torch.load(path,map_location='cpu',weights_only=False)
        model=Path(path).stem
        meta={k:ck.get(k) for k in ['levels','base','epoch','coords','norm','grid','head','target']}
        config=ck.get('hist',{}).get('config',{})
        if meta['norm']!='rms' or meta['coords']!='cellsize':
            raise ValueError('This experiment prespecifies RMS/cellsize checkpoints')
        net=D.DCO(levels=ck['levels'],base=ck['base'],head=ck.get('head','direct'))
        net.load_state_dict(ck['state']);net.to(args.device).eval();del ck
        model_record=dict(tag=model,sha256=before,metadata=meta,training_config=config)
        result['models'].append(model_record)
        for spec in specs:
            seed=spec['seed']
            for spacing,hmm in SPACINGS.items():
                h=np.array(hmm)*1e-3
                refE,refC=sample(spec,(32,32,32),h,ANCHOR-16*h)
                commonE,commonC=roi(refE),roi(refC)
                key=f's{seed}_{spacing}'
                arrays[key+'_E'],arrays[key+'_true']=commonE,commonC
                refx=torch.from_numpy(refE).float()[None].to(args.device)
                dd=torch.tensor(hmm,dtype=torch.float32,device=args.device)[None]
                _,_,fixed_a,Lc=D.normalise(refx,None,dd,'rms');del refx
                for shape in P.SHAPES:
                    size='x'.join(map(str,shape))
                    e,c=sample(spec,shape,h,ANCHOR-np.array(shape)//2*h)
                    align=max(relmax(roi(e),commonE),relmax(roi(c),commonC))
                    if align>1e-10: raise AssertionError('ROI mismatch '+str(align))
                    x=torch.from_numpy(e).float()[None].to(args.device)
                    coords=D.make_coords(shape,hmm,'cellsize',device=args.device)
                    eh,_,natural_a,Lc=D.normalise(x,None,dd,'rms')
                    for scale,a in [('natural',natural_a),('fixed32',fixed_a)]:
                        with torch.inference_mode():
                            p=D.denormalise(net(x/a,coords,D.d_rel_of(dd,Lc)),a,Lc)[0].cpu().numpy()
                        if not np.isfinite(p).all(): raise RuntimeError('nonfinite output')
                        rp=roi(p);pk=f'{model}_{key}_{size}_{scale}'
                        arrays[pk]=rp
                        met=P.vector_metrics(rp,commonC)
                        result['rows'].append(dict(model=model,seed=seed,spacing=spacing,
                                                   size=size,scale=scale,pred_key=pk,true_key=key+'_true',
                                                   rms_scale=float(a.item()),
                                                   natural_over_fixed=float((natural_a/fixed_a).item()),
                                                   roi_alignment=align,metrics=met))
                    del x,coords,eh,p
                print(f'{model} seed={seed} spacing={spacing}: 8 forward passes complete',flush=True)
        model_record['sha256_after']=sha256(path)
        if before!=model_record['sha256_after']: raise RuntimeError('weights changed')
        del net
        if args.device=='cuda': torch.cuda.empty_cache()
    result['seconds']=time.perf_counter()-start
    np.savez_compressed(out/'arrays.npz',**arrays)
    result['arrays_sha256']=sha256(out/'arrays.npz')
    dump(out/'summary.json',result)
    print('Saved',out,'192 frozen forward passes. No optimizer, no training.')


if __name__=='__main__': main()
