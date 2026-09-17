"""Shared return-audit contract for server ingest tools.

Code review 20260917, findings F04 and F20.

Two different questions were being answered by one boolean:

    "did we successfully READ a document that claims the run finished?"
    "did we independently CHECK that the delivery is complete and coherent?"

``ingest_paper01_theta_full_return`` answered the first and printed PASS: a
lone ``summary.json`` holding ``{"status": "PASS", "variants": [{}]}`` with no
history, no checkpoint, no cost and no metrics produced an audit PASS.
``ingest_paper01_return`` went much further but still accepted a 25,000-row
history whose every row said ``update=25000``, because it only compared the
row COUNT and the LAST number.

The helpers here keep the three layers apart and make each one say why it
failed:

    read_status          the claimed document exists and parses
    delivery_integrity   required files, history numbering, cost, identity
    scientific           never decided here; the caller's registered gates own it

Nothing in this module writes to the evidence tree, and nothing here upgrades
a historical FAIL.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

SCHEMA = "pidon-ingest-delivery-contract-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finite(value: Any) -> float | None:
    """A present, finite float, or None.  NaN/inf never satisfy a gate."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def required_files(output: Path, names: Sequence[str]) -> dict[str, Any]:
    """Which declared deliverables exist, with their sizes and hashes."""
    present: dict[str, Any] = {}
    missing: list[str] = []
    for name in names:
        path = output / name
        if path.is_file():
            present[name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
        else:
            missing.append(name)
    return {"missing": missing, "present": present, "complete": not missing}


def verify_history(path: Path, expected_updates: int | None = None,
                   *, loss_keys: Sequence[str] = ("loss", "train_loss", "test_mse"),
                   lr_key: str = "lr") -> dict[str, Any]:
    """Check a training history line by line instead of counting rows.

    F20: ``rows == 25000 and last == 25000`` is satisfied by 25,000 identical
    rows.  A history is complete only when the update numbers are exactly
    ``1..N``, each appearing once, in order, with a finite loss on every row.
    """
    problems: list[str] = []
    numbers: list[int] = []
    non_finite_rows: list[int] = []
    missing_lr_rows: list[int] = []
    learning_rates: set[float] = set()
    if not path.is_file():
        return {"complete": False, "rows": 0, "problems": ["history file is absent"],
                "expected_updates": expected_updates}
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            problems.append(f"line {line_number}: invalid JSON ({error.msg})")
            continue
        if not isinstance(row, dict) or "update" not in row:
            problems.append(f"line {line_number}: row has no 'update' field")
            continue
        try:
            numbers.append(int(row["update"]))
        except (TypeError, ValueError):
            problems.append(f"line {line_number}: 'update' is not an integer")
            continue
        if not any(finite(row.get(key)) is not None for key in loss_keys
                   if key in row):
            if any(key in row for key in loss_keys):
                non_finite_rows.append(line_number)
        rate = finite(row.get(lr_key))
        if lr_key in row:
            if rate is None:
                missing_lr_rows.append(line_number)
            else:
                learning_rates.add(rate)
    rows = len(numbers)
    duplicates = rows - len(set(numbers))
    if duplicates:
        problems.append(f"{duplicates} duplicated update numbers")
    if numbers != sorted(numbers):
        problems.append("update numbers are not monotonically increasing")
    if expected_updates is not None and numbers != list(range(1, expected_updates + 1)):
        problems.append(
            f"update numbers are not exactly 1..{expected_updates} "
            f"(rows={rows}, first={numbers[0] if numbers else None}, "
            f"last={numbers[-1] if numbers else None})")
    if non_finite_rows:
        problems.append(f"{len(non_finite_rows)} rows carry a non-finite loss "
                        f"(first at line {non_finite_rows[0]})")
    if missing_lr_rows:
        problems.append(f"{len(missing_lr_rows)} rows carry a non-finite learning rate "
                        f"(first at line {missing_lr_rows[0]})")
    return {
        "complete": not problems,
        "rows": rows,
        "unique_updates": len(set(numbers)),
        "first_update": numbers[0] if numbers else None,
        "last_update": numbers[-1] if numbers else None,
        "expected_updates": expected_updates,
        "distinct_learning_rates": sorted(learning_rates)[:8],
        "distinct_learning_rate_count": len(learning_rates),
        "problems": problems,
    }


def verify_optimizer_steps(checkpoint: Path, expected_updates: int | None = None) -> dict[str, Any]:
    """Read the optimizer's own step counter out of a checkpoint.

    A summary can claim any number of updates.  The Adam state inside the
    saved weights is an independent witness of how many parameter updates the
    optimizer actually applied.
    """
    result: dict[str, Any] = {"available": False, "checkpoint": str(checkpoint)}
    if not checkpoint.is_file():
        result["reason"] = "checkpoint is absent"
        return result
    try:
        import torch
    except ImportError:                                          # pragma: no cover
        result["reason"] = "torch is not importable in this environment"
        return result
    try:
        payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    except Exception as error:                                   # noqa: BLE001
        result["reason"] = f"{type(error).__name__}: {error}"
        return result
    steps: list[int] = []
    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "step" and not isinstance(value, (dict, list)):
                    try:
                        steps.append(int(float(value)))
                    except (TypeError, ValueError):
                        pass
                else:
                    walk(value)
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)
    walk(payload)
    result["available"] = bool(steps)
    result["observed_steps"] = sorted(set(steps))[:8]
    result["max_step"] = max(steps) if steps else None
    if expected_updates is not None and steps:
        result["matches_expected"] = max(steps) == expected_updates
    return result


def delivery_verdict(*, read_ok: bool, integrity_checks: dict[str, Any],
                     missing: Iterable[str] = ()) -> dict[str, Any]:
    """Combine the layers.

    A missing deliverable is INCOMPLETE, not FAIL: absent evidence is not a
    scientific verdict, and it must never be reported as a PASS either.
    """
    missing = list(missing)
    failed = sorted(name for name, value in integrity_checks.items() if not value)
    if not read_ok or missing:
        status = "INCOMPLETE"
    elif failed:
        status = "FAIL"
    else:
        status = "PASS"
    return {
        "schema": SCHEMA,
        "status": status,
        "read_status": "OK" if read_ok else "UNREADABLE",
        "delivery_integrity": {
            "complete": not missing,
            "missing": missing,
            "checks": integrity_checks,
            "failed_checks": failed,
        },
        "scientific_result_decided_here": False,
        "note": "交付完整性与科学判据分开；缺件记 INCOMPLETE，不写 PASS，也不改判旧 FAIL。",
    }
