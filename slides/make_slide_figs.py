"""Purpose-made teaching figures for the 复现 slides.  Chinese labels, big type,
one message per figure.  Every number is either computed here or transcribed
from the user's own runs (marked)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mp
import numpy as np

plt.rcParams.update({
    "font.family": "WenQuanYi Zen Hei", "font.size": 13,
    "axes.edgecolor": "#B9C4CF", "axes.labelcolor": "#344654",
    "xtick.color": "#6F7F8E", "ytick.color": "#6F7F8E",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.unicode_minus": False,
    "figure.dpi": 200, "savefig.bbox": "tight", "savefig.pad_inches": 0.12,
})
NAVY, INK, MUT = "#1E4465", "#344654", "#6F7F8E"
GREEN, TEAL, ORANGE, RED = "#3E8D6D", "#16A8B7", "#D9822D", "#B3392B"
TINT, PALE = "#F2F6F9", "#E2F4F6"
OUT = "/tmp/pfig/"


# ─────────────────────────── fig A · FDTD 循环 ───────────────────────────
def figA():
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.set_xlim(0, 10); ax.set_ylim(-0.15, 7); ax.axis("off")

    def box(x, y, w, h, txt, fc, ec, tc, fs=13, bold=True):
        ax.add_patch(mp.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12",
                     fc=fc, ec=ec, lw=1.6))
        ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center",
                fontsize=fs, color=tc, weight="bold" if bold else "normal")

    box(0.6, 4.4, 2.6, 1.3, "电场 E", PALE, TEAL, NAVY, 15)
    box(6.8, 4.4, 2.6, 1.3, "磁场 H", PALE, TEAL, NAVY, 15)
    box(3.6, 4.55, 2.8, 1.0, "算 ∇×E", "#FDECEA", RED, RED, 14)
    box(3.6, 1.45, 2.8, 1.0, "算 ∇×H", "#FDECEA", RED, RED, 14)
    box(0.6, 1.3, 2.6, 1.3, "更新 E", TINT, "#B9C4CF", INK, 14)
    box(6.8, 1.3, 2.6, 1.3, "更新 H", TINT, "#B9C4CF", INK, 14)

    ar = dict(arrowstyle="-|>", color="#8FA0AF", lw=1.8,
              mutation_scale=16, shrinkA=4, shrinkB=4)
    ax.annotate("", xy=(3.5, 5.05), xytext=(3.3, 5.05), arrowprops=ar)
    ax.annotate("", xy=(6.9, 5.05), xytext=(6.6, 5.05), arrowprops=ar)
    ax.annotate("", xy=(8.1, 2.7), xytext=(8.1, 4.3), arrowprops=ar)
    ax.annotate("", xy=(6.5, 1.95), xytext=(6.9, 1.95), arrowprops=ar)
    ax.annotate("", xy=(3.3, 1.95), xytext=(3.5, 1.95), arrowprops=ar)
    ax.annotate("", xy=(1.9, 4.3), xytext=(1.9, 2.7), arrowprops=ar)

    ax.text(5.0, 3.5, "一个时间步", ha="center", va="center", fontsize=13,
            color=MUT)
    ax.text(5.0, 3.05, "循环几千~几十万次", ha="center", va="center",
            fontsize=11, color=MUT)
    ax.add_patch(mp.FancyBboxPatch((1.5, 0.05), 7.0, 0.72,
                 boxstyle="round,pad=0.1", fc="#FDECEA", ec=RED, lw=1.4))
    ax.text(5.0, 0.41, "论文：把这两个红框换成同一个神经网络", ha="center",
            va="center", fontsize=13.5, color=RED, weight="bold")
    fig.savefig(OUT + "A_loop.png"); plt.close(fig)
    print("A_loop.png")


# ───────────────────── fig B · 腔体频谱（真实计算） ─────────────────────
def figB():
    z = np.load("/tmp/cav.npz")
    f, X = z["f"] / 1e9, z["X"]
    m = (f > 3) & (f < 12.5)
    f, X = f[m], X[m] / X[m].max()

    ana = [4.243, 7.348, 9.000, 9.487, 11.225]
    mine = [4.238, 7.340, 8.991, 9.459, 11.202]
    name = ["TE110", "TE211", "TE221", "TE310", "TE321"]

    fig, ax = plt.subplots(figsize=(8.6, 3.5))
    ax.plot(f, X, color=TEAL, lw=1.6, label="我写的 FDTD 算出来的频谱")
    lv = [1.20, 1.20, 1.20, 1.05, 1.20]      # TE310 sits close to TE221
    for a, mm, nm, yy in zip(ana, mine, name, lv):
        ax.axvline(a, color=ORANGE, ls="--", lw=1.2, alpha=0.9)
        ax.text(a, yy, nm, ha="center", fontsize=11, color=ORANGE,
                weight="bold")
        ax.text(a, yy - 0.093, f"{(mm - a) / a * 100:+.2f}%", ha="center",
                fontsize=10, color=MUT)
    ax.plot([], [], color=ORANGE, ls="--", lw=1.2, label="解析公式给出的谐振频率")
    ax.set_xlabel("频率  (GHz)"); ax.set_ylabel("归一化幅度")
    ax.set_ylim(0, 1.42); ax.set_xlim(3, 12.5)
    ax.legend(fontsize=11.5, frameon=False, loc="upper left",
              bbox_to_anchor=(0.20, 0.72))
    ax.grid(alpha=0.2, axis="x")
    fig.savefig(OUT + "B_cavity.png"); plt.close(fig)
    print("B_cavity.png")


# ───────────────── fig C · 一个训练样本长什么样（真实数据） ─────────────────
def figC():
    """一个真实的训练样本：现场用 gen_data.py 生成，不是示意图。"""
    import subprocess, sys
    subprocess.run([sys.executable, "gen_data.py", "--n", "48", "--samples", "1",
                    "--out", "/tmp/s1.npz", "--seed", "11"],
                   cwd="/home/user/HFSS_auto/pidon_mvp", stdout=subprocess.DEVNULL)
    z = np.load("/tmp/s1.npz")
    E, C = z["E"][0], z["C"][0]
    k = E.shape[-1] // 2
    fig, ax = plt.subplots(1, 2, figsize=(8.2, 3.7))
    for a, dat, t, cm in ((ax[0], E[2, :, :, k], "输入：电场 Ez 的一个切片", "RdBu_r"),
                          (ax[1], C[2, :, :, k], "答案：它的旋度", "PuOr_r")):
        v = np.abs(dat).max()
        a.imshow(dat.T, cmap=cm, vmin=-v, vmax=v, origin="lower")
        a.set_title(t, fontsize=14, color=NAVY, pad=9)
        a.set_xticks([]); a.set_yticks([])
        for sp in a.spines.values():
            sp.set_visible(True); sp.set_color("#B9C4CF")
    fig.subplots_adjust(wspace=0.30)
    fig.text(0.5, 0.52, "解析公式\n直接写出来", ha="center", va="center",
             fontsize=12.5, color=ORANGE, weight="bold")
    fig.text(0.5, 0.30, "→", ha="center", va="center", fontsize=26,
             color=ORANGE)
    fig.text(0.5, -0.04, "两边都是纸上算出来的 —— 不用求解器，不用天线模型",
             ha="center", fontsize=12.5, color=MUT)
    fig.savefig(OUT + "C_sample.png"); plt.close(fig)
    print("C_sample.png")


# ─────────────────────── fig D · DeepONet 两条腿 ───────────────────────
def figD():
    fig, ax = plt.subplots(figsize=(7.6, 4.0))
    ax.set_xlim(0, 12); ax.set_ylim(-0.1, 6.4); ax.axis("off")

    def box(x, y, w, h, txt, fc, ec, tc, fs=12.5):
        ax.add_patch(mp.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                     fc=fc, ec=ec, lw=1.5))
        ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center",
                fontsize=fs, color=tc, weight="bold")

    box(0.3, 4.15, 2.5, 1.15, "场 E\n（三个分量）", PALE, TEAL, NAVY)
    box(0.3, 1.1, 2.5, 1.15, "坐标信息\n（格子多大）", "#E4F1EA", GREEN, NAVY)

    # U-Net silhouette for the branch
    xs = [3.3, 3.95, 4.6, 5.25, 5.9]
    hs = [1.30, 0.90, 0.55, 0.90, 1.30]
    for x, h in zip(xs, hs):
        ax.add_patch(mp.FancyBboxPatch((x, 4.72 - h / 2), 0.52, h,
                     boxstyle="round,pad=0.03", fc="#CBE9EE", ec=TEAL, lw=1.1))
    ax.text(5.0, 5.75, "3D U-Net 主干  ·  2.25 M 参数", ha="center",
            fontsize=12, color=TEAL, weight="bold")
    box(3.3, 1.1, 3.12, 1.15, "小网络", "#DCEEE4", GREEN, NAVY, 12.5)

    box(7.4, 2.55, 1.5, 1.6, "逐元素\n相乘", "#EFF4F8", "#B9C4CF", NAVY, 12)
    box(9.5, 2.7, 2.2, 1.3, "输出 ∇×E", "#E4F1EA", GREEN, GREEN, 13.5)

    ar = dict(arrowstyle="-|>", color="#8FA0AF", lw=1.7, mutation_scale=15)
    ax.annotate("", xy=(3.2, 4.72), xytext=(2.9, 4.72), arrowprops=ar)
    ax.annotate("", xy=(3.2, 1.67), xytext=(2.9, 1.67), arrowprops=ar)
    ax.annotate("", xy=(7.3, 3.8), xytext=(6.5, 4.6), arrowprops=ar)
    ax.annotate("", xy=(7.3, 2.9), xytext=(6.6, 1.75), arrowprops=ar)
    ax.annotate("", xy=(9.4, 3.35), xytext=(9.0, 3.35), arrowprops=ar)

    ax.text(1.55, 5.45, "branch 分支", ha="center", fontsize=12.5,
            color=TEAL, weight="bold")
    ax.text(1.55, 2.40, "trunk 分支", ha="center", fontsize=12.5,
            color=GREEN, weight="bold")
    ax.text(6.0, 0.18, "坐标是「输入」，不是训练时写死的  →  换网格只换这一路，权重不动",
            ha="center", fontsize=12.5, color=ORANGE, weight="bold")
    fig.savefig(OUT + "D_net.png"); plt.close(fig)
    print("D_net.png")


# ─────────── fig E · 换网格误差（用户实测 pidon_R2_all） ───────────
def figE():
    lab = ["16³\n(训练用的)", "32³", "48³", "64×96×16", "32×64×16"]
    val = [1.886, 2.450, 4.119, 3.146, 3.139]                # 用户实测 ×1e-2
    fig, ax = plt.subplots(figsize=(7.2, 3.3))
    cols = [GREEN] + [TEAL] * 4
    b = ax.bar(range(5), val, color=cols, width=0.6)
    for i, v in enumerate(val):
        ax.text(i, v + 0.12, f"{v:.2f}", ha="center", fontsize=12,
                color=cols[i], weight="bold")
    ax.set_xticks(range(5)); ax.set_xticklabels(lab, fontsize=11)
    ax.set_ylabel("相对误差  (x 0.01)")
    ax.set_ylim(0, 5.1); ax.grid(alpha=0.2, axis="y"); ax.set_axisbelow(True)
    ax.annotate("同一套权重，没有重新训练", xy=(2, 4.119), xytext=(3.1, 4.75),
                fontsize=12, color=ORANGE, weight="bold",
                arrowprops=dict(arrowstyle="->", color=ORANGE, lw=1.3))
    fig.savefig(OUT + "E_grid.png"); plt.close(fig)
    print("E_grid.png")


# ─────────────── fig F · ρ 越大活得越短（用户实测 16 个模型） ───────────────
def figF():
    rho = np.array([0.1135, 0.1149, 0.1172, 0.1330, 0.1541, 0.1556, 0.1663,
                    0.1665, 0.1795, 0.1812, 0.2021, 0.2361, 0.2570, 0.2589,
                    0.4173, 0.5028])
    life = np.array([135, 125, 131, 116, 69, 73, 78, 56, 60, 75, 59, 52, 49,
                     62, 31, 30], float)
    fig, ax = plt.subplots(figsize=(7.0, 3.9))
    ax.loglog(rho, life, "o", ms=10, color=TEAL, mec="white", mew=1.2)
    xs = np.array([0.10, 0.55])
    k = np.exp(np.mean(np.log(life) + np.log(rho)))
    ax.loglog(xs, k / xs, "-", color="#B9C4CF", lw=1.5, zorder=0)
    ax.text(0.42, k / 0.42 * 1.45, "放大得越狠，\n活得越短", fontsize=12,
            color=MUT, ha="center")
    for r, l, t in ((0.1135, 135, "最好的\nρ=1.11"), (0.5028, 30, "最差的\nρ=1.50")):
        ax.annotate(t, xy=(r, l), xytext=(0, 22), textcoords="offset points",
                    ha="center", fontsize=11, color=NAVY, weight="bold")
    ax.set_xlabel("每一步放大多少   rho - 1")
    ax.set_ylabel("撑到第几步才炸")
    ax.set_xticks([0.1, 0.2, 0.3, 0.5])
    ax.set_xticklabels(["0.1", "0.2", "0.3", "0.5"])
    ax.set_yticks([30, 50, 80, 130]); ax.set_yticklabels(["30", "50", "80", "130"])
    ax.minorticks_off(); ax.grid(alpha=0.2); ax.set_axisbelow(True)
    fig.savefig(OUT + "F_rho.png"); plt.close(fig)
    print("F_rho.png")


# ────────── fig G · 减小时间步没用（用户实测，16 个模型） ──────────
def figG():
    t = {"dco_L3": [30.4, 30.1, 30.5], "dco_L3b": [29.7, 30.1, 30.3],
         "dco_L3c": [74.6, 74.7, 75.3], "dco_L3d": [48.5, 48.3, 49.3],
         "dco_L4": [76.9, 77.0, 78.2], "dco_L4b": [61.7, 61.6, 62.8],
         "dco_paper32": [123.4, 123.7, 125.0], "pidon_A2": [51.1, 50.6, 51.7],
         "pidon_A_yee": [59.7, 59.7, 60.8], "pidon_B_div": [68.6, 68.8, 70.0],
         "pidon_C2": [58.7, 58.3, 59.0], "pidon_C_both": [72.6, 72.3, 73.0],
         "pidon_D_perwave": [114.5, 115.0, 116.3], "pidon_E2": [55.4, 55.5, 55.3],
         "pidon_R1_roll": [129.4, 130.2, 131.8], "pidon_R2_all": [133.3, 134.9, 136.3]}
    cfl = np.array([0.99, 0.70, 0.50])
    raw, scaled = [], []
    for v in t.values():
        steps = np.array(v) / cfl                    # back out the raw counts
        raw.append(steps / steps.mean())
        tt = np.array(v)
        scaled.append(tt / tt.mean())
    raw = np.concatenate(raw); scaled = np.concatenate(scaled)

    fig, ax = plt.subplots(figsize=(6.6, 3.7))
    rng = np.random.default_rng(0)
    for i, (v, col, lab) in enumerate(((raw, RED, "步数"),
                                       (scaled, GREEN, "步数 × 时间步长\n（= 物理时间）"))):
        ax.plot(i + rng.uniform(-0.16, 0.16, len(v)), v, "o", ms=7, color=col,
                alpha=0.55, mec="white", mew=0.5)
        ax.text(i, 1.74, f"散开 {v.max() / v.min():.2f} 倍", ha="center",
                fontsize=13, color=col, weight="bold")
    ax.axhline(1.0, color="#B9C4CF", ls="--", lw=1.1, zorder=0)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["步数", "步数 × 时间步长\n（= 物理时间）"], fontsize=12)
    ax.set_xlim(-0.55, 1.55); ax.set_ylim(0.5, 1.95)
    ax.set_ylabel("除以各自的平均值")
    ax.grid(alpha=0.2, axis="y"); ax.set_axisbelow(True)
    fig.savefig(OUT + "G_time.png"); plt.close(fig)
    print("G_time.png")


# ────────── fig H · 结构化算子（用户实测 2-D / 3-D） ──────────
def figH():
    fig, ax = plt.subplots(1, 2, figsize=(9.0, 3.5))

    # (a) accuracy, 2-D, same task, same data
    lab = ["Yee 格式\n（教科书）", "自由 CNN\n2.8 万参数", "结构化算子\n8 个参数"]
    val = [7.307e-2, 5.338e-3, 4.948e-5]
    cols = ["#8FA0AF", ORANGE, GREEN]
    ax[0].bar(range(3), val, color=cols, width=0.6)
    ax[0].set_yscale("log")
    for i, v in enumerate(val):
        ax[0].text(i, v * 2.0, f"{v:.1e}".replace("e-0", "e-"), ha="center",
                   fontsize=12, color=cols[i], weight="bold")
    ax[0].set_xticks(range(3)); ax[0].set_xticklabels(lab, fontsize=11)
    ax[0].set_ylabel("误差（越低越好）")
    ax[0].set_ylim(1e-5, 1.2)
    ax[0].set_yticks([1e-5, 1e-4, 1e-3, 1e-2, 1e-1])
    ax[0].set_yticklabels(["1e-5", "1e-4", "1e-3", "1e-2", "1e-1"], fontsize=10)
    ax[0].minorticks_off()
    ax[0].set_title("(a) 8 个参数，比 Yee 格式准 1500 倍", fontsize=13,
                    color=NAVY, loc="left", pad=8)
    ax[0].grid(alpha=0.2, axis="y"); ax[0].set_axisbelow(True)

    # (b) where each one is stable, as the time step shrinks
    rows = [("Yee 格式", 0.99, True), ("自由 CNN", None, False),
            ("结构化算子", 0.70, True)]
    for i, (nm, cut, ok) in enumerate(rows):
        y = 2 - i
        if ok:
            ax[1].barh(y, cut, left=0.0, height=0.45, color=GREEN, alpha=0.85)
            ax[1].barh(y, 1.05 - cut, left=cut, height=0.45, color="#F0D7CE")
            ax[1].text(cut / 2, y, "稳定", ha="center", va="center",
                       fontsize=11.5, color="white", weight="bold")
        else:
            ax[1].barh(y, 1.05, left=0.0, height=0.45, color=ORANGE, alpha=0.9)
            ax[1].text(0.52, y, "整条都不稳定", ha="center", va="center",
                       fontsize=11.5, color="white", weight="bold")
        ax[1].text(-0.05, y, nm, ha="right", va="center", fontsize=11.5,
                   color=NAVY, weight="bold")
    ax[1].set_xlim(0, 1.12); ax[1].set_ylim(-1.05, 2.6)
    ax[1].set_yticks([])
    ax[1].set_xticks([0.08, 0.3, 0.5, 0.7, 0.99])
    ax[1].set_xticklabels(["0.08", "0.3", "0.5", "0.7", "0.99"], fontsize=10)
    ax[1].set_xlabel("时间步长（CFL 数）　←　越往左时间步越小")
    ax[1].spines["left"].set_visible(False)
    ax[1].set_title("(b) 而且 ρ 严格等于 1 —— 可以证明", fontsize=13,
                    color=NAVY, loc="left", pad=8)
    ax[1].text(0.52, -0.80, "自由 CNN 一路测到 CFL 0.08 仍然 ρ > 1\n减小时间步救不了它",
               ha="center", va="center", fontsize=11, color=ORANGE)
    fig.subplots_adjust(wspace=0.30)
    fig.savefig(OUT + "H_struct.png"); plt.close(fig)
    print("H_struct.png")


for fn in (figA, figB, figC, figD, figE, figF, figG, figH):
    try:
        fn()
    except Exception as e:
        print(fn.__name__, "FAILED:", e)
