import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from paper01.runner import RunConfig, run_preflight


class PaperRunnerTests(unittest.TestCase):
    def test_preflight_keeps_constant_learning_rate_and_writes_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "fresh"
            summary = run_preflight(RunConfig(output=out, grid=8, samples=8,
                                              effective_batch=4, microbatch=2,
                                              updates=2, levels=2, base=2,
                                              device="cpu"))
            self.assertEqual(summary["updates"], 2)
            self.assertEqual(summary["learning_rates"], [1e-4, 1e-4])
            self.assertEqual(summary["parameter_updates"], 2)
            self.assertTrue((out / "manifest.json").is_file())
            self.assertTrue((out / "paper_contract.json").is_file())

    def test_fresh_output_refuses_nonempty_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "occupied"
            out.mkdir()
            (out / "old.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                run_preflight(RunConfig(output=out, grid=8, samples=8,
                                        effective_batch=4, microbatch=2,
                                        updates=1, levels=2, base=2,
                                        device="cpu"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
