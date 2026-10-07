import math
import unittest

from aurora.attribution import ALLOCATION_SQL, CreditedTouch, path_weights


class AttributionTest(unittest.TestCase):
    def test_sql_against_independent_python_path(self):
        import duckdb
        touches = [CreditedTouch(1, "u", "a", 0., 3.), CreditedTouch(1, "u", "b", 1., 3.), CreditedTouch(1, "u", "c", 1., 3.)]
        expected = path_weights(touches, half_life_native=1.)
        with duckdb.connect() as connection:
            connection.execute("CREATE TABLE credited(conversion_id BIGINT,campaign VARCHAR,timestamp DOUBLE)")
            connection.executemany("INSERT INTO credited VALUES(?,?,?)", [(touch.conversion_id, touch.campaign, touch.origin) for touch in touches])
            rows = connection.execute(ALLOCATION_SQL, [1.]).fetchall()
        for index, row in enumerate(rows):
            for offset, name in enumerate(("first_touch", "last_touch", "time_decay")):
                self.assertAlmostEqual(row[offset + 2], expected[name][index])

    def test_unique_conversion_and_tie_allocations(self):
        touches = [CreditedTouch(1, "u", "a", 0., 3.), CreditedTouch(1, "u", "b", 1., 3.), CreditedTouch(1, "u", "c", 1., 3.)]
        result = path_weights(touches, half_life_native=1.)
        self.assertEqual(result["first_touch"], [1., 0., 0.])
        self.assertEqual(result["last_touch"], [0., .5, .5])
        self.assertEqual(result["time_decay"], [.2, .4, .4])
        for values in result.values():
            self.assertAlmostEqual(math.fsum(values), 1.)

    def test_incompatible_identity_or_clock_rejected(self):
        valid = CreditedTouch(1, "u", "a", 0., 2.)
        for invalid in (CreditedTouch(1, "v", "b", 1., 2.), CreditedTouch(1, "u", "b", 1., 3.), CreditedTouch(1, "u", "b", 3., 2.), CreditedTouch(2, "u", "b", 1., 2.)):
            with self.assertRaises(ValueError):
                path_weights([valid, invalid], half_life_native=1.)


if __name__ == "__main__":
    unittest.main()
