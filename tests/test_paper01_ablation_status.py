import json
import tempfile
import unittest
from pathlib import Path

from tools.paper01_ablation_status import collect_status, write_jsonl_row


class Paper01AblationStatusTests(unittest.TestCase):
    def test_collect_status_reports_running_and_complete_variants(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            baseline.mkdir()
            write_jsonl_row(baseline / "history.jsonl", {
                "update": 50,
                "train_mse": 0.2,
                "test_mse": None,
                "elapsed_seconds": 3.0,
            })
            write_jsonl_row(baseline / "history.jsonl", {
                "update": 100,
                "train_mse": 0.1,
                "test_mse": 0.05,
                "metrics": {"macro_nmae_mean": 0.4},
                "elapsed_seconds": 6.0,
            })

            theta = root / "theta_min_0p5"
            theta.mkdir()
            write_jsonl_row(theta / "history.jsonl", {
                "update": 2000,
                "train_mse": 0.03,
                "test_mse": 0.02,
                "metrics": {"macro_nmae_mean": 0.2},
                "elapsed_seconds": 20.0,
            })
            (theta / "summary.json").write_text(json.dumps({
                "status": "COMPLETE",
                "final_metrics": {"macro_nmae_mean": 0.18},
            }), encoding="utf-8")

            data = collect_status(root, target_updates=2000)

        self.assertEqual(data["status"], "RUNNING_OR_PARTIAL")
        self.assertEqual(data["variants"][0]["variant"], "baseline")
        self.assertEqual(data["variants"][0]["state"], "RUNNING_OR_PARTIAL")
        self.assertEqual(data["variants"][0]["last_update"], 100)
        self.assertEqual(data["variants"][0]["last_test_mse"], 0.05)
        self.assertEqual(data["variants"][1]["variant"], "theta_min_0p5")
        self.assertEqual(data["variants"][1]["state"], "COMPLETE")
        self.assertEqual(data["variants"][1]["summary_macro_nmae_mean"], 0.18)


if __name__ == "__main__":
    unittest.main(verbosity=2)
