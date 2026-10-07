# Contributing to AURORA-Ads

Thanks for helping improve AURORA-Ads. This repository treats research validity, reproducibility, and evidence provenance as part of correctness.

## Before opening a change

1. Read the [README](README.md), [documentation index](docs/README.md), and [reproducibility notes](docs/REPRODUCIBILITY.md).
2. For scientific changes, state the estimand, data boundary, assumptions, and whether the change is prospective or post-hoc.
3. Do not commit raw/restricted datasets, model weights, credentials, machine-local receipts, or generated runtime state.
4. Do not rewrite closed v1 claims or results. Corrections to the closed record should be additive and clearly labeled as errata or new prospective work.

## Development setup

    python -m pip install --upgrade pip
    python -m pip install -e ".[dev]"

Run before submitting:

    ruff check src tests tools
    python -m pytest -q
    python tools/validate_design.py --no-hashes
    python -m pip check

## Pull requests

A focused pull request should:

- explain the problem and intended behavior,
- identify affected evidence or protocol boundaries,
- include regression tests for behavior changes,
- preserve fail-closed behavior for ambiguous integrity or safety states,
- avoid silently weakening thresholds, retry rules, or data-separation guarantees,
- update public documentation when user-facing behavior changes.

For research-result changes, include a short **Evidence impact** section explaining whether the change affects code only, a new prospective study, or an existing published claim.

## Issues

Use the structured issue templates for reproducible bugs and research/design questions. Security-sensitive reports should follow [SECURITY.md](SECURITY.md), not a public issue.

## Style

- Python 3.11 is the reference runtime.
- Ruff is the public lint gate.
- Prefer small, testable changes with explicit invariants.
- Keep generated outputs and machine-specific artifacts out of Git.
