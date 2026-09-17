import tempfile
import unittest
import zipfile
import json
from pathlib import Path

from tools.build_paper01_server_bundle import build_bundle


class Paper01ServerBundleTests(unittest.TestCase):
    def test_bundle_contains_fresh_source_and_logged_queue_but_no_weights(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "paper01.zip"
            build_bundle(output)
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                self.assertIn("install_paper01_server.py", names)
                self.assertIn("run_paper01_full.ps1", names)
                self.assertIn("payload/_01/paper_contract.json", names)
                self.assertIn("payload/_01/src/paper01/runner.py", names)
                self.assertFalse(any(name.endswith(".pt") for name in names))
                self.assertFalse(any("/evidence/" in name for name in names))
                task = json.loads(archive.read("paper01_task.json").decode("utf-8"))
                self.assertEqual(task["id"], "PAPER01-S1")
                self.assertEqual(task["depends"], [])
                self.assertTrue(task["execution_plan"].endswith("paper01-s1-r1-protocol.md"))
                queue = archive.read("server_paper01_queue.py").decode("utf-8")
                self.assertIn("lab_log.py", queue)
                self.assertIn("PAPER01-S1", queue)
                self.assertIn("server_paper01_return.zip", queue)
                runner = archive.read("payload/_01/src/paper01/runner.py").decode("utf-8")
                self.assertIn("[update", runner)
                self.assertNotIn("C:\\PI-DON", runner)


if __name__ == "__main__":
    unittest.main(verbosity=2)
