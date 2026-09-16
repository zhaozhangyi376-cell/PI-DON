"""P4-A driver contract before the bounded optimizer comparison."""

import unittest

from r4_p4a import p4a_args


class P4ADriverTests(unittest.TestCase):
    def test_p4a_budget_is_frozen(self):
        args = p4a_args()
        self.assertEqual(args.max_inner, 200)
        self.assertEqual(args.lbfgs_closures, 200)
        self.assertEqual(args.lbfgs_lr, 1.0)
        self.assertEqual(args.lbfgs_history, 10)
        self.assertEqual(args.lbfgs_time_budget_s, 60.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
