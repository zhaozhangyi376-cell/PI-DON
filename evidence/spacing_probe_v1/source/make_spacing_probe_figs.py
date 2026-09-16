"""Milestone 3 report and figures from the ledger's verified raw-array reader."""
from pathlib import Path
import sys
import shutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import verify_claims as V
from paper_recheck import dump,sha256

plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
 'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
COLORS=['#0072B2','#D55E00']
AXES='xyz'


def main():
    j,m,f=V.spacing_evidence();models=[v['tag'] for v in j['models']]
    root=ROOT/'evidence/spacing_probe_v1';out=ROOT/'figs';out.mkdir(exist_ok=True)
    source='run #23 · arrays.npz SHA256 '+j['arrays_sha256'][:12]
    paths=[]
    def save(fig,name):
        path=out/name;fig.savefig(path,dpi=180,bbox_inches='tight',facecolor='white');plt.close(fig);paths.append(path)
    fig,axs=plt.subplots(1,3,figsize=(13,4.8),layout='constrained')
    for axis,ax in enumerate(axs):
        pols=[p for p in range(3) if p!=axis]
        for mi,model in enumerate(models):
            for pi,pol in enumerate(pols):
                rs=sorted([r for r in f['trunk_effects'] if r['model']==model and r['axis']==axis and r['pol']==pol],key=lambda r:r['value'])
                ax.plot([r['value'] for r in rs],[100*r['relative_change'] for r in rs],
                        color=COLORS[mi],linestyle=['-','--'][pi],marker=['o','s'][mi],
                        label=model if pi==0 else None)
        ax.axhline(1,color='#777777',linestyle=':',label='1%门槛' if axis==0 else None)
        ax.set(title=f'沿 {AXES[axis]} 变化；实线 E{AXES[pols[0]]}，虚线 E{AXES[pols[1]]}',
               xlabel='极化方向的横向间距 s / mm',ylabel='仅换坐标输入导致的预测变化 / %')
        ax.grid(alpha=.2);ax.set_ylim(bottom=0)
    axs[0].legend(fontsize=8)
    fig.suptitle('坐标分支的直接干预：真实答案没变，网络输出却变了\n固定电场输入、输出还原及真实旋度；另一横向间距为 0.36/s mm，传播方向始终 0.6 mm',fontsize=12)
    fig.supxlabel(source+'；分母为真值 L2；单波结构探针，不是论文测试集',fontsize=9)
    save(fig,'spacing_probe_trunk.png')

    fig,axs=plt.subplots(1,3,figsize=(13,4.8),layout='constrained')
    for axis,ax in enumerate(axs):
        values=sorted(set(r['value'] for r in f['axis_sweep'] if r['axis']==axis))
        for mi,model in enumerate(models):
            groups=[[r['rel_l2']*100 for r in f['axis_sweep'] if r['model']==model and r['axis']==axis and r['value']==v] for v in values]
            ax.plot(values,[np.median(g) for g in groups],color=COLORS[mi],marker=['o','s'][mi],label=model)
            ax.fill_between(values,[min(g) for g in groups],[max(g) for g in groups],color=COLORS[mi],alpha=.15)
        yg=[[r['yee_rel_l2']*100 for r in f['axis_sweep'] if r['model']==models[0] and r['axis']==axis and r['value']==v] for v in values]
        ax.plot(values,[np.median(g) for g in yg],color='#444444',linestyle='--',label='标准 Yee 差分')
        ax.axvspan(.3,.8,color='#bbbbbb',alpha=.13)
        ax.set(title=f'只扫描 d{AXES[axis]}，其余两轴固定 0.6 mm',xlabel='间距 / mm',ylabel='中心ROI相对 L2 误差 / %',yscale='log')
        ax.grid(alpha=.2)
    axs[0].legend(fontsize=8)
    fig.suptitle('多波单轴扫描：网络误差与离散误差分别计算\n固定32³；折线为三个振幅种子的中位数，阴影为范围；灰色背景为默认训练间距范围',fontsize=12)
    fig.supxlabel(source+'；解析旋度为共同真值，Yee 是对照而非误差下限',fontsize=9)
    save(fig,'spacing_probe_axis.png')

    fig,axs=plt.subplots(1,3,figsize=(13,4.8),layout='constrained')
    for axis,ax in enumerate(axs):
        pols=[p for p in range(3) if p!=axis]
        for mi,model in enumerate(models):
            for pi,pol in enumerate(pols):
                rs=sorted([r for r in f['plane_sweep'] if r['family']=='fixed_q' and r['model']==model
                           and r['axis']==axis and r['pol']==pol],key=lambda r:r['value'])
                ax.plot([r['value'] for r in rs],[r['active_gain'] for r in rs],color=COLORS[mi],
                        linestyle=['-','--'][pi],marker=['o','s'][mi],label=model if pi==0 else None)
        ax.axhline(1,color='#444444',linestyle=':',label='解析理想值=1')
        ax.set(title=f'沿 {AXES[axis]} 变化；实线 E{AXES[pols[0]]}，虚线 E{AXES[pols[1]]}',
               xlabel='传播方向间距 / mm',ylabel='预测在真值波形上的投影增益')
        ax.grid(alpha=.2)
    axs[0].legend(fontsize=8)
    fig.suptitle('固定每格相位变化 q=0.18：输入张量完全相同，真值幅度应按 1/d 缩放\n增益=〈预测活动分量, 真值〉/〈真值, 真值〉；增益接近1仍不保证无波形偏差或其他分量泄漏',fontsize=12)
    fig.supxlabel(source,fontsize=9)
    save(fig,'spacing_probe_scaling.png')

    lines=['# 里程碑3：单轴间距、单波与坐标分支诊断','',
        '**已得到直接模块定位：在单波探针中，只改变坐标分支输入就引入了物理上不该有的横向间距依赖。多波案例的网络误差也明显大于标准Yee差分误差。模型尚未修复，论文精度验收仍未通过。**','',
        '## 本轮实际做了什么','',
        'run #23：231个场景×2个原有权重，共462次冻结推理。所有场景32³，比较中心8³，权重前后SHA256一致。run #24复算全部指标并重跑9项回归，P2继续保留FAIL。',
        '三类对照：①原20波场，分别扫描dx/dy/dz为0.2、0.3、0.4、0.6、0.8、1.0、1.2mm，并补四格组合；②六种方向/极化单波，固定物理波数200或800m⁻¹，或固定每格相位变化q=0.18；③只改变坐标分支的横向间距输入。所有数值和S0–S2门槛在运行前写入manifest.json。','',
        '## 1. 可排除的数值混淆','',
        '对每个平面波，标准Yee差分将连续导数系数kᵢ替换为 2sin(kᵢdᵢ/2)/dᵢ；相位仍在对应H/Yee位置。这个解析离散表达与从输入场直接作差分相互核验，绕回边界不进入中心评分区。',
        f'全场景恒等式核查最大相对偏差为{max(j["checks"].values()):.3e}。固定q的输入张量一致，真值乘传播方向间距后也一致；trunk-only输入和真值的差异均为0。','',
        '## 2. 标准差分误差不足以解释原间距下的偏差','',
        '| 模型 | 振幅种子 | DCO相对L2误差 | Yee相对L2误差 | DCO/Yee误差比 |',
        '|---|---:|---:|---:|---:|']
    for r in f['interaction']:
        if r['variant']=='both':lines.append(f'| {r["model"]} | {r["seed"]} | {r["rel_l2"]:.5f} | {r["yee_rel_l2"]:.5f} | {r["network_over_yee"]:.2f} |')
    lines+=['','以上固定32³、间距(0.3,0.2,1.2)mm，同一解析真值与中心ROI。六组都超过预设5倍门槛。不能把Yee误差叫作网络误差下限：网络的目标是解析旋度，理论上可以超过有限差分精度。','',
        '![单轴扫描](../../figs/spacing_probe_axis.png)','',
        '## 3. 细间距、粗间距和组合效应','',
        '基准为(0.3,0.3,0.6)mm；仅细化y为(0.3,0.2,0.6)，仅粗化z为(0.3,0.3,1.2)，合并为(0.3,0.2,1.2)。下面都用同一种子的DCO相对L2误差除以该基准误差。','',
        '| 模型 | 仅细化y：误差比范围 | 仅粗化z：误差比范围 | 同时改变：误差比范围 |',
        '|---|---:|---:|---:|']
    for model in models:
        cells=[]
        for variant in ['fine','coarse','both']:
            vals=[r['ratio_to_base'] for r in f['interaction'] if r['model']==model and r['variant']==variant]
            cells.append(f'{min(vals):.2f}–{max(vals):.2f}')
        lines.append('| '+model+' | '+' | '.join(cells)+' |')
    lines+=['','范围覆盖三个振幅种子，不是置信区间；间距变化也改变物理采样和窗口。各轴效应可不同，不能用一条“超范围就会同样变差”的规则解释，也不能把这些误差比与上一轮nMAE误差比直接拼接。','',
        '## 4. 只干预trunk：已经定位到一个具体失效机制','',
        '让E只沿一个坐标轴变化，且仅有一个横向电场分量。传播方向间距固定0.6mm；两个横向间距取s和0.36/s mm，使其乘积不变。此时电场、解析旋度、网格形状和几何平均间距均不变。',
        '推理时进一步直接复用0.6mm基准的归一化branch输入与输出还原因子，唯一变化是trunk的三个间距通道。因此下表输出变化可归因于坐标输入路径，而不只是两个实验的相关性。变化量除以真值L2范数。','',
        '| 模型 | 传播轴 | 电场分量 | 五种横向间距中的最大预测变化 |','|---|---|---|---:|']
    for model in models:
        for axis in range(3):
            for pol in [p for p in range(3) if p!=axis]:
                vals=[r['relative_change'] for r in f['trunk_effects'] if r['model']==model and r['axis']==axis and r['pol']==pol]
                lines.append(f'| {model} | {AXES[axis]} | E{AXES[pol]} | {100*max(vals):.2f}% |')
    lines+=['','十二种组合全部超过预设1%门槛。上表报告预先定义的最大干预效应，下面给出全部五种设置的曲线，包括0.6mm参考点的零变化。','',
        '![坐标分支直接干预](../../figs/spacing_probe_trunk.png)','',
        '**适用边界：**单平面波、轴向传播与单分量极化可能不在旧训练分布内。这证明当前网络在这些结构探针上的错误依赖，不等于论文宣称在这些场景达标，也不证明Fig.6多波误差全部来自trunk。横向间距改变了计算窗口，但branch场张量、shape和输出还原固定，故该干预内的输出差异仍只能经坐标路径进入。','',
        '## 5. 相同输入能否按正确长度单位缩放','',
        '固定q=k·d=0.18，调整k使每个输入体素完全相同，真值幅度应按1/d变化；k在150–900m⁻¹之间。这排除了输入波形改变导致的混淆。物理固定波数200/800m⁻¹的对照也保存在完整数据中。','',
        '![相同输入的长度缩放](../../figs/spacing_probe_scaling.png)','',
        '| 模型 | 单波组 | 相对L2误差范围（全部方向/极化/间距） |',
        '|---|---|---:|']
    for model in models:
        for family in ['physical200','physical800','fixed_q']:
            vals=[r['rel_l2'] for r in f['plane_sweep'] if r['model']==model and r['family']==family]
            lines.append(f'| {model} | {family} | {min(vals):.4f}–{max(vals):.4f} |')
    lines+=['','单波中有严格为零的旋度分量，因此此处用向量相对L2、活动分量投影增益和非活动分量泄漏分析；不把它们改称论文MRE。增益接近1也不保证预测准确，完整波形误差和泄漏见findings.json。','',
        '## 下一步建议：进入有限预算的修复对照','',
        '不再进行无目的的全参数扫描。建议以dco_lr1e3_300为共同起点，保持结构、编码和损失不变，先只比较训练间距覆盖：A保留0.3–0.8mm，B扩为0.2–1.2mm；两组使用相同波场抽样、样本数量、更新次数和学习率，最多各200次更新。',
        '验收沿用固定的Fig.6重建测试和本轮坐标干预探针，同时报告原范围内是否退步；用独立振幅种子作为未参与选择的验证数据。先固定具体门槛与预算，再运行。若无改善，再考虑坐标表达或结构约束，不能同时修改多个因素后声称某一项有效。',
        '**扩展间距属于诊断增强版，不能替代论文原训练范围下的严格复现。**这个A/B实验要回答“数据覆盖能否修复已定位的错误依赖”，不承诺训练后必然达标。按用户要求，本轮到此停下验收，尚未开始这两组训练。','',
        '## 追溯','',
        '- arrays.npz：231个场景的中心输入/真值/Yee对照及462组预测。',
        '- manifest.json：原始参数、预设门槛、环境和source/快照哈希；summary.json：权重身份、数值检查与运行指标。',
        '- findings.json与verification_manifest.json：结论复算；图与本报告共用verify_claims.spacing_evidence。',
        '- 图脚本：slides/make_spacing_probe_figs.py；原始诊断脚本：spacing_probe.py。',
        '- RESULTS.md的S项通过表示诊断证据支持陈述；P2仍FAIL，模型没有通过论文精度验收。','']
    report=root/'STAGE_REPORT.md';report.write_text('\n'.join(lines),encoding='utf-8')
    shutil.copy2(__file__,root/'source'/'make_spacing_probe_figs.py')
    dump(root/'figures_manifest.json',dict(source_run=23,arrays_sha256=j['arrays_sha256'],
        script_sha256=sha256(__file__),report_sha256=sha256(report),
        figures={str(p.relative_to(ROOT)):sha256(p) for p in paths}))
    print('Saved 3 figures and',report)
    for model in models:
        print(model, {v:[round(r['ratio_to_base'],4) for r in f['interaction'] if r['model']==model and r['variant']==v] for v in ['fine','coarse','both']})


if __name__=='__main__':main()
