"""Durable, append-only recording helpers for formal stage-2 runs."""

from __future__ import annotations

import hashlib
import json
import os
import random
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch


def sha256_file(path: str | Path) -> str | None:
    path = Path(path)
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_hashes(root: str | Path) -> dict[str, str | None]:
    root = Path(root)
    return {
        name: sha256_file(root / name)
        for name in ("pidon_solve.py", "pidon_contract.py", "pidon_recording.py", "fdtd.py", "dco.py")
    }


def capture_rng() -> dict[str, Any]:
    state: dict[str, Any] = {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch_cpu": torch.get_rng_state(),
    }
    if torch.cuda.is_available():
        state["torch_cuda"] = torch.cuda.get_rng_state_all()
    return state


def restore_rng(state: dict[str, Any]) -> None:
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch_cpu"])
    if "torch_cuda" in state and torch.cuda.is_available():
        torch.cuda.set_rng_state_all(state["torch_cuda"])


def atomic_torch_save(payload: Any, destination: str | Path) -> None:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False, suffix=".tmp") as handle:
        temporary = Path(handle.name)
    try:
        torch.save(payload, temporary)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


class RunRecorder:
    """Writes metadata once, JSONL summaries incrementally and atomic states."""

    def __init__(self, out_dir: str | Path, metadata: dict[str, Any]):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl = self.out_dir / "steps.jsonl"
        self.metadata_path = self.out_dir / "run_metadata.json"
        if not self.metadata_path.exists():
            metadata = dict(metadata)
            metadata["created_at_utc"] = datetime.now(timezone.utc).isoformat()
            self.metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def append(self, record: dict[str, Any]) -> None:
        with self.jsonl.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def checkpoint(self, payload: dict[str, Any], *, label: str = "checkpoint_latest") -> Path:
        path = self.out_dir / f"{label}.pt"
        if label == "checkpoint_latest" and path.exists():
            prior = self.out_dir / "checkpoint_previous.pt"
            os.replace(path, prior)
        atomic_torch_save(payload, path)
        return path

    def failure_raw(self, payload: dict[str, Any]) -> Path:
        return self.checkpoint(payload, label="failure_raw")

    def snapshot(self, accepted_steps: int, payload: dict[str, Any]) -> Path:
        return self.checkpoint(payload, label=f"snapshot_step_{accepted_steps:04d}")

