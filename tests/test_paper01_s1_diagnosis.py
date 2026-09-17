import unittest

from scripts.analysis.diagnose_paper01_s1 import group_by_bins, history_trend, safe_corr


class Paper01S1DiagnosisTests(unittest.TestCase):
    def test_safe_corr_handles_constant_and_linear_inputs(self):
        self.assertIsNone(safe_corr([1, 1, 1], [1, 2, 3]))
        self.assertEqual(round(safe_corr([1, 2, 3], [2, 4, 6]), 6), 1.0)

    def test_group_by_bins_reports_counts_and_error_summary(self):
        rows = [
            {"feature": 0.2, "macro_nmae": 0.1, "global_rel_l2": 0.3},
            {"feature": 0.6, "macro_nmae": 0.2, "global_rel_l2": 0.4},
            {"feature": 1.0, "macro_nmae": 0.4, "global_rel_l2": 0.8},
        ]
        groups = group_by_bins(rows, "feature", [0.0, 0.5, 1.0])
        self.assertEqual([group["count"] for group in groups], [1, 2])
        self.assertEqual(groups[1]["macro_nmae"]["max"], 0.4)

    def test_history_trend_uses_validation_rows(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.jsonl"
            path.write_text(
                '{"update": 15000, "test_mse": 10.0}\n'
                '{"update": 20000, "test_mse": 8.0}\n'
                '{"update": 25000, "test_mse": 6.0}\n',
                encoding="utf-8",
            )
            trend = history_trend(path)
        self.assertEqual(trend["last_5k_relative_drop"], 0.25)
        self.assertEqual(trend["last_10k_relative_drop"], 0.4)


if __name__ == "__main__":
    unittest.main()
