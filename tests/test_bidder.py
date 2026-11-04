import unittest

import numpy as np
from scipy.integrate import quad
from scipy.stats import lognorm

from aurora.bidder import (
    GRID,
    calibrated_linear_bid,
    censored_market_nll,
    grid_bid_forecast,
)


class BidderTest(unittest.TestCase):
    def test_price_integrals_against_independent_quadrature(self):
        mu, sd, value = 0.2, 0.6, 1.1
        second = grid_bid_forecast(
            value_if_exposed=value,
            log_price_mean=mu,
            log_price_sd=sd,
            payment_mode="second_price",
        )
        first = grid_bid_forecast(
            value_if_exposed=value,
            log_price_mean=mu,
            log_price_sd=sd,
            payment_mode="first_price",
        )
        price = lognorm(s=sd, scale=np.exp(mu))
        expected = [
            quad(lambda m: m * price.pdf(m), 0.0, b, epsabs=1e-10)[0] for b in GRID
        ]
        np.testing.assert_allclose(
            second.expected_payment, expected, rtol=1e-8, atol=1e-10
        )
        np.testing.assert_allclose(first.expected_payment, GRID * price.cdf(GRID))
        np.testing.assert_allclose(second.score, value * price.cdf(GRID) - expected)
        zero = grid_bid_forecast(
            value_if_exposed=0.0,
            log_price_mean=mu,
            log_price_sd=sd,
            payment_mode="second_price",
        )
        self.assertEqual(zero.choice, 0.0)

    def test_censored_reference_and_no_loser_market_input(self):
        price = lognorm(s=0.4, scale=1.0)
        actual = censored_market_nll(
            [0.0, 0.0],
            0.4,
            [0.8, 1.5],
            np.array([False, True]),
            [0.0, 1.0001],
            payment_mode="second_price",
        )
        expected = (
            -(np.log(price.sf(0.8)) + np.log(price.cdf(1.0001) - price.cdf(1.0))) / 2
        )
        self.assertAlmostEqual(actual, expected, places=8)
        actual = censored_market_nll(
            [0.0, 0.0],
            0.4,
            [0.8, 1.5],
            np.array([False, True]),
            [0.0, 1.5],
            payment_mode="first_price",
        )
        expected = -(np.log(price.sf(0.8)) + np.log(price.cdf(1.5))) / 2
        self.assertAlmostEqual(actual, expected)
        actual = censored_market_nll(
            [0.0],
            0.4,
            [0.50005],
            np.array([True]),
            [0.5001],
            payment_mode="second_price",
        )
        expected = -np.log(price.cdf(0.50005) - price.cdf(0.5))
        self.assertAlmostEqual(actual, expected, places=8)
        # Stable extreme right-tail quantization interval, no silent clipping.
        extreme = censored_market_nll(
            [-20.0], 0.4, [1.5], np.array([True]), [1.0001], payment_mode="second_price"
        )
        self.assertTrue(np.isfinite(extreme))
        with self.assertRaises(ValueError):
            censored_market_nll(
                [0.0], 0.4, [1.0], np.array([False]), [2.0], payment_mode="second_price"
            )

    def test_finite_grid_and_extra_scarcity_cost(self):
        self.assertEqual(calibrated_linear_bid(0.9), 0.75)
        self.assertEqual(calibrated_linear_bid(100.0), 3.0)
        ordinary = grid_bid_forecast(
            value_if_exposed=2.0,
            log_price_mean=0.0,
            log_price_sd=0.4,
            payment_mode="second_price",
        )
        scarce = grid_bid_forecast(
            value_if_exposed=2.0,
            log_price_mean=0.0,
            log_price_sd=0.4,
            payment_mode="second_price",
            scarcity_price=1.0,
        )
        np.testing.assert_allclose(
            scarce.score, ordinary.score - ordinary.expected_payment
        )


if __name__ == "__main__":
    unittest.main()
