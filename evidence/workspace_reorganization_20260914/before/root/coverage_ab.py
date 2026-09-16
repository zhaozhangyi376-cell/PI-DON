"""Approved paired coverage experiment: exactly 200 Adam updates per arm.

The only arm factor is the mapping of shared U[0,1] spacing draws to ranges.
No scheduler, model selection, adaptive budget or validation-driven retraining.
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
import spacing_probe as S
from diagnose_grid import sample,roi
from paper_recheck import dump,sha256

VERSION='coverage-ab-v1'
SEED=20260915
RANGES={'A200':(.3,.8),'B200':(.2,1.2)}
PLAN=Path('evidence/spacing_probe_v1/NEXT_AB_PLAN.md')


def paired_specs(n=128,seed=SEED):
    rng=np.random.default_rng(seed);out=[]
    for i in range(n):
        u=rng.uniform(0,1,3)
        nw=int(rng.integers(4,17));ks=rng.uniform(1,G.K_MAX,nw)
        kh=G._draw_khat(rng);amp=np.empty((nw,3))
        amp[:,0]=rng.uniform(0,G.AMP_MAX,nw);amp[:,1]=rng.uniform(0,G.AMP_MAX,nw)
        amp[:,2]=-(kh[0]*amp[:,0]+kh[1]*amp[:,1])/kh[2]
        out.append(dict(index=i,u=u.tolist(),vectors=(ks[:,None]*kh).tolist(),
                        amplitude=amp.tolist(),direction=kh.tolist(),wave_numbers=ks.tolist()))
    return out


def make_data(specs,arm,n=32):
    lo,hi=RANGES[arm];es=[];cs=[];ds=[]
    for spec in specs:
        h=(lo+(hi-lo)*np.asarray(spec['u']))*1e-3
        e,c=sample(spec,(n,n,n),h,[0,0,0])
        es.append(e.astype(np.float32));cs.append(c.astype(np.float32));ds.append(h.astype(np.float32))
    return dict(E=np.stack(es),C=np.stack(cs),D=np.stack(ds))


def batch_schedule():
    rng=np.random.default_rng(SEED);batches=[]
    while len(batches)<200:batches.extend(rng.permutation(128).reshape(-1,4).tolist())
    return batches[:200]


def criterion(pred,true):
    return ((pred-true).square().flatten(1).mean(1)/true.square().flatten(1).mean(1).clamp_min(1e-20)).mean()


def load_net(path,device):
    ck=torch.load(path,map_location='cpu',weights_only=False)
    if (ck['norm'],ck['coords'],ck.get('head','direct'))!=('rms','cellsize','direct'):
        raise ValueError('approved checkpoint interface mismatch')
    net=D.DCO(levels=ck['levels'],base=ck['base']);net.load_state_dict(ck['state']);net.to(device)
    meta={k:ck[k] for k in ['levels','base','grid','norm','coords']}
    return net,meta


def train_arm(arm,data,initial,batches,root,device,trainable_prefix=None):
    torch.manual_seed(SEED)
    net,meta=load_net(initial,device);net.train()
    if trainable_prefix is not None:
        for name,p in net.named_parameters():p.requires_grad_(name.startswith(trainable_prefix))
    active=[p for p in net.parameters() if p.requires_grad]
    frozen={n:p.detach().cpu().clone() for n,p in net.named_parameters() if not p.requires_grad}
    opt=torch.optim.Adam(active,lr=1e-4)
    e=torch.from_numpy(data['E']);c=torch.from_numpy(data['C']);dd=torch.from_numpy(data['D'])*1e3
    hist=dict(arm=arm,updates=[],config=dict(lr=1e-4,batch=4,max_updates=200,loss='per-sample relative MSE',
                                          spacing_mm=RANGES.get(arm,RANGES['B200']),initial_sha256=sha256(initial),
                                          trainable_prefix=trainable_prefix,
                                          trainable_names=[n for n,p in net.named_parameters() if p.requires_grad],
                                          trainable_count=sum(p.numel() for p in active),
                                          frozen_count=sum(p.numel() for p in frozen.values())))
    start=time.perf_counter()
    for step,indices in enumerate(batches,1):
        x=e[indices].to(device);y=c[indices].to(device);d=dd[indices].to(device)
        coords=d[:,:,None,None,None].expand(-1,-1,32,32,32).contiguous()
        eh,ch,_,_=D.normalise(x,y,d,'rms')
        loss=criterion(net(eh,coords),ch)
        if not torch.isfinite(loss).item():raise RuntimeError(f'{arm} nonfinite loss at {step}')
        opt.zero_grad(set_to_none=True);loss.backward()
        if not all(p.grad is None or torch.isfinite(p.grad).all().item() for p in net.parameters()):
            raise RuntimeError(f'{arm} nonfinite gradient at {step}')
        opt.step()
        hist['updates'].append(dict(update=step,loss_before_update=float(loss.item()),seconds=time.perf_counter()-start))
        if step%10==0:
            dump(root/(arm+'_hist.json'),hist)
            avg=np.mean([r['loss_before_update'] for r in hist['updates'][-10:]])
            print(f'{arm} update {step}/200: last10 training loss={avg:.6g}, {time.perf_counter()-start:.1f}s',flush=True)
    if not all(torch.isfinite(p).all().item() for p in net.parameters()):raise RuntimeError('nonfinite final parameters')
    steps=[int(v['step'].item()) for v in opt.state.values()]
    if len(batches)!=200 or len(steps)!=len(active) or min(steps)!=200 or max(steps)!=200:raise AssertionError('update budget mismatch')
    if any(not torch.equal(p.detach().cpu(),frozen[n]) for n,p in net.named_parameters() if n in frozen):
        raise AssertionError('frozen parameter changed')
    path=root/(arm+'.pt')
    torch.save(dict(state=net.state_dict(),**meta,head='direct',target='analytic',updates=200,
                    source_epoch=300,hist=hist,optimizer_state=opt.state_dict()),path)
    hist['seconds']=time.perf_counter()-start;dump(root/(arm+'_hist.json'),hist)
    record=dict(tag=arm,path=str(path),sha256=sha256(path),updates=200,seconds=hist['seconds'],
                optimizer_step_min=min(steps),optimizer_step_max=max(steps),
                history_sha256=sha256(root/(arm+'_hist.json')))
    del net,opt
    if device=='cuda':torch.cuda.empty_cache()
    return record


def evaluate(models,root,device,seeds=(10,11,12),include_probes=True):
    arrays={};rows=[];probe_rows=[];test_specs=[P.wave_spec(s) for s in seeds]
    tests=[]
    for spec in test_specs:
        for shape in P.SHAPES:
            e,c,h=P.sample_wave(spec,shape);size='x'.join(map(str,shape));key=f's{spec["seed"]}_{size}'
            arrays[key+'_E']=e;arrays[key+'_true']=c
            tests.append((spec['seed'],size,key,e,c,h))
    probes=[case for case in S.cases() if case['family']=='trunk_only'] if include_probes else []
    bases={(case['axis'],case['pol']):S.generate(case) for case in probes if case['value']==.6}
    for model in models:
        before=sha256(model['path']);net,_=load_net(model['path'],device);net.eval()
        for seed,size,key,e,c,h in tests:
            x=torch.from_numpy(e).float()[None].to(device)
            d=torch.tensor(h*1e3,dtype=torch.float32,device=device)[None]
            coords=D.make_coords(e.shape[1:],(h*1e3).tolist(),'cellsize',device=device)
            with torch.inference_mode():
                eh,_,a,Lc=D.normalise(x,None,d,'rms');p=D.denormalise(net(eh,coords),a,Lc)[0].cpu().numpy()
            if not np.isfinite(p).all():raise RuntimeError('nonfinite evaluation')
            pk=model['tag']+'_'+key;arrays[pk]=p
            rows.append(dict(model=model['tag'],seed=seed,size=size,pred_key=pk,true_key=key+'_true',metrics=P.vector_metrics(p,c)))
        for case in probes:
            e,c,_,h,_=bases[(case['axis'],case['pol'])]
            x=torch.from_numpy(e).float()[None].to(device)
            d=torch.tensor(h*1e3,dtype=torch.float32,device=device)[None]
            coords=D.make_coords(S.SHAPE,case['h_mm'],'cellsize',device=device)
            with torch.inference_mode():
                eh,_,a,Lc=D.normalise(x,None,d,'rms');p=D.denormalise(net(eh,coords),a,Lc)[0].cpu().numpy()
            if not np.isfinite(p).all():raise RuntimeError('nonfinite probe')
            pk=model['tag']+'_'+case['key'];tk=case['key']+'_true'
            arrays[pk]=roi(p);arrays[tk]=roi(c)
            probe_rows.append(dict(model=model['tag'],axis=case['axis'],pol=case['pol'],value=case['value'],pred_key=pk,true_key=tk))
        model['sha256_after_evaluation']=sha256(model['path'])
        if before!=model['sha256_after_evaluation']:raise RuntimeError('evaluation changed weights')
        print('Evaluated',model['tag'],len(tests),'cases; seeds',list(seeds),'and',len(probes),'coordinate probes',flush=True)
        del net
        if device=='cuda':torch.cuda.empty_cache()
    np.savez_compressed(root/'evaluation.npz',**arrays)
    return dict(models=models,rows=rows,probe_rows=probe_rows,test_specs=test_specs,
                arrays_sha256=sha256(root/'evaluation.npz'))


def run(args):
    root=Path(args.out);root.mkdir(parents=True,exist_ok=False);source=root/'source';source.mkdir()
    files=['coverage_ab.py','test_coverage_ab.py','test_paper_protocol.py','dco.py','gen_data.py',
           'diagnose_grid.py','paper_protocol.py','paper_recheck.py','spacing_probe.py','fdtd.py','lab_log.py']
    hashes={}
    for name in files:shutil.copy2(name,source/name);hashes[name]=sha256(name)
    shutil.copy2(PLAN,source/'NEXT_AB_PLAN.md');hashes['NEXT_AB_PLAN.md']=sha256(PLAN)
    initial='dco_lr1e3_300.pt';initial_hash=sha256(initial)
    old=json.loads(Path('evidence/spacing_probe_v1/summary.json').read_text(encoding='utf-8'))
    expected=next(v['sha256'] for v in old['models'] if v['tag']=='dco_lr1e3_300')
    if initial_hash!=expected:raise ValueError('approved initial checkpoint changed')
    specs=paired_specs();batches=batch_schedule()
    manifest=dict(version=VERSION,source_hashes=hashes,approved_plan_sha256=sha256(PLAN),
        initial_path=initial,initial_sha256=initial_hash,seed=SEED,wave_specs=specs,batches=batches,
        ranges_mm=RANGES,updates_per_arm=200,batch=4,lr=1e-4,optimizer='Adam default parameters; fresh state per arm',
        scheduler=None,loss='per-sample relative MSE; denominator clamped 1e-20',norm='rms',coords='cellsize',
        test_seeds=[10,11,12],device=args.device,torch=torch.__version__,numpy=np.__version__,
        criteria=dict(T0='same initial checkpoint, paired wave/u draws, identical 200x4 batch schedule and optimizer settings; full finite evaluation, weight hashes unchanged during evaluation',
                      T1='over six noncubic held-out cases: geometric means of B200/A200 macro nMAE ratios AND x Eq5 MRE ratios <=0.8',
                      T2='mean macro nMAE on three 32^3 held-out cases: B200/A0 <=1.1',
                      T3='mean over six axis/polarization maxima of transverse trunk intervention: B200/A0 <=1.0'),
        limitations=['only one paired optimization seed, not an estimate of training variability',
                     '200-update pilot, not a fully converged training comparison',
                     'expanded range is a diagnostic enhancement, not the paper original training setting',
                     'validation seed 10/11/12 cases are evaluated only after both arms finish; no checkpoint selection'])
    dump(root/'manifest.json',manifest)
    stream=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromNames(['test_paper_protocol','test_coverage_ab'])
    res=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (root/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
    if not res.wasSuccessful():raise RuntimeError(stream.getvalue())
    torch.manual_seed(SEED);torch.set_num_threads(4)
    if args.device=='cuda':
        torch.backends.cudnn.benchmark=False;torch.backends.cudnn.allow_tf32=False
        torch.backends.cuda.matmul.allow_tf32=False
    datasets={};data_hashes={}
    for arm in RANGES:
        datasets[arm]=make_data(specs,arm)
        np.savez_compressed(root/('train_'+arm+'.npz'),**datasets[arm])
        data_hashes[arm]=sha256(root/('train_'+arm+'.npz'))
    uA=(datasets['A200']['D']*1e3-.3)/.5;uB=datasets['B200']['D']*1e3-.2
    pairing=float(np.max(np.abs(uA-uB)))
    if pairing>1e-6:raise AssertionError('unpaired spacing draws')
    print('Data pairs checked; beginning exactly 200 updates per arm.',flush=True)
    summary=dict(version=VERSION,manifest_sha256=sha256(root/'manifest.json'),data_hashes=data_hashes,
                 pairing_max_abs=pairing,tests_passed=True,test_count=res.testsRun,training=[])
    for arm in RANGES:
        record=train_arm(arm,datasets[arm],initial,batches,root,args.device)
        summary['training'].append(record);dump(root/'training_summary.json',summary)
    del datasets
    models=[dict(tag='A0',path=initial,sha256=initial_hash)]+[dict(v) for v in summary['training']]
    summary.update(evaluate(models,root,args.device))
    summary['initial_sha256_after']=sha256(initial)
    if summary['initial_sha256_after']!=initial_hash:raise RuntimeError('original weights changed')
    dump(root/'summary.json',summary)
    print('Saved',root,'400 total updates, no additional training.')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='evidence/coverage_ab_v1')
    ap.add_argument('--device',default='cuda' if torch.cuda.is_available() else 'cpu');a=ap.parse_args()
    try:run(a)
    except Exception as exc:
        root=Path(a.out)
        if root.exists() and not (root/'summary.json').exists():
            dump(root/'failure.json',dict(error_type=type(exc).__name__,error=str(exc)))
        raise
