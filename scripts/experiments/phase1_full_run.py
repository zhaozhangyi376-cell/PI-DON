"""S1 complete phase-1 DCO training and blind test.

This is a bounded, single-recipe production run for the direct mechanism plan.
It reuses the current gen_data/DCO mathematics, but streams batches so a
32^3, 1000-sample run can fit on the local GPU.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch

from project_paths import PROJECT_DIR, configure
configure()

import dco as D
import gen_data as G
import paper_protocol as P
from pidon_recording import atomic_json_save, sha256_file, source_hashes


ROOT = PROJECT_DIR
OUT = ROOT / "evidence" / "direct_mechanism_v1" / "s1_phase1"
PLAN = ROOT / "docs" / "plans" / "2026-09-14-direct-mechanism-plan.md"
SCHEMA = "pidon-s1-phase1-full-v1"

DATA_SEED = 2026091701
BLIND_SEED = 2026091702
TRAIN_SEED = 2026091703
N_SAMPLES = 1000
TRAIN_N = 800
DEV_N = 200
GRID = (32, 32, 32)
LEVELS = 4
BASE = 32
COORDS = "cellsize"
NORM = "rms"
DIRS = "shared"
LR = 1e-4
ETA_MIN = 2e-6
EPOCHS = 1000
STEPS_PER_EPOCH = 25
EFFECTIVE_BATCH = 32
VALIDATE_EVERY = 10
BLIND_SAMPLES = 16
BLIND_SHAPES = ((32, 32, 32), (64, 64, 64), (64, 96, 16), (32, 64, 16))
NMAE_GATE = 0.01
REL_L2_P90_GATE = 0.05


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_json_save(payload, path)


def jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return display(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def shape3(shape: int | tuple[int, int, int]) -> tuple[int, int, int]:
    if isinstance(shape, int):
        return (shape, shape, shape)
    return tuple(int(v) for v in shape)


def draw_spec(rng: np.random.Generator, d_m: np.ndarray) -> dict[str, Any]:
    n_waves = int(rng.integers(4, 17))
    ks = rng.uniform(1.0, G.K_MAX, size=n_waves).astype(np.float64)
    if DIRS == "shared":
        khat = G._draw_khat(rng).astype(np.float64)
        khats = np.repeat(khat[None, :], n_waves, axis=0)
    else:
        khats = np.stack([G._draw_khat(rng) for _ in range(n_waves)]).astype(np.float64)
    e0 = np.empty((n_waves, 3), dtype=np.float64)
    e0[:, 0] = rng.uniform(0.0, G.AMP_MAX, n_waves)
    e0[:, 1] = rng.uniform(0.0, G.AMP_MAX, n_waves)
    e0[:, 2] = -(khats[:, 0] * e0[:, 0] + khats[:, 1] * e0[:, 1]) / khats[:, 2]
    return {
        "d_m": d_m.astype(np.float64).tolist(),
        "n_waves": n_waves,
        "ks_rad_per_m": ks.tolist(),
        "khats": khats.tolist(),
        "amplitudes": e0.tolist(),
        "dirs": DIRS,
    }


def sample_from_spec(spec: dict[str, Any], shape: tuple[int, int, int],
                     d_m: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    dx, dy, dz = [float(v) for v in d_m]
    nx, ny, nz = shape3(shape)
    x, y, z = np.meshgrid(np.arange(nx) * dx, np.arange(ny) * dy,
                          np.arange(nz) * dz, indexing="ij")
    hx, hy, hz = 0.5 * dx, 0.5 * dy, 0.5 * dz
    pos = {
        "Ex": (x + hx, y, z),
        "Ey": (x, y + hy, z),
        "Ez": (x, y, z + hz),
        "Cx": (x, y + hy, z + hz),
        "Cy": (x + hx, y, z + hz),
        "Cz": (x + hx, y + hy, z),
    }
    e = np.zeros((3, nx, ny, nz), dtype=np.float32)
    c = np.zeros((3, nx, ny, nz), dtype=np.float32)
    ks = np.asarray(spec["ks_rad_per_m"], dtype=np.float64)
    khats = np.asarray(spec["khats"], dtype=np.float64)
    e0 = np.asarray(spec["amplitudes"], dtype=np.float64)
    for w, k in enumerate(ks):
        k_vec = k * khats[w]
        curl_amp = np.cross(k_vec, e0[w])
        for j, name in enumerate(("Ex", "Ey", "Ez")):
            px, py, pz = pos[name]
            phase = k_vec[0] * px + k_vec[1] * py + k_vec[2] * pz
            e[j] += (e0[w, j] * np.cos(phase)).astype(np.float32)
        for j, name in enumerate(("Cx", "Cy", "Cz")):
            px, py, pz = pos[name]
            phase = k_vec[0] * px + k_vec[1] * py + k_vec[2] * pz
            c[j] += (-curl_amp[j] * np.sin(phase)).astype(np.float32)
    return e, c


def build_dataset() -> dict[str, Any]:
    rng = np.random.default_rng(DATA_SEED)
    e = np.empty((N_SAMPLES, 3, *GRID), dtype=np.float32)
    c = np.empty((N_SAMPLES, 3, *GRID), dtype=np.float32)
    d = np.empty((N_SAMPLES, 3), dtype=np.float32)
    specs: list[dict[str, Any]] = []
    for i in range(N_SAMPLES):
        d_m = rng.uniform(0.3e-3, 0.8e-3, 3).astype(np.float64)
        spec = draw_spec(rng, d_m)
        ei, ci = sample_from_spec(spec, GRID, d_m)
        e[i], c[i], d[i] = ei, ci, d_m.astype(np.float32)
        specs.append(spec)
        if (i + 1) % 50 == 0:
            print(f"data {i + 1}/{N_SAMPLES}", flush=True)
    return {"E": e, "C": c, "D_m": d, "specs": specs}


def build_blind_specs() -> list[dict[str, Any]]:
    rng = np.random.default_rng(BLIND_SEED)
    specs = []
    for _ in range(BLIND_SAMPLES):
        d_m = rng.uniform(0.3e-3, 0.8e-3, 3).astype(np.float64)
        specs.append(draw_spec(rng, d_m))
    return specs


def make_blind_arrays(specs: list[dict[str, Any]], shape: tuple[int, int, int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    e = np.empty((len(specs), 3, *shape), dtype=np.float32)
    c = np.empty((len(specs), 3, *shape), dtype=np.float32)
    d = np.empty((len(specs), 3), dtype=np.float32)
    base = np.array(GRID, dtype=np.float64)
    target = np.array(shape, dtype=np.float64)
    for i, spec in enumerate(specs):
        base_d = np.asarray(spec["d_m"], dtype=np.float64)
        extent = base * base_d
        d_new = extent / target
        ei, ci = sample_from_spec(spec, shape, d_new)
        e[i], c[i], d[i] = ei, ci, d_new.astype(np.float32)
    return e, c, d


def coords_cellsize(d_mm: torch.Tensor, shape: tuple[int, int, int]) -> torch.Tensor:
    return d_mm.view(-1, 3, 1, 1, 1).expand(-1, 3, *shape).contiguous()


def rel_loss_per_sample(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    num = (pred - target).pow(2).flatten(1).mean(1)
    den = target.pow(2).flatten(1).mean(1).clamp_min(1e-20)
    return num / den


def train_microbatch(net: torch.nn.Module, optimizer: torch.optim.Optimizer,
                     E: torch.Tensor, C: torch.Tensor, Dm: torch.Tensor,
                     indices: torch.Tensor, microbatch: int,
                     device: torch.device) -> float:
    optimizer.zero_grad(set_to_none=True)
    total = 0.0
    batch_n = int(indices.numel())
    for start in range(0, batch_n, microbatch):
        idx = indices[start:start + microbatch]
        e = E[idx].to(device, non_blocking=True)
        c = C[idx].to(device, non_blocking=True)
        d_mm = (Dm[idx] * 1e3).to(device, non_blocking=True)
        x = coords_cellsize(d_mm, tuple(e.shape[2:]))
        eh, ch, _, _ = D.normalise(e, c, d_mm, NORM)
        losses = rel_loss_per_sample(net(eh, x), ch)
        loss = losses.sum() / batch_n
        loss.backward()
        total += float(losses.detach().sum().cpu())
        del e, c, d_mm, x, eh, ch, losses, loss
    optimizer.step()
    return total / batch_n


def predict_batches(net: torch.nn.Module, E: torch.Tensor, Dm: torch.Tensor,
                    device: torch.device, batch_size: int) -> np.ndarray:
    net.eval()
    preds = []
    with torch.no_grad():
        for start in range(0, len(E), batch_size):
            e = E[start:start + batch_size].to(device, non_blocking=True)
            d_mm = (Dm[start:start + batch_size] * 1e3).to(device, non_blocking=True)
            x = coords_cellsize(d_mm, tuple(e.shape[2:]))
            eh, _, a, lc = D.normalise(e, None, d_mm, NORM)
            pred = D.denormalise(net(eh, x), a, lc)
            preds.append(pred.detach().cpu().numpy().astype(np.float32))
            del e, d_mm, x, eh, a, lc, pred
    net.train()
    return np.concatenate(preds, axis=0)


def metric_summary(pred: np.ndarray, true: np.ndarray) -> dict[str, Any]:
    samples = []
    for i in range(len(true)):
        vm = P.vector_metrics(pred[i], true[i])
        samples.append(vm)
    macro_nmae = np.array([s["macro_nmae"] for s in samples], dtype=np.float64)
    rel_l2 = np.array([s["global_rel_l2"] for s in samples], dtype=np.float64)
    macro_mre = np.array([s["macro_mre_eq5"] for s in samples], dtype=np.float64)
    components: dict[str, dict[str, float]] = {}
    for name in "xyz":
        components[name] = {
            "mean_nmae": float(np.mean([s["components"][name]["nmae"] for s in samples])),
            "mean_mre_eq5": float(np.mean([s["components"][name]["mre_eq5"] for s in samples])),
            "mean_mae": float(np.mean([s["components"][name]["mae"] for s in samples])),
            "mean_true_max": float(np.mean([s["components"][name]["true_max"] for s in samples])),
            "mean_near_zero_mre_share": float(np.mean([s["components"][name]["near_zero_mre_share"] for s in samples])),
        }
    return {
        "n_samples": int(len(true)),
        "macro_nmae_mean": float(np.mean(macro_nmae)),
        "macro_nmae_median": float(np.median(macro_nmae)),
        "macro_nmae_p90": float(np.percentile(macro_nmae, 90)),
        "macro_nmae_max": float(np.max(macro_nmae)),
        "global_rel_l2_mean": float(np.mean(rel_l2)),
        "global_rel_l2_p90": float(np.percentile(rel_l2, 90)),
        "global_rel_l2_max": float(np.max(rel_l2)),
        "macro_mre_eq5_mean": float(np.mean(macro_mre)),
        "macro_mre_eq5_p90": float(np.percentile(macro_mre, 90)),
        "components": components,
        "individual": samples,
        "gate": {
            # F21: the registered S1 wording was "per-sample three-component
            # macro nMAE <= 1%", but this gate is the MEAN over samples.  One
            # sample at 2% among 99 at 0% passes the mean and fails the
            # per-sample reading.  Both reductions are reported, the mean
            # stays the registered criterion, and neither is described as the
            # other.
            "macro_nmae_mean_le_1pct": bool(float(np.mean(macro_nmae)) <= NMAE_GATE),
            "macro_nmae_every_sample_le_1pct": bool(float(np.max(macro_nmae)) <= NMAE_GATE),
            "samples_above_nmae_gate": int(np.count_nonzero(macro_nmae > NMAE_GATE)),
            "global_rel_l2_p90_le_5pct": bool(float(np.percentile(rel_l2, 90)) <= REL_L2_P90_GATE),
            "reduction": "mean over samples (registered); the per-sample reading "
                         "is reported separately and is NOT interchangeable",
            "pass": bool(float(np.mean(macro_nmae)) <= NMAE_GATE and float(np.percentile(rel_l2, 90)) <= REL_L2_P90_GATE),
        },
    }


def evaluate_dataset(net: torch.nn.Module, E_np: np.ndarray, C_np: np.ndarray,
                     D_np: np.ndarray, device: torch.device, batch_size: int) -> dict[str, Any]:
    E = torch.from_numpy(np.ascontiguousarray(E_np))
    Dm = torch.from_numpy(np.ascontiguousarray(D_np))
    pred = predict_batches(net, E, Dm, device, batch_size)
    return metric_summary(pred, C_np)


def save_checkpoint(path: Path, net: torch.nn.Module, optimizer: torch.optim.Optimizer,
                    scheduler: torch.optim.lr_scheduler._LRScheduler,
                    epoch: int, updates: int, history: list[dict[str, Any]],
                    best: dict[str, Any], microbatch: int) -> None:
    torch.save({
        "schema": SCHEMA,
        "state": net.state_dict(),
        "optimizer": optimizer.state_dict(),
        "scheduler": scheduler.state_dict(),
        "levels": LEVELS,
        "base": BASE,
        "grid": GRID[0],
        "coords": COORDS,
        "norm": NORM,
        "target": "analytic",
        "head": "direct",
        "epoch": int(epoch),
        "updates": int(updates),
        "hist": history,
        "best": best,
        "microbatch": int(microbatch),
        "rng": {
            "python": random.getstate(),
            "numpy": np.random.get_state(),
            "torch_cpu": torch.get_rng_state(),
            "torch_cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
        },
    }, path)


#: Microbatch accumulation is mathematically identical to one full batch, so
#: the only differences allowed here are floating-point reassociation.
EQUIVALENCE_LOSS_REL_TOL = 1e-5
EQUIVALENCE_GRAD_REL_TOL = 1e-4


def full_batch_equivalence(E: torch.Tensor, C: torch.Tensor, Dm: torch.Tensor,
                           device: torch.device, microbatch: int) -> dict[str, Any]:
    batch = torch.arange(EFFECTIVE_BATCH)
    torch.manual_seed(TRAIN_SEED)
    base = D.DCO(levels=LEVELS, base=BASE).to(device)
    state = copy.deepcopy(base.state_dict())

    def run_full() -> tuple[float, dict[str, torch.Tensor]]:
        net = D.DCO(levels=LEVELS, base=BASE).to(device)
        net.load_state_dict(state)
        net.zero_grad(set_to_none=True)
        e = E[batch].to(device)
        c = C[batch].to(device)
        d_mm = (Dm[batch] * 1e3).to(device)
        x = coords_cellsize(d_mm, GRID)
        eh, ch, _, _ = D.normalise(e, c, d_mm, NORM)
        loss = rel_loss_per_sample(net(eh, x), ch).mean()
        loss.backward()
        grads = {name: p.grad.detach().cpu().clone() for name, p in net.named_parameters()
                 if p.grad is not None and name in {"head.weight", "head.bias", "branch.0.c1.weight"}}
        return float(loss.detach().cpu()), grads

    def run_micro() -> tuple[float, dict[str, torch.Tensor]]:
        net = D.DCO(levels=LEVELS, base=BASE).to(device)
        net.load_state_dict(state)
        net.zero_grad(set_to_none=True)
        total = 0.0
        for start in range(0, EFFECTIVE_BATCH, microbatch):
            idx = batch[start:start + microbatch]
            e = E[idx].to(device)
            c = C[idx].to(device)
            d_mm = (Dm[idx] * 1e3).to(device)
            x = coords_cellsize(d_mm, GRID)
            eh, ch, _, _ = D.normalise(e, c, d_mm, NORM)
            losses = rel_loss_per_sample(net(eh, x), ch)
            (losses.sum() / EFFECTIVE_BATCH).backward()
            total += float(losses.detach().sum().cpu())
        grads = {name: p.grad.detach().cpu().clone() for name, p in net.named_parameters()
                 if p.grad is not None and name in {"head.weight", "head.bias", "branch.0.c1.weight"}}
        return total / EFFECTIVE_BATCH, grads

    try:
        full_loss, full_grads = run_full()
        micro_loss, micro_grads = run_micro()
        max_grad_abs = 0.0
        max_grad_rel = 0.0
        for name, gf in full_grads.items():
            gm = micro_grads[name]
            diff = (gf - gm).abs().max().item()
            denom = gf.abs().max().item() + 1e-30
            max_grad_abs = max(max_grad_abs, diff)
            max_grad_rel = max(max_grad_rel, diff / denom)
        # F21: this used to compute the differences and then write PASS
        # unconditionally.  A deliberately batch-size-dependent toy network
        # with a 98.44% relative gradient difference still produced PASS, and
        # the caller did not reject on the numbers either.  Compare against
        # the declared tolerances and say which one failed.
        failures = []
        loss_abs_diff = abs(full_loss - micro_loss)
        loss_rel_diff = loss_abs_diff / (abs(full_loss) + 1e-30)
        if not math.isfinite(loss_abs_diff) or loss_rel_diff > EQUIVALENCE_LOSS_REL_TOL:
            failures.append(f"loss relative difference {loss_rel_diff:.6g} > {EQUIVALENCE_LOSS_REL_TOL:g}")
        if not math.isfinite(max_grad_rel) or max_grad_rel > EQUIVALENCE_GRAD_REL_TOL:
            failures.append(f"gradient relative difference {max_grad_rel:.6g} > {EQUIVALENCE_GRAD_REL_TOL:g}")
        status = "FAIL" if failures else "PASS"
        return {
            "status": status,
            "failures": failures,
            "full_loss": full_loss,
            "micro_loss": micro_loss,
            "loss_abs_diff": loss_abs_diff,
            "loss_rel_diff": loss_rel_diff,
            "max_checked_grad_abs_diff": max_grad_abs,
            "max_checked_grad_rel_diff": max_grad_rel,
            "loss_rel_tolerance": EQUIVALENCE_LOSS_REL_TOL,
            "grad_rel_tolerance": EQUIVALENCE_GRAD_REL_TOL,
            "microbatch": microbatch,
        }
    except RuntimeError as exc:
        if "out of memory" in str(exc).lower():
            if device.type == "cuda":
                torch.cuda.empty_cache()
            return {"status": "OOM", "message": str(exc)[:500], "microbatch": microbatch}
        raise


def preflight_microbatch(E: torch.Tensor, C: torch.Tensor, Dm: torch.Tensor,
                         device: torch.device, preferred: int) -> tuple[int, dict[str, Any]]:
    attempts = []
    for micro in (preferred, 2):
        if micro in [a.get("microbatch") for a in attempts]:
            continue
        torch.manual_seed(TRAIN_SEED)
        net = D.DCO(levels=LEVELS, base=BASE).to(device)
        opt = torch.optim.Adam(net.parameters(), lr=LR)
        try:
            loss = train_microbatch(net, opt, E, C, Dm, torch.arange(EFFECTIVE_BATCH), micro, device)
            attempts.append({"microbatch": micro, "status": "PASS", "loss": loss})
            return micro, {"status": "PASS", "attempts": attempts}
        except RuntimeError as exc:
            if "out of memory" not in str(exc).lower():
                raise
            attempts.append({"microbatch": micro, "status": "OOM", "message": str(exc)[:500]})
            if device.type == "cuda":
                torch.cuda.empty_cache()
    return 0, {"status": "RESOURCE_LIMIT", "attempts": attempts}


def write_report(summary: dict[str, Any]) -> None:
    metrics = summary.get("blind_metrics", {})
    lines = [
        "# S1 Report - Complete Phase-1 Training",
        "",
        f"- Action: `{summary.get('action_id')}`; lab_run_id: `{summary.get('lab_run_id')}`",
        f"- Status: `{summary.get('status')}`; scientific_result: `{summary.get('scientific_result')}`",
        f"- Epochs completed: `{summary.get('epochs_completed')}`; optimizer updates: `{summary.get('updates')}`",
        f"- Best dev epoch: `{summary.get('best', {}).get('epoch')}`; best dev macro nMAE: `{summary.get('best', {}).get('dev_macro_nmae')}`",
        f"- Microbatch/effective batch: `{summary.get('microbatch')}` / `{EFFECTIVE_BATCH}`",
        "",
        "## Blind Test",
        "",
        "| Grid | Gate | mean macro nMAE | p90 relL2 | mean Eq5 MRE | d range mm |",
        "|---|---|---:|---:|---:|---|",
    ]
    for key, item in metrics.items():
        gate = item.get("gate", {}).get("pass")
        d_range = item.get("cell_size_range_mm")
        lines.append(
            f"| {key} | {gate} | {item.get('macro_nmae_mean')} | "
            f"{item.get('global_rel_l2_p90')} | {item.get('macro_mre_eq5_mean')} | {d_range} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- This is a DCO phase-1 score only; it does not count as Algorithm 1 online propagation success.",
        "- nMAE/relative L2 and paper Eq.(5) MRE are reported separately; they are not converted into each other.",
        "- There is no source point or source-outside probe in this phase-1 curl-operator task; those fields are N/A here.",
        "",
        "## Files",
        "",
        f"- Summary JSON: `{display(OUT / 'summary.json')}`",
        f"- Audit JSON: `{display(OUT / 'audit.json')}`",
        f"- History JSONL: `{display(OUT / 'history.jsonl')}`",
        f"- Best checkpoint: `{display(OUT / 'best.pt')}`",
        f"- Last checkpoint: `{display(OUT / 'last.pt')}`",
    ])
    (OUT / "S1_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_stage_status(summary: dict[str, Any]) -> None:
    status_path = OUT.parent / "stage_status.json"
    stage = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {
        "schema": "direct-mechanism-stage-status-v1",
    }
    stage["S1"] = {
        "schema": SCHEMA,
        "status": summary.get("status"),
        "scientific_result": summary.get("scientific_result"),
        "updates": summary.get("updates"),
        "epochs_completed": summary.get("epochs_completed"),
        "best": summary.get("best"),
        "blind_gate_pass": summary.get("blind_gate_pass"),
        "report": display(OUT / "S1_REPORT.md"),
        "summary": display(OUT / "summary.json"),
        "updated_at_utc": utc_now(),
    }
    write_json(status_path, stage)


def run(args: argparse.Namespace) -> dict[str, Any]:
    # F21: ``--allow-existing`` was not a resume.  It rebuilt the model from
    # scratch, overwrote best.pt/last.pt and appended a second training curve
    # to the same history file, so the directory ended up describing two runs
    # as one.  There is no verified resume path here, so the flag now refuses
    # instead of pretending.
    if OUT.exists() and any(OUT.iterdir()):
        raise FileExistsError(
            f"S1 output already exists: {display(OUT)}。"
            "本入口没有经过验证的恢复路径：重开会重置模型、覆盖权重并把两条训练曲线"
            "追加进同一个 history。请使用新的输出目录，并把续跑登记为独立新实验。")
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    device = torch.device(args.device)
    torch.backends.cudnn.benchmark = True
    random.seed(TRAIN_SEED)
    np.random.seed(TRAIN_SEED)
    torch.manual_seed(TRAIN_SEED)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(TRAIN_SEED)

    manifest = {
        "schema": SCHEMA,
        "action_id": args.action_id,
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
        "created_at_utc": utc_now(),
        "plan": display(PLAN),
        "plan_sha256": sha256_file(PLAN),
        "config": {
            "data_seed": DATA_SEED,
            "blind_seed": BLIND_SEED,
            "train_seed": TRAIN_SEED,
            "samples": N_SAMPLES,
            "train": TRAIN_N,
            "dev": DEV_N,
            "grid": GRID,
            "levels": LEVELS,
            "base": BASE,
            "coords": COORDS,
            "norm": NORM,
            "dirs": DIRS,
            "lr": LR,
            "eta_min": ETA_MIN,
            "epochs": EPOCHS,
            "steps_per_epoch": STEPS_PER_EPOCH,
            "effective_batch": EFFECTIVE_BATCH,
            "validate_every": VALIDATE_EVERY,
        },
        "gen_data_constants": {
            "COS_MIN": G.COS_MIN,
            "K_MAX": G.K_MAX,
            "AMP_MAX": G.AMP_MAX,
        },
        "source_hashes": source_hashes(ROOT),
    }
    write_json(OUT / "manifest.json", jsonable(manifest))

    dataset = build_dataset()
    np.savez_compressed(OUT / "train_dev_data.npz",
                        E=dataset["E"], C=dataset["C"], D=dataset["D_m"],
                        n=np.array(GRID), dirs=np.array(DIRS))
    write_json(OUT / "train_dev_specs.json", {"schema": SCHEMA, "specs": dataset["specs"]})
    blind_specs = build_blind_specs()
    write_json(OUT / "blind_specs.json", {"schema": SCHEMA, "specs": blind_specs})

    E_cpu = torch.from_numpy(dataset["E"])
    C_cpu = torch.from_numpy(dataset["C"])
    D_cpu = torch.from_numpy(dataset["D_m"])
    equivalence = full_batch_equivalence(E_cpu, C_cpu, D_cpu, device, args.microbatch)
    microbatch, preflight = preflight_microbatch(E_cpu, C_cpu, D_cpu, device, args.microbatch)
    write_json(OUT / "preflight.json", {"equivalence": equivalence, "microbatch_preflight": preflight})
    if equivalence.get("status") == "FAIL":
        raise SystemExit(
            "拒绝开训：微批累积与等效整批不数值等价 -> "
            + "; ".join(equivalence.get("failures", []))
            + "。等效batch声明不成立时，训练成本与论文口径无法对齐。")
    if microbatch <= 0:
        summary = {
            "schema": SCHEMA,
            "action_id": args.action_id,
            "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
            "status": "RESOURCE_LIMIT",
            "scientific_result": "NOT_RUN",
            "reason": "microbatch_preflight_oom",
            "updates": 0,
            "epochs_completed": 0,
            "microbatch": None,
            "elapsed_s": time.perf_counter() - started,
        }
        write_json(OUT / "summary.json", jsonable(summary))
        write_report(summary)
        update_stage_status(summary)
        return summary

    torch.manual_seed(TRAIN_SEED)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(TRAIN_SEED)
    net = D.DCO(levels=LEVELS, base=BASE).to(device)
    optimizer = torch.optim.Adam(net.parameters(), lr=LR)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=EPOCHS, eta_min=ETA_MIN)
    generator = torch.Generator(device="cpu")
    generator.manual_seed(TRAIN_SEED)
    history: list[dict[str, Any]] = []
    best = {"epoch": None, "dev_macro_nmae": math.inf, "dev_global_rel_l2_p90": math.inf}
    updates = 0
    train_indices_all = torch.arange(TRAIN_N)
    dev_E = dataset["E"][TRAIN_N:]
    dev_C = dataset["C"][TRAIN_N:]
    dev_D = dataset["D_m"][TRAIN_N:]
    history_path = OUT / "history.jsonl"

    for epoch in range(1, EPOCHS + 1):
        perm = train_indices_all[torch.randperm(TRAIN_N, generator=generator)]
        epoch_losses = []
        for step in range(STEPS_PER_EPOCH):
            idx = perm[step * EFFECTIVE_BATCH:(step + 1) * EFFECTIVE_BATCH]
            loss = train_microbatch(net, optimizer, E_cpu, C_cpu, D_cpu, idx, microbatch, device)
            epoch_losses.append(loss)
            updates += 1
        scheduler.step()
        row: dict[str, Any] = {
            "epoch": epoch,
            "updates": updates,
            "train_rel_loss": float(np.mean(epoch_losses)),
            "lr": float(scheduler.get_last_lr()[0]),
            "elapsed_s": time.perf_counter() - started,
        }
        if epoch == 1 or epoch % VALIDATE_EVERY == 0 or epoch == EPOCHS:
            dev_metrics = evaluate_dataset(net, dev_E, dev_C, dev_D, device, args.eval_batch)
            row["dev"] = {
                "macro_nmae_mean": dev_metrics["macro_nmae_mean"],
                "global_rel_l2_p90": dev_metrics["global_rel_l2_p90"],
                "macro_mre_eq5_mean": dev_metrics["macro_mre_eq5_mean"],
            }
            dev_key = float(dev_metrics["macro_nmae_mean"])
            if dev_key < float(best["dev_macro_nmae"]) - 1e-15:
                best = {
                    "epoch": epoch,
                    "updates": updates,
                    "dev_macro_nmae": dev_key,
                    "dev_global_rel_l2_p90": float(dev_metrics["global_rel_l2_p90"]),
                    "dev_macro_mre_eq5_mean": float(dev_metrics["macro_mre_eq5_mean"]),
                }
                save_checkpoint(OUT / "best.pt", net, optimizer, scheduler, epoch, updates, history, best, microbatch)
            print(
                f"epoch {epoch:4d} updates {updates:5d} train {row['train_rel_loss']:.3e} "
                f"dev_nMAE {row['dev']['macro_nmae_mean']:.3e} "
                f"dev_relL2p90 {row['dev']['global_rel_l2_p90']:.3e} "
                f"dev_MRE {row['dev']['macro_mre_eq5_mean']:.3e} "
                f"elapsed {row['elapsed_s']:.1f}s",
                flush=True,
            )
        else:
            print(
                f"epoch {epoch:4d} updates {updates:5d} train {row['train_rel_loss']:.3e} "
                f"elapsed {row['elapsed_s']:.1f}s",
                flush=True,
            )
        history.append(row)
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(jsonable(row), ensure_ascii=False) + "\n")

    save_checkpoint(OUT / "last.pt", net, optimizer, scheduler, EPOCHS, updates, history, best, microbatch)
    best_ck = torch.load(OUT / "best.pt", map_location=device, weights_only=False)
    net.load_state_dict(best_ck["state"])
    blind_metrics: dict[str, Any] = {}
    blind_data_dir = OUT / "blind_data"
    blind_data_dir.mkdir(exist_ok=True)
    for shape in BLIND_SHAPES:
        E_blind, C_blind, D_blind = make_blind_arrays(blind_specs, shape)
        key = "x".join(str(v) for v in shape)
        np.savez_compressed(blind_data_dir / f"blind_{key}.npz",
                            E=E_blind, C=C_blind, D=D_blind, shape=np.array(shape))
        metrics = evaluate_dataset(net, E_blind, C_blind, D_blind, device, args.eval_batch)
        metrics["shape"] = shape
        metrics["cell_size_range_mm"] = [
            float(np.min(D_blind) * 1e3),
            float(np.max(D_blind) * 1e3),
        ]
        blind_metrics[key] = metrics
        print(
            f"blind {key} gate={metrics['gate']['pass']} "
            f"nMAE={metrics['macro_nmae_mean']:.3e} "
            f"relL2p90={metrics['global_rel_l2_p90']:.3e} "
            f"MRE={metrics['macro_mre_eq5_mean']:.3e}",
            flush=True,
        )

    cube_pass = bool(blind_metrics["32x32x32"]["gate"]["pass"])
    migration_pass = all(bool(blind_metrics["x".join(str(v) for v in shape)]["gate"]["pass"])
                         for shape in BLIND_SHAPES if shape != GRID)
    blind_gate_pass = bool(cube_pass and migration_pass)
    summary = {
        "schema": SCHEMA,
        "action_id": args.action_id,
        "lab_run_id": os.environ.get("PIDON_LAB_RUN_ID"),
        "status": "PASS",
        "scientific_result": "PASS" if blind_gate_pass else "FAIL",
        "reason": "completed_single_registered_phase1_training",
        "epochs_completed": EPOCHS,
        "updates": updates,
        "closure": 0,
        "microbatch": microbatch,
        "effective_batch": EFFECTIVE_BATCH,
        "best": best,
        "blind_gate_pass": blind_gate_pass,
        "cube32_gate_pass": cube_pass,
        "migration_gate_pass": migration_pass,
        "blind_metrics": blind_metrics,
        "source_point": "N/A_phase1_no_source",
        "source_outside_probes": "N/A_phase1_no_source",
        # F21: this was literally ``True``.  The shuffle order comes from an
        # independent torch.Generator whose state is NOT in the checkpoint,
        # ``best.pt`` is not necessarily the last state, and ``last.pt`` is
        # only written at the end -- so a resume cannot reproduce the batch
        # sequence.  Report the conditions instead of asserting the verdict.
        "recovery_eligible": False,
        "recovery_contract": {
            "eligible": False,
            "shuffle_generator_state_persisted": False,
            "batch_cursor_persisted": False,
            "global_rng_persisted": True,
            "last_state_written_only_at_end": True,
            "best_is_not_necessarily_last": True,
            "note": "完成本次登记预算不产生追加资格；恢复需要独立 Generator 状态、"
                    "批游标和可验证的最新状态，当前都不满足。",
        },
        "elapsed_s": time.perf_counter() - started,
        "files": {
            "manifest": OUT / "manifest.json",
            "train_dev_data": OUT / "train_dev_data.npz",
            "train_dev_specs": OUT / "train_dev_specs.json",
            "blind_specs": OUT / "blind_specs.json",
            "history": OUT / "history.jsonl",
            "best": OUT / "best.pt",
            "last": OUT / "last.pt",
            "report": OUT / "S1_REPORT.md",
        },
    }
    audit = {
        "schema": SCHEMA + "-audit",
        "summary": summary,
        "preflight": {"equivalence": equivalence, "microbatch_preflight": preflight},
        "strict_scores": {
            "phase1_blind": blind_metrics,
        },
        "diagnostic_scores": {},
        "not_run": {
            "source_probes": "phase1 operator training has no time-domain source/probes",
        },
    }
    write_json(OUT / "summary.json", jsonable(summary))
    write_json(OUT / "audit.json", jsonable(audit))
    write_report(summary)
    update_stage_status(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action-id", required=True)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--microbatch", type=int, default=4)
    parser.add_argument("--eval-batch", type=int, default=2)
    parser.add_argument("--allow-existing", action="store_true",
                        help="已停用：它从来不是恢复，只会重开模型并混合 history（F21）")
    args = parser.parse_args()
    summary = run(args)
    print(json.dumps({
        "status": summary.get("status"),
        "scientific_result": summary.get("scientific_result"),
        "updates": summary.get("updates"),
        "best": summary.get("best"),
        "blind_gate_pass": summary.get("blind_gate_pass"),
        "report": display(OUT / "S1_REPORT.md"),
        "summary": display(OUT / "summary.json"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
