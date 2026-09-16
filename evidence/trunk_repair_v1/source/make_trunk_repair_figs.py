"""Milestone 5 report/figures using the same verified reader as U0-U3."""
from pathlib import Path
import json
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import trunk_evidence as T
from paper_recheck import dump,sha256

plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
    'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
TAGS=['A0','A200','B200','C200'];COLORS=['#555555','#0072B2','#D55E00','#009E73']


def main():
    j,m,f=T.read();root=ROOT/T.ROOT;out=ROOT/'figs';out.mkdir(exist_ok=True);paths=[]
    gm=f['geomeans'];ratios=f['ratios'];cube=f['cube_means'];probe=f['probe_mean_maximum']
    source='run #33 · heldout/evaluation.npz SHA256 '+j['heldout']['arrays_sha256'][:12]
    def save(fig,name):
        p=out/name;fig.savefig(p,dpi=180,bbox_inches='tight',facecolor='white');plt.close(fig);paths.append(p)
    fig,axs=plt.subplots(1,3,figsize=(15,5.1),layout='constrained')
    x=np.arange(6)
    for key,label,color,marker in [('C200_over_A200_nmae','分量平均 nMAE','#0072B2','o'),
                                  ('C200_over_A200_mre','x 分量式(5) MRE','#D55E00','s')]:
        axs[0].plot(x,[r[key] for r in ratios],marker=marker,color=color,label=label)
    axs[0].axhline(.8,color='#008855',linestyle='--',label='两个比值均须≤0.8')
    axs[0].axhline(1,color='#999999',linestyle=':')
    axs[0].set_xticks(x,[f"s{r['seed']}\n{r['size']}" for r in ratios],fontsize=7)
    axs[0].set(title='U1 未通过：nMAE改善不足',ylabel='新种子非立方误差比 C200 / A200',ylim=(0,1.3))
    axs[0].text(.02,.97,f"六案例几何平均比：\nnMAE {gm['C200_over_A200_nmae']:.4f}；MRE {gm['C200_over_A200_mre']:.4f}",
                transform=axs[0].transAxes,va='top',fontsize=9)
    axs[0].legend(fontsize=8,loc='lower right')
    axs[1].bar(TAGS,[100*cube[t] for t in TAGS],color=COLORS,alpha=.72)
    allvals=[]
    for i,tag in enumerate(TAGS):
        vals=[100*r['metrics']['macro_nmae'] for r in j['heldout']['rows'] if r['model']==tag and r['size']=='32x32x32']
        allvals+=vals
        axs[1].scatter(i+np.linspace(-.12,.12,3),vals,color='black',s=18,zorder=3)
        axs[1].text(i,100*cube[tag]+.012,f'{100*cube[tag]:.4f}%',ha='center',fontsize=9)
    axs[1].axhline(110*cube['A0'],color='#008855',linestyle='--',label='C允许上限：A0 × 1.1')
    axs[1].set(title=f"U2 未通过：C误差仍为起点的 {f['cube_C_over_initial']:.2f} 倍",
               ylabel='新种子32³ 分量平均 nMAE / %',ylim=(0,max(allvals)*1.4),xlabel='柱：三个种子平均；点：各个种子')
    axs[1].legend(fontsize=8,loc='upper left')
    pairs=[(a,p) for a in range(3) for p in range(3) if a!=p]
    for tag,color in zip(TAGS,COLORS):
        vals=[100*next(r['maximum'] for r in f['probe_maxima'] if (r['model'],r['axis'],r['pol'])==(tag,a,p)) for a,p in pairs]
        axs[2].plot(range(6),vals,marker='o',color=color,label=tag)
    axs[2].set_xticks(range(6),[f"沿{'xyz'[a]} / E{'xyz'[p]}" for a,p in pairs],rotation=25,fontsize=8)
    axs[2].set(title='U3 通过：错误坐标依赖比起点减轻',ylabel='已知探针：每方向最大干预效应 / %',ylim=(0,25))
    axs[2].text(.02,.98,f"最大效应的六方向平均：\nA0 {100*probe['A0']:.2f}%；B {100*probe['B200']:.2f}%；C {100*probe['C200']:.2f}%",
                transform=axs[2].transAxes,va='top',fontsize=9)
    axs[2].legend(fontsize=8,loc='upper right',bbox_to_anchor=(1,.79))
    for ax in axs:ax.grid(axis='y',alpha=.2)
    fig.suptitle('只训练坐标分支：退步有所减轻，整体修复仍未通过\nA0：起点；A：原间距全模型更新；B：扩展间距全模型更新；C：扩展间距仅trunk更新；各200次',fontsize=12)
    fig.supxlabel(source+'；左/中：新种子20/21/22；右：已知单波探针（A/B复用run #27）',fontsize=8)
    save(fig,'trunk_repair_outcomes.png')

    fig,ax=plt.subplots(figsize=(9,4),layout='constrained')
    for tag,color,r in [('B200',COLORS[2],ROOT/'evidence/coverage_ab_v1'),('C200',COLORS[3],root)]:
        hist=json.loads((r/(tag+'_hist.json')).read_text(encoding='utf-8'))
        losses=np.array([v['loss_before_update'] for v in hist['updates']])
        ax.plot(range(10,201,10),losses.reshape(20,10).mean(1),color=color,marker='o',markersize=3,label=tag)
    ax.set(xlabel='参数更新次数',ylabel='每10次更新前训练损失的平均',yscale='log',
           title='相同B数据与batch顺序：全模型更新B、仅坐标分支更新C\n训练损失描述拟合过程，模型优劣以独立验收为准')
    ax.grid(alpha=.2);ax.legend()
    fig.supxlabel('B：run #27；C：run #33；各自_hist.json完整保存200条记录',fontsize=9)
    save(fig,'trunk_repair_training.png')

    lines=['# 里程碑5：仅坐标分支更新的阶段验收','',
        '**本轮整体修复仍未通过。C比全模型更新B保留了更多原范围精度，但原范围误差仍高于起点，非立方nMAE改善未达门槛。原模型继续保留为基线，不将C提升为替代模型。**','',
        '## 实验与完整性','',
        '用户确认后执行预先保存的NEXT_TRUNK_PLAN.md。run #33正式训练C200：同一原权重、直接复用B的128组数据和200×4 batch序列，新建Adam lr=1e-4，仅trunk参数允许更新。没有修改架构、cellsize、RMS或相对平方损失，没有追加训练或进入Algorithm 1。','',
        f"从保存的权重重新核对：{f['frozen_tensors']}个非trunk张量（{f['frozen_parameters']:,}个参数）逐项完全相同；{f['active_tensors']}个trunk张量（{f['active_parameters']:,}个参数）都发生变化，且优化器计数均恰为200。运行前后原模型及B数据哈希不变。",'',
        '13项检查通过，包括用实际训练辅助函数在临时微型网络上检查冻结是否生效。run #32和run #33开头的微型测试训练日志不是正式DCO训练；临时模型已由测试框架清理。正式C200的200次更新以保存的优化器状态与C200_hist.json为准，耗时见summary.json。','',
        '评估在正式训练完成后进行：C补测已知种子10/11/12的12组网格和30组探针；新种子20/21/22统一评估A0/A200/B200/C200，共48组完整预测。已知种子不再称独立验收。四模型均使用相同输入与真值，未按测试结果挑选checkpoint。','',
        '## 运行前门槛与结果','',
        '| 项目 | 预设门槛 | 实测 | 判定 |','|---|---|---:|---|',
        f"| U1 新种子六非立方案例C/A的nMAE比和x-MRE比，各取几何平均 | 两者均≤0.8 | {gm['C200_over_A200_nmae']:.4f}；{gm['C200_over_A200_mre']:.4f} | FAIL |",
        f"| U2 新种子32³平均nMAE，C/A0 | ≤1.1 | {f['cube_C_over_initial']:.4f} | FAIL |",
        f"| U3 六方向最大坐标干预效应的平均，C/A0 | ≤1 | {f['probe_C_over_initial']:.4f} | PASS |",'',
        'U0完整性通过；U1要求两个指标同时达标，所以MRE单项通过仍不能使U1通过。式（5）逐点MRE与分量平均nMAE分别报告；坐标干预效应是真值L2归一化预测差，不是场误差。','',
        '![本轮证据](../../figs/trunk_repair_outcomes.png)','',
        '## 证据允许的解释','',
        f"1. 相对原范围对照A，C的非立方nMAE比几何平均降低{100*(1-gm['C200_over_A200_nmae']):.2f}%，x-MRE比降低{100*(1-gm['C200_over_A200_mre']):.2f}%。nMAE未达到20%要求。", 
        f"2. 在同一批新种子上，32³平均nMAE：A0={cube['A0']:.7f}，A={cube['A200']:.7f}，B={cube['B200']:.7f}，C={cube['C200']:.7f}。B/A0={cube['B200']/cube['A0']:.4f}，C/A0={f['cube_C_over_initial']:.4f}；C相对B减少了退步，但仍比起点高{100*(f['cube_C_over_initial']-1):.2f}%。不能把旧种子的B数值与新种子的C数值直接作受控比较。",
        f"3. 新种子非立方C/B比几何平均：nMAE为{gm['C200_over_B200_nmae']:.4f}，x-MRE为{gm['C200_over_B200_mre']:.4f}。C优于B的这两项平均值不等于每个案例都改善；逐例比值完整列在下表。",
        f"4. 错误坐标依赖平均最大效应：A0 {100*probe['A0']:.2f}%，B {100*probe['B200']:.2f}%，C {100*probe['C200']:.2f}%。C比起点减轻，但比B更强；不存在所有指标同时领先的模型。",'',
        '**通俗解释：只让负责读取格子尺寸的部分学习，确实少破坏了一些原有能力；但这个部分通过乘法影响整个网络输出，所以“其余参数没变”并不意味着“原来的答案不变”。**','',
        '这是当前实现、一个训练随机种子和200次更新下的受控对照。不能据此证明所有坐标分支训练都无效，也不能证明trunk是全部误差的唯一根因。扩展数据不是论文原训练设置；Fig.5/6重建仍包含实部/零相位、振幅与Yee采样等声明假设。','',
        '## 新种子非立方逐例比值','',
        '| 种子 | 网格 | C/A nMAE | C/A MRE | C/B nMAE | C/B MRE | B/A0 nMAE | B/A0 MRE |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    keys=['C200_over_A200_nmae','C200_over_A200_mre','C200_over_B200_nmae','C200_over_B200_mre',
          'B200_over_A0_nmae','B200_over_A0_mre']
    for r in ratios:lines.append(f"| {r['seed']} | {r['size']} | "+' | '.join(f'{r[k]:.5f}' for k in keys)+' |')
    for title,rows,seeds in [('新种子终验全部结果',j['heldout']['rows'],[20,21,22]),
                             ('已知种子诊断全部结果',f['diagnostic_rows'],[10,11,12])]:
        lines+=['',f'## {title}','','单元格为分量平均nMAE / x分量式（5）MRE；其他分量保留在summary.json和原始数组中。','',
                '| 种子 | 网格 | A0 | A200 | B200 | C200 |','|---|---|---:|---:|---:|---:|']
        for seed in seeds:
            for shape in ['32x32x32','64x64x64','64x96x16','32x64x16']:
                vals=[next(r['metrics'] for r in rows if (r['model'],r['seed'],r['size'])==(tag,seed,shape)) for tag in TAGS]
                lines.append(f'| {seed} | {shape} | '+' | '.join(f"{v['macro_nmae']:.6f} / {v['components']['x']['mre_eq5']:.6f}" for v in vals)+' |')
    lines+=['','## 训练记录与追溯','','![训练过程](../../figs/trunk_repair_training.png)','',
        '- run #33：正式训练及推理；run #34：独立复核13项检查、权重与数组；返回1是U1/U2及此前门槛未通过，不是程序崩溃。',
        '- manifest.json：运行前门槛、源快照、原模型与复用数据哈希、batch顺序。批准方案原样存于source/NEXT_TRUNK_PLAN.md。',
        '- C200.pt包含优化器状态；C200_hist.json含200条记录；training_summary.json为训练完成时的中间记录。',
        '- heldout/evaluation.npz保存48组新种子完整预测；diagnostic/evaluation.npz保存C的12组已知种子预测和30组探针；旧A0/A/B诊断数据复用coverage_ab_v1。',
        '- trunk_evidence.py和verify_claims.py共同计算U0–U3；本图脚本直接调用同一读取器，不从日志摘要抓数。',
        '- findings.json与verification_manifest.json保存复算结果及源码哈希；figures_manifest.json保存图/报告/脚本及数据哈希。历史T1/T2失败、P2未通过及C7反例均保留。','',
        '## 停止点与建议','',
        '本轮已达到用户要求的阶段停止点。保留原模型，不追加训练，不进入Algorithm 1。建议下一阶段先回到论文核对坐标表达和逐分量归一化，形成“原文依据—当前代码—未确认假设—最小对照”的逐项清单；仅做推导与接口检查，不开始新训练。两轮有限预算修复的结果不足以证明整个方向无效，但也不足以支持直接投入更长训练。等待用户验收确认。','']
    report=root/'STAGE_REPORT.md';report.write_text('\n'.join(lines),encoding='utf-8')
    shutil.copy2(__file__,root/'source'/Path(__file__).name)
    dump(root/'figures_manifest.json',dict(source_run=33,
        heldout_sha256=j['heldout']['arrays_sha256'],diagnostic_sha256=j['diagnostic']['arrays_sha256'],
        reader_sha256=sha256(T.__file__),script_sha256=sha256(__file__),report_sha256=sha256(report),
        figures={str(p.relative_to(ROOT)):sha256(p) for p in paths}))
    print('Saved two evidence figures and',report)


if __name__=='__main__':main()
