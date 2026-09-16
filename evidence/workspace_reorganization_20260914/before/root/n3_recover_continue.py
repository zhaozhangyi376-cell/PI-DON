"""Continue N3 after the #205 JSON serialization stop without rerunning H43."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch

import night_fixed_state as N
from night_budget import NightPaths, append_ledger, assert_can_start, assert_task_budget, stable_task_id
from pidon_recording import sha256_file, source_hashes
from pidon_solve import Solver, to_t

ROOT=Path(__file__).resolve().parent

def brief(item): return {k:v for k,v in item.items() if k not in ("prediction","target")}

def recovered_h43(root, pair, device):
    payload=torch.load(root/"n3_fixed"/"step_0043_H.pt",map_location="cpu",weights_only=False)
    baseline=Solver(N.args_for(20260913),device); field=[x.to(device) for x in payload["fit_input_H"]]; baseline.H=[x.clone() for x in field]
    initial=brief(N.residual(baseline,field,[x.to(device) for x in payload["fit_target_H"]],"H"))
    solver=Solver(N.args_for(20260913),device); solver.load_state_payload(payload,diagnostic_only=True)
    final=brief(N.residual(solver,field,[x.to(device) for x in payload["fit_target_H"]],"H")); progress=payload["fit_progress"]["H"]
    task=stable_task_id(split="development",seed=20260913,source_index=pair["source_index"],phase="H",input_hash=N.tensor_hash(field),target_hash=N.tensor_hash([x.to(device) for x in payload["fit_target_H"]]))
    return {"step":43,"split":"development","origin":"fixed_reference_state","source_index":pair["source_index"],"source":pair["source"],"accepted_steps":0,"current_time_layer":pair["source_index"],"H":{"task_id":task,"initial":initial,"final":final,"fit":{"n_updates":progress["updates"],"head_commit_count":progress["head_commit_count"],"linear_solve_calls":progress["linear_solve_calls"],"stop_reason":progress["stop_reason"],"passed":False,"recovered_from":"step_0043_H.pt"},"progress":progress},"accepted_field_metrics":None,"source_outside_probes":None,"phase":"before_H","recovery_eligible":False,"stop_reason":"max_updates"}

def oracle(root, pair, step, device):
    torch.manual_seed(20260913); np.random.seed(20260913); solver=Solver(N.args_for(20260913),device); N.set_state(solver,pair["after_e"]); target=solver.yee_curl_E(); task=stable_task_id(split="development",seed=20260913,source_index=pair["source_index"],phase="E_oracle",input_hash=N.tensor_hash(solver.E),target_hash=N.tensor_hash(target)); paths=NightPaths(root); assert_task_budget(paths,task,add_head=1,add_solve=3,add_adam=499); initial=brief(N.residual(solver,solver.E,target,"E")); fit=solver.inner_train(solver.E,target,"E"); final=brief(N.residual(solver,solver.E,target,"E")); append_ledger(paths,{"kind":"N3_oracle_E","task_id":task,"adam_updates":fit.n_updates,"head_commits":solver.fit_progress["E"]["head_commit_count"],"linear_solve_calls":solver.fit_progress["E"]["linear_solve_calls"],"training_s":fit.elapsed_s}); payload=solver.state_payload(); payload.update({"fixed_state_step":step,"origin":"oracle_after_E_source","fit_input_E":[x.detach().cpu() for x in solver.E],"fit_target_E":[x.detach().cpu() for x in target]}); torch.save(payload,root/"n3_fixed"/f"step_{step:04d}_E_oracle.pt"); return {"classification":"oracle_only_not_G1","phase":"oracle_after_E_source","task_id":task,"initial":initial,"final":final,"fit":fit.as_dict(),"progress":solver.fit_progress["E"]}

def h96(root,pair,device):
    torch.manual_seed(20260913);np.random.seed(20260913);solver=Solver(N.args_for(20260913),device);N.set_state(solver,pair["before"]);target=solver.yee_curl_H();task=stable_task_id(split="development",seed=20260913,source_index=pair["source_index"],phase="H",input_hash=N.tensor_hash(solver.H),target_hash=N.tensor_hash(target));paths=NightPaths(root);assert_task_budget(paths,task,add_head=1,add_solve=3,add_adam=499);initial=brief(N.residual(solver,solver.H,target,"H"));fit=solver.inner_train(solver.H,target,"H");final=brief(N.residual(solver,solver.H,target,"H"));append_ledger(paths,{"kind":"N3_fixed_H","task_id":task,"adam_updates":fit.n_updates,"head_commits":solver.fit_progress["H"]["head_commit_count"],"linear_solve_calls":solver.fit_progress["H"]["linear_solve_calls"],"training_s":fit.elapsed_s});payload=solver.state_payload();payload.update({"fixed_state_step":96,"origin":"fixed_reference_state","fit_input_H":[x.detach().cpu() for x in solver.H],"fit_target_H":[x.detach().cpu() for x in target]});torch.save(payload,root/"n3_fixed"/"step_0096_H.pt");return {"step":96,"split":"development","origin":"fixed_reference_state","source_index":pair["source_index"],"source":pair["source"],"accepted_steps":0,"current_time_layer":pair["source_index"],"H":{"task_id":task,"initial":initial,"final":final,"fit":fit.as_dict(),"progress":solver.fit_progress["H"]},"accepted_field_metrics":None,"source_outside_probes":None,"phase":"before_H","recovery_eligible":solver.fit_progress["H"]["resumable"],"stop_reason":fit.stop_reason},solver

def main():
    root=ROOT/"evidence/gpt6_plan_v4_night"; assert_can_start(json.loads((root/"night_manifest.json").read_text(encoding="utf-8")),training=True); pairs=N.fixed_pairs(31,.05,3.075e-12,(43,96));device="cuda" if torch.cuda.is_available() else "cpu";started=time.perf_counter();r43=recovered_h43(root,pairs[43],device);r43["oracle_E"]=oracle(root,pairs[43],43,device);r96,_=h96(root,pairs[96],device);r96["oracle_E"]=oracle(root,pairs[96],96,device);rows=[r43,r96];result={"schema":"pidon-v4-head-lstsq-fixed-v1","classification":"DCO optimization-variant fixed-state evaluation; not rollout","recovery_note":"#205 report serialization stop; H43 checkpoint remeasured without update, not rerun","g0_hash":sha256_file(root/"g0_after_head_integration"/"G0.json"),"master_hash":N.MASTER_HASH,"source_hashes":source_hashes(ROOT),"tasks":rows,"G1_development":"FAIL","elapsed_s":time.perf_counter()-started};N.write_json(root/"n3_fixed"/"N3_fixed.json",result);lines=["# N3 head_lstsq_once_adam499 固定状态报告","", "- G1开发：**FAIL**（两开发状态未全部通过；六验证与连续轨迹均不启动）。","- #205 在H43完成后仅报告JSON序列化失败；H43未重跑，已从完整检查点无更新重测。",""]+[f"- step {r['step']}：H R={r['H']['final']['R']}，H={r['H']['fit']['stop_reason']}；oracle E R={r['oracle_E']['final']['R']}（不计G1）。" for r in rows];(root/"n3_fixed"/"N3_REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8");stage=json.loads((root/"stage_status.json").read_text(encoding="utf-8"));stage["N3"]={"implementation":"PASS","scientific_gate":"FAIL","lab_run_id":None,"evidence":"n3_fixed/N3_fixed.json","stop_reason":"G1_development_failed"};N.write_json(root/"stage_status.json",stage);print(json.dumps({"out":str(root/"n3_fixed"/"N3_fixed.json"),"G1":"FAIL","h43_R":r43['H']['final']['R'],"h96_R":r96['H']['final']['R']},ensure_ascii=False))
if __name__=="__main__":main()
