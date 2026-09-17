import sys
import unittest
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from paper01.model import DCO, component_local_max_normalize


class PaperModelTests(unittest.TestCase):
    def test_four_level_model_preserves_spatial_shape(self):
        net = DCO(levels=4, base=4)
        field = torch.randn(2, 3, 16, 16, 16)
        coords = torch.randn_like(field)
        out = net(field, coords)
        self.assertEqual(tuple(out.shape), tuple(field.shape))

    def test_local_max_is_independent_for_each_output_component(self):
        target = torch.zeros(2, 3, 4, 4, 4)
        target[:, 0] = 2.0
        target[:, 1] = 4.0
        target[:, 2] = 8.0
        normalized, scale = component_local_max_normalize(target)
        self.assertTrue(torch.allclose(normalized.abs().amax((2, 3, 4)), torch.ones(2, 3)))
        self.assertEqual(tuple(scale.shape), (2, 3, 1, 1, 1))
        self.assertTrue(torch.allclose(scale[0, :, 0, 0, 0], torch.tensor([2.0, 4.0, 8.0])))


if __name__ == "__main__":
    unittest.main(verbosity=2)
