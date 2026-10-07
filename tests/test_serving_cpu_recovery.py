import importlib.util
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location("serving_cpu_recovery_test", TOOLS / "serving_cpu_study.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CPURecoveryTests(unittest.TestCase):
    def response(self):
        return {"model_sha256": "a" * 64, "scores": [1., 2., 3., 4., 5., 6.],
            "state_mutations": 0, "provisional_candidate_index": 5,
            "decision_scope": "frozen mean-head ranking only; not authorized, host-guarded or adaptive campaign decision"}

    def test_same_readonly_provisional_result(self):
        module.assert_readonly_match(self.response(), self.response())

    def test_changed_model_mutation_or_scope_rejected(self):
        for key, value in (("model_sha256", "b"*64), ("state_mutations", 1), ("decision_scope", "authorized commit")):
            with self.assertRaises(ValueError):
                module.assert_readonly_match(self.response(), self.response() | {key: value})

    def test_changed_scores_or_ranking_rejected(self):
        with self.assertRaises(AssertionError):
            module.assert_readonly_match(self.response(), self.response() | {"scores": [0.] * 6})
        with self.assertRaises(ValueError):
            module.assert_readonly_match(self.response(), self.response() | {"provisional_candidate_index": 4})


if __name__ == "__main__":
    unittest.main()
