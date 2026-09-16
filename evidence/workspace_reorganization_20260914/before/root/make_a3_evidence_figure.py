"""Plot the stored, registered A3 residuals without recomputing a fit."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import FontProperties


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "evidence" / "gpt6_plan_v3" / "h_layout_candidate" / "A3_GATE.json"
OUT = ROOT / "evidence" / "gpt6_plan_v3" / "h_layout_candidate" / "A3_residuals_readable.png"
CN = FontProperties(fname=r"C:\Windows\Fonts\msyh.ttc")


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    rows = data["tasks"]
    steps = [str(row["step"]) for row in rows]
    x = np.arange(len(rows))
    threshold = 1e-4
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8), constrained_layout=True)
    axes[0].bar(x - .18, [row["old_H_R"] for row in rows], .36, label="旧未移位 H")
    axes[0].bar(x + .18, [row["H_R"] for row in rows], .36, label="h_shift=True")
    axes[1].bar(x, [row["E_R"] for row in rows], .48, color="#d95f02", label="仅 oracle E")
    for ax, title in zip(axes, ("H：唯一位置候选", "E：H 失败后的诊断")):
        ax.axhline(threshold, color="black", ls="--", lw=1, label="原门槛 R=1e-4")
        ax.set_yscale("log")
        ax.set_xticks(x, steps)
        ax.set_xlabel("固定状态", fontproperties=CN)
        ax.set_ylabel("保存参数的 R", fontproperties=CN)
        ax.set_title(title, fontproperties=CN)
        ax.legend(fontsize=8, prop=CN)
        ax.grid(axis="y", alpha=.25)
    fig.suptitle("A3 结果：几何布局正确，不足以在登记优化预算内通过 R 门槛", fontsize=11,
                 fontproperties=CN)
    fig.savefig(OUT, dpi=180)
    print(OUT)


if __name__ == "__main__":
    main()
