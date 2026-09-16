"""Create the saved evidence figure for the 32-step Algorithm-1 run."""
from pathlib import Path
import json
import shutil
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from paper_recheck import dump, sha256
import stage2_evidence as E

plt.rcParams.update({'font.sans-serif': ['Microsoft YaHei', 'DejaVu Sans'],
                     'axes.unicode_minus': False, 'font.size': 10})


def main():
    j, f = E.read(); rows = j['rows']; x = np.arange(1, 33)
    out = ROOT / 'figs'; out.mkdir(exist_ok=True); paths = []
    def save(fig, name):
        p = out / name; fig.savefig(p, dpi=180, bbox_inches='tight', facecolor='white')
        plt.close(fig); paths.append(p)
    fig, axs = plt.subplots(1, 3, figsize=(14, 4.6), layout='constrained')
    axs[0].plot(x, [r['nmae'] for r in rows], color='#0072B2', marker='o', ms=3)
    axs[0].set(title='场误差：32步保持有限', xlabel='时间步', ylabel='相对 nMAE / FDTD', yscale='log')
    axs[1].plot(x, [r['lossH'] for r in rows], label='curl H', color='#D55E00')
    axs[1].plot(x, [r['lossE'] for r in rows], label='curl E', color='#009E73')
    axs[1].axhline(1e-4, color='#555', ls='--', label='论文停止阈值')
    axs[1].set(title='内层损失：未稳定满足阈值', xlabel='时间步', ylabel='相对平方损失', yscale='log')
    axs[1].legend(fontsize=8); axs[1].grid(alpha=.2)
    axs[2].plot(x, [r['cum'] for r in rows], color='#CC79A7', marker='o', ms=3)
    axs[2].set(title='每步累计内层损失', xlabel='时间步', ylabel='cum', yscale='log')
    for ax in axs: ax.grid(alpha=.2)
    fig.suptitle('Algorithm 1 短程机理复现：每步重训 DCO，再更新 E/H', fontsize=13)
    fig.supxlabel('run #43 · dco_lr1e3_300 · n=31 · dt=3.075 ps · lr=1e-3 · max_inner=200 · 32 steps · 更新后重新计算loss', fontsize=9)
    save(fig, 'stage2_algorithm1_32.png')
    root = ROOT / 'evidence/stage2_mechanism_32'; root.mkdir(parents=True, exist_ok=True)
    report = root / 'STAGE_REPORT.md'
    report.write_text(f'''# 第二阶段短程机理复现：Algorithm 1 32步

**结论：逐时间步重训的核心机制已经跑通了短程版本。32步内场保持有限，末步 nMAE 为 {f['final_nmae']:.3e}，全程最大 {f['max_nmae']:.3e}。但论文要求的每步 `loss < 1e-4` 在当前实现中没有稳定满足，因此不能称为完整论文复现。**

## 设置

- run #43；初始化 `dco_lr1e3_300.pt`，不是冻结推理；采用更新后重新计算loss的修正版。
- 50 mm PEC 腔体，31 个间隔，`dt=3.075 ps`，为 CFL 的 0.99 倍；推进 32 步。
- 每步执行 curl-H 内层训练、更新 E、加入中心源、curl-E 内层训练、更新 H。
- 内层 Adam 学习率 `1e-3`，每个子步骤最多 200 次更新。第二阶段学习率是论文未披露的实现选择。

## 结果

| 检查 | 结果 |
|---|---:|
| 逐步记录与有限性 | 32/32 步，全部有限 |
| 平均内层次数 | curl-H {np.mean([r['itH'] for r in rows]):.1f}；curl-E {np.mean([r['itE'] for r in rows]):.1f} |
| nMAE | 末步 {f['final_nmae']:.3e}；全程最大 {f['max_nmae']:.3e} |
| curl-H 达到 1e-4 | {f['steps_hit_h']}/31 个非零子步 |
| curl-E 达到 1e-4 | {f['steps_hit_e']}/32 个子步 |
| 最大 curl-E loss | {f['max_loss_e']:.2e} |
| 最终累计内层损失 | {f['final_cum']:.3e} |

![32步证据](../../figs/stage2_algorithm1_32.png)

## 解释与限制

冻结模型的短程发散问题在这里没有出现，说明“每步重新拟合旋度”确实是稳定性的一个有效机制。这个结果不能外推为 8192 步稳定：内层损失仍波动，且最后一步 curl-E loss 升高。

    run #36 的低成本标定显示，`1e-3`、50 次内层更新的平均损失仍约 `1.85e-2`，`1e-2` 出现 NaN。run #37 把预算扩大到 200，4 步末 nMAE 为 `2.45e-5`，但停止条件仍未全面满足。run #46 将单个非零步预算扩大到500后，第2步 curl-E loss升至约 `9.88e2`，说明继续堆叠内层次数会触发优化不稳定，问题不是单纯预算不足。当前32步参数由这些预先运行的标定确定。

当前实现仍有明确偏差：相对平方损失替代了论文式（7）的绝对平方和；DCO 输出按共同立方区域裁剪；网络在 E/H 两类旋度之间共享。下一步应先核对这些接口与停止判定，再决定是否跑 64 或 128 步，不直接投入 8192 步。

## 追溯

- 原始逐步数据：[pidon_stage2_32_lr1e3_i200_postloss.json](../pidon_stage2_32_lr1e3_i200_postloss.json)，运行账本为 run #43。run #38为修正前历史轨迹。
- 标定与4步检查为 run #36、#37；轨迹复核为 run #39。
- 数值复核脚本：[stage2_evidence.py](../../stage2_evidence.py)。图脚本保存于本目录同名源文件。
''', encoding='utf-8')
    shutil.copy2(__file__, root / 'make_stage2_figs.py')
    dump(root / 'figures_manifest.json', {'run': 38, 'json_sha256': sha256(E.PATH),
        'script_sha256': sha256(__file__), 'report_sha256': sha256(report),
        'figures': {str(p.relative_to(ROOT)): sha256(p) for p in paths}})
    print('Saved', report)


if __name__ == '__main__': main()
