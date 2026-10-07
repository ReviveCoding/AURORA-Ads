# AURORA-Ads

**Evidence-controlled research for reliable agentic advertising systems**

AURORA-Ads is a research codebase for evaluating advertising decision systems under delayed outcomes, strict evidence boundaries, executable agent workflows, causal/off-policy analysis, and model-risk controls.

Version **v1.0.0** closes the first research program. The repository intentionally publishes source code, tests, design documentation, and curated result summaries while keeping raw/restricted datasets, model weights, machine-specific receipts, and internal execution artifacts local.

## v1 disposition

The v1 program is terminal. The published evidence supports a bounded research conclusion, not a production or business-lift claim.

- Development: 192 admitted observations across prompt-only, SFT, DPO, and IPO arms.
- Agent executable-success means were zero across development; DPO was selected by a predeclared tie-break, not by demonstrated task-success improvement.
- Supplemental held-out execution added 64 observations; the original paired confirmation remains incomplete and underpowered because one prompt-only case was permanently censored.
- R3 delayed-conversion evaluation did not establish neural superiority.
- Final descriptive logloss:
  - D1 mature logistic: **0.251955**
  - D2 finite-horizon feedback-shift: **0.252963**
  - D4 neural challenger: **0.254828**
- v1 post-hoc model-risk analysis found calibration drift, concentrated errors, structured challenger disagreement, value concentration, and material Agent operability risks.
- No real ad spend, production deployment, commercial lift, or regulatory qualification is claimed.

See [docs/results/v1](docs/results/v1/README.md) for the curated v1 evidence summary.

## Research areas

- delayed-conversion prediction and calibration
- causal inference and off-policy evaluation
- budget-constrained advertising simulation
- executable LLM/agent workflows with host-side controls
- model-risk analysis, residual slicing, calibration diagnostics, and challenger disagreement
- reproducibility, immutable evidence, and fail-closed experiment orchestration
- CPU/GPU serving characterization under explicit safety envelopes

## Repository layout

- `src/aurora/`: reusable research and evaluation modules
- `tests/`: CPU-compatible unit and regression tests
- `tools/`: study, audit, qualification, and reporting utilities
- `config/`: versioned configuration and contracts
- `docs/`: design documentation and curated public results
- `research/`: research notes and bounded study inputs

Local-only directories such as `reports/`, `extensions/`, raw data, runtime state, model weights, and checkpoints are deliberately excluded from Git.

## Installation

Python 3.11 is the reference version.

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The `dev` extra includes the CPU packages needed by the public test suite. CUDA experiments require a separately qualified local environment and are not exercised in GitHub Actions.

## Validation

```bash
python -m pytest -q
ruff check src tests tools
python tools/validate_design.py
```

CI runs these checks on Ubuntu with Python 3.11.

## Reproducibility and data boundaries

AURORA-Ads separates public source code from local evidence artifacts. Raw or restricted datasets are not redistributed. Model-bearing experiments use explicit hashes, frozen protocols, immutable receipts, and bounded recovery rules. The public repository does not contain the local datasets or trained model binaries used in the v1 studies.

Post-hoc diagnostics are explicitly labeled as post-hoc. They do not rewrite v1 model selection, thresholds, calibration, or claims. Any hypothesis carried into v2 must be prospectively frozen and evaluated on eligible new data.

## v2

The next research program starts from the v1 scientific closeout and v1 post-hoc model-risk register. Its first gates focus on:

1. executable Agent operability and evaluator/oracle correctness,
2. intent-only Agent integration with simulator-owned settlement,
3. prospective calibration maintenance,
4. stable high-risk and challenger-disagreement slices,
5. unique row identity and deterministic prediction provenance,
6. new-data-only replication and power-based confirmation.

## Safety and scope

This repository is for local research and evaluation. It does not authorize live advertising actions, real spend, production deployment, or claims of causal business lift.

## Release

See [CHANGELOG.md](CHANGELOG.md) and the GitHub release for v1.0.0 details.
