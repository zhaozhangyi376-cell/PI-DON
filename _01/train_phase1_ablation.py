from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from paper01.ablation_data import VARIANTS, generate_variant_dataset, variant_contract_stats  # noqa: E402
from paper01.metrics import summarize  # noqa: E402
from paper01.model import DCO, component_local_max_normalize  # noqa: E402


CONTRACT = ROOT / "paper_contract.json"


@dataclass
class AblationConfig:
    output: Path
    variants: list[str]
    grid: int = 32
    samples: int = 1000
    effective_batch: int = 32
    microbatch: int = 8
    updates: int = 2000
    levels: int = 4
    base: int = 32
    device: str = "cuda"
    learning_rate: float = 1e-4
    seed: int = 2026091702
    validation_every: int = 250
    progress_every: int = 50
    # --- F03: what makes the arms comparable -------------------------------
    # The variant index used to be folded into the seed, so every arm changed
    # its network initialisation, its training draw AND its own test draw at
    # the same time.  Each arm was then scored on a test set drawn from its
    # OWN filtered distribution, which is why "the filtered arm scores better
    # on its own paper" cannot be read as "the filter learns the original task
    # better".  These three switches make the intervention the only变量.
    paired_seed: bool = True          # every arm starts from the same RNG stream
    shared_initialization: bool = True  # every arm starts from the same weights
    common_test_variant: str = "baseline"  # one frozen paper all arms also sit
    common_test_samples: int = 200
    common_test_seed_offset: int = 7_000_001


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024, ), b""):
            digest.update(block)
    return digest.hexdigest()


def fresh(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f"output directory is non-empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def device_for(name: str) -> torch.device:
    if name.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    return torch.device(name)


def seed_all(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def save_checkpoint(path: Path, net: DCO, optimizer: torch.optim.Optimizer, update: int, best_mse: float,
                    config: AblationConfig, variant: str) -> None:
    """Write a checkpoint atomically.

    A direct ``torch.save`` onto the live best.pt leaves a truncated file if
    the process dies mid-write, and the previous good checkpoint is already
    gone.  Write beside it and rename.
    """
    payload = {
        "schema": "pidon-paper01-ablation-checkpoint-v2",
        "variant": variant,
        "model": net.state_dict(),
        "optimizer": optimizer.state_dict(),
        "update": update,
        "best_test_mse": best_mse,
        "config": {**asdict(config), "output": str(config.output)},
        "torch_rng_state": torch.get_rng_state(),
        "numpy_rng_state": np.random.get_state(),
        "resume_contract": "weights/optimizer/RNG only; the shuffle cursor is not "
                           "persisted, so this file does not authorise an exact resume",
    }
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary)
    with temporary.open("r+b") as handle:
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def batch_loss(net: DCO, fields: torch.Tensor, curls: torch.Tensor, coords: torch.Tensor,
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
def evaluate(net: DCO, fields: torch.Tensor, curls: torch.Tensor, coords: torch.Tensor,
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
    return mse_sum / count, summarize(np.concatenate(predictions), np.concatenate(targets),
                                      np.concatenate(scales))


def run_variant(config: AblationConfig, variant: str, index: int, total_variants: int,
                common_paper: dict[str, Any] | None = None,
                initial_state: dict[str, Any] | None = None) -> dict[str, Any]:
    out = config.output / variant
    fresh(out)
    # F03: with paired_seed the data stream and the initialisation are the
    # same for every arm, so the variant rule is the single difference.
    seed = config.seed if config.paired_seed else config.seed + index * 1000
    seed_all(seed)
    dev = device_for(config.device)
    shape = (config.grid, config.grid, config.grid)
    data_started = time.perf_counter()
    fields_np, curls_np, coords_np, specs = generate_variant_dataset(config.samples, shape, seed, variant)
    data_seconds = time.perf_counter() - data_started
    write_json(out / "sample_specs.json", specs)
    write_json(out / "variant_contract_stats.json", variant_contract_stats(specs))
    fields = torch.from_numpy(fields_np)
    curls = torch.from_numpy(curls_np)
    coords = torch.from_numpy(coords_np)

    train_n = max(1, int(0.8 * config.samples))
    train_indices = torch.arange(train_n)
    test_indices = torch.arange(train_n, config.samples)
    if not len(test_indices):
        test_indices = train_indices[-1:]
    generator = torch.Generator().manual_seed(seed + 1)
    order = torch.randperm(train_n, generator=generator)
    cursor = 0

    net = DCO(config.levels, config.base).to(dev)
    if config.shared_initialization and initial_state is not None:
        net.load_state_dict({key: value.to(dev) for key, value in initial_state.items()})
    optimizer = torch.optim.Adam(net.parameters(), lr=config.learning_rate)
    manifest = {
        "schema": "pidon-paper01-ablation-run-v2",
        "created_utc": utc(),
        "variant": variant,
        "claim": "diagnostic ablation; not paper reproduction",
        "comparison_contract": {
            "paired_seed": bool(config.paired_seed),
            "shared_initialization": bool(config.shared_initialization and initial_state is not None),
            "own_test_split_is_variant_distribution": True,
            "common_test_variant": config.common_test_variant,
            "note": "自测集来自本臂自己的变体分布，只能作臂内诊断；"
                    "臂间比较看 common_test_metrics（共同试卷）。",
        },
        "config": {**asdict(config), "output": str(config.output)},
        "contract_sha256": sha256(CONTRACT),
        "old_checkpoint_loaded": False,
        "parameter_count": net.n_parameters(),
    }
    write_json(out / "manifest.json", manifest)
    shutil.copy2(CONTRACT, out / "paper_contract.json")

    best_mse = float("inf")
    best_update = 0
    history: list[dict[str, Any]] = []
    started = time.perf_counter()
    for update in range(1, config.updates + 1):
        if cursor + config.effective_batch > train_n:
            order = torch.randperm(train_n, generator=generator)
            cursor = 0
        selected = train_indices[order[cursor:cursor + config.effective_batch]]
        cursor += config.effective_batch
        loss = batch_loss(net, fields, curls, coords, selected, config.microbatch, dev, optimizer)
        validate = update == 1 or update == config.updates or update % config.validation_every == 0
        test_mse = None
        metrics = None
        if validate:
            test_mse, metrics = evaluate(net, fields, curls, coords, test_indices, config.microbatch, dev)
            if test_mse < best_mse:
                best_mse = test_mse
                best_update = update
                save_checkpoint(out / "best.pt", net, optimizer, update, best_mse, config, variant)
        elapsed = time.perf_counter() - started
        history.append({
            "update": update,
            "train_mse": loss,
            "test_mse": test_mse,
            "metrics": metrics,
            "learning_rate": float(optimizer.param_groups[0]["lr"]),
            "elapsed_seconds": elapsed,
        })
        if update == 1 or update == config.updates or update % config.progress_every == 0:
            eta = elapsed / update * (config.updates - update)
            metric = "-" if test_mse is None else f"{test_mse:.3e}"
            memory = 0.0 if dev.type != "cuda" else torch.cuda.max_memory_allocated(dev) / 2**30
            print(
                f"[variant {index + 1}/{total_variants} {variant}] "
                f"update {update:05d}/{config.updates:05d} "
                f"train_mse={loss:.3e} test_mse={metric} "
                f"gpu_mem={memory:.2f}GiB elapsed={elapsed:.1f}s eta={eta:.1f}s",
                flush=True,
            )
        if update % 50 == 0 or update == config.updates:
            with (out / "history.jsonl").open("w", encoding="utf-8") as handle:
                for row in history:
                    handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            save_checkpoint(out / "last.pt", net, optimizer, update, best_mse, config, variant)

    final_mse, final_metrics = evaluate(net, fields, curls, coords, test_indices, config.microbatch, dev)
    # F03: also score this arm on the one frozen paper every arm sits, so the
    # arms can be compared on identical questions rather than on four
    # different ones.
    common_mse = common_metrics = None
    if common_paper is not None:
        common_mse, common_metrics = evaluate(
            net, common_paper["fields"], common_paper["curls"], common_paper["coords"],
            common_paper["indices"], config.microbatch, dev)
    elapsed = time.perf_counter() - started
    summary = {
        "schema": "pidon-paper01-ablation-variant-summary-v2",
        "status": "COMPLETE",
        "scientific_result": "DIAGNOSTIC_ONLY",
        "variant": variant,
        "parameter_updates": config.updates,
        "best_test_mse": best_mse,
        "best_update": best_update,
        "final_test_mse": final_mse,
        "final_metrics": final_metrics,
        "own_test_distribution": variant,
        "common_test_mse": common_mse,
        "common_test_metrics": common_metrics,
        "common_test_variant": config.common_test_variant if common_paper is not None else None,
        "comparison_contract": manifest["comparison_contract"],
        "data_seconds": data_seconds,
        "elapsed_seconds": elapsed,
        "contract_stats": variant_contract_stats(specs),
        "best_checkpoint_sha256": sha256(out / "best.pt"),
        "last_checkpoint_sha256": sha256(out / "last.pt"),
    }
    write_json(out / "summary.json", summary)
    (out / "REPORT.md").write_text(
        "# PAPER01 ablation variant report\n\n"
        f"- Variant: `{variant}`\n"
        f"- Updates: `{config.updates}`\n"
        f"- Best test MSE: `{best_mse:.8g}` at update `{best_update}`\n"
        f"- Macro nMAE mean: `{final_metrics['macro_nmae_mean']}`\n"
        f"- relL2 p90: `{final_metrics['global_rel_l2_p90']}`\n"
        f"- Eq.(5) MRE mean: `{final_metrics['macro_mre_eq5_mean']}`\n"
        "- Claim: diagnostic ablation, not paper reproduction.\n",
        encoding="utf-8",
    )
    return summary


def write_root_report(out: Path, summaries: list[dict[str, Any]]) -> None:
    lines = [
        "# PAPER01 第一阶段小型消融报告",
        "",
        "- 状态：`PASS`；科学含义：`DIAGNOSTIC_ONLY`",
        "- 目的：比较角度奇异处理、Ez幅值限制和幅值构造对短训趋势的影响。",
        "",
        "| 变体 | 更新数 | best 自测 MSE | 自测 macro nMAE | 共同试卷 macro nMAE | 共同试卷 relL2 p90 | Ez amp p90 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    def cell(value: Any) -> str:
        return "—" if value is None else f"{value:.6g}"
    for item in summaries:
        stats = item["contract_stats"]
        metrics = item["final_metrics"]
        common = item.get("common_test_metrics") or {}
        lines.append(
            f"| {item['variant']} | {item['parameter_updates']} | {cell(item['best_test_mse'])} | "
            f"{cell(metrics['macro_nmae_mean'])} | {cell(common.get('macro_nmae_mean'))} | "
            f"{cell(common.get('global_rel_l2_p90'))} | {cell(stats['ez_amplification_p90'])} |"
        )
    contract = summaries[0].get("comparison_contract", {}) if summaries else {}
    lines += [
        "",
        "## 判读边界",
        "",
        "- 本行动是短预算消融，只判断方向，不认证第一阶段最终精度。",
        "- `projected_amp`改变了论文Eq.(4)幅值生成方式，只是诊断对照，不能声称更忠实论文。",
        "- 只有某个变体在短训趋势上显著改善，才值得登记完整1000 epoch重训。",
        "",
        "## 比较合同（F03）",
        "",
        f"- 配对种子：`{contract.get('paired_seed')}`；共同初始权重：`{contract.get('shared_initialization')}`。",
        f"- 共同试卷分布：`{contract.get('common_test_variant')}`。",
        "- 「自测」列来自各臂自己的变体分布，只能作臂内诊断；臂间改善倍数只看共同试卷列。",
        "- 训练干预与测试分布分开登记：过滤掉难角度既改变了训练集，也改变了该臂原来的自测集。",
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_common_paper(config: AblationConfig) -> dict[str, Any] | None:
    """One frozen evaluation set, drawn once, never trained on.

    Its seed is deliberately far from every training seed so no arm can have
    seen these samples.  It is the only set on which the arms are compared.
    """
    if not config.common_test_variant:
        return None
    seed = config.seed + config.common_test_seed_offset
    shape = (config.grid, config.grid, config.grid)
    fields_np, curls_np, coords_np, specs = generate_variant_dataset(
        config.common_test_samples, shape, seed, config.common_test_variant)
    return {
        "fields": torch.from_numpy(fields_np),
        "curls": torch.from_numpy(curls_np),
        "coords": torch.from_numpy(coords_np),
        "indices": torch.arange(config.common_test_samples),
        "specs": specs,
        "seed": seed,
        "variant": config.common_test_variant,
        "samples": int(config.common_test_samples),
    }


def build_initial_state(config: AblationConfig) -> dict[str, Any] | None:
    """One set of starting weights shared by every arm."""
    if not config.shared_initialization:
        return None
    seed_all(config.seed)
    net = DCO(config.levels, config.base)
    return {key: value.detach().cpu().clone() for key, value in net.state_dict().items()}


def run(config: AblationConfig) -> dict[str, Any]:
    fresh(config.output)
    common_paper = build_common_paper(config)
    initial_state = build_initial_state(config)
    if common_paper is not None:
        write_json(config.output / "common_test_specs.json", common_paper["specs"])
        write_json(config.output / "common_test_contract.json", {
            "variant": common_paper["variant"],
            "seed": common_paper["seed"],
            "samples": common_paper["samples"],
            "stats": variant_contract_stats(common_paper["specs"]),
            "note": "共同试卷：每臂都在这一份题目上评分，种子与任何训练集分离。",
        })
    summaries = []
    for index, variant in enumerate(config.variants):
        summaries.append(run_variant(config, variant, index, len(config.variants),
                                     common_paper=common_paper, initial_state=initial_state))
    summary = {
        "schema": "pidon-paper01-ablation-summary-v2",
        "status": "PASS",
        "scientific_result": "DIAGNOSTIC_ONLY",
        "parameter_updates": int(config.updates) * len(config.variants),
        "variants": summaries,
        "config": {**asdict(config), "output": str(config.output)},
        "old_checkpoint_loaded": False,
        "comparison_contract": {
            "paired_seed": bool(config.paired_seed),
            "shared_initialization": bool(initial_state is not None),
            "common_test_variant": config.common_test_variant if common_paper else None,
            "common_test_samples": int(config.common_test_samples) if common_paper else 0,
            "note": "臂间比较只用 common_test_metrics；各臂 final_metrics 来自"
                    "各自变体分布，是臂内诊断。",
        },
    }
    write_json(config.output / "summary.json", summary)
    write_root_report(config.output, summaries)
    return summary


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--device", default="cuda")
    p.add_argument("--updates", type=int, default=2000)
    p.add_argument("--samples", type=int, default=1000)
    p.add_argument("--grid", type=int, default=32)
    p.add_argument("--microbatch", type=int, default=8)
    p.add_argument("--validation-every", type=int, default=250)
    p.add_argument("--progress-every", type=int, default=50)
    p.add_argument("--variants", nargs="+", default=list(VARIANTS), choices=list(VARIANTS))
    p.add_argument("--common-test-variant", default="baseline", choices=list(VARIANTS) + [""],
                   help="每臂共同评分的冻结试卷分布；空字符串表示不建共同试卷")
    p.add_argument("--common-test-samples", type=int, default=200)
    p.add_argument("--legacy-variant-seeds", action="store_true",
                   help="复现修复前行为：变体索引同时改变种子/初始化/数据（仅用于对照旧结果）")
    return p


def main() -> None:
    args = parser().parse_args()
    config = AblationConfig(
        output=args.output,
        variants=list(args.variants),
        grid=args.grid,
        samples=args.samples,
        microbatch=args.microbatch,
        updates=args.updates,
        device=args.device,
        validation_every=args.validation_every,
        progress_every=args.progress_every,
        paired_seed=not args.legacy_variant_seeds,
        shared_initialization=not args.legacy_variant_seeds,
        common_test_variant=args.common_test_variant,
        common_test_samples=args.common_test_samples,
    )
    summary = run(config)
    print(json.dumps({
        "status": summary["status"],
        "scientific_result": summary["scientific_result"],
        "variants": [item["variant"] for item in summary["variants"]],
        "updates": summary["parameter_updates"],
        "output": str(config.output),
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
