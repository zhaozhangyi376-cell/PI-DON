from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "_01" / "evidence" / "paper01_ablation_v1"
VARIANTS = ["baseline", "theta_min_0p5", "ez_cap3", "projected_amp"]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def last_jsonl_row(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    last = None
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                last = json.loads(text)
    return last


def variant_status(output: Path, variant: str, target_updates: int) -> dict[str, Any]:
    directory = output / variant
    history_last = last_jsonl_row(directory / "history.jsonl")
    summary_path = directory / "summary.json"
    summary = read_json(summary_path) if summary_path.is_file() else None
    last_update = int(history_last.get("update", 0)) if history_last else 0
    metrics = history_last.get("metrics") if history_last else None
    if summary and summary.get("status") == "COMPLETE":
        state = "COMPLETE"
    elif history_last:
        state = "RUNNING_OR_PARTIAL"
    else:
        state = "NOT_STARTED"
    return {
        "variant": variant,
        "state": state,
        "last_update": last_update,
        "target_updates": target_updates,
        "progress_fraction": last_update / target_updates if target_updates else None,
        "last_train_mse": history_last.get("train_mse") if history_last else None,
        "last_test_mse": history_last.get("test_mse") if history_last else None,
        "last_macro_nmae_mean": metrics.get("macro_nmae_mean") if isinstance(metrics, dict) else None,
        "elapsed_seconds": history_last.get("elapsed_seconds") if history_last else None,
        "summary_macro_nmae_mean": (
            summary.get("final_metrics", {}).get("macro_nmae_mean")
            if isinstance(summary, dict) else None
        ),
    }


def collect_status(output: Path, target_updates: int = 2000) -> dict[str, Any]:
    rows = [variant_status(output, variant, target_updates) for variant in VARIANTS]
    complete = sum(1 for row in rows if row["state"] == "COMPLETE")
    started = sum(1 for row in rows if row["state"] != "NOT_STARTED")
    if complete == len(rows):
        status = "COMPLETE"
    elif started:
        status = "RUNNING_OR_PARTIAL"
    else:
        status = "NOT_STARTED"
    return {
        "schema": "pidon-paper01-ablation-status-v1",
        "status": status,
        "output": str(output),
        "complete_variants": complete,
        "started_variants": started,
        "variant_count": len(rows),
        "variants": rows,
    }


def format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def print_table(data: dict[str, Any]) -> None:
    print(f"PAPER01 ablation status: {data['status']} ({data['complete_variants']}/{data['variant_count']} complete)")
    print(f"Output: {data['output']}")
    print("")
    print("| variant | state | update | train_mse | test_mse | macro_nMAE | elapsed_s |")
    print("|---|---|---:|---:|---:|---:|---:|")
    for row in data["variants"]:
        update = f"{row['last_update']}/{row['target_updates']}"
        macro = row["summary_macro_nmae_mean"]
        if macro is None:
            macro = row["last_macro_nmae_mean"]
        print(
            f"| {row['variant']} | {row['state']} | {update} | "
            f"{format_value(row['last_train_mse'])} | {format_value(row['last_test_mse'])} | "
            f"{format_value(macro)} | {format_value(row['elapsed_seconds'])} |"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-updates", type=int, default=2000)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data = collect_status(args.output, args.target_updates)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print_table(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
