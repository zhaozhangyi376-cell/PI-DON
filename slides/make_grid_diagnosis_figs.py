"""Render logged factorial diagnosis using verify_claims' raw-array reader."""
from pathlib import Path
import json
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import verify_claims as V
from paper_recheck import sha256,dump

plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
                     'axes.unicode_minus':False,'font.size':10,
                     'axes.spines.top':False,'axes.spines.right':False})
COLORS=['#0072B2','#D55E00']


def main():
    j,m,f=V.grid_evidence()
    root=ROOT/'evidence/grid_diagnosis_v1';out=ROOT/'figs';out.mkdir(exist_ok=True)
    source='run #18 · arrays.npz SHA256 '+j['arrays_sha256'][:12]
    models=[r['tag'] for r in j['models']]
    shapes=['x'.join(map(str,s)) for s in m['shapes']]
    spacings=list(m['spacings_mm'])
    spacing_labels=['0.6 / 0.6 / 0.6','0.3 / 0.3 / 0.3','0.3 / 0.2 / 1.2','0.6 / 0.3 / 1.2']
    def rows(model,shape,spacing,scale='natural'):
        return [r for r in j['rows'] if r['model']==model and r['size']==shape
                and r['spacing']==spacing and r['scale']==scale]
    matrices=[np.array([[np.median([r['metrics']['macro_nmae'] for r in rows(model,sh,sp)])
                         for sp in spacings] for sh in shapes]) for model in models]
    fig,axs=plt.subplots(1,2,figsize=(12,5),layout='constrained')
    norm=LogNorm(vmin=min(a.min() for a in matrices),vmax=max(a.max() for a in matrices))
    for ax,a,model in zip(axs,matrices,models):
        im=ax.imshow(a,norm=norm,cmap='viridis',aspect='auto')
        for row in range(4):
            for col in range(4):
                ax.text(col,row,f'{a[row,col]:.4f}',ha='center',va='center',
                        color='black' if norm(a[row,col])>.65 else 'white')
        ax.set_xticks(range(4),spacing_labels,rotation=20,ha='right')
        ax.set_yticks(range(4),[s.replace('x','×') for s in shapes])
        ax.set_xlabel('dx / dy / dz，单位 mm（后两列超出默认训练范围）')
        ax.set_title(model)
    fig.colorbar(im,ax=axs,label='中心 ROI 三分量平均 nMAE（对数色标）',shrink=.85)
    fig.suptitle('形状 × 间距对照：保持立方形状，后两列误差仍增大\n采用各自全输入 RMS；每格为振幅种子 0/1/2 的中位数',fontsize=13)
    fig.supxlabel(source+'；诊断窗口与 Fig.6 不同，不与论文 MRE 比较',fontsize=9)
    paths=[]
    def save(fig,name):
        p=out/name;fig.savefig(p,dpi=180,bbox_inches='tight',facecolor='white');plt.close(fig);paths.append(p)
    save(fig,'grid_diagnosis_matrix.png')

    fig,axs=plt.subplots(1,2,figsize=(12,5),layout='constrained')
    for mi,model in enumerate(models):
        for col,sp in enumerate(spacings[1:]):
            vals=[r['nmae_ratio'] for r in f['spacing_effects'] if r['model']==model and r['spacing']==sp]
            x=col+(mi-.5)*.22
            axs[0].vlines(x,min(vals),max(vals),color=COLORS[mi],linewidth=2)
            axs[0].scatter(x+np.array([-.025,0,.025]),vals,color=COLORS[mi],marker=['o','s'][mi],
                           label=model if col==0 else None)
        for col,sh in enumerate(shapes[1:]):
            vals=[100*r['relative_prediction_change'] for r in f['shape_effects'] if r['model']==model and r['size']==sh]
            x=col+(mi-.5)*.22
            axs[1].vlines(x,min(vals),max(vals),color=COLORS[mi],linewidth=2)
            axs[1].scatter(x+np.array([-.025,0,.025]),vals,color=COLORS[mi],marker=['o','s'][mi])
    axs[0].axhline(2,linestyle='--',color='#555555',label='预设 2 倍诊断门槛')
    axs[0].axhline(1,linestyle=':',color='#777777')
    axs[0].set_xticks(range(3),spacing_labels[1:],rotation=15,ha='right')
    axs[0].set(title='固定 32³：只改变间距组（自然 RMS）',ylabel='ROI nMAE / 0.6 mm 基准 nMAE',xlabel='dx / dy / dz，单位 mm',yscale='log')
    axs[0].legend(fontsize=8)
    axs[1].axhline(.1,linestyle='--',color='#555555')
    axs[1].set_xticks(range(3),[s.replace('x','×') for s in shapes[1:]])
    axs[1].set(title='固定 0.6 mm 与 RMS：改变上下文形状',ylabel='同位置预测相对 32³ 的变化 / %',xlabel='网格形状',yscale='log')
    for ax in axs:ax.grid(axis='y',alpha=.2)
    fig.suptitle('两种效应都存在；左右纵轴含义不同，不能直接比较倍数\n每组三点为三个振幅种子；右图固定中心场值、采样位置与归一化',fontsize=13)
    fig.supxlabel(source,fontsize=9)
    save(fig,'grid_diagnosis_controls.png')

    norm_cases=[r for r in f['normalization_effects'] if r['size']!='32x32x32']
    scale_range=[min(r['natural_over_fixed_scale'] for r in norm_cases),max(r['natural_over_fixed_scale'] for r in norm_cases)]
    error_range=[min(r['fixed_over_natural_nmae'] for r in norm_cases),max(r['fixed_over_natural_nmae'] for r in norm_cases)]
    original=[r['ratio_to_32'] for r in f['original_window_rms']]
    lines=['# 里程碑2：DCO模型分项诊断验收','',
           '> 本轮仍属于第一阶段DCO诊断。数值运行 #18；结论复核见 #19 及后续日志。','',
           '**结论：原非立方案例混合了形状变化与间距范围外测试。固定32³后仍出现大幅误差增加，间距相关泛化应优先排查；同时，恒定间距输入并没有消除形状/上下文依赖。现有模型还没有修复，也未通过论文验收。**','',
           '## 对照为何能回答问题','',
           '两个现有权重、三个振幅种子、四种形状、四组间距、两种RMS取值方式，共192次冻结推理。只比较中心8³区域。固定同一间距时，该区域的物理位置、输入场和解析旋度在各形状中相同；坐标原点随窗口调整以对齐采样，池化网格相位也对齐。',
           'natural使用当前完整输入的RMS，符合原权重归一化；fixed32统一使用中心32³窗口的输入RMS，以免比较形状时又改变幅度缩放。后者是诊断干预，不是对模型的新修复。',
           '形状变化仍会改变外围场、物理窗口和边界距离。因此右图证明的是形状/上下文依赖，不能单独归因于填零、池化或某个编码分支。','',
           '## 1. 已测试的接口没有发现错位','',
           f'- 当前训练生成器与独立采样的最大相对偏差：{j["checks"]["training_sampler"]:.3e}。解析旋度方向与Yee位置在本测试中一致。',
           f'- 归一化再还原的最大相对偏差：{max(v for k,v in j["checks"].items() if k.startswith("roundtrip")):.3e}。',
           '- 坐标单位、相对间距换算、共同ROI一致性及9项原有回归测试通过；192组预测完整、有限，权重前后SHA256一致。',
           '- 这些结果排除已测试的算术还原和训练/评估接口错位；不证明当前归一化方式或坐标编码等同作者实现。','',
           '## 2. 间距相关误差可以在立方网格中重现','',
           '公开测试窗口19.2mm使64×96×16的间距成为(0.3,0.2,1.2)mm，使32×64×16成为(0.6,0.3,1.2)mm；而生成器默认范围为每轴0.3–0.8mm。可读data_32.npz含1000个样本，每轴实测范围均约0.300–0.800mm。',
           'dco_lr1e3_300的内嵌配置指向data_32.npz、训练样本数800，但没有当时数据哈希，不能完全确认文件未变；dco_paper32缺少内嵌训练配置。当前数据已另存哈希。','',
           '| 模型 | 间距/mm | 固定32³时的误差比范围（相对0.6mm） |','|---|---|---:|']
    for model in models:
        for spacing,label in zip(spacings[1:],spacing_labels[1:]):
            vals=[r['nmae_ratio'] for r in f['spacing_effects'] if r['model']==model and r['spacing']==spacing]
            lines.append(f'| {model} | {label} | {min(vals):.2f}–{max(vals):.2f} |')
    lines += ['', '每个范围覆盖三个振幅种子，不是置信区间；误差采用中心ROI逐分量nMAE的算术平均。两种各向异性间距全部列出，没有只展示每组较差者。改变间距也改变每个网格单元内的场变化与采样位置，尚不能区分trunk外推、各向异性耦合和branch的空间频率响应。',
              '范围内的0.3mm立方案例也可能比0.6mm差，尤其dco_lr1e3_300三个种子均变差。因此不能将问题简化为“只要不超训练范围就准确”。','',
              '![完整对照](../../figs/grid_diagnosis_matrix.png)','',
              '## 3. “恒定间距输入就精度尺寸不变”不成立','',
              '| 模型 | 形状 | 同位置预测相对32³变化范围 |','|---|---|---:|']
    for model in models:
        for shape in shapes[1:]:
            vals=[r['relative_prediction_change'] for r in f['shape_effects'] if r['model']==model and r['size']==shape]
            lines.append(f'| {model} | {shape} | {100*min(vals):.3f}%–{100*max(vals):.3f}% |')
    lines += ['', '变化定义为||预测_其他形状−预测_32³||₂ / ||预测_32³||₂，固定0.6mm间距与32³参考RMS，仅比较同位置中心8³。分母不是解析真值；这衡量预测一致性，不是场误差，也不能与上一表的误差倍数直接比较。','',
              '![分项效应](../../figs/grid_diagnosis_controls.png)','',
              '## 4. 归一化要区分算术错误与窗口效应','',
              f'算术还原通过。但本诊断改变物理窗口后，自然RMS/32³参考RMS为{scale_range[0]:.3f}–{scale_range[1]:.3f}；改用固定RMS后，nMAE相对原自然RMS为{error_range[0]:.3f}–{error_range[1]:.3f}倍，不能统一改善所有案例。',
              f'补充复算上一轮run #13的固定19.2mm窗口：各网格RMS/32³的范围仅为{min(original):.6f}–{max(original):.6f}。这是事后描述性核查，不能把本轮扩大物理窗口产生的RMS变化当成上一轮失败的已证实主因。','',
              '## 本轮判断及下一步','',
              '已经得到的证据支持：优先处理间距相关的泛化；同时保留形状/上下文依赖这一独立问题。尚不支持：已锁定某一层为唯一根因、只扩训练范围就一定修复、或者改RMS就能复现论文。',
              '建议下一轮先做低成本单轴间距扫描和单平面波方向对照，区分0.2mm细间距、1.2mm粗间距、各向异性和离散近似误差；再决定是调整编码、训练分布还是损失。暂不启动长训练或Algorithm 1。按用户要求，本里程碑完成后停下验收。','',
              '## 可追溯材料','',
              '- arrays.npz：全部共同ROI真值、输入与192组预测；summary.json：模型身份、归一化因子与元数据。',
              '- manifest.json：运行前固定的D0–D3判据、全部波场参数、环境与源代码哈希。',
              '- findings.json / verification_manifest.json：结论复算结果；figures_manifest.json：本图和报告哈希。',
              '- diagnose_grid.py：原始诊断；slides/make_grid_diagnosis_figs.py：图与报告生成；verify_claims.py：结论和图共用的数组复算。',
              '- RESULTS.md 的D0–D3为诊断陈述检验；P2仍为精度未通过。二者不能混为一谈。','']
    report=root/'STAGE_REPORT.md';report.write_text('\n'.join(lines),encoding='utf-8')
    shutil.copy2(__file__,root/'source'/'make_grid_diagnosis_figs.py')
    dump(root/'figures_manifest.json',dict(source_run=18,arrays_sha256=j['arrays_sha256'],
        script_sha256=sha256(__file__),report_sha256=sha256(report),
        figures={str(p.relative_to(ROOT)):sha256(p) for p in paths}))
    print('Wrote',report)
    print('Normalization, changed extent:',scale_range,'fixed/natural error:',error_range)
    print('Original fixed window RMS ratio:',min(original),max(original))
    print('Median natural RMS ROI nMAE matrices:',dict(zip(models,[a.tolist() for a in matrices])))


if __name__=='__main__':main()
