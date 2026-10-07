import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("ablation_analysis", Path(__file__).resolve().parents[1] / "tools/policy_ablation_analysis.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AblationAnalysisTest(unittest.TestCase):
    def fixture(self):
        world = {"world_id": "fixture", "family": "fixture", "stage": "validation"}
        evaluation = {"initial_budget": 100, "unique_purchase_value": 90,
                      "no_ad_purchase_value": 50, "spend": 30, "operating_cost": 0,
                      "utility": .1, "final_pending_exposures": 0}
        return {"world": world, "evaluation": evaluation, "not_confirmation": True}

    def test_negative_decomposition(self):
        baseline = self.fixture()
        candidate = baseline | {"evaluation": baseline["evaluation"] | {
            "unique_purchase_value": 95, "spend": 80, "operating_cost": 1, "utility": -.36}}
        result = module.paired_decomposition(candidate, baseline)
        self.assertAlmostEqual(result["utility_difference"], -.46)
        self.assertAlmostEqual(result["normalized_components"]["operating_cost"], .01)

    def test_final_and_incomplete_inputs_refused(self):
        baseline = self.fixture()
        for candidate in (baseline | {"not_confirmation": False},
                          baseline | {"world": baseline["world"] | {"stage": "final"}},
                          baseline | {"evaluation": baseline["evaluation"] | {"final_pending_exposures": 1}},
                          baseline | {"evaluation": baseline["evaluation"] | {"utility": 999}}):
            with self.assertRaises(ValueError):
                module.paired_decomposition(candidate, baseline)


if __name__ == "__main__":
    unittest.main()
