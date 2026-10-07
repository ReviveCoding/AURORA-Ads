import unittest

import numpy as np
from scipy.sparse import csr_matrix
from scipy.optimize import check_grad

from aurora.r3_sparse_exponential import likelihood_gradient, sparse_objective


class SparseExponentialTests(unittest.TestCase):
    def test_analytical_gradient_with_partial_and_mature_rows(self):
        matrix = csr_matrix([[1., 0.], [0., 1.], [1., 1.], [0., 0.]])
        age, delay = np.array([1., 3., 7., 10.]), np.array([.5, -1., -1., 6.])
        weights = np.array([.2, -.4, -2., .3, -.2, -.5])
        error = check_grad(lambda w: sparse_objective(w, matrix, age, delay, 1e-4)[0],
                           lambda w: sparse_objective(w, matrix, age, delay, 1e-4)[1], weights)
        self.assertLess(error, 2e-7)

    def test_independent_density_and_complete_horizon(self):
        q, rate = .2, .5
        rate_logit = np.log(np.expm1(rate))
        loss, dq, db = likelihood_gradient(np.full(3, np.log(q/(1-q))), np.full(3, rate_logit),
            np.array([1., 7., 0.]), np.array([.5, -1., -1.]))
        self.assertAlmostEqual(loss[0], -np.log(q*rate*np.exp(-rate*.5)/(1-np.exp(-rate*7))))
        self.assertAlmostEqual(loss[1], -np.log(1-q))
        self.assertAlmostEqual(loss[2], 0.)
        self.assertEqual(db[1], 0.)
        self.assertAlmostEqual(dq[2], 0.)

    def test_small_rate_limit_and_invalid_future(self):
        loss, dq, db = likelihood_gradient(np.array([0., 0.]), np.array([-100., -100.]),
            np.array([3., 7.]), np.array([-1., 2.]))
        np.testing.assert_allclose(loss, [-np.log(1-.5*3/7), -np.log(.5/7)], atol=1e-12)
        self.assertTrue(np.isfinite(dq).all() and np.isfinite(db).all())
        for event in (0., 2.):
            with self.assertRaises(ValueError):
                likelihood_gradient(np.zeros(1), np.zeros(1), np.ones(1), np.array([event]))


if __name__ == "__main__":
    unittest.main()
