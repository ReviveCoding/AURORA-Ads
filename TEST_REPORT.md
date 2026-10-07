# AURORA-Ads v2 preparation validation report

Date: 2026-09-30.
This report describes **preparation utilities and design checks**, not AURORA ML results.

## Executed

- Original v1 package: ZIP CRC verification and 13 existing CPU helper tests passed during the audit.
- v2: **42 CPU-only unit/reference tests passed** in the preparation container.
- Python syntax compilation passed for all four delivered helper modules and the test module.
- Active design registry: **27 nodes**, acyclic/topologically ordered, optional iPinYou and GRPO excluded from core confirmation ancestors.
- Policy, agent, R1 and R3 confirmation paths have independent freezes; an agent failure does not block policy confirmation.
- `acquire_data.py` offline plan completed without publisher network access.
- Two exact PowerShell source bodies were parsed in the user's **PowerShell 7.6.6** via the PowerShell language parser; both had **zero syntax errors**. The bodies were decoded in memory and parsed, **not executed**.
- Local installed CLI help/version was read: **codex-cli 0.155.1**, with explicit `--approve-for-me` and `--strict-config` support.

Exact PowerShell source SHA-256 values validated by the remote parser:

| Script | SHA-256 |
|---|---|
| Start-Aurora.ps1 | f1aa215285d1379d40c6339dc3ec332895fafa3089f7e3ba377335fdb5b430b5 |
| Prepare-Aurora.ps1 | db681babb645b6572a87719fa58cf21b56b9a0259b7fb5e848b00ce66d043089 |

## What the 42 tests cover

Finite-horizon delay mass/CDF boundaries; guard-projected action-probability conservation; a hand-calculated DR identity;
ordinary spend and scarcity accounting; planning-power input checks; portable/unsafe paths; HTTPS source allowlist;
HTTP Range geometry; mock successful, restarted, resumed and truncated responses; changed ETag; quota counting;
HTML-as-data rejection; ambiguous landing links; symlink rejection; offline/no-network mode; runtime ownership,
no-write plan, idempotence, reserve space; DAG independence; manifest tamper rejection.

Mocked HTTP responses are not a successful network integration test.
Small algebraic identities are not statistical coverage qualification or policy training.

## Not executed / not established

- End-to-end PowerShell extraction/Git/WSL-runtime/interactive-TUI sequence on the user's machine.
- Actual dataset payload download, decompression/CRC/schema/clock admission.
- Publisher-side HTTP range/resume behavior; the container's metadata request failed DNS resolution.
- User dataset-license acknowledgment, model redistribution rights, or public release.
- ML dependency installation, exact package lock or CUDA/PyTorch/TRL compatibility.
- GPU memory, thermal or sustained-compute qualification. The GPU inventory is not a health test.
- AURORA model, bandit, agent, MCP service, simulator, release or hypothesis execution.
- Human labels, real customer experiments, production outcomes or actual advertising spend.

## Artifact integrity

`PACKAGE_MANIFEST.json` binds delivered source/docs/config bytes. The ZIP has a separately supplied SHA-256.
The manifest excludes itself; ZIP hashing avoids any self-referential checksum requirement.
The standalone bootstrap must be reviewed as executable code. The ZIP checksum does not authenticate a maliciously replaced bootstrap.

## Interpretation

Status: **DESIGN_AND_PREPARATION_CHECKS_PASSED_WITH_RUNTIME_LIMITATIONS**.
No claim of full end-to-end execution, production readiness, or scientific superiority is made.
