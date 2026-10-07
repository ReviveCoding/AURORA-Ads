from __future__ import annotations

import gzip
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pyarrow as pa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.data import ClockRecord, SCHEMAS, eligible_features, open_batches, r3_partition, valid_rows
from aurora.measurement import censored_log_likelihood, conditional_exponential_cdf, fixed_policy_ope, projected_distribution


class NumericalTests(unittest.TestCase):
    def test_finite_horizon_partial_bins_zero_atom(self):
        mass = np.array([[.1, .2, .7]] * 3)
        result = censored_log_likelihood([.4] * 3, mass, [0., .5, 7.], [-1] * 3, [0., 1., 7.])
        np.testing.assert_allclose(np.exp(result), [.96, .92, .6], rtol=1e-14)
        np.testing.assert_allclose(conditional_exponential_cdf([0, 3, 7], 1e-12), [0, 3/7, 1], atol=1e-12)

    def test_ope_independent_fixture_and_probability_mapping(self):
        result = fixed_policy_ope([0, 1], [1., 0.], [.5, .5], [[.5, .5]] * 2, [[.2, .8]] * 2)
        self.assertAlmostEqual(result.dr, .5)
        self.assertEqual(result.ess, 2.)
        np.testing.assert_allclose(projected_distribution([.2, .3, .5], [0, 0, 1], 2), [.5, .5])
        with self.assertRaises(ValueError):
            fixed_policy_ope([0], [1], [0], [[1]], [[1]])

    def test_receipt_and_temporal_leakage_traps(self):
        clock = ClockRecord(0, 1, 5, 7)
        self.assertFalse(clock.eligible(.5))
        self.assertFalse(clock.observed(4))
        self.assertTrue(clock.observed(5))
        self.assertFalse(clock.mature(6))
        self.assertTrue(clock.mature(7))
        self.assertEqual(r3_partition(41 * 86400), "C54")
        self.assertEqual(r3_partition(47 * 86400), "excluded")
        self.assertEqual(r3_partition(82 * 86400), "excluded")
        for source, forbidden in (("criteo_uplift", "exposure"), ("criteo_attribution", "click_nb"), ("criteo_search", "Sale")):
            with self.assertRaises(ValueError):
                eligible_features(source, (forbidden,))

    def test_container_crc_and_decompression_ceiling(self):
        schema = SCHEMAS["criteo_uplift"]
        data = (",".join(schema.required) + "\n" + ",".join(["0"] * 16) + "\n").encode()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.gz"
            path.write_bytes(gzip.compress(data))
            batches = list(open_batches(path, schema))
            self.assertEqual(sum(len(table) for table, _ in batches), 1)
            broken = bytearray(path.read_bytes())
            broken[-8] ^= 1
            path.write_bytes(broken)
            with self.assertRaises(Exception):
                list(open_batches(path, schema))
            path.write_bytes(gzip.compress(data))
            with self.assertRaises(Exception):
                list(open_batches(path, schema, decompressed_limit=2))

    def test_nonbinary_and_invalid_propensity_quarantine(self):
        schema = SCHEMAS["obd_men"]
        table = pa.table({"click": [0., 1., 2.], "item_id": [1., 1., 1.], "position": [1., 1., 1.], "propensity_score": [.2, 0., .5]})
        valid, reasons = valid_rows(table, schema)
        self.assertEqual(valid.to_pylist(), [True, False, False])
        self.assertEqual(reasons, {"click": 1, "propensity_score": 1})

    def test_malformed_numeric_is_quarantined_without_losing_valid_rows(self):
        schema = SCHEMAS["criteo_uplift"]
        good = ["0"] * 16
        bad = good.copy()
        bad[0] = "malformed"
        text = ",".join(schema.required) + "\n" + ",".join(good) + "\n" + ",".join(bad) + "\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.gz"
            path.write_bytes(gzip.compress(text.encode()))
            batches = list(open_batches(path, schema))
            self.assertEqual(len(batches), 1)
            valid, reasons = valid_rows(batches[0][0], schema)
            self.assertEqual(valid.to_pylist(), [True, False])
            self.assertEqual(reasons, {"f0": 1})


if __name__ == "__main__":
    unittest.main()
