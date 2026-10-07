# AURORA-Ads

[![CI](https://github.com/ReviveCoding/AURORA-Ads/actions/workflows/ci.yml/badge.svg)](https://github.com/ReviveCoding/AURORA-Ads/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/ReviveCoding/AURORA-Ads)](https://github.com/ReviveCoding/AURORA-Ads/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Research status](https://img.shields.io/badge/research-v1%20closed-5B5BD6)](docs/results/v1/README.md)

**Evidence-controlled research for reliable agentic advertising systems**

AURORA-Ads is a research codebase for evaluating advertising decision systems under delayed outcomes, strict evidence boundaries, executable agent workflows, causal/off-policy analysis, and model-risk controls.

Version **v1.0.0** closes the first research program. The repository publishes source code, tests, design documentation, and curated result summaries while keeping raw/restricted datasets, model weights, machine-specific receipts, and internal execution artifacts local.

## At a glance

| Area | v1 disposition |
| --- | --- |
| Agent development | 192 admitted observations across prompt-only, SFT, DPO, and IPO |
| Agent held-out | 43 prompt-only + 44 DPO valid observations; original paired confirmation remains incomplete/underpowered |
| Agent task success | Zero executable-success mean; DPO selected by predeclared tie-break, not demonstrated superiority |
| R3 final | 286,467 frozen final rows |
| Final logloss | D1 **0.251955**, D2 **0.252963**, D4 **0.254828** |
| Neural challenger | D4 superiority **not established** |
| Post-hoc model risk | Calibration drift, concentrated error, structured disagreement, materiality concentration, Agent operability/safety risk |
| Production claim | None: no live spend, commercial lift, production reliability, or regulatory qualification |

## Quick links

| Resource | Purpose |
| --- | --- |
| [v1 evidence summary](docs/results/v1/README.md) | Curated scientific disposition and headline metrics |
| [v1 claims ledger](docs/results/v1/CLAIMS.md) | What v1 does and does not support |
| [v1 model-risk summary](docs/results/v1/MODEL_RISK.md) | Calibration, slicing, disagreement, and Agent risk |
| [Reproducibility](docs/REPRODUCIBILITY.md) | Public/local artifact boundaries and reproducibility expectations |
| [Simulator contract](docs/SIMULATOR_CONTRACT.md) | State, settlement, and simulator semantics |
| [Final specification](docs/FINAL_SPEC.md) | Research-system specification |
| [Documentation index](docs/README.md) | Map of public technical documentation |
| [Changelog](CHANGELOG.md) | Version history |
| [v1.0.0 release](https://github.com/ReviveCoding/AURORA-Ads/releases/tag/v1.0.0) | Source release and curated evidence bundle |

## Research areas

- delayed-conversion prediction and calibration
- causal inference and off-policy evaluation
- budget-constrained advertising simulation
- executable LLM/agent workflows with host-side controls
- model-risk analysis, residual slicing, calibration diagnostics, and challenger disagreement
- reproducibility, immutable evidence, and fail-closed experiment orchestration
- CPU/GPU serving characterization under explicit safety envelopes

## Repository layout

    src/aurora/        reusable research and evaluation modules
    tests/             CPU-compatible unit and regression tests
    tools/             study, audit, qualification, and reporting utilities
    config/            versioned configuration and contracts
    docs/              specifications, reproducibility notes, and curated results
    research/          bounded research notes and inputs
    .github/           CI, contribution workflow, issue templates, and ownership

Local-only directories such as reports/, extensions/, raw data, runtime state, model weights, and checkpoints are deliberately excluded from Git.

## Installation

Python 3.11 is the reference version.

    python -m pip install --upgrade pip
    python -m pip install -e ".[dev]"

The dev extra includes the CPU packages needed by the public test suite. CUDA experiments require a separately qualified local environment and are not exercised in GitHub Actions.

## Validation

Run the same public checks used by CI:

    ruff check src tests tools
    python -m pytest -q
    python tools/validate_design.py --no-hashes
    python -m pip check

CI runs these checks on Ubuntu with Python 3.11 and CPU PyTorch.

## Reproducibility and evidence boundaries

AURORA-Ads separates public source code from local evidence artifacts. Raw or restricted datasets are not redistributed. Model-bearing experiments use explicit hashes, frozen protocols, immutable receipts, and bounded recovery rules. The public repository does not contain the local datasets or trained model binaries used in the v1 studies.

Post-hoc diagnostics are explicitly labeled as post-hoc. They do not rewrite v1 model selection, thresholds, calibration, or claims. Any hypothesis carried into v2 must be prospectively frozen and evaluated on eligible new data.

## v2 direction

The next research program starts from the v1 scientific closeout and v1 post-hoc model-risk register. Its first gates focus on:

1. executable Agent operability and evaluator/oracle correctness,
2. intent-only Agent integration with simulator-owned settlement,
3. prospective calibration maintenance,
4. stable high-risk and challenger-disagreement slices,
5. unique row identity and deterministic prediction provenance,
6. new-data-only replication and power-based confirmation.

## Contributing, security, and citation

- Read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing code or research changes.
- Report security-sensitive issues through GitHub private vulnerability reporting; see [SECURITY.md](SECURITY.md).
- Cite the software using [CITATION.cff](CITATION.cff).

## Safety and scope

This repository is for local research and evaluation. It does not authorize live advertising actions, real spend, production deployment, or claims of causal business lift.

## Release

See [CHANGELOG.md](CHANGELOG.md) and the [v1.0.0 GitHub release](https://github.com/ReviveCoding/AURORA-Ads/releases/tag/v1.0.0).

> **Licensing note:** v1.0.0 does not include an open-source license file. Check the repository's current licensing status before reuse or redistribution.
