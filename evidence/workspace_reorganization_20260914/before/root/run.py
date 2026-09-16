"""Unified entry: py -3.11 run.py <script-name> [arguments]."""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

from project_paths import PROJECT_DIR, SOURCE_DIRS, configure, resolve_legacy


def main():
    configure()
    os.chdir(PROJECT_DIR)
    args = sys.argv[1:]
    if not args or args[0] in {'-h', '--help', 'list'}:
        print('用法: py -3.11 run.py <脚本名> [参数]')
        print('进度: py -3.11 run.py project_harness status')
        print('测试: py -3.11 run.py unittest -v test_project_harness')
        if args and args[0] == 'list':
            for directory in SOURCE_DIRS:
                for p in sorted((PROJECT_DIR / directory).glob('*.py')):
                    print(f'{p.stem:38} {p.relative_to(PROJECT_DIR).as_posix()}')
        return
    name = args.pop(0)
    if name == 'unittest':
        sys.argv = ['unittest', *args]
        runpy.run_module('unittest', run_name='__main__')
        return
    stem = Path(name).stem
    explicit = resolve_legacy(name)
    candidates = [explicit] if explicit.is_file() else [PROJECT_DIR / d / f'{stem}.py' for d in SOURCE_DIRS]
    matches = [p for p in candidates if p.is_file()]
    if len(matches) != 1:
        raise SystemExit(f'脚本不存在或名称不唯一: {name}；用 run.py list 查看。')
    # Resolve old file inputs passed by the caller. No global open()/torch patch.
    resolved = [str(resolve_legacy(s)) if not s.startswith('-') and Path(s).suffix in {'.pt', '.npz', '.json', '.py', '.txt'} else s for s in args]
    sys.argv = [str(matches[0]), *resolved]
    runpy.run_path(str(matches[0]), run_name='__main__')


if __name__ == '__main__':
    main()
