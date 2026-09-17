"""Explicit project paths and old-name lookup; does not change file I/O globally."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
SOURCE_DIRS = ('src/pidon', 'scripts/experiments', 'scripts/analysis',
               'scripts/figures', 'scripts/exploratory', 'tests', 'tools',
               # F13: tests/test_paper01_*.py import ``paper01`` from the
               # independent line.  Without this entry the root
               # ``run.py unittest discover -s tests`` could not import them
               # and reported an error that looked like a broken test.
               '_01/src')

#: Former project roots whose absolute paths may be remapped onto this tree.
#: F07: ``resolve_legacy`` used to fall back to the BASENAME for any absolute
#: path outside the project, so an unrelated external model that merely shared
#: a file name (``Z:/independent_study/dco_lr1e3_300.pt``) was silently
#: rewritten to a local asset and a "the configured paths match" check compared
#: two different weight files.  Only roots registered here are remapped, and a
#: path identity still has to be confirmed by content hash.
LEGACY_ROOTS = tuple(
    part for part in os.environ.get('PIDON_LEGACY_ROOTS', '').split(os.pathsep) if part
) or ('C:/PI-DON', 'C:\\PI-DON', 'H:/PI-DON', 'H:\\PI-DON')


def migration_entries():
    path = PROJECT_DIR / 'project/migration_map.json'
    return json.loads(path.read_text(encoding='utf-8'))['files'] if path.exists() else []


def _legacy_relative(p: Path) -> str | None:
    """The in-project relative name this path denotes, or None.

    A relative path is taken at face value.  An absolute path counts only when
    it lives under this project root or under a REGISTERED former root; an
    absolute path anywhere else is somebody else's file and is returned
    untouched, never reduced to its basename.
    """
    if not p.is_absolute():
        absolute = PROJECT_DIR / p
        try:
            return absolute.resolve().relative_to(PROJECT_DIR).as_posix()
        except ValueError:
            return p.as_posix()
    try:
        return p.resolve().relative_to(PROJECT_DIR).as_posix()
    except ValueError:
        pass
    text = str(p).replace('\\', '/')
    for root in LEGACY_ROOTS:
        prefix = str(root).replace('\\', '/').rstrip('/') + '/'
        if text.lower().startswith(prefix.lower()):
            return text[len(prefix):]
    return None


def resolve_legacy(value):
    """Resolve an explicit former root path; leave other/new paths untouched."""
    p = Path(value)
    relative = _legacy_relative(p)
    if relative is None:
        return p
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
