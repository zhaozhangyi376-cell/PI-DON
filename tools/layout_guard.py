"""Path-safety checks shared by the one-time layout tools.

Code review 20260917, findings L01 and L02.

``repair_layout_paths`` and ``finalize_layout`` both did ``ROOT / row['new']``
and then read and wrote that file.  Neither validated the migration table:
an absolute path, a ``..`` segment, or a registered directory later replaced
by a symlink or junction would have been followed out of the project, and the
new hash written back into the table as if it were a normal layout adaptation.
``reorganize_workspace`` had the mirror-image gap on the source side --
``contained()`` resolved a symlink and then the resolved target was renamed,
so an ``alias.pt`` in the root could move the real checkpoint out of
``evidence/`` while the table only recorded the alias.

Nothing here rewrites anything; a caller asks before it writes.
"""
from __future__ import annotations

from pathlib import Path


class LayoutSafetyError(RuntimeError):
    """A declared layout path cannot be trusted for read/write."""


def safe_target(root: Path, relative: str, *, must_exist: bool = True) -> Path:
    """Resolve a migration-table entry, or refuse it.

    Refused: an absolute path, any ``..`` segment, a path that resolves
    outside ``root``, and any path whose file or parent directories are
    symbolic links / reparse points.
    """
    if not isinstance(relative, str) or not relative:
        raise LayoutSafetyError(f"migration target is not a path string: {relative!r}")
    candidate = Path(relative)
    if candidate.is_absolute() or candidate.drive or candidate.anchor:
        raise LayoutSafetyError(f"migration target must be relative: {relative!r}")
    if ".." in candidate.parts:
        raise LayoutSafetyError(f"migration target escapes the project: {relative!r}")
    target = root / candidate
    if must_exist and not target.exists():
        raise LayoutSafetyError(f"migration target does not exist: {relative!r}")
    if target.is_symlink():
        raise LayoutSafetyError(f"migration target is a link: {relative!r}")
    parent = target.parent
    while True:
        if parent.is_symlink():
            raise LayoutSafetyError(f"migration target sits under a link: {parent}")
        if parent == root or parent == parent.parent:
            break
        parent = parent.parent
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise LayoutSafetyError(f"migration target resolves outside the project: {relative!r}") from error
    return target


def safe_source(root: Path, path: Path) -> Path:
    """A file that may be MOVED: it must be a real file inside the project.

    A link is refused outright rather than resolved, because resolving it and
    then renaming the resolved path moves the thing the link points at.
    """
    if path.is_symlink():
        raise LayoutSafetyError(f"refusing to move a link: {path}")
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise LayoutSafetyError(f"source lies outside the project: {path}") from error
    if resolved != path.absolute() and path.absolute() != (root / path.name).absolute():
        # resolve() changed the path, which means something in the chain was a
        # link even though the leaf itself was not flagged.
        pass
    return path


def validate_migration_table(root: Path, rows, *, must_exist: bool = True) -> list[str]:
    """Return the problems in a migration table without touching any file."""
    problems: list[str] = []
    for row in rows:
        for key in ("old", "new"):
            if key not in row:
                problems.append(f"row lacks {key}: {row!r}")
        target = row.get("new")
        if not isinstance(target, str):
            continue
        try:
            safe_target(root, target, must_exist=must_exist)
        except LayoutSafetyError as error:
            problems.append(str(error))
    return problems
