"""Numerical readback of prior runs plus bounded workspace delivery checks."""
from __future__ import annotations
import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/workspace_reorganization_20260914'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rows(path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]


def runs(folder):
    result = {}
    for p in sorted((ROOT / 'evidence' / folder / 'runs').glob('*/steps.jsonl')):
        data = rows(p)
        accepted = [r for r in data if r.get('accepted')]
        final = data[-1] if data else {}
        result[p.parent.name] = {
            'recorded_updates': sum(sum(int((r.get(k) or {}).get('n_updates', 0)) for k in ('fit_H', 'fit_E')) for r in data),
            'accepted_steps': len(accepted), 'rows': len(data),
            'last_row_accepted': final.get('accepted'),
            'last_H_R': (final.get('fit_H') or {}).get('residual_ratio'),
            'last_E_R': (final.get('fit_E') or {}).get('residual_ratio'),
            'steps_path': p.relative_to(ROOT).as_posix(), 'steps_sha256': sha(p),
        }
    return result


def backup_reverification():
    """Compare each saved original backup with its REGISTERED sha256_before.

    Reports what differs; never writes a corrected hash back into the
    migration map.  A line-ending-only difference is reported separately from
    an unexplained one, because the two mean different things.
    """
    mapping_path = ROOT / 'project/migration_map.json'
    backup_dir = OUT / 'before/root'
    if not mapping_path.is_file() or not backup_dir.is_dir():
        return {'status': 'INCOMPLETE', 'reason': 'migration map or backup directory is absent'}
    rows = json.loads(mapping_path.read_text(encoding='utf-8')).get('files', [])
    matched, line_ending_only, unexplained, absent = [], [], [], []
    for row in rows:
        name = row.get('old')
        registered = row.get('sha256_before')
        if not name or not registered:
            continue
        path = backup_dir / name
        if not path.is_file():
            absent.append(name)
            continue
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() == registered:
            matched.append(name)
            continue
        variants = (raw.replace(b'\r\n', b'\n'), raw.replace(b'\n', b'\r\n'))
        if any(hashlib.sha256(variant).hexdigest() == registered for variant in variants):
            line_ending_only.append(name)
        else:
            unexplained.append(name)
    return {
        'status': 'COMPLETE',
        'checked': len(matched) + len(line_ending_only) + len(unexplained),
        'matched': len(matched),
        'line_ending_only': sorted(line_ending_only),
        'unexplained': sorted(unexplained),
        'backups_absent': sorted(absent),
        'registered_hashes_rewritten': False,
        'note': '登记的 sha256_before 保持原值；差异只报告不覆盖，'
                '换行差异与未解释差异分列，二者都不证明权重或场数据损坏。',
    }


def main():
    from project_paths import configure
    configure()
    from project_harness import load_plan, validate_plan, available_tasks, read_events
    import torch
    old, new = runs('mechanism_1h_v2'), runs('mechanism_2h_v1')
    s_p = ROOT / 'evidence/mechanism_1h_v2/runs/S_P_retry'
    pointer = read(s_p / 'checkpoint_pointer.json')
    cp = s_p / pointer['path']
    heartbeat = read(s_p / 'heartbeat.json')
    checkpoint = torch.load(cp, map_location='cpu', weights_only=False)
    # State may be wrapped by the solver entrypoint; inspect actual schema rather than assume recovery.
    inner = checkpoint.get('solver', checkpoint)
    progress = inner.get('fit_progress', {})
    heartbeat_after_cp = datetime.fromisoformat(heartbeat['updated_at']).timestamp() > cp.stat().st_mtime
    tail_lower = int(heartbeat['updates']) if heartbeat_after_cp else 0
    old_sum = sum(r['recorded_updates'] for r in old.values())
    new_sum = sum(r['recorded_updates'] for r in new.values())
    state = load_plan(ROOT)
    errors = validate_plan(state, ROOT)
    layout = read(OUT / 'layout_validation.json')
    tests = rows(ROOT / 'records/lab_runs.jsonl')
    required_runs = {str(r['id']): {'exit_code': r['exit_code'], 'seconds': r['seconds'], 'argv': r['argv']}
                     for r in tests if r['id'] in (264, 265, 266, 267, 268, 269, 270, 271, 272)}
    allow_root = {'.gitignore', 'AGENTS.md', 'CLAUDE.md', 'README.md', 'STATUS.md', 'PLAN.md',
                  'RESULTS.md', 'run.py', 'project_paths.py', 'lab_log.py'}
    root_files = sorted(p.name for p in ROOT.iterdir() if p.is_file())
    unexpected = sorted(set(root_files) - allow_root)
    for name in ('run.py', 'project_paths.py', 'lab_log.py'):
        ast.parse((ROOT / name).read_text(encoding='utf-8-sig'))
    result = {
        'schema': 'pidon-reorganization-delivery-v1', 'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'old_1h': old, 'new_2h': new,
        'old_1h_recorded_updates': old_sum, 'old_1h_exact_updates': None,
        'old_1h_known_lower_bound': old_sum + tail_lower,
        'new_2h_recorded_updates': new_sum,
        'S_P_retry_recovery': {'verdict': 'UNVERIFIED', 'production_resume_in_next_plan': False,
            'checkpoint_sha_matches_pointer': sha(cp) == pointer['sha256'],
            'heartbeat_after_checkpoint': heartbeat_after_cp, 'heartbeat_tail_updates_lower_bound': tail_lower,
            'checkpoint_top_keys': sorted(checkpoint), 'fit_progress': progress,
            'reason': '尾部不在完整步汇总；心跳非完整参数状态；不能以指针存在认证恢复或生成精确成本'},
        'previous_2h_execution_completeness': 'INCOMPLETE',
        'root_files': root_files, 'unexpected_root_files': unexpected,
        'plan_validation_errors': errors,
        'next_tasks': [t['id'] for t in available_tasks(state, read_events(ROOT))],
        # L07: ``all_file_checks_pass`` is a CACHED verdict from an earlier
        # layout_validation run.  Re-verify the original backups against the
        # registered sha256_before here, because a consumer that reads only
        # the cached boolean cannot notice that 89 of 114 backups no longer
        # match their registered bytes.  The registered values are never
        # overwritten with fresh hashes -- that would erase the discrepancy
        # instead of reporting it.
        'migration_integrity': layout['all_file_checks_pass'],
        'migration_integrity_cached_from': 'layout_validation.json',
        'backup_reverification': backup_reverification(),
        'moved_files': layout['moved_file_count'],
        'lab_runs': required_runs, 'production_training_updates_this_delivery': 0,
        'all_new_research_stages': 'NOT_RUN',
        # L06: the JSON used to be published BEFORE the assertions below ran,
        # so a failed audit could leave a document whose three fields still
        # satisfied the report generator.  The status starts as INCOMPLETE and
        # is only rewritten to COMPLETE once every assertion has passed.
        'audit_status': 'INCOMPLETE',
    }
    (OUT / 'audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    assert old_sum == 34939 and new_sum == 4719
    assert heartbeat_after_cp and tail_lower == 183 and sha(cp) == pointer['sha256']
    assert not errors and not unexpected and result['migration_integrity']
    assert required_runs['268']['exit_code'] == 0 and required_runs['270']['exit_code'] == 0
    assert required_runs['272']['exit_code'] == 0
    result['audit_status'] = 'COMPLETE'
    (OUT / 'audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps({'old_recorded': old_sum, 'old_exact': None, 'old_lower_bound': old_sum + tail_lower,
                      'new_recorded': new_sum, 'moved_files': result['moved_files'],
                      'plan_check': 'PASS', 'next_tasks': result['next_tasks'],
                      'production_updates': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
