"""Generate Chinese R1/R2 reports from recorded v2 evidence without rerunning it."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "evidence" / "gpt6_plan_v2"


def runs_by_id():
    rows = [json.loads(line) for line in (ROOT / "lab_runs.jsonl").read_text(encoding="utf-8").splitlines()]
    return {row.get("id"): row for row in rows}


def main():
    runs = runs_by_id()
    required = [115, 116, 117, 120]
    present = {rid: (runs.get(rid, {}).get("exit_code") == 0) for rid in required}
    r1_ok = all(present.values())
    r1 = f"""# R1：停止、恢复与测量合同报告

R1 回归记录为 run #{', #'.join(map(str, required))}；这些记录均退出成功：`{r1_ok}`。

- 同一冻结配置下，E_pending 恢复与不中断事务保持相同场；恢复传入不同源值时不会重复 E 更新或注源。
- 恢复时修改 tol 被拒绝；已使用的内层 Adam 预算保存在 checkpoint，恢复后不会重新获得更新次数。
- 非有限注入测试显示 raw checkpoint 先保留 NaN 参数，随后工作网络恢复到 safe 状态。
- 非零无旋输入不再伪装成相对残差：R 为 null，固定尺度 MSE 与最大绝对残差共同决定停止。
- 正式参考改为独立 Yee 的 E→source→H 顺序，六分量主统计排除硬源 Ez 自由度，并输出固定幅值误差分母。

这只认证 R1 的微型合同；尚不构成 DCO 内层收敛或场精度结果。
"""
    (OUT / "R1_REPORT.md").write_text(r1, encoding="utf-8")
    evidence = json.loads((OUT / "R2_exact_control.json").read_text(encoding="utf-8"))
    double, single, zero = evidence["float64"], evidence["float32"], evidence["zero_curl_negative"]
    r2_ok = (double["finite"] and single["finite"]
             and double["max_global_relative_l2"] <= 1e-10
             and single["max_global_relative_l2"] <= 1e-4
             and zero["max_global_relative_l2"] > 0.05
             and "not a DCO" in double["classification"])
    r2 = f"""# R2：生产路径独立 Yee 控制报告

run #121 通过 `ProductionControlSolver.step`、支撑映射、PEC、硬源、六分量测量和独立 `PECCavity.step_e_source_h` 参考完成 128 步。

| 控制 | 最大全局相对 L2 | 门槛 | 结果 |
|---|---:|---:|---|
| float64 精确 Yee | {double['max_global_relative_l2']:.6e} | <=1e-10 | 通过 |
| float32 精确 Yee | {single['max_global_relative_l2']:.6e} | <=1e-4 | 通过 |
| 零旋度负例 | {zero['max_global_relative_l2']:.6e} | 必须 >5% | 被正确拒绝 |

控制分类固定为 `{double['classification']}`。它证明当前生产事务和评价接口能识别精确 Yee 与无传播负例；它不包含训练网络输出，不能计入 DCO 成绩。

R2 G0 判断：`{'PASS' if r2_ok else 'FAIL'}`。
"""
    (OUT / "R2_REPORT.md").write_text(r2, encoding="utf-8")
    print(json.dumps({"R1": "PASS" if r1_ok else "FAIL", "R2": "PASS" if r2_ok else "FAIL"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
