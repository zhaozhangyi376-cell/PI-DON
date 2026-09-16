"""Move the append-only ledgers when no logger is active; complete path metadata."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / 'project/migration_map.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    for row in manifest['files']:
        p = ROOT / row['new']
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
