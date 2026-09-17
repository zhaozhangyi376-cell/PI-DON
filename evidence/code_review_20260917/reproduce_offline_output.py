"""Independent verification of offline-review output and model identity risks."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from project_paths import configure
configure()

import torch
import dco
import train_dco

torch.set_num_threads(1)
OBS = {}
ADAM_CALLS = 0


def tiny_data(*args, **kwargs):
    field = torch.ones((5, 3, 4, 4, 4))
    return field, field.clone(), field.clone(), torch.ones((5, 3)), 4


def train_once(output):
    argv = ["train_dco", "--device", "cpu", "--epochs", "1", "--levels", "2", "--base", "2",
            "--batch", "4", "--ckpt-every", "1", "--out", str(output)]
    original = torch.optim.Adam.step

    def count(optimizer, *args, **kwargs):
        global ADAM_CALLS
        result = original(optimizer, *args, **kwargs)
        ADAM_CALLS += 1
        return result

    with patch.object(sys, "argv", argv), patch.object(train_dco, "load", side_effect=tiny_data), \
         patch.object(torch.optim.Adam, "step", count):
        train_dco.main()


class OfflineOutputReview(unittest.TestCase):
    def test_non_pt_extension_overwrites_checkpoint_with_history(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "model.bin"
            train_once(output)
            result = json.loads(output.read_text())
            self.assertIn("epoch", result)
            self.assertNotIn("state", result)
            self.assertEqual(result["epoch"], [1])
        OBS["non_pt_output"] = {"path_suffix": ".bin", "output_is_json_not_weights": True,
                                "observed_epochs": result["epoch"]}

    def test_missing_parent_detected_after_training_update(self):
        before = ADAM_CALLS
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "not_created/model.pt"
            with self.assertRaisesRegex(RuntimeError, "does not exist"):
                train_once(output)
            self.assertFalse(output.exists())
        self.assertEqual(ADAM_CALLS - before, 1)
        OBS["missing_parent"] = {"adam_before_save_failure": ADAM_CALLS - before,
                                  "checkpoint_exists": False}

    def test_identical_parameter_keys_do_not_preserve_head_semantics(self):
        torch.manual_seed(2718)
        potential = dco.DCO(levels=2, base=2, head="potential")
        direct = dco.DCO(levels=2, base=2)
        match = direct.load_state_dict(potential.state_dict(), strict=True)
        x = torch.ones((1, 3, 4, 4, 4))
        with torch.no_grad():
            a = potential(x, x, torch.ones((1, 3)))
            b = direct(x, x)
        difference = float((a - b).abs().max())
        self.assertGreater(difference, 1e-5)
        self.assertEqual(match.missing_keys, [])
        self.assertEqual(match.unexpected_keys, [])
        OBS["head_semantics"] = {"state_dict_strict_load_succeeds": True,
                                  "max_output_difference": difference,
                                  "source_head": potential.head_mode, "loaded_head": direct.head_mode}


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(OfflineOutputReview))
    with Path(__file__).with_name("offline_output_counterexamples.json").open("x", encoding="utf-8") as handle:
        json.dump({"review_only": True, "production_updates": 0, "toy_adam_calls": ADAM_CALLS,
                   "tests": result.testsRun, "errors": len(result.errors), "failures": len(result.failures),
                   "observations": OBS}, handle, indent=2)
        handle.write("\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)
