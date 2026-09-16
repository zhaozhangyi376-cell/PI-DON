"""One-time, hash-checked layout migration. No deletion and no training."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/workspace_reorganization_20260914'
CORE = {'dco', 'fdtd', 'gen_data', 'pidon_solve', 'pidon_contract',
        'pidon_recording', 'head_lstsq', 'paper_protocol', 'reference_cache',
        'rollout', 'exact_stencil'}
EXPLORATORY = {'mini2d', 'symplectic', 'manifold_check', 'diag_coords', 'diag_exp3'}
KEEP = {'AGENTS.md', 'CLAUDE.md', 'README.md', 'STATUS.md', 'PLAN.md',
        'RESULTS.md', '.gitignore', 'lab_log.py', 'project_paths.py', 'run.py',
        'LAB_NOTEBOOK.md', 'lab_runs.jsonl'}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def destination(p):
    if p.name in KEEP:
        return None
    if p.suffix == '.py':
        if p.stem in CORE:
            folder = 'src/pidon'
        elif p.stem.startswith('test_') and p.stem != 'test_dco':
            folder = 'tests'
        elif p.stem.startswith('structured') or p.stem in EXPLORATORY:
            folder = 'scripts/exploratory'
        elif p.stem.startswith(('make_', 'export_')):
            folder = 'scripts/figures'
        elif p.stem.startswith(('audit_', 'verify_', 'review_', 'check_')) or any(
                x in p.stem for x in ('report', 'evidence', 'readback', 'recompute')):
            folder = 'scripts/analysis'
        else:
            folder = 'scripts/experiments'
        return f'{folder}/{p.name}'
    if p.suffix == '.pt':
        return f'assets/models/{p.name}'
    if p.suffix == '.npz':
        return f'assets/datasets/{p.name}' if p.stem.startswith('data_') else f'archive/legacy_results/arrays/{p.name}'
    if p.suffix == '.json':
        folder = 'training_curves' if p.stem.endswith('_hist') else 'metrics'
        return f'archive/legacy_results/{folder}/{p.name}'
    if p.suffix == '.bat':
        return f'archive/legacy_commands/{p.name}'
    if p.name in {'PAPER_FIRST_REVIEW.md', 'PAPER_NOTES.md', 'paper_text.txt'}:
        return f'docs/paper/{p.name}'
    if p.name in {'SERVER_SETUP.md', 'WALKTHROUGH.md'}:
        return f'docs/guides/{p.name}'
    if p.suffix == '.md':
        return f'docs/history/{p.name}'
    raise ValueError(f'Unclassified root file: {p.name}')


def contained(path):
    path = path.resolve()
    path.relative_to(ROOT.resolve())
    if path == ROOT:
        raise ValueError('root is not a file target')
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / 'project/migration_map.json'
    if manifest_path.exists():
        raise FileExistsError('migration already registered; inspect before retrying')
    rows = []
    for p in sorted(ROOT.iterdir()):
        if p.is_file() and (dest := destination(p)):
            q = contained(ROOT / dest)
            contained(p)
            if q.exists():
                raise FileExistsError(q)
            rows.append({'old': p.name, 'new': dest, 'bytes': p.stat().st_size,
                         'sha256_before': sha(p)})
    manifest = {'schema': 'pidon-layout-migration-v1', 'created_at_utc': datetime.now(timezone.utc).isoformat(),
                'purpose': '分类管理；旧证据不改写；路径迁移不是科学认证', 'files': rows}
    (OUT / 'migration_proposed.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    if not a.apply:
        print(json.dumps({'planned_files': len(rows), 'planned_bytes': sum(r['bytes'] for r in rows)}))
        return
    backup = OUT / 'before/root'
    backup.mkdir(parents=True, exist_ok=True)
    for p in ROOT.iterdir():
        if p.is_file() and p.suffix in {'.py', '.md', '.bat', '.txt'}:
            shutil.copy2(p, backup / p.name)
    (OUT / 'before/git_status.txt').write_bytes(subprocess.check_output(['git', 'status', '--short'], cwd=ROOT))
    (OUT / 'before/working_tree.diff').write_bytes(subprocess.check_output(['git', 'diff'], cwd=ROOT))
    manifest_path.parent.mkdir(exist_ok=True)
    # The proposed map is durable before moving the first file.
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    journal = OUT / 'migration_events.jsonl'
    for row in rows:
        p, q = contained(ROOT / row['old']), contained(ROOT / row['new'])
        q.parent.mkdir(parents=True, exist_ok=True)
        p.rename(q)
        row['sha256_after_move'] = sha(q)
        if row['sha256_before'] != row['sha256_after_move']:
            raise RuntimeError(f'hash mismatch: {q}')
        with journal.open('a', encoding='utf-8') as f:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    manifest['status'] = 'MOVED_HASH_VERIFIED'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'moved': len(rows), 'all_hashes_equal': True, 'deleted': 0}))


if __name__ == '__main__':
    main()
