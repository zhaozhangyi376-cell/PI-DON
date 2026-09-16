"""Small analytic regression tests. Run through lab_log.py; no model training."""
import unittest
import numpy as np
import torch
import dco
import fdtd
import paper_protocol as P


class PaperProtocolTests(unittest.TestCase):
    def test_eq5_uses_exact_zero_branch_not_small_value_cutoff(self):
        t = torch.tensor([1e-40, 0.0], dtype=torch.float64)
        p = torch.tensor([2e-40, 0.2], dtype=torch.float64)
        self.assertAlmostEqual(float(dco.mre_eq5(p, t)), 0.6)

    def test_mre_scaling_is_not_nmae(self):
        t = torch.tensor([1., 100.], dtype=torch.float64)
        p = torch.tensor([2., 101.], dtype=torch.float64)
        self.assertAlmostEqual(float(dco.mre_eq5(p, t)), .505)
        self.assertAlmostEqual(float(dco.mre_eq5(p / 100, t / 100)), .505)
        self.assertAlmostEqual(float(dco.nmae(p, t)), .01)

    def test_metric_zero_branch_is_unit_sensitive(self):
        t = np.array([0., 2.])
        p = np.array([.4, 2.2])
        self.assertAlmostEqual(P.scalar_metrics(p, t)['mre_eq5'], .25)
        self.assertAlmostEqual(P.scalar_metrics(p / 10, t / 10)['mre_eq5'], .07)

    def test_component_aggregation(self):
        t = np.array([[1., 1.], [10., 10.], [100., 100.]])
        p = t + 1
        m = P.vector_metrics(p, t)
        self.assertAlmostEqual(m['macro_nmae'], .37)
        self.assertAlmostEqual(m['global_nmae'], .01)
        self.assertAlmostEqual(m['macro_mre_eq5'], .37)

    def test_fixed_case_reuses_wave_spec_across_grids(self):
        spec = P.wave_spec(0)
        e, c, h = P.sample_wave(spec, (32, 32, 32))
        e2, c2, h2 = P.sample_wave(spec, (64, 96, 16))
        np.testing.assert_allclose(np.array(h) * 32, .0192)
        np.testing.assert_allclose(np.array(h2) * [64, 96, 16], .0192)
        self.assertEqual(e.shape, (3, 32, 32, 32))
        self.assertEqual(c2.shape, (3, 64, 96, 16))
        np.testing.assert_array_equal(spec['k'], np.linspace(.021, 838.34, 20))
        np.testing.assert_allclose(np.asarray(spec['amplitude']) @ spec['direction'], 0, atol=1e-14)

    def test_single_wave_analytic_curl(self):
        # E=(0,cos(3x),0), curl_z=-3sin(3x), sampled at Hz=(x+h/2,y+h/2,z).
        spec = {'k': [3.], 'direction': [1., 0., 0.], 'amplitude': [[0., 1., 0.]]}
        e, c, h = P.sample_wave(spec, (8, 8, 8))
        x = (np.arange(8) + .5) * h[0]
        np.testing.assert_allclose(c[2, :, 0, 0], -3 * np.sin(3 * x), atol=1e-14)
        np.testing.assert_array_equal(c[:2], 0)

    def test_three_curl_components_at_yee_positions(self):
        # Polynomial fields isolate the three signs and each derivative's units.
        n, dx = 6, .002
        esh = [(n,n+1,n+1), (n+1,n,n+1), (n+1,n+1,n)]
        hsh = [(n+1,n,n), (n,n+1,n), (n,n,n+1)]
        for shapes, offsets, curl in [(esh, P.E_OFFSETS, fdtd.curl_E),
                                       (hsh, P.H_OFFSETS, fdtd.curl_H)]:
            for out_c, in_c, axis in [(0,2,1),(1,0,2),(2,1,0)]:
                arrays = [np.zeros(sh) for sh in shapes]
                grids = np.indices(shapes[in_c], dtype=float)
                arrays[in_c] = (grids[axis] + offsets[in_c][axis]) * dx
                ans = curl(*arrays, dx, dx, dx)
                for k in range(3):
                    np.testing.assert_allclose(ans[k], float(k == out_c), atol=2e-15)

    def test_pec_and_zero_field_fixed_point(self):
        cav = fdtd.PECCavity(n=7)
        for _ in range(3): cav.step()
        for a in [cav.Ex,cav.Ey,cav.Ez,cav.Hx,cav.Hy,cav.Hz]:
            np.testing.assert_array_equal(a, 0)
        cav.Ex.fill(1); cav.Ey.fill(1); cav.Ez.fill(1); cav.apply_pec()
        self.assertEqual(cav.Ex[3,3,3], 1)
        for a in [cav.Ex[:,0,:],cav.Ex[:,:,-1],cav.Ey[0,:,:],cav.Ey[:,:,-1],
                  cav.Ez[0,:,:],cav.Ez[:,-1,:]]: np.testing.assert_array_equal(a, 0)

    def test_nonfinite_metrics_rejected(self):
        with self.assertRaises(ValueError): P.scalar_metrics(np.array([np.nan]), np.array([1.]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
