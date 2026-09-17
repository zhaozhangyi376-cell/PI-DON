import tempfile
import unittest
from pathlib import Path

from tools.ingest_paper01_ablation_return import review, write_json


class Paper01AblationReturnIngestTests(unittest.TestCase):
    def test_review_extracts_variant_table_and_best_macro_nmae(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary = root / "_01" / "evidence" / "paper01_ablation_v1" / "summary.json"
            summary.parent.mkdir(parents=True)
            write_json(summary, {
                "status": "PASS",
                "parameter_updates": 8000,
                "variants": [
                    {
                        "variant": "baseline",
                        "parameter_updates": 2000,
                        "best_test_mse": 0.1,
                        "final_metrics": {"macro_nmae_mean": 0.2, "global_rel_l2_p90": 0.3, "macro_mre_eq5_mean": 1.0},
                        "contract_stats": {"ez_amplification_p90": 3.0, "diagnostic_not_paper_literal": False},
                    },
                    {
                        "variant": "theta_min_0p5",
                        "parameter_updates": 2000,
                        "best_test_mse": 0.05,
                        "final_metrics": {"macro_nmae_mean": 0.1, "global_rel_l2_p90": 0.2, "macro_mre_eq5_mean": 0.9},
                        "contract_stats": {"ez_amplification_p90": 1.0, "diagnostic_not_paper_literal": False},
                    },
                    {
                        "variant": "ez_cap3",
                        "parameter_updates": 2000,
                        "best_test_mse": 0.07,
                        "final_metrics": {"macro_nmae_mean": 0.15, "global_rel_l2_p90": 0.25, "macro_mre_eq5_mean": 0.95},
                        "contract_stats": {"ez_amplification_p90": 2.0, "diagnostic_not_paper_literal": False},
                    },
                    {
                        "variant": "projected_amp",
                        "parameter_updates": 2000,
                        "best_test_mse": 0.06,
                        "final_metrics": {"macro_nmae_mean": 0.12, "global_rel_l2_p90": 0.22, "macro_mre_eq5_mean": 0.85},
                        "contract_stats": {"ez_amplification_p90": 1.5, "diagnostic_not_paper_literal": True},
                    },
                ],
            })
            data = review(summary, root)
        self.assertEqual(data["status"], "PASS")
        self.assertEqual(data["variant_count"], 4)
        self.assertEqual(data["best_macro_nmae_variant"]["variant"], "theta_min_0p5")
        self.assertAlmostEqual(data["best_vs_baseline_macro_nmae_ratio"], 0.5)
        self.assertEqual(data["recommendation"]["code"], "REGISTER_FULL_S1_WITH_MATCHING_FILTER")
        self.assertFalse(data["long_run_unlocked"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
