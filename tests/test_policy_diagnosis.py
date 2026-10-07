import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("policy_diagnosis", Path(__file__).resolve().parents[1] / "tools/policy_negative_diagnosis.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PolicyDiagnosisTests(unittest.TestCase):
    def test_ordinary_and_operating_cost_are_distinct(self):
        base = {"initial_budget": 100, "unique_purchase_value": 90, "no_ad_purchase_value": 50,
                "spend": 30, "operating_cost": 0, "utility": .1}
        candidate = base | {"unique_purchase_value": 95, "spend": 80, "operating_cost": 1, "utility": -.36}
        result = module.decompose(candidate, base)
        self.assertAlmostEqual(result["purchase_value_difference_normalized"], .05)
        self.assertAlmostEqual(result["utility_difference"], -.46)
        self.assertEqual(result["no_ad_value_difference_normalized"], 0)

    def test_mismatched_budget_or_utility_refused(self):
        base = {"initial_budget": 100, "unique_purchase_value": 90, "no_ad_purchase_value": 50,
                "spend": 30, "operating_cost": 0, "utility": .1}
        for candidate in (base | {"initial_budget": 101}, base | {"utility": 999}):
            with self.assertRaises(ValueError):
                module.decompose(candidate, base)
