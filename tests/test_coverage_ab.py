"""Pre-training checks for paired data, physical loss and strict update budget."""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[1]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

import unittest
import copy
import numpy as np
import torch
import coverage_ab as A
import gen_data as G


class CoverageTests(unittest.TestCase):
    def test_paired_samples_match_existing_generator(self):
        specs=A.paired_specs(n=1)
        rng=np.random.default_rng(A.SEED);u=rng.uniform(0,1,3)
        state=copy.deepcopy(rng.bit_generator.state)
        for arm,(lo,hi) in A.RANGES.items():
            replay=np.random.default_rng();replay.bit_generator.state=copy.deepcopy(state)
            e,c=G.one_sample(replay,8,(lo+(hi-lo)*u)*1e-3)
            actual=A.make_data(specs,arm,n=8)
            for got,want in [(actual['E'][0],e),(actual['C'][0],c)]:
                self.assertLess(np.max(np.abs(got-want))/np.max(np.abs(want)),2e-6)

    def test_budget_has_exactly_200_complete_batches(self):
        batches=np.array(A.batch_schedule())
        self.assertEqual(batches.shape,(200,4));self.assertTrue(np.all((batches>=0)&(batches<128)))
        for start in range(0,192,32):
            np.testing.assert_array_equal(np.sort(batches[start:start+32].ravel()),np.arange(128))
        np.testing.assert_array_equal(batches,A.batch_schedule())

    def test_relative_loss_weights_samples_equally(self):
        true=torch.tensor([[1.],[100.]])
        pred=torch.tensor([[2.],[100.]])
        self.assertAlmostEqual(A.criterion(pred,true).item(),.5)


if __name__=='__main__':unittest.main(verbosity=2)
