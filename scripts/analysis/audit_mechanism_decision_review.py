"""No-training audit. Preserve all v1 outputs; independently recompute metrics."""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
import dco as D
import mechanism_decision_eval as E
import mechanism_first_failure as F
import pidon_solve as S

ROOT = PROJECT_ROOT
OLD = ROOT / 'evidence/mechanism_decision_v1'
OUT = ROOT / 'evidence/mechanism_decision_v1_review'

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def main():
    OUT.mkdir(exist_ok=True)
    dst = OUT / 'audit.json'
    if dst.exists(): raise FileExistsError(dst)
    old = read(OLD/'phase1_raw.json'); protocol = read(OLD/'protocol.json')
    paths = [OLD/'protocol.json', OLD/'phase1_raw.json', OLD/'runs/P/failure_raw_000001_attempt_1.pt',
             OLD/'runs/P/steps.jsonl', OLD/'runs/R/steps.jsonl', ROOT/protocol['master']['path']]
    before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    ck = torch.load(ROOT/protocol['master']['path'], map_location=dev, weights_only=False)
    net = D.DCO(levels=ck['levels'], base=ck['base'], head=ck.get('head','direct')).to(dev).eval()
    net.load_state_dict(ck['state'])
    rows = []
    for spec in old['specs']:
        inp, true, h = E.sample_spec(spec,(32,32,32),.0192)
        pred,_ = E.predict(net,inp,h,dev)
        p,t = pred[:,:-1,:-1,:-1],true[:,:-1,:-1,:-1]
        err = p-t
        peaks=np.max(np.abs(t),axis=(1,2,3))
        mae=np.mean(np.abs(err),axis=(1,2,3))
        nmae=mae/peaks
        orig=next(r for r in old['master_rows'] if r['group']=='cube32' and r['sample_id']==spec['sample_id'])
        rows.append({'sample_id':spec['sample_id'],'macro_nmae':float(nmae.mean()),
                     'global_rel_l2':float(np.linalg.norm(err.ravel())/np.linalg.norm(t.ravel())),
                     'component_nmae':nmae.tolist(),'component_target_peak':peaks.tolist(),
                     'component_mae':mae.tolist(),
                     'macro_difference_from_original':float(nmae.mean()-orig['dco']['macro_nmae'])})
    spec=old['specs'][0]
    first=dict(spec,k_rad_per_m=spec['k_rad_per_m'][:1],amplitude=spec['amplitude'][:1],phase_rad=spec['phase_rad'][:1])
    second=dict(spec,k_rad_per_m=spec['k_rad_per_m'][1:2],amplitude=spec['amplitude'][1:2],phase_rad=spec['phase_rad'][1:2])
    a,_,h=E.sample_spec(first,(32,32,32),.0192); b,_,_=E.sample_spec(second,(32,32,32),.0192)
    pa,_=E.predict(net,a,h,dev); pb,_=E.predict(net,b,h,dev); pab,_=E.predict(net,a+b,h,dev)
    sl=(slice(None),slice(None,-1),slice(None,-1),slice(None,-1))
    correct=float(np.linalg.norm((pab-pa-pb)[sl].ravel())/np.linalg.norm(pab[sl].ravel()))
    full,_=E.predict(net,E.sample_spec(spec,(32,32,32),.0192)[0],h,dev)
    wrong=float(np.linalg.norm((full-pa-pb).ravel())/np.linalg.norm(full.ravel()))
    p_rows=[json.loads(l) for l in (OLD/'runs/P/steps.jsonl').read_text().splitlines()]
    r_rows=[json.loads(l) for l in (OLD/'runs/R/steps.jsonl').read_text().splitlines()]
    meta=read(OLD/'runs/P/run_metadata.json')
    sol=S.Solver(argparse.Namespace(**meta['config']),dev)
    payload=torch.load(OLD/'runs/P/failure_raw_000001_attempt_1.pt',map_location='cpu',weights_only=False)
    sol.load_state_payload(payload,diagnostic_only=True)
    pred,tgt,planes=F.core_target(sol)
    sse=sum(float(np.square((p.detach().cpu().double().numpy()-t.detach().cpu().double().numpy())).sum()) for p,t in zip(pred,tgt))
    ss=sum(float(np.square(t.detach().cpu().double().numpy()).sum()) for t in tgt)
    pr=sse/ss
    fit0=p_rows[0]['fit_E']; fitr=r_rows[0]['fit_E']
    psafe=not p_rows[0]['accepted'] and p_rows[0]['accepted_steps']==0
    rchecks=[]
    for i,r in enumerate(r_rows):
        fits=[]
        for label in ['H','E']:
            f=r['fit_'+label]
            ok=(f['sse']==0 if f['target_ss']==0 else f['sse']/f['target_ss']<1e-4)
            fits.append(ok and f['n_updates']<=500 and f['elapsed_s']<=360)
        rchecks.append(r['step']==i and r['accepted_steps']==i+1 and r['accepted'] and all(fits))
    after={str(p.relative_to(ROOT)):sha(p) for p in paths}
    ledger=[json.loads(l) for l in (ROOT/'lab_runs.jsonl').read_text(encoding='utf-8').splitlines()]
    total=sum(x['seconds'] for x in ledger if 223<=x['id']<=244)
    train=[{k:x[k] for k in ('id','seconds','exit_code','cmd')} for x in ledger if x['id'] in [233,234]]
    result={'schema':'mechanism-decision-review-v1','optimizer_updates_this_audit':0,'device':dev,
        'original_evidence_hashes':before,'original_evidence_unchanged':before==after,
        'master_matches_protocol':sha(ROOT/protocol['master']['path'])==protocol['master']['sha256'],
        'core_source_matches_protocol':{k:sha(ROOT/k)==v for k,v in protocol['source_hashes'].items()},
        'cube32_recomputed':rows,'cube32_original_gate_passes':sum(r['macro_nmae']<=.01 for r in rows),
        'cube32_max_macro':max(r['macro_nmae'] for r in rows),
        'cube32_L2_p90':float(np.quantile([r['global_rel_l2'] for r in rows],.9)),
        'superposition':{'original_wrong_test_recomputed':wrong,'correct_two_input_common_ROI':correct,
                        'reason':'original subtracts two waves from prediction of all waves; not a linearity test'},
        'P':{'R_disk_float64_accumulation':pr,'R_recorded':fit0['residual_ratio'],
             'actual_updates':fit0['n_updates'],'failed_without_advancing':psafe,
             'initial_SSE_reconstructed':fit0['loss_initial']*fit0['target_ss'],
             'final_physical_SSE':sse,'target_SS':ss,'PEC_planes':planes,
             'R_400':next(x['loss'] for x in p_rows[0]['fit_traces']['E'] if x['updates']==400),
             'R_500':fit0['residual_ratio']},
        'R_partial':{'saved_rows':len(r_rows),'row_numeric_checks':rchecks,
                     'saved_update_count':sum(r['fit_H']['n_updates']+r['fit_E']['n_updates'] for r in r_rows),
                     'unsaved_tail_updates':'UNKNOWN; process killed between persisted rows',
                     'first_E_updates':fitr['n_updates'],'first_E_R':fitr['sse']/fitr['target_ss'],
                     'last_six_component_metrics':r_rows[-1]['six_component_metrics'],
                     'last_source_outside_probes':r_rows[-1]['source_outside_probes'],
                     'checkpoint_files':[p.name for p in (OLD/'runs/R').glob('*.pt')]},
        'recorded_run_wall_seconds_223_to_244':total,'training_runs':train,
        'limits':['Correct superposition is one diagnostic example, not a general linearity bound.',
                  'Pure forward readback verifies these weights under this implementation, not every interface.',
                  'Saved R first-step comparison valid as local observation; B trajectory benefit unmeasured.'],
        'audit_script_sha256':sha(__file__)}
    dst.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['original_evidence_unchanged','master_matches_protocol','cube32_original_gate_passes','cube32_max_macro','cube32_L2_p90','superposition','P','recorded_run_wall_seconds_223_to_244','training_runs']},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
