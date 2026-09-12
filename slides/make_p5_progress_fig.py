"""
生成 P5（总结与后续计划）顶部的"结果对比图"。

    cd slides && py -3.11 make_p5_progress_fig.py

2026-09-13 改了一版
    第一版画的是"训练轮数 300/1000"，被用户指出：这是【过程】（投入了多少
    算力/时间），不是【进展】（做出来的东西离论文差多少）。练了多少轮
    本身不是成果，练出来的精度才是。改成两块真正的"结果"：
      左：阶段一的精度实际落在论文哪两档目标之间（数字来自 dco_L4_hist.json
          真实训练记录的最终值，跟 P3 图是同一份数据）
      右：阶段二能连续闭环跑多少步（158/8192，这个数字本身就是论文
          验收用的口径——Table II 要求跑完整 8192 步——所以它不是"投入
          多少"，是"做到了多少"，留下不改）
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["WenQuanYi Zen Hei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 12.5,
})
NAVY, ORANGE, RED, GREEN, MUT, TRACK = \
    "#1E4465", "#D9822D", "#B3392B", "#3E8D6D", "#6F7F8E", "#E4E9EE"
OUT = "figs"

fig, (axL, axR) = plt.subplots(1, 2, figsize=(14.4, 1.95),
                               gridspec_kw={"width_ratios": [1.35, 1]})

# ---- 左：阶段一，精度落在论文哪两档之间（结果，不是过程） ----
h = json.load(open("../dco_L4_hist.json"))
ours = h["nmae"][-1]                      # 1.81e-3，跟 P3 图同一份数据
L3, L4 = 5.3e-3, 7.7e-4                   # 论文 Table I 两档目标
axL.set_xscale("log")
axL.axhline(0, color=TRACK, lw=10, zorder=1, solid_capstyle="round")
for x, label, color, dy in [(L3, "论文 L=3 档\n5.3e-3", MUT, 1),
                            (L4, "论文 L=4 档\n7.7e-4（更严）", MUT, 1),
                            (ours, f"我们\n{ours:.2e}", ORANGE, -1)]:
    axL.scatter([x], [0], s=140, color=color, zorder=3,
                edgecolor="white", linewidth=1.2)
    axL.text(x, 0.55 * dy, label, ha="center",
             va="bottom" if dy > 0 else "top", fontsize=10.5,
             color=color, weight="bold", linespacing=1.25)
axL.set_xlim(4e-4, 8e-3)
axL.set_ylim(-1.3, 1.3)
# 这是个"数轴示意图"，三个点自己标了数值，坐标轴本身的刻度只会挤成一团
# 反而看不清（对数轴在这么窄的范围里刻度很密）——干脆不画刻度。
# 注意 set_xticks([]) 只清一次主刻度，对数轴的次刻度会在画图时重新生成，
# 必须连 locator 一起换成 NullLocator 才是真的不画。
axL.xaxis.set_major_locator(mticker.NullLocator())
axL.xaxis.set_minor_locator(mticker.NullLocator())
axL.set_yticks([]); axL.set_xlabel("nMAE（越靠左越准，对数坐标）")
for sp in ("left", "top", "right"):
    axL.spines[sp].set_visible(False)
axL.set_title("阶段一 · 结果：精度落在论文两档目标之间，更靠近严的那档",
              fontsize=11.5, loc="left")

# ---- 右：阶段二，闭环实测能跑多少步（本身就是论文的验收口径） ----
done, target = 158, 8192
frac = done / target
axR.barh(0, 1.0, height=0.42, color=TRACK, zorder=1)
axR.barh(0, frac, height=0.42, color=RED, zorder=2)
axR.text(frac + 0.02, 0, f"{done}/{target}\n({frac*100:.0f}%)", ha="left",
         va="center", fontsize=12, color=RED, weight="bold", linespacing=1.2)
axR.axvline(1.0, color=NAVY, lw=1.2, ls=":")
axR.text(1.0, 0.45, "论文要求\n跑完整 8192 步", ha="right", va="bottom",
         fontsize=9.5, color=NAVY, linespacing=1.2)
axR.set_xlim(0, 1.28); axR.set_ylim(-0.6, 0.9)
axR.axis("off")
axR.set_title("阶段二 · 结果：闭环实测能连续跑多少步就停在这（这数字\n"
              "本身就是论文 Table II 的验收口径，不是投入了多少训练量）",
              fontsize=11.2, loc="left")

fig.savefig(f"{OUT}/p5_progress.png", bbox_inches="tight", pad_inches=0.15,
            dpi=200)
plt.close(fig)
print(f"p5_progress.png  ours_nmae={ours:.3e}  steps={done}/{target}")

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
