"""Read-only storage refresh after user cleanup; no training or cleanup."""
from datetime import datetime, timezone
from pathlib import Path
import json
import math
import shutil

from pidon_recording import sha256_file

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'evidence/gpt6_plan_v4_review/storage_revision'
PLAN = ROOT / 'docs/superpowers/plans/2026-09-13-pidon-10h-goal-night-plan.md'
GIB = 1024 ** 3


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    destination = OUT / 'storage_audit.json'
    if destination.exists():
        raise FileExistsError(destination)
    old = json.loads((ROOT / 'evidence/gpt6_plan_v4_review/audit.json').read_text(encoding='utf-8'))
    checkpoints = []
    for row in old['historical_fits']:
        path = ROOT / row['path']
        checkpoints.append({'path': row['path'], 'exists': path.is_file(),
            'bytes': path.stat().st_size if path.is_file() else None,
            'sha256': sha256_file(path), 'expected_sha256': row['sha256']})
    preserved = all(row['exists'] and row['sha256'] == row['expected_sha256'] for row in checkpoints)
    disk = shutil.disk_usage(ROOT)
    observed = old['resources']['max_task_checkpoint_bytes']
    conservative_checkpoint_bytes = math.ceil(observed * 1.25)
    counts = {'main_every_256_to_8192': 32, 'main_64_and_128': 2,
              'repeat_seed_128': 1, 'fixed_state_final': 8,
              'two_slots_two_seeds': 4, 'failure_raw_safe_allowance': 8}
    estimate = sum(counts.values()) * conservative_checkpoint_bytes + int(1.25 * GIB)
    normal_budget = min(12 * GIB, max(0, disk.free - 6 * GIB))
    plan_snapshot = OUT / 'plan_before_storage_revision.md'
    if plan_snapshot.exists():
        raise FileExistsError(plan_snapshot)
    shutil.copy2(PLAN, plan_snapshot)
    result = {'measured_at_utc': datetime.now(timezone.utc).isoformat(),
        'classification': 'storage_planning_only_no_training_no_deletion',
        'disk': {'free_bytes': disk.free, 'free_gib': disk.free / GIB,
                 'total_bytes': disk.total, 'old_audit_free_bytes': old['resources']['disk_free_bytes']},
        'checkpoint_max_observed_bytes': observed,
        'conservative_checkpoint_bytes': conservative_checkpoint_bytes,
        'checkpoint_counts_budget': counts, 'other_artifact_allowance_bytes': int(1.25*GIB),
        'estimated_new_artifact_bytes': estimate, 'estimated_new_artifact_gib': estimate/GIB,
        'normal_artifact_budget_bytes': normal_budget, 'normal_artifact_budget_gib': normal_budget/GIB,
        'os_free_floor_bytes': 5*GIB, 'emergency_reserve_bytes': GIB,
        'cleanup_needed_now': estimate > normal_budget,
        'historical_weights_preserved': preserved, 'checkpoints': checkpoints,
        'master_preserved': sha256_file(ROOT/'dco_lr1e3_300.pt') == '3f259bc887a10fac77f6bdf77b43ba1ad6b45827a3f8b9bd685934acc47ca5d7',
        'night_started': (ROOT/'evidence/gpt6_plan_v4_night/night_manifest.json').exists(),
        'original_plan_sha256': sha256_file(plan_snapshot), 'deleted_files': [],
        'formal_dco_updates': 0}
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='checkpoints'},ensure_ascii=False))
    if not preserved or not result['master_preserved']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
