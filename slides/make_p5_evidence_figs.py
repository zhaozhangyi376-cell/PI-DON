"""
生成 P5「我们多做的部分」用的两张证据图 —— 不是画意思意思的示意图，是直接
调用 verify_claims.py 里算 C2/C3 结论那两个函数，把它们算出来的真实点画出来。

    cd slides && py -3.11 make_p5_evidence_figs.py

为什么要这么做（2026-09-13）
    用户原话："我要的是试错、纠偏、多做且有效的证据图！证明我们真的做了，
    而且做的是有用的！否则我看到文字一概觉得你在放屁"。
    光写"相关系数 0.894，192 个点"这种结论式的一句话，读者没法验证这句话
    是不是真的算出来的。这两张图直接复用 verify_claims.py 的 spectral() /
    usable() / per_ckpt()，跟 RESULTS.md 里 C2 / C3 那两行数字是同一份计算，
    图和结论对得上号，不是另起一次口径。
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

sys.path.insert(0, "..")
import verify_claims as V   # noqa: E402  就是要用它的 spectral/usable/per_ckpt

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["WenQuanYi Zen Hei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 12.5,
    "axes.edgecolor": "#B9C4CF", "axes.labelcolor": "#344654",
    "xtick.color": "#6F7F8E", "ytick.color": "#6F7F8E",
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 200, "savefig.bbox": "tight", "savefig.pad_inches": 0.12,
})
NAVY, INK, MUT = "#1E4465", "#344654", "#6F7F8E"
GREEN, ORANGE, RED = "#3E8D6D", "#D9822D", "#B3392B"
OUT = "figs"


def fig_c2_rho_predicts():
    """C2：谱半径 rho 预测出的寿命，跟实测寿命一致吗。"""
    os.chdir("..")
    m = V.spectral()
    os.chdir("slides")
    flat = [r for rs in m.values() for r in V.usable(rs)]
    p = np.log([r["pred_blowup"] for r in flat])
    q = np.log([r["blowup"] for r in flat])
    corr = float(np.corrcoef(p, q)[0, 1])

    fig, ax = plt.subplots(figsize=(5.6, 4.2))
    ax.scatter(p, q, s=22, color=NAVY, alpha=0.55, edgecolor="none")
    lo, hi = min(p.min(), q.min()), max(p.max(), q.max())
    ax.plot([lo, hi], [lo, hi], color=RED, lw=1.4, ls="--",
            label="预测=实测（完美预测线）")
    ax.set_xlabel("log(算子谱半径 rho 预测的寿命)")
    ax.set_ylabel("log(实际闭环跑出来的寿命)")
    ax.set_title(f"证据：rho 能不能预测闭环能跑多少步\n"
                 f"{len(flat)} 个点，16 个 checkpoint，相关系数 {corr:+.3f}",
                 fontsize=12, loc="left")
    ax.legend(fontsize=10, frameon=False, loc="upper left")
    ax.grid(alpha=0.2, lw=0.5)
    fig.savefig(f"{OUT}/p5_c2_rho.png")
    plt.close(fig)
    print(f"p5_c2_rho.png  corr={corr:.3f}  n={len(flat)}")


def fig_c3_fixed_time():
    """C3：把时间步切细一倍，能不能多撑一倍步数？（能=步数固定，不能=物理
    时间固定）——每条线是一个 checkpoint，横轴 CFL，纵轴寿命，都是对数坐标；
    斜率 -1 说明"寿命 x CFL = 常数"，也就是撑住的物理时长跟时间步切多细
    完全无关。"""
    os.chdir("..")
    m = V.spectral()
    os.chdir("slides")
    fig, ax = plt.subplots(figsize=(5.9, 4.2))
    slopes = []
    for i, (t, rs) in enumerate(sorted(m.items())):
        rs = V.usable(rs)
        cfls = sorted({r["cfl"] for r in rs})
        if len(cfls) < 3:
            continue
        y = [float(np.mean([r["blowup"] for r in rs if r["cfl"] == c]))
             for c in cfls]
        b = float(np.polyfit(np.log(cfls), np.log(y), 1)[0])
        slopes.append(b)
        ax.plot(cfls, y, "o-", ms=4, lw=1.1, color=NAVY, alpha=0.5)
    med = float(np.median(slopes))
    # 画一条斜率恰好 -1 的参考线，位置摆在数据点云中间，纯做视觉对照
    xs = np.array([min(min(l.get_xdata()) for l in ax.lines),
                   max(max(l.get_xdata()) for l in ax.lines)])
    ys0 = np.median([np.median(l.get_ydata()) for l in ax.lines])
    xmid = float(np.exp(np.mean(np.log(xs))))
    ref = ys0 * (xs / xmid) ** -1
    ax.plot(xs, ref, color=RED, lw=1.8, ls="--",
            label="斜率 = -1（时长跟步长切多细无关）")
    ax.set_xscale("log"); ax.set_yscale("log")
    # 默认的对数坐标刻度用 mathtext 画负指数，WenQuanYi 里没有对应的负号
    # 字形，渲染成方块乱码（跟 P3/P4 那次是同一个坑）——改成纯小数刻度。
    plain = mticker.FuncFormatter(lambda v, _: f"{v:g}")
    ax.xaxis.set_major_formatter(plain)
    ax.xaxis.set_minor_formatter(plain)
    ax.set_xlabel("时间步长 / 稳定性上限 CFL（对数坐标）")
    ax.set_ylabel("闭环撑住的步数（对数坐标）")
    inband = sum(1 for b in slopes if -1.15 <= b <= -0.85)
    ax.set_title(f"证据：切细时间步能不能延长寿命\n"
                 f"{len(slopes)} 个 checkpoint 各自拟合的斜率，中位数 "
                 f"{med:+.3f}，{inband}/{len(slopes)} 落在 -1 附近",
                 fontsize=11.5, loc="left")
    ax.legend(fontsize=9.5, frameon=False, loc="lower left")
    ax.grid(alpha=0.2, lw=0.5, which="both")
    fig.savefig(f"{OUT}/p5_c3_cfl.png")
    plt.close(fig)
    print(f"p5_c3_cfl.png  median_slope={med:.3f}  n_ckpt={len(slopes)}")


def fig_metric_fix():
    """精度口径这个坑：改口径前后的差距摆在一起看。
    数字来自 verify_claims.py 的 _metric_note()/c_metric_gap()docstring 里
    记录的实测范围（40~200x、0.7~1.5x）——那两个 npz 原始文件是大文件，
    按仓库规则不进 git，所以这里画的是【已经核对过、写进 RESULTS.md 的
    结论范围】，不是现场重新算的；这一点在 PPT 里也会标出来。"""
    fig, ax = plt.subplots(figsize=(5.4, 2.7))
    rows = [("改口径前\n（公式字面实现）", 40, 200, RED),
            ("改口径后\n（按论文定义算）", 0.7, 1.5, GREEN)]
    for i, (label, lo, hi, color) in enumerate(rows):
        y = 1 - i
        ax.plot([lo, hi], [y, y], color=color, lw=8, solid_capstyle="round")
        ax.text((lo * hi) ** 0.5, y + 0.28, f"{lo}~{hi} 倍", ha="center",
                fontsize=12, color=color, weight="bold")
        ax.text(0.055, y, label, ha="right", va="center", fontsize=11.5,
                color=INK, linespacing=1.3)
    ax.axvline(1, color=NAVY, lw=1.3, ls=":")
    ax.text(1, 1.85, "1x = 跟论文数字\n完全对上", ha="center", va="bottom",
            fontsize=9.5, color=NAVY, linespacing=1.2)
    ax.set_xscale("log")
    ax.set_xlim(0.4, 400)
    ax.set_ylim(-0.7, 2.2)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_xlabel("我们的结果 / 论文的结果（倍数，对数坐标，越接近 1 越好）")
    ax.set_yticks([])
    for sp in ("left", "top", "right"):
        ax.spines[sp].set_visible(False)
    ax.set_title("证据：换对量精度的方法之后，差距从「差 40~200 倍」\n"
                 "变成「差 0.7~1.5 倍」——不是结果变好了，是量对了",
                 fontsize=11.5, loc="left")
    fig.savefig(f"{OUT}/p5_metric_fix.png")
    plt.close(fig)
    print("p5_metric_fix.png")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    fig_c2_rho_predicts()
    fig_c3_fixed_time()
    fig_metric_fix()
