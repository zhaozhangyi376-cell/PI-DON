import json
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.build_paper01_ablation_bundle import build_bundle


class Paper01AblationBundleTests(unittest.TestCase):
    def test_bundle_contains_ablation_source_queue_and_no_old_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "ablation.zip"
            build_bundle(output)
            sidecar = output.with_suffix(output.suffix + ".sha256")
            legacy_sidecar = output.with_suffix(".sha256")
            self.assertTrue(sidecar.is_file())
            self.assertTrue(legacy_sidecar.is_file())
            self.assertEqual(
                sidecar.read_text(encoding="utf-8"),
                f"{hashlib.sha256(output.read_bytes()).hexdigest().upper()}  {output.name}\n",
            )
            self.assertEqual(legacy_sidecar.read_text(encoding="utf-8"), sidecar.read_text(encoding="utf-8"))
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                self.assertIn("install_paper01_ablation.py", names)
                self.assertIn("server_paper01_ablation_queue.py", names)
                self.assertIn("run_paper01_ablation.ps1", names)
                self.assertIn("payload/_01/train_phase1_ablation.py", names)
                self.assertIn("payload/_01/src/paper01/ablation_data.py", names)
                self.assertFalse(any(name.endswith(".pt") for name in names))
                self.assertFalse(any("/evidence/" in name for name in names))

                task = json.loads(archive.read("paper01_ablation_task.json").decode("utf-8"))
                self.assertEqual(task["id"], "PAPER01-ABLATION-SMOKE")
                self.assertEqual(task["depends"], [])
                self.assertTrue(task["execution_plan"].endswith("paper01-ablation-smoke-protocol.md"))

                queue = archive.read("server_paper01_ablation_queue.py").decode("utf-8")
                installer = archive.read("install_paper01_ablation.py").decode("utf-8")
                self.assertIn("UPDATE = Path(__file__).resolve().parent", installer)
                self.assertIn("ROOT = UPDATE.parent", installer)
                self.assertIn("SOURCE = UPDATE / \"payload\" / \"_01\"", installer)
                self.assertIn("UPDATE = Path(__file__).resolve().parent", queue)
                self.assertIn("ROOT = UPDATE.parent", queue)
                self.assertIn("PAPER01 ablation installer expected project root", installer)
                self.assertIn("PAPER01 ablation queue expected project root", queue)
                self.assertIn("lab_log.py", queue)
                self.assertIn("PAPER01-ABLATION-SMOKE", queue)
                self.assertIn("--variants", queue)
                self.assertIn("server_paper01_ablation_return.zip", queue)


if __name__ == "__main__":
    unittest.main(verbosity=2)
