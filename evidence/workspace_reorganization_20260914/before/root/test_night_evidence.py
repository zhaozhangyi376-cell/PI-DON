import unittest

import night_evidence


class NightEvidenceTests(unittest.TestCase):
    def test_registered_gate_is_not_promoted_by_controls_or_oracles(self):
        evidence = night_evidence.compute()
        self.assertEqual(evidence["G0"]["status"], "PASS")
        self.assertEqual(evidence["N3"]["G1"], "FAIL")
        self.assertEqual(evidence["N4"]["status"], "NOT_RUN")
        self.assertEqual(evidence["gates"]["G2"], "NOT_RUN")
        self.assertEqual(evidence["gates"]["G3"], "NOT_RUN")
        self.assertEqual(len(evidence["N3"]["oracle_rows_excluded"]), 2)

    def test_disk_remeasurements_and_metric_labels_are_explicit(self):
        evidence = night_evidence.compute()
        rows = evidence["N3"]["registered_rows"]
        self.assertTrue(all(row["R_disk"] is not None for row in rows))
        self.assertGreater(rows[0]["R_disk"], 1e-4)
        self.assertLess(rows[1]["R_disk"], 1e-4)
        self.assertGreater(rows[2]["R_disk"], 1e-4)
        self.assertEqual(evidence["N5"]["label_provenance"], "INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
