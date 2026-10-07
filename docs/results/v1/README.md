# AURORA-Ads v1 Results

This directory contains a curated public summary of the v1 research program. It is derived from immutable local scientific and post-hoc artifacts, but excludes raw/restricted datasets, model binaries, detailed machine-local receipts, and private execution state.

## Scientific closeout

### Agent evaluation
- Development: 192 admitted observations, 48 per arm.
- Development family-macro executable-success mean: 0 for prompt-only, SFT, DPO, and IPO.
- DPO was selected by the predeclared tie-break after equal zero success means.
- Supplemental held-out: 43 valid prompt-only observations and 44 DPO observations.
- Matched held-out comparison: 43 pairs across nine semantic dependence groups.
- Original confirmation remains incomplete and UNDERPOWERED.

### R3 delayed-conversion comparison
Final released cohort:
- rows: 286,467
- known 7-day labels: 286,381
- unknown labels: 86
- origin days: 70 through 81

Final descriptive metrics:

| Model | Logloss | Brier | AUROC | PR-AUC |
|---|---:|---:|---:|---:|
| D1 mature logistic | 0.251955 | 0.069688 | 0.737733 | 0.183870 |
| D2 finite-horizon feedback-shift | 0.252963 | n/a | n/a | n/a |
| D4 neural challenger | 0.254828 | n/a | n/a | n/a |

D4 superiority was **not established**.

## Post-hoc model-risk findings

The post-hoc appendix is diagnostic only. It does not change v1 selection or claims.

- D1 mean prediction 0.09031 vs prevalence 0.07973.
- D1 calibration slope 0.9481.
- Fixed-bin ECE increased from 0.00412 on selection to 0.01059 on final.
- Worst 5% of D1 rows contributed about 49.5% of total logloss; worst 10% about 69.9%.
- D1-D4 mean absolute prediction disagreement was about 0.0231, with p99 about 0.1276.
- Top 1% of users by observed benchmark value accounted for about 54.4% of observed 7-day value.
- Across 279 authoritative admitted Agent cases, executable success remained 0.
- The admitted Agent evidence included 11 unsafe proposals, one wrong committed action, and 144 host-blocked errors.

## Interpretation

These are bounded research results. Rows are not independent people, temporal dependence remains, and observed benchmark value is not causal lift or live P&L. Monitoring bands and recalibration experiments from the post-hoc analysis are hypotheses for prospective v2 evaluation, not deployable v1 rules.

See:
- [MODEL_RISK.md](MODEL_RISK.md)
- [CLAIMS.md](CLAIMS.md)
- [RESULTS.csv](RESULTS.csv)
