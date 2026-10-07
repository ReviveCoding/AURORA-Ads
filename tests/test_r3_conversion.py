import importlib.util
import io
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("r3_conversion", Path(__file__).resolve().parents[1] / "tools/convert_r3_source.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class R3ConversionTests(unittest.TestCase):
    def test_no_header_first_record_and_sentinel_preserved(self):
        row = ["-1"] * 23
        row[0], row[3], row[5], row[7] = "0", "1598891820", "0.0", "hashed_device"
        options = module.reader_options()
        reader = module.csv.open_csv(io.BytesIO(("\t".join(row) + "\n").encode()),
                                    read_options=options[0], parse_options=options[1], convert_options=options[2])
        table = module.numeric_table(next(reader))
        self.assertEqual(len(table), 1)
        self.assertEqual(table["click_timestamp"][0].as_py(), 1598891820)
        self.assertEqual(table["SalesAmountInEuro"][0].as_py(), -1)
        self.assertEqual(table["device_type"][0].as_py(), "hashed_device")
