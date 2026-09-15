"""
一张总的「论文 vs 当前进展」对比表，汇总 STATUS.md 里的关键数字。

    cd slides && py -3.11 make_comparison_table.py

数字来源（全部可在 RESULTS.md / LAB_NOTEBOOK.md 溯源，没有一个是记忆写的）：
    训练设置/32³精度      dco_lr1e3_300（当前最优checkpoint），LAB_NOTEBOOK run #45
    换网格 64³/64x96x16/32x64x16   dco_paper32（旧checkpoint）——只有它在论文
        的确切网格尺寸上测过，标了「旧」，不能默认读成当前最优的表现
    16³/48³                dco_lr1e3_300 自己测的网格，跟论文不是同一组尺寸，
        不能横向比倍数，单列一栏
    第二阶段步数            dco_paper32→158，dco_lr1e3_300→230，均为 EXP3
        冻结推理（不是论文 Algorithm 1 本身），见 AGENTS.md 2.1
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["WenQuanYi Zen Hei", "DejaVu Sans"],
    "axes.unicode_minus": False,
})
NAVY, INK, MUT = "#1E4465", "#344654", "#6F7F8E"
GREEN, ORANGE, RED, TINT = "#3E8D6D", "#D9822D", "#B3392B", "#F2F6F9"
WHITE, HEAD = "#FFFFFF", "#1E4465"
OUT = "figs"

# (分区标题, [(项目, 论文, 我们, 说明, 说明颜色), ...])
SECTIONS = [
 ("训练设置", [
   ("网格 / 样本数", "32³ / 1000", "32³ / 1000", "一致", INK),
   ("网络层数 L / 参数", "4 / 9.25M", "4 / 9.25M", "一致", INK),
   ("训练轮数", "1000", "300", "30%，消融证明瓶颈在\n优化步数不是轮数", ORANGE),
   ("学习率 / batch", "1e-4 / 32", "1e-3 / 16", "消融选出，2.32x 优于\n论文同配置基线", GREEN),
 ]),
 ("阶段一 · 精度（nMAE，32³ 训练网格）", [
   ("同网格 nMAE", "L=3: 5.3e-3\nL=4: 7.7e-4", "2.791e-3",
    "比 L=3 好 1.9x\n比 L=4 差 3.6x", ORANGE),
 ]),
 ("阶段一 · 换网格泛化（论文 III-D 口径）", [
   ("64³", "4.1e-3", "2.875e-3 ①", "0.70x 优于论文", GREEN),
   ("64×96×16", "3.8e-3", "5.687e-3 ①", "1.50x", ORANGE),
   ("32×64×16", "4.7e-3", "6.266e-3 ①", "1.33x", ORANGE),
   ("16³ / 48³（论文未测这组）", "—", "6.845e-3 / 3.258e-3 ②", "无法对比倍数", MUT),
 ]),
 ("阶段二 · 闭环能连续跑多少步", [
   ("步数", "8192（Algorithm 1\n每步重训）③", "158 ① → 230 ②\n（冻结推理，非①③同法）",
    "2.8%，且方法不同\n不能直接说「差多少倍」", RED),
 ]),
]

NOTES = [
 "①  dco_paper32（旧 checkpoint，lr 3e-4+cosine），在论文的确切网格尺寸上测过",
 "②  dco_lr1e3_300（当前最优 checkpoint），尚未在①的网格尺寸上重测",
 "③  论文的第二阶段是每个时间步重新训练，不是训好一次冻结推理；两者不是同一方法，8192 与 158/230 不能算倍数",
]

fig_h = 1.1 + sum(0.62 + 0.50 * len(rows) for _, rows in SECTIONS) + 0.28 * len(NOTES) + 0.5
fig, ax = plt.subplots(figsize=(11.5, fig_h))
ax.set_xlim(0, 11.5); ax.set_ylim(0, fig_h); ax.axis("off")

COLW = [3.55, 2.55, 3.05, 2.35]
X0 = [0.05, 0.05 + 3.55, 0.05 + 3.55 + 2.55, 0.05 + 3.55 + 2.55 + 3.05]
y = fig_h - 0.15

# 标题行
ax.text(0.05, y, "论文 vs 我们 —— 当前进展对比", fontsize=17, weight="bold",
        color=NAVY, va="top")
y -= 0.5

for sec_title, rows in SECTIONS:
    # 分区条
    ax.add_patch(plt.Rectangle((0.02, y - 0.40), 11.46, 0.40, color=HEAD))
    ax.text(0.18, y - 0.20, sec_title, fontsize=11.5, weight="bold",
            color=WHITE, va="center")
    y -= 0.40
    # 表头
    for x, w, t in zip(X0, COLW, ["项目", "论文", "我们", "说明"]):
        ax.text(x + 0.08, y - 0.16, t, fontsize=9.5, weight="bold", color=MUT,
                va="center")
    y -= 0.30
    for i, (item, paper, ours, note, ncolor) in enumerate(rows):
        h = 0.50
        if i % 2 == 0:
            ax.add_patch(plt.Rectangle((0.02, y - h), 11.46, h, color=TINT,
                                        zorder=0))
        ax.text(X0[0] + 0.08, y - h / 2, item, fontsize=10, color=INK,
                va="center", linespacing=1.3)
        ax.text(X0[1] + 0.08, y - h / 2, paper, fontsize=10, color=INK,
                va="center", linespacing=1.25)
        ax.text(X0[2] + 0.08, y - h / 2, ours, fontsize=10, weight="bold",
                color=NAVY, va="center", linespacing=1.25)
        ax.text(X0[3] + 0.08, y - h / 2, note, fontsize=9, color=ncolor,
                va="center", linespacing=1.25)
        y -= h
    y -= 0.14

y -= 0.05
for n in NOTES:
    ax.text(0.10, y, n, fontsize=8.3, color=MUT, va="top")
    y -= 0.28

fig.savefig(f"{OUT}/comparison_table.png", dpi=200, bbox_inches="tight",
            pad_inches=0.15)
plt.close(fig)
print("comparison_table.png")

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
