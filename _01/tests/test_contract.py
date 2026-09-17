import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PaperContractTests(unittest.TestCase):
    def test_every_contract_field_has_fidelity_class_and_source(self):
        contract = json.loads((ROOT / "paper_contract.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["schema"], "pidon-paper01-contract-v1")
        self.assertEqual(contract["claim"], "paper-explicit reference; not author-code identity")
        rows = contract["fields"]
        self.assertGreaterEqual(len(rows), 20)
        for row in rows:
            self.assertIn(row["class"], {"EXPLICIT", "DERIVED", "ASSUMED"})
            self.assertTrue(row["source"])
            self.assertIn("value", row)
        assumed = {row["name"] for row in rows if row["class"] == "ASSUMED"}
        self.assertIn("base_channels", assumed)
        self.assertIn("real_field_representation", assumed)
        self.assertIn("local_max_scope", assumed)
        self.assertIn("trunk_coordinate_unit", assumed)
        self.assertIn("theta_singularity_rejection", assumed)
        self.assertIn("phase_one_collocation", assumed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
