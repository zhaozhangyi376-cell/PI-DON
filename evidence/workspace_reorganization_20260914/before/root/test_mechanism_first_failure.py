import unittest

import torch

from mechanism_first_failure import component_relative_residual


class FirstFailureTests(unittest.TestCase):
    def test_component_residual_keeps_total_and_each_component_separate(self):
        predicted = [torch.tensor([2.0]), torch.tensor([2.0]), torch.tensor([2.0])]
        target = [torch.tensor([1.0]), torch.tensor([2.0]), torch.tensor([4.0])]
        result = component_relative_residual(predicted, target)
        self.assertEqual(result["components"][0]["R"], 1.0)
        self.assertEqual(result["components"][1]["R"], 0.0)
        self.assertEqual(result["components"][2]["R"], 0.25)
        self.assertAlmostEqual(result["total_R"], 5.0 / 21.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
