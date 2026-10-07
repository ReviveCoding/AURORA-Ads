import importlib.util
import unittest
from pathlib import Path

import duckdb

from aurora.data import SCHEMAS

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("r3_preparation_fixture", ROOT / "tools/prepare_r3_development.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class R3CohortQueryTests(unittest.TestCase):
    def test_half_open_query_and_missing_codes_with_eligible_fields_only(self):
        fields = SCHEMAS["criteo_search"].features
        connection = duckdb.connect()
        definitions = ",".join(f'\'-1\'::VARCHAR AS "{name}"' for name in fields)
        connection.execute(f"CREATE VIEW events AS SELECT {definitions},0. AS Sale,-1. AS time_delay_for_conversion,-1. AS SalesAmountInEuro,origin AS click_timestamp,CAST(uid AS VARCHAR) AS user_id FROM range(0,3) t(origin),range(0,128) u(uid)")
        frame = connection.execute(MODULE.cohort_query(fields), [0, 2]).fetchdf()
        self.assertGreater(len(frame), 0)
        self.assertTrue((frame.click_timestamp < 2).all())
        self.assertTrue((frame[list(fields)].to_numpy() == 0).all())
        self.assertNotIn("Sale", fields)
        with self.assertRaises(ValueError):
            MODULE.cohort_query((*fields, "Sale"))
