"""Read-only pure-inference verification of the saved A3 candidate states."""

from __future__ import annotations

import json
from pathlib import Path

import torch

from h_layout_candidate import residual, solver_args
from pidon_recording import sha256_file
from pidon_solve import Solver


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "evidence" / "gpt6_plan_v3" / "h_layout_candidate"


def main():
    development = json.loads((OUT / "A3_development.json").read_text(encoding="utf-8"))
    args = solver_args(development["config"])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    rows = []
    for task in development["tasks"]:
        if task.get("status") == "NOT_RUN":
            continue
        for role, filename, which, expected in (
            ("H", f"H_step_{task['step']:04d}.pt", "H", task["saved_parameter_R_H"]),
            ("E_oracle", f"E_oracle_step_{task['step']:04d}.pt", "E", task["oracle_E"]["saved_parameter_R"]),
        ):
            path = OUT / filename
            payload = torch.load(path, map_location="cpu", weights_only=False)
            solver = Solver(args, device)
            solver.load_state_payload(payload)
            observed = residual(solver, which)["R"]
            rows.append({"step": task["step"], "role": role, "path": filename,
                         "sha256": sha256_file(path), "saved_R": expected, "readback_R": observed,
                         "abs_difference": abs(observed - expected),
                         "passed": abs(observed - expected) <= 1e-10})
    result = {"schema": "pidon-a3-readback-v3", "classification": "read_only_pure_inference",
              "device": device, "rows": rows, "all_pass": all(row["passed"] for row in rows)}
    (OUT / "A3_readback.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(OUT / "A3_readback.json"), "all_pass": result["all_pass"]}, ensure_ascii=False))
    if not result["all_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
