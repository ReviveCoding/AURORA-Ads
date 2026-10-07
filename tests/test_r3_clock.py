import unittest

from aurora.r3_clock import check_delay_schema, infer_clock_scale


class R3ClockTests(unittest.TestCase):
    def test_duration_not_numeric_epoch_supports_seconds_and_milliseconds(self):
        self.assertEqual(infer_clock_scale(91 * 86400)["native_unit"], "seconds")
        self.assertEqual(infer_clock_scale(90 * 86400 * 1000)["native_unit"], "milliseconds")
        with self.assertRaises(ValueError):
            infer_clock_scale(42 * 86400)

    def test_delay_schema_zero_atom_and_nonconversion_sentinels(self):
        check_delay_schema(min_positive_delay=0, max_positive_delay=30 * 86400, clock_scale=1,
                           bad_nonconversion_delays=0)
        for low, high, bad in ((-1, 100, 0), (0, 30 * 86400 + 1, 0), (0, 100, 1)):
            with self.assertRaises(ValueError):
                check_delay_schema(min_positive_delay=low, max_positive_delay=high, clock_scale=1,
                                   bad_nonconversion_delays=bad)
