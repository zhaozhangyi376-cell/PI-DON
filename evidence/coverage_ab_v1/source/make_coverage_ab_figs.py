"""Generate milestone 4 evidence from the same raw-array reader as RESULTS."""
from pathlib import Path
import json
import shutil
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import verify_claims as V
from paper_recheck import dump, sha256

plt.rcParams.update({'font.sans-serif': ['Microsoft YaHei', 'DejaVu Sans'],
    'axes.unicode_minus': False, 'font.size': 10,
    'axes.spines.top': False, 'axes.spines.right': False})
COLORS = ['#555555', '#0072B2', '#D55E00']
TAGS = ['A0', 'A200', 'B200']


def main():
    j, m, f = V.coverage_evidence()
    root = ROOT / 'evidence/coverage_ab_v1'
    out = ROOT / 'figs'
    out.mkdir(exist_ok=True)
    paths = []
    source = 'run #27 · evaluation.npz SHA256 ' + j['arrays_sha256'][:12]

    def save(fig, name):
        path = out / name
        fig.savefig(path, dpi=180, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        paths.append(path)

    fig, axs = plt.subplots(1, 3, figsize=(15, 5.1), layout='constrained')
    rs = f['noncubic_ratios']
    x = np.arange(len(rs))
    for key, label, color, marker in [
        ('nmae_B_over_A', '分量平均 nMAE', COLORS[1], 'o'),
        ('mre_B_over_A', 'x 分量式(5) MRE', COLORS[2], 's')]:
        axs[0].plot(x, [r[key] for r in rs], marker=marker, color=color, label=label)
    axs[0].axhline(.8, color='#008855', linestyle='--', label='验收要求 ≤0.8')
    axs[0].axhline(1, color='#999999', linestyle=':')
    axs[0].set_xticks(x, [f"s{r['seed']}\n{r['size']}" for r in rs], fontsize=7)
    axs[0].set(title='T1 未通过：非立方改善不足', ylabel='B200 / A200 误差比值（越低越好）',
               ylim=(.55, 1.16))
    axs[0].legend(fontsize=8, loc='lower right')
    axs[0].text(.02, .96, f"六案例几何平均：\nnMAE {f['geomean_nmae_B_over_A']:.4f}；MRE {f['geomean_mre_B_over_A']:.4f}",
                transform=axs[0].transAxes, va='top', fontsize=9)
    cube = [f['cube_means'][tag]*100 for tag in TAGS]
    axs[1].bar(TAGS, cube, color=COLORS, alpha=.72)
    for i, tag in enumerate(TAGS):
        vals = [r['metrics']['macro_nmae']*100 for r in j['rows']
                if r['model'] == tag and r['size'] == '32x32x32']
        axs[1].scatter(i + np.linspace(-.12, .12, 3), vals, color='black', s=18, zorder=3)
        axs[1].text(i, cube[i]+.012, f'{cube[i]:.4f}%', ha='center', fontsize=9)
    axs[1].axhline(cube[0]*1.1, color='#008855', linestyle='--', label='B允许上限：A0 × 1.1')
    axs[1].set(title=f"T2 未通过：B误差为起点的 {f['cube_B_over_initial']:.2f} 倍",
               ylabel='32³ 分量平均 nMAE / %（越低越好）', ylim=(0, max(cube)*1.35))
    axs[1].legend(fontsize=8, loc='upper left')
    axs[1].set_xlabel('柱：三个种子的平均；点：各个种子')
    pairs = [(a, p) for a in range(3) for p in range(3) if a != p]
    for tag, color in zip(TAGS, COLORS):
        vals = [100*next(r['maximum'] for r in f['probe_maxima']
                        if (r['model'], r['axis'], r['pol']) == (tag, a, p)) for a, p in pairs]
        axs[2].plot(range(6), vals, marker='o', color=color, label=tag)
    axs[2].set_xticks(range(6), [f"沿{'xyz'[a]} / E{'xyz'[p]}" for a, p in pairs], rotation=25, fontsize=8)
    axs[2].set(title='T3 通过：错误坐标依赖减轻',
               ylabel='每方向最大干预效应 / %（越低越好）', ylim=(0, 25))
    axs[2].text(.02, .98, '六方向最大值的平均：\n' + ' → '.join(
        f"{f['probe_mean_maximum'][tag]*100:.2f}%" for tag in TAGS),
        va='top', transform=axs[2].transAxes, fontsize=9)
    axs[2].legend(fontsize=8, loc='upper right', bbox_to_anchor=(1, .78))
    for ax in axs:
        ax.grid(axis='y', alpha=.2)
    fig.suptitle('扩大间距覆盖：局部依赖改善，整体修复未通过\nA0：原模型；A200：0.3–0.8 mm；B200：0.2–1.2 mm；两组各200次更新', fontsize=13)
    fig.supxlabel(source + '；测试种子10/11/12，单波干预效应不是场误差', fontsize=9)
    save(fig, 'coverage_ab_outcomes.png')

    fig, axs = plt.subplots(1, 2, figsize=(10, 4), layout='constrained')
    for ax, tag, color in zip(axs, TAGS[1:], COLORS[1:]):
        h = json.loads((root / (tag+'_hist.json')).read_text(encoding='utf-8'))
        losses = np.array([r['loss_before_update'] for r in h['updates']])
        ax.plot(range(1, 201), losses, color=color, alpha=.25, linewidth=.8, label='每次更新前batch损失')
        ax.plot(range(10, 201, 10), losses.reshape(20, 10).mean(axis=1), color=color, label='每10次平均')
        ax.set(title=tag, xlabel='参数更新次数', ylabel='逐样本相对平方损失', yscale='log')
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    fig.suptitle('训练过程记录：预算固定为每组200次\n两组训练间距不同，损失曲线不能用于判断谁的测试精度更高', fontsize=12)
    fig.supxlabel('run #27 · A200_hist.json / B200_hist.json；完整200条记录及SHA256见summary.json', fontsize=9)
    save(fig, 'coverage_ab_training.png')

    lines = ['# 里程碑4：间距覆盖A/B修复验收', '',
        '**本轮整体修复未通过。扩大间距范围减轻了单波探针的错误坐标依赖，但非立方精度改善不足，原范围内32³精度退步。保留原模型作为基线，不将B200提升为替代模型。**', '',
        '## 已完成的实验', '',
        '用户批准的NEXT_AB_PLAN.md保持原样。run #26通过3项训练实现检查；run #27从同一原权重开始，完成A/B各200次Adam更新，再统一评估A0/A200/B200。共36组完整网格预测、90组单波坐标干预探针；12项检查通过。实际优化器计数也核验为每组200，没有追加训练或运行Algorithm 1。', '',
        '- A200：每轴间距U[0.3,0.8]mm；B200：每轴U[0.2,1.2]mm。',
        '- 各128组32³配对波场，随机种子20260915，相同波参数与间距随机数、相同batch索引；batch=4，Adam lr=1e-4，均重建优化器，不继承旧动量。',
        '- 架构、cellsize输入、RMS及相对平方损失均不变。扩大覆盖会改变实际波场采样与训练目标，是本次唯一受控处理。',
        '- 验收振幅种子10/11/12在两组训练结束后一次性使用；固定19.2mm窗口、四种网格。实部、零相位、振幅与Yee采样等仍为公开参数下的声明假设，不是作者原始数据。',
        '- B是诊断增强版，不是论文原训练设置的严格复现。', '',
        '## 预设门槛与结果', '',
        '| 验收项 | 运行前门槛 | 实测 | 结论 |', '|---|---|---:|---|',
        f"| T1 非立方六案例B/A的nMAE比、x-MRE比分别取几何平均 | 两者均≤0.8 | {f['geomean_nmae_B_over_A']:.4f}；{f['geomean_mre_B_over_A']:.4f} | FAIL |",
        f"| T2 32³三种子平均nMAE，B/A0 | ≤1.1 | {f['cube_B_over_initial']:.4f} | FAIL |",
        f"| T3 六种方向各自最大坐标干预效应的平均，B/A0 | ≤1 | {f['probe_B_over_initial']:.4f} | PASS |", '',
        'T0证据完整性通过不代表精度达标。式（5）MRE严格按逐点分支计算；nMAE先按分量最大真值归一化MAE，再等权平均三个分量。坐标干预效应是真值L2归一化的预测差，不是场误差。', '',
        '![本轮验收](../../figs/coverage_ab_outcomes.png)', '',
        '## 如何理解这个结果', '',
        f"扩大范围后，B对A的非立方误差比几何平均分别下降{100*(1-f['geomean_nmae_B_over_A']):.2f}%（nMAE）和{100*(1-f['geomean_mre_B_over_A']):.2f}%（x-MRE），均未达到20%要求。下表保留了误差变大的案例，不能将平均改善说成每个案例都改善。", '',
        f"32³平均nMAE：A0={f['cube_means']['A0']:.7f}，A200={f['cube_means']['A200']:.7f}，B200={f['cube_means']['B200']:.7f}。原范围对照A也比起点退步{100*(f['cube_means']['A200']/f['cube_means']['A0']-1):.2f}%；因此不能把B相对起点的全部退步都归因于范围扩展。继续训练本身也改变了原来的能力；B/A的受控比较才能衡量本次范围处理的额外作用。", '',
        f"坐标错误依赖的平均最大效应从A0的{100*f['probe_mean_maximum']['A0']:.2f}%变为A的{100*f['probe_mean_maximum']['A200']:.2f}%、B的{100*f['probe_mean_maximum']['B200']:.2f}%。这说明该依赖在当前设置下可以被训练减轻，但尚未消除，也不能据此断言Fig.6精度恢复。", '',
        '**直观解释：补充不同格子尺寸的训练后，模型对尺寸变化的一部分错误反应减弱了，但它在原来熟悉的格子上答得更差。单项缺陷减轻与整体模型变好是两件需要分别验收的事。**', '',
        '## 六个非立方案例（比值越小越好）', '',
        '| 种子 | 网格 | nMAE B/A | x-MRE B/A | nMAE B/A0 | x-MRE B/A0 |', '|---|---|---:|---:|---:|---:|']
    for r in rs:
        lines.append(f"| {r['seed']} | {r['size']} | {r['nmae_B_over_A']:.5f} | {r['mre_B_over_A']:.5f} | {r['nmae_B_over_initial']:.5f} | {r['mre_B_over_initial']:.5f} |")
    lines += ['', '## 全部网格精度（单元格为分量平均nMAE / x分量MRE）', '',
        '| 种子 | 网格 | A0 | A200 | B200 |', '|---|---|---:|---:|---:|']
    for seed in [10, 11, 12]:
        for shape in ['32x32x32', '64x64x64', '64x96x16', '32x64x16']:
            vals = [next(r['metrics'] for r in j['rows'] if (r['model'], r['seed'], r['size']) == (tag, seed, shape)) for tag in TAGS]
            lines.append(f'| {seed} | {shape} | ' + ' | '.join(f"{v['macro_nmae']:.6f} / {v['components']['x']['mre_eq5']:.6f}" for v in vals) + ' |')
    lines += ['', '全部逐分量指标见summary.json；图表使用verify_claims.coverage_evidence直接从evaluation.npz复算。', '',
        '## 过程、限制与停止点', '', '![训练记录](../../figs/coverage_ab_training.png)', '',
        '每组只有一个训练随机种子、200次更新；三个振幅种子也不是全面的方向/波数泛化测试。这次FAIL只否定“此配置、此预算已完成修复”，不能证明扩大覆盖普遍无效。损失下降不能代替独立验收，继续加轮次的收益本轮没有测试。', '',
        '建议下一步检查：同样扩展数据和200次预算，只允许坐标分支更新，冻结其余模块，能否保留原范围精度。这是可检验的模块对照，不保证有效；具体设置与门槛见NEXT_TRUNK_PLAN.md。按用户要求，本轮到此停止，等待验收，不执行该方案。', '',
        '## 追溯', '',
        '- 原始实验：LAB_NOTEBOOK.md / lab_runs.jsonl 的run #27；原权重SHA256为'+m['initial_sha256']+'，训练前后不变。',
        '- manifest.json保存运行前门槛、全量波场参数、batch索引与源快照哈希；train_A200.npz/train_B200.npz为训练数据。',
        '- A200.pt/B200.pt独立保存权重与优化器状态；各自_hist.json含200条记录。训练用时与所有产物哈希见summary.json。',
        '- evaluation.npz保存36组完整预测、输入/真值及90组探针；findings.json为复算派生值。',
        '- run #28验收因科学门槛FAIL返回退出码1，不是训练崩溃。它的日志自动摘要将T1的0.9420误抓成“nMAE”；该值实际为B/A几何平均比，不能当绝对误差。保留原日志，并调整后续输出文本避免同类误抓。',
        '- 最终复核首次尝试在lab_log转发输出时触发GBK UnicodeEncodeError，未写入运行账本；固定PYTHONIOENCODING=utf-8后重试。该包装器异常与训练失败或科学门槛FAIL不同；详细错误记录见FINAL_CHECK_ENCODING_NOTE.md。',
        '- RESULTS.md保留此前P/D/S与历史反例，并加入T0–T3；本轮数值以原始数组复算为准。',
        '- slides/make_coverage_ab_figs.py生成本报告和图，figures_manifest.json记录其哈希。', '']
    report = root / 'STAGE_REPORT.md'
    report.write_text('\n'.join(lines), encoding='utf-8')
    shutil.copy2(__file__, root / 'source' / Path(__file__).name)
    dump(root / 'figures_manifest.json', dict(source_run=27, arrays_sha256=j['arrays_sha256'],
        script_sha256=sha256(__file__), report_sha256=sha256(report),
        figures={str(p.relative_to(ROOT)): sha256(p) for p in paths}))
    print('Saved two figures and', report)


if __name__ == '__main__':
    main()
