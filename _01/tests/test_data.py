import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from paper01.data import draw_spec, sample_from_spec, spatial_coordinates


class PaperDataTests(unittest.TestCase):
    def test_plane_wave_amplitudes_are_transverse(self):
        spec = draw_spec(np.random.default_rng(4), n_waves=20)
        khat = np.asarray(spec["khat"])
        amplitudes = np.asarray(spec["amplitudes"])
        self.assertLess(float(np.max(np.abs(amplitudes @ khat))), 1e-10)
        self.assertTrue(np.all((amplitudes[:, :2] >= 0.0) & (amplitudes[:, :2] <= 5.0)))
        self.assertGreaterEqual(abs(float(khat[2])), 0.15)
        self.assertEqual(spec["amplitude_construction"], "paper_eq4_Ez_from_Ex_Ey_draw")
        self.assertTrue(np.all((np.asarray(spec["ks_rad_per_m"]) >= 0.0) &
                               (np.asarray(spec["ks_rad_per_m"]) <= 1048.0)))

    def test_analytic_curl_matches_finite_difference_away_from_boundary(self):
        spec = {
            "cell_size_m": [1e-4, 1e-4, 1e-4],
            "theta": np.pi / 2,
            "phi": 0.0,
            "khat": [1.0, 0.0, 0.0],
            "ks_rad_per_m": [20.0],
            "amplitudes": [[0.0, 1.0, 0.0]],
        }
        e, curl = sample_from_spec(spec, (32, 8, 8))
        dx = spec["cell_size_m"][0]
        numerical_curl_z = np.gradient(e[1], dx, axis=0, edge_order=2)
        self.assertLess(float(np.max(np.abs(numerical_curl_z[2:-2] - curl[2, 2:-2]))), 0.02)

    def test_trunk_coordinates_are_positions_not_constant_cellsize_channels(self):
        coords = spatial_coordinates((4, 5, 6), np.array([0.3e-3, 0.5e-3, 0.8e-3]))
        self.assertEqual(coords.shape, (3, 4, 5, 6))
        self.assertGreater(np.unique(coords[0]).size, 1)
        self.assertAlmostEqual(float(coords[0, 1, 0, 0]), 0.3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
