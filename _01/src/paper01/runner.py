from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch

from .data import generate_dataset
from .metrics import summarize
from .model import DCO, component_local_max_normalize


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = PACKAGE_ROOT / "paper_contract.json"


@dataclass
class RunConfig:
    output: Path
    grid: int = 32
    samples: int = 1000
    effective_batch: int = 32
    microbatch: int = 8
    updates: int = 25000
    levels: int = 4
    base: int = 32
    device: str = "cuda"
    learning_rate: float = 1e-4
    seed: int = 2026091701
    validation_every: int = 250
    progress_every: int = 25
    # F10: fraction of the sample pool sealed away from model selection.  The
    # default 0.0 keeps the registered PAPER01-S1 protocol byte-for-byte; a
    # new experiment that wants a real blind score sets it explicitly.
    blind_fraction: float = 0.0


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def _fresh(output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"output directory is non-empty: {output}")
    output.mkdir(parents=True, exist_ok=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _device(name: str) -> torch.device:
    if name.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")
    return torch.device(name)


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _prepare(config: RunConfig) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, list[dict[str, Any]]]:
    shape = (config.grid, config.grid, config.grid)
    fields, curls, coords, specs = generate_dataset(config.samples, shape, config.seed)
    return torch.from_numpy(fields), torch.from_numpy(curls), torch.from_numpy(coords), specs


def _batch_loss(net: DCO, fields: torch.Tensor, curls: torch.Tensor, coords: torch.Tensor,
                indices: torch.Tensor, microbatch: int, device: torch.device,
                optimizer: torch.optim.Optimizer) -> float:
    optimizer.zero_grad(set_to_none=True)
    total = 0.0
    n = int(indices.numel())
    for start in range(0, n, microbatch):
        idx = indices[start:start + microbatch]
        field = fields[idx].to(device, non_blocking=True)
        target = curls[idx].to(device, non_blocking=True)
        coord = coords[idx].to(device, non_blocking=True)
        normalized, _ = component_local_max_normalize(target)
        loss = torch.nn.functional.mse_loss(net(field, coord), normalized, reduction="sum")
        loss = loss / (n * normalized[0].numel())
        loss.backward()
        total += float(loss.detach().cpu())
    optimizer.step()
    return total


@torch.no_grad()
def _evaluate(net: DCO, fields: torch.Tensor, curls: torch.Tensor, coords: torch.Tensor,
              indices: torch.Tensor, microbatch: int, device: torch.device) -> tuple[float, dict[str, Any]]:
    net.eval()
    predictions: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    mse_sum = 0.0
    count = 0
    scales: list[np.ndarray] = []
    for start in range(0, int(indices.numel()), microbatch):
        idx = indices[start:start + microbatch]
        field = fields[idx].to(device)
        target = curls[idx].to(device)
        coord = coords[idx].to(device)
        normalized, scale = component_local_max_normalize(target)
        prediction = net(field, coord)
        mse_sum += float(torch.nn.functional.mse_loss(prediction, normalized, reduction="sum").cpu())
        count += normalized.numel()
        predictions.append(prediction.cpu().numpy())
        targets.append(normalized.cpu().numpy())
        # F09/F11: keep the per-component scale the normalisation removed, so
        # a physical-unit relL2 can be reported next to the normalised one and
        # the restoration rule is visible rather than implicit.
        scales.append(scale.reshape(scale.shape[0], 3).cpu().numpy())
    net.train()
    pred = np.concatenate(predictions)
    true = np.concatenate(targets)
    return mse_sum / count, summarize(pred, true, np.concatenate(scales))


def _manifest(config: RunConfig, mode: str, net: DCO) -> dict[str, Any]:
    return {
        "schema": "pidon-paper01-s1-run-v1",
        "created_utc": _utc(),
        "mode": mode,
        "claim": "paper-explicit reference; not author-code identity",
        "config": {**asdict(config), "output": str(config.output)},
        "contract_sha256": _sha256(CONTRACT),
        "parameter_count": net.n_parameters(),
        "initial_checkpoint": None,
        "old_evidence_reused": False,
    }


def _save_checkpoint(path: Path, net: DCO, optimizer: torch.optim.Optimizer,
                     update: int, best_mse: float, config: RunConfig) -> None:
    """Write the checkpoint beside its destination and rename it into place.

    A direct ``torch.save`` onto the live best.pt destroys the previous good
    checkpoint before the new one is complete: an interrupted write leaves no
    loadable file at all.  Also state the resume contract explicitly -- the
    optimizer is saved but the shuffle cursor is not, so the presence of this
    file does not authorise an exact continuation.
    """
    payload = {
        "schema": "pidon-paper01-s1-checkpoint-v2",
        "model": net.state_dict(),
        "optimizer": optimizer.state_dict(),
        "update": update,
        "best_test_mse": best_mse,
        "config": {**asdict(config), "output": str(config.output)},
        "torch_rng_state": torch.get_rng_state(),
        "numpy_rng_state": np.random.get_state(),
        "resume_contract": "weights/optimizer/RNG only; the shuffle generator cursor "
                           "is not persisted, so this file does not authorise an exact resume",
    }
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary)
    with temporary.open("r+b") as handle:
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _run(config: RunConfig, mode: str) -> dict[str, Any]:
    config.output = Path(config.output)
    _fresh(config.output)
    shutil.copy2(CONTRACT, config.output / "paper_contract.json")
    _seed_everything(config.seed)
    device = _device(config.device)
    net = DCO(config.levels, config.base).to(device)
    optimizer = torch.optim.Adam(net.parameters(), lr=config.learning_rate)
    manifest = _manifest(config, mode, net)
    _json(config.output / "manifest.json", manifest)

    data_started = time.perf_counter()
    fields, curls, coords, specs = _prepare(config)
    _json(config.output / "sample_specs.json", specs)
    data_seconds = time.perf_counter() - data_started
    train_n = max(1, int(0.8 * config.samples))
    train_indices = torch.arange(train_n)
    test_indices = torch.arange(train_n, config.samples)
    # F10: this split is computed repeatedly during training and drives the
    # ``best.pt`` selection, then the same samples are reported as the final
    # score.  That makes it a DEVELOPMENT set, not a blind test set, and the
    # split contract below says so instead of leaving the name to imply
    # otherwise.  ``blind_fraction`` (default 0, i.e. unchanged behaviour)
    # carves out a sealed set that selection never touches.
    blind_indices = torch.arange(0)
    blind_fraction = float(getattr(config, "blind_fraction", 0.0) or 0.0)
    if blind_fraction > 0.0 and len(test_indices):
        blind_n = max(1, int(round(blind_fraction * config.samples)))
        blind_n = min(blind_n, max(0, len(test_indices) - 1))
        if blind_n:
            blind_indices = test_indices[-blind_n:]
            test_indices = test_indices[:-blind_n]
    test_is_training_sample = False
    if not len(test_indices):
        test_indices = train_indices[-1:]
        test_is_training_sample = True
    split_contract = {
        "train_samples": int(train_n),
        "dev_samples": int(len(test_indices)),
        "blind_samples": int(len(blind_indices)),
        "dev_used_for_model_selection": True,
        "dev_reported_as_final_score": True,
        "dev_is_a_training_sample_fallback": test_is_training_sample,
        "blind_used_for_selection": False,
        "note": "`test_*` 字段是开发集：训练期间反复评估并据此保存 best，"
                "同一批样本又用于最终指标，因此不是独立盲测。"
                "blind_* 字段（如存在）从未参与选模。",
    }
    generator = torch.Generator().manual_seed(config.seed + 1)
    order = torch.randperm(train_n, generator=generator)
    cursor = 0
    history: list[dict[str, Any]] = []
    learning_rates: list[float] = []
    best_mse = float("inf")
    best_update = 0
    started = time.perf_counter()

    for update in range(1, config.updates + 1):
        if cursor + config.effective_batch > train_n:
            order = torch.randperm(train_n, generator=generator)
            cursor = 0
        selected = train_indices[order[cursor:cursor + config.effective_batch]]
        cursor += config.effective_batch
        loss = _batch_loss(net, fields, curls, coords, selected, config.microbatch, device, optimizer)
        learning_rates.append(float(optimizer.param_groups[0]["lr"]))

        validate = update == 1 or update == config.updates or update % config.validation_every == 0
        metrics = None
        test_mse = None
        if validate:
            test_mse, metrics = _evaluate(net, fields, curls, coords, test_indices,
                                          config.microbatch, device)
            if test_mse < best_mse:
                best_mse = test_mse
                best_update = update
                _save_checkpoint(config.output / "best.pt", net, optimizer, update, best_mse, config)
        elapsed = time.perf_counter() - started
        row = {
            "update": update,
            "train_mse": loss,
            "test_mse": test_mse,
            "metrics": metrics,
            "learning_rate": learning_rates[-1],
            "elapsed_seconds": elapsed,
        }
        history.append(row)
        if update == 1 or update == config.updates or update % config.progress_every == 0:
            eta = elapsed / update * (config.updates - update)
            epoch = update / max(train_n / config.effective_batch, 1)
            metric_text = "-" if test_mse is None else f"{test_mse:.3e}"
            memory = 0.0 if device.type != "cuda" else torch.cuda.max_memory_allocated(device) / 2**30
            print(
                f"[update {update:05d}/{config.updates:05d}] epoch~{epoch:7.2f} "
                f"train_mse={loss:.3e} test_mse={metric_text} lr={learning_rates[-1]:.1e} "
                f"gpu_mem={memory:.2f}GiB elapsed={elapsed:.1f}s eta={eta:.1f}s",
                flush=True,
            )
        if update % 25 == 0 or update == config.updates:
            with (config.output / "history.jsonl").open("w", encoding="utf-8") as handle:
                for item in history:
                    handle.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
            _save_checkpoint(config.output / "last.pt", net, optimizer, update, best_mse, config)

    final_mse, final_metrics = _evaluate(net, fields, curls, coords, test_indices,
                                        config.microbatch, device)
    blind_mse = blind_metrics = None
    if len(blind_indices):
        blind_mse, blind_metrics = _evaluate(net, fields, curls, coords, blind_indices,
                                             config.microbatch, device)
    elapsed = time.perf_counter() - started
    summary = {
        "schema": "pidon-paper01-s1-summary-v1",
        "status": "PASS" if mode == "preflight" else "COMPLETE",
        "scientific_result": "PENDING_REGISTERED_COMPARISON" if mode == "train" else "PREFLIGHT_ONLY",
        "mode": mode,
        "updates": config.updates,
        "parameter_updates": config.updates,
        "learning_rates": learning_rates,
        "best_test_mse": best_mse,
        "best_update": best_update,
        "final_test_mse": final_mse,
        "final_metrics": final_metrics,
        # Same numbers, names that say what the split actually is.
        "best_dev_mse": best_mse,
        "final_dev_mse": final_mse,
        "final_dev_metrics": final_metrics,
        "blind_mse": blind_mse,
        "blind_metrics": blind_metrics,
        "split_contract": split_contract,
        "elapsed_seconds": elapsed,
        "data_seconds": data_seconds,
        "contract_sha256": manifest["contract_sha256"],
        "old_checkpoint_loaded": False,
        "output": str(config.output),
    }
    _json(config.output / "summary.json", summary)
    _json(config.output / "audit.json", {
        "manifest_present": True,
        "contract_present": True,
        "constant_lr": len(set(learning_rates)) == 1 and learning_rates[0] == 1e-4,
        "checkpoint_init": None,
        "parameter_updates": config.updates,
        "best_checkpoint_sha256": _sha256(config.output / "best.pt"),
        "last_checkpoint_sha256": _sha256(config.output / "last.pt") if (config.output / "last.pt").exists() else None,
    })
    (config.output / "REPORT.md").write_text(
        "# Paper01 S1 report\n\n"
        f"- Mode: `{mode}`\n"
        f"- Updates: `{config.updates}`\n"
        f"- Fixed learning rate: `{config.learning_rate}`\n"
        f"- Best normalized DEV MSE: `{best_mse:.8g}` at update `{best_update}`\n"
        f"- Final normalized DEV MSE: `{final_mse:.8g}`\n"
        f"- Blind (never selected on) MSE: `{'-' if blind_mse is None else format(blind_mse, '.8g')}`\n"
        f"- Old checkpoints loaded: `False`\n"
        "- Split contract: the `test_*` split is a development set -- it drives "
        "`best.pt` selection and is then reported as the final score, so it is "
        "not an independent blind test (code review 20260917, F10).\n"
        "- Claim: paper-explicit reference, not author-code identity.\n",
        encoding="utf-8",
    )
    return summary


def run_preflight(config: RunConfig) -> dict[str, Any]:
    return _run(config, "preflight")


def run_training(config: RunConfig) -> dict[str, Any]:
    return _run(config, "train")
