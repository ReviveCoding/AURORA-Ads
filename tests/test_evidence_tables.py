import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from verify_evidence_tables import nullable_number, pointer_value


class EvidenceTableTest(unittest.TestCase):
    def test_blank_is_not_zero_and_numbers_are_finite(self):
        self.assertIsNone(nullable_number(""))
        self.assertEqual(nullable_number("0"), 0.)
        self.assertEqual(nullable_number("-5.400699300955959e-4"), -.0005400699300955959)
        for value in ("nan", "inf", "-inf", "missing"):
            with self.assertRaises(ValueError):
                nullable_number(value)
        self.assertTrue(math.isfinite(nullable_number("1e-12")))

    def test_json_pointer_retains_array_and_escaped_source_identity(self):
        document = {"a/b": {"tilde~key": [0., None, -.02]}}
        self.assertEqual(pointer_value(document, "/a~1b/tilde~0key/0"), 0.)
        self.assertIsNone(pointer_value(document, "/a~1b/tilde~0key/1"))
        self.assertEqual(pointer_value(document, "/a~1b/tilde~0key/2"), -.02)
        with self.assertRaises(KeyError):
            pointer_value(document, "/unavailable")


if __name__ == "__main__":
    unittest.main()
