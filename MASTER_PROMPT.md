# AURORA-Ads implementation master prompt

You are now receiving the separate implementation instruction that `AGENTS.md` was waiting for. Implement and execute AURORA-Ads end to end in this repository, using the reviewed v2 scientific design as the controlling specification.

## 0. Objective and operating mode

Your objective is to turn the current design/preparation bundle into a complete, evidence-controlled local research project that implements, runs, analyzes, and documents the AURORA-Ads framework and experiments as far as the available public data, hardware, licenses, and statistically valid evidence allow.

Do not stop after scaffolding. Continue through implementation, data admission, modeling, experiments, ablations, serving qualification, final analysis, and portfolio documentation. A negative scientific result is a valid completion outcome. A genuine blocker is not permission to invent data, change the estimand, weaken a frozen gate, silently substitute a source, or relabel synthetic evidence as real evidence.

This is a single-agent application project. Do not add Tree-of-Thought, multi-agent teams, agent debate, recursive agent delegation, live advertising writes, actual ad spend, paid cloud jobs, or a video-recommendation subproject.

Use the local NVIDIA GeForce RTX 4090 Laptop GPU where technically justified, but keep one heavy CUDA job at a time. Parallelize numerically within a job and use bounded CPU workers for ingestion/simulation. Never alter BIOS, GPU driver, global power settings, or global Codex configuration.

## 1. Source-of-truth hierarchy

Read these files before editing code:

1. `AGENTS.md`
2. `WORK_STATE.md`
3. `docs/FINAL_SPEC.md`
4. `docs/SIMULATOR_CONTRACT.md`
5. `config/contract.json`
6. `config/experiments.json`
7. `config/hypotheses.json`
8. `config/interface_contracts.json`
9. `config/datasets.json`
10. `config/resources.json`
11. `DESIGN_KO.md`
12. `docs/DESIGN_AUDIT_KO.md`
13. `TEST_REPORT.md`

`docs/BASELINE_V1_ARCHIVED.md` is historical context only and must not override active v2 contracts.

If an active specification and JSON contract appear inconsistent, do not silently choose one. First determine whether it is an implementation-detail difference or a true scientific-contract conflict. For a true conflict, write `reports/design/SPEC_AMENDMENT.md` describing the conflict, the least-invasive resolution, and why it preserves the intended estimand/evidence boundary. Update all affected active contracts consistently before dependent experiments. Do not use final outcomes to choose the amendment.

## 2. Plan, execution, and checkpoints

Before implementation, inspect the repository and runtime and create:

- `IMPLEMENTATION_PLAN.md`: milestone-by-milestone plan mapped to E00-E16 and their dependencies.
- `IMPLEMENTATION_LOG.md`: append-only decisions, commands, failures, fixes, and evidence pointers.
- update `WORK_STATE.md` to `IMPLEMENTING` with the next runnable node.

Do not wait for me to approve the plan. Self-review it against the active contracts and proceed immediately unless there is a non-delegable human blocker.

After every milestone:

- run the relevant unit, contract, numerical, integration, and regression tests;
- record exact commands, exit status, wall time, and produced artifact paths;
- update the experiment/state ledger atomically;
- preserve failures and unfavorable results;
- continue independent valid tracks when another track is blocked.

If the Codex session must stop because of context/time/runtime limits, write a precise checkpoint to `WORK_STATE.md` and `IMPLEMENTATION_LOG.md`. Do not claim background execution continues after the session ends.

## 3. Approval and human-interaction policy

The Codex session is launched with Approve for me. Use automatic review for eligible command/network/filesystem approval requests, but do not weaken the sandbox or switch to dangerous full access.

Do not ask me routine questions that can be answered from the repository, official documentation, programmatic inspection, or a conservative implementation choice.

Pause and ask me only when a human action is genuinely non-delegable, such as:

- account login, CAPTCHA, subscription, credential entry, or browser-only acceptance;
- new legal/click-through terms not already authorized below;
- destructive action outside this repository/runtime;
- a hardware condition that makes further heavy execution unsafe or ambiguous;
- a scientific choice that would materially change the primary estimand or frozen confirmatory contract and cannot be resolved from the specification.

Never use `--dangerously-bypass-approvals-and-sandbox`, `--yolo`, or an approval-policy downgrade.

## 4. Explicit dataset authorization and boundaries

This project is personal, local, non-commercial research. I authorize downloading and locally using the public CORE datasets already listed in `config/datasets.json` under the listed licenses:

- Criteo datasets listed as `CC-BY-NC-SA-4.0`;
- Open Bandit Dataset listed as `CC-BY-4.0`.

You may pass those exact license acknowledgement strings to the repository acquisition utility when needed.

This authorization does NOT authorize:

- additional click-through terms not already represented by those licenses;
- authenticated/private sources;
- bypassing access controls;
- silent third-party mirrors;
- iPinYou if additional/manual terms acceptance is required;
- redistribution of raw/source-derived restricted artifacts beyond the documented license boundary.

If a core source cannot be downloaded from the configured official/publisher source, mark only the affected source/experiment `BLOCKED_SOURCE`, preserve diagnostics, and continue independent tracks. Do not invent replacement data.

## 5. Environment and resource admission

The canonical editable source is the Windows repository. Heavy Python/CUDA runtime data, environments, caches, checkpoints, runs, and SQLite state belong under the WSL-native runtime declared by `tools/prepare_runtime.py`. Do not create a second editable Git worktree in WSL.

Run E00 before installing or training anything substantial. Record at minimum:

- PowerShell/Codex/WSL versions;
- WSL Python availability;
- Windows backing-volume free space and WSL filesystem free space;
- CPU count and RAM;
- `nvidia-smi` device, driver, CUDA compatibility, utilization, memory usage, temperature, power state, and active compute processes;
- whether another heavy GPU workload is active.

The prior inventory is observational only. Re-measure everything.

Do not begin a heavy GPU run if the machine lacks the declared VRAM/disk headroom, if another heavy compute process is active, or if the bounded health qualification is unstable. Do not invent a universal temperature safety threshold. Record observed baseline and stepped-load behavior; if stability is unclear, mark heavy GPU tracks `BLOCKED_HARDWARE` and continue CPU-valid tracks.

Use one heavy CUDA process at a time. Begin CPU ingestion/simulation with two workers and increase to at most four only after memory/thermal qualification. Keep at least the declared storage reserve. Before large downloads/model caches, compute expected growth and verify both the WSL filesystem and its Windows backing volume have enough capacity; if not, reduce to the declared developer/core profile or block expansion rather than exhausting the disk.

## 6. Dependency environment

Do not modify global Python environments. Create a project-scoped WSL environment under the declared runtime. Inspect existing Python/CUDA compatibility first. Prefer a user-space environment mechanism already available; otherwise create an isolated venv and install only required pinned packages.

Do not blindly install `latest`. Start with a tiny CPU/GPU compatibility matrix for Python, PyTorch/CUDA, Transformers, TRL, PEFT, XGBoost, scikit-learn, DuckDB/Parquet tooling, FastAPI, and test/lint/type tooling. Freeze exact versions only after tiny import, numerical, one-update, and device checks pass. Save the lock/environment report as an artifact.

Model downloads must use exact repository IDs and resolved revisions. Pin tokenizer and chat-template revisions with the model. Do not treat an unpinned moving branch as reproducible evidence.

## 7. Implementation requirements

Implement the declared module structure under `src/aurora/` with typed interfaces and explicit contracts. At minimum cover:

- source acquisition/admission and chunked conversion to partitioned Parquet;
- schema/time/lineage validation and quarantine reporting;
- as-of features and leakage controls;
- predictive model ladder;
- finite-horizon delay/conversion model ladder;
- value modeling;
- randomized causal replication and constrained policy evaluation;
- logged-bandit OPE validation;
- optional source-gated auction replay;
- structural simulator and falsification controls;
- multi-signal incident detection/diagnosis;
- constrained policy baselines and MSCP-v2;
- atomic budget reservation/settlement and idempotent state transitions;
- one MCP server and the single tool-using LLM agent;
- SFT, DPO, IPO, and optional bounded GRPO;
- policy×agent integration;
- ablation/OOD experiments;
- serving/profiling/restart/recovery tests;
- independent evaluation/report generation and claim ledger.

Use deterministic/typed code for validators, authorization, budget invariants, SQL allowlisting, prepare/commit semantics, and metric computation. Do not make the LLM the source of economic quantities or ground truth.

## 8. Data and clock discipline

Implement all source-specific prohibitions and time rules from `FINAL_SPEC.md`.

Never silently join unrelated Criteo datasets by fabricated identities. Never multiply models from unrelated source domains and call the product a calibrated per-impression probability without an explicit synthetic coupling study.

For the primary Sponsored Search study, preserve the M41+C54 contract and half-open intervals exactly. Do not refit at day 70 with a stale calibrator. Treat conversion occurrence time and reporting availability as distinct concepts; when the source does not expose reporting delay, label the modeling assumption explicitly.

The primary policy study uses 14 decision days plus a 7-day maturation flush. Primary action-value learning updates only from fully matured origin-interval cohorts. Nowcasts may inform state/value estimates but are not pseudo-observed reward. Ensure event/cohort ledgers replace prior pending estimates rather than double-counting outcomes.

## 9. Baselines and fair comparisons

Implement the specified serious baselines, not strawmen. Screen broadly on development, then run complete confirmatory comparisons only for qualified finalists.

Prediction: empirical prior, hashed logistic/FTRL, XGBoost CUDA, embedding MLP, DCNv2 where feasible.

Delay/value: pending-negative diagnostic, mature-only, feedback correction, finite-horizon incidence+delay baseline, neural finite-horizon model, two-part and direct value models.

Causal/OPE: response targeting, T-learner, cross-fitted DR, optional neural treatment head; DM/IPS/SNIPS/DR with support/ESS/weight diagnostics.

Policy: no-change/static, rule/PID pacing, epsilon-greedy, LinUCB, neural-linear Thompson sampling, delay-aware Thompson + conventional primal-dual budget control, a conventional support-gated policy, MPC-style pacing, and MSCP-v2.

Agent: prompt-only, SFT, same-SFT DPO, same-SFT IPO. Run GRPO only if its separate prerequisite gates pass and budget remains.

All principal policy comparisons must share action masks, mechanical budget protections, cooldowns, action duration, and authorization rules. Do not give MSCP stronger hard guards than its principal comparator and then attribute the gain to the learned policy.

## 10. Simulator and policy validity

Follow `docs/SIMULATOR_CONTRACT.md` exactly. Keep simulator truth evaluator-only. Use disjoint mechanism families, not merely new random seeds. Include weak/no-heterogeneity cases and negative-effect cases where the complex policy can rationally lose.

Keep exogenous randomness keyed so policy actions do not alter future random streams by consuming different numbers of RNG draws. State may diverge by action, but shared exogenous shocks remain paired where the contract requires them.

Use completed-episode utility as the primary policy endpoint. Use unique synthetic purchase value, not duplicated impression credit. Charge ordinary spend plus any declared operational cost; scarcity dual is an additional budget-control price, not a replacement for spend.

Do not use one-step DR to certify an adaptive long-horizon budget controller. Evaluate full adaptive policies through complete independently randomized simulator worlds.

## 11. Agent implementation and evaluation

Use one Qwen3-based application agent with bounded tool rounds. No ToT and no multi-agent architecture.

Required tools are the declared typed interfaces for campaign snapshots, metrics, outcome estimates, policy simulation/recommendation, validation, prepare/commit, and measurement reports. `validate_action` is deterministic code, not another agent.

The LLM may never directly mutate live advertising systems. All state mutation is mock/local and must pass host-side authorization, version, idempotency, budget, and expiry checks.

Before training, verify the complete system/tool contract fits the effective context window. If not, reduce tool/context payload or increase context only after resource qualification. Do not silently truncate tool contracts.

Generate training/evaluation tasks from executable state, constraints, metrics, and source-grounded documentation. Hold out entire semantic/template/scenario families. Never let held-out prompts, corrections, retrieval docs, or expected tool arguments leak into SFT/preference data.

Evaluate unsafe proposal rate, host-blocked error rate, and wrong committed-action rate separately. A host guard preventing a bad proposal does not prove the model itself learned safe behavior.

## 12. Experiments, freeze, and confirmation

Execute the registry DAG in dependency order while allowing independent tracks to proceed. Preserve engineering status separately from scientific status.

Required scientific statuses are those declared by the spec, including `SUPPORTED`, `NOT_ESTABLISHED`, `UNDERPOWERED`, `INVALID`, and source/hardware blockers. Never reinterpret a failed gate as success because another metric looks favorable.

Run A/A, randomization/SRM checks, zero-effect and label-shuffle controls, deliberately leaky negative controls, duplicate-conversion tests, numerical reference fixtures, and source/split identity checks before confirmatory claims.

Freeze each track separately. Final confirmation data may not be reused for tuning, threshold choice, reward-function edits, or model reselection. A baseline is allowed to remain the final selected system.

For policy inference, respect the declared practical margin and independent-world unit. For agent inference, use semantic families as the primary dependence unit. If the available number of independent units is insufficient, report underpowered rather than pretending row/seed multiplication creates independence.

## 13. Serving and reliability experiments

Measure separately:

- model inference-only latency;
- feature-to-decision latency;
- network end-to-end latency;
- complete agent-task latency.

Benchmark CPU/GPU, batch/concurrency, cold/warm/compile, and cache effects under matched requests. Synchronize CUDA correctly. Do not exclude startup or failure costs from a deployment conclusion.

Exercise timeout, queue saturation, cancellation, stale model/state, duplicate retry, process restart, GPU OOM handling, idempotent replay, and budget double-spend prevention. Training must not run concurrently with isolated serving benchmarks.

The local latency/SLO targets in the spec are project engineering targets only, not Amazon production claims.

## 14. Required analysis and deliverables

Generate all report families required by `FINAL_SPEC.md`, including at least:

- desktop/literature study and nearest-method comparison;
- source/license/data capability matrix;
- EDA and data-quality report;
- clock/leakage audit;
- model comparison and calibration report;
- delay/value study;
- causal/OPE report;
- simulator qualification/falsification report;
- incident-detection analysis;
- policy comparison, statistical inference, and ablations;
- agent/post-training evaluation;
- policy×agent integration analysis;
- OOD/stress/failure-slice report;
- serving/performance/recovery report;
- final limitations/threats-to-validity report;
- immutable result/claim-evidence ledger.

Also create portfolio-facing artifacts derived only from validated result files:

- `reports/final/FINAL_TECHNICAL_REPORT.md`
- `reports/final/EXECUTIVE_SUMMARY.md`
- `reports/final/RESULTS_MATRIX.csv`
- `reports/final/CLAIM_EVIDENCE_LEDGER.csv`
- `reports/final/RESUME_EVIDENCE.md`
- `reports/final/INTERVIEW_GUIDE.md`
- final figures and machine-readable metrics.

`RESUME_EVIDENCE.md` must clearly separate real public-data evidence, randomized benchmark evidence, logged-bandit OPE, synthetic counterfactual results, local serving measurements, and agent benchmark results. Never turn a simulation result into production business impact.

## 15. Completion standard

Do not declare success merely because code exists or tests are green.

At the end, report the project in layers:

- engineering implementation completeness;
- source/data availability;
- each empirical track status;
- policy scientific conclusion;
- agent scientific conclusion;
- serving/reliability qualification;
- blocked or unavailable evidence;
- strongest defensible claims;
- claims that remain unsupported;
- recommended future work.

A valid final conclusion may be that a simpler baseline is better, that AURORA helps only under certain delay/support regimes, that the agent fine-tuning does not beat prompt-only, or that a key comparison is underpowered. Preserve that outcome.

## 16. Start now

Start by reading the source-of-truth files, running the existing 42 design/contract tests and design validator, then perform E00. Create the implementation plan and log, update the work state, and proceed through the full DAG without waiting for routine user confirmation.
