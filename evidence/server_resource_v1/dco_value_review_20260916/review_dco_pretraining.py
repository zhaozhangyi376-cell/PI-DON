"""Zero-update archive/checkpoint audit and paired DCO retrospective plots."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import zipfile

import numpy as np
import torch

from project_paths import PROJECT_DIR, configure
configure()
from pidon_contract import six_component_metrics

ROOT = PROJECT_DIR
BASE = ROOT / "evidence/server_resource_v1"
COMPONENTS = ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def row_cost(row):
    return sum(int((row.get(k) or {}).get("n_updates", 0)) for k in ("fit_H", "fit_E"))


def field_gate(metrics):
    components = metrics["components"]
    assert set(components) == set(COMPONENTS)
    failures = [name for name, m in components.items() if
                (m["absolute_mae"] > 1e-5 if m["weak_reference"] else
                 m["nmae"] is None or not math.isfinite(m["nmae"]) or m["nmae"] > .01)]
    q, fixed = metrics["global_weighted_relative_l2"], metrics["fixed_amplitude_error"]
    return {"pass": not failures and math.isfinite(q) and q <= .05 and math.isfinite(fixed) and fixed <= .001,
            "Q": q, "component_failures": failures, "fixed_amplitude_error": fixed}


def extract(archive, dest):
    dest.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        seen = set()
        for info in z.infolist():
            name = info.filename.replace("\\", "/")
            parts = PurePosixPath(name).parts
            if name.startswith("/") or ".." in parts or ":" in name or name.lower() in seen:
                raise ValueError(f"Invalid/duplicate archive member: {name}")
            seen.add(name.lower())
            target = dest.joinpath(*parts)
            target.resolve().relative_to(dest.resolve())
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, target.open("xb") as dst:
                    shutil.copyfileobj(src, dst)


def audit_probe(directory):
    summary, metadata = read(directory / "summary.json"), read(directory / "run_metadata.json")
    rows = jsonl(directory / "steps.jsonl")
    assert len(rows) == 128 and all(row["accepted"] for row in rows)
    assert [r["sequence_id"] for r in rows] == list(range(128))
    assert [r["accepted_steps"] for r in rows] == list(range(1, 129))
    assert summary["accepted_steps"] == 128
    adam = sum(row_cost(r) for r in rows)
    assert adam == summary["new_adam_updates"] == summary["budget"]["adam"]
    assert all(row_cost(r) == r["row_cost"]["adam"] for r in rows)
    assert summary["new_closures"] == sum((r.get(k) or {}).get("n_closures", 0) for r in rows for k in ("fit_H", "fit_E")) == 0
    assert all((r.get(k) or {}).get("n_lbfgs_steps", 0) == 0 for r in rows for k in ("fit_H", "fit_E"))
    for row in rows:
        for k in ("fit_H", "fit_E"):
            fit = row[k]
            assert fit["passed"]
            if fit["target_ss"] > 0:
                assert math.isclose(fit["residual_ratio"], fit["sse"] / fit["target_ss"], rel_tol=2e-5)
                assert fit["residual_ratio"] < metadata["config"]["tol"]
    pointer = read(directory / "checkpoint_pointer.json")
    assert pointer["last_committed_sequence_id"] == 127
    assert sha(directory / pointer["path"]) == pointer["sha256"]
    ck = torch.load(directory / pointer["path"], map_location="cpu", weights_only=False)
    assert ck["last_committed_sequence_id"] == 127 and ck["accepted_steps"] == 128
    assert ck["phase"] == "before_H" and ck["frozen_config"] == metadata["frozen_config"]
    assert ck["recorder_identity"]["run_id"] == metadata["run_id"]
    optimizer_last = {}
    for key, fit_key in (("opt_H", "fit_H"), ("opt_E", "fit_E")):
        values = sorted({int(s["step"]) for s in ck[key]["state"].values() if "step" in s})
        assert values == [rows[-1][fit_key]["n_updates"]]
        optimizer_last[key] = values
    del ck
    checks = {}
    for step in (32, 64, 128):
        ck = torch.load(directory / f"snapshot_step_{step:04d}.pt", map_location="cpu", weights_only=False)
        assert ck["accepted_steps"] == step and ck["last_committed_sequence_id"] == step - 1
        n = ck["config"]["n"]
        reference = ck["reference"]
        measured = six_component_metrics(ck["E"], ck["H"],
            [reference[k].float() for k in COMPONENTS[:3]],
            [reference[k].float() for k in COMPONENTS[3:]],
            [ck["config"]["side"] / n] * 3, source_ez_index=(n // 2,) * 3)
        recorded = rows[step-1]["six_component_metrics"]
        for key in ("global_weighted_relative_l2", "fixed_amplitude_error"):
            assert math.isclose(measured[key], recorded[key], rel_tol=1e-7, abs_tol=1e-14)
        for name in COMPONENTS:
            for key in ("absolute_mae", "nmae", "reference_max"):
                a, b = measured["components"][name][key], recorded["components"][name][key]
                assert a is None and b is None or a is not None and b is not None and math.isclose(a, b, rel_tol=1e-7, abs_tol=1e-14)
        checks[str(step)] = field_gate(measured)
        if step in (64, 128):
            assert checks[str(step)]["pass"] == summary[f"field_gate_{step}"]["pass"]
        del ck
    expected = "PASS_128" if checks["128"]["pass"] else "FAIL"
    assert summary["scientific_result"] == expected
    failing = [r["accepted_steps"] for r in rows if field_gate(r["six_component_metrics"])["component_failures"]]
    probes = []
    for i in range(3):
        p = np.array([r["source_outside_probes"][i]["dut_Ez"] for r in rows])
        ref = np.array([r["source_outside_probes"][i]["ref_Ez"] for r in rows])
        probes.append({"cells": rows[-1]["source_outside_probes"][i]["cells"],
                       "relative_l2_all_128_samples": float(np.linalg.norm(p-ref)/np.linalg.norm(ref)),
                       "last": rows[-1]["source_outside_probes"][i]})
    return {"directory": str(directory.relative_to(ROOT)), "summary": summary,
            "config": metadata["frozen_config"], "source_hashes": metadata["source_hashes"],
            "row_sum_adam": adam, "snapshot_checks": checks,
            "optimizer_last_half_steps": optimizer_last, "first_component_failure": min(failing) if failing else None,
            "source_outside_waveform_diagnostics": probes}, rows, metadata


def plot(runs, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "Microsoft YaHei", "axes.unicode_minus": False, "font.size": 10})
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    for name, rows, color in runs:
        steps = np.arange(1, len(rows)+1)
        axes[0, 0].plot(steps, np.cumsum([row_cost(r) for r in rows]), label=name, color=color)
        trace = rows[0]["fit_traces"]["E"]
        axes[0, 1].semilogy([t["updates"] for t in trace], [t["loss"] for t in trace], label=name, color=color)
        axes[1, 0].plot(steps, [r["six_component_metrics"]["global_weighted_relative_l2"] * 100 for r in rows], label=name, color=color)
        for component, style in (("Ex", "-"), ("Ey", "--")):
            vals = [r["six_component_metrics"]["components"][component] for r in rows]
            axes[1, 1].plot(steps, [v["nmae"] * 100 if not v["weak_reference"] else np.nan for v in vals], style, color=color, label=f"{name} {component}")
    axes[0, 0].set(title="相同128步：随机组累计更新更少", xlabel="完整物理时间步", ylabel="累计 Adam 更新次数")
    axes[0, 1].axhline(1e-5, color="gray", ls=":")
    axes[0, 1].set(title="第1步相同 E 输入：预训练起点更差", xlabel="该半步 Adam 更新次数", ylabel="R = SSE / 目标平方和")
    axes[1, 0].axhline(5, color="gray", ls=":", label="项目 Q 门 5%")
    axes[1, 0].set(title="总场误差接近，两组均低于5%", xlabel="完整物理时间步", ylabel="Q (%)")
    axes[1, 1].axhline(1, color="gray", ls=":", label="项目分量门 1%")
    axes[1, 1].set(title="Ex/Ey 分量门：两组后期均失败", xlabel="完整物理时间步", ylabel="分量 nMAE (%)")
    for ax in axes.flat:
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    fig.suptitle("DCO 预训练与随机初始化：当前实现的一组对照", fontsize=16)
    fig.savefig(out / "pretraining_comparison.png", dpi=180)
    fig.savefig(out / "pretraining_comparison.pdf")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--action-id", required=True)
    ap.add_argument("--zip", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    from run import require_action
    require_action(args.action_id)
    torch.set_num_threads(2)
    out = args.output.resolve()
    out.relative_to(BASE.resolve())
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out / "review_dco_pretraining.py")
    print("Extracting and hashing random128 return", flush=True)
    extract(args.zip, out / "returned")
    rnd = out / "returned/random_low_lr128"
    summary, manifest = read(rnd / "summary.json"), read(rnd / "manifest.json")
    labs = jsonl(out / "returned/lab_runs.jsonl")
    lab = [r for r in labs if str(r["id"]) == summary["lab_run_id"]]
    assert len(lab) == 1
    lab = lab[0]
    assert lab["exit_code"] == 0 and summary["action_id"] in lab["argv"]
    file_checks = []
    for item in lab["outputs"]:
        prefix = "evidence/server_resource_v1/random_low_lr128/"
        assert item["path"].startswith(prefix)
        path = rnd / item["path"][len(prefix):]
        digest = sha(path)
        assert digest == item["sha256"] and path.stat().st_size == item["bytes"]
        file_checks.append({"path": item["path"], "sha256": digest})
    events = [e for e in jsonl(out / "returned/actions.jsonl") if e["action_id"] == summary["action_id"]]
    assert [e["event"] for e in events] == ["start", "finish"]
    assert events[0]["task_id"] == "SR-128-LOWLR-RANDOM"
    assert events[0]["protocol_sha256"] == manifest["protocol_sha256"]
    assert sha(rnd / "source" / manifest["protocol"]) == manifest["protocol_sha256"]
    for rel, digest in manifest["source_snapshot_hashes"].items():
        assert sha(rnd / "source" / rel) == digest
    assert sha(ROOT / "src/pidon/pidon_contract.py") == manifest["source_hashes"]["pidon_contract.py"]
    print("Verifying random128 and clean128 checkpoints and saved field metrics", flush=True)
    random_result, random_rows, random_meta = audit_probe(rnd)
    pretrained_dir = BASE / "imports/server_clean_low_lr128_return_20260916T092721Z/clean_low_lr128"
    pretrained, pretrained_rows, pretrained_meta = audit_probe(pretrained_dir)
    differences = {k: [pretrained["config"].get(k), random_result["config"].get(k)]
                   for k in set(pretrained["config"]) | set(random_result["config"])
                   if pretrained["config"].get(k) != random_result["config"].get(k)}
    assert set(differences) == {"init"}
    assert pretrained["source_hashes"] == random_result["source_hashes"]
    assert random_result["config"]["init"] == "random" and random_meta["init_sha256"] is None
    first_e = {name: rows[0]["fit_E"] for name, rows in (("pretrained", pretrained_rows), ("random", random_rows))}
    assert first_e["pretrained"]["target_ss"] == first_e["random"]["target_ss"]
    assert first_e["pretrained"]["target_count"] == first_e["random"]["target_count"]
    weight = ROOT / "assets/models/dco_lr1e3_300.pt"
    assert sha(weight) == pretrained_meta["init_sha256"]
    ck = torch.load(weight, map_location="cpu", weights_only=False)
    weight_meta = {k: ck.get(k) for k in ("epoch", "levels", "base", "grid", "coords", "norm", "target", "head")}
    weight_meta["history_config"] = ck.get("hist", {}).get("config")
    del ck
    limitation = [
        "One pretrained checkpoint and one random seed at 128; no population-level speed claim.",
        "Both 128 field gates fail; cost comparison is not successful same-accuracy solver certification.",
        "Random metadata master/row arm labels still name pretrained legacy defaults; init=random and init_sha256=null define actual initialization.",
        "No initial model snapshot before the first update; initialization verified through config, command and saved code, not a zero-step tensor hash.",
        "pidon_contract.py was not copied into returned source; local copy hash matches the recorded production hash.",
        "Milestone saved fields remeasured; no forward/backward training run and no independent reconstruction of every inter-milestone field.",
        "Saved reference fields checked against saved metrics, not an independent accuracy certification of Yee against a continuum solution.",
        "Source-outside whole-window L2 reported as retrospective diagnostic, not a substituted registered active-window gate.",
        "No current checkpoint authorizes continuation: scientific FAIL and recovery_eligible=False.",
    ]
    result = {"status": "PASS", "action_id": args.action_id, "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
              "new_adam_updates": 0, "new_closures": 0, "zip_sha256": sha(args.zip),
              "server_lab_id": lab["id"], "server_lab_wall_s": lab["seconds"],
              "verified_files": file_checks, "pretrained": pretrained, "random": random_result,
              "frozen_config_differences": differences, "core_source_hashes_identical": True,
              "old_weight_metadata": weight_meta, "first_E_comparison": first_e,
              "random_update_saving": 1-random_result["row_sum_adam"]/pretrained["row_sum_adam"],
              "random_wall_saving": 1-summary["elapsed_s"]/pretrained["summary"]["elapsed_s"],
              "limitations": limitation, "long_run_unlocked": False}
    save(out / "audit.json", result)
    plot([("预训练", pretrained_rows, "#236b8e"), ("随机初始化", random_rows, "#ba4f32")], out)
    lines = ["# DCO预训练价值：128步证据审计", "", "本次仅读取、复算和绘图，参数更新为0。原始回传保存在returned/。", "",
             "| 指标 | 预训练初始化 | 随机初始化 |", "|---|---:|---:|"]
    p, r = pretrained["summary"], random_result["summary"]
    for label, a, b in [("完整时间步", p["accepted_steps"], r["accepted_steps"]),
                        ("Adam更新", p["new_adam_updates"], r["new_adam_updates"]),
                        ("运行耗时（秒）", round(p["elapsed_s"], 2), round(r["elapsed_s"], 2)),
                        ("交付状态", p["status"], r["status"]),
                        ("科学状态", p["scientific_result"], r["scientific_result"]),
                        ("128步Q (%)", 100*p["field_gate_128"]["global_weighted_relative_l2"], 100*r["field_gate_128"]["global_weighted_relative_l2"]),
                        ("首个分量门失败步", pretrained["first_component_failure"], random_result["first_component_failure"]),
                        ("恢复资格", p["recovery_eligible"], r["recovery_eligible"])]:
        lines.append(f"| {label} | {a} | {b} |")
    lines += ["", f"随机组更新少 {result['random_update_saving']:.2%}，墙钟少 {result['random_wall_saving']:.2%}；两组最终场门均失败，不作同精度成功求解的加速认证。", "",
              "## 第一个E半步", "", "相同零初场、硬源波形、支持域和目标平方和；第一个H半步均为零输入直通。", "",
              "| 指标 | 预训练 | 随机 |", "|---|---:|---:|"]
    for key in ("loss_initial", "target_ss", "target_count", "n_updates", "residual_ratio"):
        lines.append(f"| {key} | {first_e['pretrained'][key]} | {first_e['random'][key]} |")
    lines += ["", "## 第128步六分量", "", "nMAE与相对L2均用百分数；弱参考分量保留绝对误差。", "",
              "| 分量 | 预训练 nMAE (%) | 随机 nMAE (%) | 预训练 absMAE | 随机 absMAE |", "|---|---:|---:|---:|---:|"]
    for name in COMPONENTS:
        a = pretrained_rows[-1]["six_component_metrics"]["components"][name]
        b = random_rows[-1]["six_component_metrics"]["components"][name]
        av = "弱参考" if a["weak_reference"] else f"{100*a['nmae']:.6f}"
        bv = "弱参考" if b["weak_reference"] else f"{100*b['nmae']:.6f}"
        lines.append(f"| {name} | {av} | {bv} | {a['absolute_mae']:.8g} | {b['absolute_mae']:.8g} |")
    lines += ["", "## 源点与源外探针", "", "源点为硬赋值，不能单独证明传播正确。所有数值均来自原始记录。", ""]
    for label, item, rows in (("预训练", pretrained, pretrained_rows), ("随机", random_result, random_rows)):
        lines += [f"### {label}", "", f"末步H/E残差：{rows[-1]['fit_H']['residual_ratio']:.8g} / {rows[-1]['fit_E']['residual_ratio']:.8g}。",
                  f"源点：`{rows[-1]['source_probe_Ez']}`", ""]
        for probe in item["source_outside_waveform_diagnostics"]:
            lines.append(f"- {probe['cells']}：128个样本整体相对L2={probe['relative_l2_all_128_samples']:.6%}；末步=`{probe['last']}`")
    lines += ["", "## 审计范围", "", f"随机组lab #{lab['id']}，输出哈希核对 {len(file_checks)} 项；两组32/64/128快照指标均读回复算一致。",
              "冻结配置仅init不同，记录的核心源码哈希一致。优化器每步重置，其step计数只核对最后半步；累计成本按逐步记录重算。", "",
              *[f"- {v}" for v in limitation], "", "![对照曲线](pretraining_comparison.png)"]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "new_updates": 0, "report": str(out / "REPORT.md"),
                      "random_scientific_result": summary["scientific_result"], "random_adam": r["new_adam_updates"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
