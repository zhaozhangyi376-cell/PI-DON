"""Negative tests for the 20260917 code-review fixes.

Each test reproduces the counterexample the review recorded and asserts the
fixed behaviour.  They are negative tests on purpose: the review's finding was
almost always "this check accepts something it should reject", so a test that
only exercises the happy path would have passed before the fix too.

Nothing here writes to the evidence tree, trains a production model, or
re-judges a historical result.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

from project_paths import PROJECT_DIR, configure, resolve_legacy

configure()

import fdtd
import pidon_contract as C
import pidon_solve as S
from pidon_recording import RunRecorder, atomic_json_save, sha256_file, source_hash_gaps, source_hashes


def load_module(relative: str, name: str):
    """Import a script by path without giving it an importable package name."""
    path = PROJECT_DIR / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MaterialSupportTests(unittest.TestCase):
    """F01: eps_r was accepted and then ignored."""

    def test_uniform_dielectric_changes_the_trajectory(self):
        dt = 4.0e-12
        vacuum = fdtd.PECCavity(n=6, side=0.05, dt=dt)
        dielectric = fdtd.PECCavity(n=6, side=0.05, dt=dt, eps_r=4.0)
        for _ in range(8):
            for cavity in (vacuum, dielectric):
                cavity.step_e_source_h(src_value=1.0, src_idx=(3, 3, 3))
        self.assertFalse(np.allclose(vacuum.Ez, dielectric.Ez),
                         "eps_r=1 and eps_r=4 must not produce identical fields")

    def test_vacuum_path_is_bit_identical_to_the_scalar_coefficient(self):
        cavity = fdtd.PECCavity(n=5, side=0.05, dt=3e-12)
        for coefficient in cavity.e_coefficients():
            self.assertTrue(np.isscalar(coefficient))
            self.assertEqual(coefficient, 3e-12 / fdtd.EPS0)
        self.assertTrue(cavity.is_vacuum())

    def test_uniform_medium_slows_the_wave_by_sqrt_eps_r(self):
        # A uniform medium must slow propagation by 1/sqrt(eps_r).  Measure the
        # first arrival of a pulse at a fixed distance in both cavities.
        def first_arrival(eps_r):
            n, side = 24, 0.05
            dt = 0.4 * (side / n) / fdtd.C0
            cavity = fdtd.PECCavity(n=n, side=side, dt=dt, eps_r=eps_r)
            probe = (12, 12, 20)
            for step in range(400):
                cavity.step_e_source_h(src_value=(1.0 if step < 3 else 0.0), src_idx=(12, 12, 12))
                if abs(cavity.Ez[probe]) > 1e-4:
                    return step
            return None
        vacuum_step = first_arrival(None)
        dielectric_step = first_arrival(4.0)
        self.assertIsNotNone(vacuum_step)
        self.assertIsNotNone(dielectric_step)
        ratio = dielectric_step / vacuum_step
        self.assertGreater(ratio, 1.5, f"eps_r=4 must roughly halve the speed; ratio={ratio}")
        self.assertLess(ratio, 2.6, f"eps_r=4 must roughly halve the speed; ratio={ratio}")

    def test_material_interface_is_sampled_on_each_staggered_support(self):
        cavity = fdtd.PECCavity(n=6, side=0.06, dt=3e-12,
                                eps_r=lambda x, y, z: np.where(z < 0.03, 1.0, 4.0))
        self.assertEqual(cavity.material["kind"], "inhomogeneous")
        # Each E component owns an array of its OWN shape: one node array
        # cannot serve three differently staggered supports.
        self.assertEqual(cavity.eps_x.shape, cavity.Ex.shape)
        self.assertEqual(cavity.eps_y.shape, cavity.Ey.shape)
        self.assertEqual(cavity.eps_z.shape, cavity.Ez.shape)
        self.assertAlmostEqual(float(cavity.eps_x.min()), fdtd.EPS0)
        self.assertAlmostEqual(float(cavity.eps_x.max()), 4.0 * fdtd.EPS0)

    def test_bare_array_and_invalid_permittivity_are_refused(self):
        with self.assertRaises(TypeError):
            fdtd.PECCavity(n=4, eps_r=np.ones((5, 5, 5)))
        with self.assertRaises(ValueError):
            fdtd.PECCavity(n=4, eps_r=0.0)
        with self.assertRaises(ValueError):
            fdtd.PECCavity(n=4, eps_r=float("nan"))


class CourantLimitTests(unittest.TestCase):
    """F12: a super-Courant reference used to be a warning, not a refusal."""

    def test_super_courant_reference_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            fdtd.PECCavity(n=32, side=0.05, dt=3.075e-12)
        self.assertIn("Courant", str(caught.exception))

    def test_registered_n31_configuration_still_constructs(self):
        cavity = fdtd.PECCavity(n=31, side=0.05, dt=3.075e-12)
        self.assertFalse(cavity.super_cfl)
        self.assertLess(cavity.dt / cavity.cfl_limit, 1.0)

    def test_labelled_diagnostic_entry_may_opt_in(self):
        cavity = fdtd.PECCavity(n=32, side=0.05, dt=3.075e-12, allow_super_cfl=True)
        self.assertTrue(cavity.super_cfl)
        self.assertTrue(cavity.allow_super_cfl)


class MetricContractTests(unittest.TestCase):
    """F08 and the interpolation boundary."""

    def test_eq5_zero_branch_is_reported_in_physical_units(self):
        reference = torch.zeros(2, 2, 2)
        prediction = torch.full((2, 2, 2), 0.002654)
        metric = C.component_metric(prediction, reference, scale=1.0,
                                    dxyz=(1.0, 1.0, 1.0), offsets=(0.0, 0.0, 0.0))
        self.assertAlmostEqual(metric["mre_eq5_physical"], 0.002654, places=9)
        metric_scaled = C.component_metric(prediction, reference, scale=0.002654,
                                           dxyz=(1.0, 1.0, 1.0), offsets=(0.0, 0.0, 0.0))
        # The normalised reading is the historical 1.0; the physical one keeps
        # its units and is no longer published under the physical name.
        self.assertAlmostEqual(metric_scaled["mre_eq5_normalized"], 1.0, places=6)
        self.assertAlmostEqual(metric_scaled["mre_eq5_physical"], 0.002654, places=9)
        self.assertEqual(metric_scaled["mre_eq5_zero_branch_units"], "physical")

    def test_highest_legal_node_is_inside_the_support(self):
        values = torch.arange(27.0).reshape(3, 3, 3)
        sampled = C.trilinear_sample(values, (2.0, 1.0, 1.0), (1.0, 1.0, 1.0), (0.0, 0.0, 0.0))
        self.assertAlmostEqual(sampled, 22.0)

    def test_a_point_outside_the_support_is_still_refused(self):
        values = torch.arange(27.0).reshape(3, 3, 3)
        with self.assertRaises(ValueError):
            C.trilinear_sample(values, (3.0, 1.0, 1.0), (1.0, 1.0, 1.0), (0.0, 0.0, 0.0))
        with self.assertRaises(ValueError):
            C.trilinear_sample(values, (-0.5, 1.0, 1.0), (1.0, 1.0, 1.0), (0.0, 0.0, 0.0))


class LegacyPathTests(unittest.TestCase):
    """F07: an external absolute path was reduced to its basename."""

    def test_external_absolute_path_is_not_remapped_by_basename(self):
        migrated = json.loads((PROJECT_DIR / "project/migration_map.json").read_text(encoding="utf-8"))
        name = migrated["files"][0]["old"]
        self.assertEqual(os.fspath(resolve_legacy(name)),
                         os.fspath(PROJECT_DIR / migrated["files"][0]["new"]))
        foreign = Path(tempfile.gettempdir()).resolve() / "independent_study" / name
        self.assertEqual(os.fspath(resolve_legacy(foreign)), os.fspath(foreign))


class SolverContractTests(unittest.TestCase):
    """F05, F18 and the source-outside probe geometry."""

    def test_module_binds_a_bare_Path_name(self):
        # F18: the resume branch used ``Path`` while only ``_LayoutPath`` was
        # imported, so --resume raised NameError before reading its metadata.
        self.assertIs(S.Path, Path)

    def test_absolute_tolerance_mode_stops_on_the_absolute_residual(self):
        source = (PROJECT_DIR / "src/pidon/pidon_solve.py").read_text(encoding="utf-8")
        self.assertIn('if self.a.tol_mode == "abs":', source)
        marker = source.index("def stop_met(")
        window = source[marker:marker + 2000]
        self.assertIn("reached(float(physical_sse.detach()), self.a.tol)", window)

    def test_registered_probes_are_validated_before_the_run(self):
        self.assertTrue(hasattr(S, "validate_source_outside_probes"))

        class Tiny:
            n = 4
            dev = "cpu"
            E = [torch.zeros(4, 5, 5), torch.zeros(5, 4, 5), torch.zeros(5, 5, 4)]

            class cav:
                dx = dy = dz = 1e-3
        with self.assertRaises(ValueError) as caught:
            S.validate_source_outside_probes(Tiny())
        self.assertIn("probe", str(caught.exception).lower())


class SourceHashTests(unittest.TestCase):
    """The five-name freeze was not the dependency closure."""

    def test_declared_closure_covers_the_imported_solver_modules(self):
        for name in ("head_lstsq.py", "paper_protocol.py"):
            self.assertIn(name, source_hashes.__defaults__[0])
        hashes = source_hashes(PROJECT_DIR / "src/pidon")
        self.assertEqual(source_hash_gaps(hashes), [],
                         "every declared solver dependency must be hashable")

    def test_an_unhashable_dependency_is_reported_as_a_gap(self):
        self.assertEqual(source_hash_gaps({"a.py": "x", "b.py": None}), ["b.py"])


class RollingCheckpointTests(unittest.TestCase):
    """F06: the A/B pointer and the metadata mirror could disagree."""

    def _recorder(self, directory, run_id="run-1"):
        return RunRecorder(directory, {"run_id": run_id, "protocol_hash": "hash-1"}, mode="new")

    def test_the_committed_pointer_decides_the_next_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            recorder = self._recorder(out)
            recorder.append({"step": 0, "accepted": True, "accepted_steps": 1})
            first = recorder.rolling_checkpoint({"payload": 1})
            self.assertEqual(first.name, "checkpoint_A.pt")
            # Simulate the crash window: the pointer is committed but the
            # metadata mirror still names the previous slot.
            recorder.append({"step": 1, "accepted": True, "accepted_steps": 2})
            recorder.rolling_checkpoint({"payload": 2})
            metadata = json.loads((out / "run_metadata.json").read_text(encoding="utf-8"))
            metadata["active_checkpoint_slot"] = "A"
            atomic_json_save(metadata, out / "run_metadata.json")
            reopened = RunRecorder(out, {"run_id": "run-1", "protocol_hash": "hash-1"}, mode="resume")
            pointer = json.loads((out / "checkpoint_pointer.json").read_text(encoding="utf-8"))
            self.assertEqual(pointer["slot"], "B")
            recorder2_path = reopened.rolling_checkpoint({"payload": 3})
            self.assertEqual(recorder2_path.name, "checkpoint_A.pt",
                             "the slot named by the committed pointer must not be overwritten")
            # The recovery point we would have resumed from is still loadable.
            self.assertTrue((out / "checkpoint_B.pt").is_file())

    def test_durable_rows_are_readable_for_resume_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            recorder = self._recorder(out, run_id="run-2")
            recorder.append({"step": 0, "accepted": True, "accepted_steps": 1})
            recorder.append({"step": 1, "accepted": True, "accepted_steps": 2})
            rows = recorder.durable_rows()
            self.assertEqual([row["sequence_id"] for row in rows], [0, 1])


class ResumeContinuityTests(unittest.TestCase):
    """F19: an old snapshot could replay already recorded physical layers."""

    class _FakeSolver:
        def __init__(self, accepted_steps, time_layer, phase="before_H"):
            self.accepted_steps = accepted_steps
            self.current_time_layer = time_layer
            self.phase = phase

    def _prepared(self, tmp, rows):
        out = Path(tmp) / "run"
        recorder = RunRecorder(out, {"run_id": "r", "protocol_hash": "p"}, mode="new")
        for row in rows:
            recorder.append(row)
        recorder.metadata["last_checkpoint_sequence_id"] = len(rows) - 1
        recorder.metadata["recovery_tail_sequence_ids"] = []
        atomic_json_save(recorder.metadata, recorder.metadata_path)
        return recorder

    def test_a_stale_checkpoint_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = self._prepared(tmp, [
                {"step": 0, "accepted": True, "accepted_steps": 1, "phase": "before_H"},
                {"step": 1, "accepted": True, "accepted_steps": 2, "phase": "before_H"},
            ])
            payload = {"last_committed_sequence_id": 0, "source_index": 1}
            with self.assertRaises(ValueError) as caught:
                S.assert_checkpoint_continues_log(recorder, payload,
                                                  self._FakeSolver(1, 1), 128)
            self.assertIn("already recorded", str(caught.exception))

    def test_a_checkpoint_at_the_log_tail_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = self._prepared(tmp, [
                {"step": 0, "accepted": True, "accepted_steps": 1, "phase": "before_H"},
                {"step": 1, "accepted": True, "accepted_steps": 2, "phase": "before_H"},
            ])
            payload = {"last_committed_sequence_id": 1, "source_index": 2}
            report = S.assert_checkpoint_continues_log(recorder, payload,
                                                      self._FakeSolver(2, 2), 128)
            self.assertEqual(report["resumed_accepted_steps"], 2)

    def test_a_checkpoint_that_disagrees_with_the_log_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = self._prepared(tmp, [
                {"step": 0, "accepted": True, "accepted_steps": 1, "phase": "before_H"},
            ])
            payload = {"last_committed_sequence_id": 0, "source_index": 5}
            with self.assertRaises(ValueError):
                S.assert_checkpoint_continues_log(recorder, payload,
                                                  self._FakeSolver(1, 5), 128)


class FieldGateTests(unittest.TestCase):
    """F02: the field gate passed on an incomplete record."""

    @classmethod
    def setUpClass(cls):
        cls.probe = load_module("scripts/experiments/server_short_tol_probe.py", "short_tol_probe_under_test")

    def _row(self, components, probes=None, q=0.01, fixed=1e-9, accepted_steps=1):
        return {
            "accepted": True,
            "accepted_steps": accepted_steps,
            "six_component_metrics": {
                "components": components,
                "global_weighted_relative_l2": q,
                "fixed_amplitude_error": fixed,
            },
            "source_outside_probes": probes if probes is not None else [
                {"cells": (12.0, 12.0, 13.0), "dut_Ez": 1.0, "ref_Ez": 1.0},
                {"cells": (8.0, 10.0, 12.0), "dut_Ez": 0.5, "ref_Ez": 0.5},
            ],
        }

    def _good_components(self):
        return {name: {"nmae": 0.001, "weak_reference": False}
                for name in ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz")}

    def test_empty_component_table_is_incomplete_not_pass(self):
        gate = self.probe.field_gate(self._row({}))
        self.assertFalse(gate["pass"])
        self.assertEqual(gate["status"], "INCOMPLETE")
        self.assertEqual(len(gate["missing_components"]), 6)

    def test_a_missing_component_is_incomplete(self):
        components = self._good_components()
        del components["Hz"]
        gate = self.probe.field_gate(self._row(components))
        self.assertEqual(gate["status"], "INCOMPLETE")
        self.assertEqual(gate["missing_components"], ["Hz"])

    def test_a_non_finite_component_never_passes(self):
        components = self._good_components()
        components["Ey"]["nmae"] = float("nan")
        gate = self.probe.field_gate(self._row(components))
        self.assertEqual(gate["status"], "FAIL")
        self.assertFalse(gate["components"]["Ey"]["pass"])

    def test_source_outside_probes_take_part_in_the_verdict(self):
        good = self.probe.field_gate(self._row(self._good_components()))
        self.assertEqual(good["status"], "PASS")
        bad = self.probe.field_gate(self._row(self._good_components(), probes=[
            {"cells": (12.0, 12.0, 13.0), "dut_Ez": 5.0, "ref_Ez": 1.0},
            {"cells": (8.0, 10.0, 12.0), "dut_Ez": 0.5, "ref_Ez": 0.5},
        ]))
        self.assertEqual(bad["status"], "FAIL")
        self.assertFalse(bad["source_outside_probe_check"]["pass"])
        absent = self.probe.field_gate(self._row(self._good_components(), probes=[]))
        self.assertEqual(absent["status"], "INCOMPLETE")

    def test_the_window_gate_sees_a_mid_window_failure_the_endpoint_hides(self):
        rows = []
        for step in range(1, 5):
            components = self._good_components()
            if step == 2:
                components["Ex"]["nmae"] = 0.4
            rows.append(self._row(components, accepted_steps=step))
        endpoint = self.probe.field_gate(rows[-1])
        self.assertEqual(endpoint["status"], "PASS")
        window = self.probe.window_field_gate(rows, 4)
        self.assertEqual(window["status"], "FAIL")
        self.assertEqual(window["first_failing_component_step"]["Ex"]["step"], 2)

    def test_the_window_gate_reports_gaps_as_incomplete(self):
        rows = [self._row(self._good_components(), accepted_steps=step) for step in (1, 2, 4)]
        window = self.probe.window_field_gate(rows, 4)
        self.assertEqual(window["status"], "INCOMPLETE")
        self.assertEqual(window["reason"], "window_has_gaps")


class M2AuditTests(unittest.TestCase):
    """F02 (supplement) and F22 in the M2 audit generator."""

    @classmethod
    def setUpClass(cls):
        cls.audit = load_module("scripts/analysis/direct_m2_audit.py", "direct_m2_audit_under_test")

    def test_missing_summary_with_evidence_is_incomplete_not_not_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "A_P"
            run_dir.mkdir()
            (run_dir / "steps.jsonl").write_text("{}\n", encoding="utf-8")
            state = self.audit.missing_summary_state(run_dir)
            self.assertEqual(state["status"], "INCOMPLETE")
            self.assertIn("steps.jsonl", state["evidence_present"])

    def test_an_absent_run_directory_is_not_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self.audit.missing_summary_state(Path(tmp) / "never")
            self.assertEqual(state["status"], "NOT_RUN")

    def test_interpretation_is_derived_not_hard_coded(self):
        source = (PROJECT_DIR / "scripts/analysis/direct_m2_audit.py").read_text(encoding="utf-8")
        self.assertNotIn("A-R failed at 33 accepted steps", source)


class BenefitVerdictTests(unittest.TestCase):
    """F27: the benefit boolean contradicted the other fields."""

    def test_the_layers_are_named_in_the_source(self):
        source = (PROJECT_DIR / "scripts/experiments/direct_benefit_runner.py").read_text(encoding="utf-8")
        for key in ("residual_window_comparable", "all_field_gates_pass", "cost_saving_pass"):
            self.assertIn(key, source)
        self.assertIn('"benefit_status"', source)


class StopClassificationTests(unittest.TestCase):
    """F25: a save exception was outranked by the accepted-step count."""

    @classmethod
    def setUpClass(cls):
        cls.runner = load_module("scripts/experiments/direct_m2_runner.py", "direct_m2_runner_under_test")

    def test_a_checkpoint_exception_is_not_a_pass(self):
        self.assertEqual(self.runner.classify_stop({"reason": "EXCEPTION"}, 128, 128), "EXCEPTION")

    def test_a_clean_target_is_still_a_pass(self):
        self.assertEqual(self.runner.classify_stop(None, 128, 128), "PASS")

    def test_reaching_the_target_with_any_other_stop_is_incomplete(self):
        self.assertEqual(self.runner.classify_stop({"reason": "FIT_FAIL"}, 128, 128), "INCOMPLETE")


class CostAccountingTests(unittest.TestCase):
    """F23 and F26: resumed cost was doubled, unknown cost was zero."""

    @classmethod
    def setUpClass(cls):
        cls.m0 = load_module("scripts/experiments/direct_mechanism_runner.py", "direct_mechanism_runner_under_test")

    def test_a_resumed_half_step_is_counted_once(self):
        interrupted = [{"step": 0, "accepted": False, "fit_H": {"n_updates": 1, "n_closures": 0}}]
        resumed = [{"step": 0, "accepted": True,
                    "fit_H": {"n_updates": 2, "n_closures": 0},
                    "fit_E": {"n_updates": 0, "n_closures": 0}}]
        budget = self.m0.budget_from_rows(interrupted + resumed)
        self.assertEqual(budget["adam"], 2)
        self.assertEqual(budget["adam_row_sum"], 3)
        self.assertEqual(budget["resume_double_counted_adam"], 1)

    def test_independent_half_steps_still_add_up(self):
        rows = [{"step": 0, "accepted": True,
                 "fit_H": {"n_updates": 2, "n_closures": 0},
                 "fit_E": {"n_updates": 3, "n_closures": 0}}]
        self.assertEqual(self.m0.budget_from_rows(rows)["adam"], 5)


class M1AssociationTests(unittest.TestCase):
    """F30: a case's reading was written onto another case's id."""

    @classmethod
    def setUpClass(cls):
        cls.m1 = load_module("scripts/experiments/direct_m1_diagnosis.py", "direct_m1_diagnosis_under_test")

    def _case(self, case_id, readback, head_best, recorded):
        return {"case_id": case_id,
                "readback_E": {"residual_ratio": readback},
                "head_projection_E": {"best_physical": {"residual_ratio": head_best}},
                "recorded_fit_E": {"residual_ratio": recorded}}

    def test_a_case_missing_a_value_keeps_its_own_identity(self):
        result = self.m1.interpretation([
            self._case("first", 0.3, 0.2, None),
            self._case("second", 0.4, 0.1, 0.4),
        ])
        notes = result["case_interpretations"]
        self.assertEqual([note["case_id"] for note in notes], ["first", "second"])
        self.assertEqual(notes[0]["head_best_R"], 0.2)
        self.assertEqual(notes[1]["head_best_R"], 0.1)
        self.assertEqual(notes[0]["status"], "INCOMPLETE")

    def test_a_first_case_missing_a_value_does_not_raise(self):
        result = self.m1.interpretation([self._case("only", None, None, None)])
        self.assertEqual(result["incomplete_cases"], ["only"])


class PlanStateTests(unittest.TestCase):
    """F17: reinstalling a queue reset an audited task."""

    @classmethod
    def setUpClass(cls):
        cls.plan_state = load_module("tools/plan_state.py", "plan_state_under_test")

    def test_a_recorded_outcome_is_protected(self):
        plan = {"goal": {"id": "G"}, "current_task": None, "tasks": [{
            "id": "T", "status": "PASS", "scientific_result": "FAIL",
            "evidence": ["evidence/x.json"], "title": "old title",
        }]}
        report = self.plan_state.ensure_task(plan, {
            "id": "T", "goal_id": "G", "title": "new title", "status": "READY",
            "scientific_result": "NOT_RUN", "evidence": [],
        })
        task = plan["tasks"][0]
        self.assertEqual(task["status"], "PASS")
        self.assertEqual(task["scientific_result"], "FAIL")
        self.assertEqual(task["evidence"], ["evidence/x.json"])
        self.assertEqual(task["title"], "new title")
        self.assertTrue(report["protected_outcome"])
        self.assertIsNone(plan["current_task"])

    def test_a_task_without_an_outcome_may_still_be_declared(self):
        plan = {"goal": {"id": "G"}, "current_task": None, "tasks": [{
            "id": "T", "status": "BLOCKED", "scientific_result": "NOT_RUN", "evidence": [],
        }]}
        # BLOCKED is terminal-shaped but carries no result or evidence, so the
        # installer may still stage it.  The protection is about outcomes.
        self.plan_state.ensure_task(plan, {"id": "T", "status": "READY"})
        self.assertEqual(plan["tasks"][0]["status"], "READY")

    def test_a_new_task_is_inserted(self):
        plan = {"goal": {"id": "G"}, "current_task": None, "tasks": []}
        report = self.plan_state.ensure_task(plan, {"id": "NEW", "status": "READY"})
        self.assertEqual(report["action"], "inserted")
        self.assertEqual(plan["current_task"], "NEW")

    def test_an_audited_summary_and_dependency_survive_a_reinstall(self):
        plan = {"goal": {"id": "G"}, "current_task": None, "tasks": [{
            "id": "T", "status": "PASS", "scientific_result": "FAIL",
            "evidence": ["evidence/x.json"], "depends": ["DEP"],
            "summary": "returned PASS; scientific_result=FAIL; adam=261209",
        }]}
        self.plan_state.ensure_task(plan, {
            "id": "T", "status": "READY", "depends": [],
            "summary": "clean trajectory from step0; target=128.",
        })
        task = plan["tasks"][0]
        self.assertEqual(task["depends"], ["DEP"])
        self.assertIn("adam=261209", task["summary"])

    def test_ready_cannot_bypass_an_unmet_prerequisite(self):
        plan = {"goal": {"id": "G"}, "current_task": None, "tasks": [
            {"id": "DEP", "status": "FAIL", "scientific_result": "FAIL",
             "evidence": ["evidence/x.json"]},
        ]}
        report = self.plan_state.ensure_task(
            plan, {"id": "T", "status": "READY", "depends": ["DEP"]})
        self.assertEqual(plan["tasks"][-1]["status"], "BLOCKED")
        self.assertEqual(report["blocked_by"], ["DEP"])
        self.assertIsNone(plan["current_task"])

    def test_every_queue_installer_is_idempotent_on_the_real_plan(self):
        # Run every installer's task registration against a COPY of the real
        # plan and assert that no recorded outcome moved.  This is the check
        # that would have caught F17 before it reached project/plan.json.
        import importlib.util
        import shutil
        plan_path = PROJECT_DIR / "project/plan.json"
        original = plan_path.read_bytes()
        before = json.loads(original.decode("utf-8"))
        snapshot = {task["id"]: dict(task) for task in before["tasks"]}
        try:
            for path in sorted((PROJECT_DIR / "tools").glob("server_*_queue.py")):
                spec = importlib.util.spec_from_file_location(
                    f"queue_under_test_{path.stem}", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                register = getattr(module, "ensure_task", None) or getattr(module, "ensure_tasks", None)
                if register is not None:
                    register()
            after = json.loads(plan_path.read_text(encoding="utf-8"))
            for task in after["tasks"]:
                old_task = snapshot.get(task["id"])
                if old_task is None:
                    continue
                for key in ("status", "scientific_result", "evidence", "summary", "depends"):
                    self.assertEqual(old_task.get(key), task.get(key),
                                     f"{task['id']}.{key} changed on reinstall")
        finally:
            plan_path.write_bytes(original)


class IngestContractTests(unittest.TestCase):
    """F04 and F20: a self-asserted summary was read as an audit."""

    @classmethod
    def setUpClass(cls):
        cls.contract = load_module("tools/ingest_contract.py", "ingest_contract_under_test")
        cls.theta = load_module("tools/ingest_paper01_theta_full_return.py", "theta_ingest_under_test")

    def test_a_lone_self_asserted_summary_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "summary.json").write_text(
                json.dumps({"status": "PASS", "variants": [{}]}), encoding="utf-8")
            review = self.theta.review(output / "summary.json", output)
            self.assertEqual(review["status"], "INCOMPLETE")
            self.assertEqual(review["scientific_result"], "INCOMPLETE")
            self.assertIn("history.jsonl", review["delivery_integrity"]["missing"])

    def test_a_repeated_update_number_is_not_a_complete_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            path.write_text("".join(
                json.dumps({"update": 25000, "loss": 1.0, "lr": 1e-4}) + "\n"
                for _ in range(25000)), encoding="utf-8")
            audit = self.contract.verify_history(path, 25000)
            self.assertFalse(audit["complete"])
            self.assertEqual(audit["unique_updates"], 1)

    def test_a_genuine_history_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            path.write_text("".join(
                json.dumps({"update": i, "loss": 1.0 / i, "lr": 1e-4}) + "\n"
                for i in range(1, 101)), encoding="utf-8")
            audit = self.contract.verify_history(path, 100)
            self.assertTrue(audit["complete"], audit["problems"])
            self.assertEqual(audit["distinct_learning_rate_count"], 1)

    def test_a_non_finite_loss_row_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            rows = [json.dumps({"update": i, "loss": 1.0, "lr": 1e-4}) for i in range(1, 5)]
            rows.append('{"update": 5, "loss": NaN, "lr": 0.0001}')
            path.write_text("\n".join(rows) + "\n", encoding="utf-8")
            audit = self.contract.verify_history(path, 5)
            self.assertFalse(audit["complete"])

    def test_a_missing_deliverable_is_incomplete_and_never_pass(self):
        verdict = self.contract.delivery_verdict(read_ok=True, integrity_checks={"a": True},
                                                 missing=["best.pt"])
        self.assertEqual(verdict["status"], "INCOMPLETE")
        failed = self.contract.delivery_verdict(read_ok=True, integrity_checks={"a": False})
        self.assertEqual(failed["status"], "FAIL")


class G0VerifierTests(unittest.TestCase):
    """F29: structure and physics were not separated."""

    @classmethod
    def setUpClass(cls):
        cls.g0 = load_module("scripts/experiments/g0_verifier.py", "g0_verifier_under_test")

    def _result(self, rows=128, probes_per_row=3):
        def row(step):
            components = {name: {"nmae": 0.0, "volume_nmae": 0.0, "mre_eq5_physical": 0.0,
                                 "mre_nonzero": 0.0, "relative_l2": 0.0, "sse": 0.0,
                                 "reference_energy": 1.0, "support_count": 1,
                                 "strict_zero_reference_count": 0}
                          for name in ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz")}
            return {"step": step, "accepted": True, "accepted_steps": step + 1,
                    "accepted_field_metrics": {"components": components,
                                               "global_weighted_relative_l2": 0.0,
                                               "fixed_amplitude_error": 0.0},
                    "source_outside_probes": [{"dut_Ez": 1.0, "ref_Ez": 1.0}] * probes_per_row}
        return {"rows": [row(i) for i in range(rows)],
                "support": {"uncovered": 0}, "reference_dtype": "float64",
                "control_only": True,
                "identity": {"run_id": "r", "protocol_hash": "p", "source_hashes": {}}}

    def test_a_complete_control_passes(self):
        passed, detail = self.g0.control_numeric(self._result(), threshold=1e-10, should_pass=True)
        self.assertTrue(passed)
        self.assertEqual(detail["status"], "PASS")

    def test_deleting_probes_is_incomplete_not_a_valid_negative_control(self):
        broken = self._result()
        broken["rows"][0]["source_outside_probes"] = []
        passed, detail = self.g0.control_numeric(broken, threshold=1e-10, should_pass=False)
        self.assertFalse(passed, "a structurally broken record is not a valid negative control")
        self.assertEqual(detail["status"], "INCOMPLETE")

    def test_a_wrong_field_is_a_valid_negative_control(self):
        wrong = self._result()
        for row in wrong["rows"]:
            row["accepted_field_metrics"]["global_weighted_relative_l2"] = 1.0
        passed, detail = self.g0.control_numeric(wrong, threshold=1e-10, should_pass=False)
        self.assertTrue(passed)
        self.assertTrue(detail["structural_complete"])

    def test_an_empty_source_hash_table_fails_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "control"
            (run_dir / "source_snapshot").mkdir(parents=True)
            atomic_json_save({"run_id": "r", "protocol_hash": "p"}, run_dir / "run_metadata.json")
            (run_dir / "steps.jsonl").write_text("".join(
                json.dumps({"sequence_id": i, "step": i, "accepted": True, "accepted_steps": i + 1}) + "\n"
                for i in range(128)), encoding="utf-8")
            result = self._result()
            result["source_snapshot_hashes"] = {}
            self.assertFalse(self.g0.control_integrity(result, run_dir))


class HourRunnerTests(unittest.TestCase):
    """F28: finalize overwrote a terminal verdict and trusted a bare pointer."""

    @classmethod
    def setUpClass(cls):
        cls.hour = load_module("scripts/experiments/mechanism_hour_runner.py", "mechanism_hour_runner_under_test")

    def test_an_empty_pointer_does_not_certify_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "checkpoint_pointer.json").write_text("{}", encoding="utf-8")
            check = self.hour.verified_recovery_eligible(out, [{"sequence_id": 0}])
            self.assertFalse(check["eligible"])

    def test_a_pointer_to_a_missing_slot_does_not_certify_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "checkpoint_pointer.json").write_text(json.dumps({
                "schema": "pidon-rolling-checkpoint-v1", "slot": "A",
                "path": "checkpoint_A.pt", "sha256": "0" * 64,
                "last_committed_sequence_id": 0,
            }), encoding="utf-8")
            check = self.hour.verified_recovery_eligible(out, [{"sequence_id": 0}])
            self.assertFalse(check["eligible"])

    def test_terminal_status_list_protects_fail(self):
        self.assertIn("FAIL", self.hour.TERMINAL_ARM_STATUS)


class Phase1ContractTests(unittest.TestCase):
    """F21: equivalence PASS without a threshold, recovery True by fiat."""

    @classmethod
    def setUpClass(cls):
        cls.s1 = load_module("scripts/experiments/phase1_full_run.py", "phase1_full_run_under_test")

    def test_equivalence_tolerances_exist(self):
        self.assertGreater(self.s1.EQUIVALENCE_GRAD_REL_TOL, 0.0)
        self.assertLess(self.s1.EQUIVALENCE_GRAD_REL_TOL, 0.01)

    def test_recovery_is_no_longer_asserted_true(self):
        source = (PROJECT_DIR / "scripts/experiments/phase1_full_run.py").read_text(encoding="utf-8")
        self.assertNotIn('"recovery_eligible": True,', source)
        self.assertIn('"recovery_contract"', source)

    def test_allow_existing_no_longer_reopens_a_finished_directory(self):
        source = (PROJECT_DIR / "scripts/experiments/phase1_full_run.py").read_text(encoding="utf-8")
        self.assertNotIn("and not args.allow_existing", source)


class Paper01MetricTests(unittest.TestCase):
    """F09/F10/F11 in the independent first-stage line."""

    @classmethod
    def setUpClass(cls):
        import sys
        path = str(PROJECT_DIR / "_01/src")
        if path not in sys.path:
            sys.path.insert(0, path)

    def test_normalized_and_physical_relative_l2_are_separate_fields(self):
        from paper01.metrics import summarize
        prediction = np.zeros((1, 3, 2, 2, 2))
        target = np.ones((1, 3, 2, 2, 2))
        prediction[0, 0] = 1.0
        prediction[0, 1] = 1.0
        result = summarize(prediction, target, scales=np.array([[1.0, 1.0, 0.01]]))
        self.assertIn("component_normalized_vector_rel_l2_p90", result)
        self.assertIn("physical_vector_rel_l2_p90", result)
        self.assertNotAlmostEqual(result["component_normalized_vector_rel_l2_p90"],
                                  result["physical_vector_rel_l2_p90"])

    def test_the_split_contract_states_that_test_is_a_development_set(self):
        source = (PROJECT_DIR / "_01/src/paper01/runner.py").read_text(encoding="utf-8")
        self.assertIn('"dev_used_for_model_selection": True', source)
        self.assertIn('"blind_used_for_selection": False', source)

    def test_the_ablation_declares_a_common_paper_and_shared_initialization(self):
        source = (PROJECT_DIR / "_01/train_phase1_ablation.py").read_text(encoding="utf-8")
        self.assertIn("common_test_variant", source)
        self.assertIn("shared_initialization", source)
        self.assertNotIn("seed = config.seed + index * 1000\n    seed_all", source)

    def test_checkpoints_are_written_atomically(self):
        for relative in ("_01/src/paper01/runner.py", "_01/train_phase1_ablation.py"):
            source = (PROJECT_DIR / relative).read_text(encoding="utf-8")
            self.assertIn("os.replace(temporary, path)", source, relative)


class LabLogTests(unittest.TestCase):
    """F14, F15 and F16 in the ledger."""

    @classmethod
    def setUpClass(cls):
        cls.lab = load_module("lab_log.py", "lab_log_under_test")

    def test_verify_reports_missing_evidence_in_its_exit_code(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                os.makedirs("records", exist_ok=True)
                Path(self.lab.JSONL).write_text(json.dumps({
                    "id": 1, "outputs": [{"path": "absent.pt", "bytes": 1, "sha256": "0" * 64}],
                }) + "\n", encoding="utf-8")

                class Args:
                    pass
                self.assertEqual(self.lab.do_verify(Args()), 3,
                                 "a missing recorded output must not exit 0")
                present = Path("present.bin")
                present.write_bytes(b"hello")
                Path(self.lab.JSONL).write_text(json.dumps({
                    "id": 1, "outputs": [{"path": "present.bin", "bytes": 5,
                                          "sha256": sha256_file(present)}],
                }) + "\n", encoding="utf-8")
                self.assertEqual(self.lab.do_verify(Args()), 0)
            finally:
                os.chdir(cwd)

    def test_a_complete_output_manifest_is_written_and_hashed(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                outputs = [{"path": f"f{i}.bin", "bytes": i, "sha256": "0" * 64} for i in range(40)]
                manifest = self.lab.write_output_manifest(7, "abcd", outputs)
                document = json.loads(Path(manifest["path"]).read_text(encoding="utf-8"))
                self.assertEqual(document["count"], 40)
                self.assertEqual(len(document["outputs"]), 40)
                self.assertEqual(manifest["sha256"], sha256_file(Path(manifest["path"])))
            finally:
                os.chdir(cwd)

    def test_run_ids_are_reserved_so_parallel_wrappers_differ(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                os.makedirs("records", exist_ok=True)
                first = self.lab.next_id()
                second = self.lab.next_id()
                self.assertNotEqual(first, second)
                self.assertEqual(second, first + 1)
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
