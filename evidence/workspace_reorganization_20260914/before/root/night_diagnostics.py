"""N5 no-update diagnostics: frozen feature head bound and label/gradient audit."""
from __future__ import annotations
import argparse, gc, hashlib, json, math, os
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import torch
import dco as D
import head_lstsq
import night_fixed_state as N
from pidon_recording import sha256_file
from pidon_solve import Solver

ROOT=Path(__file__).resolve().parent
OLD=("H_step_0043.pt","E_oracle_step_0043.pt","H_step_0096.pt","E_oracle_step_0096.pt")
def finite(v): return float(v) if math.isfinite(float(v)) else None
def write(path,v):
 t=path.with_suffix(path.suffix+".tmp");t.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8");os.replace(t,path)
def frozen_feature(path):
 p=torch.load(path,map_location="cpu",weights_only=False); role="H" if p["role"]=="H" else "E";a=N.args_for(20260913);s=Solver(a,"cpu");s.net_H.load_state_dict(p["net_H"]);s.net_E.load_state_dict(p["net_E"]);field=[x.to(s.dev) for x in (p["H"] if role=="H" else p["E"])];target=[x.to(s.dev) for x in p["target"]];core=s.extract_input_core(field,role);core=core*s.a.h_scale if role=="H" else core;net=s.net_H if role=="H" else s.net_E;features=[];hook=net.head.register_forward_pre_hook(lambda _m,inputs:features.append(inputs[0].detach().clone()))
 try:
  with torch.no_grad(): old=s.predict(core,role)
 finally: hook.remove()
 sc=s.last_predict_context["input_scale"].reshape(-1)[0];lc=s.last_predict_context["Lc"].reshape(-1)[0];out_scale=s.last_predict_context["out_scale"];norm_targets=[x*lc/(sc*out_scale) for x in target];w,b,diag=head_lstsq.solve_head(features[0][0],norm_targets);old_parts=[];ls_parts=[]
 for k,t in enumerate(target):
  shape=t.shape;f=features[0][0][:,:shape[0],:shape[1],:shape[2]];old_parts.append(old[k,:shape[0],:shape[1],:shape[2]]);ls=(w[k,:,0,0,0].to(f).view(-1,1,1,1)*f).sum(0)+b[k];ls_parts.append(ls*sc*out_scale/lc)
 if role=="H": old_parts=[x/s.a.h_scale/s.a.h_output_scale for x in old_parts];ls_parts=[x/s.a.h_scale/s.a.h_output_scale for x in ls_parts]
 def r(parts):
  ss=float(sum((x-y).pow(2).sum() for x,y in zip(parts,target)));tt=float(sum(y.pow(2).sum() for y in target));return ss/tt if tt else None
 return {"asset":str(path.relative_to(ROOT)).replace("\\","/"),"sha256":sha256_file(path),"role":role,"stored_R":p.get("saved_parameter_R"),"forward_R":r(old_parts),"frozen_feature_lstsq_R":r(ls_parts),"target_energy":[float(x.pow(2).sum()) for x in target],"rank":[d["rank"] for d in diag],"singular_values":[d["singular_values"] for d in diag],"linear_solve_calls":3,"parameter_updates":0}
def label_gradient():
 rows=[]
 for name in ("data_16.npz","data_16_pw.npz","data_32.npz","data_32_pw.npz"):
  p=ROOT/name
  if not p.is_file(): rows.append({"path":name,"status":"MISSING"});continue
  z=np.load(p);rows.append({"path":name,"sha256":sha256_file(p),"keys":{k:{"shape":list(z[k].shape),"dtype":str(z[k].dtype)} for k in z.files},"label_provenance":"INCOMPLETE_no_wavevector_phase_polarization_metadata"})
 torch.manual_seed(20260913);n=7;dmm=torch.tensor([1.,1.,1.],dtype=torch.float64).view(1,3);coords=D.make_coords((n,n,n),dmm[0],"cellsize",dtype=torch.float64);z=torch.arange(n,dtype=torch.float64).view(1,1,1,n);field=torch.zeros((1,3,n,n,n),dtype=torch.float64);field[:,1]=torch.sin(.4*z);target=torch.zeros_like(field);target[:,0]=-.4*torch.cos(.4*z);net=D.DCO(levels=1,base=2).double();output=net(field,coords,D.d_rel_of(dmm,torch.ones((1,1,1,1,1),dtype=torch.float64)));loss=(output-target).square().mean();params=[p for p in net.parameters()];grad=torch.autograd.grad(loss,params);direction=[torch.randn_like(p) for p in params];ad=sum((g*v).sum() for g,v in zip(grad,direction)).item();checks=[]
 with torch.no_grad():
  original=[p.clone() for p in params]
  for eps in (1e-5,5e-6):
   for p,o,v in zip(params,original,direction):p.copy_(o+eps*v)
   plus=(net(field,coords,D.d_rel_of(dmm,torch.ones((1,1,1,1,1),dtype=torch.float64)) )-target).square().mean().item()
   for p,o,v in zip(params,original,direction):p.copy_(o-eps*v)
   minus=(net(field,coords,D.d_rel_of(dmm,torch.ones((1,1,1,1,1),dtype=torch.float64)) )-target).square().mean().item()
   fd=(plus-minus)/(2*eps);checks.append({"epsilon":eps,"autodiff":ad,"central_difference":fd,"abs_difference":abs(fd-ad),"pass":abs(fd-ad)<=1e-7+1e-4*max(abs(fd),abs(ad))})
  for p,o in zip(params,original):p.copy_(o)
 return {"old_label_assets":rows,"analytic_plane_wave":{"n":7,"direction":"z","polarization":"Ey","k":.4,"continuous_curl":"curl_x=-k*cos(kz)","parameter_updates":0},"gradient_direction_checks":checks,"gradient_all_finite":all(torch.isfinite(g).all().item() for g in grad),"parameter_updates":0}

def old_sample_gradients():
 """One real sample per legacy asset; autograd only, never optimizer.step()."""
 device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
 torch.manual_seed(20260913); net=D.DCO(levels=4,base=32).to(device).train(); out=[]
 for name in ("data_16.npz","data_16_pw.npz","data_32.npz","data_32_pw.npz"):
  path=ROOT/name
  if not path.is_file(): out.append({"path":name,"status":"MISSING"});continue
  z=np.load(path); n=int(z["n"]); e=torch.from_numpy(np.array(z["E"][0:1],copy=True)).to(device); c=torch.from_numpy(np.array(z["C"][0:1],copy=True)).to(device); d=torch.from_numpy(np.array(z["D"][0:1],copy=True)*1e3).to(device); x=D.make_coords(n,d[0],"cellsize").to(device)
  eh,ch,_,_=D.normalise(e,c,d,"rms"); pred=net(eh,x); loss=(pred-ch).square().mean(); grads=torch.autograd.grad(loss,tuple(net.parameters()),allow_unused=True)
  layers=[]; zeros=0; total=0; all_finite=True
  for (key,param),g in zip(net.named_parameters(),grads):
   count=param.numel(); total+=count
   if g is None: finite=False; norm=None; zero=count
   else: finite=bool(torch.isfinite(g).all()); norm=float(g.norm().detach().cpu()); zero=int((g==0).sum().detach().cpu())
   all_finite=all_finite and finite; zeros+=zero; layers.append({"name":key,"parameter_count":count,"gradient_finite":finite,"gradient_l2":norm,"zero_gradient_parameter_count":zero})
  out.append({"path":name,"sample_index":0,"grid":n,"loss_name":"normalised_MSE_for_connectivity_diagnostic","loss":float(loss.detach().cpu()),"output_requires_grad":bool(pred.requires_grad),"loss_requires_grad":bool(loss.requires_grad),"all_gradients_finite":all_finite,"zero_gradient_parameter_ratio":zeros/max(total,1),"layers":layers,"parameter_updates":0,"status":"PASS" if all_finite and loss.requires_grad else "FAIL"})
  del z,e,c,d,x,eh,ch,pred,loss,grads;gc.collect()
  if device.type=="cuda": torch.cuda.empty_cache()
 return {"device":str(device),"architecture":"DCO L4/base32 direct head; fresh fixed-seed diagnostic network","samples":out,"parameter_updates":0}
def main():
 p=argparse.ArgumentParser();p.add_argument("--root",default="evidence/gpt6_plan_v4_night");p.add_argument("--attempt",default="attempt02");a=p.parse_args();root=ROOT/a.root;out=root/f"n5_diagnostics_{a.attempt}";out.mkdir(exist_ok=False);features=[frozen_feature(ROOT/"evidence/gpt6_plan_v3/h_layout_candidate"/name) for name in OLD];labels=label_gradient();old_gradients=old_sample_gradients();result={"schema":"pidon-v4-n5-diagnostics-v2","classification":"no_parameter_updates","attempt":a.attempt,"frozen_feature":features,"labels_and_gradients":labels,"old_sample_gradients":old_gradients,"formal_dco_updates":0};write(out/"N5_diagnostics.json",result);lines=["# N5 无更新诊断","", "- 正式DCO参数更新：0", "- 冻结特征 least-squares 仅是当前特征空间的拟合估计，不是完整网络的理论下界。", "- 旧数据缺少可复核的波矢、相位和偏振元数据，标签来源仍为 INCOMPLETE；这与梯度有限性诊断分开。",""]+[f"- {x['asset']}：存储R={x['stored_R']}，冻结特征LS R={x['frozen_feature_lstsq_R']}" for x in features];(out/"N5_REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8");stage=json.loads((root/"stage_status.json").read_text(encoding="utf-8"));stage["N4"]={"implementation":"NOT_RUN","scientific_gate":"NOT_RUN","stop_reason":"G1_development_failed"};stage["N5"]={"implementation":"PASS","scientific_gate":"N/A","evidence":f"n5_diagnostics_{a.attempt}/N5_diagnostics.json"};write(root/"stage_status.json",stage);print(json.dumps({"out":str(out),"diagnostics":len(features),"gradient_pass":all(x['pass'] for x in labels['gradient_direction_checks']),"old_gradient_pass":all(x.get('status')=='PASS' for x in old_gradients['samples'])},ensure_ascii=False))
if __name__=="__main__":main()
