"""N0: freeze the v4 night identity, source snapshot and resource baseline."""
from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import torch

from night_budget import NightPaths, append_ledger, init_or_load, sha256_file
from pidon_recording import source_hashes


ROOT = PROJECT_ROOT
MASTER_SHA256 = '3f259bc887a10fac77f6bdf77b43ba1ad6b45827a3f8b9bd685934acc47ca5d7'
HISTORICAL = (
    'dco_lr1e3_300.pt',
    'evidence/gpt6_plan_v3/h_layout_candidate/H_step_0043.pt',
    'evidence/gpt6_plan_v3/h_layout_candidate/E_oracle_step_0043.pt',
    'evidence/gpt6_plan_v3/h_layout_candidate/H_step_0096.pt',
    'evidence/gpt6_plan_v3/h_layout_candidate/E_oracle_step_0096.pt',
)
SOURCE_FILES = (
    'pidon_solve.py', 'pidon_recording.py', 'pidon_contract.py', 'pidon_exact_control.py',
    'reference_cache.py', 'g0_verifier.py', 'fdtd.py', 'dco.py', 'night_budget.py',
    'night_init.py', 'test_night_budget.py',
)


def shell(args):
    return subprocess.check_output(args, cwd=ROOT, text=True, encoding='utf-8', errors='replace')


def copy_snapshot(destination: Path) -> dict[str, str]:
    destination.mkdir(exist_ok=False)
    hashes = {}
    for name in SOURCE_FILES:
        source, target = ROOT / name, destination / name
        shutil.copy2(source, target)
        hashes[name] = sha256_file(target)
    return hashes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='evidence/gpt6_plan_v4_night')
    args = parser.parse_args()
    out = (ROOT / args.root).resolve()
    paths = NightPaths(out)
    plan = ROOT / 'docs/superpowers/plans/2026-09-13-pidon-10h-goal-night-plan.md'
    master = ROOT / 'dco_lr1e3_300.pt'
    if sha256_file(master) != MASTER_SHA256:
        raise RuntimeError('registered master checkpoint hash differs')
    manifest = init_or_load(paths, plan_path=plan, master_weight=master,
                            source_hashes=source_hashes(ROOT))
    if paths.stage_status.exists():
        raise RuntimeError('N0 already initialized; use the persisted manifest, do not recreate evidence')
    free = shutil.disk_usage(ROOT).free
    if free < manifest['system_floor_bytes'] + manifest['emergency_reserve_bytes']:
        raise RuntimeError('disk is below the protected system/emergency floor')
    historical = {}
    for relative in HISTORICAL:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        historical[relative] = sha256_file(path)
    snapshot_hashes = copy_snapshot(out / 'source_snapshot')
    dirty = shell(['git', 'diff'])
    (out / 'working_tree.diff').write_text(dirty, encoding='utf-8')
    status = shell(['git', 'status', '--short'])
    (out / 'git_status.txt').write_text(status, encoding='utf-8')
    gpu = {'available': torch.cuda.is_available()}
    if torch.cuda.is_available():
        gpu.update({'name': torch.cuda.get_device_name(0), 'memory_total_bytes': torch.cuda.get_device_properties(0).total_memory,
                    'memory_allocated_bytes': torch.cuda.memory_allocated(0)})
    stage = {
        'schema': 'pidon-v4-night-stage-status-v1', 'manifest_experiment_id': manifest['experiment_id'],
        'N0': {'implementation': 'PASS', 'scientific_gate': 'N/A', 'lab_run_id': None},
        'N1': {'implementation': 'NOT_RUN', 'scientific_gate': 'N/A'},
        'N2': {'implementation': 'NOT_RUN', 'scientific_gate': 'NOT_RUN'},
        'N3': {'implementation': 'NOT_RUN', 'scientific_gate': 'NOT_RUN'},
        'N4': {'implementation': 'NOT_RUN', 'scientific_gate': 'NOT_RUN'},
        'N5': {'implementation': 'NOT_RUN', 'scientific_gate': 'N/A'},
        'N6': {'implementation': 'NOT_RUN', 'scientific_gate': 'NOT_RUN'},
        'historical_asset_hashes': historical,
        'resource_baseline': {'disk_free_bytes': free, 'disk_total_bytes': shutil.disk_usage(ROOT).total,
                              'python': sys.version, 'torch': torch.__version__, 'platform': platform.platform(), 'gpu': gpu},
        'source_snapshot_hashes': snapshot_hashes, 'plan_sha256': sha256_file(plan),
        'master_weight_sha256': sha256_file(master),
        'cleanup_performed': False,
    }
    with paths.stage_status.open('x', encoding='utf-8') as handle:
        json.dump(stage, handle, ensure_ascii=False, indent=2)
        handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
    append_ledger(paths, {'kind': 'N0_baseline', 'task_id': 'N0', 'disk_free_bytes': free,
                          'artifact_used_bytes': 0, 'adam_updates': 0, 'head_commits': 0,
                          'linear_solve_calls': 0, 'training_s': 0.0, 'cleanup_bytes': 0})
    report = ['# N0 资产、身份与资源冻结', '', f"- experiment_id：`{manifest['experiment_id']}`", f"- started_at：`{manifest['started_at']}`", f"- training_deadline：`{manifest['training_deadline']}`", f"- deadline：`{manifest['deadline']}`", f"- C盘空闲：`{free}` bytes", f"- 主权重SHA256：`{stage['master_weight_sha256']}`", '- 正式DCO更新：0', '- 清理软件数据：0 bytes', '', '历史权重、失败现场与源码快照均已登记；夜间目录此前不存在。']
    (out / 'N0_REPORT.md').write_text('\n'.join(report) + '\n', encoding='utf-8')
    print(json.dumps({'out': str(out), 'experiment_id': manifest['experiment_id'], 'disk_free_bytes': free,
                      'deadline': manifest['deadline'], 'formal_dco_updates': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
