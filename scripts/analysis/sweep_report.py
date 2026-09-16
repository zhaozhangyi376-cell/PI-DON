"""
把一夜的消融扫描读成一张排名表。

    py -3.11 sweep_report.py            # 读 sweep_*_hist.json，按测试损失排名

判断标准写在这里，跑之前就定死：
  * 主指标是【nMAE 的末段均值】（逐样本口径，与 test_dco / 论文一致），不是
    最小值 —— 最小值会挑中一次幸运的抖动，而我们要的是「这个配置稳定在什么
    水平」。
  * 2026-09-12 的教训：原先按 test（训练用的损失函数值）排名是【错的】。
    --loss mse 的 run 报的是普通 MSE，--loss rel 的 run 报的是逐样本相对 MSE，
    两者量纲根本不同 —— 一个 5.3e-4 和一个 6.0e-3 放同一列比大小毫无意义。
    按 test 排，mse 配置「赢」基线 11.37x；按 nMAE 排，它只有 1.05x，是噪声。
    只有 nMAE 和相对 L2 是跨配置可比的，因为它们在物理旋度上算，与训练时用
    哪个损失函数无关。test 列保留只为看收敛形状，带 * 的行不可与他行比大小。
  * 报「末段均值 / 首段均值」作为改善幅度，以及末段的抖动幅度 —— 一个还在
    剧烈抖动的配置，即使均值好看也不能算赢。
"""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import glob
import json
import os

import numpy as np

SCRIPT_VERSION = "2026-09-12b"
MIN_PTS = 4          # 少于这个点数说不出趋势


def tail_of(n):
    """末段取多少个点。

    2026-09-11 的 bug：这里写死 TAIL = 10 并要求至少 2*TAIL = 20 个点。
    但 train_dco 每 10 轮才记录一次，80 轮只有 9 个点 —— 于是八个消融文件
    被【静默全部跳过】，报告只说「还没有文件」，看上去像任务没跑。
    静默跳过是最坏的失败方式：它把「我读不了」伪装成「没有数据」。
    现在按实际长度自适应，并且在报告里写明每个配置用了几个点。
    """
    return max(2, min(10, n // 3))


def read(f):
    try:
        j = json.load(open(f, encoding="utf-8"))
    except Exception:
        return None
    ep = j.get("epoch") or []
    if len(ep) < MIN_PTS:
        print(f"  [跳过] {os.path.basename(f)}：只有 {len(ep)} 个记录点，"
              f"少于 {MIN_PTS}")
        return None
    T = tail_of(len(ep))
    tag = os.path.basename(f)[len("sweep_"):-len("_hist.json")]
    # 训练用的是哪个损失函数。新版 train_dco 会把 config 写进 hist；旧文件
    # 没有这一项，退回按文件名判断（run H 叫 sweep_mse）。这决定 test 列能
    # 不能跨行比大小 —— 见模块 docstring。
    cfg = j.get("config") or {}
    lossfn = cfg.get("loss") or ("mse" if "mse" in tag else "rel")
    out = {"tag": tag, "loss": lossfn,
           "epochs": int(ep[-1]) if ep else 0, "pts": len(ep), "T": T}
    for k in ("test", "train", "nmae", "relL2"):
        v = j.get(k)
        if isinstance(v, list) and len(v) >= MIN_PTS:
            out[k + "_tail"] = float(np.mean(v[-T:]))
            out[k + "_head"] = float(np.mean(v[:T]))
            out[k + "_jit"] = float(np.std(v[-T:]) / max(np.mean(v[-T:]),
                                                         1e-30))
    return out if "nmae_tail" in out else None


def main():
    print(f"[sweep_report.py  version {SCRIPT_VERSION}]")
    rows = [r for r in (read(f) for f in sorted(glob.glob("sweep_*_hist.json")))
            if r]
    if not rows:
        print("  还没有 sweep_*_hist.json。先跑 run_night3.bat。")
        return
    KEY = "nmae_tail"
    rows.sort(key=lambda r: r[KEY])
    mixed = len({r["loss"] for r in rows}) > 1
    print(f"  {len(rows)} 个配置，按 nMAE 末段均值排名（越小越好）\n")
    print(f"  {'配置':<20s} {'轮数':>5s} {'点/末':>7s} {'nMAE':>11s} "
          f"{'改善':>7s} {'抖动':>7s} {'relL2':>11s} {'train损失':>12s}")
    print("  " + "-" * 90)
    for r in rows:
        imp = r["nmae_head"] / max(r[KEY], 1e-30)
        star = "*" if r["loss"] == "mse" else " "
        print(f"  {r['tag']:<20s} {r['epochs']:>5d} "
              f"{r['pts']:>3d}/{r['T']:<3d} {r[KEY]:>11.3e} "
              f"{imp:>6.2f}x {r['nmae_jit']:>6.0%} "
              f"{r.get('relL2_tail', float('nan')):>11.3e} "
              f"{r.get('test_tail', float('nan')):>11.3e}{star}")
    if mixed:
        print("\n  * 这一行训练时用的损失函数与其他行不同（mse vs rel），"
              "【train损失】那一列量纲不同，")
        print("    不能跨行比大小。排名只用 nMAE / relL2，它们算在物理旋度上，"
              "与用哪个损失函数无关。")
    b, w = rows[0], rows[-1]
    print(f"\n  最好 {b['tag']}：nMAE {b[KEY]:.3e}")
    print(f"  最差 {w['tag']}：nMAE {w[KEY]:.3e}   相差 "
          f"{w[KEY] / b[KEY]:.2f}x")
    base = next((r for r in rows if "baseline" in r["tag"]), None)
    if base:
        print(f"\n  相对基线 nMAE {base[KEY]:.3e}：")
        for r in rows:
            if r is base:
                continue
            k = base[KEY] / r[KEY]
            mark = "好" if k > 1.15 else ("差" if k < 0.87 else "持平")
            print(f"    {r['tag']:<22s} {k:>6.2f}x   {mark}")
        print("\n  只有明显超过 1.15x 的才值得跟进；1.15 以内是训练噪声。")
    print(f"RESULT sweep_best {b['tag']} {b[KEY]:.4e}")


if __name__ == "__main__":
    main()
