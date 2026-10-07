"""R3 authorization boundaries are distinct from generic acquisition caps."""
import importlib.util
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
spec = importlib.util.spec_from_file_location("r3_recovery", Path(__file__).resolve().parents[1] / "tools/recover_r3_source.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class R3ExceptionTests(unittest.TestCase):
    def test_backing_reserve_stop_preserves_partial(self):
        meter = module.DualReserveMeter(Path("/owned"), Path("/backing"), 20)
        with patch.object(module.shutil, "disk_usage", side_effect=[SimpleNamespace(free=100), SimpleNamespace(free=19)]):
            with self.assertRaises(ValueError):
                meter.charge(4)
        self.assertEqual(meter.used, 4)

    def test_original_large_object_only(self):
        source = {"id": "criteo_search", "license": "CC-BY-NC-SA-4.0", "max_total_download_bytes": 700_000_000}
        url = "https://go.criteo.net/criteo-research-search-conversion.tar.gz"
        headers = {"Content-Length": "2002864638", "Content-Type": "application/gzip"}
        self.assertEqual(module.validate_exception(source, url, headers, 200), 2002864638)
        self.assertEqual(source["max_total_download_bytes"], 700_000_000)
        for change in ({"Content-Length": "2100000001"}, {"Content-Length": ""}, {"Content-Type": "text/html"}, {"Content-Encoding": "gzip"}):
            with self.assertRaises(ValueError):
                module.validate_exception(source, url, headers | change, 200)

    def test_no_mirror_auth_or_other_source(self):
        source = {"id": "criteo_search", "license": "CC-BY-NC-SA-4.0", "max_total_download_bytes": 700_000_000}
        url = "https://go.criteo.net/criteo-research-search-conversion.tar.gz"
        headers = {"Content-Length": "2002864638"}
        for altered in (url.replace("https:", "http:"), url.replace("go.criteo.net", "mirror.example"), url + "?token=x", url.replace("go.criteo.net", "user:secret@go.criteo.net")):
            with self.assertRaises(ValueError):
                module.validate_exception(source, altered, headers, 200)
        with self.assertRaises(ValueError):
            module.validate_exception(source | {"id": "obd_men"}, url, headers, 200)
        with self.assertRaises(ValueError):
            module.validate_exception(source, url, headers, 401)
