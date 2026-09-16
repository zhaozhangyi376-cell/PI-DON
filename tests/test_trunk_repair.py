"""Exercise the real training helper's frozen-module and budget safeguards."""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[1]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

import tempfile
from pathlib import Path
from unittest.mock import patch
import unittest
import numpy as np
import torch
import coverage_ab as A


class TinyNet(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.trunk=torch.nn.Linear(1,1,bias=False)
        self.branch=torch.nn.Linear(1,1,bias=False)
    def forward(self,x,coords):return self.trunk(x)+self.branch(x)


class TrunkTests(unittest.TestCase):
    def test_actual_helper_freezes_branch_and_updates_only_trunk(self):
        torch.manual_seed(7);net=TinyNet()
        initial={k:v.clone() for k,v in net.state_dict().items()}
        data={'E':np.ones((4,1),dtype=np.float32),'C':np.zeros((4,1),dtype=np.float32),
              'D':np.full((4,3),.0006,dtype=np.float32)}
        # Use a well-conditioned target to exercise optimizer changes, not loss overflow.
        data['C'][:]=2
        with tempfile.TemporaryDirectory() as td, patch.object(A,'load_net',return_value=(net,{})), \
             patch.object(A,'sha256',return_value='test-hash'), \
             patch.object(A.D,'normalise',side_effect=lambda x,y,d,n:(x,y,None,None)):
            A.train_arm('C200',data,'dummy',[[0,1,2,3]]*200,Path(td),'cpu','trunk.')
            ck=torch.load(Path(td)/'C200.pt',weights_only=False)
            self.assertTrue(torch.equal(initial['branch.weight'],ck['state']['branch.weight']))
            self.assertFalse(torch.equal(initial['trunk.weight'],ck['state']['trunk.weight']))
            self.assertEqual(len(ck['optimizer_state']['state']),1)
            self.assertEqual(ck['hist']['config']['trainable_names'],['trunk.weight'])
            self.assertEqual(ck['updates'],200)


if __name__=='__main__':unittest.main(verbosity=2)
