"""Run the separately registered zero-curl negative control for A2."""

from __future__ import annotations

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import json
from pathlib import Path

import numpy as np

from pidon_exact_control import run


OUT = Path("evidence/gpt6_plan_v3/A2_zero_curl_negative.json")
RUN_DIR = Path("evidence/gpt6_plan_v3/A2_control_runs/zero_curl")


def main():
    result = run(np.float64, steps=128, mode="zero", out_dir=RUN_DIR)
    result["negative_control_expected"] = "must fail exact-control field gate after propagation"
    result["negative_control_rejected"] = not result["field_gate_pass"]
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"out": str(OUT), "field_gate_pass": result["field_gate_pass"],
                      "negative_control_rejected": result["negative_control_rejected"]}, ensure_ascii=False))
    if not result["negative_control_rejected"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
