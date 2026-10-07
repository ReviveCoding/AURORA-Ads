from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.agent_ablation import INPUT_VARIANTS, ablated_messages, ablation_prefix_encoder, development_ablation_subset
from aurora.agent import messages


class AgentAblationTests(unittest.TestCase):
    def test_frozen_default_unchanged_and_full_phase_contract_preserved(self):
        task = SimpleNamespace(family="metric_lookup", category="analytic", prompt="UNIT abstract prompt, not a final scenario")
        self.assertEqual(ablated_messages(task, [], "frozen_full_context"), messages(task, []))
        class Tokenizer:
            def apply_chat_template(self, messages, **kwargs):
                self.kwargs = kwargs
                self.messages = messages
                return [1, 2]
        tool_schemas = []
        for variant in INPUT_VARIANTS:
            tokenizer = Tokenizer()
            self.assertEqual(ablation_prefix_encoder(variant)(tokenizer, task, []), [1, 2])
            self.assertFalse(tokenizer.kwargs["enable_thinking"])
            tool_schemas.append(tokenizer.kwargs["tools"])
        self.assertEqual(tool_schemas[0], tool_schemas[1])
        self.assertEqual(tool_schemas[1], tool_schemas[2])

    def test_subset_is_complete_development_only_and_no_extra_groups(self):
        items = [{"task": {"family": family, "task_id": "validation_" + family + "_" + str(number), "split": "validation"}, "semantic_group": "g_" + family} for family in ("abstract_a", "abstract_b") for number in range(1000, 1005)]
        result = development_ablation_subset(items)
        self.assertEqual(len(result), 6)
        self.assertEqual(len({item["semantic_group"] for item in result}), 2)
        with self.assertRaises(ValueError):
            development_ablation_subset(items + [{"task": {"family": "abstract_final", "task_id": "final_abstract_final_2000", "split": "final"}, "semantic_group": "final_g"}])
        with self.assertRaises(ValueError):
            ablation_prefix_encoder("remove_host_guards")
