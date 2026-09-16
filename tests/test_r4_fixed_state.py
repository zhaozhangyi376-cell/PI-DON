"""Regression tests for v2 fixed-state construction before any R4 fit."""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[1]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import unittest

import numpy as np

from r4_fixed_state import fixed_pairs, solver_args


class FixedStateV2Tests(unittest.TestCase):
    def test_pairs_follow_e_source_h_and_keep_complete_six_fields(self):
        pairs = fixed_pairs(31, 0.05, 3.075e-12, (1, 2))
        self.assertEqual(set(pairs), {1, 2})
        first = pairs[1]
        self.assertEqual(first["source_index"], 0)
        self.assertEqual(set(first["before"]), {"Ex", "Ey", "Ez", "Hx", "Hy", "Hz"})
        self.assertEqual(set(first["after_h"]), set(first["before"]))
        # Start from zero H: step 1 E update is only the registered hard source.
        self.assertTrue(np.array_equal(first["before"]["Hx"], np.zeros_like(first["before"]["Hx"])))
        c = 31 // 2
        self.assertEqual(first["after_e"]["Ez"][c, c, c], first["source"])

    def test_no_update_baseline_has_zero_inner_budget(self):
        base = argparse.Namespace(n=31, side=.05, dt=3.075e-12, init="dco_lr1e3_300.pt", lr=3e-4,
                                  tol=1e-4, max_inner=500, per_task_budget_s=360)
        self.assertEqual(solver_args(base, max_inner=0).max_inner, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
