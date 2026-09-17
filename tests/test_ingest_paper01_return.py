import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.ingest_paper01_return import REQUIRED, audit_output


def dump(path: Path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


class Paper01ReturnAuditTests(unittest.TestCase):
    def test_complete_return_checks_contract_history_and_registered_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            local_contract = Path(__file__).resolve().parents[1] / "_01/paper_contract.json"
            contract_bytes = local_contract.read_bytes()
            (output / "paper_contract.json").write_bytes(contract_bytes)
            contract_hash = hashlib.sha256(contract_bytes).hexdigest()
            dump(output / "sample_specs.json", [{}] * 1000)
            with (output / "history.jsonl").open("w", encoding="utf-8") as handle:
                for update in range(1, 25001):
                    handle.write(json.dumps({"update": update}) + "\n")
            (output / "best.pt").write_bytes(b"best")
            (output / "last.pt").write_bytes(b"last")
            dump(output / "manifest.json", {
                "schema": "pidon-paper01-s1-run-v1",
                "mode": "train",
                "config": {"grid": 32, "samples": 1000, "effective_batch": 32,
                           "updates": 25000, "levels": 4, "learning_rate": 1e-4},
                "contract_sha256": contract_hash,
                "initial_checkpoint": None,
                "old_evidence_reused": False,
            })
            dump(output / "summary.json", {
                "schema": "pidon-paper01-s1-summary-v1",
                "status": "COMPLETE",
                "mode": "train",
                "updates": 25000,
                "parameter_updates": 25000,
                "learning_rates": [1e-4] * 25000,
                "contract_sha256": contract_hash,
                "old_checkpoint_loaded": False,
                "best_test_mse": 0.1,
                "best_update": 24000,
                "final_test_mse": 0.11,
                "elapsed_seconds": 123,
                "final_metrics": {
                    "macro_nmae_mean": 0.005,
                    "global_rel_l2_p90": 0.04,
                    "macro_mre_eq5_mean": 0.2,
                    "individual": [{"macro_nmae": 0.006}, {"macro_nmae": 0.009}],
                },
            })
            dump(output / "audit.json", {
                "constant_lr": True,
                "best_checkpoint_sha256": hashlib.sha256(b"best").hexdigest(),
                "last_checkpoint_sha256": hashlib.sha256(b"last").hexdigest(),
            })
            (output / "REPORT.md").write_text("report", encoding="utf-8")
            self.assertEqual(set(REQUIRED), {path.name for path in output.iterdir()})
            result = audit_output(output)
            self.assertTrue(result["engineering_pass"])
            self.assertEqual(result["scientific_result"], "PASS_REGISTERED_S1_GATES")

    def test_missing_history_is_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "summary.json").write_text("{}", encoding="utf-8")
            result = audit_output(output)
            self.assertFalse(result["engineering_pass"])
            self.assertIn("history.jsonl", result["missing"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
