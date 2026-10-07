import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("serving_study_test", Path(__file__).resolve().parents[1] / "tools/serving_study.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ServingIsolationTests(unittest.TestCase):
    def test_new_driver_arguments_detected_without_unrelated_names(self):
        root = Path("/owned/repo")
        names = ("policy_ablation_study.py", "policy_pilot_study.py", "r3_parametric_delay_study.py")
        for name in names:
            self.assertTrue(module.compute_arguments([b"python", str(root / "tools" / name).encode()], root, names))
            self.assertTrue(module.compute_arguments([b"python", ("tools/" + name).encode()], root, names))
        self.assertFalse(module.compute_arguments([b"python", b"/another/project/script.py"], root, names))

    def test_p99_and_invalid_latency_samples(self):
        result = module.quantiles([.001, .002, .003])
        self.assertAlmostEqual(result["p99_ms"], 2.98)
        self.assertEqual(result["n"], 3)
        for values in ([], [-1.], [float("nan")]):
            with self.assertRaises(ValueError):
                module.quantiles(values)

    def test_explicit_partial_cpu_profile_preserves_default_match(self):
        self.assertEqual(module.qualified_devices(("cpu",)), ("cpu",))
        self.assertEqual(module.qualified_devices(("cpu", "cuda")), ("cpu", "cuda"))
        for invalid in (("cuda",), (), ("cpu", "other")):
            with self.assertRaises(ValueError):
                module.qualified_devices(invalid)


if __name__ == "__main__":
    unittest.main()
