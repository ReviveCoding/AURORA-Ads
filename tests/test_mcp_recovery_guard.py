from __future__ import annotations

import importlib.util
import json
import signal
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mcp_recovery_guard_fixture", ROOT / "tools/mcp_recovery_study.py")
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class MCPRecoveryGuardTests(unittest.TestCase):
    def setup_receipt(self, root):
        study = SimpleNamespace(directory=root, name="abstract_guard_fixture")
        command = [sys.executable, str(ROOT / "tools/mcp_server.py"), "--tenant", study.name, "--caller", "mcp_recovery", "--mock-preauthorized"]
        record = {"pid": 123456789, "start_ticks": "original", "expected_exec_command": command}
        return study, record, root / "receipt.json"

    def test_foreign_context_rejected_before_proc_inspection_or_signal(self):
        with tempfile.TemporaryDirectory() as name:
            study, record, receipt = self.setup_receipt(Path(name))
            record["expected_exec_command"][3] = "another_tenant"
            receipt.write_text(json.dumps(record))
            with patch.object(Path, "read_bytes") as read, patch.object(recovery.os, "kill") as kill:
                with self.assertRaises(ValueError):
                    recovery.kill_owned_server(receipt, study)
                read.assert_not_called()
                kill.assert_not_called()

    def test_start_tick_and_argv_match_required_even_for_owned_receipt(self):
        with tempfile.TemporaryDirectory() as name:
            study, record, receipt = self.setup_receipt(Path(name))
            command_bytes = b"\0".join(item.encode() for item in record["expected_exec_command"]) + b"\0"
            for start_ticks, may_signal in (("reused_pid", False), ("original", True)):
                stat = "123456789 (python) " + " ".join(["S", *(["0"] * 18), start_ticks])
                def contents(path, *args, **kwargs):
                    return json.dumps(record) if path == receipt else stat
                with patch.object(Path, "read_text", contents), patch.object(Path, "read_bytes", return_value=command_bytes), patch.object(recovery.os, "kill") as kill:
                    if may_signal:
                        recovery.kill_owned_server(receipt, study)
                        kill.assert_called_once_with(record["pid"], signal.SIGKILL)
                    else:
                        with self.assertRaises(ValueError):
                            recovery.kill_owned_server(receipt, study)
                        kill.assert_not_called()
