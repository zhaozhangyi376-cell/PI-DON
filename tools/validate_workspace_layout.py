"""Read-only integrity/AST audit and navigation indexes; run through lab_log."""
from __future__ import annotations
import ast
import hashlib
import importlib.util
import json
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/workspace_reorganization_20260914'


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def functions(text):
    tree = ast.parse(text)
    return {node.name: ast.dump(node, include_attributes=False)
            for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}


def suite_ids(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from suite_ids(test)
        else:
            yield test.id()


def main():
    from project_paths import configure, resolve_legacy
    configure()
    manifest = json.loads((ROOT / 'project/migration_map.json').read_text(encoding='utf-8'))
    files = manifest['files']
    integrity = []
    for row in files:
        p = ROOT / row['new']
        if row.get('mutable_append_only'):
            # Existing ledger prefix remains byte-exact; later runs append.
            with p.open('rb') as f:
                digest = hashlib.sha256(f.read(row['bytes'])).hexdigest()
        else:
            digest = sha(p)
        expected = row.get('sha256_current', row['sha256_before'])
        original_copy = OUT / 'before/root' / row['old']
        copy_matches = sha(original_copy) == row['sha256_before'] if p.suffix == '.py' else True
        integrity.append({'old': row['old'], 'new': row['new'], 'exists': p.exists(),
                          'hash_matches': digest == expected, 'original_copy_matches': copy_matches,
                          'old_name_resolves': resolve_legacy(row['old']).resolve() == p.resolve()})
    parsed = []
    for folder in ('src', 'scripts', 'tests', 'tools'):
        for p in sorted((ROOT / folder).rglob('*.py')):
            ast.parse(p.read_text(encoding='utf-8-sig'))
            parsed.append(p.relative_to(ROOT).as_posix())
    ast_results = {}
    for name in ('dco.py', 'fdtd.py', 'pidon_contract.py', 'head_lstsq.py', 'pidon_solve.py'):
        before = functions((OUT / 'before/root' / name).read_text(encoding='utf-8-sig'))
        after = functions((ROOT / 'src/pidon' / name).read_text(encoding='utf-8-sig'))
        ast_results[name] = [key for key in before if before[key] != after.get(key)]
    # Solver.__init__ needs the old checkpoint filename resolved after relocation.
    old_solver = ast.parse((OUT / 'before/root/pidon_solve.py').read_text(encoding='utf-8-sig'))
    new_solver = ast.parse((ROOT / 'src/pidon/pidon_solve.py').read_text(encoding='utf-8-sig'))
    old_class = next(n for n in old_solver.body if isinstance(n, ast.ClassDef) and n.name == 'Solver')
    new_class = next(n for n in new_solver.body if isinstance(n, ast.ClassDef) and n.name == 'Solver')
    old_methods = {n.name: ast.dump(n, include_attributes=False) for n in old_class.body if isinstance(n, ast.FunctionDef)}
    new_methods = {n.name: ast.dump(n, include_attributes=False) for n in new_class.body if isinstance(n, ast.FunctionDef)}
    changed_methods = [n for n in old_methods if old_methods[n] != new_methods.get(n)]
    modules = ('test_project_harness', 'test_pidon_contract', 'test_pidon_contract_v3', 'test_pidon_contract_v4', 'test_mechanism_hour')
    ids = list(suite_ids(unittest.defaultTestLoader.loadTestsFromNames(modules)))
    summary = {
        'schema': 'pidon-layout-validation-v1', 'files': integrity,
        'moved_file_count': len(files), 'all_file_checks_pass': all(all(x[k] for k in ('exists', 'hash_matches', 'old_name_resolves', 'original_copy_matches')) for x in integrity),
        'python_ast_parsed': parsed, 'changed_top_level_definitions': ast_results,
        'changed_solver_methods': changed_methods,
        'test_run': {'lab_log_id': 268, 'execution_count': len(ids), 'unique_test_count': len(set(ids)), 'unique_ids': sorted(set(ids)),
                     'interpretation': '迁移回归，非完整G0；存在导入导致的重复执行，不将重复计作额外覆盖'},
        'production_training_updates': 0,
    }
    (OUT / 'layout_validation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    sections = ['# 文件索引', '', '通过旧名称查位置：`py -3.11 run.py project_harness resolve dco_lr1e3_300.pt`。', '',
                '旧实验中的路径、命令和哈希保持历史原文；迁移映射不赋予旧FAIL恢复资格。', '']
    for folder in sorted({str(Path(r['new']).parent).replace('\\', '/') for r in files}):
        sections += [f'## {folder}', '', '| 文件 | 原位置 | 大小 MiB |', '|---|---|---:|']
        for row in files:
            if str(Path(row['new']).parent).replace('\\', '/') == folder:
                sections.append(f"| [{Path(row['new']).name}](../{row['new']}) | `{row['old']}` | {row['bytes']/(1024**2):.3f} |")
        sections += ['']
    (ROOT / 'docs/FILE_INDEX.md').write_text('\n'.join(sections), encoding='utf-8')
    # Model metadata is a navigation aid, never a training-provenance certificate.
    import torch
    assets = ['# 模型与数据资产', '', '所有旧权重原字节保留。下列训练轮数来自checkpoint自述，不自动等于经过日志认证的实际轮数。', '',
              '| 模型 | checkpoint epoch | 网络 levels/base | 编码 / 归一化 | 原文件SHA256 |', '|---|---:|---|---|---|']
    for row in files:
        if row['new'].startswith('assets/models/'):
            ck = torch.load(ROOT / row['new'], map_location='cpu', weights_only=False)
            if isinstance(ck, dict):
                assets.append(f"| [{Path(row['new']).name}](../{row['new']}) | {ck.get('epoch', 'UNKNOWN')} | {ck.get('levels','?')}/{ck.get('base','?')} | {ck.get('coords','?')} / {ck.get('norm','?')} | `{row['sha256_before']}` |")
            del ck
    import numpy as np
    assets += ['', '## 数据集', '', '下列形状读取npz内npy头，不推断未记录的生成来源。', '', '| 数据 | E / C形状 | 间距D形状 | SHA256 |', '|---|---|---|---|']
    for row in files:
        if row['new'].startswith('assets/datasets/'):
            shapes = {}
            with zipfile.ZipFile(ROOT / row['new']) as z:
                for name in ('E.npy', 'C.npy', 'D.npy'):
                    if name in z.namelist():
                        with z.open(name) as f:
                            version = np.lib.format.read_magic(f)
                            header = np.lib.format.read_array_header_1_0(f) if version == (1, 0) else np.lib.format.read_array_header_2_0(f)
                            shapes[name] = list(header[0])
            assets.append(f"| [{Path(row['new']).name}](../{row['new']}) | {shapes.get('E.npy')} / {shapes.get('C.npy')} | {shapes.get('D.npy')} | `{row['sha256_before']}` |")
    assets += ['', '数据文件按原始文件名存放在 [datasets](../assets/datasets)。训练曲线在 [training_curves](../archive/legacy_results/training_curves)。',
               '正式新实验必须另建协议，记录数据生成参数、划分种子、数据哈希；旧文件名不能替代标签来源证明。']
    (ROOT / 'docs/ASSETS.md').write_text('\n'.join(assets) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k not in ('files', 'python_ast_parsed', 'test_run')}, ensure_ascii=False))
    print(json.dumps({'test_execution_count': len(ids), 'unique_test_count': len(set(ids))}))
    if not summary['all_file_checks_pass']:
        raise SystemExit('MIGRATION_INTEGRITY_FAIL')


if __name__ == '__main__':
    main()
