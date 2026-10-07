from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.agent_evaluation import AgentCase, AgentOutcome, family_event_interval, matched_agent_comparison


class AgentEvaluationTests(unittest.TestCase):
    def fixture(self):
        cases = [AgentCase("a1", "a", "g1"), AgentCase("a2", "a", "g1"), AgentCase("b1", "b", "g2"), AgentCase("c1", "c", "g3")]
        seeds = [41, 73, 101]
        candidate = [AgentOutcome(case.identity, seed, case.workflow == "a", 0, 0, 0) for case in cases for seed in seeds]
        baseline = [AgentOutcome(case.identity, seed, False, 0, 0, 0) for case in cases for seed in seeds]
        return cases, seeds, {"a": "g1", "b": "g2", "c": "g3"}, candidate, baseline

    def test_groups_not_rows_or_seeds_and_underpower_preserved(self):
        args = self.fixture()
        result = matched_agent_comparison(*args, prospective_status="UNDERPOWERED", bootstrap_draws=100)
        self.assertEqual(result["independent_dependence_groups"], 3)
        self.assertEqual(result["case_seed_evaluations_per_arm"], 12)
        self.assertAlmostEqual(result["paired_group_success_contrast"]["mean"], 1 / 3)
        self.assertEqual(result["scientific_status"], "UNDERPOWERED")
        self.assertFalse(result["superiority_claim_authorized"])
        self.assertIsNone(result["shared_generator_sensitivity"]["interval"])
        risk = result["arms"]["candidate"]["safety"]["wrong_committed_actions"]
        self.assertGreater(risk["conditional_independent_family_one_sided_95pct_upper"], .6)

        # Even a uniformly favorable reference fixture cannot promote the
        # prospective UNDERPOWERED status or authorize a population claim.
        all_success = [AgentOutcome(item.case_identity, item.training_seed, True, 0, 0, 0) for item in args[3]]
        favorable = matched_agent_comparison(*args[:3], all_success, args[4], prospective_status="UNDERPOWERED", bootstrap_draws=100)
        self.assertTrue(favorable["directional_interval_above_zero"])
        self.assertEqual(favorable["scientific_status"], "UNDERPOWERED")
        self.assertFalse(favorable["superiority_claim_authorized"])

    def test_all_failures_and_matched_roster_required(self):
        cases, seeds, mapping, candidate, baseline = self.fixture()
        for wrong in (candidate[:-1], candidate + candidate[:1], candidate[:-1] + [AgentOutcome("unknown", 101, False, 0, 0, 0)]):
            with self.assertRaises(ValueError):
                matched_agent_comparison(cases, seeds, mapping, wrong, baseline, prospective_status="UNDERPOWERED")
        with self.assertRaises(ValueError):
            matched_agent_comparison(cases, seeds, mapping | {"omitted_workflow": "g3"}, candidate, baseline, prospective_status="UNDERPOWERED")
        with self.assertRaises(ValueError):
            matched_agent_comparison(cases, seeds, mapping | {"a": "g2"}, candidate, baseline, prospective_status="UNDERPOWERED")

    def test_safety_separate_not_hidden_by_success_or_guard(self):
        cases, seeds, mapping, candidate, baseline = self.fixture()
        candidate[0] = AgentOutcome("a1", 41, True, 2, 3, 0)
        result = matched_agent_comparison(cases, seeds, mapping, candidate, baseline, prospective_status="UNDERPOWERED", bootstrap_draws=100)
        safety = result["arms"]["candidate"]["safety"]
        self.assertEqual(safety["unsafe_proposals"]["event_count"], 2)
        self.assertEqual(safety["host_blocked_errors"]["event_count"], 3)
        self.assertEqual(safety["wrong_committed_actions"]["families_with_event"], 0)
        self.assertEqual(safety["unsafe_proposals"]["families_with_event"], 1)
        self.assertEqual(safety["unsafe_proposals"]["family_denominator"], 3)

    def test_exact_family_risk_endpoints_and_counter_validation(self):
        low, high = family_event_interval(0, 9)
        self.assertEqual(low, 0.)
        self.assertAlmostEqual((1 - high)**9, .025, places=12)
        self.assertEqual(family_event_interval(9, 9)[1], 1.)
        for count in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                AgentOutcome("case", 41, True, count, 0, 0)
        with self.assertRaises(ValueError):
            family_event_interval(10, 9)
