"""Figure uses the same saved audit and checks as verify_claims."""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from night_review_evidence import ROOT, load_review, contract_checks

data = load_review()
font = FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout='constrained')
rows = data['historical_fits']
values = [r['saved_parameter_R'] for r in rows]
bars = axes[0].bar([f"{r['step']} / {r['role']}" for r in rows], values, color=['#476fa1','#b75c50']*2)
axes[0].set_yscale('log')
axes[0].axhline(1e-4, color='#384c40', linestyle='--', label='R < 1e-4')
axes[0].set_ylim(4e-5, .6)
axes[0].bar_label(bars, labels=[f'{x:.3e}' for x in values], padding=4, fontsize=9)
axes[0].set_title('旧训练失败保留：每项真实 Adam 500 次', fontproperties=font)
axes[0].set_xlabel('固定状态 / curl角色；E均为oracle诊断', fontproperties=font)
axes[0].set_ylabel('R = SSE / target_ss')
axes[0].legend()
labels = ['拒绝缺失127步记录','拒绝被改坏的误差数值','崩溃恢复序号不重复','拒绝终止态再次训练','按物理总R停止','测量参考保持double']
checks = list(contract_checks(data).values())
axes[1].set_xlim(0, 1)
axes[1].set_ylim(-.8, 5.8)
axes[1].axis('off')
axes[1].set_title('G0反例审计：六项要求均未满足', fontproperties=font)
for i, (label, passed) in enumerate(zip(labels, checks)):
    axes[1].text(.02, 5-i, label, fontproperties=font, fontsize=11)
    axes[1].text(.84, 5-i, 'PASS' if passed else 'FAIL', color='#2e6b47' if passed else '#b23b32', weight='bold')
fig.suptitle('夜间计划前核查｜#173；旧R来自#166，磁盘权重推理已由#167复核', fontproperties=font)
out = ROOT / 'evidence/gpt6_plan_v4_review/review_evidence.png'
fig.savefig(out, dpi=160)
print(out)
