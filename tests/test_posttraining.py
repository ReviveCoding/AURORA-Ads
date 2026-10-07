from __future__ import annotations

import math
import copy
import io
import tempfile
import sys
import unittest
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aurora.posttraining import assistant_labels, completion_logp, suffix_completion_logp, preference_loss


class PosttrainingTests(unittest.TestCase):
    def test_suffix_projection_matches_full_context_loss_and_gradients(self):
        from transformers import Qwen3Config, Qwen3ForCausalLM
        torch.manual_seed(713)
        model = Qwen3ForCausalLM(Qwen3Config(vocab_size=31, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2, head_dim=8, max_position_embeddings=64, attention_dropout=0., use_cache=False)).float().eval()
        ids = torch.randint(0, 31, (1, 15))
        for average in (False, True):
            full = completion_logp(model(input_ids=ids).logits, ids, 11, average=average)
            full.backward()
            gradients = {name: p.grad.clone() for name, p in model.named_parameters() if p.grad is not None}
            model.zero_grad(set_to_none=True)
            suffix = suffix_completion_logp(model, ids, 11, average=average)
            torch.testing.assert_close(suffix, full.detach(), rtol=1e-6, atol=1e-6)
            suffix.backward()
            for name, p in model.named_parameters():
                if name in gradients:
                    torch.testing.assert_close(p.grad, gradients[name], rtol=1e-5, atol=1e-6)
            model.zero_grad(set_to_none=True)
        original = model(input_ids=ids, labels=assistant_labels(ids, 11)).loss
        torch.testing.assert_close(-suffix_completion_logp(model, ids, 11, average=True), original, rtol=1e-6, atol=1e-6)

    def test_independent_optimizer_replays_reload_immutable_bytes(self):
        parameter = torch.nn.Parameter(torch.tensor([1.], dtype=torch.float32))
        optimizer = torch.optim.AdamW([parameter], lr=.01)
        parameter.square().sum().backward()
        optimizer.step()
        initial = parameter.detach().clone()
        buffer = io.BytesIO()
        torch.save(optimizer.state_dict(), buffer)
        immutable_bytes = buffer.getvalue()
        results = []
        for _ in range(2):
            fresh = torch.nn.Parameter(initial.clone())
            replay = torch.optim.AdamW([fresh], lr=.01)
            restored = torch.load(io.BytesIO(immutable_bytes), weights_only=True)
            replay.load_state_dict(restored)
            self.assertEqual(int(replay.state[fresh]["step"]), 1)
            fresh.square().sum().backward()
            replay.step()
            self.assertEqual(int(replay.state[fresh]["step"]), 2)
            results.append(fresh.detach().clone())
        torch.testing.assert_close(results[0], results[1], rtol=0, atol=0)
        final = torch.load(io.BytesIO(immutable_bytes), weights_only=True)
        self.assertEqual(int(next(iter(final["state"].values()))["step"]), 1)

    def test_dpo_ipo_against_independent_fp64_scalar_formulas(self):
        chosen = torch.tensor(-3., dtype=torch.float64, requires_grad=True)
        rejected = torch.tensor(-7., dtype=torch.float64, requires_grad=True)
        reference_c, reference_r = torch.tensor(-4., dtype=torch.float64), torch.tensor(-6., dtype=torch.float64)
        ratio = 2.
        for objective in ("dpo", "ipo"):
            loss = preference_loss(chosen, rejected, reference_c, reference_r, objective=objective)
            expected = math.log1p(math.exp(-.1 * ratio)) if objective == "dpo" else (ratio - 5.) ** 2
            self.assertAlmostEqual(float(loss.detach()), expected, places=13)
            dc, dr = torch.autograd.grad(loss, (chosen, rejected), retain_graph=True)
            derivative = -.1 / (1 + math.exp(.1 * ratio)) if objective == "dpo" else 2 * (ratio - 5.)
            self.assertAlmostEqual(float(dc), derivative, places=13)
            self.assertAlmostEqual(float(dr), -derivative, places=13)

    def test_sequential_recompute_gradient_equals_joint_graph(self):
        for objective in ("dpo", "ipo"):
            w = torch.tensor(.3, dtype=torch.float64, requires_grad=True)
            loss = preference_loss(2 * w, -3 * w, torch.tensor(0.), torch.tensor(0.), objective=objective)
            reference = torch.autograd.grad(loss, w)[0]
            a, b = torch.tensor(float(2 * w.detach()), dtype=torch.float64, requires_grad=True), torch.tensor(float(-3 * w.detach()), dtype=torch.float64, requires_grad=True)
            dc, dr = torch.autograd.grad(preference_loss(a, b, torch.tensor(0.), torch.tensor(0.), objective=objective), (a, b))
            sequential = dc * 2 + dr * -3
            torch.testing.assert_close(reference, sequential, rtol=0, atol=1e-14)

    def test_prefix_mask_and_completion_only_log_probability(self):
        ids = torch.tensor([[0, 1, 2, 1]])
        labels = assistant_labels(ids, 2)
        self.assertEqual(labels.tolist(), [[-100, -100, 2, 1]])
        logits = torch.zeros((1, 4, 3))
        self.assertAlmostEqual(float(completion_logp(logits, ids, 2)), -2 * math.log(3), places=6)
        self.assertAlmostEqual(float(completion_logp(logits, ids, 2, average=True)), -math.log(3), places=6)

    def test_optimizer_boundary_resume_replays_only_uncommitted_microbatches(self):
        # CPU reference for the persisted AdamW/RNG/sampler boundary mechanism,
        # not a claim that a real CUDA adapter has already survived a restart.
        torch.manual_seed(713)
        initial = torch.nn.Linear(3, 1, dtype=torch.float64)
        initial_state = copy.deepcopy(initial.state_dict())
        data = torch.randn(12, 3, dtype=torch.float64)
        targets = torch.randn(12, 1, dtype=torch.float64)
        initial_rng = torch.get_rng_state().clone()
        order = list(range(12))
        def setup():
            model = torch.nn.Linear(3, 1, dtype=torch.float64)
            model.load_state_dict(initial_state)
            return model, torch.optim.AdamW(model.parameters(), lr=.01)
        def microbatches(model, optimizer, start, stop):
            for position in range(start, stop):
                # Stochastic input exercises RNG restoration, unlike dropout0
                # training where an incorrect RNG checkpoint can go unnoticed.
                sample = data[order[position]] + .01 * torch.randn(3, dtype=torch.float64)
                loss = (model(sample) - targets[order[position]]).square().mean()
                (loss / 4).backward()
                if (position + 1) % 4 == 0:
                    optimizer.step()
                    optimizer.zero_grad(set_to_none=True)
        complete, complete_optimizer = setup()
        torch.set_rng_state(initial_rng)
        microbatches(complete, complete_optimizer, 0, 12)
        partial, partial_optimizer = setup()
        torch.set_rng_state(initial_rng)
        microbatches(partial, partial_optimizer, 0, 4)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "optimizer_boundary.pt"
            torch.save({"weights": partial.state_dict(), "optimizer": partial_optimizer.state_dict(), "cpu_rng": torch.get_rng_state(), "next_position": 4, "order": order}, path)
            microbatches(partial, partial_optimizer, 4, 7)  # uncommitted gradients discarded
            restored = torch.load(path, weights_only=True)
            resumed, resumed_optimizer = setup()
            resumed.load_state_dict(restored["weights"])
            resumed_optimizer.load_state_dict(restored["optimizer"])
            torch.set_rng_state(restored["cpu_rng"])
            self.assertEqual(restored["order"], order)
            microbatches(resumed, resumed_optimizer, restored["next_position"], 12)
        for actual, expected in zip(resumed.parameters(), complete.parameters()):
            torch.testing.assert_close(actual, expected, rtol=0, atol=0)
        for key, expected in complete_optimizer.state_dict()["state"].items():
            actual = resumed_optimizer.state_dict()["state"][key]
            for field in ("step", "exp_avg", "exp_avg_sq"):
                torch.testing.assert_close(actual[field], expected[field], rtol=0, atol=0)
