"""One-time mechanical import/root updates, logged separately from science."""
from __future__ import annotations
import ast
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from layout_guard import LayoutSafetyError, safe_target, validate_migration_table


def main():
    manifest_path = ROOT / 'project/migration_map.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    # L01: validate the whole table before touching a single file.  The old
    # code did ROOT / row['new'] and read/wrote it straight away, so an
    # absolute path, a '..' segment or a registered directory replaced by a
    # link would have been followed out of the project -- and the new hash
    # written back into the table as an ordinary layout adaptation.
    problems = validate_migration_table(ROOT, manifest['files'], must_exist=False)
    if problems:
        raise LayoutSafetyError('migration table is not safe to apply:\n  '
                                + '\n  '.join(problems))
    changed = []
    for row in manifest['files']:
        if not str(row['new']).endswith('.py'):
            continue
        p = safe_target(ROOT, row['new'])
        if p.suffix != '.py':
            continue
        original = p.read_text(encoding='utf-8-sig')
        if '# Project layout bootstrap' in original:
            raise RuntimeError(f'already patched: {p}')
        tree = ast.parse(original)
        end = 0
        if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
            end = tree.body[0].end_lineno
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == '__future__':
                end = node.end_lineno
        if not end and original.startswith('#!'):
            end = 1
        lines = original.splitlines(keepends=True)
        depth = len(Path(row['new']).parts) - 1
        header = ("\n# Project layout bootstrap (imports and paths only).\n"
                  "import sys as _layout_sys\nfrom pathlib import Path as _LayoutPath\n"
                  f"_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[{depth}]))\n"
                  "from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy\n"
                  "_layout_configure()\n\n")
        text = ''.join(lines[:end]) + header + ''.join(lines[end:])
        text = re.sub(r'Path\(__file__\)\.resolve\(\)\.parent(?!s)', 'PROJECT_ROOT', text)
        # Readers which explicitly bind project-root input paths retain old names via ROOT lookup.
        text = text.replace('Path(__file__).parent', 'PROJECT_ROOT')
        if p.name == 'pidon_recording.py':
            text = text.replace('path = Path(path)', 'path = Path(resolve_legacy(path))', 1)
            text = text.replace('name: sha256_file(root / name)', 'name: sha256_file(root / name if (root / name).is_file() else PROJECT_ROOT / name)')
        if p.name == 'pidon_solve.py':
            text = text.replace('torch.load(a.init,', 'torch.load(resolve_legacy(a.init),')
            text = text.replace('os.path.isfile(a.init)', 'Path_for_layout(a.init).is_file()')
            text = text.replace('Path_for_layout(a.init)', '_LayoutPath(resolve_legacy(a.init))')
        if p.name in {'test_dco.py', 'train_dco.py'}:
            text = text.replace('torch.load(path,', 'torch.load(resolve_legacy(path),')
            text = text.replace('torch.load(a.init,', 'torch.load(resolve_legacy(a.init),')
            text = text.replace('np.load(path)', 'np.load(resolve_legacy(path))')
        if p.name == 'verify_claims.py':
            text = text.replace('def run_claim(cid, name, cmd, pat, ok_fn, crit):',
                                'def run_claim(cid, name, cmd, pat, ok_fn, crit):\n    cmd = [cmd[0], str(resolve_legacy(cmd[1])), *cmd[2:]]')
        ast.parse(text)
        p.write_text(text, encoding='utf-8', newline='\n')
        row['sha256_current'] = hashlib.sha256(p.read_bytes()).hexdigest()
        row['change'] = 'layout_import_and_path_only; original byte copy in evidence/workspace_reorganization_20260914/before/root'
        changed.append(row['new'])
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'evidence/workspace_reorganization_20260914/path_repairs.json').write_text(
        json.dumps({'files': changed, 'scientific_algorithm_edits': 0}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'path_adapted_python_files': len(changed), 'training_updates': 0}))


if __name__ == '__main__':
    main()
