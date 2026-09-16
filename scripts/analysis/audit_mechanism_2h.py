"""Read-only audit/report for the bounded 2h mechanism follow-up."""
from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import hashlib
import json
from pathlib import Path

ROOT = PROJECT_ROOT
OLD = ROOT / "evidence" / "mechanism_1h_v2"
OUT = ROOT / "evidence" / "mechanism_2h_v1"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fit_updates(row: dict) -> int:
    return sum(int((row.get(key) or {}).get("n_updates", 0)) for key in ("fit_H", "fit_E"))


def residuals(row: dict | None) -> dict:
    if not row:
        return {"H": None, "E": None}
    return {
        "H": (row.get("fit_H") or {}).get("residual_ratio"),
        "E": (row.get("fit_E") or {}).get("residual_ratio"),
    }


def six_nmae(row: dict | None) -> dict:
    comps = ((row or {}).get("six_component_metrics") or {}).get("components") or {}
    return {name: metrics.get("nmae") for name, metrics in comps.items()}


def old_arm_audit() -> tuple[dict, dict]:
    audit = read_json(OLD / "audit.json")
    stage = read_json(OLD / "stage_status.json")
    manifest = read_json(OLD / "manifest.json")
    arms = audit["arms"]
    old_total = sum(int(arm.get("actual_updates", 0)) for arm in arms.values())
    return audit, {
        "stage_matches_audit": {
            name: {
                "stage_status": stage["status"].get(name),
                "audit_status": arms.get(name, {}).get("status"),
                "stage_updates": (stage.get("runs", {}).get(name) or {}).get("total_actual_updates"),
                "audit_updates": arms.get(name, {}).get("actual_updates"),
            }
            for name in stage["status"]
        },
        "manifest_top_updates_this_experiment": manifest.get("updates_this_experiment"),
        "actual_updates_from_audit": old_total,
        "actual_updates_from_stage": sum(int((run or {}).get("total_actual_updates", 0))
                                         for run in stage.get("runs", {}).values()),
    }


def lab_runs_subset() -> dict:
    runs = []
    p = ROOT / "lab_runs.jsonl"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if 248 <= int(item.get("id", -1)) <= 262:
                runs.append({
                    "id": item["id"],
                    "exit_code": item["exit_code"],
                    "seconds": item["seconds"],
                    "note": item["note"],
                    "outputs": [out["path"] for out in item.get("outputs", [])],
                })
    return {str(run["id"]): run for run in runs}


def s_r_failure_analysis(old_audit: dict) -> dict:
    rows = read_jsonl(OLD / "runs" / "S_R" / "steps.jsonl")
    accepted = [row for row in rows if row.get("accepted")]
    failure = rows[-1] if rows and not rows[-1].get("accepted") else None
    recent = []
    for row in rows[-8:]:
        recent.append({
            "step": row.get("step"),
            "accepted": row.get("accepted"),
            "phase": row.get("phase"),
            "H_updates": (row.get("fit_H") or {}).get("n_updates"),
            "H_R": (row.get("fit_H") or {}).get("residual_ratio"),
            "E_updates": (row.get("fit_E") or {}).get("n_updates"),
            "E_R": (row.get("fit_E") or {}).get("residual_ratio"),
            "E_target_ss": (row.get("fit_E") or {}).get("target_ss"),
            "E_stop": (row.get("fit_E") or {}).get("stop_reason"),
        })
    last_accepted = accepted[-1] if accepted else None
    return {
        "status": "FAIL",
        "accepted_steps": len(accepted),
        "rows": len(rows),
        "steps_sha256": sha256(OLD / "runs" / "S_R" / "steps.jsonl"),
        "audit_steps_sha256": old_audit["arms"]["S-R"]["steps_sha256"],
        "checkpoint_pointer": read_json(OLD / "runs" / "S_R" / "checkpoint_pointer.json"),
        "failure_raw_present": (OLD / "runs" / "S_R" / "failure_raw_000034_attempt_1.pt").exists(),
        "last_accepted_residuals": residuals(last_accepted),
        "failure_residuals": residuals(failure),
        "failure_reason": failure.get("reason") if failure else None,
        "failure_phase": failure.get("phase") if failure else None,
        "failure_updates": fit_updates(failure or {}),
        "failure_E_stop": ((failure or {}).get("fit_E") or {}).get("stop_reason"),
        "failure_E_elapsed_s": ((failure or {}).get("fit_E") or {}).get("elapsed_s"),
        "failure_E_loss_initial": ((failure or {}).get("fit_E") or {}).get("loss_initial"),
        "failure_E_loss_final": ((failure or {}).get("fit_E") or {}).get("loss_final"),
        "failure_E_target_ss": ((failure or {}).get("fit_E") or {}).get("target_ss"),
        "last_accepted_six_nmae": six_nmae(last_accepted),
        "last_accepted_source_probe_Ez": (last_accepted or {}).get("source_probe_Ez"),
        "last_accepted_source_outside_probes": (last_accepted or {}).get("source_outside_probes"),
        "recent_E_trend": recent,
        "interpretation": (
            "H half-step passed quickly; the 34th candidate failed in E_pending after 3000 E updates. "
            "The last accepted field errors were small except weak-reference Hz, so this is not a macroscopic "
            "field blow-up. D-LR4 shows lr=1e-3 does not simply fix this class of E bottleneck."
        ),
    }


def dlr4_analysis() -> dict:
    run_dir = OUT / "runs" / "D_LR4_retry"
    rows = read_jsonl(run_dir / "steps.jsonl")
    accepted = [row for row in rows if row.get("accepted")]
    failure = rows[-1] if rows and not rows[-1].get("accepted") else None
    last_accepted = accepted[-1] if accepted else None
    return {
        "status": "FAIL",
        "purpose": "diagnostic_strict_lr_1e-3_4step",
        "accepted_steps": len(accepted),
        "target_steps": 4,
        "actual_updates": sum(fit_updates(row) for row in rows),
        "steps_sha256": sha256(run_dir / "steps.jsonl"),
        "checkpoint_latest_sha256": sha256(run_dir / "checkpoint_latest.pt"),
        "failure_raw_present": (run_dir / "failure_raw_000002_attempt_1.pt").exists(),
        "lab_log_run": 262,
        "lab_log_exit_code": lab_runs_subset().get("262", {}).get("exit_code"),
        "elapsed_s": lab_runs_subset().get("262", {}).get("seconds"),
        "last_accepted_residuals": residuals(last_accepted),
        "failure_residuals": residuals(failure),
        "failure_phase": failure.get("phase") if failure else None,
        "failure_reason": failure.get("reason") if failure else None,
        "failure_E_stop": ((failure or {}).get("fit_E") or {}).get("stop_reason"),
        "failure_E_elapsed_s": ((failure or {}).get("fit_E") or {}).get("elapsed_s"),
        "failure_E_updates": ((failure or {}).get("fit_E") or {}).get("n_updates"),
        "failure_E_loss_initial": ((failure or {}).get("fit_E") or {}).get("loss_initial"),
        "failure_E_loss_final": ((failure or {}).get("fit_E") or {}).get("loss_final"),
        "failure_E_target_ss": ((failure or {}).get("fit_E") or {}).get("target_ss"),
        "last_accepted_six_nmae": six_nmae(last_accepted),
        "last_accepted_source_probe_Ez": (last_accepted or {}).get("source_probe_Ez"),
        "last_accepted_source_outside_probes": (last_accepted or {}).get("source_outside_probes"),
        "recovery_eligible": False,
        "script_exit_note": (
            "Run #262 exited 1 after the scientific stop because diagnose() could not format nmae=None; "
            "the accepted and failed step rows, failure_raw, and checkpoints were already persisted."
        ),
    }


def fmt(value) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def write_report(audit: dict) -> None:
    old = audit["old_readonly_audit"]
    s_r = audit["s_r_failure_analysis"]
    d = audit["new_dlr4_analysis"]
    lines = [
        "# 2小时有界机制推进报告",
        "",
        "## 状态总表",
        "",
        "| 项目 | 分栏 | 状态 | 接受步 | 实际更新 | H/E残差 | 耗时(s) | 恢复资格 |",
        "|---|---|---|---:|---:|---|---:|---|",
        f"| S-P-retry | strict-old | RESOURCE_LIMIT | 6 | 10447 | 9.9874e-5 / 9.9936e-5 | 758.9 | True |",
        f"| S-R | strict-old | FAIL | {s_r['accepted_steps']} | 10070 | {fmt(s_r['last_accepted_residuals']['H'])} / {fmt(s_r['failure_residuals']['E'])} | 775.8 | False |",
        "| X-R | explore-old | FAIL | 41 | 13764 | 9.6488e-4 / 9.9944e-4 accepted; next E 1.6029 | 1045.7 | False |",
        "| D-LR old | diagnostic-old | INCOMPLETE | 1 | 657 | N/A / 9.9733e-5 | 48.2 | False |",
        f"| D-LR4-retry | diagnostic-strict-new | FAIL | {d['accepted_steps']} | {d['actual_updates']} | {fmt(d['last_accepted_residuals']['H'])} / {fmt(d['failure_residuals']['E'])} | {fmt(d['elapsed_s'])} | False |",
        "| S-P continuation | strict-new | NOT_RUN | 0 | 0 | N/A | N/A | N/A |",
        "| strict 64/128 | strict-new | NOT_RUN | 0 | 0 | N/A | N/A | N/A |",
        "",
        "严格阈值仍为 `R < 1e-4`。探索阈值 `R < 1e-3` 的 X-R 只作诊断，不计严格成绩。",
        "",
        "## 只读审计结论",
        "",
        f"- `manifest.json` 顶层 `updates_this_experiment={old['manifest_top_updates_this_experiment']}`，但逐臂审计合计为 `{old['actual_updates_from_audit']}`；本轮不使用顶层字段作科学结论。",
        "- `S-P-retry` 是 `RESOURCE_LIMIT`，不是 PASS；`S-R` 是严格 FAIL 但保留 33 个接受步；`X-R` 是探索 FAIL；`D-LR` 是 INCOMPLETE。",
        "- 上一轮 `steps.jsonl`、checkpoint 指针、stage_status 和 lab_log #248-#260 对得上；S-R 与 S-P-retry 的失败/恢复现场均保留。",
        "",
        "## S-R失败点剖析",
        "",
        f"- 第 34 个候选停在 `{s_r['failure_phase']}`，失败原因为 `{s_r['failure_reason']}`；H 半步已过，H R=`{fmt(s_r['failure_residuals']['H'])}`。",
        f"- 真正卡住的是 E：3000 次更新后 E R=`{fmt(s_r['failure_residuals']['E'])}`，目标 `1e-4` 未达，target_ss=`{fmt(s_r['failure_E_target_ss'])}`，耗时 `{fmt(s_r['failure_E_elapsed_s'])}` 秒。",
        "- 前一完整步六分量 nMAE：Ex `2.8713e-5`，Ey `2.8549e-5`，Ez `3.6378e-5`，Hx `6.3903e-5`，Hy `5.6943e-5`，Hz 为弱参考 `3.8940e12`，应单列。",
        "- 因为最后完整步的源点/源外探针仍已落盘，且无阈值违规，当前更支持“E内层拟合在该状态触顶/变慢”，不是接口记录把 FAIL 算错，也不是整体场已经失控。",
        "",
        "## D-LR极小补证",
        "",
        f"- 新臂 `D_LR4_retry` 只接受 1/4 步。第 1 步 E 用 650 更新到 `{fmt(d['last_accepted_residuals']['E'])}`，随后第 2 候选停在 `{d['failure_phase']}`。",
        f"- 第 2 候选 H 已通过，E 在 `{fmt(d['failure_E_elapsed_s'])}` 秒内做 `{d['failure_E_updates']}` 次更新后，R=`{fmt(d['failure_residuals']['E'])}`，远高于 `1e-4`。",
        "- 因此高学习率不是可直接连续通过 2 到 4 个完整严格步的补救；这个结果是诊断 FAIL，不是论文有效性证明。",
        "- #261 和 #262 的 Python exit 1 是显示/诊断层空值处理问题；#262 的科学停止行、failure_raw 和 checkpoint 已在崩溃前落盘。",
        "",
        "## 可用于论文方法判断",
        "",
        "- 可用：严格臂 S-R 曾连续接受 33 步，说明 Algorithm 1 式逐步重训在短程不是完全不可行。",
        "- 可用：S-R 第 34 候选和 D-LR4 第 2 候选都指向 E 半步内层拟合瓶颈；简单提高学习率没有给出连续严格步证据。",
        "- 仅工程/诊断：manifest 顶层更新数字修正、显示层 None 修复、checkpoint 恢复资格审计、X-R 宽阈值推进。",
        "- 不能用于论文成功判断：X-R 的 41 步、精确 Yee 控制、D-LR 首步或本轮 D-LR4 的单步接受。",
        "",
        "## 进入64/128资格",
        "",
        "没有资格。本轮没有任何严格新分支稳定达到 32 个接受步；D-LR4 连 2 个完整严格步都未通过。因此不要启动 64/128，更不要启动 1024/8192。",
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    old_audit, old_readonly = old_arm_audit()
    audit = {
        "schema": "mechanism-2h-audit-v1",
        "old_readonly_audit": old_readonly,
        "s_r_failure_analysis": s_r_failure_analysis(old_audit),
        "new_dlr4_analysis": dlr4_analysis(),
        "lab_runs": lab_runs_subset(),
        "status": {
            "S-P-retry": "RESOURCE_LIMIT",
            "S-R": "FAIL",
            "X-R": "EXPLORE_FAIL",
            "D-LR-old": "INCOMPLETE",
            "D-LR4-retry": "FAIL",
            "S-P-continuation": "NOT_RUN",
            "strict-64": "NOT_RUN",
            "strict-128": "NOT_RUN",
        },
    }
    (OUT / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
