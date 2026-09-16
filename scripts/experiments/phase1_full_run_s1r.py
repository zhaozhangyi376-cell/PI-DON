"""S1R server rerun wrapper for complete phase-1 DCO training.

This wrapper intentionally reuses the registered S1 recipe but writes to a new
evidence directory, so the interrupted S1 record remains untouched.
"""
from __future__ import annotations

import argparse
import json

import torch

from project_paths import PROJECT_DIR, configure
configure()

import phase1_full_run as base


base.OUT = PROJECT_DIR / "evidence" / "direct_mechanism_v2" / "s1r_phase1_server"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action-id", required=True)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--microbatch", type=int, default=4)
    parser.add_argument("--eval-batch", type=int, default=2)
    parser.add_argument("--allow-existing", action="store_true")
    args = parser.parse_args()
    summary = base.run(args)
    print(json.dumps({
        "status": summary.get("status"),
        "scientific_result": summary.get("scientific_result"),
        "updates": summary.get("updates"),
        "best": summary.get("best"),
        "blind_gate_pass": summary.get("blind_gate_pass"),
        "report": base.display(base.OUT / "S1_REPORT.md"),
        "summary": base.display(base.OUT / "summary.json"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
