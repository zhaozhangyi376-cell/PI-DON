"""Registered N3 fixed-state evaluation for head_lstsq_once_adam499 only."""
from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import hashlib
import json
import math
import os
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

from night_budget import NightPaths, append_ledger, assert_can_start, assert_task_budget, stable_task_id
from pidon_contract import SOURCE_OUTSIDE_PROBES_CELLS, six_component_metrics, trilinear_sample
from pidon_recording import sha256_file, source_hashes
from pidon_solve import Solver, to_t
from r4_fixed_state import fixed_pairs

ROOT = PROJECT_ROOT
MASTER = ROOT / "dco_lr1e3_300.pt"
MASTER_HASH = "3f259bc887a10fac77f6bdf77b43ba1ad6b45827a3f8b9bd685934acc47ca5d7"


def safe(value):
    if isinstance(value, dict): return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [safe(v) for v in value]
    if isinstance(value, (float, np.floating)): return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, (np.integer,)): return int(value)
    return value


def tensor_hash(parts) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def args_for(seed: int) -> SimpleNamespace:
    return SimpleNamespace(n=31, side=.05, dt=3.075e-12, init=str(MASTER), coords="cellsize", norm="rms",
        levels=4, base=32, lr=3e-4, separate_nets=True, reset_opt_each_step=False, grad_clip=0.0,
        h_scale=1.0, h_output_scale=1.0, h_shift=True, tol=1e-4, tol_mode="rel", component_rel=False,
        max_inner=499, inner_time_budget_s=360.0, strict_stop=True, lbfgs_closures=0, lbfgs_lr=1.0,
        lbfgs_history=10, lbfgs_time_budget_s=0.0, fmax=15e9, seed=seed, torch_dtype="float32",
        source_mode="hard", head_lstsq_once=True, head_rcond=1e-12)


def set_state(solver, fields):
    solver.E = [to_t(fields[name], solver.dev, solver.dtype) for name in ("Ex", "Ey", "Ez")]
    solver.H = [to_t(fields[name], solver.dev, solver.dtype) for name in ("Hx", "Hy", "Hz")]


def residual(solver, field, target, which):
    core = solver.extract_input_core(field, which)
    if which == "H": core = core * solver.a.h_scale
    with torch.no_grad(): output = solver.predict(core, which)
    prediction, true = [], []
    for index, item in enumerate(target):
        shape = tuple(min(size, solver.n) for size in item.shape)
        prediction.append(output[index, :shape[0], :shape[1], :shape[2]])
        true.append(item[:shape[0], :shape[1], :shape[2]])
    if which == "H": prediction = [item / solver.a.h_scale / solver.a.h_output_scale for item in prediction]
    sse = float(sum((p - t).pow(2).sum() for p, t in zip(prediction, true)))
    target_ss = float(sum(t.pow(2).sum() for t in true))
    return {"R": sse / target_ss if target_ss else None, "physical_sse": sse,
            "physical_mse": sse / max(sum(t.numel() for t in true), 1), "target_ss": target_ss,
            "target_count": sum(t.numel() for t in true), "prediction": [p.detach().cpu() for p in prediction],
            "target": [t.detach().cpu() for t in true]}


def probes(solver, reference):
    dxyz = (solver.cav.dx, solver.cav.dy, solver.cav.dz); ref = to_t(reference["Ez"], solver.dev, solver.dtype)
    return [{"cells": cells, "dut_Ez": trilinear_sample(solver.E[2], tuple(c*d for c, d in zip(cells, dxyz)), dxyz, (0,0,.5)),
             "ref_Ez": trilinear_sample(ref, tuple(c*d for c, d in zip(cells, dxyz)), dxyz, (0,0,.5))}
            for cells in SOURCE_OUTSIDE_PROBES_CELLS]


def write_json(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp"); tmp.write_text(json.dumps(safe(value), ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8"); os.replace(tmp,path)


def run(root: Path, *, states=(43,96), device="cuda"):
    night = root; paths = NightPaths(night); manifest=json.loads(paths.manifest.read_text(encoding="utf-8")); assert_can_start(manifest, training=True)
    if sha256_file(MASTER) != MASTER_HASH: raise RuntimeError("registered master weight hash differs")
    g0_path = night / "g0_after_head_integration" / "G0.json"
    if json.loads(g0_path.read_text(encoding="utf-8")).get("G0") != "PASS": raise RuntimeError("final post-integration G0 is not PASS")
    out=night/"n3_fixed"; out.mkdir(exist_ok=False)
    pairs=fixed_pairs(31,.05,3.075e-12,tuple(states)); rows=[]; started=time.perf_counter()
    for step in states:
        pair=pairs[step]; torch.manual_seed(20260913); np.random.seed(20260913); solver=Solver(args_for(20260913),device)
        set_state(solver,pair["before"]); target_h=solver.yee_curl_H(); task_h=stable_task_id(split="development",seed=20260913,source_index=pair["source_index"],phase="H",input_hash=tensor_hash(solver.H),target_hash=tensor_hash(target_h))
        assert_task_budget(paths,task_h,add_head=1,add_solve=3,add_adam=499)
        before_h=residual(solver,solver.H,target_h,"H"); fit_h=solver.inner_train(solver.H,target_h,"H"); after_h=residual(solver,solver.H,target_h,"H")
        row={"step":step,"split":"development","origin":"fixed_reference_state","source_index":pair["source_index"],"source":pair["source"],"accepted_steps":0,"current_time_layer":pair["source_index"],"H":{"task_id":task_h,"initial":before_h,"final":after_h,"fit":fit_h.as_dict(),"progress":solver.fit_progress["H"]},"accepted_field_metrics":None,"source_outside_probes":None,"phase":"before_H","recovery_eligible":solver.fit_progress["H"]["resumable"]}
        payload=solver.state_payload(); payload.update({"fixed_state_step":step,"origin":"fixed_reference_state","fit_input_H":[x.detach().cpu() for x in solver.H],"fit_target_H":[x.detach().cpu() for x in target_h],"row":"H"}); torch.save(payload,out/f"step_{step:04d}_H.pt")
        append_ledger(paths,{"kind":"N3_fixed_H","task_id":task_h,"adam_updates":fit_h.n_updates,"head_commits":solver.fit_progress["H"]["head_commit_count"],"linear_solve_calls":solver.fit_progress["H"]["linear_solve_calls"],"training_s":fit_h.elapsed_s})
        if fit_h.passed:
            solver._update_E_and_source(fit_h.prediction,pair["source"]); target_e=solver.yee_curl_E(); task_e=stable_task_id(split="development",seed=20260913,source_index=pair["source_index"],phase="E",input_hash=tensor_hash(solver.E),target_hash=tensor_hash(target_e)); assert_task_budget(paths,task_e,add_head=1,add_solve=3,add_adam=499)
            before_e=residual(solver,solver.E,target_e,"E"); fit_e=solver.inner_train(solver.E,target_e,"E"); after_e=residual(solver,solver.E,target_e,"E"); row["E"]={"task_id":task_e,"initial":before_e,"final":after_e,"fit":fit_e.as_dict(),"progress":solver.fit_progress["E"]}; append_ledger(paths,{"kind":"N3_fixed_E","task_id":task_e,"adam_updates":fit_e.n_updates,"head_commits":solver.fit_progress["E"]["head_commit_count"],"linear_solve_calls":solver.fit_progress["E"]["linear_solve_calls"],"training_s":fit_e.elapsed_s})
            if fit_e.passed:
                solver._update_H(fit_e.prediction); re=[to_t(pair["after_h"][name],solver.dev,solver.dtype) for name in ("Ex","Ey","Ez")]; rh=[to_t(pair["after_h"][name],solver.dev,solver.dtype) for name in ("Hx","Hy","Hz")]; row["accepted_field_metrics"]=six_component_metrics(solver.E,solver.H,re,rh,(solver.cav.dx,)*3,source_ez_index=(15,15,15)); row["source_outside_probes"]=probes(solver,pair["after_h"]); row["phase"]="completed"; row["recovery_eligible"]=solver.fit_progress["E"]["resumable"]
        else:
            torch.manual_seed(20260913); oracle=Solver(args_for(20260913),device); set_state(oracle,pair["after_e"]); target_oe=oracle.yee_curl_E(); oe_before=residual(oracle,oracle.E,target_oe,"E"); oe_fit=oracle.inner_train(oracle.E,target_oe,"E"); oe_after=residual(oracle,oracle.E,target_oe,"E"); row["oracle_E"]={"classification":"oracle_only_not_G1","phase":"oracle_after_E_source","initial":oe_before,"final":oe_after,"fit":oe_fit.as_dict(),"progress":oracle.fit_progress["E"]}
        row["elapsed_s"]=time.perf_counter()-started; rows.append(row); write_json(out/f"step_{step:04d}.json",row)
    g1=bool(rows) and len(rows)==len(states) and all(r["H"]["fit"]["passed"] and r.get("E",{}).get("fit",{}).get("passed") and r.get("accepted_field_metrics",{}).get("fixed_amplitude_error",float("inf"))<=1e-3 for r in rows)
    result={"schema":"pidon-v4-head-lstsq-fixed-v1","classification":"DCO optimization-variant fixed-state evaluation; not rollout","config":vars(args_for(20260913)),"g0_hash":sha256_file(g0_path),"master_hash":MASTER_HASH,"source_hashes":source_hashes(ROOT),"tasks":rows,"G1_development": "PASS" if g1 else "FAIL","elapsed_s":time.perf_counter()-started}
    write_json(out/"N3_fixed.json",result); report=["# N3 head_lstsq_once_adam499 固定状态", "", f"- G1开发：**{result['G1_development']}**", "- 这是一种新优化规则，不是论文已确认算法。", ""]+[f"- step {r['step']}：H R={r['H']['final']['R']}，H={r['H']['fit']['stop_reason']}，E={r.get('E',{}).get('fit',{}).get('stop_reason','NOT_RUN')}" for r in rows]; (out/"N3_REPORT.md").write_text("\n".join(report)+"\n",encoding="utf-8"); print(json.dumps({"out":str(out),"G1":result["G1_development"],"tasks":len(rows)},ensure_ascii=False)); return result


def main():
    p=argparse.ArgumentParser();p.add_argument("--root",default="evidence/gpt6_plan_v4_night");p.add_argument("--device",default="cuda" if torch.cuda.is_available() else "cpu");a=p.parse_args(); result=run((ROOT/a.root).resolve(),device=a.device); raise SystemExit(0 if result["G1_development"]=="PASS" else 2)
if __name__=="__main__":main()
