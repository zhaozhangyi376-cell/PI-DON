import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

import briefing_operator_audit as audit


class BriefingOperatorAuditTests(unittest.TestCase):
    def test_fig5_reconstruction_freezes_disclosed_parameters(self):
        spec = audit.fig5_reconstruction_spec()
        self.assertEqual(spec["n_waves"], 20)
        self.assertEqual(spec["cell_size_m"], [0.0006] * 3)
        self.assertAlmostEqual(spec["theta_deg"], 45.0)
        self.assertAlmostEqual(spec["phi_deg"], 60.0)
        self.assertAlmostEqual(spec["ks_rad_per_m"][0], 0.021)
        self.assertAlmostEqual(spec["ks_rad_per_m"][-1], 838.34)
        self.assertEqual(spec["amplitudes_provenance"], "ASSUMED_seed_2026091705")

    def test_spatial_coordinates_vary_and_encode_spacing(self):
        coords = audit.spatial_coordinates((4, 5, 6), np.array([0.3e-3, 0.5e-3, 0.8e-3]))
        self.assertEqual(coords.shape, (3, 4, 5, 6))
        self.assertAlmostEqual(float(coords[0, 1, 0, 0] - coords[0, 0, 0, 0]), 0.3)
        self.assertAlmostEqual(float(coords[1, 0, 1, 0] - coords[1, 0, 0, 0]), 0.5)
        self.assertAlmostEqual(float(coords[2, 0, 0, 1] - coords[2, 0, 0, 0]), 0.8)
        self.assertGreater(np.unique(coords[0]).size, 1)

    def test_state_hash_changes_only_when_parameters_change(self):
        net = torch.nn.Conv3d(3, 3, 1)
        before = audit.model_state_sha256(net)
        self.assertEqual(before, audit.model_state_sha256(net))
        with torch.no_grad():
            net.weight[0, 0, 0, 0, 0] += 1.0
        self.assertNotEqual(before, audit.model_state_sha256(net))

    def test_panel_contains_input_target_prediction_and_error(self):
        arrays = np.arange(3 * 8 * 8 * 8, dtype=np.float32).reshape(3, 8, 8, 8)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "panel.png"
            audit.plot_component_panel(arrays, arrays * 2, arrays * 1.5, out, "unit")
            self.assertTrue(out.is_file())
            self.assertGreater(out.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
