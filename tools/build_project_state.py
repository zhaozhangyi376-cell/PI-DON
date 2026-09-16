"""One-time current state registration and historical entrypoint inventory."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    audit = 'evidence/workspace_reorganization_20260914/INDEPENDENT_AUDIT.md'
    plan = 'docs/plans/2026-09-14-direct-mechanism-plan.md'
    definitions = [
        ('W0', '核查与工作区整理', 'RUNNING', [], '建立共同目标入口，保留原始证据并更正成本与恢复误判', [audit]),
        ('M0', '新队列记录/测量最小修复', 'READY', [], '使pending恢复、实际成本和场验收可信', []),
        ('M1', '真实失败输入的拟合鉴别', 'NOT_RUN', [], '区分当前特征与非线性优化问题；只读部分不依赖新runner，避免盲扫学习率', []),
        ('M2', '登记A/B和P/R连续128队列', 'NOT_RUN', ['M0', 'M1'], '直接跨越已知34步瓶颈，失败切换独立臂', []),
        ('G128', '新轨迹128数值验收门', 'NOT_RUN', ['M2'], '残差与场/源外波形均达标才能延长，不把交付完成当科学PASS', []),
        ('S1', '一次完整第一阶段训练与盲测', 'READY', [], '独立回答是否学到可迁移旋度，避免被在线局部问题挤掉', []),
        ('B', '共同窗口预训练收益配对', 'NOT_RUN', ['M2'], '同精度同规则配对，判断预训练成本是否值得；详细计划另有有效配对条件', []),
        ('L1', '同一合格轨迹1024', 'NOT_RUN', ['G128'], '覆盖300/600/900切片和实际传播/反射', []),
        ('G1024', '1024数值验收门', 'NOT_RUN', ['L1'], '逐项复算场门槛与增长风险，不从完成长度自动推PASS', []),
        ('L2', '同轨迹8192及频谱', 'NOT_RUN', ['G1024'], '验证完整论文长度、场与五模频率', []),
        ('U', '问题训练后的冻结复用', 'NOT_RUN', ['G1024'], '判断在线重训以外的实际复用价值', []),
        ('V', '成本、限制与研究判断', 'READY', [], '独立分析随时可做，所有登记任务终结后才最终交付', []),
    ]
    tasks = []
    for ident, title, status, depends, reason, evidence in definitions:
        tasks.append({'id': ident, 'goal_id': 'G-REPRO', 'title': title, 'status': status,
                      'depends': depends, 'reason': reason, 'evidence': evidence,
                      'kind': 'scientific_gate' if ident.startswith('G') else 'delivery',
                      'scientific_result': 'NOT_RUN' if ident != 'W0' else 'NOT_APPLICABLE',
                      'execution_plan': plan})
    state = {
        'schema': 'pidon-master-plan-v1', 'updated': '2026-09-14',
        'goal': {'id': 'G-REPRO', 'objective': '以可追溯证据复现旋度算子学习与逐时间步适配求解机制，判断精度、成本、复用收益是否支持研究方向'},
        'current_task': 'M0',
        'status_semantics': 'delivery PASS仅表示任务交付；G128/G1024 PASS才表示对应科学门全数值通过。harness不认证科学。',
        'gaps': [
            {'id': 'S1', 'target': '未见旋度算子学习及同场换网格验收', 'current': '旧S1 FAIL，新完整训练NOT_RUN', 'status': 'FAIL', 'evidence': ['evidence/mechanism_decision_v1_review/REVIEW.md']},
            {'id': 'SHORT', 'target': '新合法连续128残差+全场+源外波形', 'current': '旧S-R33残差合格前缀，终端FAIL；新64/128 NOT_RUN', 'status': 'NOT_RUN', 'evidence': [audit]},
            {'id': 'LONG', 'target': '同轨迹1024→8192场和频谱', 'current': 'DCO尚未验收；Yee参考不计成绩', 'status': 'NOT_RUN', 'evidence': [audit]},
            {'id': 'BENEFIT', 'target': '同精度P/R及冻结复用成本', 'current': '共同窗口不足，收益未证实', 'status': 'INCOMPLETE', 'evidence': [audit]},
            {'id': 'PROVENANCE', 'target': '成本和恢复证据完整', 'current': '1h精确总数UNKNOWN/下界35122；2h新更新4719；S-P恢复未认证', 'status': 'INCOMPLETE', 'evidence': [audit]},
        ],
        'tasks': tasks,
    }
    p = ROOT / 'project/plan.json'
    if p.exists():
        raise FileExistsError('state already exists; review and update explicitly')
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'project/actions.jsonl').touch(exist_ok=False)
    mapping = json.loads((ROOT / 'project/migration_map.json').read_text(encoding='utf-8'))['files']
    active = {'scripts/experiments/train_dco.py'}
    historical = [r['new'] for r in mapping if r['new'].startswith('scripts/') and r['new'].endswith('.py') and r['new'] not in active]
    # These old core entrypoints also emit fixed root filenames or use old defaults.
    historical.extend(['src/pidon/rollout.py', 'src/pidon/reference_cache.py', 'src/pidon/exact_stencil.py'])
    registry = {'schema': 'pidon-script-entrypoints-v1',
                'historical_entrypoints': sorted(historical),
                'reason': '保留源码供阅读/导入；历史主入口可能覆盖旧证据或依赖原根目录glob，先适配新输出再登记新入口。',
                'active_reviewed_entrypoints': ['src/pidon/pidon_solve.py', 'src/pidon/gen_data.py', 'scripts/experiments/train_dco.py', 'tools/project_harness.py'],
                'old_verify_claims': '封存主入口；旧RESULTS/C7原文保留。根目录glob未迁移，不得重跑后称NODATA。'}
    (ROOT / 'project/script_registry.json').write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding='utf-8')
    print('共同状态与历史入口登记完成。')


if __name__ == '__main__':
    main()
