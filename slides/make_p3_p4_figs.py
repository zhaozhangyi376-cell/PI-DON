"""
生成 5 页进展 PPT 里 P3（训练曲线）和 P4（发散曲线）用的两张图。

    cd slides && py -3.11 make_p3_p4_figs.py

为什么单独一个脚本
    这两张图之前是哪次会话现场敲命令画的，没有存脚本，所以下次要改
    （比如 2026-09-13 这次改坐标轴格式、加图注）就没法重新生成，只能
    对着截图猜。教训：能生成图的代码本身也要存下来。

用的是哪些数据，为什么（2026-09-13 查证）
    P3 训练曲线：用 dco_L4_hist.json —— 这是仓库里【记录最完整】的一条
    L=4 曲线（800 轮，81 个点，跟论文架构一致）。注意：这不是专门用来
    和论文验收表比对的 dco_paper32 checkpoint（那张验收表的数字已经在
    RESULTS.md 里核对过，见 build_progress_deck.js 里的表格）——
    dco_paper32 自己的训练曲线文件当时没有随代码一起提交，这张图只是
    用来展示"训练损失/精度实际是怎么随轮数下降的"，不代表验收表那个
    checkpoint 的曲线。

    P4 发散曲线：用 pidon_solve_random.json —— 随机初始化、n=15 小网格
    跑 Algorithm 1 的 60 步真实记录（itE/itH 固定 4 次内层迭代，注意
    并未收敛到论文要求的 tol=1e-4）。选它是因为它是仓库里唯一一份
    【逐步】记录了"内层损失"和"解的误差"两条曲线的真实数据，能直接
    画出"损失没有跟着变大，误差却在长"这件事。P4 侧边"定量结论"面板
    里 1.0156/2e5 那组数字，来自 pidon_solve.py 的 diagnose() 函数doc-
    string 里记录的另一次跑（n=31，正确网格），那次的原始 json 同样没
    提交 —— 这一点在 PPT 备注里写清楚，不能含糊说成同一份数据。
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# WenQuanYi 管中文字形，DejaVu Sans 管数字/负号/上下标 —— 分开配置是关键。
# 之前的版本把 font.family 直接写成 "WenQuanYi Zen Hei"，连数字和数学符号
# 也逼着用这个中文字体渲染，负号字形（U+2212）在这个字体里没有，渲染成了
# 方块乱码（PPT 截图里的 "10¤4"）。
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["WenQuanYi Zen Hei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 13,
    "axes.edgecolor": "#B9C4CF", "axes.labelcolor": "#344654",
    "xtick.color": "#6F7F8E", "ytick.color": "#6F7F8E",
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 200, "savefig.bbox": "tight", "savefig.pad_inches": 0.12,
})
NAVY, INK, MUT = "#1E4465", "#344654", "#6F7F8E"
GREEN, ORANGE, RED = "#3E8D6D", "#D9822D", "#B3392B"
OUT = "figs"


def sci(y, _pos=None):
    """把纵轴刻度统一写成 "1e-04" 这种纯文本格式 —— 跟 PPT 表格、正文里
    "5.3e-3" "1.18e-16" 的写法保持一致，不用带上标的科学计数法（那种
    写法在某些字体组合下会露出上面说的负号乱码，纯文本没有这个问题）。"""
    if y <= 0:
        return ""
    e = int(np.floor(np.log10(y)))
    m = y / 10 ** e
    return f"{m:.0f}e{e:+03d}" if abs(m - round(m)) < 0.05 else f"{y:.0e}"


def fig_p3():
    """P3：训练曲线。左边看「学得进去没有」，右边看「学得准不准」。"""
    h = json.load(open("../dco_L4_hist.json"))
    ep = h["epoch"]

    fig, ax = plt.subplots(figsize=(6.6, 3.9))
    ax.semilogy(ep, h["train"], color=NAVY, lw=2.0, label="训练损失（网络在训练集上的误差）")
    ax.semilogy(ep, h["test"], color=ORANGE, lw=2.0, label="测试损失（在没见过的数据上的误差）")
    ax.set_xlabel("训练轮数 epoch")
    ax.set_ylabel("损失（越低越好，对数坐标）")
    ax.set_title("图注：训练越久，网络预测旋度的误差越小\n"
                  "（L=4 架构，真实训练记录，共 800 轮）", fontsize=12, loc="left")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(sci))
    ax.legend(fontsize=10.5, frameon=False, loc="upper right")
    ax.grid(alpha=0.25, lw=0.5)
    fig.savefig(f"{OUT}/p3_training.png")
    plt.close(fig)
    print("p3_training.png")

    fig, ax = plt.subplots(figsize=(6.6, 3.9))
    ax.semilogy(ep, h["nmae"], color=GREEN, lw=2.2,
                label="我们的 nMAE（预测旋度 vs 真实旋度，逐样本 平均绝对误差/最大值）")
    ax.axhline(5.3e-3, color=MUT, lw=1.3, ls=":")
    ax.text(ep[-1], 5.3e-3, "论文 L=3 档 5.3e-3  ", ha="right", va="bottom",
            fontsize=10, color=MUT)
    ax.axhline(7.7e-4, color=RED, lw=1.3, ls="--")
    ax.text(ep[-1], 7.7e-4, "论文 L=4 档 7.7e-4  ", ha="right", va="top",
            fontsize=10, color=RED)
    ax.set_xlabel("训练轮数 epoch")
    ax.set_ylabel("nMAE（越低越好，对数坐标）")
    ax.set_title("图注：精度随训练轮数改善，虚线是论文自己报的两档目标值\n"
                  "（同一次 L=4 训练；此曲线仅示意收敛趋势，不是验收表的 checkpoint）",
                  fontsize=12, loc="left")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(sci))
    ax.legend(fontsize=10, frameon=False, loc="upper right")
    ax.grid(alpha=0.25, lw=0.5)
    fig.savefig(f"{OUT}/p3_accuracy.png")
    plt.close(fig)
    print("p3_accuracy.png")


def fig_p4():
    """P4：为什么「内层损失不大」判断不出「解有没有跑飞」。"""
    d = json.load(open("../pidon_solve_random.json"))
    rows = d["rows"]
    step = np.array([r["step"] for r in rows])
    nmae = np.array([r["nmae"] for r in rows])
    lossE = np.array([r["lossE"] for r in rows])
    lossH = np.array([r["lossH"] for r in rows])

    fig, ax1 = plt.subplots(figsize=(6.9, 4.1))
    ax1.semilogy(step, np.maximum(nmae, 1e-13), color=RED, lw=2.2,
                 label="解的误差 nMAE（DUT 场 vs 参考场，越低越准）")
    ax1.set_xlabel("时间步")
    ax1.set_ylabel("解的误差 nMAE（对数坐标）", color=RED)
    ax1.tick_params(axis="y", labelcolor=RED)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(sci))

    ax2 = ax1.twinx()
    ax2.plot(step, lossE, color=NAVY, lw=1.6, ls="--", label="内层训练损失 lossE")
    ax2.plot(step, lossH, color=MUT, lw=1.6, ls=":", label="内层训练损失 lossH")
    ax2.set_ylabel("每一步的内层训练损失（线性坐标）", color=NAVY)
    ax2.tick_params(axis="y", labelcolor=NAVY)
    ax2.set_ylim(0, 1.3)

    ax1.set_title("图注：60 步真实记录 —— 内层损失（虚线，右轴）全程停在\n"
                  "0.5~1.0 没怎么变小，解的误差（红线，左轴）却涨了 12 个数量级",
                  fontsize=11.5, loc="left")
    l1, lb1 = ax1.get_legend_handles_labels()
    l2, lb2 = ax2.get_legend_handles_labels()
    ax1.legend(l1 + l2, lb1 + lb2, fontsize=9.3, frameon=False, loc="upper left")
    ax1.grid(alpha=0.2, lw=0.5)
    fig.savefig(f"{OUT}/p4_growth.png")
    plt.close(fig)
    print("p4_growth.png")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    fig_p3()
    fig_p4()
