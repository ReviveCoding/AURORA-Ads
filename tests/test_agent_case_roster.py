from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.agent_case_roster import balanced_case_roster


class AgentCaseRosterTests(unittest.TestCase):
    def test_all_workflows_branches_group_balance_without_extra_units(self):
        mapping = {"abstract_a": "group_a", "abstract_b": "group_b", "abstract_c": "group_b"}
        cases = balanced_case_roster(mapping, cases_per_group=6, index_start=2000)
        self.assertEqual(Counter(case.semantic_group for case in cases), {"group_a": 6, "group_b": 6})
        self.assertEqual(len({case.identity for case in cases}), 12)
        for workflow in mapping:
            residues = {int(case.identity.rsplit("_", 1)[1]) % 3 for case in cases if case.workflow == workflow}
            self.assertEqual(residues, {0, 1, 2})
        self.assertEqual(len(set(mapping.values())), 2)

    def test_fractional_or_partial_branch_rosters_refused(self):
        for count in (0, 3, 5, 7, True, 6.):
            with self.assertRaises(ValueError):
                balanced_case_roster({"a": "g1", "b": "g2", "c": "g2"}, cases_per_group=count, index_start=2000)
