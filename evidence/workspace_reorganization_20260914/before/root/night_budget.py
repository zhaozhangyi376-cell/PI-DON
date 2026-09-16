"""Persistent wall-clock and per-task accounting for the v4 night run.

This module contains no model training.  The manifest is created once with an
exclusive write; all later callers validate it instead of obtaining a new
ten-hour window.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


GIB = 1024 ** 3


class BudgetError(RuntimeError):
    """The persisted protocol disallows the requested action."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise BudgetError("manifest time is missing a timezone")
    return parsed.astimezone(timezone.utc)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_task_id(*, split: str, seed: int, source_index: int, phase: str,
                   input_hash: str, target_hash: str) -> str:
    document = {"split": split, "seed": seed, "source_index": source_index,
                "phase": phase, "input_hash": input_hash, "target_hash": target_hash}
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _atomic_json(payload: dict[str, Any], destination: Path, *, exclusive: bool = False) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        try:
            with destination.open("xb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            raise
        return
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, destination)


@dataclass(frozen=True)
class NightPaths:
    root: Path

    @property
    def manifest(self) -> Path:
        return self.root / "night_manifest.json"

    @property
    def stage_status(self) -> Path:
        return self.root / "stage_status.json"

    @property
    def ledger(self) -> Path:
        return self.root / "resource_ledger.jsonl"


def init_or_load(paths: NightPaths, *, plan_path: Path, master_weight: Path,
                 source_hashes: dict[str, str | None], now: datetime | None = None) -> dict[str, Any]:
    """Create the one allowed night window or validate its immutable identity."""
    now = utc_now() if now is None else now.astimezone(timezone.utc)
    plan_hash = sha256_file(plan_path)
    master_hash = sha256_file(master_weight)
    if not paths.manifest.exists():
        manifest = {
            "schema": "pidon-v4-night-manifest-v1",
            "experiment_id": str(uuid.uuid4()),
            "started_at": now.isoformat(),
            "deadline": (now + timedelta(hours=10)).isoformat(),
            "training_deadline": (now + timedelta(hours=9, minutes=30)).isoformat(),
            "plan_path": str(plan_path), "plan_sha256": plan_hash,
            "master_weight": str(master_weight), "master_weight_sha256": master_hash,
            "source_hashes_at_start": source_hashes,
            "artifact_limit_bytes": 16 * GIB,
            "system_floor_bytes": 5 * GIB,
            "emergency_reserve_bytes": GIB,
            "status": "RUNNING",
        }
        _atomic_json(manifest, paths.manifest, exclusive=True)
        return manifest
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    required = {"experiment_id", "started_at", "deadline", "training_deadline", "plan_sha256",
                "master_weight_sha256", "artifact_limit_bytes", "status"}
    absent = sorted(required - set(manifest))
    if absent:
        raise BudgetError("night manifest lacks required fields: " + ", ".join(absent))
    if manifest["plan_sha256"] != plan_hash:
        raise BudgetError("night plan hash differs from persistent manifest")
    if manifest["master_weight_sha256"] != master_hash:
        raise BudgetError("master weight hash differs from persistent manifest")
    started, deadline, training_deadline = (parse_utc(manifest[key]) for key in
                                             ("started_at", "deadline", "training_deadline"))
    if not (started < training_deadline < deadline):
        raise BudgetError("night manifest has invalid deadline ordering")
    return manifest


def remaining_seconds(manifest: dict[str, Any], *, training: bool, now: datetime | None = None) -> float:
    now = utc_now() if now is None else now.astimezone(timezone.utc)
    boundary = parse_utc(manifest["training_deadline" if training else "deadline"])
    return (boundary - now).total_seconds()


def assert_can_start(manifest: dict[str, Any], *, training: bool, now: datetime | None = None) -> None:
    if manifest.get("status") != "RUNNING":
        raise BudgetError("night manifest is not RUNNING")
    remain = remaining_seconds(manifest, training=training, now=now)
    if remain <= 0:
        label = "training deadline" if training else "night deadline"
        raise BudgetError(f"{label} has elapsed")


def read_ledger(paths: NightPaths) -> list[dict[str, Any]]:
    if not paths.ledger.exists():
        return []
    records: list[dict[str, Any]] = []
    expected = 0
    for raw in paths.ledger.read_text(encoding="utf-8").splitlines():
        record = json.loads(raw)
        if record.get("sequence_id") != expected:
            raise BudgetError("resource ledger has a non-monotonic or duplicate sequence")
        expected += 1
        records.append(record)
    return records


def append_ledger(paths: NightPaths, record: dict[str, Any]) -> dict[str, Any]:
    """Append a durable resource fact; a caller cannot forge its sequence."""
    records = read_ledger(paths)
    item = dict(record)
    if "sequence_id" in item:
        raise BudgetError("ledger owns sequence_id")
    item["sequence_id"] = len(records)
    item.setdefault("recorded_at", utc_now().isoformat())
    item.setdefault("schema", "pidon-v4-night-ledger-v1")
    paths.root.mkdir(parents=True, exist_ok=True)
    with paths.ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return item


def task_usage(paths: NightPaths, task_id: str) -> dict[str, float | int]:
    totals: dict[str, float | int] = {"adam_updates": 0, "head_commits": 0,
                                      "linear_solve_calls": 0, "training_s": 0.0}
    for row in read_ledger(paths):
        if row.get("task_id") == task_id:
            for key in totals:
                totals[key] += row.get(key, 0)
    return totals


def assert_task_budget(paths: NightPaths, task_id: str, *, add_adam: int = 0,
                       add_head: int = 0, add_solve: int = 0,
                       add_training_s: float = 0.0) -> dict[str, float | int]:
    usage = task_usage(paths, task_id)
    if usage["adam_updates"] + add_adam > 499:
        raise BudgetError("task exceeds its 499 Adam-update allowance")
    if usage["head_commits"] + add_head > 1:
        raise BudgetError("task exceeds its one head-commit allowance")
    if usage["linear_solve_calls"] + add_solve > 3:
        raise BudgetError("task exceeds its three component solve allowance")
    if usage["training_s"] + add_training_s > 360.0:
        raise BudgetError("task exceeds its 360-second fit allowance")
    return usage
