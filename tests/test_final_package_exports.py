import json
import tempfile
import unittest
from pathlib import Path

from tools.verify_final_package import flattened, locate, verify_csv


class FinalExportsTests(unittest.TestCase):
    def test_json_pointer_exact_saved_value(self):
        self.assertEqual(locate({"a/b": [{"~metric": -.25}]}, "/a~1b/0/~0metric"), -.25)
        with self.assertRaises(KeyError):
            locate({"mean": -.25}, "/estimate")

    def test_null_is_not_zero_and_lists_remain_metadata(self):
        self.assertEqual(flattened(None), "")
        self.assertEqual(flattened(0), "0")
        self.assertEqual(json.loads(flattened(["SHA", None])), ["SHA", None])

    def test_saved_numeric_export_and_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.csv"
            path.write_text("result_id,estimate,ci_lower\nmeasured,-0.25,\nunavailable,,\n")
            rows = [{"result_id": "measured", "estimate": -.25, "ci_lower": None},
                    {"result_id": "unavailable", "estimate": None, "ci_lower": None}]
            self.assertEqual(verify_csv(path, rows, "result_id"), 2)
            path.write_text("result_id,estimate,ci_lower\nmeasured,-0.25,\nunavailable,0,\n")
            with self.assertRaises(ValueError):
                verify_csv(path, rows, "result_id")

    def test_duplicate_measurements_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.csv"
            path.write_text("result_id,estimate\nx,1\nx,1\n")
            with self.assertRaises(ValueError):
                verify_csv(path, [{"result_id": "x", "estimate": 1}] * 2, "result_id")


if __name__ == "__main__":
    unittest.main()
