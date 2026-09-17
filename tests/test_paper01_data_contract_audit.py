import unittest

import numpy as np

from scripts.analysis.audit_paper01_data_contract import bins, safe_corr, transversality


class Paper01DataContractAuditTests(unittest.TestCase):
    def test_transversality_reports_near_zero_for_constructed_wave(self):
        khat = np.array([0.3, 0.4, np.sqrt(1.0 - 0.3**2 - 0.4**2)])
        amp = np.array([[2.0, 1.0, -(khat[0] * 2.0 + khat[1] * 1.0) / khat[2]]])
        result = transversality({"khat": khat.tolist(), "amplitudes": amp.tolist()})
        self.assertLess(result["k_dot_e0_rel_max"], 1e-14)

    def test_bins_preserve_last_edge_and_report_counts(self):
        rows = [
            {"feature": 0.15, "macro_nmae": 0.1, "z_nmae": 0.2, "z_active_fraction_0p1": 0.3, "max_abs_ez_over_xy": 1.0},
            {"feature": 1.0, "macro_nmae": 0.4, "z_nmae": 0.5, "z_active_fraction_0p1": 0.6, "max_abs_ez_over_xy": 2.0},
        ]
        grouped = bins(rows, "feature", [0.15, 0.5, 1.0])
        self.assertEqual([item["count"] for item in grouped], [1, 1])
        self.assertEqual(grouped[-1]["macro_nmae"]["mean"], 0.4)

    def test_safe_corr_rejects_constant_axis(self):
        self.assertIsNone(safe_corr([1, 1, 1], [1, 2, 3]))
        self.assertEqual(round(safe_corr([1, 2, 3], [3, 2, 1]), 6), -1.0)


if __name__ == "__main__":
    unittest.main()
