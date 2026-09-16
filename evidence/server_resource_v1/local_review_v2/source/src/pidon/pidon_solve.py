"""
Stage 2 of the paper: Algorithm 1.  THIS IS THE PART WE HAD NEVER BUILT.

    py -3.11 pidon_solve.py --steps 200 --init dco_paper32.pt
    py -3.11 pidon_solve.py --steps 200 --init random      # the Fig 8 control

WHAT ALGORITHM 1 ACTUALLY IS  (paper IV-A, and see PAPER_NOTES.md)
    Not "run the trained DCO inside a leapfrog".  That is what test_dco.py's
    EXP 3 does, and it diverges at 158 steps -- but the paper never claims it
    works, because the paper does something else entirely:

        while N < Nmax:
            Train  grad x H   using the physics-informed loss
            Update E          using eps and dt
            Implement excitation
            Train  grad x E   using eq. (7), with boundary conditions
            Update H          using mu and dt

    The DCO's WEIGHTS ARE RE-OPTIMISED AT EVERY TIME STEP, by backprop, until
    the loss drops below 1e-4 (paper's own stopping rule).  And eq. (7), the
    "physics-informed loss", is literally the squared difference between the
    network's output and the Yee finite-difference stencil written out term by
    term.  So each step drives the network back onto the exact discrete curl.

    That is why it does not blow up.  It is not a learnt operator evolving
    freely; it is an optimisation that re-fits the exact curl every step.
    The paper pays for it in time: 583 s on an A6000 versus 6.47 s for FDTD on
    a CPU, for the same cavity -- about 90x slower.

WHAT THIS SCRIPT REPRODUCES
    * Fig 7(b)(c) / Table II : the 50 mm cavity, 32 cells, centre Gaussian
      source, PEC on all six faces, compared against our own FDTD.
    * Fig 8 : cumulative training loss per time step, pretrained-DCO
      initialisation versus random initialisation.  Note what that figure
      actually plots -- "the total loss summed over all training epochs at
      each time step", i.e. HOW MUCH OPTIMISATION EACH STEP COSTS, not
      whether the field diverges.  Reproducing it means reproducing the
      optimisation cost curve.

ONE DOCUMENTED DEVIATION
    Our DCO maps (3, n, n, n) -> (3, n, n, n), while the cavity's Yee arrays
    have a different shape per component (Hx is (n+1, n, n) and so on).  As in
    EXP 3, the network supplies the first n slices of each component and the
    remaining boundary slice keeps its exact Yee value.  The physics-informed
    loss is therefore computed over the region the network actually predicts.
"""

# Project layout bootstrap (imports and paths only).
import sys as _layout_sys
from pathlib import Path as _LayoutPath
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2]))
from project_paths import ROOT as PROJECT_ROOT, configure as _layout_configure, resolve_legacy
_layout_configure()


import argparse
import copy
import hashlib
import json
import os
import sys
import time
import uuid

import numpy as np
import torch

import dco as D
import fdtd
import head_lstsq
from pidon_contract import (CURL_E0, CURL_H0, FitRecord, StepRecord, SOURCE_OUTSIDE_PROBES_CELLS,
                            all_finite, reached, six_component_metrics,
                            trilinear_sample, finite_scalar)
from pidon_recording import (RunRecorder, capture_rng, restore_rng, sha256_file,
                             source_hashes)

SCRIPT_VERSION = "2026-09-13b"
STATE_SCHEMA = "pidon-solver-state-v4"
TERMINAL_FIT_REASONS = frozenset(("max_updates", "closure_budget", "nonfinite", "time_budget"))


# --------------------------------------------------------------------------- #
def to_t(a, dev, dtype=torch.float32):
    return torch.from_numpy(np.ascontiguousarray(a)).to(device=dev, dtype=dtype)


RESUME_CONFIG_KEYS = (
    "n", "side", "dt", "init", "tol", "tol_mode", "max_inner", "lr", "levels", "base",
    "coords", "norm", "separate_nets", "reset_opt_each_step", "grad_clip", "h_scale",
    "component_rel", "h_output_scale", "h_shift", "strict_stop", "inner_time_budget_s",
    "fmax", "seed", "lbfgs_closures", "lbfgs_lr", "lbfgs_history", "lbfgs_time_budget_s",
    "torch_dtype", "source_mode",
    "head_lstsq_once", "head_rcond",
)

_FORMAL_MUTABLE_KEYS = {"steps", "out_dir", "resume", "out", "device", "checkpoint_every", "config"}


def explicit_cli_destinations(parser, argv):
    """Return destinations explicitly supplied by the user, including --x=y."""
    supplied = set()
    for action in parser._actions:
        for option in action.option_strings:
            if any(token == option or token.startswith(option + "=") for token in argv):
                supplied.add(action.dest)
    return supplied


def apply_frozen_config(args, loaded_config, explicit_destinations):
    """Load a formal configuration without silently overriding a CLI conflict."""
    if not isinstance(loaded_config, dict):
        raise ValueError("--config must contain a JSON object or an object with key 'config'")
    allowed = set(RESUME_CONFIG_KEYS) | _FORMAL_MUTABLE_KEYS
    unknown = sorted(set(loaded_config) - allowed)
    if unknown:
        raise ValueError(f"configuration has unsupported keys: {unknown}")
    missing = [key for key in RESUME_CONFIG_KEYS if key not in loaded_config]
    if missing:
        raise ValueError("formal configuration lacks frozen fields: " + ", ".join(missing))
    for key, value in loaded_config.items():
        if key in _FORMAL_MUTABLE_KEYS:
            continue
        if key in explicit_destinations and getattr(args, key) != value:
            raise ValueError(f"CLI/config conflict for {key}: cli={getattr(args, key)!r}, config={value!r}")
        setattr(args, key, value)


def resolve_torch_dtype(value):
    if isinstance(value, torch.dtype):
        return value
    allowed = {"float32": torch.float32, "float64": torch.float64}
    if value not in allowed:
        raise ValueError(f"unsupported torch_dtype {value!r}; formal runs support: {sorted(allowed)}")
    return allowed[value]


def frozen_config(a):
    return {key: getattr(a, key, None) for key in RESUME_CONFIG_KEYS}


def formal_run_identity(a, *, run_id=None):
    """Return a unique execution identity and a stable protocol identity.

    ``run_id`` answers *which execution produced this evidence* and is a
    UUID.  ``protocol_hash`` answers *which frozen dynamics/code it used*.
    They used to be the same digest, which made two independent executions
    look like a resume of one another.
    """
    source = source_hashes(os.path.dirname(__file__))
    document = {"frozen_config": frozen_config(a), "source_hashes": source,
                "init_sha256": sha256_file(a.init) if _LayoutPath(resolve_legacy(a.init)).is_file() else None}
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return {"run_id": str(run_id or uuid.uuid4()), "protocol_hash": digest, **document}


def assert_resume_compatible(current, saved):
    missing = [key for key in RESUME_CONFIG_KEYS if key not in saved]
    if missing:
        raise ValueError("checkpoint lacks frozen configuration fields: " + ", ".join(missing))
    changed = {}
    for key, value in frozen_config(current).items():
        if key not in saved:
            continue
        old = saved[key]
        if key == "init":
            old_compare = os.fspath(resolve_legacy(old))
            new_compare = os.fspath(resolve_legacy(value))
            if old_compare != new_compare:
                changed[key] = (old, value)
        elif old != value:
            changed[key] = (old, value)
    if changed:
        rendered = ", ".join(f"{key}: saved={old!r}, requested={new!r}"
                             for key, (old, new) in changed.items())
        raise ValueError(f"resume configuration differs from checkpoint: {rendered}")


def _cpu_clone(value):
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().clone()
    if isinstance(value, dict):
        return {key: _cpu_clone(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_cpu_clone(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_cpu_clone(item) for item in value)
    return copy.deepcopy(value)


def _new_fit_progress():
    return {
        "updates": 0, "lbfgs_steps": 0, "closures": 0,
        "head_commit_count": 0, "linear_solve_calls": 0, "head_committed": False,
        "elapsed_s": 0.0, "lbfgs_elapsed_s": 0.0,
        "attempt_id": 0, "optimization_phase": "not_started",
        "stop_reason": None, "resumable": True,
    }


def core_of(Fx, Fy, Fz, n):
    """The (3, n, n, n) block the network sees, from three Yee arrays."""
    return torch.stack([Fx[:n, :n, :n], Fy[:n, :n, :n], Fz[:n, :n, :n]])


class Solver:
    def __init__(self, a, dev):
        self.a, self.dev = a, dev
        self.n = a.n
        self.dtype = resolve_torch_dtype(getattr(a, "torch_dtype", torch.float32))
        self.cav = fdtd.PECCavity(side=a.side, n=a.n, dt=a.dt)
        self.dt = self.cav.dt
        self.d_mm = [self.cav.dx * 1e3] * 3

        self.E = [torch.zeros(s, device=dev, dtype=self.dtype) for s in
                  ((a.n, a.n + 1, a.n + 1), (a.n + 1, a.n, a.n + 1),
                   (a.n + 1, a.n + 1, a.n))]
        self.H = [torch.zeros(s, device=dev, dtype=self.dtype) for s in
                  ((a.n + 1, a.n, a.n), (a.n, a.n + 1, a.n),
                   (a.n, a.n, a.n + 1))]
        # A physical step is a transaction.  ``E_pending`` means that curl-H
        # has already updated E and the hard source has been applied exactly
        # once, while curl-E has not yet been accepted to update H.
        self.phase = "before_H"
        self.accepted_steps = 0
        self.current_time_layer = 0
        self.pending_fit_H = None
        self.fit_progress = {"H": _new_fit_progress(), "E": _new_fit_progress()}

        self.net, self.tag = self._make_net()
        self.opt = torch.optim.Adam(self.net.parameters(), lr=a.lr)
        self.net_H, self.net_E = self.net, self.net
        self.opt_H, self.opt_E = self.opt, self.opt
        if getattr(a, "separate_nets", False):
            self.net_E, _ = self._make_net()
            self.opt_E = torch.optim.Adam(self.net_E.parameters(), lr=a.lr)
        self.lbfgs_H = None
        self.lbfgs_E = None
        # The U-net halves the grid at each level, so the side must be a
        # multiple of 2^(levels-1) or the skip connection meets a tensor one
        # cell short on the way back up.  The paper's cavity is 31 intervals
        # (see --n), which is odd, so pad up to the next multiple and crop the
        # prediction back.  Padding is replicate: the slab is cropped away
        # again and only reaches the outermost predicted cell through the
        # convolution's receptive field.
        q = 2 ** (self.levels - 1)
        self.np_ = ((a.n + q - 1) // q) * q
        self.pad = self.np_ - a.n
        self.coords = D.make_coords((self.np_,) * 3, self.d_mm,
                                    self.coord_mode, device=dev, dtype=self.dtype)
        self.d_t = torch.tensor(self.d_mm, dtype=self.dtype).view(1, 3).to(dev)

    def _make_net(self):
        a = self.a
        if a.init in ("random", "rand", "scratch"):
            self.coord_mode, self.norm_mode = a.coords, a.norm
            self.levels = a.levels
            net = D.DCO(levels=a.levels, base=a.base).to(device=self.dev, dtype=self.dtype)
            return net, "random"
        ck = torch.load(resolve_legacy(a.init), map_location=self.dev, weights_only=False)
        self.coord_mode = ck.get("coords", a.coords)
        self.norm_mode = ck.get("norm", a.norm)
        self.levels = ck["levels"]
        net = D.DCO(levels=ck["levels"], base=ck["base"],
                    head=ck.get("head", "direct")).to(device=self.dev, dtype=self.dtype)
        net.load_state_dict(ck["state"])
        return net, os.path.splitext(os.path.basename(a.init))[0]

    # -- the network's curl, in physical units ----------------------------- #
    def predict(self, core, which="shared"):
        e = core.unsqueeze(0)
        if self.pad:
            e = torch.nn.functional.pad(e, (0, self.pad) * 3, mode="replicate")
        eh, _, sc, Lc = D.normalise(e, None, self.d_t, self.norm_mode)
        net = self.net_H if which == "H" else self.net_E if which == "E" else self.net
        out_scale = (getattr(self.a, "h_output_scale", 1.0)
                     if which == "H" else 1.0)
        out = D.denormalise(net(eh, self.coords,
                                     D.d_rel_of(self.d_t, Lc)),
                           sc * out_scale, Lc)[0]
        self.last_predict_context = {"input_scale": sc.detach().clone(), "Lc": Lc.detach().clone(),
                                     "out_scale": float(out_scale), "which": which}
        n = self.n
        return out[:, :n, :n, :n] if self.pad else out

    def _head_lstsq_once(self, core, targets, which):
        """Fit the real direct head once, using features from production predict."""
        if float(getattr(self.a, "head_rcond", head_lstsq.RCOND)) != head_lstsq.RCOND:
            raise ValueError("only registered head_rcond=1e-12 is permitted")
        net = self.net_H if which == "H" else self.net_E if which == "E" else self.net
        if getattr(net, "head_mode", "direct") != "direct":
            raise ValueError("head_lstsq_once requires the registered direct DCO head")
        captured = []

        def capture(_module, inputs):
            captured.append(inputs[0].detach().clone())

        hook = net.head.register_forward_pre_hook(capture)
        try:
            with torch.no_grad():
                self.predict(core, which)
        finally:
            hook.remove()
        if len(captured) != 1:
            raise RuntimeError("production head feature hook did not capture exactly one tensor")
        context = self.last_predict_context
        scale, lc, out_scale = context["input_scale"], context["Lc"], context["out_scale"]
        # ``targets`` are in the exact units currently compared by
        # ``inner_train``.  Convert them through the same scale/Lc/output
        # mapping used by ``predict``; this also covers the registered H
        # scale without inventing a second normalisation path.
        scale_scalar = scale.reshape(-1)[0]
        lc_scalar = lc.reshape(-1)[0]
        normalized_targets = [target * lc_scalar / (scale_scalar * out_scale) for target in targets]
        weight, bias, diagnostics = head_lstsq.solve_head(captured[0][0], normalized_targets)
        if not all_finite((weight, bias)):
            raise FloatingPointError("head_lstsq produced non-finite parameters")
        previous = {"weight": net.head.weight.detach().clone(), "bias": net.head.bias.detach().clone()}
        with torch.no_grad():
            net.head.weight.copy_(weight.to(device=net.head.weight.device, dtype=net.head.weight.dtype))
            net.head.bias.copy_(bias.to(device=net.head.bias.device, dtype=net.head.bias.dtype))
        optimizer = self.opt_H if which == "H" else self.opt_E if which == "E" else self.opt
        cleared = head_lstsq.clear_head_adam_state(optimizer, net.head)
        # Re-run the production path after float32 write-back.  The caller
        # evaluates the physical R; this normalized SSE check catches a bad
        # cast or an accidental support mismatch before Adam begins.
        with torch.no_grad():
            prediction = self.predict(core, which)
        return {"previous": previous, "diagnostics": diagnostics, "cleared_adam_state": cleared,
                "feature_shape": list(captured[0][0].shape), "prediction": prediction}

    # -- eq. (7): the target IS the Yee stencil ---------------------------- #
    def yee_curl_E(self):
        cx, cy, cz = fdtd.curl_E(*[t.cpu().numpy() for t in self.E],
                                 self.cav.dx, self.cav.dy, self.cav.dz)
        return [to_t(c, self.dev, self.dtype) for c in (cx, cy, cz)]

    def yee_curl_H(self):
        cx, cy, cz = fdtd.curl_H(*[t.cpu().numpy() for t in self.H],
                                 self.cav.dx, self.cav.dy, self.cav.dz)
        return [to_t(c, self.dev, self.dtype) for c in (cx, cy, cz)]

    def extract_input_core(self, field, which):
        """Single production adapter for the E layout and registered H shift."""
        n = self.n
        if which == "H" and getattr(self.a, "h_shift", False):
            Hx, Hy, Hz = field
            return torch.stack([Hx[1:n + 1, :n, :n],
                                Hy[:n, 1:n + 1, :n],
                                Hz[:n, :n, 1:n + 1]])
        return core_of(*field, n)

    def inner_train(self, field, target, which="shared"):
        """Fit one curl target and return an explicit, post-update record.

        The only zero shortcut is a strictly zero *input and target* physical
        field.  A non-zero irrotational input has zero target but still goes
        through the network with an input-derived scale, so it cannot receive
        a hidden target-value shortcut.
        """
        started = time.perf_counter()
        progress = getattr(self, "fit_progress", {}).setdefault(which, _new_fit_progress())
        for key, value in _new_fit_progress().items():
            progress.setdefault(key, value)
        # A terminal attempt is evidence of an exhausted or unsafe budget.  A
        # resumed formal run must not erase that fact by simply entering this
        # function again.  Diagnostic loading is handled explicitly in
        # ``load_state_payload``; production training always rejects it.
        if (progress.get("stop_reason") in TERMINAL_FIT_REASONS
                or not bool(progress.get("resumable", True))):
            raise ValueError(f"terminal fit state for {which}; start a new registered attempt")
        prior_updates = int(progress.get("updates", 0))
        prior_lbfgs = int(progress.get("lbfgs_steps", 0))
        prior_closures = int(progress.get("closures", 0))
        prior_elapsed = float(progress.get("elapsed_s", 0.0))
        prior_lbfgs_elapsed = float(progress.get("lbfgs_elapsed_s", 0.0))
        progress["attempt_id"] = int(progress["attempt_id"]) + 1
        progress["optimization_phase"] = "adam"
        progress["stop_reason"] = None
        progress["resumable"] = True
        remaining_updates = max(0, int(self.a.max_inner) - prior_updates)
        n = self.n
        core = self.extract_input_core(field, which)
        # E is in V/m while H is in A/m.  The free-space pretraining sees
        # one field scale; without impedance scaling the H samples arrive at
        # ~1/377 of the E magnitude and the input-derived output normaliser
        # amplifies their dimensionless curl targets by ~Z0.  Scaling only
        # the network input is invertible through normalise/denormalise and
        # leaves the Yee update in physical units.
        h_scale = getattr(self.a, "h_scale", 1.0) if which == "H" else 1.0
        out_scale = getattr(self.a, "h_output_scale", 1.0) if which == "H" else 1.0
        if h_scale != 1.0:
            core = core * h_scale
        # The Yee curl components are staggered and therefore do not share
        # one common shape.  The old implementation cropped every component
        # to the smallest cube (30^3 for curl-H), silently dropping one valid
        # plane from the first component and shifting the other two.  The
        # paper's (7) sums each component on its own Yee support.  Keep every
        # target element the network can emit, while leaving a possible outer
        # n+1 boundary plane at its exact Yee value.
        def pred_slices(out):
            return [out[k, :min(t.shape[0], n),
                            :min(t.shape[1], n),
                            :min(t.shape[2], n)]
                    for k, t in enumerate(target)]

        tgt = [t[:min(t.shape[0], n),
                 :min(t.shape[1], n),
                 :min(t.shape[2], n)] for t in target]
        physical_tgt = [t.clone() for t in tgt]
        physical_target_ss = float(sum(t.pow(2).sum() for t in physical_tgt))
        target_count = sum(t.numel() for t in physical_tgt)
        den_parts = [float(t.pow(2).sum()) for t in tgt]
        den = sum(den_parts)
        # If H is rescaled into the network, train the network to return the
        # correspondingly rescaled curl and convert it back before the Yee
        # update.  This is the physically consistent transformation; applying
        # a scale only to the input would silently multiply curl-H by Z0.
        if h_scale != 1.0:
            tgt = [t * h_scale for t in tgt]
            den_parts = [d * h_scale ** 2 for d in den_parts]
            den = sum(den_parts)
        if out_scale != 1.0:
            tgt = [t * out_scale for t in tgt]
            den_parts = [d * out_scale ** 2 for d in den_parts]
            den = sum(den_parts)
        # Step 1 has H identically zero, so its curl is zero: the relative
        # denominator would be 0 and, worse, rms normalisation of an all-zero
        # input divides by zero and poisons the weights with NaN.  A zero
        # field has a zero curl exactly -- no network needed, nothing to
        # learn from, so return it and leave the weights untouched.
        zero_input = all(float(part.abs().max()) == 0.0 for part in field)
        if zero_input and physical_target_ss == 0.0:
            zeros = [torch.zeros_like(t) for t in physical_tgt]
            progress["attempt_id"] = int(progress["attempt_id"])
            progress["optimization_phase"] = "complete"
            progress["stop_reason"] = "zero_input"
            progress["resumable"] = True
            progress["elapsed_s"] = prior_elapsed + (time.perf_counter() - started)
            return FitRecord(prior_updates, 0, 0.0, 0.0, 0.0, 0.0, 0.0, True,
                             "zero_input", time.perf_counter() - started,
                             zeros, 0.0, target_count)
        zero_target = physical_target_ss == 0.0
        curl0 = CURL_H0 if which == "H" else CURL_E0
        # Scale.  Eq. (7) is written as a plain SUM of squares and IV-A stops
        # the inner training below 1e-4.  Taken literally that threshold is
        # scale-dependent, and at the start of a cavity run the fields are
        # ~0, so the sum is ~1e-9 and the rule is satisfied on iteration 1 --
        # even by a randomly initialised network.  The run then trains
        # nothing and the Fig 8 control would be meaningless.
        # Fig 8's own axis is labelled "Cumulative M.S.E." and starts near
        # 1.0, which an untrained network reaches only if the quantity is
        # NORMALISED.  So the default here is the relative form; --tol-mode
        # abs gives the literal reading of eq. (7) for comparison.
        # A non-zero input with a zero curl is scored by the registered fixed
        # physical scale.  It must never be reported as a relative residual:
        # its target energy is exactly zero.
        if den == 0.0:
            den = max(float(target_count) * curl0 * curl0, 1e-30)
        den_t = torch.tensor(den, device=self.dev).clamp_min(1e-30)
        tot, n_updates, n_evals = 0.0, 0, 0
        n_lbfgs_steps = n_closures = 0
        opt = self.opt_H if which == "H" else self.opt_E if which == "E" else self.opt

        def elapsed_total():
            return prior_elapsed + (time.perf_counter() - started)

        def save_progress(phase, reason=None, *, lbfgs_elapsed=None):
            progress["updates"] = prior_updates + n_updates
            progress["lbfgs_steps"] = prior_lbfgs + n_lbfgs_steps
            progress["closures"] = prior_closures + n_closures
            progress["elapsed_s"] = elapsed_total()
            if lbfgs_elapsed is not None:
                progress["lbfgs_elapsed_s"] = prior_lbfgs_elapsed + lbfgs_elapsed
            progress["optimization_phase"] = phase
            progress["stop_reason"] = reason
            progress["resumable"] = reason not in ("max_updates", "closure_budget", "nonfinite", "time_budget")
        def evaluate(with_grad=False):
            nonlocal n_evals
            context = torch.enable_grad() if with_grad else torch.no_grad()
            with context:
                pred = pred_slices(self.predict(core, which))
                sq_parts = [(p - t).pow(2).sum() for p, t in zip(pred, tgt)]
                sq = sum(sq_parts)
                if zero_target:
                    loss = sq / den_t
                elif self.a.tol_mode == "rel" and getattr(self.a, "component_rel", False):
                    loss = sum(q / max(d, 1e-30) for q, d in zip(sq_parts, den_parts)) / 3.0
                else:
                    loss = sq / den_t if self.a.tol_mode == "rel" else sq
            n_evals += 1
            return pred, sq, loss

        def stop_met(prediction, objective):
            if not zero_target:
                physical = prediction
                if out_scale != 1.0:
                    physical = [part / out_scale for part in physical]
                if h_scale != 1.0:
                    physical = [part / h_scale for part in physical]
                physical_sse = sum((part - ref).pow(2).sum()
                                   for part, ref in zip(physical, physical_tgt))
                physical_ratio = float((physical_sse / max(physical_target_ss, 1e-30)).detach())
                # Component-wise relative objectives are useful gradients,
                # but Algorithm 1's acceptance contract is the total physical
                # residual on the declared Yee support.  Never accept a fit
                # merely because two small components hide a large one.
                return reached(physical_ratio, self.a.tol)
            physical = prediction
            if out_scale != 1.0:
                physical = [part / out_scale for part in physical]
            if h_scale != 1.0:
                physical = [part / h_scale for part in physical]
            maximum = max(float((part - ref).abs().max()) for part, ref in zip(physical, physical_tgt))
            return (finite_scalar(objective) and float(objective.detach()) <= 1e-10
                    and maximum / curl0 <= 1e-4)

        pred, _, loss = evaluate(with_grad=False)
        initial_loss = float(loss.detach())
        self.last_fit_trace = [{"updates": prior_updates, "loss": initial_loss}]
        if not all_finite(pred) or not torch.isfinite(loss):
            save_progress("adam", "nonfinite")
            return FitRecord(0, n_evals, initial_loss, initial_loss, float("nan"),
                             float("nan"), physical_target_ss, False, "nonfinite",
                             time.perf_counter() - started, pred, 0.0, target_count)
        if getattr(self.a, "head_lstsq_once", False):
            if int(self.a.max_inner) > 499 or int(getattr(self.a, "lbfgs_closures", 0)) != 0:
                raise ValueError("head_lstsq_once requires Adam<=499 and no LBFGS")
            if not stop_met(pred, loss) and not bool(progress.get("head_committed", False)):
                try:
                    head_info = self._head_lstsq_once(core, tgt, which)
                except (FloatingPointError, RuntimeError, ValueError):
                    save_progress("head_lstsq", "head_numeric_failure")
                    return FitRecord(prior_updates + n_updates, n_evals, initial_loss, float("nan"), float("nan"),
                                     float("nan"), physical_target_ss, False, "head_numeric_failure",
                                     time.perf_counter() - started, pred, tot, target_count)
                progress["head_commit_count"] = int(progress.get("head_commit_count", 0)) + 1
                progress["linear_solve_calls"] = int(progress.get("linear_solve_calls", 0)) + 3
                progress["head_committed"] = True
                progress["head_diagnostics"] = _cpu_clone(head_info["diagnostics"])
                progress["head_adam_state_cleared"] = list(head_info["cleared_adam_state"])
                progress["head_feature_shape"] = list(head_info["feature_shape"])
                n_evals += 1
                pred, _, loss = evaluate(with_grad=False)
                self.last_fit_trace.append({"updates": prior_updates, "loss": float(loss.detach()),
                                            "head_commit_count": progress["head_commit_count"]})
                if not all_finite(pred) or not torch.isfinite(loss):
                    save_progress("head_lstsq", "head_numeric_failure")
                    return FitRecord(prior_updates + n_updates, n_evals, initial_loss, float("nan"), float("nan"),
                                     float("nan"), physical_target_ss, False, "head_numeric_failure",
                                     time.perf_counter() - started, pred, tot, target_count)
        stop_reason = "tol_met" if stop_met(pred, loss) else "max_updates"
        while not stop_met(pred, loss) and n_updates < remaining_updates:
            if getattr(self.a, "inner_time_budget_s", 0.0) > 0.0 and (
                elapsed_total() >= self.a.inner_time_budget_s
            ):
                stop_reason = "time_budget"
                save_progress("adam", stop_reason)
                break
            opt.zero_grad(set_to_none=True)
            pred, _, train_loss = evaluate(with_grad=True)
            value = float(train_loss.detach())
            if not all_finite(pred) or not torch.isfinite(train_loss):
                save_progress("adam", "nonfinite")
                return FitRecord(prior_updates + n_updates, n_evals, initial_loss, value, float("nan"),
                                 float("nan"), physical_target_ss, False, "nonfinite",
                                 time.perf_counter() - started, pred, tot, target_count)
            tot += value
            train_loss.backward()
            params = list(self.net_H.parameters() if which == "H" else
                          self.net_E.parameters() if which == "E" else
                          self.net.parameters())
            if not all_finite(param.grad for param in params if param.grad is not None):
                save_progress("adam", "nonfinite")
                return FitRecord(prior_updates + n_updates, n_evals, initial_loss, value, float("nan"),
                                 float("nan"), physical_target_ss, False, "nonfinite",
                                 time.perf_counter() - started, pred, tot, target_count)
            if getattr(self.a, "grad_clip", 0.0) > 0.0:
                torch.nn.utils.clip_grad_norm_(params, self.a.grad_clip)
                if not all_finite(param.grad for param in params if param.grad is not None):
                    save_progress("adam", "nonfinite")
                    return FitRecord(prior_updates + n_updates, n_evals, initial_loss, value, float("nan"),
                                     float("nan"), physical_target_ss, False, "nonfinite",
                                     time.perf_counter() - started, pred, tot, target_count)
            opt.step()
            n_updates += 1
            if not all_finite(params):
                save_progress("adam", "nonfinite")
                return FitRecord(prior_updates + n_updates, n_evals, initial_loss, value, float("nan"),
                                 float("nan"), physical_target_ss, False, "nonfinite",
                                 time.perf_counter() - started, pred, tot, target_count)
            save_progress("adam")
            pred, _, loss = evaluate(with_grad=False)
            if n_updates % 10 == 0 or stop_met(pred, loss) or n_updates == remaining_updates:
                self.last_fit_trace.append({"updates": prior_updates + n_updates,
                                            "loss": float(loss.detach())})
            if not all_finite(pred) or not torch.isfinite(loss):
                save_progress("adam", "nonfinite")
                return FitRecord(prior_updates + n_updates, n_evals, initial_loss, float("nan"), float("nan"),
                                 float("nan"), physical_target_ss, False, "nonfinite",
                                 time.perf_counter() - started, pred, tot, target_count)
            callback = getattr(self, "on_inner_update", None)
            if callback is not None and callback(which, _cpu_clone(progress)):
                stop_reason = "interrupt"
                save_progress("adam", stop_reason)
                break
        # P4-A is an explicitly registered fixed-state branch: a bounded
        # LBFGS refinement may follow Adam.  Closure evaluations are reported
        # separately because one LBFGS ``step`` is not comparable to one Adam
        # parameter update.
        closure_budget = max(0, int(getattr(self.a, "lbfgs_closures", 0)) - prior_closures)
        lbfgs_budget_s = float(getattr(self.a, "lbfgs_time_budget_s", 0.0))
        if (not stop_met(pred, loss) and closure_budget > 0):
            lbfgs_started = time.perf_counter()
            progress["optimization_phase"] = "lbfgs"
            lbfgs = self._lbfgs_for(which, max_eval=closure_budget)
            # Advance this snapshot only after a whole LBFGS.step() accepts.
            lbfgs_safe = self._network_state(which, include_lbfgs=True)
            class _ClosureBudget(Exception):
                pass
            def closure():
                nonlocal n_closures, tot
                lbfgs_elapsed = time.perf_counter() - lbfgs_started
                if (n_closures >= closure_budget or
                    (lbfgs_budget_s > 0 and prior_lbfgs_elapsed + lbfgs_elapsed >= lbfgs_budget_s) or
                    (getattr(self.a, "inner_time_budget_s", 0.0) > 0.0 and elapsed_total() >= self.a.inner_time_budget_s)):
                    raise _ClosureBudget()
                lbfgs.zero_grad(set_to_none=True)
                pred_c, _, loss_c = evaluate(with_grad=True)
                if not all_finite(pred_c) or not torch.isfinite(loss_c):
                    raise FloatingPointError("nonfinite LBFGS closure")
                n_closures += 1
                tot += float(loss_c.detach())
                loss_c.backward()
                save_progress("lbfgs", lbfgs_elapsed=time.perf_counter() - lbfgs_started)
                return loss_c
            try:
                while (not stop_met(pred, loss) and n_closures < closure_budget
                       and (lbfgs_budget_s <= 0 or prior_lbfgs_elapsed + time.perf_counter() - lbfgs_started < lbfgs_budget_s)
                       and (getattr(self.a, "inner_time_budget_s", 0.0) <= 0.0 or elapsed_total() < self.a.inner_time_budget_s)):
                    lbfgs.step(closure)
                    n_lbfgs_steps += 1
                    pred, _, loss = evaluate(with_grad=False)
                    lbfgs_safe = self._network_state(which, include_lbfgs=True)
                    save_progress("lbfgs", lbfgs_elapsed=time.perf_counter() - lbfgs_started)
                    if not all_finite(pred) or not torch.isfinite(loss):
                        save_progress("lbfgs", "nonfinite", lbfgs_elapsed=time.perf_counter() - lbfgs_started)
                        return FitRecord(prior_updates + n_updates, n_evals, initial_loss, float("nan"), float("nan"),
                                         float("nan"), physical_target_ss, False, "nonfinite",
                                         time.perf_counter() - started, pred, tot, target_count,
                                         prior_lbfgs + n_lbfgs_steps, prior_closures + n_closures)
                    callback = getattr(self, "on_lbfgs_step", None)
                    if callback is not None and callback(which, _cpu_clone(progress)):
                        stop_reason = "interrupt"
                        save_progress("lbfgs", stop_reason,
                                      lbfgs_elapsed=time.perf_counter() - lbfgs_started)
                        break
            except _ClosureBudget:
                # Strong-Wolfe may leave parameters at a trial point when the
                # closure budget interrupts it.  Preserve that raw state for
                # diagnosis, then return to the last accepted parameters and
                # recompute the reported residual on those parameters.
                save_progress("lbfgs", "closure_budget", lbfgs_elapsed=time.perf_counter() - lbfgs_started)
                self.last_failure_raw = self.state_payload()
                self._restore_network_state(which, lbfgs_safe)
                pred, _, loss = evaluate(with_grad=False)
                stop_reason = "closure_budget"
            except FloatingPointError:
                save_progress("lbfgs", "nonfinite", lbfgs_elapsed=time.perf_counter() - lbfgs_started)
                return FitRecord(prior_updates + n_updates, n_evals, initial_loss, float("nan"), float("nan"),
                                 float("nan"), physical_target_ss, False, "nonfinite",
                                 time.perf_counter() - started, pred, tot, target_count,
                                 prior_lbfgs + n_lbfgs_steps, prior_closures + n_closures)
            if not stop_met(pred, loss) and lbfgs_budget_s > 0 and prior_lbfgs_elapsed + time.perf_counter() - lbfgs_started >= lbfgs_budget_s:
                stop_reason = "time_budget"
                save_progress("lbfgs", stop_reason, lbfgs_elapsed=time.perf_counter() - lbfgs_started)
        # ``loss`` was evaluated after the last update, including a hit on the
        # last permitted update; this avoids the old pre-update mislabelling.
        out = pred
        final_loss = float(loss.detach())
        passed = stop_met(pred, loss)
        if passed:
            stop_reason = "tol_met"
        save_progress("complete" if passed else progress.get("optimization_phase", "adam"), stop_reason)
        # Physical-unit residuals are calculated after undoing all network
        # scaling, independently of the stopping-objective normalisation.
        if out_scale != 1.0:
            out = [p / out_scale for p in out]
        if h_scale != 1.0:
            out = [p / h_scale for p in out]
        physical_sse = float(sum((p - t).pow(2).sum() for p, t in zip(out, physical_tgt)))
        max_abs = float(max((p - t).abs().max().item() for p, t in zip(out, physical_tgt)))
        rule = "zero_target_fixed_scale" if zero_target else "relative_target"
        return FitRecord(prior_updates + n_updates, n_evals, initial_loss, final_loss, physical_sse,
                         physical_sse / max(target_count, 1), physical_target_ss,
                         passed, stop_reason, time.perf_counter() - started,
                         out, tot, target_count, prior_lbfgs + n_lbfgs_steps, prior_closures + n_closures,
                         None if zero_target else physical_sse / physical_target_ss,
                         max_abs / curl0, rule)

    def _lbfgs_for(self, which, *, max_eval=None):
        """Return the persistent LBFGS state for one curl fit direction."""
        attr = "lbfgs_H" if which == "H" else "lbfgs_E"
        optimizer = getattr(self, attr, None)
        if optimizer is None:
            net = self.net_H if which == "H" else self.net_E
            optimizer = torch.optim.LBFGS(
                list(net.parameters()), lr=float(getattr(self.a, "lbfgs_lr", 1.0)),
                max_iter=1, max_eval=max_eval,
                history_size=int(getattr(self.a, "lbfgs_history", 10)),
                line_search_fn="strong_wolfe",
            )
            setattr(self, attr, optimizer)
        return optimizer

    def _network_state(self, which, *, include_lbfgs=False):
        net = self.net_H if which == "H" else self.net_E
        opt = self.opt_H if which == "H" else self.opt_E
        state = {"net": _cpu_clone(net.state_dict()), "opt": _cpu_clone(opt.state_dict())}
        if include_lbfgs:
            lbfgs = self.lbfgs_H if which == "H" else self.lbfgs_E
            state["lbfgs"] = _cpu_clone(lbfgs.state_dict()) if lbfgs is not None else None
        return state

    def _restore_network_state(self, which, state):
        net = self.net_H if which == "H" else self.net_E
        opt = self.opt_H if which == "H" else self.opt_E
        net.load_state_dict(state["net"])
        opt.load_state_dict(state["opt"])
        if "lbfgs" in state:
            if state["lbfgs"] is None:
                if which == "H":
                    self.lbfgs_H = None
                else:
                    self.lbfgs_E = None
            else:
                self._lbfgs_for(which).load_state_dict(state["lbfgs"])

    @staticmethod
    def _fit_payload(record):
        if record is None:
            return None
        data = record.as_dict(include_prediction=True)
        data["prediction"] = _cpu_clone(data["prediction"])
        return data

    @staticmethod
    def _fit_from_payload(payload, dev):
        if payload is None:
            return None
        data = dict(payload)
        data["prediction"] = [part.to(dev) for part in data["prediction"]]
        return FitRecord(**data)

    def _record_fit_attempt(self, which, record):
        progress = self.fit_progress[which]
        progress["updates"] = max(int(progress["updates"]), int(record.n_updates))
        progress["lbfgs_steps"] = max(int(progress["lbfgs_steps"]), int(record.n_lbfgs_steps))
        progress["closures"] = max(int(progress["closures"]), int(record.n_closures))
        # inner_train maintains elapsed time incrementally so a raw checkpoint
        # taken during an optimizer call contains the consumed budget already.
        progress["elapsed_s"] = max(float(progress["elapsed_s"]), float(record.elapsed_s))
        progress["stop_reason"] = record.stop_reason
        progress["resumable"] = record.stop_reason not in ("max_updates", "closure_budget", "nonfinite", "time_budget")

    def _clear_fit_progress(self, which):
        self.fit_progress[which] = _new_fit_progress()
        if which == "H":
            self.lbfgs_H = None
        else:
            self.lbfgs_E = None

    def state_payload(self):
        """Complete DUT state for atomic checkpoints; reference state is added by main."""
        return {
            "state_schema": STATE_SCHEMA,
            "payload_role": "solver_state",
            "script_version": SCRIPT_VERSION,
            "phase": self.phase,
            "accepted_steps": self.accepted_steps,
            "current_time_layer": self.current_time_layer,
            "E": _cpu_clone(self.E),
            "H": _cpu_clone(self.H),
            "net_H": _cpu_clone(self.net_H.state_dict()),
            "net_E": _cpu_clone(self.net_E.state_dict()),
            "opt_H": _cpu_clone(self.opt_H.state_dict()),
            "opt_E": _cpu_clone(self.opt_E.state_dict()),
            "lbfgs_H": _cpu_clone(self.lbfgs_H.state_dict()) if self.lbfgs_H is not None else None,
            "lbfgs_E": _cpu_clone(self.lbfgs_E.state_dict()) if self.lbfgs_E is not None else None,
            "shared_network": self.net_H is self.net_E,
            "rng": capture_rng(),
            "config": vars(self.a).copy(),
            "frozen_config": frozen_config(self.a),
            "fit_progress": _cpu_clone(self.fit_progress),
            "pending_fit_H": self._fit_payload(self.pending_fit_H),
        }

    def load_state_payload(self, payload, *, diagnostic_only=False):
        required = {"state_schema", "payload_role", "phase", "accepted_steps", "current_time_layer",
                    "E", "H", "net_H", "net_E", "opt_H", "opt_E", "rng", "frozen_config",
                    "fit_progress", "pending_fit_H"}
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError("checkpoint lacks required solver fields: " + ", ".join(missing))
        if payload.get("state_schema") != STATE_SCHEMA or payload.get("payload_role") != "solver_state":
            raise ValueError("checkpoint has incompatible solver schema or role")
        if "frozen_config" in payload:
            assert_resume_compatible(self.a, payload["frozen_config"])
        loaded_progress = _cpu_clone(payload.get("fit_progress", self.fit_progress))
        terminal_roles = [which for which in ("H", "E")
                          if (loaded_progress.get(which, {}).get("stop_reason") in TERMINAL_FIT_REASONS
                              or not bool(loaded_progress.get(which, {}).get("resumable", True)))]
        if terminal_roles and not diagnostic_only:
            raise ValueError("terminal fit state cannot be restored for production training: "
                             + ", ".join(terminal_roles))
        self.phase = payload["phase"]
        self.accepted_steps = int(payload["accepted_steps"])
        self.current_time_layer = int(payload["current_time_layer"])
        self.E = [x.to(self.dev).clone() for x in payload["E"]]
        self.H = [x.to(self.dev).clone() for x in payload["H"]]
        self.net_H.load_state_dict(payload["net_H"])
        if self.net_E is not self.net_H:
            self.net_E.load_state_dict(payload["net_E"])
        self.opt_H.load_state_dict(payload["opt_H"])
        if self.opt_E is not self.opt_H:
            self.opt_E.load_state_dict(payload["opt_E"])
        self.fit_progress = {}
        for which in ("H", "E"):
            merged = _new_fit_progress()
            merged.update(loaded_progress.get(which, {}))
            self.fit_progress[which] = merged
        for which, state in (("H", payload.get("lbfgs_H")), ("E", payload.get("lbfgs_E"))):
            if state is not None:
                self._lbfgs_for(which).load_state_dict(state)
        self.pending_fit_H = self._fit_from_payload(payload.get("pending_fit_H"), self.dev)
        restore_rng(payload["rng"])

    def _insert_prediction(self, exact, prediction, which):
        """Insert every learned target degree; PEC-only planes are analytic.

        Curl-H targets lie entirely in the network cube.  Curl-E has one
        high-side plane per component.  After a PEC projection that plane is
        identically zero, so formal runs impose the physical boundary value
        explicitly rather than retaining an unlabelled exact-Yee fallback.
        """
        for k in range(3):
            sh = tuple(min(exact[k].shape[d], prediction[k].shape[d]) for d in range(3))
            exact[k][:sh[0], :sh[1], :sh[2]] = prediction[k][:sh[0], :sh[1], :sh[2]]
            uncovered = exact[k].numel() - int(np.prod(sh))
            if uncovered:
                if which != "E" or exact[k].shape[k] != self.n + 1:
                    raise RuntimeError(f"uncovered non-boundary curl support: {which}{k} {tuple(exact[k].shape)}")
                high = [slice(None)] * 3
                high[k] = self.n
                if not bool(torch.all(exact[k][tuple(high)] == 0).item()):
                    raise RuntimeError("curl-E high plane is not the registered PEC-zero boundary")
                exact[k][tuple(high)] = 0.0
            if which == "E":
                # H normal to a PEC wall is zero.  The network cube includes
                # the low normal face, so project it explicitly as well as the
                # high face that lies outside that cube.
                low = [slice(None)] * 3
                high = [slice(None)] * 3
                low[k], high[k] = 0, exact[k].shape[k] - 1
                exact[k][tuple(low)] = 0.0
                exact[k][tuple(high)] = 0.0
        return exact

    def _update_E_and_source(self, predicted_curl_H, g_t):
        ch = self._insert_prediction(self.yee_curl_H(), predicted_curl_H, "H")
        ke = self.dt / fdtd.EPS0
        self.E[0][:, 1:-1, 1:-1] += ke * ch[0]
        self.E[1][1:-1, :, 1:-1] += ke * ch[1]
        self.E[2][1:-1, 1:-1, :] += ke * ch[2]
        c = self.n // 2
        self.E[2][c, c, c] = g_t
        self.apply_pec()

    def _update_H(self, predicted_curl_E):
        ce = self._insert_prediction(self.yee_curl_E(), predicted_curl_E, "E")
        kh = self.dt / self.cav.mu
        for k in range(3):
            self.H[k] -= kh * ce[k]

    def step(self, g_t):
        """Execute or resume exactly one physical time-layer transaction."""
        strict = bool(getattr(self.a, "strict_stop", False))
        fit_H = getattr(self, "pending_fit_H", None)
        fit_E = None
        if self.phase == "before_H":
            if getattr(self.a, "reset_opt_each_step", False) and not getattr(self, "fit_progress", {}).get("H", {}).get("updates", 0):
                self.opt_H = torch.optim.Adam(self.net_H.parameters(), lr=self.a.lr)
                self.opt_E = self.opt_H if self.net_E is self.net_H else torch.optim.Adam(self.net_E.parameters(), lr=self.a.lr)
            safe_H = self._network_state("H")
            fit_H = self.inner_train(self.H, self.yee_curl_H(), "H")
            if hasattr(self, "_record_fit_attempt"):
                self._record_fit_attempt("H", fit_H)
            if fit_H.stop_reason in ("nonfinite", "head_numeric_failure"):
                self.last_failure_raw = self.state_payload()
                self._restore_network_state("H", safe_H)
                return StepRecord(self.current_time_layer, False, "before_H", fit_H, None, fit_H.stop_reason)
            if strict and not fit_H.passed:
                return StepRecord(self.current_time_layer, False, "before_H", fit_H, None, fit_H.stop_reason)
            self._update_E_and_source(fit_H.prediction, g_t)
            self.phase = "E_pending"
            self.pending_fit_H = fit_H
        elif self.phase != "E_pending":
            raise RuntimeError(f"unknown transaction phase: {self.phase}")

        safe_E = self._network_state("E")
        fit_E = self.inner_train(self.E, self.yee_curl_E(), "E")
        if hasattr(self, "_record_fit_attempt"):
            self._record_fit_attempt("E", fit_E)
        if fit_E.stop_reason in ("nonfinite", "head_numeric_failure"):
            self.last_failure_raw = self.state_payload()
            self._restore_network_state("E", safe_E)
            return StepRecord(self.current_time_layer, False, "E_pending", fit_H, fit_E, fit_E.stop_reason)
        if strict and not fit_E.passed:
            return StepRecord(self.current_time_layer, False, "E_pending", fit_H, fit_E, fit_E.stop_reason)
        self._update_H(fit_E.prediction)
        self.phase = "completed"
        self.accepted_steps += 1
        self.current_time_layer += 1
        completed = StepRecord(self.current_time_layer - 1, True, "completed", fit_H, fit_E)
        self.phase = "before_H"
        self.pending_fit_H = None
        if hasattr(self, "_clear_fit_progress"):
            self._clear_fit_progress("H")
            self._clear_fit_progress("E")
        return completed

    def apply_pec(self):
        """Tangential E = 0 on all six faces.

        The paper says PECs are "modeled in the PI-DON by setting the
        predicted tangential components on PECs to zero" -- that is a
        condition on E, not on the curl components, so it belongs here after
        the E update rather than inside the curl loss.  (First version of this
        file masked faces of the predicted CURL instead, which is a different
        and wrong constraint.)
        """
        Ex, Ey, Ez = self.E
        Ex[:, 0, :] = Ex[:, -1, :] = Ex[:, :, 0] = Ex[:, :, -1] = 0.0
        Ey[0, :, :] = Ey[-1, :, :] = Ey[:, :, 0] = Ey[:, :, -1] = 0.0
        Ez[0, :, :] = Ez[-1, :, :] = Ez[:, 0, :] = Ez[:, -1, :] = 0.0


# --------------------------------------------------------------------------- #
def diagnose(hist, a):
    """Print a descriptive nMAE trend only; it is not a stability proof."""
    ok = [r for r in hist
          if r.get("nmae") is not None and np.isfinite(float(r["nmae"])) and float(r["nmae"]) > 0]
    if len(ok) < 8:
        return
    x = np.array([r["step"] for r in ok], float)
    y = np.log(np.array([r["nmae"] for r in ok], float))
    m = x > x.max() * 0.15
    if m.sum() < 5:
        return
    k = float(np.polyfit(x[m], y[m], 1)[0])
    g = float(np.exp(k))
    ls = [r["lossE"] for r in ok if np.isfinite(r["lossE"])]
    loss = float(np.median(ls)) if ls else float("nan")
    print("\n  --- 描述性轨迹拟合（非谱半径、非稳定性证明） ---")
    print(f"  nMAE 对数线性拟合 stepgain = {g:.5f}（每步 {100 * (g - 1):+.2f}%）")
    print(f"  curl-E 最终停止目标中位数 = {loss:.2e}")
    print(f"RESULT descriptive_stepgain {g:.6f}")


def calibrate(a, dev):
    """Sweep the inner learning rate.  Algorithm 1 is only Algorithm 1 if the
    inner training actually reaches the stopping tolerance; otherwise it is
    just "N gradient steps per time step" and the paper's stability argument
    does not apply.

    2026-09-11, first GPU run: every step used the full 20 inner iterations
    and the loss sat at 0.04-0.27, never near 1e-4.  lr was 1e-4 -- copied
    from the paper's STAGE-1 setting, where it runs for 1000 epochs.  The
    paper does not state a stage-2 inner learning rate, so it is ours to
    choose, and 1e-4 over a handful of iterations is simply too slow.
    """
    print("  lr sweep: does the inner training reach the tolerance at all?")
    print(f"  {a.steps} time steps each, tol {a.tol:.0e}, "
          f"max {a.max_inner} inner iters\n")
    print(f"  {'lr':>8s} {'max it':>7s} {'reached tol':>12s} "
          f"{'mean iters':>11s} {'mean loss':>11s} {'s/step':>8s}  "
          f"{'nMAE@end':>10s}")
    print("  " + "-" * 76)
    best = None
    grid = [(lr, it) for lr in (a.calib or [a.lr])
            for it in (a.calib_iters or [a.max_inner])]
    for lr, mi in grid:
        b = argparse.Namespace(**vars(a))
        b.lr, b.max_inner = lr, mi
        s = Solver(b, dev)
        g = fdtd.source_waveform(a.steps, s.dt, a.fmax, "gauss")
        c = a.n // 2
        ref = fdtd.PECCavity(side=a.side, n=a.n, dt=a.dt)
        hit, its, ls, t0 = 0, [], [], time.time()
        for t in range(a.steps):
            r = s.step(float(g[t]))
            ref.step(src_value=0.0, src_idx=(c, c, c))
            ref.Ez[c, c, c] = g[t]
            ref.apply_pec()
            for fit in (r.fit_H, r.fit_E):
                if fit is None or fit.stop_reason == "zero_input":
                    continue
                its.append(fit.n_updates)
                ls.append(fit.loss_final)
                hit += fit.passed
        dt_s = (time.time() - t0) / a.steps
        e = s.E[2].detach().cpu().numpy()
        nm = float(np.abs(e - ref.Ez).mean() / (np.abs(ref.Ez).max() + 1e-30))
        frac = hit / len(its)
        print(f"  {lr:>8.0e} {mi:>7d} {frac:>11.0%} {np.mean(its):>11.1f} "
              f"{np.mean(ls):>11.2e} {dt_s:>7.2f}s {nm:>10.2e}")
        if best is None or np.mean(ls) < best[1]:
            best = (lr, float(np.mean(ls)), frac, mi)
    print(f"\n  best mean loss at lr = {best[0]:.0e}, max_inner = {best[3]} "
          f"({best[1]:.2e}, reached tol on {best[2]:.0%} of real sub-steps)")
    if best[2] < 0.5:
        print("  STILL not reaching the tolerance on most sub-steps.  Then the")
        print("  bottleneck is not the learning rate -- raise --max-inner, or")
        print("  the network cannot represent the cavity curl that closely and")
        print("  that is itself the finding.")
    return 0


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    return value


def _fmt_optional_sci(value):
    return "n/a" if value is None else f"{float(value):.2e}"


def _fmt_optional_nmae(value):
    return "n/a" if value is None else f"{float(value):.3e}"


def _reference_payload(ref):
    return {name: torch.from_numpy(np.ascontiguousarray(getattr(ref, name)))
            for name in ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz")}


def _restore_reference(ref, payload):
    for name, value in payload.items():
        setattr(ref, name, value.detach().cpu().numpy().copy())


def _checkpoint_payload(solver, ref, *, requested_steps, source_index):
    payload = solver.state_payload()
    payload.update({
        "checkpoint_schema": "pidon-formal-checkpoint-v4",
        "checkpoint_role": "formal_solver_and_reference",
        "requested_steps": requested_steps,
        "source_index": source_index,
        "reference": _reference_payload(ref),
    })
    return payload


def _step_summary(solver, ref, step_record):
    base = {
        "step": step_record.time_layer,
        "accepted_steps": solver.accepted_steps,
        "phase": step_record.phase,
        "accepted": step_record.accepted,
        "reason": step_record.reason,
        "fit_H": step_record.fit_H.as_dict() if step_record.fit_H else None,
        "fit_E": step_record.fit_E.as_dict() if step_record.fit_E else None,
        "recovery_eligible": bool(getattr(solver, "fit_progress", {}).get(
            "H" if step_record.phase == "before_H" else "E", {}).get("resumable", False)),
    }
    if not step_record.accepted:
        # No full Maxwell time layer exists.  A field/reference comparison
        # here would pair an H or E half transaction with the next complete
        # reference layer, so it is diagnostic only and cannot be scored.
        base.update({"accepted_field_metrics": None, "six_component_metrics": None,
                     "source_probe_Ez": None, "source_outside_probes": None})
        return base
    dxyz = (solver.cav.dx, solver.cav.dy, solver.cav.dz)
    reference_E = [to_t(getattr(ref, name), solver.dev) for name in ("Ex", "Ey", "Ez")]
    reference_H = [to_t(getattr(ref, name), solver.dev) for name in ("Hx", "Hy", "Hz")]
    c = solver.n // 2
    metrics = six_component_metrics(solver.E, solver.H, reference_E, reference_H, dxyz,
                                   source_ez_index=(c, c, c))
    probes = []
    for cells in SOURCE_OUTSIDE_PROBES_CELLS:
        xyz = tuple(q * d for q, d in zip(cells, dxyz))
        probes.append({
            "cells": cells,
            "xyz_m": xyz,
            "dut_Ez": trilinear_sample(solver.E[2], xyz, dxyz, (0.0, 0.0, 0.5)),
            "ref_Ez": trilinear_sample(reference_E[2], xyz, dxyz, (0.0, 0.0, 0.5)),
        })
    base.update({
        "accepted_field_metrics": metrics,
        "six_component_metrics": metrics,
        "source_probe_Ez": {"dut": float(solver.E[2][c, c, c]), "ref": float(ref.Ez[c, c, c])},
        "source_outside_probes": probes,
    })
    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="", help="frozen JSON configuration required for formal/resumed runs")
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--n", type=int, default=31,
                    help="当前重建采用的网格间隔数；31 间隔是与论文 dt 一致的假设，"
                         "不是作者已确认的实现细节。")
    ap.add_argument("--side", type=float, default=50e-3)
    ap.add_argument("--dt", type=float, default=3.075e-12,
                    help="论文 IV-A 的值。配合 --n 31 时它就等于 0.99xCFL；"
                         "传 0 则直接用 0.99xCFL（两者一致）。")
    ap.add_argument("--init", default="dco_paper32.pt",
                    help="pretrained checkpoint, or 'random' for the Fig 8 "
                         "control")
    ap.add_argument("--tol", type=float, default=1e-4,
                    help="paper IV-A: stop the inner training below this")
    ap.add_argument("--tol-mode", choices=["rel", "abs"], default="rel",
                    help="rel = |pred-yee|^2 / |yee|^2 (scale free, default); "
                         "abs = eq.(7)'s literal sum of squares")
    ap.add_argument("--max-inner", type=int, default=50)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--head-lstsq-once", action="store_true",
                    help="registered variant: one direct-head CPU least-squares commit before Adam")
    ap.add_argument("--head-rcond", type=float, default=1e-12,
                    help="frozen rcond for --head-lstsq-once; only 1e-12 is registered")
    ap.add_argument("--levels", type=int, default=4)
    ap.add_argument("--base", type=int, default=32)
    ap.add_argument("--coords", default="cellsize")
    ap.add_argument("--norm", default="rms")
    ap.add_argument("--separate-nets", action="store_true",
                    help="use independent DCO/Adam states for curl-H and curl-E")
    ap.add_argument("--reset-opt-each-step", action="store_true",
                    help="reset Adam moments at each physical time step")
    ap.add_argument("--grad-clip", type=float, default=0.0,
                    help="clip inner-training gradient norm; 0 disables")
    ap.add_argument("--h-scale", type=float, default=1.0,
                    help="multiply H before DCO normalisation (use Z0≈376.7)")
    ap.add_argument("--component-rel", action="store_true",
                    help="average relative curl loss per component")
    ap.add_argument("--h-output-scale", type=float, default=1.0,
                    help="scale H curl output in network units (physical result unchanged)")
    ap.add_argument("--h-shift", action="store_true",
                    help="align H input components to interior Yee E locations")
    ap.add_argument("--strict-stop", action="store_true", default=True,
                    help="formal mode: a finite fit that misses tol may not advance its physical substep")
    ap.add_argument("--no-strict-stop", action="store_false", dest="strict_stop",
                    help="exploratory only; its output cannot enter G2/G3")
    ap.add_argument("--inner-time-budget-s", type=float, default=0.0,
                    help="per-inner-fit budget; 0 means only --max-inner limits it")
    ap.add_argument("--lbfgs-closures", type=int, default=0,
                    help="registered diagnostic-only closure cap; formal candidates normally use 0")
    ap.add_argument("--lbfgs-lr", type=float, default=1.0)
    ap.add_argument("--lbfgs-history", type=int, default=10)
    ap.add_argument("--lbfgs-time-budget-s", type=float, default=0.0)
    ap.add_argument("--source-mode", choices=["hard"], default="hard",
                    help="the registered cavity source is assigned after E update")
    ap.add_argument("--torch-dtype", choices=["float32", "float64"], default="float32",
                    help="frozen tensor precision for the registered run")
    ap.add_argument("--out-dir", default="",
                    help="formal run directory for JSONL, atomic checkpoints and field snapshots")
    ap.add_argument("--resume", default="",
                    help="resume a checkpoint; --steps is the target total accepted-step count")
    ap.add_argument("--checkpoint-every", type=int, default=64)
    ap.add_argument("--seed", type=int, default=20260913)
    ap.add_argument("--device", default="", choices=["", "cpu", "cuda"])
    ap.add_argument("--fmax", type=float, default=15e9)
    ap.add_argument("--calib", type=float, nargs="+", default=[],
                    help="sweep these inner learning rates instead of doing a "
                         "full run, and report whether the tolerance is ever "
                         "reached")
    ap.add_argument("--calib-iters", type=int, nargs="+", default=[],
                    help="sweep these --max-inner values too; the cross "
                         "product with --calib is run")
    ap.add_argument("--out", default="")
    raw_argv = sys.argv[1:]
    a = ap.parse_args(raw_argv)
    if a.config:
        with open(a.config, encoding="utf-8") as handle:
            loaded_config = json.load(handle)
        loaded_config = loaded_config.get("config", loaded_config)
        apply_frozen_config(a, loaded_config, explicit_cli_destinations(ap, raw_argv))
    if a.dt == 0:
        a.dt = None
    if a.calib:
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[pidon_solve.py  version {SCRIPT_VERSION}]  calibration\n")
        raise SystemExit(calibrate(a, dev))

    random_seed = a.seed
    torch.manual_seed(random_seed)
    np.random.seed(random_seed)
    dev = a.device or ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[pidon_solve.py  version {SCRIPT_VERSION}]  Algorithm 1")
    resume_payload = None
    if a.resume:
        if not a.config:
            raise ValueError("formal resume requires --config so dynamics cannot silently change")
        if not a.out_dir:
            raise ValueError("formal resume requires --out-dir for recorder identity verification")
        resume_payload = torch.load(a.resume, map_location="cpu", weights_only=False)
        checkpoint_required = {"checkpoint_schema", "checkpoint_role", "source_index", "reference"}
        absent = sorted(checkpoint_required - set(resume_payload))
        if absent:
            raise ValueError("formal checkpoint lacks required fields: " + ", ".join(absent))
        if (resume_payload.get("checkpoint_schema") != "pidon-formal-checkpoint-v4"
                or resume_payload.get("checkpoint_role") != "formal_solver_and_reference"):
            raise ValueError("formal checkpoint has incompatible schema or role")
        if "frozen_config" not in resume_payload:
            raise ValueError("checkpoint predates v2 frozen configuration and may not be resumed formally")
        assert_resume_compatible(a, resume_payload["frozen_config"])
    s = Solver(a, dev)
    print(f"  cavity {a.side * 1e3:.1f} mm / {a.n} cells  dx = "
          f"{s.cav.dx * 1e3:.4f} mm   dt = {s.dt * 1e12:.4f} ps")
    cfl = fdtd.cfl_dt(s.cav.dx, s.cav.dy, s.cav.dz, safety=1.0)
    print(f"  CFL limit {cfl * 1e12:.4f} ps  ->  dt / CFL = {s.dt / cfl:.4f}"
          + ("   *** 超出 Courant 限，连参考 FDTD 都会发散，"
             "腔体请用 --n 31" if s.dt > cfl else "   ok"))
    print(f"  init = {s.tag}   coords={s.coord_mode} norm={s.norm_mode}   "
          f"{sum(p.numel() for p in s.net.parameters()) / 1e6:.2f}M params")
    print(f"  inner training: stop below {a.tol:.0e}, at most {a.max_inner} "
          f"iters, lr {a.lr:g}   device {dev}\n")

    ref = fdtd.PECCavity(side=a.side, n=a.n, dt=a.dt)
    if resume_payload is not None:
        s.load_state_payload(resume_payload)
        _restore_reference(ref, resume_payload["reference"])
        if a.steps < s.accepted_steps:
            raise ValueError("--steps is a target total and cannot precede accepted_steps in checkpoint")
    g = fdtd.source_waveform(a.steps, s.dt, a.fmax, "gauss")
    c = a.n // 2
    recorder = None
    if a.out_dir:
        existing_run_id = None
        if a.resume:
            metadata_path = Path(a.out_dir) / "run_metadata.json"
            if not metadata_path.is_file():
                raise FileNotFoundError("formal resume lacks recorder metadata")
            existing_run_id = json.loads(metadata_path.read_text(encoding="utf-8")).get("run_id")
            if not existing_run_id:
                raise ValueError("formal resume metadata lacks run_id")
        identity = formal_run_identity(a, run_id=existing_run_id)
        recorder = RunRecorder(a.out_dir, {
            "schema": "pidon-formal-run-v3", "script_version": SCRIPT_VERSION,
            "config": vars(a).copy(), "strict_stop": a.strict_stop, **identity,
        }, mode="resume" if a.resume else "new")
        if resume_payload is not None:
            checkpoint_identity = resume_payload.get("recorder_identity")
            current_identity = {key: identity[key] for key in RunRecorder.IDENTITY_KEYS}
            if checkpoint_identity != current_identity:
                raise ValueError("checkpoint run identity differs from output directory/configuration")
    hist, t0, stop_record = [], time.time(), None
    snapshot_steps = {1, 2, 16, 32, 43, 64, 96, 128, 192, 300, 600, 900, 1024, 2048, 4096, 8192}
    while s.accepted_steps < a.steps:
        t = s.current_time_layer
        rec = s.step(float(g[t]))
        if rec.accepted:
            ref.step_e_source_h(src_value=g[t], src_idx=(c, c, c))
        summary = _json_safe(_step_summary(s, ref, rec))
        if recorder:
            recorder.append(summary)
        if rec.accepted:
            fit_h, fit_e = rec.fit_H, rec.fit_E
            hist.append({"step": rec.time_layer, "nmae": summary["six_component_metrics"]["components"]["Ez"]["nmae"],
                         "lossH": fit_h.loss_final if fit_h else float("nan"),
                         "lossE": fit_e.loss_final if fit_e else float("nan"),
                         "updatesH": fit_h.n_updates if fit_h else 0,
                         "updatesE": fit_e.n_updates if fit_e else 0})
            if recorder and (s.accepted_steps in snapshot_steps):
                recorder.snapshot(s.accepted_steps, _checkpoint_payload(s, ref, requested_steps=a.steps, source_index=t + 1))
            if recorder and s.accepted_steps % max(a.checkpoint_every, 1) == 0:
                recorder.checkpoint(_checkpoint_payload(s, ref, requested_steps=a.steps, source_index=t + 1))
            if s.accepted_steps <= 5 or s.accepted_steps % max(a.steps // 20, 1) == 0:
                print(f"  step {s.accepted_steps:>5d} updates H/E "
                      f"{fit_h.n_updates if fit_h else 0}/{fit_e.n_updates if fit_e else 0}"
                      f" loss {_fmt_optional_sci(fit_h.loss_final if fit_h else None)}/"
                      f"{_fmt_optional_sci(fit_e.loss_final if fit_e else None)}"
                      f" Ez-nMAE {_fmt_optional_nmae(summary['six_component_metrics']['components']['Ez']['nmae'])}"
                      f" {(time.time() - t0) / s.accepted_steps:.2f}s/step")
        else:
            stop_record = summary
            if recorder:
                raw = getattr(s, "last_failure_raw", None)
                if raw is not None:
                    raw["reference"] = _reference_payload(ref)
                    recorder.failure_raw(raw)
                else:
                    recorder.failure_raw(_checkpoint_payload(s, ref, requested_steps=a.steps, source_index=t))
                recorder.checkpoint(_checkpoint_payload(s, ref, requested_steps=a.steps, source_index=t))
            print(f"  stopped before accepting layer {t}: phase={rec.phase}, reason={rec.reason}")
            break

    if hist:
        diagnose(hist, a)
    if recorder:
        recorder.checkpoint(_checkpoint_payload(s, ref, requested_steps=a.steps, source_index=s.current_time_layer))
    out = a.out or (os.path.join(a.out_dir, "legacy_summary.json") if a.out_dir else f"pidon_solve_{s.tag}.json")
    final = {
        "version": SCRIPT_VERSION, "init": s.tag, "n": a.n, "side": a.side,
        "dt": s.dt, "tol": a.tol, "lr": a.lr, "requested_steps": a.steps,
        "accepted_steps": s.accepted_steps, "phase": s.phase, "strict_stop": a.strict_stop,
        "rows": hist, "stop_record": stop_record,
    }
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(_json_safe(final), handle, ensure_ascii=False, indent=2)
    tot = time.time() - t0
    print(f"\n  accepted {s.accepted_steps}/{a.steps} steps in {tot:.0f} s")
    if hist:
        print(f"  mean actual updates: curlH {np.mean([r['updatesH'] for r in hist]):.1f}"
              f"  curlE {np.mean([r['updatesE'] for r in hist]):.1f}")
        print(f"  final Ez nMAE vs FDTD {hist[-1]['nmae']:.3e}")
    print(f"  saved {out}")
    print("\n  Fig 8's y-axis is the 'cum' column -- the loss summed over all"
          "\n  inner epochs at each time step.  Run this again with "
          "--init random\n  to get the control curve.")


if __name__ == "__main__":
    main()
