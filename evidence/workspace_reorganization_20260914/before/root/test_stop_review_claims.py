import unittest
from stop_review_evidence import g1_development_status


class ReviewGateTests(unittest.TestCase):
    @staticmethod
    def row(step):
        fit = {'passed':True,'residual_ratio':5e-5,'n_updates':10,'stop_reason':'tol_met'}
        return {'step':step,'phase':'completed','fit_H':dict(fit),'fit_E':dict(fit),'fixed_amplitude_error':1e-4}

    def test_one_successful_state_is_not_complete_development(self):
        self.assertEqual(g1_development_status([self.row(43)]),'INCOMPLETE')

    def test_both_curls_required(self):
        a,b = self.row(43),self.row(96); b['fit_E']=None
        self.assertEqual(g1_development_status([a,b]),'INCOMPLETE')

    def test_scientific_failure_is_not_relabelled_missing(self):
        a=self.row(43); a['fit_H']['passed']=False
        self.assertEqual(g1_development_status([a]),'FAIL')

    def test_development_pass_is_distinct_from_full_g1(self):
        self.assertEqual(g1_development_status([self.row(43),self.row(96)]),'PASS')


if __name__ == '__main__':
    unittest.main()
