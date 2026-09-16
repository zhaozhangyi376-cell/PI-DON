"""Generate the Chinese N6 handoff from the single night_evidence reader."""
from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import datetime as dt
import json
from pathlib import Path

import matplotlib.pyplot as plt

import night_evidence
import night_fixed_state as fixed

ROOT = PROJECT_ROOT


def dump(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def make_figures(root: Path, evidence: dict) -> list[str]:
    figures = root / "figs"; figures.mkdir(exist_ok=True)
    rows = evidence["N3"]["registered_rows"]
    fig, ax = plt.subplots(figsize=(8, 4.5), layout="constrained")
    # Matplotlib's bundled DejaVu font lacks CJK glyphs on this host.  Keep
    # these numeric evidence labels ASCII so the saved figure is legible; the
    # Chinese interpretation remains in FINAL_REPORT.md.
    labels = ["H43", "H96", "E96 sequential"]
    values = [item["R_disk"] for item in rows]
    colors = ["#c94c4c" if item["status"] == "FAIL" else "#3b8c5a" for item in rows]
    bars = ax.bar(labels, values, color=colors)
    ax.axhline(evidence["N3"]["threshold_R_strict"], color="black", linestyle="--", linewidth=1,
               label="G1 R < 1e-4")
    ax.set_yscale("log"); ax.set_ylabel("Disk-recomputed physical R (log scale)")
    ax.set_title("N3 registered candidate: fixed-state gate")
    ax.set_ylim(8.5e-5, 1.75e-4)
    for bar, value in zip(bars, values):
        ax.annotate(f"{value:.3e}", (bar.get_x() + bar.get_width()/2, value),
                    xytext=(0, 6), textcoords="offset points", ha="center", fontsize=9)
    ax.legend(loc="upper right")
    path = figures / "n3_registered_disk_residuals_v3.png"; fig.savefig(path, dpi=180); plt.close(fig)
    return [str(path.relative_to(ROOT)).replace("\\", "/")]


def markdown(e: dict, figs: list[str]) -> str:
    rows = e["N3"]["registered_rows"]
    n5 = e["N5"]
    g0 = e["G0"]
    resource = e["resource"]
    lines = [
        "# PI-DON 10 小时夜间执行：N6 验收报告",
        "",
        "## 可直接验收的结论",
        "",
        f"本夜有限目标的证据包已完成，但论文第二阶段**未复现**：G0={e['gates']['G0']}，G1={e['gates']['G1']}，G2={e['gates']['G2']}，G3={e['gates']['G3']}，论文复现状态={e['gates']['paper_reproduction']}。",
        "",
        "G0 是测量、恢复、控制链路的认证，不是 DCO 成绩。N3 的唯一登记优化规则候选在 H43 和顺序 E96 均未达到既定 `R < 1e-4`，因此按门槛停止，未启动 64、128、1024 或 8192 步 DCO 轨迹。",
        "",
        "## 阶段总表",
        "",
        "| 阶段/门 | 状态 | 可验收证据 |",
        "|---|---|---|",
        f"| N0 资产与资源 | {e['N0']['status']} | 5 个历史资产哈希全部匹配；初始空闲 {e['N0']['disk_free_initial_bytes']} bytes；清理 0 bytes |",
        f"| N1 合同与恢复 | {e['N1']['status']} | {e['N1']['checks_passed']}/{e['N1']['checks_required']} 项 C01–C15；lab_log #{e['N1']['lab_run_id']} |",
        f"| G0 测量认证 | {g0['status']} | {g0['checks_passed']}/{g0['checks_required']} 项；lab_log #{g0['lab_run_id']}；仅 Yee/control |",
        f"| N3 / G1 | {e['N3']['G1']} | 3 个登记顺序目标中有 2 个失败；lab_log #205/#206/#207 |",
        "| N4 / G2 / G3 | NOT_RUN | G1 失败，按注册前置禁止进入长程轨迹 |",
        f"| N5 无更新诊断 | {n5['status']} | lab_log #{n5['lab_run_id']}；正式 DCO 参数更新 0 |",
        "| N6 证据汇总 | PASS | lab_log #217：本报告、JSON重算结果和图；#216：Y0–Y3结论表 |",
        "",
        "## G0：已通过的工程认证（不计作 DCO）",
        "",
        f"完整 G0 为 {g0['checks_passed']}/{g0['checks_required']} PASS。float64 精确 Yee 128 步控制的 `Q=0`、`A_fixed=0`、源外探针绝对误差为 0；float32 对独立 float64 参考的最大 `Q=2.808238e-06`、`A_fixed=9.224699e-10`、探针误差 `8.429449e-09`，均通过其 `1e-4` 数值控制阈值。第 64 接受步确实从磁盘恢复，8192 步参考缓存哈希也通过。",
        "",
        "G0 的负对照（零旋度、仅硬源、错误 H 半步和非有限）被认证器正确拒绝；这正是这些 M08–M10 的 PASS 含义，绝不是它们的数值也通过了精确控制阈值。",
        "",
        "## N3：唯一新规则的真实结果",
        "",
        "候选是 `head_lstsq_once_adam499`：每目标 1 次末层联合提交（3 个分量线性求解），随后最多 499 次全网络 Adam，零次 LBFGS；它是优化规则变体，不是论文已确认的 Algorithm 1。接受条件在任何运行前固定为物理 `R < 1e-4`。",
        "",
        "| 任务 | 实际 Adam / head / 求解 / closure | 终止 | 记录 R | 磁盘复测 R | 结果 |",
        "|---|---:|---|---:|---:|---|",
    ]
    for label, row in zip(("H43", "H96", "顺序 E96"), rows):
        lines.append(f"| {label} | {row['adam_updates']} / {row['head_commits']} / {row['linear_solve_calls']} / {row['closures']} | {row['stop_reason']} | {row['R_recorded']:.9g} | {row['R_disk']:.9g} | {row['status']} |")
    lines += [
        "",
        f"![N3 磁盘复测残差](/C:/PI-DON/{figs[0]})",
        "",
        "H43 以 `R_disk=1.4894104e-4` 失败，H96 以 `9.9804751e-5` 通过，但随后同一顺序状态的 E96 为 `1.1543830e-4`，仍失败。没有合格的完整 H→E 接受状态，所以六分量误差、`A_fixed`、源外三探针和恢复轨迹都是 `NOT_RUN`，没有借用 Yee 控制数据填充。",
        "",
        "每个登记目标都从保存的 checkpoint 以 `diagnostic_only=True` 回读并重新计算 R。H43/H96/E96 的 checkpoint、输入/靶值 hash、物理 SSE/MSE、source index、phase、UTC记录时间、恢复资格、L4/base32/cellsize/RMS/h_shift 配置和源码 hash 都在 `night_evidence.json`。",
        "",
        "## N5：无更新诊断",
        "",
        "解析平面波的 CPU double 方向导数在预登记的两个 epsilon 均通过：`1e-5` 的差为 `1.0335e-9`，`5e-6` 的差为 `2.6469e-10`。旧四份数据各取一个真实样本，经 L4/base32 反向传播均有限，零梯度参数比例均为 0；此过程没有 optimizer，也没有参数提交。",
        "",
        "不过旧 NPZ 只提供 E/C/D、网格和方向标签，缺少可核对的平面波波矢、相位、偏振及生成 seed。因此标签来源的结论是 `LABEL_PROVENANCE_INCOMPLETE`；梯度能传通不等于旧解析标签已经认证。冻结特征最小二乘只是当前固定特征空间的拟合估计，不能被称为全网络理论下界。",
        "",
        "## 资源、偏差与保留现场",
        "",
        f"登记 G1 任务合计 Adam 更新 {resource['registered_g1_adam_updates']}、head 提交 {resource['registered_g1_head_commits']}、线性求解 {resource['registered_g1_linear_solve_calls']}。另有 {resource['oracle_excluded_adam_updates']} 次 oracle-E Adam 更新完整保留但从 G1 排除。本夜证据实际占用 {resource['artifact_used_bytes']} bytes，完成时可用空间 {resource['disk_free_final_bytes']} bytes；初始空间足够，条件清理分支没有触发。",
        "",
        "#205 在 H43 checkpoint 已写入后因报告 JSON 序列化失败退出；只做了磁盘重测，没有给 H43 新预算。#206 的脚本流程还运行了 oracle-E；E96 oracle 因 H96 已通过而属于明确流程缺陷。两份 oracle 文件与账本均保留并从 G1 排除。N5 的 #208/#209 是诊断脚本错误，#210 使用了不符合计划的 n=8 微型网格；这三次都没有正式 DCO 参数更新。#211 修正为 n=7，#212 才补齐旧四样本梯度检查并作为 N5 正式证据。",
        "",
        "## 复核入口",
        "",
        "```powershell",
        "py -3.11 lab_log.py run -m \"N6 夜间证据重算、中文报告和图\" -- py -3.11 make_night_report.py --root evidence/gpt6_plan_v4_night",
        "```",
        "",
        "```powershell",
        "py -3.11 lab_log.py run -m \"N6 更新结论核对表\" -- py -3.11 verify_claims.py --pidon-v4-night --md",
        "```",
        "",
        "指标备注：nMAE 与论文式 MRE 分栏保存，未混作同一指标；精确 Yee/几何控制从未作为 DCO 成绩。",
    ]
    return "\n".join(lines) + "\n"


def bind_run_id(root: Path, run_id: int) -> None:
    stage_path = root / "stage_status.json"; stage = json.loads(stage_path.read_text(encoding="utf-8"))
    stage["N2"].update({"lab_run_id": 204, "evidence": "g0_after_head_integration/G0.json"})
    stage["N3"].update({"lab_run_ids": [205, 206, 207], "evidence": "n3_fixed/N3_fixed.json"})
    stage["N5"].update({"lab_run_id": 212, "evidence": "n5_diagnostics_attempt05/N5_diagnostics.json"})
    stage["N6"] = {"implementation": "PASS", "scientific_gate": "N/A", "lab_run_id": run_id,
                   "evidence": "FINAL_REPORT.md", "night_goal": "COMPLETE"}
    dump(stage_path, stage)
    manifest_path = root / "night_manifest.json"; manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({"status": "COMPLETE", "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(), "n6_lab_run_id": run_id})
    dump(manifest_path, manifest)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="evidence/gpt6_plan_v4_night")
    parser.add_argument("--bind-run-id", type=int)
    args = parser.parse_args(); root = (ROOT / args.root).resolve()
    if args.bind_run_id is not None:
        bind_run_id(root, args.bind_run_id); print(json.dumps({"bound_lab_run_id": args.bind_run_id}, ensure_ascii=False)); return
    evidence = night_evidence.compute(root)
    if not evidence["acceptance_file"]["exists"]: raise RuntimeError("N0 acceptance.json is missing")
    figs = make_figures(root, evidence)
    dump(root / "night_evidence.json", evidence)
    g0 = json.loads((root / "g0_after_head_integration" / "G0.json").read_text(encoding="utf-8"))
    dump(root / "required_g0_checks.json", {"required_ids": g0["required_ids"], "checks": g0["required_g0_checks"]})
    (root / "FINAL_REPORT.md").write_text(markdown(evidence, figs), encoding="utf-8")
    print(json.dumps({"night_goal": evidence["night_goal"], "gates": evidence["gates"], "figures": figs}, ensure_ascii=False))


if __name__ == "__main__":
    main()
