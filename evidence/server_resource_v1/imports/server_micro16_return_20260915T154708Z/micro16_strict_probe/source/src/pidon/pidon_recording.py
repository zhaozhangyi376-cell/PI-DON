"""Durable, append-only recording helpers for formal stage-2 runs."""

from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import hashlib
import json
import os
import random
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch


def sha256_file(path: str | Path) -> str | None:
    path = Path(resolve_legacy(path))
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
        name: sha256_file(root / name if (root / name).is_file() else PROJECT_ROOT / name)
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
        # ``torch.save`` closes its own file handle.  Flush the completed
        # temporary file before moving it into the evidence namespace so a
        # power loss cannot leave a named but partly persisted checkpoint.
        with temporary.open("r+b") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def atomic_json_save(payload: dict[str, Any], destination: str | Path) -> None:
    """Replace metadata only after a complete JSON document is durable."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=destination.parent, delete=False,
                                     suffix=".tmp", encoding="utf-8") as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


class RunRecorder:
    """Append-only run evidence with explicit new/resume identity checks."""

    IDENTITY_KEYS = ("run_id", "protocol_hash")

    def __init__(self, out_dir: str | Path, metadata: dict[str, Any], *, mode: str = "new"):
        if mode not in ("new", "resume"):
            raise ValueError(f"unknown recorder mode {mode!r}")
        self.out_dir = Path(out_dir)
        self.jsonl = self.out_dir / "steps.jsonl"
        self.metadata_path = self.out_dir / "run_metadata.json"
        metadata = dict(metadata)
        missing_identity = [key for key in self.IDENTITY_KEYS if not metadata.get(key)]
        if missing_identity:
            raise ValueError("recorder metadata lacks identity: " + ", ".join(missing_identity))
        if self.metadata_path.exists():
            existing = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            if mode == "new":
                raise ValueError("run identity already exists; create a new output directory or use verified resume")
            if any(existing.get(key) != metadata.get(key) for key in self.IDENTITY_KEYS):
                raise ValueError("run identity differs from existing metadata")
            self.metadata = existing
            self._classify_uncheckpointed_tail()
        else:
            if mode == "resume":
                raise FileNotFoundError("cannot resume: run metadata does not exist")
            if self.out_dir.exists() and any(self.out_dir.iterdir()):
                raise ValueError("new run directory is non-empty; refusing to mix evidence")
            self.out_dir.mkdir(parents=True, exist_ok=True)
            metadata["created_at_utc"] = datetime.now(timezone.utc).isoformat()
            metadata["last_committed_sequence_id"] = -1
            metadata["last_checkpoint_sequence_id"] = -1
            metadata["last_checkpoint_serial"] = -1
            metadata["recovery_tail_sequence_ids"] = []
            atomic_json_save(metadata, self.metadata_path)
            self.metadata = metadata
        self._next_sequence_id = int(self.metadata.get("last_committed_sequence_id", -1)) + 1

    def _classify_uncheckpointed_tail(self) -> None:
        """Reconcile a durable JSONL prefix with the metadata pointer.

        The JSONL append is intentionally committed before its metadata
        pointer.  Therefore a metadata-write crash leaves a valid extra row;
        it must be adopted exactly once on resume.  Malformed or non-contiguous
        rows have no unambiguous recovery and are rejected rather than silently
        reusing a sequence id.
        """
        rows: list[dict[str, Any]] = []
        if self.jsonl.exists():
            with self.jsonl.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        raise ValueError(f"invalid JSONL at line {line_number}: blank row")
                    try:
                        row = json.loads(line, parse_constant=lambda token: (_ for _ in ()).throw(
                            ValueError(f"non-finite JSON constant {token}")))
                    except (json.JSONDecodeError, ValueError) as error:
                        raise ValueError(f"invalid JSONL at line {line_number}") from error
                    if not isinstance(row, dict) or not isinstance(row.get("sequence_id"), int):
                        raise ValueError(f"invalid JSONL at line {line_number}: missing sequence_id")
                    if row["sequence_id"] != len(rows):
                        raise ValueError(f"invalid JSONL at line {line_number}: non-contiguous sequence_id")
                    rows.append(row)
        checkpointed = int(self.metadata.get("last_checkpoint_sequence_id", -1))
        metadata_committed = int(self.metadata.get("last_committed_sequence_id", -1))
        durable_committed = len(rows) - 1
        if metadata_committed > durable_committed:
            raise ValueError("invalid JSONL: metadata claims rows absent from durable log")
        if checkpointed > durable_committed:
            raise ValueError("invalid JSONL: checkpoint is beyond durable log")
        # Adopt a post-append/pre-metadata crash tail, never discard it.
        self.metadata["last_committed_sequence_id"] = durable_committed
        self.metadata["recovered_metadata_from_jsonl"] = durable_committed > metadata_committed
        self.metadata["recovery_tail_sequence_ids"] = list(range(checkpointed + 1, durable_committed + 1))
        atomic_json_save(self.metadata, self.metadata_path)

    def _checkpoint_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        item = dict(payload)
        item["recorder_identity"] = {key: self.metadata.get(key) for key in self.IDENTITY_KEYS}
        item["last_committed_sequence_id"] = self.metadata.get("last_committed_sequence_id", -1)
        return item

    def rolling_checkpoint(self, payload: dict[str, Any]) -> Path:
        """Commit a complete state to the inactive A/B slot, then its pointer.

        No slot is overwritten until the other slot is a previously committed
        recovery point.  The pointer records a hash and is written only after
        a loadable new slot exists.  This is the storage-efficient API for
        night trajectories; legacy ``checkpoint_latest`` remains for old
        compatibility tests and historical artifacts.
        """
        payload = self._checkpoint_payload(payload)
        active = self.metadata.get("active_checkpoint_slot")
        slot = "B" if active == "A" else "A"
        path = self.out_dir / f"checkpoint_{slot}.pt"
        atomic_torch_save(payload, path)
        loaded = torch.load(path, map_location="cpu", weights_only=False)
        if loaded.get("recorder_identity") != payload["recorder_identity"]:
            raise ValueError("written checkpoint identity does not round-trip")
        digest = sha256_file(path)
        pointer = {
            "schema": "pidon-rolling-checkpoint-v1", "slot": slot,
            "path": path.name, "sha256": digest,
            "last_committed_sequence_id": payload["last_committed_sequence_id"],
        }
        atomic_json_save(pointer, self.out_dir / "checkpoint_pointer.json")
        self.metadata["active_checkpoint_slot"] = slot
        self.metadata["last_checkpoint_sequence_id"] = int(payload["last_committed_sequence_id"])
        self.metadata["last_checkpoint_serial"] = int(self.metadata.get("last_checkpoint_serial", -1)) + 1
        self.metadata["recovery_tail_sequence_ids"] = []
        atomic_json_save(self.metadata, self.metadata_path)
        return path

    def load_rolling_checkpoint(self) -> dict[str, Any]:
        pointer_path = self.out_dir / "checkpoint_pointer.json"
        if not pointer_path.is_file():
            raise FileNotFoundError("rolling checkpoint pointer does not exist")
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        if pointer.get("schema") != "pidon-rolling-checkpoint-v1":
            raise ValueError("rolling checkpoint pointer schema is invalid")
        path = self.out_dir / str(pointer.get("path", ""))
        if path.name not in {"checkpoint_A.pt", "checkpoint_B.pt"} or not path.is_file():
            raise ValueError("rolling checkpoint pointer path is invalid")
        if sha256_file(path) != pointer.get("sha256"):
            raise ValueError("rolling checkpoint hash differs from pointer")
        payload = torch.load(path, map_location="cpu", weights_only=False)
        expected = {key: self.metadata.get(key) for key in self.IDENTITY_KEYS}
        if payload.get("recorder_identity") != expected:
            raise ValueError("rolling checkpoint identity differs from recorder")
        return payload

    def append(self, record: dict[str, Any]) -> None:
        record = dict(record)
        if "sequence_id" in record:
            raise ValueError("recorder owns sequence_id")
        record["sequence_id"] = self._next_sequence_id
        with self.jsonl.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.metadata["last_committed_sequence_id"] = self._next_sequence_id
        atomic_json_save(self.metadata, self.metadata_path)
        self._next_sequence_id += 1

    def checkpoint(self, payload: dict[str, Any], *, label: str = "checkpoint_latest") -> Path:
        payload = self._checkpoint_payload(payload)
        path = self.out_dir / f"{label}.pt"
        if label == "checkpoint_latest":
            # First create an immutable, independently complete state.  It is
            # never removed by the replacement of the moving latest pointer.
            sequence_id = int(payload["last_committed_sequence_id"])
            serial = int(self.metadata.get("last_checkpoint_serial", -1)) + 1
            immutable = self.out_dir / f"checkpoint_commit_{sequence_id:06d}_{serial:06d}.pt"
            if immutable.exists():
                raise FileExistsError(f"immutable checkpoint already exists: {immutable.name}")
            atomic_torch_save(payload, immutable)
        if label == "checkpoint_latest" and path.exists():
            prior = self.out_dir / "checkpoint_previous.pt"
            shutil.copy2(path, prior)
        atomic_torch_save(payload, path)
        if label == "checkpoint_latest":
            self.metadata["last_checkpoint_sequence_id"] = int(payload["last_committed_sequence_id"])
            self.metadata["last_checkpoint_serial"] = int(self.metadata.get("last_checkpoint_serial", -1)) + 1
            self.metadata["recovery_tail_sequence_ids"] = []
            atomic_json_save(self.metadata, self.metadata_path)
        return path

    def failure_raw(self, payload: dict[str, Any]) -> Path:
        failed_role = payload.get("failed_role", "H")
        attempt = payload.get("fit_progress", {}).get(failed_role, {}).get("attempt_id", "unknown")
        label = f"failure_raw_{self._next_sequence_id:06d}_attempt_{attempt}"
        path = self.out_dir / f"{label}.pt"
        if path.exists():
            raise FileExistsError(f"failure evidence already exists: {path.name}")
        return self.checkpoint(payload, label=label)

    def snapshot(self, accepted_steps: int, payload: dict[str, Any]) -> Path:
        return self.checkpoint(payload, label=f"snapshot_step_{accepted_steps:04d}")
