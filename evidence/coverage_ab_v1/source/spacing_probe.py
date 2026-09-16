"""Frozen single-axis sweep, Yee-symbol check and isolated trunk intervention.

All criteria are saved before inference. Single waves are diagnostic probes,
not samples from the paper's 20-wave test or the old 4--16-wave training set.
"""
import argparse
from pathlib import Path
import shutil
import time
import numpy as np
import torch
import dco as D
import paper_protocol as P
from diagnose_grid import sample, spec_for, roi, relmax, ANCHOR
from paper_recheck import dump,sha256

VERSION='spacing-probe-v1'
VALUES=[.2,.3,.4,.6,.8,1.,1.2]
TRANSVERSE=[.3,.4,.6,.8,1.2]
SHAPE=(32,32,32)


def yee_roi(e,h):
    # Wrapped cells are outside the scored central ROI.
    diff=lambda a,axis:(np.roll(a,-1,axis)-a)/h[axis]
    return roi(np.stack([diff(e[2],1)-diff(e[1],2),
                         diff(e[0],2)-diff(e[2],0),
                         diff(e[1],0)-diff(e[0],1)]))


def symbolic_yee(spec,h,origin):
    xyz=np.meshgrid(*[origin[k]+np.arange(32)*h[k] for k in range(3)],indexing='ij',sparse=True)
    c=np.zeros((3,*SHAPE))
    for vector,amp in zip(spec['vectors'],spec['amplitude']):
        kv=np.asarray(vector);keff=2*np.sin(kv*h/2)/h
        cross=np.cross(keff,amp);phase=sum(kv[k]*xyz[k] for k in range(3))
        for k in range(3): c[k]-=cross[k]*np.sin(phase+np.dot(kv*h,P.H_OFFSETS[k]))
    return roi(c)


def cases():
    out=[]
    for seed in [0,1,2]:
        for axis in range(3):
            for v in VALUES:
                h=[.6]*3;h[axis]=v
                out.append(dict(key=f'm{seed}_axis{axis}_{v:g}',family='multi_axis',seed=seed,
                                axis=axis,value=v,h_mm=h,spec=spec_for(seed)))
        for name,h in [('base',[.3,.3,.6]),('fine',[.3,.2,.6]),
                       ('coarse',[.3,.3,1.2]),('both',[.3,.2,1.2])]:
            out.append(dict(key=f'm{seed}_interaction_{name}',family='interaction',seed=seed,
                            variant=name,h_mm=h,spec=spec_for(seed)))
    for axis in range(3):
        for pol in [k for k in range(3) if k!=axis]:
            caxis=3-axis-pol
            for family,parameter in [('physical200',200.),('physical800',800.),('fixed_q',.18),('trunk_only',.18)]:
                for value in (TRANSVERSE if family=='trunk_only' else VALUES):
                    h=np.array([.6]*3)
                    if family=='trunk_only':
                        h[pol]=value;h[caxis]=.36/value
                    else:h[axis]=value
                    k=parameter/(h[axis]*1e-3) if family in ['fixed_q','trunk_only'] else parameter
                    vector=np.zeros(3);vector[axis]=k
                    amp=np.zeros(3);amp[pol]=1.
                    spec=dict(vectors=[vector.tolist()],amplitude=[amp.tolist()])
                    out.append(dict(key=f'p{axis}{pol}_{family}_{value:g}',family=family,
                                    axis=axis,pol=pol,active_curl=caxis,value=value,h_mm=h.tolist(),
                                    physical_k=k,q=k*h[axis]*1e-3,phase=.8,spec=spec))
    return out


def generate(case):
    h=np.array(case['h_mm'])*1e-3
    origin=ANCHOR-16*h if case['family'] in ['multi_axis','interaction'] else -16*h
    if 'phase' in case:origin[case['axis']]+=case['phase']/case['physical_k']
    e,c=sample(case['spec'],SHAPE,h,origin)
    return e,c,yee_roi(e,h),h,origin


def error(pred,true):
    p,t=np.asarray(pred,dtype=float),np.asarray(true,dtype=float)
    return float(np.linalg.norm((p-t).ravel())/np.linalg.norm(t.ravel()))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='evidence/spacing_probe_v1')
    ap.add_argument('--device',default='cuda' if torch.cuda.is_available() else 'cpu')
    a=ap.parse_args();root=Path(a.out);root.mkdir(parents=True,exist_ok=False)
    src=root/'source';src.mkdir()
    hashes={}
    for name in ['spacing_probe.py','diagnose_grid.py','paper_protocol.py','paper_recheck.py','dco.py','fdtd.py','gen_data.py','lab_log.py']:
        shutil.copy2(name,src/name);hashes[name]=sha256(name)
    cs=cases()
    manifest=dict(version=VERSION,source_hashes=hashes,cases=cs,shape=SHAPE,roi=8,
        device=a.device,torch=torch.__version__,numpy=np.__version__,
        criteria=dict(S0='all 462 predictions finite; exact Yee Fourier symbol vs differences <=1e-10; fixed-q input and scaled target identities <=1e-10; trunk-only input/target identities <=1e-10; weights unchanged',
                      S1='in all six model/seed multiwave interaction-both cases, DCO relative L2 error is >5 times exact Yee relative L2 error',
                      S2='in every model/polarization pair (12 total), at least one trunk-only transverse spacing has prediction change >1% of true curl L2, vs value=0.6 baseline'),
        notes=['single-axis multiwave sweep uses natural full-input RMS and the same 32^3 central anchor as run18',
               'trunk_only changes only coordinate channels: branch input and output rescaling are reused exactly from its own 0.6mm reference',
               'trunk_only active spacing=0.6mm; two transverse spacings have product 0.36mm^2, so analytic curl, E and geometric normalization length also remain unchanged',
               'fixed_q varies physical wave number inversely with active spacing to keep every input voxel identical; target amplitude changes as 1/h',
               'single waves and axis directions can be outside the old training distribution; these are structural probes, not paper accuracy benchmarks',
               'Yee comparison uses only interior ROI; periodic wrap is never scored; analytic curl is still the target',
               'single-wave zero components use vector relative L2 and separate leakage, not macro nMAE or paper MRE'])
    dump(root/'manifest.json',manifest)
    arrays={};checks=dict(yee_symbol=0.,fixed_q_input=0.,fixed_q_scaled_target=0.,
                         trunk_input=0.,trunk_target=0.)
    baselines={}
    for case in cs:
        if case['family'] in ['fixed_q','trunk_only'] and case['value']==.6:
            baselines[(case['family'],case['axis'],case['pol'])]=generate(case)
    for case in cs:
        e,c,y,h,origin=generate(case);key=case['key']
        checks['yee_symbol']=max(checks['yee_symbol'],relmax(y,symbolic_yee(case['spec'],h,origin)))
        arrays[key+'_E']=roi(e);arrays[key+'_true']=roi(c);arrays[key+'_yee']=y
        if case['family'] in ['fixed_q','trunk_only']:
            eb,cb,_,hb,_=baselines[(case['family'],case['axis'],case['pol'])]
            if case['family']=='fixed_q':
                checks['fixed_q_input']=max(checks['fixed_q_input'],relmax(e,eb))
                checks['fixed_q_scaled_target']=max(checks['fixed_q_scaled_target'],relmax(c*h[case['axis']],cb*hb[case['axis']]))
            else:
                checks['trunk_input']=max(checks['trunk_input'],relmax(e,eb))
                checks['trunk_target']=max(checks['trunk_target'],relmax(c,cb))
    if max(checks.values())>1e-10:raise AssertionError(checks)
    print('Pre-inference identities:',checks,flush=True)
    result=dict(version=VERSION,manifest_sha256=sha256(root/'manifest.json'),checks=checks,models=[],rows=[])
    torch.set_num_threads(4)
    if a.device=='cuda':
        torch.backends.cudnn.benchmark=False;torch.backends.cudnn.allow_tf32=False
        torch.backends.cuda.matmul.allow_tf32=False
    start=time.perf_counter()
    for path in ['dco_paper32.pt','dco_lr1e3_300.pt']:
        before=sha256(path);ck=torch.load(path,map_location='cpu',weights_only=False)
        if ck['coords']!='cellsize' or ck['norm']!='rms' or ck.get('head','direct')!='direct':
            raise ValueError('prespecified RMS/cellsize/direct checkpoint required')
        model=Path(path).stem;net=D.DCO(levels=ck['levels'],base=ck['base'])
        net.load_state_dict(ck['state']);net.to(a.device).eval();del ck
        record=dict(tag=model,path=path,sha256=before);result['models'].append(record)
        for i,case in enumerate(cs):
            e,c,y,h,_=generate(case)
            if case['family']=='trunk_only':
                # An intervention with everything except trunk input fixed.
                eb,_,_,hb,_=baselines[('trunk_only',case['axis'],case['pol'])]
                xt=torch.from_numpy(eb).float()[None].to(a.device)
                dd=torch.tensor(hb*1e3,dtype=torch.float32,device=a.device)[None]
            else:
                xt=torch.from_numpy(e).float()[None].to(a.device)
                dd=torch.tensor(h*1e3,dtype=torch.float32,device=a.device)[None]
            eh,_,scale,Lc=D.normalise(xt,None,dd,'rms')
            coords=D.make_coords(SHAPE,case['h_mm'],'cellsize',device=a.device)
            with torch.inference_mode():
                pred=D.denormalise(net(eh,coords),scale,Lc)[0].cpu().numpy()
            if not np.isfinite(pred).all():raise RuntimeError('nonfinite prediction')
            rp=roi(pred);true=roi(c);key=model+'_'+case['key'];arrays[key]=rp
            row=dict(model=model,case=case['key'],pred_key=key,
                     rel_l2=error(rp,true),yee_rel_l2=error(y,true),
                     pred_vs_yee_rel_l2=error(rp,y),scale=float(scale.item()),Lc_m=float(Lc.item()))
            if 'active_curl' in case:
                active=case['active_curl'];ta=true[active];pa=rp[active]
                row['active_gain']=float(np.sum(pa.astype(float)*ta)/np.sum(ta*ta))
                row['leakage_rel_l2']=float(np.linalg.norm(rp[[q for q in range(3) if q!=active]].ravel())/np.linalg.norm(true.ravel()))
            result['rows'].append(row)
            if (i+1)%50==0:print(model,i+1,'/',len(cs),flush=True)
        record['sha256_after']=sha256(path)
        if before!=record['sha256_after']:raise RuntimeError('weights changed')
        del net
        if a.device=='cuda':torch.cuda.empty_cache()
    result['seconds']=time.perf_counter()-start
    np.savez_compressed(root/'arrays.npz',**arrays)
    result['arrays_sha256']=sha256(root/'arrays.npz');dump(root/'summary.json',result)
    print('Saved',root,'cases=',len(cs),'predictions=',len(result['rows']),'No training.')


if __name__=='__main__':main()
