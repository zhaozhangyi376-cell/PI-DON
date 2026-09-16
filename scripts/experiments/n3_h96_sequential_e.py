"""Run the registered sequential E96 fit from saved, passing H96 state only."""
from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

import json, time
from pathlib import Path
import torch
import night_fixed_state as N
from night_budget import NightPaths, append_ledger, assert_can_start, assert_task_budget, stable_task_id
from pidon_contract import six_component_metrics
from pidon_recording import sha256_file
from pidon_solve import Solver, to_t

ROOT=PROJECT_ROOT
def brief(x): return {k:v for k,v in x.items() if k not in ("prediction","target")}
def main():
 root=ROOT/"evidence/gpt6_plan_v4_night";paths=NightPaths(root);assert_can_start(json.loads(paths.manifest.read_text(encoding="utf-8")),training=True);out=root/"n3_fixed";payload=torch.load(out/"step_0096_H.pt",map_location="cpu",weights_only=False);solver=Solver(N.args_for(20260913),"cuda" if torch.cuda.is_available() else "cpu");solver.load_state_payload(payload,diagnostic_only=True);pair=N.fixed_pairs(31,.05,3.075e-12,(96,))[96];field_h=[x.to(solver.dev) for x in payload["fit_input_H"]];target_h=[x.to(solver.dev) for x in payload["fit_target_H"]];h=N.residual(solver,field_h,target_h,"H");
 if not h["R"] < 1e-4: raise RuntimeError(f"saved H96 no longer passes disk remeasure: {h['R']}")
 solver._update_E_and_source(h["prediction"],pair["source"]);target=solver.yee_curl_E();task=stable_task_id(split="development",seed=20260913,source_index=pair["source_index"],phase="E",input_hash=N.tensor_hash(solver.E),target_hash=N.tensor_hash(target));assert_task_budget(paths,task,add_head=1,add_solve=3,add_adam=499);started=time.perf_counter();before=brief(N.residual(solver,solver.E,target,"E"));fit=solver.inner_train(solver.E,target,"E");after=brief(N.residual(solver,solver.E,target,"E"));progress=solver.fit_progress["E"];append_ledger(paths,{"kind":"N3_fixed_E_sequential","task_id":task,"adam_updates":fit.n_updates,"head_commits":progress["head_commit_count"],"linear_solve_calls":progress["linear_solve_calls"],"training_s":fit.elapsed_s});row={"task_id":task,"phase":"E_pending_after_passing_H96","initial":before,"final":after,"fit":fit.as_dict(),"progress":progress,"elapsed_s":time.perf_counter()-started};state=solver.state_payload();state.update({"fixed_state_step":96,"origin":"fixed_reference_state_sequential_after_H96","fit_input_E":[x.detach().cpu() for x in solver.E],"fit_target_E":[x.detach().cpu() for x in target]});torch.save(state,out/"step_0096_E_sequential.pt");
 if fit.passed:
  solver._update_H(fit.prediction);re=[to_t(pair["after_h"][n],solver.dev,solver.dtype) for n in ("Ex","Ey","Ez")];rh=[to_t(pair["after_h"][n],solver.dev,solver.dtype) for n in ("Hx","Hy","Hz")];row["accepted_field_metrics"]=six_component_metrics(solver.E,solver.H,re,rh,(solver.cav.dx,)*3,source_ez_index=(15,15,15));row["source_outside_probes"]=N.probes(solver,pair["after_h"]);row["phase"]="completed"
 result=json.loads((out/"N3_fixed.json").read_text(encoding="utf-8"));task96=next(x for x in result["tasks"] if x["step"]==96);task96["E_sequential_registered"]=row;task96["unplanned_E_oracle_excluded"]={"path":"step_0096_E_oracle.pt","reason":"script flow defect; not a registered oracle because H96 passed; excluded from G1"};result["G1_development"]="FAIL";result["stop_reason"]="H43_R_above_threshold";N.write_json(out/"N3_fixed.json",result);lines=["# N3 顺序 E96 补充记录","",f"- H96 磁盘重测 R：{h['R']}",f"- E96 顺序 R：{after['R']}",f"- E96 stop：{fit.stop_reason}","- E96 oracle 文件由流程缺陷产生，保留但明确排除，不计任何G1结果。","- G1仍为FAIL，因为H43 R超过门槛。"];(out/"N3_E96_REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8");print(json.dumps({"H96_R_disk":h['R'],"E96_R":after['R'],"E_stop":fit.stop_reason,"E_pass":fit.passed},ensure_ascii=False))
if __name__=="__main__":main()
