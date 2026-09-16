"""Evidence figures/report from the same verified arrays used by RESULTS.md.

Run from repository root, wrapped with lab_log.py. No training or inference.
"""
from pathlib import Path
import sys
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import verify_claims as V
import paper_protocol as P
from paper_recheck import sha256

plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
                     'axes.unicode_minus':False, 'font.size':10,
                     'axes.spines.top':False, 'axes.spines.right':False})
OUT = ROOT/'figs'
EVID = ROOT/'evidence/paper_first_v1'
COLORS = ['#0072B2','#D55E00']


def save(fig, name):
    path = OUT/name
    fig.savefig(path, dpi=180, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return path


def main():
    OUT.mkdir(exist_ok=True)
    j,m = V.paper_evidence()
    models = [v['tag'] for v in j['models']]
    sizes = ['x'.join(map(str,s)) for s in P.SHAPES]
    source = '来源：run #13 · arrays.npz SHA256 '+j['arrays_sha256'][:12]
    fig,axs=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    for mi,model in enumerate(models):
        for ai,key in enumerate(['mre_eq5','nmae']):
            ax=axs[ai]
            for gi,size in enumerate(sizes):
                vals=[r['metrics']['components']['x'][key] for r in j['rows']
                      if r['model']==model and r['size']==size]
                x=gi+(mi-.5)*.23
                ax.vlines(x,min(vals),max(vals),color=COLORS[mi],linewidth=2)
                ax.scatter([x-.035,x,x+.035],vals,color=COLORS[mi],
                           marker=['o','s'][mi],s=35,label=model if gi==0 else None)
    for gi,size in enumerate(sizes):
        if size in P.PAPER_MRE:
            y=P.PAPER_MRE[size]
            axs[0].plot([gi-.36,gi+.36],[y,y],color='#333333',linestyle='--',
                        label='论文 Fig.6 标值（原始振幅未知）' if gi==1 else None)
    for ax in axs:
        ax.set_xticks(range(4),[s.replace('x','×') for s in sizes])
        ax.set_yscale('log'); ax.grid(axis='y',alpha=.2)
        ax.set_xlabel('同一物理窗口：19.2 mm × 19.2 mm × 19.2 mm')
    axs[0].set_title('x 分量：式（5）逐点相对误差')
    axs[0].set_ylabel('MRE（越低越好；对数轴）')
    axs[0].legend(fontsize=8,loc='upper left')
    axs[1].set_title('x 分量：另列 nMAE，检查整体偏差')
    axs[1].set_ylabel('MAE / max|真值|（不能替代 MRE）')
    fig.suptitle('现有模型重评：非立方网格偏差明显\n每组三点为振幅种子 0 / 1 / 2；声明假设的重建案例，非作者原始数据',fontsize=13)
    fig.supxlabel(source,fontsize=9)
    paths=[save(fig,'paper_first_metrics.png')]

    # Compare one declared checkpoint and seed, without selecting the best slice.
    model='dco_lr1e3_300'
    with np.load(EVID/'arrays.npz',allow_pickle=False) as z:
        fig,axs=plt.subplots(4,3,figsize=(10,11.5),layout='constrained')
        for ri,size in enumerate(sizes):
            key='s0_'+size
            true=z[key+'_true'][0]; pred=z[model+'_'+key+'_pred'][0]
            plane=true.shape[2]//2
            peak=np.max(np.abs(true))
            slices=[true[:,:,plane]/peak,pred[:,:,plane]/peak,(pred-true)[:,:,plane]/peak]
            row=next(r for r in j['rows'] if r['model']==model and r['seed']==0 and r['size']==size)
            met=row['metrics']['components']['x']
            for ci,a in enumerate(slices):
                limit=1 if ci<2 else max(float(np.abs(a).max()),1e-12)
                dx=19.2/true.shape[0]
                im=axs[ri,ci].imshow(a.T,origin='lower',extent=[-.5*dx,19.2-.5*dx,0,19.2],
                                    cmap='RdBu_r',vmin=-limit,vmax=limit,interpolation='nearest')
                axs[ri,ci].set_xlabel('x / mm'); axs[ri,ci].set_ylabel('y / mm')
                fig.colorbar(im,ax=axs[ri,ci],shrink=.75)
                axs[ri,ci].set_title(['解析旋度 / max|真值|','网络旋度 / max|真值|',
                                     '差值 / max|真值|（独立色标）'][ci],fontsize=9)
            axs[ri,0].set_ylabel(size.replace('x','×')+'\ny / mm')
            axs[ri,1].set_title('网络旋度 / max|真值|\n'+f'全体素 MRE={met["mre_eq5"]:.4f}；nMAE={met["nmae"]:.4f}',fontsize=9)
        fig.suptitle(model+' · 振幅种子 0 · x 旋度分量\n每网格取中间 z 层；像素中心对应真实 Yee 采样位置',fontsize=12)
        fig.supxlabel(source,fontsize=9)
        paths.append(save(fig,'paper_first_fields.png'))

        r=j['reference'];t=np.arange(1,r['steps']+1)*r['dt_s']*1e9
        fig,axs=plt.subplots(2,1,figsize=(11,6.5),layout='constrained')
        axs[0].plot(t,z['fdtd_trace'],color=COLORS[0],linewidth=.65)
        axs[0].set(xlabel='时间 / ns',ylabel='源外探针 Ez / (V/m)',
                   title='探针 (12,12,13) 与硬源 (15,15,15) 分开；8192 步参考推进')
        sp=z['fdtd_spectrum'];freq=z['fdtd_f']/1e9
        axs[1].plot(freq,sp/sp.max(),color=COLORS[0],linewidth=1)
        for mode in r['modes']:
            axs[1].axvline(mode['analytic_GHz'],color='#777777',alpha=.6,linestyle='--')
            axs[1].text(mode['analytic_GHz'],1.03,mode['mode'],ha='center',fontsize=9)
        axs[1].set(xlabel='频率 / GHz',ylabel='归一化频谱幅值',xlim=(3,12.5),ylim=(0,1.14),
                   title='虚线为五个解析模式；实测峰位最大相对误差 '+f'{max(abs(v["error_pct"]) for v in r["modes"]):.3f}%')
        for ax in axs: ax.grid(alpha=.2)
        fig.suptitle('FDTD 基准通过本轮门槛；这是参考解，不是 PI-DON 结果\n50 mm 空气 PEC 腔体 · 31 间隔候选 · Δt = 3.075 ps',fontsize=13)
        fig.supxlabel(source+'\nHann 窗 + 零填充 + 峰位插值；原始频点间隔 '+f'{r["raw_fft_bin_Hz"]/1e6:.1f} MHz，零填充不增加物理分辨率',fontsize=9)
        paths.append(save(fig,'paper_first_fdtd.png'))

    lines=['# 阶段验收：评估基准与现有权重重评','',
           '本轮完成 G0 空气参考解检查，以及 G1 的评估协议和现有权重重评。**参考解通过，现有 DCO 在声明假设的案例中未通过预设目标。** 未重新训练网络，尚未验收 Algorithm 1。','',
           '## 做了什么及证据','',
           '- run #11：9 项回归测试中 1 项失败，定位到式（5）把极小非零真值按零处理。',
           '- run #12：修正零值分支后 9 项通过。',
           '- run #13：再跑 9 项测试、8192 步纯 FDTD、2 权重 × 3 振幅种子 × 4 网格，共 24 组推理；权重前后 SHA256 一致。',
           '- 图和本报告从原始数组重算，采用 verify_claims.paper_evidence()，与 RESULTS.md 共用指标函数。绘图本身没有重新训练或推理。',
           '- run #15 完成结论复算和9项测试；退出1表示P2精度门槛未通过。该条日志自动摘要误把C10的指标比值下界2.6提取成nMAE；不是实测nMAE，完整输出保留，后续更正了比值的打印格式以避免误提取。','',
           '## FDTD 参考验收','',
           '预先固定门槛：8192 步，检查到的全场保持有限，五个模式相对频率误差均低于 0.5%。源外探针避免读到被直接写入的激励。',
           '每 128 步检查六分量有限性；保存完整源外时序与 300/600/900 步 Ez 切片。31 间隔是当前候选解释，尚未经作者确认；本轮通过不等于论文网格约定已确认，也不代表材料或吸收边界已验证。','',
           '| 模式 | 解析 / GHz | 本轮 FDTD / GHz | 相对误差 |','|---|---:|---:|---:|']
    for row in j['reference']['modes']:
        lines.append(f'| {row["mode"]} | {row["analytic_GHz"]:.6f} | {row["measured_GHz"]:.6f} | {row["error_pct"]:.4f}% |')
    lines += ['', '![FDTD参考](../../figs/paper_first_fdtd.png)','',
              '峰位采用 Hann 窗、2^20 零填充和抛物线插值；原始频点间隔约 39.7 MHz。这是本轮 0.5% 工程门槛，不能包装成对 Table II 的逐位复现。','',
              '## DCO 精度验收','',
              '采用 Fig.5/6 公开参数：θ=45°、φ=60°、20 个波数在 0.021–838.34 m⁻¹ 等间隔取样；物理窗口各边 19.2 mm，换网格时保持同一波场。','',
              '**声明假设**：Ex/Ey 振幅按 U[0,5] 重建、由横向条件确定 Ez，取复表达式实部且零相位，间距 L/N，在 Yee 分量位置采样。三个种子检验振幅敏感性，不是三次独立训练。作者原始振幅与部分实现约定未披露，因此这些是重建案例，不能称为作者的完全相同测试集。','',
              '保留权重训练时的 RMS 输入归一化和 cellsize 坐标输入，以确保评估的是现有模型；这不表示它们符合论文实现。式（5）对每个非零真值计算相对误差，严格为零才走绝对误差分支；不加 epsilon，不截断近零点。分别给出 x/y/z 与算术平均，另列 nMAE 和相对 L2。','',
              '预先固定门槛：至少一个权重在三种 Fig.6 网格、三个振幅种子的 x 分量式（5）误差均不高于图注标值。论文分量汇总口径有歧义，x 分量是本轮明确声明的对照选择。**两个模型均未通过此门槛。**','',
              '| 网格 | 论文 Fig.6 标值 | dco_paper32 x-MRE 范围 | dco_lr1e3_300 x-MRE 范围 |',
              '|---|---:|---:|---:|']
    for size in sizes:
        vals=[]
        for model in models:
            v=[r['metrics']['components']['x']['mre_eq5'] for r in j['rows'] if r['model']==model and r['size']==size]
            vals.append(f'{min(v):.5f}–{max(v):.5f}')
        lines.append('| '+size.replace('x','×')+' | '+(f'{P.PAPER_MRE[size]:.4f}' if size in P.PAPER_MRE else '未设置同图门槛')+' | '+' | '.join(vals)+' |')
    lines += ['', '范围覆盖三个振幅种子，不是置信区间。', '',
              '![误差对照](../../figs/paper_first_metrics.png)','',
              '![场与差值](../../figs/paper_first_fields.png)','',
              '通俗解释：MRE 会放大真值接近零处的偏差，nMAE 则反映相对于场整体幅度的平均偏差。两种指标用途不同，不能因为前者更大就把它换掉。图中另列 nMAE，避免只凭近零点敏感性解释所有问题；本轮还不能单独把偏差归因到网络结构、归一化或训练分布中的某一项。','',
              '## 修正旧结论','',
              '- 撤回“MAE/max 就是式（5）”及“第一阶段已达到论文 0.70–1.50 倍”的比较。旧实验原始文件保留。',
              '- 保留已有训练器、权重、多尺寸推理与空气 FDTD 作为基础资产；它们尚不足以支持“第一阶段成功”。',
              '- C2–C6、C8 标为待重审；C7 不利反例保留。两点精度/寿命外推不能证明冻结算子路线普遍不可能。',
              '- Algorithm 1 训练与完成训练后的冻结评估必须分开；本轮没有运行其中任何一个。',
              '- dco_paper32 的权重元数据 epoch=260，不能再写成已确认 300 轮。','',
              '## 下一步建议与停止点','',
              '按用户要求，停在本轮验收。建议下一步仍留在第一阶段：核对 branch/trunk 输入、归一化可逆性、解析旋度采样位置和训练分布，先做不训练或小规模的诊断对照。先定位非立方网格偏差，再决定有限预算的重新训练；暂不启动 8192 步 Algorithm 1 内层训练。这个建议依据本轮失败更新了旧的“直接扫第二阶段学习率”优先级。','',
              '## 追溯','',
              '- 原始输入、真值、预测、参考时序：arrays.npz；完整逐分量指标与权重身份：summary.json。',
              '- manifest.json 记录预设门槛、波场振幅、软件版本和 source/ 源代码快照哈希。',
              '- 历史文档备份：../history_before_paper_first/；日志：../../LAB_NOTEBOOK.md。',
              '- 图脚本：../../slides/make_paper_first_figs.py；结论脚本：../../verify_claims.py。',
              f'- 数组 SHA256：`{j["arrays_sha256"]}`。','']
    report=EVID/'STAGE_REPORT.md'
    report.write_text('\n'.join(lines),encoding='utf-8')
    shutil.copy2(__file__,EVID/'source'/'make_paper_first_figs.py')
    trace=dict(source_run=13,arrays_sha256=j['arrays_sha256'],
               script_sha256=sha256(__file__),report_sha256=sha256(report),
               figures={str(p.relative_to(ROOT)):sha256(p) for p in paths})
    (EVID/'figures_manifest.json').write_text(json.dumps(trace,indent=2),encoding='utf-8')
    print('Verified raw arrays; wrote 3 figures and',report)
    for p in paths: print(p)


if __name__=='__main__': main()
