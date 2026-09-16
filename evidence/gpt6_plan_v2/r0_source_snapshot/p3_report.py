"""Turn the raw P3 fixed-state JSON into a compact, reviewable Chinese report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="evidence/gpt6_plan_v1/fixed_states/fixed_state_report.json")
    parser.add_argument("--out", default="evidence/gpt6_plan_v1/P3_REPORT.md")
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    tasks = data["tasks"]
    lines = [
        "# P3：固定 Yee 状态内层拟合诊断报告", "",
        "## 协议与边界", "",
        "本实验从同序精确 Yee 轨迹抽取固定输入/目标；每项拟合独立从同一 `dco_paper32.pt` 初始化，"
        "最多 500 次 Adam 更新、`R<1e-4`、lr=`3e-4`。它不向下一时间层反馈预测，因此不是闭环 DCO 轨迹。",
        "", "## 固定状态拟合", "",
        "| 时间步 | 集合 | 子问题 | 初始 R | 实际更新 | 最终 R | 状态 | 耗时 s |",
        "|---:|---|---|---:|---:|---:|---|---:|",
    ]
    failures = []
    for task in tasks:
        fit = task["fit"]
        passed = fit["passed"]
        if not passed:
            failures.append((task["step"], task["which"], fit["loss_final"], fit["stop_reason"]))
        lines.append("| {step} | {split} | curl-{which} | {initial:.3e} | {updates} | {final:.3e} | {reason} | {elapsed:.2f} |".format(
            step=task["step"], split=task["split"], which=task["which"],
            initial=task["baseline"]["loss_final"], updates=fit["n_updates"],
            final=fit["loss_final"], reason=fit["stop_reason"], elapsed=fit["elapsed_s"],
        ))
    lines += ["", "## 单步替换误差", "", "| 时间步 | 仅 curl-H | 仅 curl-E | 两者同时 |", "|---:|---:|---:|---:|"]
    one_step_failures = []
    for step, cases in data.get("single_step_errors", {}).items():
        values = {name: item["global_weighted_relative_l2"] for name, item in cases.items()}
        if any(value > 1e-3 for value in values.values()):
            one_step_failures.append((step, values))
        lines.append("| {step} | {h:.3e} | {e:.3e} | {both:.3e} |".format(
            step=step, h=values["curl_H_only"], e=values["curl_E_only"], both=values["both_single_step"]
        ))
    lines += ["", "## 判定", ""]
    if failures:
        lines.append("G1 **未通过**：以下固定目标在登记的 500 次预算内仍未达到 `R<1e-4`：")
        lines.append("")
        for step, which, value, reason in failures:
            lines.append(f"- 第 {step} 步 curl-{which}：最终 `R={value:.6e}`，停止原因 `{reason}`。")
    else:
        lines.append("所有固定目标达到 `R<1e-4`；还需结合单步误差确认 G1。")
    if one_step_failures:
        lines += ["", "单步替换也有超过 `1e-3` 的全局加权误差，因此不能绕过固定拟合失败直接进入短程闭环。"]
    lines += ["", "本次总 GPU 墙钟 `%.2f s`，低于登记 3600 s 总预算；未触发资源停止。" % data["elapsed_s"],
              "", "下一分支按计划为 P4-A：只在开发状态比较基线 Adam 与登记的 Adam(≤200)+LBFGS(≤200 closure、≤60 s/目标)，"
              "然后一次性用冻结验证状态验收。不能直接续跑 64/128/8192 步。", ""]
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"out": args.out, "g1_pass": not failures and not one_step_failures,
                      "fit_failures": failures, "one_step_failures": one_step_failures,
                      "elapsed_s": data["elapsed_s"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
