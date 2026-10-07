from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.agent_evidence import verified_pointer, verified_checkpoint, verified_model_files
from aurora.artifacts import atomic_json, digest


class AgentEvidenceTests(unittest.TestCase):
    def test_inline_pointer_claims_not_substituted_for_actual_payload(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            artifact, pointer = root / "actual.json", root / "pointer.json"
            atomic_json(artifact, {"passed": False})
            atomic_json(pointer, {"artifact": str(artifact), "sha256": digest(artifact), "passed": True})
            result, reference = verified_pointer(pointer, (root,))
            self.assertFalse(result["passed"])
            self.assertEqual(reference["sha256"], digest(artifact))
            atomic_json(artifact, {"passed": True})
            with self.assertRaises(ValueError):
                verified_pointer(pointer, (root,))

    def test_escape_missing_optimizer_and_corrupted_weight_refused(self):
        with tempfile.TemporaryDirectory() as name:
            runtime = Path(name)
            checkpoint = runtime / "runs" / "abstract" / "adapter"
            checkpoint.mkdir(parents=True)
            for filename in ("adapter_model.safetensors", "adapter_config.json"):
                (checkpoint / filename).write_text(json.dumps({"abstract": True}))
            optimizer = checkpoint.parent / "optimizer.json"
            atomic_json(optimizer, {"abstract_fixture_not_tensor": True})
            report = {"checkpoint": str(checkpoint), "checkpoint_hashes": {path.name: digest(path) for path in checkpoint.iterdir()}, "optimizer_state": {"path": str(optimizer), "sha256": digest(optimizer)}}
            verified_checkpoint(report, runtime)
            report["checkpoint_hashes"]["../escape"] = "a" * 64
            with self.assertRaises(ValueError):
                verified_checkpoint(report, runtime)
            del report["checkpoint_hashes"]["../escape"]
            report["optimizer_state"] = None
            with self.assertRaises(ValueError):
                verified_checkpoint(report, runtime)
            report["optimizer_state"] = {"path": str(optimizer), "sha256": digest(optimizer)}
            atomic_json(checkpoint / "adapter_model.safetensors", {"corrupted_abstract_fixture": True})
            with self.assertRaises(ValueError):
                verified_checkpoint(report, runtime)

    def test_pinned_actual_model_files_are_not_just_an_admission_label(self):
        with tempfile.TemporaryDirectory() as name:
            runtime = Path(name)
            model = runtime / "abstract_model"
            model.mkdir()
            atomic_json(model / "model.safetensors", {"abstract_fixture_not_model": True})
            atomic_json(model / "tokenizer_config.json", {"abstract_template": "fixed"})
            admission = {"model_directory": str(model), "weights_downloaded": True, "file_hashes": {path.name: digest(path) for path in model.iterdir()}}
            self.assertEqual(len(verified_model_files(admission, runtime)), 2)
            atomic_json(model / "tokenizer_config.json", {"abstract_template": "changed"})
            with self.assertRaises(ValueError):
                verified_model_files(admission, runtime)
