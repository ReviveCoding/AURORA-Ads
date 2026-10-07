import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_public_figures import point_interval


class PublicFigureTest(unittest.TestCase):
    def test_missing_interval_is_not_zero_width(self):
        self.assertEqual(point_interval({"estimate": "0", "ci_lower": "", "ci_upper": ""}), (0., None))
        self.assertEqual(point_interval({"estimate": ".005", "ci_lower": "-.003", "ci_upper": ".014"}), (.005, (-.003, .014)))

    def test_bad_intervals_are_not_clipped(self):
        for row in ({"estimate": ".1", "ci_lower": "", "ci_upper": ".2"},
                    {"estimate": ".1", "ci_lower": ".2", "ci_upper": ".3"},
                    {"estimate": "nan", "ci_lower": "", "ci_upper": ""}):
            with self.assertRaises(ValueError):
                point_interval(row)


if __name__ == "__main__":
    unittest.main()
