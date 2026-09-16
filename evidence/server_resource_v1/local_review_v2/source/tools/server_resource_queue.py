"""Install only this queue's tasks, then launch through harness and lab_log."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

from project_paths import PROJECT_DIR, configure
configure()
import project_harness as H
from pidon_recording import atomic_json_save

PROTOCOL = 'docs/plans/2026-09-15-server-resource-protocol.md'
JOBS = (
    ('SR-COMPARE', '服务器三模型同题重测与S1R原始证据审核', 'server_phase1_compare', 'phase1_compare'),
    ('SR-PERF', 'GV100等效批次吞吐测试', 'server_compute_probe', 'compute_probe'),
)


def new_tasks():
    return [{'id': task, 'goal_id': 'G-REPRO', 'title': title, 'status': 'READY', 'depends': [],
             'reason': title, 'evidence': [], 'kind': 'delivery', 'scientific_result': 'NOT_RUN',
             'execution_plan': PROTOCOL} for task, title, _, _ in JOBS]


def merge_tasks(plan):
    """Leave existing entries/events intact; never reset a previously installed job."""
    ids = {t['id'] for t in plan['tasks']}
    added = []
    for task in new_tasks():
        if task['id'] not in ids:
            plan['tasks'].append(task)
            added.append(task['id'])
    return added


def setup(root=PROJECT_DIR):
    plan = H.load_plan(root)
    added = merge_tasks(plan)
    if added:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
        backup = root / f'evidence/server_resource_v1/plan_before_install_{stamp}.json'
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / 'project/plan.json', backup)
        errors = H.validate_plan(plan, root)
        if errors:
            raise H.HarnessError('\n'.join(errors))
        atomic_json_save(plan, root / 'project/plan.json')
    print('Queue tasks:', ', '.join(added) if added else 'already installed; existing states preserved')


def run_queue():
    root = PROJECT_DIR
    if shutil.disk_usage(root).free < 50*1024**3:
        raise RuntimeError('Server batch requires at least 50 GiB free disk; no jobs started')
    setup(root)
    for task, title, script, folder in JOBS:
        events = H.read_events(root)
        if any(e.get('event') == 'start' and e.get('task_id') == task for e in events):
            print('SKIP already registered:', task, flush=True)
            continue
        out = root / f'evidence/server_resource_v1/{folder}'
        if out.exists():
            print('SKIP output exists, audit before retry:', out, flush=True)
            continue
        args = argparse.Namespace(task=task, question=title, expected='Complete bounded diagnostic under server-resource protocol',
                                  success='Raw metrics hashes report and cost retained; no scientific promotion',
                                  failure='Preserve failure; continue next independent registered diagnostic', protocol=PROTOCOL)
        action = H.start_action(args, root)
        command = [sys.executable, 'lab_log.py', 'run', '-m', f'{task}: {title}', '--', sys.executable,
                   'run.py', '--action', action, script, '--action-id', action, '--device', 'cuda']
        completed = subprocess.run(command, cwd=root, check=False)
        summary_path = out / 'summary.json'
        status = 'INCOMPLETE'
        if summary_path.exists():
            summary = H.read_json(summary_path)
            status = summary.get('status', 'INCOMPLETE') if completed.returncode == 0 else 'INCOMPLETE'
        else:
            out.mkdir(parents=True, exist_ok=True)
            summary_path = out / 'failure.json'
            atomic_json_save({'action_id': action, 'exit_code': completed.returncode,
                              'status': 'INCOMPLETE', 'scientific_result': 'NOT_APPLICABLE',
                              'cost': 'UNKNOWN_if_process_died_before_summary'}, summary_path)
        H.finish_action(argparse.Namespace(action=action, status=status, evidence=[[str(summary_path)]],
                        summary=f'{task} diagnostic delivery {status}; exit {completed.returncode}; requires review; no scientific gate unlocked'), root)
    print('Batch ended. Review evidence/server_resource_v1/*/REPORT.md and summary.json.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('setup', 'run'))
    args = parser.parse_args()
    if args.mode == 'setup':
        setup()
    else:
        run_queue()


if __name__ == '__main__':
    main()
