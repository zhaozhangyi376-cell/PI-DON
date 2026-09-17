import unittest

import numpy as np

from paper01.ablation_data import draw_variant_spec, ez_amplification, variant_contract_stats


class Paper01AblationDataTests(unittest.TestCase):
    def test_theta_min_variant_stays_away_from_eq4_singularity(self):
        rng = np.random.default_rng(123)
        for _ in range(20):
            spec = draw_variant_spec(rng, "theta_min_0p5")
            self.assertGreaterEqual(abs(float(np.cos(float(spec["theta"])))), 0.5)

    def test_ez_cap_variant_enforces_registered_cap(self):
        rng = np.random.default_rng(456)
        for _ in range(20):
            spec = draw_variant_spec(rng, "ez_cap3")
            self.assertLessEqual(ez_amplification(spec), 3.0)

    def test_projected_variant_is_transverse_but_marked_diagnostic(self):
        rng = np.random.default_rng(789)
        spec = draw_variant_spec(rng, "projected_amp")
        khat = np.asarray(spec["khat"])
        amplitudes = np.asarray(spec["amplitudes"])
        self.assertLess(float(np.max(np.abs(amplitudes @ khat))), 1e-12)
        self.assertTrue(spec["diagnostic_not_paper_literal"])

    def test_contract_stats_reports_ez_amplification(self):
        rng = np.random.default_rng(999)
        specs = [draw_variant_spec(rng, "baseline") for _ in range(5)]
        stats = variant_contract_stats(specs)
        self.assertEqual(stats["diagnostic_not_paper_literal"], False)
        self.assertGreaterEqual(stats["ez_amplification_max"], stats["ez_amplification_mean"])


if __name__ == "__main__":
    unittest.main()
