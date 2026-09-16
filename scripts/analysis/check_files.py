"""Print every script's version stamp.  Run this FIRST whenever anything is
odd -- four separate debugging sessions in this project have turned out to be
a file that was not actually overwritten.

    py -3.11 check_files.py
"""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

import hashlib
import os
import re

FILES = ["fdtd.py", "gen_data.py", "dco.py", "train_dco.py", "train_pidon.py",
         "test_dco.py", "gap_analysis.py", "diag_exp3.py", "manifold_check.py",
         "make_figs.py", "run_fdtd_cavity.py", "cst_compare.py",
         "rollout.py", "check_files.py", "exact_stencil.py", "mini2d.py",
         "symplectic.py", "structured.py"]

# capability markers: the feature each file must have for the current workflow
NEEDS = {
    "fdtd.py": "def source_waveform",          # zero-DC excitation lives here
    "gen_data.py": "def _draw_khat",           # --dirs per-wave
    "dco.py": "def curl_periodic",             # structural div(curl)=0 head
    "train_pidon.py": "t[crop] = cy * Lc / a_sc",   # full-size Yee target
    "test_dco.py": "def k_eff_d",              # handover-band check
    "gap_analysis.py": "WHICH READING OF eq.(5)",   # three-metric comparison
    "diag_exp3.py": "fdtd.source_waveform",
    "manifold_check.py": "def dir_share",
    "make_figs.py": "def fig6",                # gap figure
    "cst_compare.py": "def _unit_from_header",
    "rollout.py": "def selftest",              # scheme verification
    "exact_stencil.py": "def yee_conv",        # the 12-weight result
    "mini2d.py": "class MiniOp",               # end-to-end 2-D demonstration
    "symplectic.py": "def amplification",      # the stability mechanism
    "structured.py": "class Structured",       # 2-D structure-preserving head
    "structured3d.py": "class Sep3D",          # its 3-D counterpart
    "structured.py": "class Structured",       # the stable, accurate operator
}

print(f"{'file':<22} {'version':<14} {'sha1':<10} status")
print("-" * 62)
bad = 0
for f in FILES:
    if not os.path.exists(f):
        print(f"{f:<22} {'-':<14} {'-':<10} MISSING")
        bad += 1
        continue
    src = open(f, encoding="utf-8").read()
    m = re.search(r'SCRIPT_VERSION\s*=\s*"([^"]+)"', src)
    ver = m.group(1) if m else "(none)"
    h = hashlib.sha1(src.encode()).hexdigest()[:8]
    need = NEEDS.get(f)
    if need and need not in src:
        print(f"{f:<22} {ver:<14} {h:<10} STALE -- missing {need!r}")
        bad += 1
    else:
        print(f"{f:<22} {ver:<14} {h:<10} ok")
print()
if bad:
    print(f"{bad} file(s) are stale or missing.  Ask for them BY NAME and copy")
    print("them over before running anything else -- a stale file here has")
    print("cost this project four separate debugging sessions.")
else:
    print("all files current")
