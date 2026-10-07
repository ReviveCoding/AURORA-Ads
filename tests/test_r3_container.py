import importlib.util
import sys
import tarfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
spec = importlib.util.spec_from_file_location("r3_container", Path(__file__).resolve().parents[1] / "tools/inspect_r3_container.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class R3ContainerTests(unittest.TestCase):
    def test_portable_and_case_duplicate(self):
        seen = set()
        self.assertEqual(module.validate_member(tarfile.TarInfo("source/data.tsv"), seen), "source/data.tsv")
        with self.assertRaises(ValueError):
            module.validate_member(tarfile.TarInfo("SOURCE/data.tsv"), seen)

    def test_links_and_traversal_refused(self):
        for name in ("../escape", "/absolute", "C:/device", "source/CON.txt"):
            with self.assertRaises(ValueError):
                module.validate_member(tarfile.TarInfo(name), set())
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE):
            member = tarfile.TarInfo("source/link")
            member.type = kind
            with self.assertRaises(ValueError):
                module.validate_member(member, set())
