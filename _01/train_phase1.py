from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from paper01.runner import RunConfig, run_preflight, run_training


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("preflight", "train"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--microbatch", type=int, default=8)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--validation-every", type=int, default=250)
    args = parser.parse_args()
    if args.mode == "preflight":
        config = RunConfig(output=args.output, grid=8, samples=8, effective_batch=4,
                           microbatch=2, updates=2, levels=2, base=2,
                           device=args.device, validation_every=1, progress_every=1)
        summary = run_preflight(config)
    else:
        config = RunConfig(output=args.output, device=args.device,
                           microbatch=args.microbatch,
                           validation_every=args.validation_every,
                           progress_every=args.progress_every)
        summary = run_training(config)
    print(json.dumps({
        "status": summary["status"],
        "scientific_result": summary["scientific_result"],
        "updates": summary["updates"],
        "output": str(args.output),
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
