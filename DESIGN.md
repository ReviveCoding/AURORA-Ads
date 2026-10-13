# AURORA-Ads v2 research design

**Status at the original design freeze (September 30, 2026):** ready for implementation. This document does not establish completed model training, empirical superiority, or production deployment.

The study evaluates advertising decisions under conversion delays, fixed budgets, and distribution shift, then tests whether one LLM agent can invoke and explain the resulting numerical decision policy correctly. Multi-agent planning, tree-of-thought search, live media spend, video recommendation, and paid cloud execution are outside scope. The [authoritative implementation specification](docs/FINAL_SPEC.md) contains the complete machine-readable and experimental contracts.

## Research questions

1. Does the Maturity- and Support-Aware Constrained Policy (MSCP) improve completed-episode value over the strongest validation-selected conventional policy?
2. Does training a single tool-using agent improve task completion and valid tool behavior?
3. Can the complete workload run reproducibly within a qualified local compute and operational safety envelope?

These are separate endpoints, not components of an invented overall AURORA score. Keeping the baseline is an acceptable result. MSCP does not claim a new regret theorem.

## Data and interpretation boundaries

| Role | Source | Supported use | Not established |
|---|---|---|---|
| R1 | Criteo Attribution | CTR, temporal structure, descriptive attribution | Real monetary ROAS or randomized causal lift |
| R2 | Criteo Uplift v2.1 | Assignment ITT and released-population targeting | Ground-truth individual CATE or multi-action bid effects |
| R3 | Sponsored Search Conversion | Post-click conversion, maturation delay and attributed value | Impression-level CTR or raw creative semantics |
| R4 | Open Bandit Dataset | Position-conditional off-policy evaluation with logged propensities | Arbitrary-policy truth from a BTS mean |
| R5 | Optional iPinYou | Conditional historical auction replay | Observed counterfactual outcomes for unseen auctions |
| S1 | Explicit synthetic worlds | Full policy, budget and counterfactual comparisons | Actual customer or production impact |
| A1 | Executable agent tasks | Tool use, actions, numerical correctness, evidence and policy compliance | Completed human evaluation or safety certification |

Never join unrelated source identifiers or multiply CTR from one source by CVR from another and label the result validated impression value. Record original source version, hashes, licenses, and previous benchmark exposure. Re-splitting a previously studied public benchmark does not create an independent external test.

Source acquisition is cache-first. Downloading requires explicit license acknowledgement and an `--apply` action. A successful HTTP transfer does not by itself establish schema, CRC or timestamp admission.

## Timing, preprocessing and selection

Record `origin_time`, `information_time`, `outcome_time` and `received_at` separately. The R3 source does not publish a measured reporting-arrival clock; the primary `received_at` is based on click time plus conversion delay, with additional reporting lag assessed only as synthetic sensitivity.

R3 uses a seven-day outcome horizon and half-open time ranges:

- **M41:** Fit using information available at day 41 for origins in days [0, 41). Mature-only controls use records with origin + 7 days no later than day 41; delay-aware likelihood may use censored recent records.
- **C54:** Calibrate the frozen M41 predictor using origins [41, 47) after their outcomes mature by day 54.
- **Selection:** Use origins [54, 60), observed through day 67.
- **Day 70:** Freeze M41 + C54 and all primary decisions. Do not silently refit the primary model.
- **Confirmation:** Evaluate origins [70, 82) using outcomes matured by day 89.

Any newly refitted model requires a separately qualified calibration pair and a secondary study. EDA covers missingness, duplicates, maturity, sparse categories, campaign/time drift and propensity support. Stream admitted raw records into Parquet/DuckDB and quarantine malformed rows with a stated reason.

## Numerical modeling

Compare prior models, hashed logistic/FTRL, CUDA XGBoost, embedding MLP and DCNv2. The delay study includes mature-only modeling, pending-negative diagnostics, feedback correction, truncated exponential incidence and a learned finite-horizon distribution. Value models include positive-value means, corrected log two-part methods and direct Tweedie/MLP. Causal work compares response targeting, T-learners, cross-fitted doubly robust estimation and optional treatment-head networks.

Predictive primary metric: log loss. Also report Brier, PR-AUC, AUROC, calibration, worst slices and tails. Never select calibration by final-test ECE; match feature availability across candidates.

Let `q = P(conversion by H)` and `sum(f_k) = 1`. The likelihood for observed conversion in age bin k is `q*f_k`, and survival through age u is `1-q*F(u)`. Condition an exponential baseline on the finite horizon so that `F(H)=1`. Multiple snapshots from the same origin do not constitute independent rows.

## World model, bidder and slow policy

The default synthetic world contains eight noncompeting campaigns with distinct fixed budgets and common exogenous shocks. Each episode has 14 decision days followed by a 7-day conversion-maturation period. Policies use independent mutable states but matched exogenous random draws. Include zero, negative and heterogeneous effects; nonlinear dynamics; fatigue/carryover; and reporting or competition shifts. Candidates cannot access latent truth, future outcomes or fault identifiers.

Fast bidding compares fixed bids, calibrated-value bidding and a grid utility optimizer. Slow actions are `NO_CHANGE`, `BID_UP`, `BID_DOWN`, `PACE_UP`, `PACE_DOWN` and `PAUSE_SEGMENT`. An action expires after one 15-minute interval. Bid multipliers range [0.5, 1.5] in 10% increments; pacing ranges [0, 1] in 0.1 increments. The overall budget cannot increase.

The proposed MSCP score is:

`gross_value - (1 + scarcity_dual)*spend - operating_cost - beta*uncertainty`

Count spend once. Uncertainty is an evaluated proxy, not a formal safety guarantee. Fall back to the qualified baseline for poor support, stale state or invalid actions. Update the primary policy learner only from matured origin-interval cohort rewards. Use nowcasts for state, value and pacing, not as self-generated reward labels. Pseudo-reward updates are a separate sensitivity study.

Include the strongest safe static policy, rule/PID control, epsilon-greedy, LinUCB, neural-linear Thompson sampling, delay-aware TS with primal-dual control, support-gated conventional policy and MPC. Apply the same mechanical budget and authorization guards to all policies.

## Policy evaluation and identification

R2 binary-assignment uplift does not identify the effects of S1 multi-action bid/pacing decisions. Train S1 action-value models using randomized S1 data. The off-policy logger uses an explicit categorical mixture and records probabilities of the final guarded executed actions. A Thompson-sampling Monte Carlo frequency is not an exact logged propensity.

Use one-step DM, IPS, SNIPS and DR only under stated fixed-policy and overlap conditions. Evaluate full adaptive budget trajectories with completed independent worlds. Begin OBD validation with a uniform-target identity control; BTS comparison without exact reconstruction is diagnostic.

The policy utility is:

`(unique_purchase_value - paired_no_ad_purchase_value - spend - operating_cost) / initial_budget`

The no-ad term cancels in a paired MSCP-versus-conventional comparison. The learner does not see this evaluator oracle. Validate a unique user-event ledger so low spend or double-attributed conversions cannot produce an artificial win.

## Single agent and post-training

The fast numerical bidder contains no LLM. The single agent exposes `get_campaign_snapshot`, `query_metrics`, `estimate_outcomes`, `simulate_policy`, `recommend_action`, `validate_action`, `prepare_action`, `commit_mock_action` and `build_measurement_report`.

Queries use allowlisted parameterized SQL. Prepared actions bind tenant, state version, payload, expiry and evidence. A commit requires host-issued approval or explicit `MOCK_ONLY` preauthorization. A model-generated `approved=true` value is never approval.

Compare prompt-only, SFT, then DPO/IPO from a matched SFT reference; bounded GRPO is optional. The development candidate is Qwen3-1.7B, with a proposed 4B qualification candidate. Fix model, tokenizer and chat-template revisions. Planned figures of 8,000 SFT examples, 2,000 preference examples, and 400 final tasks across 80 families are *targets*, not completed collections.

Train on assistant text and tool arguments; mask system text and tool observations. Audit the complete tokenized tool contract and never silently truncate a 1,024-token context. Report harmful proposals, host-prevented violations, committed violations, task success and over-refusal separately. The integration design is a 2×2 numerical-policy (conventional/MSCP) by agent (prompt/learned) study. Pure policy comparisons use a deterministic executor.

## Experiments, statistical decisions and computing

Twenty-seven machine-readable DAG nodes refine E00–E16: inventory, data/EDA, predictive/delay/causal/OPE work, simulator, incidents and policy, agent learning, integration and ablations, track-specific freezes, independent confirmation, and reporting. Separate R1, R3, POLICY and AGENT freezes. Optional iPinYou/GRPO and an unavailable source cannot block independent core tracks. Reports record terminal status honestly, including BLOCKED and INVALID.

The primary policy comparison is MSCP versus the strongest validation-selected conventional method. A practical improvement requires the lower paired 95% confidence bound to exceed **0.01 normalized utility**, corresponding to 1% of initial budget. This is a preregistered decision rule, not a predicted result. Estimate power after 20 pilot worlds for 40–200 final worlds, distinguishing a null margin of 0.01 from a planning alternative of 0.02. Use `UNDERPOWERED` when warranted. Agent inference uses family-cluster analysis and seed variability; zero observed harmful actions is not zero true risk. Holm-adjust secondary confirmatory claims or label them exploratory.

Report worst slices by delay, budget, support and shift, along with error transitions, ablations, cost/risk trade-offs and serving latency. Derive tables from frozen JSON/Parquet, not hand-entered summaries.

The execution design uses the Windows repository as the single editable source and WSL ext4 as the runtime area. Run one heavy GPU job at a time. Begin with two CPU workers, qualify up to four; target no more than 12 GiB planned VRAM with at least 2 GiB free headroom. Compare numerical estimators with CPU FP64 references. Do not present single-GPU experiments as multi-GPU scaling. Proposed fast-path targets are 100 RPS, p95 at most 50 ms and error rate at most 0.1%, not a commercial advertising SLO. Measure inference-only, feature-to-decision, HTTP and complete agent latency separately.

## Completion terminology

- `DESIGN_READY`: design, contracts and preparation code agree.
- `ENGINEERING_EXECUTED`: implemented runtime and smoke paths were actually executed.
- `CORE_TRACKS_CLOSED`: every core track reached a documented terminal status.
- `CORE_EMPIRICAL_COMPLETE`: all required empirical capabilities were genuinely exercised.
- `SCIENTIFIC_SUPPORTED`: a particular hypothesis met its frozen acceptance rule.

These statuses are not interchangeable. The original September 2026 preparation package was only `DESIGN_READY`. See the live execution records for subsequent evidence rather than treating this document as a present-day project-status claim.

The original interactive preparation verified archive paths, hashes, WSL and CLI capabilities; launching Codex without a prompt did not itself implement, install, train or evaluate the project. Approval modes do not override the user's security and host policies.
