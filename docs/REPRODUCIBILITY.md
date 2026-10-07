# Reproducibility and Evidence Boundaries

AURORA-Ads uses a split between public source code and local experimental evidence.

## Public repository

The GitHub repository contains:
- source code and tests,
- study and audit utilities,
- design/configuration files,
- curated v1 summaries.

## Local-only evidence

The following are intentionally not distributed:
- raw or restricted datasets,
- trained model binaries and checkpoints,
- detailed runtime receipts and monitor streams,
- machine-specific paths and process metadata,
- intermediate failed-attempt directories,
- private/local execution state.

## Reproducibility rules

Scientific runs use frozen inputs, source hashes, explicit budgets, immutable receipts, and fail-closed recovery. Valid scientific outcomes are counted once and are not retried because of unfavorable results.

v1 post-hoc diagnostics are separate from the frozen v1 scientific selection. Post-hoc recalibration, thresholds, slice rules, or challenger policies may only become part of v2 after a new prospective freeze and eligible evaluation.

## Row identity

The v1 post-hoc audit identified a row-attribution hazard when non-unique sort keys were evaluated with parallel query execution. Reproducing the historical single-thread query restored exact row/label alignment. Future protocols should store a globally unique, frozen row identifier with every prediction artifact.
