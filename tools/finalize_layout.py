"""Move the append-only ledgers when no logger is active; complete path metadata."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from layout_guard import LayoutSafetyError, safe_target, validate_migration_table


def main():
    path = ROOT / 'project/migration_map.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    # L01/L03: check the declared targets AND the ledger preconditions before
    # rewriting any source.  The old order rewrote every Python file first and
    # only then discovered that the ledgers had already been moved, so a
    # second run normalised line endings and then aborted without saving the
    # migration table.
    problems = validate_migration_table(ROOT, manifest['files'], must_exist=False)
    if problems:
        raise LayoutSafetyError('migration table is not safe to apply:\n  '
                                + '\n  '.join(problems))
    for name in ('LAB_NOTEBOOK.md', 'lab_runs.jsonl'):
        if (ROOT / 'records' / name).exists():
            raise FileExistsError(
                f'records/{name} already exists: 收尾已完成，拒绝再次改写源码。')
        if not (ROOT / name).is_file():
            raise FileNotFoundError(f'{name} 不在根目录，无法完成收尾。')
    for row in manifest['files']:
        if not str(row['new']).endswith('.py'):
            continue
        p = safe_target(ROOT, row['new'])
        if p.suffix == '.py':
            text = p.read_text(encoding='utf-8')
            depth = len(Path(row['new']).parts) - 1
            wrong = f'_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[{depth-1}]))'
            correct = f'_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[{depth}]))'
            text = text.replace(wrong, correct)
            p.write_text(text, encoding='utf-8', newline='\n')
            row['sha256_current'] = hashlib.sha256(p.read_bytes()).hexdigest()
    for name in ('LAB_NOTEBOOK.md', 'lab_runs.jsonl'):
        p, q = ROOT / name, ROOT / 'records' / name
        p.resolve().relative_to(ROOT)
        q.resolve().relative_to(ROOT)
        if q.exists():
            raise FileExistsError(q)
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        row = {'old': name, 'new': q.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size,
               'sha256_before': digest, 'sha256_after_move': digest,
               'mutable_append_only': True}
        q.parent.mkdir(exist_ok=True)
        p.rename(q)
        assert hashlib.sha256(q.read_bytes()).hexdigest() == digest
        manifest['files'].append(row)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print('账本已原样搬入 records；路径登记完成。')


if __name__ == '__main__':
    main()
