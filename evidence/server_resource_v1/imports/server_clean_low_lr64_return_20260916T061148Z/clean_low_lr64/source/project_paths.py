"""Explicit project paths and old-name lookup; does not change file I/O globally."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
SOURCE_DIRS = ('src/pidon', 'scripts/experiments', 'scripts/analysis',
               'scripts/figures', 'scripts/exploratory', 'tests', 'tools')


def migration_entries():
    path = PROJECT_DIR / 'project/migration_map.json'
    return json.loads(path.read_text(encoding='utf-8'))['files'] if path.exists() else []


def resolve_legacy(value):
    """Resolve an explicit former root path; leave other/new paths untouched."""
    p = Path(value)
    absolute = p if p.is_absolute() else PROJECT_DIR / p
    try:
        relative = absolute.resolve().relative_to(PROJECT_DIR).as_posix()
    except ValueError:
        relative = p.name if p.is_absolute() else p.as_posix()
    lookup = {row['old']: row['new'] for row in migration_entries()}
    return PROJECT_DIR / lookup[relative] if relative in lookup else p


class _ProjectRoot(type(Path())):
    def __truediv__(self, key):
        # Remap only a former top-level file. Evidence subpaths stay literal.
        return resolve_legacy(Path(str(self)) / key)


ROOT = _ProjectRoot(PROJECT_DIR)


def configure():
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    directories = [str(PROJECT_DIR)] + [str(PROJECT_DIR / p) for p in SOURCE_DIRS]
    for directory in reversed(directories):
        if directory not in sys.path:
            sys.path.insert(0, directory)
    inherited = os.environ.get('PYTHONPATH', '')
    os.environ['PYTHONPATH'] = os.pathsep.join(dict.fromkeys(directories + ([inherited] if inherited else [])))
