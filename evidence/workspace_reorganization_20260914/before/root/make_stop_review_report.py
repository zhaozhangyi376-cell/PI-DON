"""Chinese review report and standalone figure from the same audited JSON."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from stop_review_evidence import ROOT, engineering_status, load_review


def main():
    a, ref, layout = load_review()
    report_path = ROOT / 'STOP_REVIEW.md'
    figure_path = ROOT / 'stop_evidence.png'
    if report_path.exists() or figure_path.exists():
        raise FileExistsError('Preserve existing report/figure; use a separately registered revision')
    fits = a['assets']['saved_fits']
    status, failures = engineering_status()
    rows = '\n'.join(f"| {x['name']} | {x['record_updates']} | {x['record_lbfgs_steps']} / {x['record_closures']} | {x['reported_R']:.9e} | {x['recomputed']['R']:.9e} | FAIL |" for x in fits)
    scale = a['assets']['zero_update_scale_diagnostics']
    max_equiv = max(x['relative_prediction_scaling_difference'] for x in scale)
    metadata = a['p5_data_audit']
    geometry = {x['layout']:x for x in layout['rows']}
    text = f'''# v2 停止点复核与计划调整

## 当前判断

**应当调整执行计划，但没有依据放宽数值门槛。** 已保存权重的局部残差FAIL可信；“完整G0通过”的认证不成立。既有停止避免了直接浪费长程算力，但没有证明整个DCO路线不可行。

本轮只做CPU微型故障复现、已有权重无更新推理和参考/几何控制；正式DCO新增优化器更新为0。原输入权重及数据hash未变：`{a['original_inputs_unchanged']}`。新的修复与位置候选训练均**未执行**。

## 1. 真实失败，不能拿工程缺口抹掉

run #137重新载入已保存参数，CPU纯推理并用double累加SSE，结果如下。与原GPU float32汇总只有舍入差异，不影响严格R<1e-4判定。

| 保存资产 | Adam实际更新 | LBFGS完成调用 / closure | 原报告R | 本轮复算R | 判定 |
|---|---:|---:|---:|---:|---|
{rows}

主权重元数据为L4/base32/direct、cellsize/RMS、epoch300，与本轮实际加载一致。优化器step字段也确认Adam500/200发生过。失败意义仅限这些输入、主权重和有限预算；不能扩大为“增加精度必然无用”或“网络无法表示旋度”。

## 2. 四个实际工程反例

run #137的微型反例状态：**{status}**，覆盖 `{', '.join(failures)}`。

1. 累计耗时已用2秒，预算1秒，仍新增1次Adam更新。源码保存了elapsed_s，却只比较本次调用耗时，没有扣除历史耗时。
2. 将恢复的LBFGS closure额度从0改成999，配置检查未拒绝；这些字段未进入冻结配置。
3. 在已有run A目录创建run B，记录器未拒绝且保留A元数据。这可能使不同运行输出混在一起。
4. 测试替身完成第一次LBFGS调用、在第二次closure中断时，回滚到了全部LBFGS之前，丢失已完整接受的第一次结果。应该仅回滚未完成调用，并保留消耗的closure数。

第四项由可控optimizer替身验证生产异常路径，不是一次真实LBFGS训练成绩。#132的raw_trial_saved=false，未触发该回滚；因此不能声称修它就能改变#132，也不能据此重跑旧P4-A。

P4-A两份checkpoint还有额外记录缺陷：opt_H.step=200，但fit_progress的updates/closures均为0，且没有LBFGS状态；物理time_layer=0。它们可用于权重推理复核，**不可作为正式恢复续训状态**。43/96 Adam500文件有累计500，但同样属于固定状态诊断，不是从零场接受了43/96步的轨迹。

## 3. 原验收器为什么给了过度通过

- W1旧实现只检查报告内是否出现E_pending、不会重新获得更新次数、NaN三个字符串。这不能认证完整合同。
- 旧恢复测试使用max_inner=0的E_pending失败重放，比较了场，没有覆盖真正中断后继续优化、完整优化器/RNG一致性或LBFGS恢复。
- W0只核对三个数字；完整协议、源码、预算和支撑清单未由它认证。
- W4旧实现可因单一P4A布尔值而PASS，遗漏另一个开发状态、E子步与全部验证点。
- 全时长参考峰值、弱场规则、式(5)六分量字段、故障尾记录、独立硬源负例及真实support计数未全部实现。已有19测试通过只代表已覆盖行为。

本轮已修正文案型认证：W0记INCOMPLETE，W1读实际反例记FAIL，W2保留窄同序控制PASS，W3/W4失败保留。新的完整G0实现仍待A1/A2；没有声称已修好这些生产缺陷。

## 4. 两项可排除的猜测与一项新的几何依据

**参考时层：** run #138使用原PECCavity.step且明确hard source，再只在测量副本补H半步，与旧E→source→H参考128步最大全局Q={ref['aligned_max_Q']:.6e}；故意不补H时为{ref['unaligned_max_Q']:.6e}。两参考在正确对齐时相等，不能把旧局部训练失败归因于这个参考写法。尚需把独立参考、生产控制、测量、落盘恢复连成完整G0测试。

run #137的参考子测误用了step默认加法源；其失败保留，已由#138的显式硬源子测更正。#137其他四个合同反例及权重复算不依赖此子测，仍有效。

**简单幅值缩放：** 第43步H/E按1e-3/1/1e3共同缩放输入和目标，RMS floor均未触发，输出还原相对差异最大{max_equiv:.6e}。旧主模型无更新R仍很大；这批证据不支持用“乘377”或幅值单位重标就能解决当前任务。测试没有排除其他时刻的floor问题。

**H输入位置：** run #139使用预训练E→curl位置对应的精确前向核，在n=7各向异性随机H上比较fdtd.curl_H。旧未shift输入相对L2={geometry['legacy_unshifted']['relative_l2']:.6e}，现有h_shift=True为{geometry['existing_h_shift']['relative_l2']:.6e}。数学上，Hx沿x、Hy沿y、Hz沿z取下一个索引，再取共同半网格原点，恰好恢复E型输入和C型输出布局。

这是转用预训练接口的几何证据，**不是DCO精度**。网络在旧布局也可能学会另一映射；新布局是否改善当前冷启动优化，仍需一次有预算对照。旧历史h-shift阴性结果不能替代本轮相同主权重/支持/预算的候选实验。

## 5. P5仍须区分错误指标与缺失来源

正确四样本宏nMAE=2.006568e-2继续FAIL，未放宽1e-3。#137确认四条E/C shape={metadata['shape_E']}、有限、数据hash匹配、Adam step={metadata['optimizer_step_values']}；curl归一化往返相对L2={metadata['curl_roundtrip_relative_l2']:.6e}。

但NPZ只有{metadata['npz_keys']}，没有原波参数/RNG/生成代码版本；这些检查不能认证具体存储标签一定正确。因此“已经完整排除实际标签/位置/梯度缺陷”应撤回为INCOMPLETE。

v2已有floor审计表明所有128×3分量都未触发旧/新floor，实际loss与梯度相同。这应解释为“常数虽不符协议，但对该批样本的损失权重没有影响”，而不是v2报告误写的“同数值证明不同损失”。不据此新增P5训练。

## 6. 调整后的执行路径

1. A1：修累计预算、真实恢复、LBFGS安全状态、身份/原子落盘、机器验收。CPU微型测试，先记录失败再修复。
2. A2：补齐独立参考生产链、测量峰值/弱场、完整支撑和负例，真正认证G0。
3. A3：唯一新候选为h_shift=True，其他配置不变；43/96先拟合H，H达标再在实际E上顺序拟合E。H失败则只补一次明确oracle的E诊断。每目标仍500/360秒，开发与全部固定验证共30分钟GPU，不追加旧P4-A。
4. 完整G1通过后沿原64→128→1024→8192路径；科学阈值、种子与长程预算保持。否则保存具体瓶颈并停止，未跑阶段NOT_RUN。

执行计划：`C:/PI-DON/docs/superpowers/plans/2026-09-13-pidon-g0-completion-and-h-layout-plan.md`。

本轮交付是**检查与计划调整**，不是已经实现新的位置候选或完成论文复现。

## 7. 证据索引

- #137：`audit.json`与`source_snapshot/`；原输入前后hash、四个实际工程反例、保存权重、缩放、P5来源检查。
- #138：`reference_alignment_corrected.json`，显式硬源的参考修正与错半层反例。
- #139：`h_layout.json`，几何精确核控制。
- 本报告/图由`make_stop_review_report.py`读取`stop_review_evidence.load_review()`生成，与verify_claims读相同JSON；出图运行由lab_log记录。

![停止点证据](C:/PI-DON/evidence/gpt6_plan_v3_review/stop_evidence.png)
'''
    report_path.write_text(text,encoding='utf-8')
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans']
    plt.rcParams['axes.unicode_minus']=False
    fig, axes = plt.subplots(1,2,figsize=(12,4.8),gridspec_kw={'width_ratios':[1.5,1]})
    vals = [x['recomputed']['R'] for x in fits]
    labels = ['43步\nAdam500','96步\nAdam500','43步\nAdam200','43步\nAdam200+LBFGS']
    axes[0].bar(labels,vals,color=['#527ba5','#527ba5','#929eac','#cf7a3e'])
    axes[0].set_yscale('log'); axes[0].set_ylim(5e-5,2e-2)
    axes[0].axhline(1e-4,color='#bd3434',linestyle='--',label='原门槛 R < 1e-4')
    for i,v in enumerate(vals): axes[0].text(i,v*1.16,f'{v:.3e}',ha='center',fontsize=9)
    axes[0].set_title('保存权重重算：局部失败仍成立')
    axes[0].set_ylabel('R = SSE / target_ss'); axes[0].legend(fontsize=9)
    axes[0].grid(axis='y',alpha=.18)
    geo = [geometry['legacy_unshifted']['relative_l2'],geometry['existing_h_shift']['relative_l2']]
    axes[1].bar(['旧H输入','H位置对齐'],geo,color=['#cf7a3e','#478b67'])
    for i,v in enumerate(geo): axes[1].text(i,max(v,0)+.06,f'{v:.6f}',ha='center')
    axes[1].set_ylim(0,1.85); axes[1].set_ylabel('相对 L2（精确核位置检验）')
    axes[1].set_title('位置对应成立；不代表DCO收敛')
    axes[1].grid(axis='y',alpha=.18)
    fig.suptitle('PI-DON 停止点复核｜原阈值不变',fontsize=15)
    fig.text(.5,.015,'左：run #137，原资产 #129/#132；右：run #139，精确核控制，不计 DCO 成绩。',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.055,1,.94)); fig.savefig(figure_path,dpi=170); plt.close(fig)
    print(json.dumps({'report':str(report_path),'figure':str(figure_path),'engineering_status':status},ensure_ascii=False))


if __name__ == '__main__':
    main()
