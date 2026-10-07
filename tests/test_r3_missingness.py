import itertools
import unittest

import numpy as np

from aurora.r3_missingness import binary_score_bounds, paired_logloss_bounds


class MissingnessTests(unittest.TestCase):
    def test_bounds_match_every_unknown_label_assignment(self):
        label = np.array([1., np.nan, 0., np.nan])
        candidate, comparator = np.array([.8, .7, .1, .3]), np.array([.6, .4, .2, .6])
        losses, contrasts = [], []
        for assignment in itertools.product((0., 1.), repeat=2):
            complete = label.copy()
            complete[np.isnan(complete)] = assignment
            left = -(complete * np.log(candidate) + (1 - complete) * np.log1p(-candidate))
            right = -(complete * np.log(comparator) + (1 - complete) * np.log1p(-comparator))
            losses.append(left.mean())
            contrasts.append((left - right).mean())
        bounds = binary_score_bounds(label, candidate)
        self.assertAlmostEqual(bounds["full_cohort_logloss_lower"], min(losses))
        self.assertAlmostEqual(bounds["full_cohort_logloss_upper"], max(losses))
        np.testing.assert_allclose(paired_logloss_bounds(label, candidate, comparator), [min(contrasts), max(contrasts)], atol=1e-15)
        self.assertEqual(bounds["known_outcome_n"], 2)

    def test_no_unknown_outcomes_collapses_bounds(self):
        bounds = binary_score_bounds(np.array([1., 0.]), np.array([.8, .2]))
        self.assertEqual(bounds["full_cohort_logloss_lower"], bounds["full_cohort_logloss_upper"])
        self.assertEqual(bounds["unknown_outcome_n"], 0)
