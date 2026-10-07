import unittest

from aurora.final_evidence import core_empirical_complete, final_reporting_gate, saved_record, unavailable_record


class FinalEvidenceTests(unittest.TestCase):
    def record(self):
        return {"record_status": "MEASURED", "evidence_domain": "FIXTURE", "estimand_id": "fixture",
            "comparison_id": "fixture", "candidate": "candidate", "baseline": "baseline", "population": "fixture",
            "metric": "utility", "estimate": -.2, "difference": -.3, "unit": "normalized utility", "horizon": "fixture14+7",
            "n_independent_units": 8, "independent_unit": "world", "uncertainty_method": "fixture paired world",
            "ci_lower": -.4, "ci_upper": -.1, "source_hashes": ["a"*64], "config_hash": "a"*64,
            "model_calibrator_id": "fixture", "scientific_outcome": "UNDERPOWERED", "execution_status": "EXECUTED",
            "scope_limits": ["Synthetic fixture, not research"]}

    def export(self, row, target="difference"):
        return saved_record(row, artifact="fixture.json", sha256="a"*64, location="/fixture",
                            evidence_class="SYNTHETIC_FIXTURE_NOT_RESEARCH", role="FIXTURE", interval_target=target)

    def test_retains_negative_outcome_and_interval_target_without_mutation(self):
        record = self.record()
        exported = self.export(record)
        self.assertEqual(exported["scientific_outcome"], "UNDERPOWERED")
        self.assertEqual(exported["difference"], -.3)
        self.assertEqual(exported["interval_target"], "difference")
        self.assertNotIn("artifact", record)
        exported["scope_limits"].append("export note")
        self.assertEqual(len(record["scope_limits"]), 1)

    def test_missing_is_not_zero_and_invalid_numerics_rejected(self):
        exported = self.export(self.record() | {"difference": None, "ci_lower": None, "ci_upper": None}, "UNAVAILABLE")
        self.assertIsNone(exported["difference"])
        descriptive = self.export(self.record() | {"n_independent_units": None, "ci_lower": None, "ci_upper": None}, "UNAVAILABLE")
        self.assertIsNone(descriptive["n_independent_units"])
        with self.assertRaises(ValueError):
            self.export(self.record() | {"n_independent_units": None})
        for key, value in (("estimate", float("nan")), ("estimate", True), ("n_independent_units", True), ("n_independent_units", 0), ("ci_lower", None)):
            with self.assertRaises(ValueError):
                self.export(self.record() | {key: value})

    def test_contrast_cannot_be_replaced_by_absolute_interval_or_planned_number(self):
        with self.assertRaises(ValueError):
            self.export(self.record() | {"difference": None})
        with self.assertRaises(ValueError):
            self.export(self.record() | {"execution_status": "PENDING"})
        with self.assertRaises(ValueError):
            self.export(self.record() | {"evidence_domain": "R1"})

    def test_no_final_reporting_while_empirical_run_active_or_unfinished(self):
        state = {"nodes": {"A": {"execution_status": "EXECUTED"}, "E16": {"execution_status": "PENDING"}}}
        final_reporting_gate(state, active_owned_compute=[])
        with self.assertRaises(ValueError):
            final_reporting_gate(state, active_owned_compute=[123])
        state["nodes"]["A"]["execution_status"] = "RUNNING"
        with self.assertRaises(ValueError):
            final_reporting_gate(state, active_owned_compute=[])

    def test_blocked_track_is_unmeasured_and_forbids_empirical_complete(self):
        blocked = {"execution_status": "BLOCKED_HARDWARE", "scientific_outcome": "BLOCKED_HARDWARE",
            "reason": "Frozen monitoring hold", "artifacts": [{"path": "fixture", "sha256": "a"*64}]}
        result = unavailable_record("A", blocked, evidence_class="BLOCKED_RESOURCE")
        self.assertIsNone(result["estimate"])
        self.assertIsNone(result["n_independent_units"])
        registry = [{"id": "A", "scope": "core"}]
        self.assertFalse(core_empirical_complete(registry, {"nodes": {"A": blocked}}))


if __name__ == "__main__":
    unittest.main()
