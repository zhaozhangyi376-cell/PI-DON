"""Read-only CPU counterexamples for the 2026-09-17 code review.

Passing cases confirm the OBSERVED behavior, not that the implementation is
correct. No production model, checkpoint, plan, or experiment is modified.
Run under lab_log. Temporary fixtures are isolated from real evidence.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from project_paths import configure, resolve_legacy
configure()
sys.path.insert(0, str(ROOT / "_01/src"))

import numpy as np
import torch
import fdtd
import pidon_contract as contract
import pidon_recording as recording
import pidon_solve as solve
import server_short_tol_probe as short
import ingest_paper01_theta_full_return as theta_ingest
from paper01.ablation_data import generate_variant_dataset
from paper01.metrics import rel_l2
from paper01.model import component_local_max_normalize

torch.set_num_threads(1)
OBSERVATIONS = {}


def tiny_args():
    return SimpleNamespace(
        n=3, side=0.05, dt=3.075e-12, init="random", coords="cellsize",
        norm="rms", levels=2, base=2, lr=1e-4, separate_nets=True,
        h_scale=1.0, h_output_scale=1.0, h_shift=False, tol_mode="abs",
        component_rel=False, tol=1e-4, max_inner=0, grad_clip=0.0,
        inner_time_budget_s=0.0, strict_stop=True, reset_opt_each_step=False,
    )


class ReviewCounterexamples(unittest.TestCase):
    def test_material_parameter_does_not_change_evolution(self):
        air = fdtd.PECCavity(n=4, eps_r=1.0)
        dielectric = fdtd.PECCavity(n=4, eps_r=4.0)
        for cav in (air, dielectric):
            cav.Hz[:] = np.arange(cav.Hz.shape[1])[None, :, None]
            cav.step_e_source_h()
        equal = all(np.array_equal(getattr(air, n), getattr(dielectric, n))
                    for n in ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz"))
        self.assertTrue(equal)
        OBSERVATIONS["material"] = {"eps_r_1_and_4_identical": equal,
                                    "stored_eps_ratio": float(dielectric.eps.flat[0] / fdtd.EPS0)}

    def test_cfl_violation_is_accepted_by_constructor(self):
        cav = fdtd.PECCavity(n=32, side=0.05, dt=3.075e-12)
        ratio = cav.dt / fdtd.cfl_dt(cav.dx, cav.dy, cav.dz, safety=1.0)
        self.assertGreater(ratio, 1.0)
        OBSERVATIONS["cfl"] = {"n32_dt_over_limit": float(ratio), "raises": False}

    def test_absolute_mode_stops_on_relative_ratio(self):
        args = tiny_args()
        solver = solve.Solver(args, "cpu")
        field = [torch.ones_like(v) for v in solver.H]
        target = [torch.full((3, 3, 3), 1e-5) for _ in range(3)]
        prediction = torch.zeros((3, 3, 3, 3))
        with patch.object(solver, "predict", return_value=prediction):
            fit = solver.inner_train(field, target, "H")
        self.assertLess(fit.loss_final, args.tol)
        self.assertEqual(fit.residual_ratio, 1.0)
        self.assertFalse(fit.passed)
        OBSERVATIONS["absolute_mode"] = {
            "absolute_loss": fit.loss_final, "tol": args.tol,
            "relative_residual": fit.residual_ratio, "passed": fit.passed,
            "parameter_updates": fit.n_updates,
        }

    def test_field_gate_passes_without_any_components_or_probes(self):
        gate = short.field_gate({"six_component_metrics": {
            "global_weighted_relative_l2": 0.0, "fixed_amplitude_error": 0.0}})
        self.assertTrue(gate["pass"])
        self.assertEqual(gate["components"], {})
        self.assertIsNone(gate["source_outside_probes"])
        OBSERVATIONS["missing_field_evidence"] = gate

    def test_field_gate_ignores_wrong_probe(self):
        row = {"six_component_metrics": {
            "components": {n: {"nmae": 0.0, "weak_reference": False}
                           for n in ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz")},
            "global_weighted_relative_l2": 0.0, "fixed_amplitude_error": 0.0},
            "source_outside_probes": [{"dut_Ez": 1000., "ref_Ez": 1.}],
            "accepted": True}
        gate = short.field_gate(row)
        self.assertTrue(gate["pass"])
        OBSERVATIONS["probe_gate"] = {"pass": gate["pass"], "dut": 1000., "ref": 1.}

    def test_theta_ingest_passes_summary_without_raw_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "summary.json"
            path.write_text(json.dumps({"status": "PASS", "variants": [{}]}), encoding="utf-8")
            data = theta_ingest.review(path, root)
            self.assertEqual(data["status"], "PASS")
            self.assertIsNone(data["parameter_updates"])
            self.assertIsNone(data["macro_nmae_mean"])
            OBSERVATIONS["theta_ingest"] = {"status": data["status"],
                                            "files_present": [p.name for p in root.iterdir()],
                                            "updates": data["parameter_updates"]}

    def test_rollover_after_metadata_crash_can_destroy_pointed_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata = {"run_id": "review-only", "protocol_hash": "review-only"}
            recorder = recording.RunRecorder(directory, metadata)
            recorder.append({"step": 0})
            recorder.rolling_checkpoint({"value": 1})
            recorder.append({"step": 1})
            original = recording.atomic_json_save

            def fail_metadata(value, destination):
                if Path(destination).name == "run_metadata.json":
                    raise OSError("simulated metadata crash after pointer commit")
                return original(value, destination)

            with patch.object(recording, "atomic_json_save", side_effect=fail_metadata):
                with self.assertRaises(OSError):
                    recorder.rolling_checkpoint({"value": 2})
            resumed = recording.RunRecorder(directory, metadata, mode="resume")
            self.assertEqual(resumed.load_rolling_checkpoint()["value"], 2)
            with patch.object(recording, "atomic_json_save", side_effect=OSError("pointer crash")):
                with self.assertRaises(OSError):
                    resumed.rolling_checkpoint({"value": 3})
            with self.assertRaisesRegex(ValueError, "hash differs"):
                resumed.load_rolling_checkpoint()
            OBSERVATIONS["rolling_crash"] = {
                "first_resume_loaded_value": 2,
                "second_write_overwrote_pointed_slot": True,
                "second_resume_error": "rolling checkpoint hash differs from pointer",
            }

    def test_physical_mre_name_contains_scaled_zero_branch(self):
        ref = torch.zeros((2, 2, 2), dtype=torch.float64)
        pred = torch.full_like(ref, contract.H0)
        metric = contract.component_metric(pred, ref, scale=contract.H0,
                    dxyz=(1., 1., 1.), offsets=(0., .5, .5))
        self.assertAlmostEqual(metric["mre_eq5_physical"], 1.)
        OBSERVATIONS["mre_units"] = {
            "physical_absolute_error_A_per_m": contract.H0,
            "reported_mre_eq5_physical": metric["mre_eq5_physical"],
        }

    def test_component_scaling_changes_vector_rel_l2(self):
        target = torch.tensor([100., 1., 1.]).reshape(1, 3, 1, 1, 1)
        prediction = torch.tensor([100., 2., 1.]).reshape(1, 3, 1, 1, 1)
        normalized, scale = component_local_max_normalize(target)
        raw = rel_l2(prediction.numpy(), target.numpy())
        normalized_error = rel_l2((prediction / scale).numpy(), normalized.numpy())
        self.assertGreater(normalized_error, 50 * raw)
        OBSERVATIONS["rel_l2_units"] = {"physical": raw, "component_normalized": normalized_error}

    def test_theta_variant_also_changes_test_distribution(self):
        values = {}
        for index, variant in enumerate(("baseline", "theta_min_0p5")):
            fields, _, _, specs = generate_variant_dataset(100, (2, 2, 2),
                                                           2026091702 + index * 1000, variant)
            test_specs = specs[80:]
            count = int(sum(abs(np.cos(s["theta"])) < .5 for s in test_specs))
            values[variant] = {"test_size": len(test_specs), "test_abs_cos_below_0p5": count,
                               "field_sha256": hashlib.sha256(fields.tobytes()).hexdigest(),
                               "seed": 2026091702 + index * 1000}
        self.assertGreater(values["baseline"]["test_abs_cos_below_0p5"], 0)
        self.assertEqual(values["theta_min_0p5"]["test_abs_cos_below_0p5"], 0)
        OBSERVATIONS["ablation_confounding"] = values

    def test_legacy_resolution_discards_explicit_external_model_identity(self):
        external = Path("Z:/independent_study/dco_lr1e3_300.pt")
        mapped = resolve_legacy(external)
        self.assertEqual(mapped, ROOT / "assets/models/dco_lr1e3_300.pt")
        OBSERVATIONS["path_alias"] = {"requested": str(external), "resolved": str(mapped)}

    def test_yee_curls_match_independent_linear_field_derivatives(self):
        n = 5
        d = (.2, .3, .4)
        matrix = np.array([[1., 2., 3.], [4., 5., 6.], [7., 8., 9.]])
        expected = np.array([2., -4., 2.])
        cav = fdtd.PECCavity(n=n)
        errors = {}
        for kind, operator in (("E", fdtd.curl_E), ("H", fdtd.curl_H)):
            fields = []
            for i, component in enumerate("xyz"):
                name = kind + component
                shape = getattr(cav, name).shape
                offsets = contract.component_offsets(name)
                axes = [(np.arange(shape[j]) + offsets[j]) * d[j] for j in range(3)]
                xyz = np.meshgrid(*axes, indexing="ij")
                fields.append(sum(matrix[i, j] * xyz[j] for j in range(3)))
            result = operator(*fields, *d)
            errors[kind] = max(float(np.max(np.abs(a - b))) for a, b in zip(result, expected))
            self.assertLess(errors[kind], 1e-12)
        OBSERVATIONS["independent_linear_curl"] = errors


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReviewCounterexamples)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    target = Path(__file__).with_name("counterexamples.json")
    if target.exists():
        raise FileExistsError(target)
    target.write_text(json.dumps({"review_only": True, "production_parameter_updates": 0,
                                 "tests": result.testsRun, "errors": len(result.errors),
                                 "failures": len(result.failures), "observations": OBSERVATIONS},
                                indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
