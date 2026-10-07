import unittest

import numpy as np
import torch

from aurora.measurement import conditional_exponential_cdf
from aurora.r3_delay_models import conditional_cdf, exponential_log_likelihood


class R3ExponentialTests(unittest.TestCase):
    def test_conditional_cdf_matches_independent_FP64_reference(self):
        ages = torch.tensor([0., .5, 3., 7., 12.], dtype=torch.float64)
        rates = torch.tensor([-12., -3., 0., 2., 9.], dtype=torch.float64)
        reference = conditional_exponential_cdf(ages.numpy(), torch.nn.functional.softplus(rates).numpy())
        np.testing.assert_allclose(conditional_cdf(ages, rates).numpy(), reference, atol=1e-12, rtol=1e-12)

    def test_immediate_atom_mature_negative_and_gradient(self):
        q = torch.tensor([.2, .2, .2, .2], dtype=torch.float64, requires_grad=True)
        rate = torch.tensor([-8., -8., -8., -8.], dtype=torch.float64, requires_grad=True)
        atom = torch.zeros(4, dtype=torch.float64, requires_grad=True)
        value = exponential_log_likelihood(q, rate, atom, torch.tensor([0., 1., 7., 2.]),
                                           torch.tensor([0., -1., -1., 1.]))
        self.assertAlmostEqual(value[0].item(), torch.nn.functional.logsigmoid(q[0]).item() - np.log(2), places=12)
        self.assertAlmostEqual(value[2].item(), torch.nn.functional.logsigmoid(-q[2]).item(), places=12)
        (-value.sum()).backward()
        for gradient in (q.grad, rate.grad, atom.grad):
            self.assertTrue(torch.isfinite(gradient).all())

    def test_future_or_afterH_event_rejected(self):
        for delay, age in ((2., 1.), (8., 10.), (-2., 2.)):
            with self.assertRaises(ValueError):
                exponential_log_likelihood(torch.zeros(1), torch.zeros(1), torch.zeros(1),
                                           torch.tensor([age]), torch.tensor([delay]))
