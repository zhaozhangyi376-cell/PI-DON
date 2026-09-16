"""Raw-array and checkpoint verification for the registered C200 experiment."""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

import json
from pathlib import Path
import numpy as np
import torch
import paper_protocol as P
from paper_recheck import sha256

ROOT=Path('evidence/trunk_repair_v1')


def read():
    import verify_claims as V
    old,_,of=V.coverage_claims_data()
    j=json.loads((ROOT/'summary.json').read_text(encoding='utf-8'))
    m=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
    assert j['version']==m['version']=='trunk-repair-v1'
    assert sha256(ROOT/'manifest.json')==j['manifest_sha256']
    for name,h in m['source_hashes'].items():assert sha256(ROOT/'source'/name)==h
    assert sha256(m['initial_path'])==m['initial_sha256']
    assert sha256(m['data_path'])==m['data_sha256']==old['data_hashes']['B200']
    oldroot=Path('evidence/coverage_ab_v1')
    assert sha256(oldroot/'manifest.json')==m['old_manifest_sha256']
    assert sha256(oldroot/'summary.json')==m['old_summary_sha256']
    om=json.loads((oldroot/'manifest.json').read_text(encoding='utf-8'))
    assert m['batches']==om['batches'] and len(m['batches'])==200
    assert (m['updates'],m['batch'],m['lr'],m['trainable_prefix'])==(200,4,1e-4,'trunk.')
    assert m['diagnostic_seeds']==[10,11,12] and m['heldout_seeds']==[20,21,22]
    tr=j['training'];assert sha256(tr['path'])==tr['sha256']
    assert sha256(ROOT/'C200_hist.json')==tr['history_sha256']
    h=json.loads((ROOT/'C200_hist.json').read_text(encoding='utf-8'))
    assert [r['update'] for r in h['updates']]==list(range(1,201))
    assert all(np.isfinite(r['loss_before_update']) for r in h['updates'])
    ck=torch.load(tr['path'],map_location='cpu',weights_only=False)
    initial=torch.load(m['initial_path'],map_location='cpu',weights_only=False)['state']
    final=ck['state'];assert set(initial)==set(final)
    frozen=[n for n in initial if not n.startswith('trunk.')]
    active=[n for n in initial if n.startswith('trunk.')]
    assert all(torch.equal(initial[n],final[n]) for n in frozen)
    assert all(torch.isfinite(p).all().item() for p in final.values())
    changed=[n for n in active if not torch.equal(initial[n],final[n])]
    assert changed and h['config']['trainable_names']==active
    assert h['config']['initial_sha256']==m['initial_sha256']
    assert (h['config']['lr'],h['config']['batch'],h['config']['max_updates'])==(1e-4,4,200)
    assert h['config']['trainable_prefix']=='trunk.'
    opt=ck['optimizer_state'];ids=opt['param_groups'][0]['params']
    assert len(opt['param_groups'])==1 and opt['param_groups'][0]['lr']==1e-4
    assert len(ids)==len(active) and set(ids)==set(opt['state'])
    assert all(int(v['step'].item())==200 for v in opt['state'].values()) and ck['updates']==200
    f=dict(frozen_tensors=len(frozen),active_tensors=len(active),changed_active_tensors=len(changed),
           frozen_parameters=sum(initial[n].numel() for n in frozen),
           active_parameters=sum(initial[n].numel() for n in active),ratios=[],probe_maxima=[])
    assert f['active_parameters']==h['config']['trainable_count'] and f['frozen_parameters']==h['config']['frozen_count']
    del ck,initial,final
    tags=['A0','A200','B200','C200'];shapes=['x'.join(map(str,s)) for s in P.SHAPES]
    for sub,seeds,models in [('diagnostic',[10,11,12],['C200']),('heldout',[20,21,22],tags)]:
        block=j[sub];assert sha256(ROOT/sub/'evaluation.npz')==block['arrays_sha256']
        expected={(tag,s,shape) for tag in models for s in seeds for shape in shapes}
        assert len(block['rows'])==len(expected)
        assert {(r['model'],r['seed'],r['size']) for r in block['rows']}==expected
        for model in block['models']:
            assert sha256(model['path'])==model['sha256']==model['sha256_after_evaluation']
        with np.load(ROOT/sub/'evaluation.npz',allow_pickle=False) as z:
            for r in block['rows']:
                p=z[r['pred_key']];t=z[r['true_key']]
                assert np.isfinite(p).all() and np.isfinite(t).all()
                r['metrics']=P.vector_metrics(p,t)
            if sub=='heldout':assert not block['probe_rows']
            else:
                probes=block['probe_rows']
                expectedp={(a,p,v) for a in range(3) for p in range(3) if a!=p for v in [.3,.4,.6,.8,1.2]}
                assert len(probes)==30 and {(r['axis'],r['pol'],r['value']) for r in probes}==expectedp
                effects=[]
                for r in probes:
                    base=next(b for b in probes if (b['axis'],b['pol'],b['value'])==(r['axis'],r['pol'],.6))
                    p=z[r['pred_key']].astype(float);pb=z[base['pred_key']];t=z[r['true_key']]
                    assert np.isfinite(p).all() and np.array_equal(t,z[base['true_key']])
                    effects.append(dict(**{k:r[k] for k in ['model','axis','pol','value']},
                        relative_change=float(np.linalg.norm((p-pb).ravel())/np.linalg.norm(t.ravel()))))
                f['probe_effects']=effects
    def get(tag,s,shape):return next(r['metrics'] for r in j['heldout']['rows']
        if (r['model'],r['seed'],r['size'])==(tag,s,shape))
    for s in [20,21,22]:
        for shape in ['64x96x16','32x64x16']:
            row=dict(seed=s,size=shape)
            for numerator,denominator in [('C200','A200'),('C200','B200'),('C200','A0'),('B200','A0')]:
                a=get(numerator,s,shape);b=get(denominator,s,shape);key=numerator+'_over_'+denominator
                row[key+'_nmae']=a['macro_nmae']/b['macro_nmae']
                row[key+'_mre']=a['components']['x']['mre_eq5']/b['components']['x']['mre_eq5']
            f['ratios'].append(row)
    f['geomeans']={k:float(np.exp(np.mean(np.log([r[k] for r in f['ratios']]))))
                    for k in f['ratios'][0] if k not in ['seed','size']}
    f['cube_means']={tag:float(np.mean([get(tag,s,'32x32x32')['macro_nmae'] for s in [20,21,22]])) for tag in tags}
    f['cube_C_over_initial']=f['cube_means']['C200']/f['cube_means']['A0']
    for a in range(3):
        for p in range(3):
            if a==p:continue
            f['probe_maxima'].append(dict(model='C200',axis=a,pol=p,maximum=max(r['relative_change']
                for r in f['probe_effects'] if (r['axis'],r['pol'])==(a,p))))
    f['probe_maxima']=of['probe_maxima']+f['probe_maxima']
    f['probe_mean_maximum']={tag:float(np.mean([r['maximum'] for r in f['probe_maxima'] if r['model']==tag])) for tag in tags}
    f['probe_C_over_initial']=f['probe_mean_maximum']['C200']/f['probe_mean_maximum']['A0']
    f['diagnostic_rows']=old['rows']+j['diagnostic']['rows']
    return j,m,f


_CACHE=None
def data():
    global _CACHE
    if _CACHE is None:_CACHE=read()
    return _CACHE


def protocol(_):
    j,_,f=data();ok=j['tests_passed'] and j['test_count']>=13
    return ('PASS' if ok else 'FAIL',f"冻结{f['frozen_tensors']}个张量逐项完全相同；仅{f['active_tensors']}个trunk张量各更新200次；60组场、30组探针；13项检查",'同一B数据和batch序列；核验实际权重、优化器step、源与数组哈希；已知诊断集与新种子终验分开。')


def improvement(_):
    _,_,f=data();a=f['geomeans']['C200_over_A200_nmae'];b=f['geomeans']['C200_over_A200_mre']
    return ('PASS' if a<=.8 and b<=.8 else 'FAIL',f'新种子非立方C/A几何平均比：nMAE比值 {a:.4f}，x-MRE比值 {b:.4f}',
            '预设：种子20/21/22、六案例，两个几何平均比均≤0.8；全部逐例C/B及B/A0另报。')


def regression(_):
    _,_,f=data();v=f['cube_C_over_initial']
    return ('PASS' if v<=1.1 else 'FAIL',f'新种子32³平均nMAE的C/起点比值 {v:.4f}','预设：≤1.1，不比起点退步超过10%。')


def probe(_):
    _,_,f=data();v=f['probe_C_over_initial']
    return ('PASS' if v<=1 else 'FAIL',f'六方向最大坐标干预效应平均的C/起点比值 {v:.4f}',
            '预设：≤1；已知单波诊断集，非独立场精度或论文复现验收。')


CLAIMS=[('U0','仅trunk训练的冻结、预算和证据完整',protocol),
        ('U1','仅trunk训练在新种子非立方测试达改善门槛',improvement),
        ('U2','仅trunk训练在新种子原范围内未明显退步',regression),
        ('U3','仅trunk训练的错误坐标依赖未比起点加重',probe)]
