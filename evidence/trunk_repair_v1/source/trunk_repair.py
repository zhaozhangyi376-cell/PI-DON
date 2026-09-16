"""Approved C200 experiment: only trunk parameters, same B data and batches."""
import argparse
import copy
import io
import json
from pathlib import Path
import shutil
import unittest
import numpy as np
import torch
import coverage_ab as A
from paper_recheck import dump,sha256

ROOT=Path('evidence/trunk_repair_v1')
OLD=Path('evidence/coverage_ab_v1')
PLAN=OLD/'NEXT_TRUNK_PLAN.md'


def run(device):
    ROOT.mkdir(parents=True,exist_ok=False);(ROOT/'source').mkdir()
    old=json.loads((OLD/'summary.json').read_text(encoding='utf-8'))
    manifest=json.loads((OLD/'manifest.json').read_text(encoding='utf-8'))
    initial=manifest['initial_path'];data_path=OLD/'train_B200.npz'
    assert sha256(initial)==manifest['initial_sha256']
    assert sha256(data_path)==old['data_hashes']['B200']
    assert sha256(OLD/'manifest.json')==old['manifest_sha256']
    for model in old['models']:assert sha256(model['path'])==model['sha256']
    files=['trunk_repair.py','coverage_ab.py','test_trunk_repair.py','test_coverage_ab.py',
           'test_paper_protocol.py','dco.py','gen_data.py','diagnose_grid.py','paper_protocol.py',
           'paper_recheck.py','spacing_probe.py','fdtd.py','lab_log.py']
    hashes={}
    for name in files:
        shutil.copy2(name,ROOT/'source'/name);hashes[name]=sha256(name)
    shutil.copy2(PLAN,ROOT/'source'/'NEXT_TRUNK_PLAN.md');hashes['NEXT_TRUNK_PLAN.md']=sha256(PLAN)
    dump(ROOT/'manifest.json',dict(version='trunk-repair-v1',source_hashes=hashes,
        initial_path=initial,initial_sha256=sha256(initial),data_path=str(data_path),data_sha256=sha256(data_path),
        old_manifest_sha256=sha256(OLD/'manifest.json'),old_summary_sha256=sha256(OLD/'summary.json'),
        batches=manifest['batches'],seed=A.SEED,trainable_prefix='trunk.',updates=200,batch=4,lr=1e-4,
        device=device,torch=torch.__version__,numpy=np.__version__,diagnostic_seeds=[10,11,12],heldout_seeds=[20,21,22],
        criteria=dict(U0='all non-trunk state tensors bitwise unchanged; all and only trunk parameters receive exactly 200 Adam steps; same B data and batch schedule; complete finite evidence',
                      U1='held-out six noncubic cases: geometric means of C200/A200 macro nMAE ratios AND x Eq5 MRE ratios <=0.8',
                      U2='held-out 32^3 three-seed mean macro nMAE: C200/A0 <=1.1',
                      U3='six direction maxima of known coordinate intervention, averaged: C200/A0 <=1.0'),
        limitations=['one optimization seed, 200 updates only','expanded data are a diagnostic enhancement, not strict paper protocol',
                     '10/11/12 and coordinate probes are known diagnostic sets; 20/21/22 evaluated only after training']))
    stream=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromNames(
        ['test_paper_protocol','test_coverage_ab','test_trunk_repair'])
    res=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (ROOT/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
    if not res.wasSuccessful():raise RuntimeError(stream.getvalue())
    torch.manual_seed(A.SEED);torch.set_num_threads(4)
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.allow_tf32=False
    torch.backends.cuda.matmul.allow_tf32=False
    with np.load(data_path,allow_pickle=False) as z:data={k:z[k] for k in ['E','C','D']}
    record=A.train_arm('C200',data,initial,manifest['batches'],ROOT,device,trainable_prefix='trunk.')
    summary=dict(version='trunk-repair-v1',manifest_sha256=sha256(ROOT/'manifest.json'),training=record,
                 tests_passed=True,test_count=res.testsRun)
    dump(ROOT/'training_summary.json',summary)
    del data
    for sub in ['diagnostic','heldout']:(ROOT/sub).mkdir()
    summary['diagnostic']=A.evaluate([copy.deepcopy(record)],ROOT/'diagnostic',device,seeds=(10,11,12))
    models=[copy.deepcopy(v) for v in old['models']]+[copy.deepcopy(record)]
    summary['heldout']=A.evaluate(models,ROOT/'heldout',device,seeds=(20,21,22),include_probes=False)
    assert sha256(initial)==manifest['initial_sha256'] and sha256(data_path)==old['data_hashes']['B200']
    dump(ROOT/'summary.json',summary)
    print('C200 complete: exactly 200 updates; 12 diagnostic + 48 heldout fields, 30 diagnostic probes.')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--device',default='cuda' if torch.cuda.is_available() else 'cpu')
    args=ap.parse_args()
    try:run(args.device)
    except Exception as exc:
        if ROOT.exists() and not (ROOT/'summary.json').exists():
            dump(ROOT/'failure.json',dict(error_type=type(exc).__name__,error=str(exc)))
        raise
