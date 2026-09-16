
# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[1]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

import unittest

import paper_protocol as PP
from mechanism_decision_eval import make_specs, sample_spec, wave_numbers


class MechanismDecisionEvaluationTests(unittest.TestCase):
    def test_wave_number_accessor_accepts_both_registered_metadata_schemas(self):
        paper = PP.wave_spec(20260914)
        random = make_specs(20260914, 1)[0]
        self.assertEqual(wave_numbers(paper), paper["k"])
        self.assertEqual(wave_numbers(random), random["k_rad_per_m"])

    def test_paper_protocol_wave_spec_is_a_valid_analytic_sampling_input(self):
        spec = dict(PP.wave_spec(20260914), sample_id="paper_fixed")
        e, c, h = sample_spec(spec, (32, 32, 32), .0192)
        self.assertEqual(e.shape, (3, 32, 32, 32))
        self.assertEqual(c.shape, (3, 32, 32, 32))
        self.assertEqual(h.shape, (3,))


if __name__ == "__main__":
    unittest.main(verbosity=2)
