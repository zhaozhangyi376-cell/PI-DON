"""
Stage 3 -- the Deep Curl Operator (DCO).

Architecture transcribed line by line from paper section III-A:

  "The U-net architecture comprises two branches: a downsampling branch and an
   upsampling branch. Each branch contains L levels of corresponding blocks."
  "In each block, there are two 3x3x3 convolution filters with an activation
   function."                                        -> Block = conv,GELU,conv,GELU
  "we use Gaussian error linear units (GELUs)"       -> nn.GELU, not ReLU
  "The padding size ... is 1 on each boundary, and the step size ... is also 1,
   ensuring that the output dimensions remain unchanged after each block."
  "We add an additional residual connection within each block to maintain the
   gradient flow from the input feature map to the second convolution layer."
  "In the downsampling branch, there is a max-pooling layer between two
   neighboring blocks. The kernel size ... is 2x2x2"
  "In the upsampling branch, there is a transposed convolutional layer between
   each block. The kernel size of this layer is also 2x2x2"
  "The outputs of the two downsampling branches are combined using the Hadamard
   product"                                          -> branch * trunk, elementwise
  "there is a skip connection between the corresponding block ... directly
   copies the output from one downsampling branch to the corresponding block in
   the upsampling branch"                            -> concat

TWO DOWNSAMPLING BRANCHES, NOT ONE
  Section III-C: "Each additional level introduced six convolutional layers
  (FOUR in the downsampling branch and two in the upsampling branch)."
  Four = 2 (branch net, eats E) + 2 (trunk net, eats coordinates).  The trunk
  is a full parallel encoder, not a small side network.

WHAT THE PAPER DOES NOT STATE (our choices, flag them in the report)
  * channel counts        -> base=32, doubling per level  [MVP; paper silent]
  * where exactly the residual lands -> out = act(c2(act(c1(x)))) + proj(x)
  * how the output is de-normalised -> see normalise() below
"""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import torch
import torch.nn as nn


# --------------------------------------------------------------------------- #
#  the exact discrete curl, as a layer
# --------------------------------------------------------------------------- #
def curl_periodic(A, d_rel):
    """Yee curl on the gen_data staggered layout, periodic.  (B,3,n,n,n) in/out.

    d_rel is the cell size in whatever length unit A is expressed per; pass
    d/Lc when A is a normalised field, which keeps the result dimensionless.

    torch.roll(x, -1, dim)[i] == x[i+1], i.e. the forward difference a quantity
    at half-index +1/2 needs.  rollout.curl_E_p delegates here so there is one
    definition of the operator, not two.
    """
    dx, dy, dz = (d_rel[:, k].view(-1, 1, 1, 1) for k in range(3))
    Ax, Ay, Az = A[:, 0], A[:, 1], A[:, 2]
    cx = (torch.roll(Az, -1, 2) - Az) / dy - (torch.roll(Ay, -1, 3) - Ay) / dz
    cy = (torch.roll(Ax, -1, 3) - Ax) / dz - (torch.roll(Az, -1, 1) - Az) / dx
    cz = (torch.roll(Ay, -1, 1) - Ay) / dx - (torch.roll(Ax, -1, 2) - Ax) / dy
    return torch.stack([cx, cy, cz], 1)


def d_rel_of(d_mm, Lc):
    """Cell size divided by the normalisation length -- O(1), per sample.

    d_mm is (B,3) in millimetres, Lc is the (B,1,1,1,1) metre length that
    dco.normalise divided the curl by.  Returns (B,3).
    """
    return d_mm / (Lc.reshape(-1, 1) * 1e3)


class Block(nn.Module):
    """Two 3x3x3 convs + GELU, with an intra-block residual connection."""

    def __init__(self, c_in, c_out):
        super().__init__()
        self.c1 = nn.Conv3d(c_in, c_out, 3, padding=1)
        self.c2 = nn.Conv3d(c_out, c_out, 3, padding=1)
        self.act = nn.GELU()
        self.proj = nn.Conv3d(c_in, c_out, 1) if c_in != c_out else nn.Identity()

    def forward(self, x):
        h = self.act(self.c1(x))
        h = self.act(self.c2(h))
        return h + self.proj(x)


class DCO(nn.Module):
    """E field (3ch) + coordinates (3ch) -> curl E (3ch).

    Fully convolutional: no layer depends on the grid size, so a net trained at
    16^3 runs unchanged at 32^3 / 64x96x16 (paper section III-D).  The only
    constraint is that every spatial dimension be divisible by 2**(L-1).
    """

    def __init__(self, levels=3, base=32, c_in=3, c_out=3, head="direct"):
        """head="direct"     the network's last 1x1 conv IS the curl. This is
                             what the paper does, and it cannot satisfy
                             div(curl) = 0 -- measured 6.7e5 times the exact
                             operator's numerical zero, and an explicit
                             lambda*||div||^2 penalty only bought 1.5x.
           head="potential"  the network outputs a vector potential A and the
                             EXACT discrete curl is applied to it. Then
                             div(curl(A)) = 0 holds BY CONSTRUCTION to machine
                             precision, and the penalty is unnecessary. Costs
                             one extra finite difference. forward() then needs
                             d_rel; see curl_periodic.
        """
        super().__init__()
        if head not in ("direct", "potential"):
            raise ValueError(f"unknown head {head!r}")
        self.head_mode = head
        self.levels = levels
        chans = [base * (2 ** i) for i in range(levels)]

        # two parallel downsampling encoders
        self.branch = nn.ModuleList()
        self.trunk = nn.ModuleList()
        cb = ct = c_in
        for c in chans:
            self.branch.append(Block(cb, c)); cb = c
            self.trunk.append(Block(ct, c)); ct = c
        self.pool = nn.MaxPool3d(2)

        # upsampling decoder
        self.up = nn.ModuleList()
        self.dec = nn.ModuleList()
        for i in range(levels - 1, 0, -1):
            self.up.append(nn.ConvTranspose3d(chans[i], chans[i - 1], 2, stride=2))
            # concat(skip) doubles the channels, the block brings them back down
            self.dec.append(Block(2 * chans[i - 1], chans[i - 1]))

        self.head = nn.Conv3d(chans[0], c_out, 1)

    def forward(self, e, coords, d_rel=None):
        if self.head_mode == "potential" and d_rel is None:
            raise ValueError("head='potential' needs d_rel -- see curl_periodic")
        feats = []
        b, t = e, coords
        for i in range(self.levels):
            if i > 0:
                b, t = self.pool(b), self.pool(t)
            b = self.branch[i](b)
            t = self.trunk[i](t)
            feats.append(b * t)                 # Hadamard product, paper III-A

        x = feats[-1]
        for j, i in enumerate(range(self.levels - 1, 0, -1)):
            x = self.up[j](x)
            x = torch.cat([x, feats[i - 1]], dim=1)   # skip connection
            x = self.dec[j](x)
        out = self.head(x)
        # the whole point: the curl is applied, not learnt, so the identity
        # div(curl(.)) = 0 is structural rather than encouraged
        return out if self.head_mode == "direct" else curl_periodic(out, d_rel)

    def n_params(self):
        return sum(p.numel() for p in self.parameters())


# --------------------------------------------------------------------------- #
#  invertible normalisation
# --------------------------------------------------------------------------- #
def normalise(E, C, d_mm, norm="max"):
    """Scale E and curl E to O(1) in a way that can be UNDONE at inference.

    The paper says only: "The U-net output was normalized by the local maximum
    for each component ... reduced the MRE from 4.1e-2 to 7.9e-4."  Taken
    literally that divides the TARGET by the target's own maximum, which cannot
    be inverted on unseen data (you would need the answer to recover the answer).

    We use an input-derived scale instead, which is invertible and physically
    consistent -- curl has units of field/length:

        a  = max|E|                       (per sample, from the INPUT)
        Lc = (dx dy dz)^(1/3)             (per sample, from the coordinates)
        E_hat    = E / a
        curl_hat = curl * Lc / a
        -> at inference:  curl = net(E/a, coords) * a / Lc

    norm="max" uses a = max|E|; norm="rms" uses a = sqrt(mean(E^2)).

    Both max and RMS depend on the sampled field and physical window. Neither
    guarantees invariant prediction accuracy across grid sizes. Run #18 fixes
    the RMS explicitly to separate normalization from context effects; run #13
    instead resamples one fixed physical window. Do not conflate these tests.
    Existing checkpoints must keep the normalization used in their training.

    Returns (E_hat, C_hat, a, Lc).  Pass C=None to normalise inputs only.
    """
    if norm == "rms":
        a = E.pow(2).mean(dim=(1, 2, 3, 4), keepdim=True).sqrt().clamp_min(1e-12)
    else:
        a = E.abs().amax(dim=(1, 2, 3, 4), keepdim=True).clamp_min(1e-12)
    Lc = (d_mm[:, 0] * d_mm[:, 1] * d_mm[:, 2]).pow(1.0 / 3.0)
    Lc = Lc.view(-1, 1, 1, 1, 1) * 1e-3               # mm -> m
    E_hat = E / a
    C_hat = None if C is None else C * Lc / a
    return E_hat, C_hat, a, Lc


def denormalise(C_hat, a, Lc):
    return C_hat * a / Lc


def mre_eq5(pred, true):
    """Eq.(5): exact zero uses |pred|; every nonzero uses relative error.

    Near-zero sensitivity is reported, not removed. Common scaling cancels
    in the nonzero branch; it does NOT convert MRE to MAE/max. The zero
    branch is unit-dependent, so callers must record their physical units.
    """
    denom = true.abs()
    nonzero = denom != 0
    safe = torch.where(nonzero, denom, torch.ones_like(denom))
    rel = torch.where(nonzero, (pred - true).abs() / safe, pred.abs())
    return rel.mean()


def rel_l2(pred, true, eps=1e-30):
    """Relative L2 norm  ||yp-yt||_2 / ||yt||_2.

    A supplementary norm; never compare this value to paper Eq.(5) MRE.
    """
    num = (pred - true).pow(2).sum().sqrt()
    den = true.pow(2).sum().sqrt().clamp_min(eps)
    return num / den


def nmae(pred, true, eps=1e-30):
    """Legacy global MAE/max over the supplied tensor, NOT paper Eq.(5).

    If the tensor contains three components they share one denominator.
    Use paper_protocol.vector_metrics for explicitly per-component reports.
    """
    return (pred - true).abs().mean() / true.abs().max().clamp_min(eps)


# backwards-compatible alias
mre = mre_eq5


# --------------------------------------------------------------------------- #
#  trunk input encoding
# --------------------------------------------------------------------------- #
def make_coords(shape, d_mm, mode="centered", device=None, dtype=torch.float32):
    """Build the trunk input, (1,3,*shape).

    The paper feeds "the coordinates of E and H fields" into the trunk, which
    "decodes coordinate information into cell sizes". Direct cell-size channels
    are an implementation alternative, not proof of the author's encoding.
    Coordinates can leave the training range when physical extent changes;
    transfer must be evaluated under a declared grid/physical-window protocol.

    modes
      abs       (i)*d           -- node coordinates; origin convention explicit
      centered  (i-(n-1)/2)*d   -- coordinates centered on this tensor's window
      cellsize  dx,dy,dz        -- constant channels; tensor shapes can change,
                                   but prediction invariance is NOT guaranteed.
                                   Convolutions, pooling and boundary context
                                   still matter (run #18 common-ROI evidence).
    """
    if isinstance(shape, int):
        shape = (shape, shape, shape)
    d = torch.as_tensor(d_mm, dtype=dtype).view(3)
    if mode == "cellsize":
        g = d.view(1, 3, 1, 1, 1).expand(1, 3, *shape).clone()
        return g.to(device) if device is not None else g
    axes = []
    for k, n in enumerate(shape):
        # arange MUST land on d's device: d_mm arrives as a CUDA tensor from
        # rollout.dco_curl, and a CPU arange times a CUDA d raises "Expected
        # all tensors to be on the same device".  The cellsize branch above
        # never builds an arange, which is why only the abs/centered
        # checkpoints hit this -- it went unnoticed until the 2026-09-10
        # spectral sweep silently skipped dco_L3 and dco_L3b.
        i = torch.arange(n, dtype=dtype, device=d.device)
        if mode == "centered":
            i = i - (n - 1) / 2.0
        elif mode != "abs":
            raise ValueError(f"unknown coord mode {mode!r}")
        axes.append(i * d[k])
    g = torch.stack(torch.meshgrid(*axes, indexing="ij")).unsqueeze(0)
    return g.to(device) if device is not None else g
