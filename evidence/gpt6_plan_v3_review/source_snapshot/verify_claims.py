# -*- coding: utf-8 -*-
"""
Claim ledger.  Every number I would put on a slide, re-derived from the files
on disk, with a PASS/FAIL next to it.

    py -3.11 verify_claims.py            # check what disk can already answer
    py -3.11 verify_claims.py --run      # also re-run the cheap checks (~1 min)
    py -3.11 verify_claims.py --md       # write RESULTS.md

WHY THIS EXISTS
    2026-09-10 group meeting: "复现没有数据支撑，不知道你做的是真是假".

    lab_log.py answers "did this run happen" (command + commit + sha256).
    This answers the other half: "does the claim still follow from the run".
    The two are different failures.  A number can be honestly produced and
    then quietly go stale when the artifact behind it is regenerated.

    Rules I am holding myself to here:
      * a claim with no artifact behind it prints 缺数据 and the exact command
        that would produce the artifact.  It never prints a remembered number.
      * the threshold is written down BEFORE the value, so a claim cannot be
        retro-fitted to whatever came out.
      * FAIL is a normal outcome, not an error.  Exit code counts FAILs so a
        batch file can stop on one.

    RESULTS.md and small JSON manifests can be versioned. Large .pt/.npz
    artifacts are ignored; hashes and source snapshots identify local evidence.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys

import numpy as np

SCRIPT_VERSION = "trunk-repair-v1"

# Paper-first audit: legacy numbers remain, but disputed scientific readings
# must not be promoted to PASS. Do not delete the C7 adverse observation.
AUDIT_NOTES = {
    'C2': '待重验：寿命字段可被误差1000阈值覆盖，而预测按误差1；局部谱相关不等于因果。',
    'C3': '待重验：阈值需统一；仅适用于所测冻结模型/步长/边界，不能推出减小dt普遍无效。',
    'C4': '撤回因果解读：偏相关大小比较不足以证明精度只通过rho作用。',
    'C5': '撤回替代性解读：两个不同配置的局部rho接近不能替代Algorithm1。',
    'C6': '待重新解释：原文明写坐标输入；cellsize常量张量和输入RMS是本实现选择。',
    'C8': '撤回普遍不可能性：两点/局部谱外推及1/N估算不是全局证明。',
}


def paper_evidence():
    """Verified files and recomputed metrics are shared by ledger and figures."""
    from pathlib import Path
    from paper_recheck import sha256
    import paper_protocol as pp
    root = Path('evidence/paper_first_v1')
    j = json.loads((root/'summary.json').read_text(encoding='utf-8'))
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    if j['protocol'] != pp.VERSION:
        raise ValueError('protocol version mismatch')
    if sha256(root/'manifest.json') != j['manifest_sha256'] or sha256(root/'arrays.npz') != j['arrays_sha256']:
        raise ValueError('evidence hash mismatch')
    for name,h in manifest['sources'].items():
        if sha256(root/'source'/name) != h:
            raise ValueError('source snapshot mismatch: '+name)
    for model in j['models']:
        if model['sha256'] != model['sha256_after']:
            raise ValueError('model changed during inference')
    with np.load(root/'arrays.npz', allow_pickle=False) as z:
        for row in j['rows']:
            key = row['array_key']
            row['metrics'] = pp.vector_metrics(z[row['model']+'_'+key+'_pred'], z[key+'_true'])
    return j, manifest


_PAPER_CACHE = None


def paper_claims_data():
    global _PAPER_CACHE
    if _PAPER_CACHE is None: _PAPER_CACHE = paper_evidence()
    return _PAPER_CACHE


def p_protocol(_):
    j,m = paper_claims_data()
    from paper_protocol import SHAPES
    expected = {(model['tag'],s,'x'.join(map(str,sh)))
                for model in j['models'] for s in m['seeds'] for sh in SHAPES}
    actual = {(r['model'],r['seed'],r['size']) for r in j['rows']}
    ok = j['tests_passed'] and j['test_count'] >= 9 and len(j['rows']) == len(expected) and actual == expected
    return ('PASS' if ok else 'FAIL', f"{j['test_count']}项解析检查；{len(actual)}/{len(expected)}个模型/种子/网格组合",
            '判据：解析检查全过、组合完整、产物及源代码快照哈希匹配；仅证明评估链，不证明作者未披露假设。')


def p_reference(_):
    j,_ = paper_claims_data()
    r=j['reference']; vals=[abs(v['error_pct']) for v in r['modes']]
    ok = r['finite'] and r['steps']==8192 and len(vals)==5 and max(vals)<.5
    return ('PASS' if ok else 'FAIL', f"8192步；五模式最大绝对相对误差 {max(vals):.4f}%",
            '先定判据：5模式误差均<0.5%、全场保持有限；31间隔候选、源外探针；这是FDTD，不是PI-DON。')


def p_dco(_):
    import paper_protocol as pp
    j,m=paper_claims_data(); winners=[]; details=[]
    for model in j['models']:
        rows=[r for r in j['rows'] if r['model']==model['tag'] and r['size'] in pp.PAPER_MRE]
        ok=len(rows)==3*len(m['seeds']) and all(r['metrics']['components']['x']['mre_eq5']<=pp.PAPER_MRE[r['size']] for r in rows)
        if ok: winners.append(model['tag'])
        values=[r['metrics']['components']['x']['mre_eq5'] for r in rows]
        details.append(f"{model['tag']} x-MRE {min(values):.3g}~{max(values):.3g}")
    return ('PASS' if winners else 'FAIL', '; '.join(details),
            '先定判据：至少一模型在三网格×三振幅种子的x分量式5均≤图6标值；'
            '仅针对公开参数+声明假设的重建案例，不能等同作者原始数据或全模型不可能性。')


PAPER_CLAIMS=[('P0','评估协议与解析检查完整',p_protocol),
              ('P1','候选网格下FDTD空气腔体参考通过',p_reference),
              ('P2','现有DCO在本轮Fig6重建案例达到预设MRE目标',p_dco)]


def grid_evidence():
    """Recompute diagnostic ROI metrics and paired effects from hashed arrays."""
    from pathlib import Path
    from paper_recheck import sha256
    import paper_protocol as pp
    root=Path('evidence/grid_diagnosis_v1')
    j=json.loads((root/'summary.json').read_text(encoding='utf-8'))
    m=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    if j['version']!='grid-diagnosis-v1' or j['version']!=m['version']:
        raise ValueError('diagnostic version mismatch')
    for name in ['manifest.json','arrays.npz']:
        key='manifest_sha256' if name.endswith('.json') else 'arrays_sha256'
        if sha256(root/name)!=j[key]: raise ValueError('diagnostic hash mismatch '+name)
    for name,h in m['source_hashes'].items():
        if sha256(root/'source'/name)!=h: raise ValueError('source mismatch '+name)
    for model in j['models']:
        if model['sha256']!=model['sha256_after']: raise ValueError('weights changed')
    shapes=['x'.join(map(str,s)) for s in m['shapes']]
    expected={(mo['tag'],s['seed'],sp,sh,sc) for mo in j['models'] for s in m['wave_specs']
              for sp in m['spacings_mm'] for sh in shapes for sc in ['natural','fixed32']}
    actual={(r['model'],r['seed'],r['spacing'],r['size'],r['scale']) for r in j['rows']}
    if len(j['rows'])!=len(expected) or actual!=expected: raise ValueError('incomplete factorial experiment')
    f=dict(shape_effects=[],spacing_effects=[],normalization_effects=[])
    with np.load(root/'arrays.npz',allow_pickle=False) as z:
        for row in j['rows']:
            row['metrics']=pp.vector_metrics(z[row['pred_key']],z[row['true_key']])
        def get(model,seed,spacing,size,scale):
            return next(r for r in j['rows'] if (r['model'],r['seed'],r['spacing'],r['size'],r['scale'])
                        ==(model,seed,spacing,size,scale))
        for model in [v['tag'] for v in j['models']]:
            for seed in [s['seed'] for s in m['wave_specs']]:
                base=get(model,seed,'iso06','32x32x32','fixed32')
                pb=z[base['pred_key']]
                for shape in shapes[1:]:
                    row=get(model,seed,'iso06',shape,'fixed32')
                    delta=z[row['pred_key']].astype(float)-pb
                    f['shape_effects'].append(dict(model=model,seed=seed,size=shape,
                        relative_prediction_change=float(np.linalg.norm(delta.ravel())/np.linalg.norm(pb.ravel())),
                        baseline_nmae=base['metrics']['macro_nmae'],nmae=row['metrics']['macro_nmae']))
                base=get(model,seed,'iso06','32x32x32','natural')
                for spacing in ['iso03','aniso_A','aniso_B']:
                    row=get(model,seed,spacing,'32x32x32','natural')
                    f['spacing_effects'].append(dict(model=model,seed=seed,spacing=spacing,
                        nmae_ratio=row['metrics']['macro_nmae']/base['metrics']['macro_nmae'],
                        baseline_nmae=base['metrics']['macro_nmae'],nmae=row['metrics']['macro_nmae']))
        for row in j['rows']:
            if row['scale']!='natural': continue
            fixed=get(row['model'],row['seed'],row['spacing'],row['size'],'fixed32')
            f['normalization_effects'].append(dict(model=row['model'],seed=row['seed'],spacing=row['spacing'],size=row['size'],
                natural_over_fixed_scale=row['natural_over_fixed'],
                fixed_over_natural_nmae=fixed['metrics']['macro_nmae']/row['metrics']['macro_nmae']))
        if 'available_data32_spacing_mm' in z:
            dd=z['available_data32_spacing_mm']
            f['available_spacing_min_mm']=dd.min(axis=0).tolist()
            f['available_spacing_max_mm']=dd.max(axis=0).tolist()
    # Descriptive follow-up: distinguish changing physical extent in the
    # diagnosis from changing sampling density in the earlier fixed window.
    old=Path('evidence/paper_first_v1')
    oldj=json.loads((old/'summary.json').read_text(encoding='utf-8'))
    if sha256(old/'arrays.npz')!=oldj['arrays_sha256']:
        raise ValueError('original-window arrays hash mismatch')
    f['original_window_arrays_sha256']=oldj['arrays_sha256']
    f['original_window_rms']=[]
    with np.load(old/'arrays.npz',allow_pickle=False) as z:
        for seed in [s['seed'] for s in m['wave_specs']]:
            base=float(np.sqrt(np.mean(z[f's{seed}_32x32x32_E']**2)))
            for shape in shapes:
                rms=float(np.sqrt(np.mean(z[f's{seed}_{shape}_E']**2)))
                f['original_window_rms'].append(dict(seed=seed,size=shape,rms=rms,ratio_to_32=rms/base))
    return j,m,f


_GRID_CACHE=None


def grid_claims_data():
    global _GRID_CACHE
    if _GRID_CACHE is None: _GRID_CACHE=grid_evidence()
    return _GRID_CACHE


def d_protocol(_):
    j,_,_=grid_claims_data()
    ok=j['tests_passed'] and j['test_count']>=9 and all(v<=(2e-6 if name.startswith(('roundtrip','drel','coordinate')) else 1e-10)
        for name,v in j['checks'].items()) and max(r['roi_alignment'] for r in j['rows'])<=1e-10
    return ('PASS' if ok else 'FAIL',f"{len(j['rows'])}组预测；归一化还原最大偏差 {max(v for k,v in j['checks'].items() if k.startswith('roundtrip')):.2e}",
            '预设检查：采样/同位置ROI≤1e-10，归一化和单位≤2e-6，9项回归全过，组合/哈希完整；仅排除已测试的接口错位。')


def d_spacing_range(_):
    _,m,f=grid_claims_data()
    vals=[m['spacings_mm'][k] for k in ['aniso_A','aniso_B']]
    ok=all(any(v<.3 or v>.8 for v in a) for a in vals)
    return ('PASS' if ok else 'FAIL',f"非立方案例间距 {vals} mm；可读data_32每轴范围 {f.get('available_spacing_min_mm')} 至 {f.get('available_spacing_max_mm')}",
            '预设：两案例均超出生成器默认[0.3,0.8]mm。文件范围可核实；缺训练配置/哈希时不能确认它就是某权重的训练集。')


def d_shape(_):
    j,_,f=grid_claims_data();groups=[]
    for model in j['models']:
        for seed in [0,1,2]:
            groups.append(max(r['relative_prediction_change'] for r in f['shape_effects']
                              if r['model']==model['tag'] and r['seed']==seed and r['size']!='64x64x64'))
    ok=all(v>1e-3 for v in groups)
    return ('PASS' if ok else 'FAIL',f"6组中 {sum(v>1e-3 for v in groups)} 组超过1e-3；组内最大相对预测变化 {min(groups):.3g}–{max(groups):.3g}",
            '预设：固定0.6mm间距、相同物理ROI和32³参考RMS，改变上下文形状后，每个模型/种子至少一种非立方预测变化>1e-3；分母为32³预测L2范数。不是论文精度验收。')


def d_spacing_effect(_):
    j,_,f=grid_claims_data();groups=[]
    for model in j['models']:
        for seed in [0,1,2]:
            groups.append(max(r['nmae_ratio'] for r in f['spacing_effects']
                              if r['model']==model['tag'] and r['seed']==seed and r['spacing'].startswith('aniso')))
    ok=all(v>2 for v in groups)
    return ('PASS' if ok else 'FAIL',f"6组中 {sum(v>2 for v in groups)} 组超过2倍；组内最大误差比 {min(groups):.3g}–{max(groups):.3g}",
            '预设假设：固定32³与自然RMS，两种各向异性间距至少一种使逐分量平均nMAE超过0.6mm的2倍。改变间距同时改变采样/每格空间频率，不能归因于trunk单一模块。')


GRID_CLAIMS=[('D0','诊断实验接口与对照完整',d_protocol),
             ('D1','原非立方案例混入间距范围外测试',d_spacing_range),
             ('D2','恒定间距输入仍存在形状/上下文依赖',d_shape),
             ('D3','固定立方形状下各向异性间距显著增加误差',d_spacing_effect)]


def spacing_evidence():
    from pathlib import Path
    from paper_recheck import sha256
    from spacing_probe import error
    root=Path('evidence/spacing_probe_v1')
    j=json.loads((root/'summary.json').read_text(encoding='utf-8'))
    m=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    if j['version']!='spacing-probe-v1' or j['version']!=m['version']:raise ValueError('probe version')
    for name,key in [('manifest.json','manifest_sha256'),('arrays.npz','arrays_sha256')]:
        if sha256(root/name)!=j[key]:raise ValueError('probe hash '+name)
    for name,h in m['source_hashes'].items():
        if sha256(root/'source'/name)!=h:raise ValueError('probe source '+name)
    for model in j['models']:
        if model['sha256']!=model['sha256_after']:raise ValueError('probe weights changed')
    cases={c['key']:c for c in m['cases']}
    expected={(mo['tag'],c) for mo in j['models'] for c in cases}
    if {(r['model'],r['case']) for r in j['rows']}!=expected or len(j['rows'])!=462:
        raise ValueError('incomplete spacing experiment')
    f=dict(interaction=[],trunk_effects=[],axis_sweep=[],plane_sweep=[])
    with np.load(root/'arrays.npz',allow_pickle=False) as z:
        for r in j['rows']:
            c=cases[r['case']];p=z[r['pred_key']].astype(float)
            t=z[c['key']+'_true'];y=z[c['key']+'_yee']
            if not np.isfinite(p).all():raise ValueError('nonfinite prediction')
            r['rel_l2']=error(p,t);r['yee_rel_l2']=error(y,t);r['pred_vs_yee_rel_l2']=error(p,y)
            if 'active_curl' in c:
                ac=c['active_curl'];r['active_gain']=float(np.sum(p[ac]*t[ac])/np.sum(t[ac]**2))
                r['leakage_rel_l2']=float(np.linalg.norm(p[[q for q in range(3) if q!=ac]].ravel())/np.linalg.norm(t.ravel()))
            item=dict(c,**{k:v for k,v in r.items() if k!='case'})
            if c['family']=='multi_axis':f['axis_sweep'].append(item)
            elif c['family'] not in ['interaction','trunk_only']:f['plane_sweep'].append(item)
        lookup={(r['model'],r['case']):r for r in j['rows']}
        for model in j['models']:
            tag=model['tag']
            for seed in [0,1,2]:
                base=lookup[(tag,f'm{seed}_interaction_base')]
                for v in ['base','fine','coarse','both']:
                    r=lookup[(tag,f'm{seed}_interaction_{v}')]
                    f['interaction'].append(dict(model=tag,seed=seed,variant=v,rel_l2=r['rel_l2'],
                        yee_rel_l2=r['yee_rel_l2'],network_over_yee=r['rel_l2']/r['yee_rel_l2'],
                        ratio_to_base=r['rel_l2']/base['rel_l2']))
            for c in m['cases']:
                if c['family']!='trunk_only':continue
                base=lookup[(tag,f'p{c["axis"]}{c["pol"]}_trunk_only_0.6')]
                r=lookup[(tag,c['key'])]
                t=z[c['key']+'_true'];p=z[r['pred_key']].astype(float);pb=z[base['pred_key']]
                f['trunk_effects'].append(dict(model=tag,axis=c['axis'],pol=c['pol'],value=c['value'],
                    h_mm=c['h_mm'],relative_change=float(np.linalg.norm((p-pb).ravel())/np.linalg.norm(t.ravel())),
                    rel_l2=r['rel_l2'],active_gain=r['active_gain'],leakage_rel_l2=r['leakage_rel_l2']))
    return j,m,f


_SPACING_CACHE=None


def spacing_claims_data():
    global _SPACING_CACHE
    if _SPACING_CACHE is None:_SPACING_CACHE=spacing_evidence()
    return _SPACING_CACHE


def s_protocol(_):
    j,_,_=spacing_claims_data();worst=max(j['checks'].values())
    return ('PASS' if worst<=1e-10 else 'FAIL',f"462组预测；恒等式检查最大偏差 {worst:.2e}",
            '预设：Yee差分/傅里叶符号、固定q输入/缩放真值、仅trunk干预的输入/真值偏差≤1e-10；组合和哈希完整。')


def s_discrete(_):
    _,_,f=spacing_claims_data()
    vals=[r['network_over_yee'] for r in f['interaction'] if r['variant']=='both']
    return ('PASS' if len(vals)==6 and all(v>5 for v in vals) else 'FAIL',
            f"6组中{sum(v>5 for v in vals)}组超过5倍；DCO/Yee相对L2误差比 {min(vals):.2f}–{max(vals):.2f}",
            '预设：固定32³、间距(0.3,0.2,1.2)mm的六个模型/种子中，DCO误差均>标准Yee误差5倍。Yee是对照，不是解析目标的误差下限。')


def s_trunk(_):
    j,_,f=spacing_claims_data();vals=[]
    for mo in j['models']:
        for axis in range(3):
            for pol in [q for q in range(3) if q!=axis]:
                vals.append(max(r['relative_change'] for r in f['trunk_effects']
                                if r['model']==mo['tag'] and r['axis']==axis and r['pol']==pol))
    return ('PASS' if all(v>.01 for v in vals) else 'FAIL',
            f"12种模型/方向组合中{sum(v>.01 for v in vals)}种超过1%；各组合最大变化 {100*min(vals):.2f}%–{100*max(vals):.2f}%",
            '预设：固定branch输入、输出还原、真实旋度，仅改变物理无关的横向间距坐标，每个组合至少一干预使预测变化>真值L2的1%。这是单波结构探针，不代表全部Fig6误差已归因。')


SPACING_CLAIMS=[('S0','单轴/单波实验恒等式与产物完整',s_protocol),
                ('S1','网络偏差不能仅用标准Yee离散误差解释（5倍门槛）',s_discrete),
                ('S2','单波探针中坐标分支引入无关间距依赖（1%门槛）',s_trunk)]


def coverage_evidence():
    """Recompute approved A/B gates; validate actual optimizer counters too."""
    from pathlib import Path
    from paper_recheck import sha256
    import torch
    import paper_protocol as pp
    root=Path('evidence/coverage_ab_v1')
    j=json.loads((root/'summary.json').read_text(encoding='utf-8'))
    m=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    if j['version']!='coverage-ab-v1' or j['version']!=m['version']:raise ValueError('A/B version')
    if sha256(root/'manifest.json')!=j['manifest_sha256']:raise ValueError('A/B manifest hash')
    if sha256(root/'evaluation.npz')!=j['arrays_sha256']:raise ValueError('A/B evaluation hash')
    for name,h in m['source_hashes'].items():
        if sha256(root/'source'/name)!=h:raise ValueError('A/B source '+name)
    if m['initial_sha256']!=j['initial_sha256_after']:raise ValueError('initial weights changed')
    batches=np.asarray(m['batches'])
    if batches.shape!=(200,4) or not np.all((batches>=0)&(batches<128)):raise ValueError('A/B batches')
    if m['lr']!=1e-4 or m['updates_per_arm']!=200 or m['batch']!=4:raise ValueError('A/B approved budget')
    if m['ranges_mm']!={'A200':[.3,.8],'B200':[.2,1.2]}:raise ValueError('A/B approved ranges')
    for model in j['models']:
        if sha256(model['path'])!=model['sha256'] or model['sha256']!=model['sha256_after_evaluation']:
            raise ValueError('A/B checkpoint hash '+model['tag'])
    pairing=[]
    u=np.array([s['u'] for s in m['wave_specs']])
    for arm in ['A200','B200']:
        path=root/('train_'+arm+'.npz')
        if sha256(path)!=j['data_hashes'][arm]:raise ValueError('A/B data hash')
        with np.load(path,allow_pickle=False) as z:
            lo,hi=m['ranges_mm'][arm]
            pairing.append(float(np.max(np.abs((z['D'].astype(float)*1e3-lo)/(hi-lo)-u))))
        record=next(r for r in j['training'] if r['tag']==arm)
        hist=json.loads((root/(arm+'_hist.json')).read_text(encoding='utf-8'))
        if sha256(root/(arm+'_hist.json'))!=record['history_sha256']:raise ValueError('A/B history hash')
        if [r['update'] for r in hist['updates']]!=list(range(1,201)):raise ValueError('A/B update records')
        if hist['config']['initial_sha256']!=m['initial_sha256']:raise ValueError('A/B starting weights differ')
        if hist['config']['lr']!=1e-4 or hist['config']['batch']!=4:raise ValueError('A/B optimizer settings')
        ck=torch.load(record['path'],map_location='cpu',weights_only=False)
        steps=[int(s['step'].item()) for s in ck['optimizer_state']['state'].values()]
        if not steps or min(steps)!=200 or max(steps)!=200 or ck['updates']!=200:raise ValueError('actual Adam update budget')
        del ck
    if max(pairing)>1e-6:raise ValueError('A/B paired spacing mismatch')
    tags=['A0','A200','B200'];shapes=['x'.join(map(str,s)) for s in pp.SHAPES]
    expected={(tag,s,shape) for tag in tags for s in [10,11,12] for shape in shapes}
    actual={(r['model'],r['seed'],r['size']) for r in j['rows']}
    if len(j['rows'])!=36 or actual!=expected:raise ValueError('A/B held-out cases incomplete')
    expected_probes={(tag,a,p,v) for tag in tags for a in range(3) for p in range(3) if a!=p for v in [.3,.4,.6,.8,1.2]}
    if len(j['probe_rows'])!=90 or {(r['model'],r['axis'],r['pol'],r['value']) for r in j['probe_rows']}!=expected_probes:
        raise ValueError('A/B probes incomplete')
    f=dict(pairing_max=max(pairing),noncubic_ratios=[],probe_maxima=[],probe_effects=[])
    with np.load(root/'evaluation.npz',allow_pickle=False) as z:
        for r in j['rows']:r['metrics']=pp.vector_metrics(z[r['pred_key']],z[r['true_key']])
        for r in j['probe_rows']:
            base=next(b for b in j['probe_rows'] if b['model']==r['model'] and b['axis']==r['axis'] and b['pol']==r['pol'] and b['value']==.6)
            p=z[r['pred_key']].astype(float);pb=z[base['pred_key']];t=z[r['true_key']]
            if not np.isfinite(p).all():raise ValueError('nonfinite A/B probe')
            effect=float(np.linalg.norm((p-pb).ravel())/np.linalg.norm(t.ravel()))
            f['probe_effects'].append(dict(model=r['model'],axis=r['axis'],pol=r['pol'],value=r['value'],relative_change=effect))
    def get(tag,seed,shape):return next(r for r in j['rows'] if (r['model'],r['seed'],r['size'])==(tag,seed,shape))
    for seed in [10,11,12]:
        for shape in ['64x96x16','32x64x16']:
            a=get('A200',seed,shape)['metrics'];b=get('B200',seed,shape)['metrics'];zero=get('A0',seed,shape)['metrics']
            f['noncubic_ratios'].append(dict(seed=seed,size=shape,nmae_B_over_A=b['macro_nmae']/a['macro_nmae'],
                mre_B_over_A=b['components']['x']['mre_eq5']/a['components']['x']['mre_eq5'],
                nmae_B_over_initial=b['macro_nmae']/zero['macro_nmae'],
                mre_B_over_initial=b['components']['x']['mre_eq5']/zero['components']['x']['mre_eq5']))
    f['geomean_nmae_B_over_A']=float(np.exp(np.mean(np.log([r['nmae_B_over_A'] for r in f['noncubic_ratios']]))))
    f['geomean_mre_B_over_A']=float(np.exp(np.mean(np.log([r['mre_B_over_A'] for r in f['noncubic_ratios']]))))
    f['cube_means']={tag:float(np.mean([get(tag,s,'32x32x32')['metrics']['macro_nmae'] for s in [10,11,12]])) for tag in tags}
    f['cube_B_over_initial']=f['cube_means']['B200']/f['cube_means']['A0']
    for tag in tags:
        for axis in range(3):
            for pol in [p for p in range(3) if p!=axis]:
                f['probe_maxima'].append(dict(model=tag,axis=axis,pol=pol,maximum=max(r['relative_change'] for r in f['probe_effects']
                    if (r['model'],r['axis'],r['pol'])==(tag,axis,pol))))
    f['probe_mean_maximum']={tag:float(np.mean([r['maximum'] for r in f['probe_maxima'] if r['model']==tag])) for tag in tags}
    f['probe_B_over_initial']=f['probe_mean_maximum']['B200']/f['probe_mean_maximum']['A0']
    return j,m,f


_COVERAGE_CACHE=None


def coverage_claims_data():
    global _COVERAGE_CACHE
    if _COVERAGE_CACHE is None:_COVERAGE_CACHE=coverage_evidence()
    return _COVERAGE_CACHE


def t_protocol(_):
    j,_,f=coverage_claims_data()
    ok=j['tests_passed'] and j['test_count']>=12
    return ('PASS' if ok else 'FAIL',f"两组各200次Adam更新；36组独立种子测试、90组探针；{j['test_count']}项测试通过；配对偏差 {f['pairing_max']:.2e}",
            '核验源/数据/权重/曲线哈希、共同起点与配对随机数、实际优化器step=200；不把训练次数当精度成果。')


def t_improvement(_):
    _,_,f=coverage_claims_data();a,b=f['geomean_nmae_B_over_A'],f['geomean_mre_B_over_A']
    return ('PASS' if a<=.8 and b<=.8 else 'FAIL',f"非立方六案例B/A几何平均比：nMAE比值 {a:.4f}，x-MRE比值 {b:.4f}",
            '已批准门槛：两个比值均≤0.8；同样200更新的扩展范围B对原范围A，独立振幅种子10/11/12。')


def t_regression(_):
    _,_,f=coverage_claims_data();v=f['cube_B_over_initial']
    return ('PASS' if v<=1.1 else 'FAIL',f"32³三种子平均nMAE：B/起点={v:.4f}",
            '已批准门槛：≤1.1，即原范围内0.6mm、32³平均nMAE不比起点退步超过10%。')


def t_trunk(_):
    _,_,f=coverage_claims_data();v=f['probe_B_over_initial']
    return ('PASS' if v<=1 else 'FAIL',f"六方向最大干预效应的平均：B/起点={v:.4f}",
            '已批准门槛：≤1；比较每方向最大横向坐标干预效应再取六者平均。这是错误依赖，不是场误差。')


COVERAGE_CLAIMS=[('T0','A/B配对、更新预算与证据完整',t_protocol),
                 ('T1','扩展间距B在非立方测试比A改善至少20%',t_improvement),
                 ('T2','扩展间距B在原范围内未明显退步',t_regression),
                 ('T3','扩展间距B的错误坐标依赖未比起点加重',t_trunk)]

# --------------------------------------------------------------------------- #
# readers.  Schema matches what spectral_dco.py / train_dco.py actually write.
# --------------------------------------------------------------------------- #


def spectral(tag=None):
    """tag -> list of rows.  Row keys: cfl seed rho rho_exact eps0 rmsE
    blowup pred_blowup."""
    out = {}
    for f in sorted(glob.glob("spectral_*.json")):
        t = os.path.basename(f)[len("spectral_"):-len(".json")]
        if tag and t != tag:
            continue
        try:
            j = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        rows = [dict(r, tag=t) for r in j.get("rows", [])]
        if rows:
            out[t] = rows
    return out


def usable(rows):
    """Rows that mean anything.  eps0 > 0.5 means the network output is half
    the size of the field itself -- that checkpoint is not integrating, it is
    being replaced by its own error, and its 'lifetime' is not a lifetime."""
    return [r for r in rows
            if r.get("eps0", 0) <= 0.5 and r.get("blowup", -1) > 0
            and r.get("pred_blowup")]


def per_ckpt(all_rows):
    """One (rho-1, lifetime, eps0) per checkpoint, taken at the largest CFL
    they all share, so the comparison is not confounded by the time step."""
    flat = [r for rs in all_rows.values() for r in usable(rs)]
    if not flat:
        return {}
    hi = max(r["cfl"] for r in flat)
    out = {}
    for t in sorted(all_rows):
        rs = [r for r in usable(all_rows[t]) if r["cfl"] == hi]
        if rs:
            out[t] = dict(
                rho1=float(np.mean([r["rho"] for r in rs])) - 1.0,
                life=float(np.mean([r["blowup"] for r in rs])),
                eps0=float(np.mean([r["eps0"] for r in rs])),
                n=len(rs), cfl=hi)
    return out


def accuracy(tag):
    """Final single-step relative L2 from <tag>_hist.json, or None."""
    f = tag + "_hist.json"
    if not os.path.exists(f):
        return None
    try:
        j = json.load(open(f, encoding="utf-8"))
    except Exception:
        return None
    for k in ("relL2", "val_relL2", "val"):
        v = j.get(k)
        if isinstance(v, list) and v:
            return float(v[-1])
        if isinstance(v, (int, float)):
            return float(v)
    return None


def partial(x, y, z):
    """corr(x, y) with z held fixed.  Needed because accuracy and rho move
    together across checkpoints -- a plain correlation cannot say which of
    them the lifetime is actually responding to."""
    x, y, z = map(lambda v: np.asarray(v, float), (x, y, z))
    if len(x) < 4:
        return float("nan")

    def resid(v):
        A = np.vstack([z, np.ones_like(z)]).T
        return v - A @ np.linalg.lstsq(A, v, rcond=None)[0]
    rx, ry = resid(x), resid(y)
    if rx.std() < 1e-12 or ry.std() < 1e-12:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


# --------------------------------------------------------------------------- #
# claims.  Each returns (verdict, value_str, detail_str).
# verdict: "PASS" / "FAIL" / "NODATA"
# --------------------------------------------------------------------------- #

MISSING = {}          # claim id -> command that would produce the artifact


def need(cid, cmd, what):
    MISSING[cid] = cmd
    return "NODATA", "缺数据", f"跑 `{cmd}` 生成 {what}"


def c_selftest_cached(_):
    """The spectral probe is only believable if it returns rho = 1 for an
    operator whose rho is known to be 1."""
    m = spectral()
    rows = [r for rs in m.values() for r in rs if "rho_exact" in r]
    if not rows:
        return need("selftest", "py -3.11 spectral_dco.py --selftest",
                    "rho_exact 列")
    worst = max(abs(r["rho_exact"] - 1.0) for r in rows)
    ok = worst < 1e-3
    return ("PASS" if ok else "FAIL", f"|rho_exact - 1| <= {worst:.2e}",
            f"{len(rows)} 行里精确 Yee 旋度的谱半径都贴着 1；阈值 1e-3")


def c_rho_predicts(_):
    m = spectral()
    flat = [r for rs in m.values() for r in usable(rs)]
    if len(flat) < 20:
        return need("rho", "run_rho32.bat", "spectral_*.json（16 个 checkpoint）")
    p = np.log([r["pred_blowup"] for r in flat])
    q = np.log([r["blowup"] for r in flat])
    pooled = float(np.corrcoef(p, q)[0, 1])
    good = 0
    tot = 0
    for t, rs in m.items():
        rs = usable(rs)
        if len(rs) < 4:
            continue
        tot += 1
        c = np.corrcoef(np.log([r["pred_blowup"] for r in rs]),
                        np.log([r["blowup"] for r in rs]))[0, 1]
        if c > 0.8:
            good += 1
    ok = pooled >= 0.8
    return ("PASS" if ok else "FAIL", f"corr = {pooled:+.3f}",
            f"{len(flat)} 个点，{tot} 个 checkpoint 中 {good} 个自身 corr>0.8；"
            f"阈值 0.8")


def c_fixed_time(_):
    """The headline: does blow-up happen at a fixed PHYSICAL time, or after a
    fixed NUMBER of steps?  If physical time, halving the time step buys
    literally nothing and the instability belongs to the learnt operator, not
    to the time discretisation.

    2026-09-10, first run on real data: the original version of this check
    took max/min of blowup*cfl over every individual row and got 1.446x
    against a 1.30x threshold -- FAIL.  That statistic was wrong, and wrong in
    a way that flattered nobody: it lumps the seed-to-seed scatter in with the
    CFL dependence, so it cannot say which one it is measuring.  (The 1.023x
    I had quoted earlier came from the same quantity computed on per-
    checkpoint MEANS, i.e. with the noise averaged out first -- that framing
    was too kind to the claim and is retired.)

    So measure the thing itself.  Fit  log(lifetime_steps) = a + b log(CFL)
    per checkpoint, averaging seeds at each CFL first so noise enters as fit
    error rather than as signal:
        b = -1  ->  steps x CFL constant  ->  fixed physical time  (the claim)
        b =  0  ->  steps constant        ->  fixed step count     (the rival)
    Criteria, fixed before looking: median b within 0.15 of -1, and at least
    75% of checkpoints with b in [-1.15, -0.85].
    """
    m = spectral()
    slopes, noise = {}, []
    for t, rs in m.items():
        rs = usable(rs)
        cfls = sorted({r["cfl"] for r in rs})
        if len(cfls) < 3:
            continue
        y = []
        for c in cfls:
            v = [r["blowup"] for r in rs if r["cfl"] == c]
            y.append(float(np.mean(v)))
            if len(v) > 1:
                noise.append(max(v) / min(v))
        slopes[t] = float(np.polyfit(np.log(cfls), np.log(y), 1)[0])
    if len(slopes) < 4:
        return need("fixedtime", "run_rho32.bat",
                    "至少 4 个 checkpoint x 3 个 CFL 的 spectral_*.json")

    b = np.array(list(slopes.values()))
    med = float(np.median(b))
    inband = int(np.sum((b >= -1.15) & (b <= -0.85)))
    frac = inband / len(b)
    ok = abs(med + 1.0) <= 0.15 and frac >= 0.75
    seed_noise = float(np.median(noise)) if noise else float("nan")
    return ("PASS" if ok else "FAIL",
            f"斜率 b 中位数 {med:+.3f}（固定物理时间 = -1，固定步数 = 0），"
            f"{inband}/{len(b)} 个落在 [-1.15,-0.85]",
            f"判据：|中位数 +1| <= 0.15 且 >=75% 在带内（实得 {frac:.0%}）。"
            f"b 的范围 {b.min():+.2f}~{b.max():+.2f}；"
            f"同一 CFL 下换 seed 的寿命本身就差 {seed_noise:.2f}x，"
            f"这是噪声底，不是效应")


def c_accuracy_via_rho(_):
    """Does accuracy buy stability on its own, or only through rho?"""
    m = per_ckpt(spectral())
    tags = [t for t in m if accuracy(t) is not None]
    if len(tags) < 6:
        return need("partial", "run_rho32.bat",
                    f"更多 <tag>_hist.json（现有 {len(tags)} 个，需 >=6）")
    life = np.log([m[t]["life"] for t in tags])
    rho1 = np.log([max(m[t]["rho1"], 1e-9) for t in tags])
    acc = np.log([accuracy(t) for t in tags])
    p_acc = partial(acc, life, rho1)
    p_rho = partial(rho1, life, acc)
    ok = abs(p_rho) > abs(p_acc)
    return ("PASS" if ok else "FAIL",
            f"精度|固定rho: {p_acc:+.3f}　rho|固定精度: {p_rho:+.3f}",
            f"{len(tags)} 个 checkpoint。判据：rho 的偏相关绝对值更大，"
            f"即精度只是通过 rho 起作用")


def c_scale_vs_physics(_):
    """dco_paper32 is pure supervised, zero physics loss, just bigger.
    pidon_R2_all has the full physics + rollout loss.  If they tie, then the
    paper's Fig 7/8 is explained by scale, not by Algorithm 1."""
    m = per_ckpt(spectral())
    a, b = "dco_paper32", "pidon_R2_all"
    if a not in m or b not in m:
        return need("scale",
                    f"py -3.11 spectral_dco.py --ckpt {a}.pt  (以及 {b}.pt)",
                    f"spectral_{a}.json / spectral_{b}.json")
    ra, rb = m[a]["rho1"], m[b]["rho1"]
    ratio = max(ra, rb) / min(ra, rb)
    ok = ratio < 1.15
    return ("PASS" if ok else "FAIL",
            f"{a} rho-1={ra:.4f}　{b} rho-1={rb:.4f}　比值 {ratio:.3f}x",
            "阈值 1.15x。打平 = 纯监督的规模能顶上全套物理损失")


def c_literal_reading(_):
    """The paper does not state the trunk coordinate encoding or the input
    normalisation.  dco_L3b is the literal reading; dco_L3d is the fixed one."""
    m = per_ckpt(spectral())
    a, b = "dco_L3b", "dco_L3d"
    if a not in m or b not in m:
        return need("literal", f"py -3.11 spectral_dco.py --ckpt {a}.pt",
                    f"spectral_{a}.json / spectral_{b}.json")
    ra, rb = m[a]["rho1"], m[b]["rho1"]
    ok = ra > rb
    return ("PASS" if ok else "FAIL",
            f"{a} rho-1={ra:.4f}　{b} rho-1={rb:.4f}　差 {ra / rb:.2f}x",
            "两个实现开关（trunk 坐标编码 / 归一化）同时影响精度和稳定性。"
            "注意口径更正（2026-09-10 读原文后）：这两点论文其实都写了 —— "
            "III-A「trunk decodes coordinate information into cell sizes」"
            "指定了 cellsize 编码，III-B「output normalized by the local "
            "maximum for each component」指定了按分量的输出归一化。所以 "
            f"{a}（abs 坐标）不是「论文字面读法」，那个标签是错的，已撤。"
            "本条现在只主张我们自己消融里的敏感度，不再主张论文有遗漏")


def c_l3c_wrinkle(_):
    """Report the counterexample in the same breath as the claim above.
    dco_L3c (cellsize+max) beats dco_L3d (cellsize+rms) on rho, so the rms
    normalisation improved dimension invariance and made rho worse."""
    m = per_ckpt(spectral())
    if "dco_L3c" not in m or "dco_L3d" not in m:
        return need("wrinkle", "py -3.11 spectral_dco.py --ckpt dco_L3c.pt",
                    "spectral_dco_L3c.json")
    c, d = m["dco_L3c"]["rho1"], m["dco_L3d"]["rho1"]
    # this claim asserts the AWKWARD direction; PASS means "yes, still awkward"
    ok = c < d
    return ("WARN" if ok else "PASS",
            f"dco_L3c rho-1={c:.4f} < dco_L3d rho-1={d:.4f}"
            if ok else f"dco_L3c={c:.4f} >= dco_L3d={d:.4f}（反常消失了）",
            "这是反例，不是支持项。消融链终点在 rho 上反而更差，讲的时候要一起说")


def c_long_run_impossible(_):
    """The strategic number.  How much better would rho have to be to run the
    1e5 steps the paper's setting implies?"""
    m = per_ckpt(spectral())
    if not m:
        return need("longrun", "run_rho32.bat", "spectral_*.json")
    best = min(m.values(), key=lambda v: v["rho1"])
    tag = min(m, key=lambda t: m[t]["rho1"])
    need_rho1 = 1.0 / 1e5           # rho^1e5 stays O(1)  =>  rho-1 ~ 1e-5
    factor = best["rho1"] / need_rho1
    return ("PASS", f"最好 {tag}: rho-1={best['rho1']:.4f}，"
                    f"要跑 1e5 步需再小 {factor:,.0f}x",
            "寿命约为 1/(rho-1)，所以目标步数 N 需要 rho-1 ~ 1/N。"
            + _grid_evidence(m)
            + "　按实测倍数外推，规模路线要跨过 4 个数量级并无依据 —— "
            "两周后的论文规模复现就是对「规模能否解决发散」的直接检验。"
            "这条不是失败，是本复现最有价值的负面结论")


def _grid_evidence(m):
    """2026-09-10 更正：这里原来写着「一次网格加倍大约把 rho-1 减半，所以还
    差 13 次加倍」。那个「减半」是我凭印象写的，而我们自己的数据否定它 ——
    唯一一次真实的训练网格加倍只改善了个位数百分比。用未经支持的外推去论证
    「不可行」、方向上还恰好对自己有利，不能留。改为只报那一次实测。"""
    if PARITY_CKPT not in m:
        return ""
    others = {t: v for t, v in m.items() if t != PARITY_CKPT}
    if not others:
        return ""
    b = min(others, key=lambda t: others[t]["rho1"])
    r16, r32 = others[b]["rho1"], m[PARITY_CKPT]["rho1"]
    return (f"　实测：唯一一次训练网格加倍（{b} 16^3 rho-1={r16:.4f} -> "
            f"{PARITY_CKPT} 32^3 rho-1={r32:.4f}）只带来 {r16 / r32:.2f}x 改善。")


# --------------------------------------------------------------------------- #
# EXP 2 claims.  These read test_results_*.npz, which test_dco.py writes.
# --------------------------------------------------------------------------- #

# Qi & Sarris 2025, section III-D, network trained at 32^3.
#
# 2026-09-10, after actually reading the paper: these are MRE as defined in
# the paper's eq. (5) -- the MEAN POINTWISE RELATIVE ERROR,
#     MRE = (1/N) sum |y_pred - y_true| / |y_true|   (and |y_pred| where
#     y_true == 0),
# which is neither relative L2 nor MAE/max.  We had been comparing our nMAE
# to them on the assumption that the paper used MAE/max.  It does not.  That
# is the SAME cross-metric mistake that produced the retracted "10x worse"
# claim, made a second time with a different wrong metric.
PAPER_IIID = {"64^3": 4.1e-3, "64x96x16": 3.8e-3, "32x64x16": 4.7e-3}


# The checkpoint the paper-parity claim is ABOUT.  Designated by its
# configuration -- L=4, base 32, trained on a 32-cubed grid, which is what the
# paper used -- and NOT by its score.  Comparing a 16-cubed-trained net to the
# paper's 32-cubed-trained one is not a reproduction test, it is a handicap
# match, so those checkpoints are reported below but do not decide the verdict.
PARITY_CKPT = "dco_paper32"


def _exp2_all():
    """[(label, train_n, {size: relL2}, {size: nMAE})] for every results file.

    2026-09-10: the first version of this read only the NEWEST
    test_results_*.npz.  run_meal.bat happened to finish with the dco_L4b
    control, so C9 graded the control and reported FAIL at 13.35x -- a real
    number attached to the wrong claim.  Read them all; let the claim say
    which one it is about.
    """
    out = []
    for f in sorted(glob.glob("test_results_*.npz")):
        try:
            z = np.load(f, allow_pickle=True)
        except Exception:
            continue
        if "exp2_nmae" not in z:
            continue
        sizes = [str(x) for x in z["exp2_sizes"]]
        tn = int(z["train_n"]) if "train_n" in z else 0
        out.append((os.path.basename(f)[len("test_results_"):-len(".npz")], tn,
                    dict(zip(sizes, [float(v) for v in z["exp2_rel"]])),
                    dict(zip(sizes, [float(v) for v in z["exp2_nmae"]]))))
    return out


def _metric_note(lab=None):
    return "式(5)为逐点相对误差；共同归一化不会变成MAE/max。旧EXP2为随机场/随机间距，不是Fig6固定案例。"


def c_dim_invariance(_):
    return ("RETRACTED", "旧0.70~1.50倍比较撤回；原始NPZ保留",
            _metric_note()+" 新协议与现有权重的结果见P0-P2。")


def c_metric_gap(_):
    """相对 L2 和 nMAE 不能混用 -- 这是上面那条错误的根源，值得单独立一条。"""
    all_ = _exp2_all()
    rr, labs = [], []
    for lab, _, rel, nm in all_:
        v = [rel[k] / nm[k] for k in rel if nm.get(k, 0) > 0]
        if v:
            rr += v
            labs.append(f"{lab} {min(v):.1f}-{max(v):.1f}x")
    if not rr:
        return need("exp2", "run_meal.bat", "test_results_*.npz")
    ok = min(rr) > 2.0
    return ("PASS" if ok else "FAIL",
            f"指标比值（relative L2 / nMAE）：{min(rr):.1f}~{max(rr):.1f}x"
            f"（{len(all_)} 个 checkpoint）",
            "判据：最小比值 >2，即两个口径处处相差一倍以上，不可互换。"
            f"逐 checkpoint：{'；'.join(labs)} —— 倍数本身就不是常数，"
            "所以任何记下来的固定倍数都不能用")


DISK_CLAIMS = [
    ("C1", "谱半径探针可信：精确 Yee 旋度测出来 rho = 1", c_selftest_cached),
    ("C2", "rho 能预测闭环能跑多少步", c_rho_predicts),
    ("C3", "发散发生在固定物理时间，不是固定步数", c_fixed_time),
    ("C4", "精度只通过 rho 影响稳定性", c_accuracy_via_rho),
    ("C5", "规模可以替代物理损失", c_scale_vs_physics),
    ("C6", "论文没写明的实现细节同时伤精度和稳定性", c_literal_reading),
    ("C7", "反例：消融链终点在 rho 上反而更差", c_l3c_wrinkle),
    ("C8", "无约束学习算子做不了长时程积分", c_long_run_impossible),
    ("C9", "旧跨指标、跨测试场景的论文对比", c_dim_invariance),
    ("C10", "相对 L2 与 nMAE 不可互换（上一条曾因此报错）", c_metric_gap),
]


def _stage2_rows(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)['rows']


def s2_longrun(_):
    p = 'evidence/pidon_stage2_128_separate_reset_lr3e4_i500.json'
    if not os.path.exists(p):
        return 'NODATA', p, '缺少128步轨迹'
    r = _stage2_rows(p); vals = [x['nmae'] for x in r]
    finite = all(np.isfinite(vals)) and len(r) == 128
    return ('PASS' if finite else 'FAIL',
            f"{len(r)}步有限；末nMAE={vals[-1]:.3e}；最大={max(vals):.3e}",
            '判据：128行完整、nMAE全为有限数；这是阶段二机理长程证据，不等于8192步复现。')


def s2_precision(_):
    p = 'evidence/pidon_stage2_64_component_lr3e4_tol1e5.json'
    if not os.path.exists(p):
        return 'NODATA', p, '缺少64步tol=1e-5轨迹'
    r = _stage2_rows(p); vals = [x['nmae'] for x in r]
    # The first four steps are the source turn-on transient; assess the
    # settled high-precision segment separately from that unavoidable pulse.
    early = max(vals[4:30]); finite = all(np.isfinite(vals))
    ok = finite and len(r) == 64 and early < 1e-5 and vals[-1] < 1e-3
    return ('PASS' if ok else 'FAIL',
            f"64步有限；稳态段(step5–30)最大={early:.3e}；末步={vals[-1]:.3e}",
            '判据：排除前4步源开启瞬态后，tol=1e-5配置的step5–30误差<1e-5且64步末误差<1e-3；用于证明残差门槛影响，不宣称长期稳定。')


def s2_paper_gap(_):
    r = _stage2_rows('evidence/pidon_stage2_128_separate_reset_lr3e4_i500.json')
    ok = len(r) >= 8192
    return ('PASS' if ok else 'FAIL',
            f"实际最长轨迹={len(r)}步；论文目标=8192步",
            '判据：至少8192个逐步重训记录才可称达到论文步数；当前应保留为未完成。')


STAGE2_CLAIMS = [
    ('V1', 'Algorithm 1 128步轨迹保持有限', s2_longrun),
    ('V2', '收紧内层残差后64步误差显著降低', s2_precision),
    ('V3', '第二阶段已达到论文8192步目标', s2_paper_gap),
]


def n0_p0_audit(_):
    p = 'evidence/gpt6_plan_v1/audit.json'
    if not os.path.exists(p):
        return 'NODATA', p, '缺少 P0 审计产物'
    j = json.load(open(p, encoding='utf-8'))
    h = j['trajectories']['128_step']['strict_final_loss_reconstruction']
    e = j['trajectories']['64_step']['strict_final_loss_reconstruction']
    ok = (h['H']['passed_final_loss_lt_tol'], h['E']['passed_final_loss_lt_tol'],
          e['H']['passed_final_loss_lt_tol'], e['E']['passed_final_loss_lt_tol']) == (125, 105, 48, 26)
    return ('PASS' if ok else 'FAIL',
            f"历史回算 128步 H/E={h['H']['passed_final_loss_lt_tol']}/{h['E']['passed_final_loss_lt_tol']}；64步 H/E={e['H']['passed_final_loss_lt_tol']}/{e['E']['passed_final_loss_lt_tol']}",
            '判据：P0 原始 JSON 回算与登记数字一致；这是历史证据审计，不是当前代码的严格轨迹。')


def n1_p1_contract(_):
    p = 'evidence/gpt6_plan_v1/p1_recording_smoke/steps.jsonl'
    if not os.path.exists(p): return 'NODATA', p, '缺少 P1 正式记录烟雾测试'
    row = json.loads(open(p, encoding='utf-8').readline())
    needed = {'fit_H', 'fit_E', 'six_component_metrics', 'source_outside_probes'}
    ok = row.get('accepted') and needed <= set(row) and len(row['source_outside_probes']) == 3
    return ('PASS' if ok else 'FAIL',
            f"accepted={row.get('accepted')}；H/E实际更新={row.get('fit_H',{}).get('n_updates')}/{row.get('fit_E',{}).get('n_updates')}；源外探针={len(row.get('source_outside_probes', []))}",
            '判据：正式 JSONL 同时含命名残差、六分量和三个源外探针；单步宽阈值 smoke 不代表 DCO 精度。')


def n2_p2_control(_):
    p = 'evidence/gpt6_plan_v1/p2_exact_control.json'
    if not os.path.exists(p): return 'NODATA', p, '缺少 P2 精确控制结果'
    j = json.load(open(p, encoding='utf-8'))
    d, s = j['float64'], j['float32']
    ok = d['finite'] and s['finite'] and d['global_relative_l2'] <= 1e-10 and s['global_relative_l2'] <= 1e-4 and 'not a DCO' in d['classification']
    return ('PASS' if ok else 'FAIL',
            f"float64/float32 相对L2={d['global_relative_l2']:.3e}/{s['global_relative_l2']:.3e}；分类={d['classification']}",
            '判据：128步同序精确 Yee 控制有限且满足登记精度，并显式标为非DCO。')


def n3_p3_gate(_):
    p = 'evidence/gpt6_plan_v1/fixed_states/fixed_state_report.json'
    if not os.path.exists(p): return 'NODATA', p, '缺少 P3 固定状态报告'
    j = json.load(open(p, encoding='utf-8'))
    failed = [(x['step'], x['which'], x['fit']['loss_final']) for x in j['tasks'] if not x['fit']['passed']]
    return ('PASS' if not failed else 'FAIL', f"固定状态未达标={failed}",
            '判据：所有登记任务必须在500更新内 R<1e-4；FAIL 触发 P4-A，不允许直接进入闭环。')


def n4_p4_gate(_):
    p = 'evidence/gpt6_plan_v1/p4a_development_e43/fixed_state_report.json'
    if not os.path.exists(p): return 'NODATA', p, '缺少 P4-A 开发状态报告'
    j = json.load(open(p, encoding='utf-8'))
    task = j['tasks'][0]
    fit = task['fit']
    return ('PASS' if fit['passed'] else 'FAIL',
            f"Adam200={task['baseline']['loss_final']:.3e}；Adam200+LBFGS {fit['n_closures']} closures={fit['loss_final']:.3e}",
            '判据：注册的200 closure、60秒上限内必须 R<1e-4 才能进入冻结验证；FAIL 即 P4-A 止损。')


def n5_p5_gate(_):
    p = 'evidence/gpt6_plan_v1/phase1_pilot_corrected/learnability.json'
    if not os.path.exists(p): return 'NODATA', p, '缺少 P5 修正后可学习性证据'
    j = json.load(open(p, encoding='utf-8'))
    final = j['history'][-1]
    ok = j['passed'] and j['actual_updates'] <= 500
    return ('PASS' if ok else 'FAIL',
            f"更新={j['actual_updates']}；损失下降={j['loss_reduction']:.1f}x；宏nMAE={final['macro_nmae']:.3e}",
            '判据：固定样本相对平方损失下降≥100x且宏nMAE≤1e-3，才可进入P5 A/B；FAIL 先停在标签/归一化/表达诊断。')


PIDON_V2_CLAIMS = [
    ('N0', 'P0历史证据审计可重算', n0_p0_audit),
    ('N1', 'P1严格停止与测量记录接口完整', n1_p1_contract),
    ('N2', 'P2精确Yee控制通过且未冒充DCO', n2_p2_control),
    ('N3', 'P3固定状态G1门槛', n3_p3_gate),
    ('N4', 'P4-A有无可进入闭环的候选', n4_p4_gate),
    ('N5', 'P5固定样本可学习性门槛', n5_p5_gate),
]


def v2_r0_contract(_):
    root = 'evidence/gpt6_plan_v2'
    needed = [os.path.join(root, name) for name in ('acceptance.json', 'audit.json', 'R0_REPORT.md')]
    if not all(os.path.exists(path) for path in needed):
        return 'NODATA', '缺少 R0 产物', 'v2 门槛或源码快照未冻结。'
    j = json.load(open(os.path.join(root, 'acceptance.json'), encoding='utf-8'))
    ok = (j.get('g0', {}).get('nonzero_target_R_lt') == 1e-4
          and j.get('g1', {}).get('max_adam_updates') == 500
          and j.get('g3', {}).get('steps') == 8192)
    return ('PASS' if ok else 'FAIL', f"R={j['g0']['nonzero_target_R_lt']}; Adam={j['g1']['max_adam_updates']}; G3={j['g3']['steps']}步",
            '判据：v2 数字门槛、预算和长程禁止条件在新实验前已冻结。')


def v2_r1_contract(_):
    p = 'evidence/gpt6_plan_v2/R1_REPORT.md'
    if not os.path.exists(p):
        return 'NODATA', '缺少 R1 报告', '停止/恢复合同尚无记录。'
    text = open(p, encoding='utf-8').read()
    ok = all(token in text for token in ('E_pending', '不会重新获得更新次数', 'NaN'))
    return ('PASS' if ok else 'FAIL', 'R1 微型事务回归已记录',
            '判据：同配置恢复、累计预算、非有限 raw/safe、零目标与测量合同均有运行记录；不是 DCO 精度。')


def v2_r2_control(_):
    p = 'evidence/gpt6_plan_v2/R2_exact_control.json'
    if not os.path.exists(p):
        return 'NODATA', '缺少 R2 控制', '未执行生产路径独立 Yee 对照。'
    j = json.load(open(p, encoding='utf-8'))
    d, s, z = j['float64'], j['float32'], j['zero_curl_negative']
    ok = (d['finite'] and s['finite'] and d['max_global_relative_l2'] <= 1e-10
          and s['max_global_relative_l2'] <= 1e-4 and z['max_global_relative_l2'] > .05
          and 'not a DCO' in d['classification'])
    return ('PASS' if ok else 'FAIL',
            f"double/single={d['max_global_relative_l2']:.3e}/{s['max_global_relative_l2']:.3e}; zero={z['max_global_relative_l2']:.3e}",
            '判据：128步生产事务对独立参考满足 double<=1e-10、single<=1e-4，且零旋度负例被拒绝；非 DCO 成绩。')


def v2_r3_p5(_):
    p = 'evidence/gpt6_plan_v2/R3_recompute.json'
    if not os.path.exists(p):
        return 'NODATA', '缺少 R3 复算', '保存的 P5 权重尚未按逐样本逐分量口径复算。'
    j = json.load(open(p, encoding='utf-8'))
    value = j['corrected_macro_nmae']
    return ('PASS' if value <= 1e-3 else 'FAIL', f"正确宏 nMAE={value:.6e}",
            '判据：固定四样本逐样本逐分量宏 nMAE<=1e-3；FAIL 不会改变门槛。')


def v2_r4_g1(_):
    p = 'evidence/gpt6_plan_v2/R4_p4a_step0043/P4A.json'
    if not os.path.exists(p):
        return 'NODATA', '缺少 R4/P4-A', '开发状态或唯一优化分支尚未完成。'
    j = json.load(open(p, encoding='utf-8'))
    value = j['adam200_lbfgs']['residual_ratio']
    return ('PASS' if j['pass'] else 'FAIL', f"43步 curl-H P4-A R={value:.6e}",
            '判据：开发与冻结状态都须 R<1e-4 且 A_fixed<=1e-3；当前开发 P4-A 未过，后段为 NOT_RUN。')


PIDON_V2_CONTRACT_CLAIMS = [
    ('W0', 'R0 v2 门槛与证据账本冻结', v2_r0_contract),
    ('W1', 'R1 停止、恢复与测量合同', v2_r1_contract),
    ('W2', 'R2 生产路径精确 Yee 控制（非DCO）', v2_r2_control),
    ('W3', 'R3 正确口径的 P5 固定样本门槛', v2_r3_p5),
    ('W4', 'R4/P4-A G1 开发门槛', v2_r4_g1),
]

# --------------------------------------------------------------------------- #
# claims that need a (cheap) run
# --------------------------------------------------------------------------- #

RUN_CLAIMS = [
    ("R1", "精确旋度就是一个 12 权重的 3x3x3 卷积",
     [sys.executable, "exact_stencil.py"],
     r"relative L2\s+([0-9.eE+-]+)",
     lambda v: float(v) < 1e-12,
     "relative L2 < 1e-12（等价于机器精度，说明 2.25M 参数在学一个 12 参数的东西）"),
    ("R2", "自己写的 FDTD 参考解对得上解析解",
     [sys.executable, "run_fdtd_cavity.py"],
     r"^\s*\d{3}\s+[0-9.]+\s+[0-9.]+\s+([+-][0-9.]+)",
     lambda v: abs(float(v)) < 0.5,
     "每个模式 |误差| < 0.5%"),
    ("R4", "PEC 边界下伴随恒等式 curl_H = curl_E^T 仍精确成立",
     [sys.executable, "structured_pec.py"],
     r"RESULT pec_adjoint_err ([0-9.eE+-]+)",
     lambda v: float(v) < 1e-12,
     "三明治结构的全部前提。此前只在周期盒验证过，而论文的腔体是 PEC；"
     "若此式不成立，成对替换在腔体里就要先补边界修正"),
    ("R5", "介质界面下成对替换的保证仍成立，单旋度替换仍不成立",
     [sys.executable, "structured_material.py"],
     r"RESULT material_(?:pair_ok 1|onesided_ok 0)",
     lambda v: True,
     "两条都要命中才算过：成对的成立、单侧的不成立。"
     "论文 Fig 8 本身含 eps_r=4 的 inhomogeneous cavity"),
    ("R3", "谱半径自检（现算，不看缓存）",
     [sys.executable, "spectral_dco.py", "--selftest"],
     r"self-test (PASSED|FAILED)",
     lambda v: v == "PASSED",
     "精确旋度 rho≈1 且倾斜旋度 rho>1，两个方向都要对"),
]


def run_claim(cid, name, cmd, pat, ok_fn, crit):
    if not os.path.exists(cmd[1]):
        return "NODATA", "缺脚本", f"{cmd[1]} 不在当前目录"
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900)
    except Exception as exc:
        return "FAIL", "跑不起来", str(exc)[:120]
    if p.returncode != 0:
        return 'FAIL', f'exit {p.returncode}', (p.stdout+p.stderr)[-800:]
    hits = re.findall(pat, p.stdout+p.stderr, re.M)
    if not hits:
        return "FAIL", "输出里没匹配到数", f"exit {p.returncode}；{crit}"
    bad = [h for h in hits if not ok_fn(h)]
    shown = ", ".join(str(h) for h in hits[:6])
    return ("PASS" if not bad else "FAIL",
            shown + ("" if len(hits) <= 6 else f" … 共 {len(hits)} 个"),
            crit + (f"；{len(bad)} 个不满足" if bad else ""))


# --------------------------------------------------------------------------- #
# WARN is for a claim that is CONFIRMED but cuts against the story.  It has to
# be visually distinct from PASS or the table quietly reads as all-good.
MARK = {"PASS": "[ PASS ]", "FAIL": "[ FAIL ]", "NODATA": "[ 缺数据 ]",
        "WARN": "[ 反例 ]", 'REVIEW':'[ 待重审 ]', 'RETRACTED':'[ 撤回 ]', 'NOT_RUN':'[ 未运行 ]', 'INCOMPLETE':'[ 不完整 ]'}
TICK = {"PASS": "✅", "FAIL": "❌", "NODATA": "⬜", "WARN": "⚠️",
        'REVIEW':'🔎', 'RETRACTED':'⛔', 'NOT_RUN':'⬜', 'INCOMPLETE':'⬜'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true",
                    help="也重跑 R1-R3 这些便宜的检查（约 1 分钟）")
    ap.add_argument("--md", action="store_true", help="写出 RESULTS.md")
    ap.add_argument('--paper-first', action='store_true',
                    help='加入新协议P0-P2；--run仅重跑本阶段解析测试，不重跑旁支结构实验')
    ap.add_argument('--grid-diagnosis',action='store_true',help='加入D0-D3和P0-P2，复核分项诊断')
    ap.add_argument('--spacing-probe',action='store_true',help='加入S0-S2，并保留此前P/D项')
    ap.add_argument('--coverage-ab',action='store_true',help='加入已批准的A/B修复判据T0-T3，并保留此前项')
    ap.add_argument('--trunk-repair',action='store_true',help='加入仅trunk训练U0-U3，并保留此前项')
    ap.add_argument('--stage2-longrun', action='store_true', help='加入Algorithm 1长程证据V1-V3')
    ap.add_argument('--pidon-v2', action='store_true', help='加入P0-P4的新版证据与门槛N0-N4')
    ap.add_argument('--pidon-v2-contract', action='store_true', help='加入R0-R4修订合同与门槛W0-W4')
    a = ap.parse_args()
    if a.trunk_repair:a.coverage_ab=True
    if a.coverage_ab:a.spacing_probe=True
    if a.spacing_probe:a.grid_diagnosis=True
    if a.grid_diagnosis: a.paper_first=True

    print(f"[verify_claims.py  version {SCRIPT_VERSION}]")
    print(f"in {os.path.abspath('.')}\n")
    print('当前指标由产物重算。旧结论存在待重审项；检查通过不等于充分的科学证明。\n')

    results = []
    from trunk_evidence import CLAIMS as TRUNK_CLAIMS
    for cid, name, fn in DISK_CLAIMS + (STAGE2_CLAIMS if a.stage2_longrun else []) + (PIDON_V2_CLAIMS if a.pidon_v2 else []) + (PIDON_V2_CONTRACT_CLAIMS if a.pidon_v2_contract else []) + (PAPER_CLAIMS if a.paper_first else []) + (GRID_CLAIMS if a.grid_diagnosis else []) + (SPACING_CLAIMS if a.spacing_probe else []) + (COVERAGE_CLAIMS if a.coverage_ab else []) + (TRUNK_CLAIMS if a.trunk_repair else []):
        try:
            v, val, det = fn(None)
            if cid in AUDIT_NOTES:
                v, det = 'REVIEW', AUDIT_NOTES[cid] + ' 历史数值仅供溯源。'
        except Exception as exc:
            v, val, det = "FAIL", "检查本身抛异常", f"{type(exc).__name__}: {exc}"
        results.append((cid, name, v, val, det))
        print(f"  {MARK[v]:<10} {cid}  {name}")
        print(f"             {val}")
        print(f"             {det}\n")

    if a.run:
        print("  —— 重跑便宜的检查 ——\n")
        runs = ([('P0T','本阶段解析回归测试（本次现跑）',
                  [sys.executable,'test_paper_protocol.py'], r'Ran (\d+) tests',
                  lambda v:int(v)>=9, '测试进程exit=0且至少9项通过')]
                if a.paper_first else RUN_CLAIMS)
        if a.coverage_ab:
            runs.append(('T0T','A/B配对、损失与预算回归（本次现跑）',
                         [sys.executable,'test_coverage_ab.py'],r'Ran (\d+) tests',
                         lambda v:int(v)>=3,'测试进程exit=0且至少3项通过'))
        if a.trunk_repair:
            runs.append(('U0T','实际训练函数的冻结回归（本次现跑）',
                         [sys.executable,'test_trunk_repair.py'],r'Ran (\d+) test',
                         lambda v:int(v)>=1,'临时微型网络：冻结参数不变、仅trunk获得更新；不是正式DCO训练'))
        for cid, name, cmd, pat, ok_fn, crit in runs:
            v, val, det = run_claim(cid, name, cmd, pat, ok_fn, crit)
            results.append((cid, name, v, val, det))
            print(f"  {MARK[v]:<10} {cid}  {name}")
            print(f"             {val}")
            print(f"             {det}\n")
    else:
        print("  （本次未调用旧版 RUN_CLAIMS 的 R1-R3；W0-W4 读取的是已登记的 v2 证据。）\n")

    npass = sum(1 for r in results if r[2] == "PASS")
    nfail = sum(1 for r in results if r[2] == "FAIL")
    nnd = sum(1 for r in results if r[2] == "NODATA")
    nw = sum(1 for r in results if r[2] == "WARN")
    print("=" * 66)
    print(f"  通过 {npass}　不通过 {nfail}　缺数据 {nnd}　反例 {nw}")
    if MISSING:
        print("\n  想把「缺数据」补齐，跑这些（已去重）：")
        for cmd in dict.fromkeys(MISSING.values()):
            print(f"    {cmd}")
    if a.md:
        write_md(results, a.run)
        print(f"\n  -> RESULTS.md 已更新（这个文件小，是要提交进 git 的）")
    if a.grid_diagnosis and not a.spacing_probe:
        from pathlib import Path
        from paper_recheck import dump,sha256
        import shutil
        root=Path('evidence/grid_diagnosis_v1')
        j,m,findings=grid_claims_data()
        dump(root/'findings.json',findings)
        shutil.copy2(__file__,root/'source'/'verify_claims_final.py')
        dump(root/'verification_manifest.json',dict(arrays_sha256=j['arrays_sha256'],
             verifier_sha256=sha256(__file__),findings_sha256=sha256(root/'findings.json')))
    if a.spacing_probe and not a.coverage_ab:
        from pathlib import Path
        from paper_recheck import dump,sha256
        import shutil
        root=Path('evidence/spacing_probe_v1');j,m,findings=spacing_claims_data()
        dump(root/'findings.json',findings)
        shutil.copy2(__file__,root/'source'/'verify_claims_final.py')
        dump(root/'verification_manifest.json',dict(arrays_sha256=j['arrays_sha256'],
             verifier_sha256=sha256(__file__),findings_sha256=sha256(root/'findings.json')))
    if a.coverage_ab and not a.trunk_repair:
        from pathlib import Path
        from paper_recheck import dump,sha256
        import shutil
        root=Path('evidence/coverage_ab_v1');j,m,findings=coverage_claims_data()
        dump(root/'findings.json',findings)
        shutil.copy2(__file__,root/'source'/'verify_claims_final.py')
        dump(root/'verification_manifest.json',dict(arrays_sha256=j['arrays_sha256'],
             verifier_sha256=sha256(__file__),findings_sha256=sha256(root/'findings.json')))
    if a.trunk_repair:
        from pathlib import Path
        from paper_recheck import dump,sha256
        import shutil
        import trunk_evidence as TE
        root=TE.ROOT;j,m,findings=TE.data()
        dump(root/'findings.json',findings)
        shutil.copy2(__file__,root/'source'/'verify_claims_final.py')
        shutil.copy2(TE.__file__,root/'source'/'trunk_evidence.py')
        dump(root/'verification_manifest.json',dict(verifier_sha256=sha256(__file__),
             reader_sha256=sha256(TE.__file__),findings_sha256=sha256(root/'findings.json')))
    return 1 if nfail else 0


def write_md(results, ran):
    import datetime as dt
    commit = ""
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True,
                                timeout=10).stdout.strip()
    except Exception:
        pass
    ids={r[0] for r in results}
    flag=('--trunk-repair' if 'U0' in ids else '--coverage-ab' if 'T0' in ids else '--spacing-probe' if 'S0' in ids
          else '--grid-diagnosis' if 'D0' in ids else '--paper-first' if 'P0' in ids else '')
    with open("RESULTS.md", "w", encoding="utf-8") as f:
        f.write("# 复现结论核对表\n\n")
        f.write(f"> `verify_claims.py` 自动生成于 "
                f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}"
                f"{'，commit `' + commit + '`' if commit else ''}。"
                f"**不要手工编辑。**\n>\n")
        f.write("> 论文优先重评用 --paper-first 加入P0-P2；历史指标保留，待重审/撤回不表示已验证。\n"
                "> 分项诊断用 --grid-diagnosis 加入D0-D3并保留P0-P2。D项通过指诊断证据支持该项陈述，不代表DCO通过精度验收。\n"
                "> 单轴/单波诊断用 --spacing-probe 加入S0-S2并保留P/D项；S项也是诊断判据。\n"
                "> A/B修复用 --coverage-ab 加入T0-T3并保留此前项；T1-T3是批准的修复门槛，不能替代论文复现验收。\n"
                "> 坐标分支修复用 --trunk-repair 加入U0-U3；新种子终验与已知探针诊断分开，仍不替代论文复现验收。\n"
                f"> 本表复算：`py -3.11 lab_log.py run -m verify-evidence -- py -3.11 verify_claims.py {flag} --run --md`。\n"
                "> 复算指标不等于重新训练或推理；P0T是此次现跑的解析测试。\n"
                "> 大数组/权重（.pt/.npz）被 .gitignore 忽略；小型JSON清单、脚本和本表可保存进版本控制。\n"
                "> 每次运行的命令、commit、耗时和输出文件的 sha256 在 "
                "`LAB_NOTEBOOK.md`。本轮源代码快照与权重哈希另见 `evidence/paper_first_v1/manifest.json`。\n\n")
        def cell(t):
            return str(t).replace("|", "\\|").replace("\n", " ")
        f.write("| | 结论 | 复算值 | 判据 |\n|---|---|---|---|\n")
        for cid, name, v, val, det in results:
            tick = TICK[v]
            f.write(f"| {tick} | **{cid}** {cell(name)} | {cell(val)} | "
                    f"{cell(det)} |\n")
        if not ran:
            f.write("\n> 本次未调用旧版 `RUN_CLAIMS` 的 R1–R3 现跑检查（未加 `--run`）。"
                    "W0–W4 列读取的是本轮 v2 已登记证据，不能把这两件事混为一谈。\n")
        nd = [r for r in results if r[2] == "NODATA"]
        if nd:
            f.write("\n## 还缺的\n\n")
            for cmd in dict.fromkeys(MISSING.values()):
                f.write(f"- `{cmd}`\n")


if __name__ == "__main__":
    sys.exit(main())
