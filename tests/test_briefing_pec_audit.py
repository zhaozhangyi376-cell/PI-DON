import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

import briefing_pec_audit as audit


class BriefingPECAuditTests(unittest.TestCase):
    def test_tangential_masks_cover_four_faces_per_e_component(self):
        masks = audit.tangential_e_masks(5)
        self.assertEqual(masks["Ex"].shape, (5, 6, 6))
        self.assertEqual(masks["Ey"].shape, (6, 5, 6))
        self.assertEqual(masks["Ez"].shape, (6, 6, 5))
        for mask in masks.values():
            self.assertEqual(int(mask.sum()), 4 * 5 * 5)

    def test_gradient_demo_distinguishes_loss_before_and_after_projection(self):
        result = audit.gradient_support_demo()
        self.assertGreater(result["unprojected_masked_gradient_l1"], 0.0)
        self.assertEqual(result["projected_masked_gradient_l1"], 0.0)
        self.assertGreater(result["projected_unmasked_gradient_l1"], 0.0)

    def test_production_apply_pec_matches_expected_masks(self):
        result = audit.audit_production_pec(5)
        self.assertTrue(result["all_expected_zero"])
        self.assertTrue(result["all_interior_preserved"])
        self.assertEqual(result["unexpected_zero_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
