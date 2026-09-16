"""Prove/refute the E-to-curl pretrained layout transfer to staggered H."""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()

import json
from pathlib import Path

import numpy as np
import torch

import dco as D
import fdtd
from pidon_recording import sha256_file


def main():
    n = 7
    d = (0.1, 0.2, 0.3)
    rng = np.random.default_rng(20260913)
    h = [rng.normal(size=shape) for shape in ((n+1,n,n),(n,n+1,n),(n,n,n+1))]
    target = fdtd.curl_H(*h, *d)
    ht = [torch.from_numpy(x) for x in h]
    cases = {
        'legacy_unshifted': torch.stack([x[:n,:n,:n] for x in ht])[None],
        'existing_h_shift': torch.stack([ht[0][1:n+1,:n,:n], ht[1][:n,1:n+1,:n], ht[2][:n,:n,1:n+1]])[None],
    }
    rows = []
    for name, core in cases.items():
        # The periodic implementation is used only where its forward stencil
        # never wraps: each curl component is cropped on its transverse axes.
        out = D.curl_periodic(core, torch.tensor([d],dtype=torch.float64))[0]
        ss = err = 0.0
        for k, true in enumerate(target):
            slices = tuple(slice(0, size) for size in true.shape)
            predicted = out[k][slices].numpy()
            err += float(np.sum((predicted - true)**2)); ss += float(np.sum(true**2))
        rows.append({'layout':name,'relative_l2':float(np.sqrt(err/ss)), 'sse':err,'target_ss':ss,
                     'geometry_gate_pass':bool(np.sqrt(err/ss)<=1e-10)})
    result = {'classification':'exact-kernel geometry control only; NOT DCO performance',
              'n':n,'dxyz':d,'seed':20260913,'rows':rows,
              'h_shift_origin_m':[x/2 for x in d],
              'source_hashes':{p:sha256_file(p) for p in ('dco.py','fdtd.py','gen_data.py','pidon_solve.py',__file__)}}
    path = Path('evidence/gpt6_plan_v3_review/h_layout.json')
    if path.exists(): raise FileExistsError(path)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__ == '__main__':
    main()
