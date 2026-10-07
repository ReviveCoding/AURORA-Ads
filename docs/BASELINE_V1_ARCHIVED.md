# AURORA-Ads v1.0: implementation and experimental contract

Design date: 2026-09-30. Status: DESIGN SPECIFICATION, NOT AN EXECUTED ML RESULT.
Owner: Jinwoo Bae. Hardware target: one NVIDIA RTX 4090 Laptop GPU; resources must be discovered.

## 1. Scope and central question

One project, one coherent decision lifecycle, one LLM agent. Tree-of-Thought, agent teams, agent debate, recursive delegation, live advertising API writes, paid cloud jobs and actual advertising spend are out of scope. Video recommendation and MOSAIC expansion are separate future work.

Central question: under delayed outcomes, finite budgets and distribution changes, does a maturity- and support-aware constrained intervention policy improve completed-episode utility relative to the best qualified conventional policy, without worsening declared operating constraints? A second, separately evaluated question is whether a single tool-using agent can reliably execute and explain that policy through typed tools.

The proposed policy is an experimentally testable integration of established delay modeling, causal/policy estimation, uncertainty diagnostics and budget control. Do not claim a new regret theorem, universal causal identification, a production safety guarantee or prior-art novelty. The desktop study must record the nearest existing approaches.

Primary scientific artifact: the policy comparison and its ablations. Supporting artifacts: real-data predictive/delay studies, real randomized-effect replication, real propensity-logged OPE, auction-log conditional replay, controlled agent post-training, and isolated service measurements.

## 2. Evidence domains: NEVER silently join them

R1: Criteo Attribution: observed display-impression response, campaign time patterns and descriptive attribution. Costs/cpo are transformed. Logged response is not a randomized intervention effect. Do not use post-event columns as pre-impression features.
R2: Criteo Uplift v2.1: randomized binary assignment ITT for visit (primary) and conversion (secondary). No genuine campaign time/bid/price fields. Exposure is post-assignment, not a substitute for assignment. No invented longitudinal ordering or individual treatment-effect truth.
R3: Criteo Sponsored Search Conversion Log: post-click conversion, delay and sales amount. No impression CTR denominator. Product title and categories are hashed, not natural-language creative text.
R4: Open Bandit Dataset: action, propensity, click and context under logged recommendation policies. Not a campaign budget experiment. Primary OPE uses one position and explicitly states the marginal-position/no-slate-interference assumptions.
R5: iPinYou: auction/bid/impression logs, subject to availability and licensing. Standard impression replay is conditional on historical exposure and censoring. Do not claim outcomes for newly won auctions that lack observed labels.
S1: independently specified structural synthetic environments anchored to selected aggregate distributions from R1/R3/R5. All generated budgets, action effects, organic outcomes, confounders, policies, permissions and faults are labeled synthetic. Joint user/campaign identities across unrelated sources are prohibited.
A1: programmatically generated agent tasks over R1 descriptive marts and S1 mock campaigns. Ground truth derives from query results, constraints and executable state transitions, not another LLM's unsupported assertions.

Data license and code license are separate. Criteo is CC BY-NC-SA 4.0; OBD's listed license is CC BY 4.0; iPinYou has noncommercial restrictions. Capture source terms before use. Default publication excludes raw/row-level/derived customer data, generated source-grounded training traces and model adapters until redistribution terms are reviewed. Do not infer that a code repository's Apache/MIT license covers its upstream datasets.

## 3. Desktop study deliverables

Produce docs/problem_statement.md, literature_matrix.csv, data_capability_matrix.csv, nearest_method_comparison.md and assumptions_register.json before full modeling. Each literature row must record primary source, intended estimand, assumptions, actual dataset fields, compute needs, baseline role and differences from AURORA. Required topics: calibrated response models; Chapelle-style delayed feedback and feedback-shift correction; DR policy evaluation; budget-constrained bandits; auction censoring and bid optimization; single-agent typed tool use; SFT/DPO/IPO; project-level serving benchmarks. Include contemporary delay/GMV work such as TRACE only as an optional dataset review, not a new mandatory task.

Existing reports are evidence to learn from, not a source of AURORA outcomes. AIX showed a contextual policy can lose to a strong static policy. AD-DIAG exposed missing causal observation channels and excessive false alarms. ReasonForge showed no confirmed advantage of adaptive training and weak absolute tool performance. ScaleForge showed model and runtime improvements are separate, and serving shutdown failures matter. Preserve old experiments; do not retune them or relabel their exposed holdouts as unseen AURORA tests.

## 4. Architecture and responsibilities

Data plane (millisecond-scale engineering target): input schema -> as-of features -> calibrated small-model scores -> eligible candidate set -> bid/pacing decision -> atomic budget reservation -> mock auction -> events. No LLM inference on this path.

Control plane (campaign interval; default 15 minutes in simulation): mature/as-of campaign aggregates -> telemetry quality and incident model -> constrained intervention policy -> single agent may request snapshot, predictions, replay and evidence -> deterministic validation -> prepare/commit on mock state -> report. Model policy selects numerical actions; agent may orchestrate tools but may not bypass constraints or fabricate economic quantities.

Evaluation plane: immutable source/split/config/model IDs -> independent metric implementation -> paired comparisons -> validity and promotion status -> descriptive analysis -> claim ledger and final report.

Services: a small FastAPI data service, one MCP server, a deterministic simulator, an asynchronous single-agent worker, and a local analytics/reporting process. Modules are not agents. No Redis/Kafka/Kubernetes/Spark cluster is necessary for v1. SQLite provides state/idempotency; Parquet + DuckDB analytics. A local[2] Spark parity extension is optional and must be labeled single-host.

## 5. Data ingestion, audit and schema

Acquisition is cache-first and explicit-opt-in. Manifest records upstream URL/revision, license acknowledgment, time, SHA-256, size, access status and prior exposure. Stream downloads to .part files, validate source identity and expected hash where published, then atomically rename. Do not bypass authentication, accept arbitrary mirrors, log signed tokens, auto-extract archives or erase raw caches. Gzip CRC/archive member validation belongs to admission, not just HTTP success.

No entire-source pandas load. Stream CSV/TSV in bounded chunks, validate and write partitioned Parquet. Keep quarantined counts and reasons, not silent dropna. Validate binary labels, nonnegative elapsed times, arrival >= origin, conversion IDs, units, currency, sentinel values, sortedness, category cardinality and actual number of fields. Avoid arbitrary winsorization of outcome tails; train-only transformations plus raw-tail sensitivity must be reported.

Mandatory data-quality outputs: source/sampling funnel, schema dictionary, missingness by time/campaign, label prevalence and maturation, duplicate-event and duplicate-conversion counts, time span, per-campaign support, selection distribution, train/test overlap and parser exclusions. Never expand KDD aggregate rows into claimed independent users or events.

Canonical contracts:
- observations: source_id, event_id, origin_time, information_time, campaign_id (nullable), native context, sample weight and field lineage.
- outcomes: event_id, outcome_time, received_at, horizon, event_observed, value, label_mature, source outcome identity.
- decisions: decision_id, state_version, as_of, eligible_actions, selected_action, requested_action, logging_probability, policy_version, model_version, random_seed_key, expected_cost, budget_reservation.
- traces: task_family, task_id, action_index, tool_name, validated_arguments, result/evidence hashes, execution_status, token_count and latency. No credentials or unnecessary raw identifiers.
- campaigns: native or synthetic namespace, campaign budget, residual budget, spend-to-date, pacing target, action cooldown and telemetry freshness.

For attribution exclude conversion, conversion_timestamp, conversion_id, attribution, click_pos, click_nb and conversion-dependent cpo from pre-impression input. click is a target, not an input to impression CTR. Any 'history' field must be reconstructed strictly as-of or excluded. Deduplicate conversion IDs for business counting; per-impression prediction labels and unique conversions have different denominators.

For uplift use only pretreatment f* features; treatment is the assignment label. Visit/conversion/exposure are not confounder features. Inspect all 12 f0-f11 fields rather than trusting prose feature counts. ITT assignment and observed exposure are distinct estimands.

For sponsored search, click_timestamp=0 is missing; -1 is missing for designated fields. Sale=0 with sales/delay=-1 means no recorded conversion in the provided horizon, not zero delay. Only a completed horizon permits a zero revenue label. The title cannot be decoded into natural text. Audit what SalesAmountInEuro represents before calling it GMV or unique order revenue; publisher notes attribution issues.

## 6. Time and split design

Every run fixes an event clock, availability clock, training cutoff and outcome horizon. Row order or a random shuffle is not a real temporal clock. Availability includes delayed arrival, not merely event creation.

Sponsored Search primary horizon H=7 days to retain meaningful train/calibrate/select/test periods inside the documented 90-day source. Proposed relative-day split, subject to source audit: initial model training origins days 0-40; calibration origins 41-47, fully mature by day54; selection origins54-60, mature by67; freeze all rules at70; final origins70-82, mature by89. Crucial: the first model snapshot is fitted as-of day41. For training origins0-40, the mature-only arm can use completed7-day labels only when origin+7<=41; the delay-aware arm may additionally use recent origins with correctly censored as-of labels. Do not retrospectively fill all0-40 labels and then score calibration origins41-47 as if that model existed at41. Generate calibration predictions from eligible historical snapshots, and fit their calibrator only once outcomes mature. Freeze primary real-data final model weights as-of70. A separately labeled prequential-update secondary study is allowed only if the update rule was preregistered and uses no evaluator feedback. Report warm-user out-of-time performance separately from unseen-user/product challenge. H=30-day analysis is secondary and only uses genuinely complete follow-up; no fabricated day119 observations.

Attribution: use forward chronological response-prediction splits and a separate user/campaign challenge. Its 30-day source is not enough by itself to pretend all rolling 30-day conversion labels were already available. Use it for impression-response modeling, time patterns and descriptive paths; delayed-feedback primary evidence comes from the 90-day source. Timestamp uncertainties trigger an unavailable status, not guessed units.

Uplift: deterministic group hashes over identical pretreatment profiles; reuse existing exposure manifests when available. Benchmark replication on an already viewed source is labeled retrospective replication. New hashes do not create genuinely new external data. Estimate held-out average policy value, not individual-effect RMSE against nonexistent truth.

OBD: one explicitly selected position; action-space/item-context and propensity checks; temporal training/evaluation if exposed fields support it. Compare random-policy-based OPE to contemporaneous on-policy aggregates cautiously, accounting for campaign/policy population and temporal differences. Do not infer unbiased full-slate value from marginal position propensities.

Simulation: disjoint scenario parameters and exogenous-randomness keys across development/calibration/final. Hold out entire mechanism families, not just seeds. Same keyed potential-outcome noise across policies for paired comparisons; action-dependent states evolve separately. Oracle latent outcomes and scenario labels are evaluator-only.

Agent tasks: split by semantic template, scenario family, schema version and campaign namespace. All paraphrases of a template family remain together. Test tasks cannot appear in SFT examples, preference pairs, retrieval documents, or generated corrections.

## 7. Baseline model roster and fair resource allocation

Predictive models P0 empirical prior; P1 hashed logistic/FTRL; P2 XGBoost hist/cuda; P3 categorical-embedding MLP; P4 DCNv2. Common feature policy, sample populations, calibration candidates and selection metric. Logistic is a serious comparator. Test simpler model first. No full Cartesian product of all models, tasks and policies. Screen on development; full final comparison only for qualified finalists. Report data fraction, wall time and GPU time per model.

CTR on native impression data: log loss primary; Brier, PR-AUC, ROC-AUC and calibration curves secondary. Calibration compares none, scalar/logistic and isotonic on separate calibration data. Report ECE bins as diagnostics, not sole selection target.

CVR/delay D0 recent-pending=negative (deliberately biased diagnostic); D1 mature-only logistic/XGB; D2 observation-age/feedback-shift correction with explicit assumptions; D3 logistic incidence + exponential delay baseline; D4 neural discrete-time event-time model with a nonconversion mass. Use shared categorical backbone for D3/D4 where possible to isolate timing. Mature-only is not a strawman.

For horizon H, let q=P(conversion by H | x); conditional conversion-time masses f_k sum to one over bins within H; F(u)=sum_{k<=u} f_k. For observed conversion bin k likelihood is q*f_k; for not-yet-observed at age u likelihood is 1-q*F(u). At H the latter becomes1-q. Compute log probabilities stably. This is one observation per origin at a fitting cutoff, not many independent duplicated snapshots. Validate on a toy process with known q/F; mass sums, F(H)=1, monotonicity and finite gradients are required. Observation-age correction cannot identify outcome-dependent permanent missingness without assumptions.

Revenue: compare a two-part CVR x conditional positive-value model with direct Tweedie/log-link and embedding-MLP baselines. Use untrimmed economic loss and a declared robust sensitivity. Do not multiply predictions from two unrelated source domains and call the product a calibrated per-impression value.

Uplift assignment propensity must follow the released sampling/randomization documentation and be audited; do not hard-code an approximate published treatment fraction as an exact known probability. Record when the propensity is estimated rather than known. Causal C0 response-only targeter; C1 T-learner; C2 cross-fitted DR learner; C3 shared-backbone treatment-head neural model only if budget allows. Primary visitation ITT on uplift; conversion ITT is a sparse secondary endpoint. Report average effect and policy value under capacities10%,20%,40%, but do not select capacity on test. Nuisance cross-fitting and policy learning must be separated from final evaluation. Grouped DR calibration has noise; no individual CATE truth claims.

## 8. Proposed AURORA policy

Working name: MSCP, Maturity- and Support-Aware Constrained Policy. This is a proposed engineering/research method, not an established superior algorithm.

Fast bidder: for native/synthetic compatible units, choose among a small bid grid using expected gross or incremental value (different clearly labeled modes), win probability and expected auction cost. Include fixed bid, linear calibrated response bid and optimized expected-utility bid. Second-price and first-price payments are distinct in the simulator. iPinYou results are conditional historical replay; full counterfactual bid claims require simulation or explicit identification assumptions.

Slow campaign controller state: budget/spend/pacing, eligible supply, auction-loss diagnostics, calibrated response, estimated mature outcomes, outcome age distribution, incident scores, feature freshness and support. Action set v1: NO_CHANGE, BID_MULTIPLIER_DOWN, BID_MULTIPLIER_UP, PACE_DOWN, PACE_UP, PAUSE_SEGMENT. Budgets are fixed; no 'increase budget' action creates money. Any later cross-campaign reallocation conserves total budget.

All policies share deterministic eligibility, action bounds, cooldown and an atomic budget reservation mechanism. The proposed method does not receive a stronger mechanical safety layer than its principal comparison. Reserve integer cost units up to the maximum payable bid; settle and release unused reservation on the mock auction. Concurrency tests must prevent double spending. Pausing an eligible segment is modeled as a decision, not hidden data deletion.

MSCP computes action estimates from delay-aware as-of outcomes and compares an empirical lower-bound utility score:
score_t(a) = Qhat_t(s,a) - lambda_t*Chat_t(s,a) - beta*uncertainty_t(s,a).
Here Qhat is gross or incremental value under a declared estimand, Chat is expected cost, lambda is the budget shadow price, and beta is chosen on development. If Qhat is net value already, do not subtract the same cost again. For difference-to-NO_CHANGE intervals use paired model/bootstrap predictions, retaining covariance. Low support, stale features or inadmissible action triggers a qualified baseline/NO_CHANGE, not arbitrary extrapolation. Ensemble spread is an uncertainty proxy; absent coverage evidence it is not a formal confidence interval or safe-exploration guarantee.

Delayed rewards: maintain an event-keyed contribution ledger. Observed value plus expected remaining value may be used for a model-based update, but this is not directly observed causal reward. New evidence replaces the old contribution; it is not added as another independent reward. Mature outcomes remain the principal evaluation endpoint. Compare plug-in, mature-only and delay-aware updates under identical action masks.

Budget pacing: dual/primal control based on spending relative to target schedule; update rate/normalization/caps frozen before test. Empty feasible set -> NO_BID/NO_CHANGE. A low-budget campaign cannot bypass the invariant because its estimate is attractive.

Bandit baseline roster: static/no-change; rule-based pacing; epsilon-greedy; LinUCB; neural-linear Thompson sampling; delay-aware Thompson + conventional primal-dual budget control (strong primary comparator). Behavior propensities are explicit for collected randomized simulator logs. Log the probability of the actual executed action after eligibility masks, fallback and deterministic guard transformations; multiple rejected proposals mapping to NO_CHANGE require summed probability mass. Logging only the pre-guard proposal probability is invalid. Use exact mixture probabilities or a tractable randomized policy when doing OPE; do not report an estimated probability of a deterministic UCB choice as known randomized logging probability.

Budget and action carryover make the full problem stateful. MSCP's bandit policy is an approximation, not proof that the system is a stateless contextual bandit. Include a fixed MPC-style pacing controller as a budget-state-aware comparator. Evaluate learning policies through independently randomized whole episodes/worlds, not one-step DR applied incorrectly to adaptive long-horizon budget trajectories.

## 9. Simulator and identification

Structural variables: exogenous traffic intensity, latent intent, eligible inventory, competition/market price, exposure/click, organic baseline outcome, incremental exposure effect, delay, telemetry availability, budget and action-induced state changes. Four mechanism families: additive weak effects; nonlinear heterogeneous effects; saturation/fatigue and carryover; confounding/observation failure and competition shift. At least one family has no heterogeneity and one contains negative effects, so complex targeting can rationally lose.

Anchor only source-supported marginals/conditional patterns. The simulator is not 'validated as realistic' by matching a time histogram. Cross-source coupling assumptions must be varied. Generator architecture may not be the same trained network used as the candidate's simulator oracle. Fit empirical anchors on permitted development source only; latent intervention structures are separately specified and held out.

Policy primary population: independent auction/campaign worlds with fixed budgets, predefined horizon and isolated resource pools. Common exogenous draws are keyed by event ID. Changing an action must not change which random stream later events receive. Independent world is the resampling unit; campaigns within one interacting market are not independent.

Faults: budget exhaustion, throttling, competition rise, supply decline, eligibility restriction, performance shift, conversion delay shift and telemetry loss. No fault-ID-as-input. Evaluate observable versus unobservable cause classes separately. Compare impression-only detector with multi-signal statistical rules, multi-signal XGB and a compact temporal model. Root-cause accuracy conditional on detected incidents and end-to-end missed-incident loss are separate metrics.

## 10. OPE and measurement

One-step DR for a fixed target policy with support:
V_DR = mean[sum_a pi(a|x)*qhat(x,a) + pi(a_i|x)/b(a_i|x)*(r_i-qhat(x,a_i))].
Compare DM, IPS, SNIPS and DR with cross-fitting. Report effective sample size, weight tails, action coverage, clipping bias sensitivity, estimated variance and calibration against on-policy/simulation truth. Support failure yields NOT_IDENTIFIED/INSUFFICIENT_SUPPORT, not a number that looks precise. Unknown historical propensities are not filled with a fitted score and then called known randomization.

Real uplift uses assignment ITT; conditioning on exposed treatment rows would change the estimand. Real attribution reports first/last/time-decay descriptive credit separately from randomized incrementality. Conversion events counted once in economic reports. No ROI/euro profitability from transformed cost/cpo. Observation-dependent missing outcomes get bounded/sensitivity analysis rather than a universal unbiasedness statement.

Full adaptive-policy performance: prospective randomized simulator episodes or carefully specified sequential estimators with full logging/state assumptions. One-step DR alone cannot certify a full budget-adaptive controller.

## 11. Single-agent design and learning

One Qwen3 model, bounded observation/action loop; no ToT or multi-agent. A deterministic validator is software, not a second LLM agent. Development model1.7B; final4B if resource-qualified. Record exact model/tokenizer revisions and chat template. Do not expose long hidden reasoning as a required artifact. Store concise task plan, tool calls, outcomes, evidence references and final explanation.

Tools: get_campaign_snapshot; query_metrics (allowlisted parameterized SQL only); estimate_outcomes; simulate_policy; recommend_action; validate_action; prepare_action; commit_mock_action; build_measurement_report. Prepare binds campaign version, allowed change, expiry and artifact hash. Commit requires host-issued approval or preauthorized test policy, never an approval string generated by the LLM. Reports cite actual tool evidence, units, denominators, horizons and uncertainty.

Action constraints: no live ad API, no shell, no network fetch from user-supplied URL, no DDL/DML in analytics tools, no cross-tenant read, no forged approval, idempotent retry and optimistic version checks. The quantitative policy is available through a tool; LLM output is not directly executed as a bid.

Training tasks: 8,000 initial instruction trajectories and 2,000 preference pairs are budget targets, not acquired real annotations. Generate from executable permitted training scenarios and curated metric docs. Include underdelivery, delayed reporting, low support, ambiguous requests, stale state, wrong units, duplicate conversions, contradictory instructions and injection attempts. Expert scripts produce reference plans; alternative valid plans must not be penalized solely for differing wording. Preference construction is lexicographic: constraint correctness, task completion, evidence/numeric fidelity, unnecessary action/tool cost. Reject ties/ambiguous labels. Hold out scenario/template families and paraphrases.

Agent baselines: deterministic workflow where applicable (reference ceiling, not universal NL competitor); prompt-only single agent; SFT; same-SFT DPO; same-SFT IPO. DPO/IPO share pairs, reference, tokenizer, selection data and compute envelope. Explicit TRL loss selection is required; do not call every preference loss DPO. Initial rank8/16 QLoRA, length1024, batch1, accumulation16. Parameters are proposal defaults and must pass a bounded smoke test.

Optional bounded GRPO extension only after SFT and executable rewards pass validation: compare SFT+GRPO to same-SFT preference baselines under a separately budgeted study, group size2-4, bounded tool rounds, fixed episode tokens. Keep explicit loss normalization and reference settings in config. Reward code cannot reward appearance of success words; it verifies final state and evidence. No reward/ground-truth side channel in prompts. If group rewards are constant or gradients invalid, mark study invalid rather than resume tuning on test.

Agent evaluation target400 held-out tasks from80 semantic families with5 instances each; final2 recipes repeated across3 training seeds if feasible. Families, not seed-expanded rows, drive uncertainty. Report absolute task success, policy compliance, incorrect authorized action, unnecessary refusal, numerical/citation correctness, tool calls, token budget, latency and cost. Shared constraints applied to all deployed variants. Removing guards is an offline diagnostic only; no real writes.

## 12. Experiment design and budgets

Phases are a DAG, not one fragile monolithic script. Independent tracks may continue after a scientific failure; dependent efficacy claims cannot bypass it. Per-stage engineering status and scientific outcome are distinct.

E00 hardware/software/license/source qualification.
E01 admission/EDA/clock and leakage controls.
E02 supervised prediction model ladder.
E03 delay-model study and maturity/value calibration.
E04 randomized ITT and capacity-policy replication.
E05 real logged-bandit OPE validation.
E06 auction conditional replay (source-gated).
E07 simulator qualification and falsification controls.
E08 multi-signal incidents and recovery diagnostic.
E09 constrained bandit/controller comparison, oracle diagnostics withheld.
E10 SFT/DPO/IPO single-agent comparison.
E11 optional small GRPO.
E12 end-to-end single-agent+policy integration.
E13 ablations and declared shifts.
E14 serving/CPU-GPU/profiling and failure recovery.
E15 freeze selected configuration and final confirmatory execution.
E16 post-final descriptive diagnostics and report.

Budget policy: developer profile uses deterministic500k-2M row cohorts and a few bounded trials; scale profile streams full qualified source. Candidate data exposure and tuning budget are logged. Default max8 trials per tabular family,2 neural architectures/configurations then3 seeds only for finalists. Trial budgets are caps, not evidence of equal optimization difficulty. Report wall/GPU hours and use both matched examples and matched compute views. All primary/final gates freeze before inspecting final outcomes.

Planning allocation for full study: tabular/delay/causal24 GPU-hours, policy/simulation12, agent SFT/preference36, evaluation/systems12. These are caps/quotas to avoid uncontrolled runtime, NOT runtime forecasts. Initial microbenchmarks revise the operational allocation before freeze. GRPO extra12hours only by explicit config authorization. No unbounded search or 'run until candidate wins'.

Simulation power pilot: start20 independent development worlds to estimate paired variance. Select final N within40-200 independent worlds using MC power for a prespecified practically meaningful effect and alpha0.05. If required N exceeds resource cap, label underpowered; no post-hoc margin relaxation. A world may contain8 campaigns over7 days at15-minute control intervals, with configurable event count. Number of impressions is not the number of independent worlds.

A/A controls, randomization-unit SRM, zero-effect/label-shuffle checks, intentionally leaky feature negative controls and duplicate-conversion tests must precede final treatment claims. Leaky controls are never candidate models.

## 13. Ablations: isolate mechanisms

Primary matched factors: (1) mature-only versus delay-aware reward information, (2) ordinary versus maturity/support-aware policy gate, (3) no empirical uncertainty penalty versus penalty, (4) fixed versus dual pacing. Same backbone, data, actions and mechanical budget protections. Run leave-one-component-out plus a2x2 delay-awareness x policy-reliability interaction study, not a full exponential grid.

Additional ablations: response-value versus incremental objective only where identified; impression-only versus multi-signal incident detection; context retrieval versus required-dependency retrieval; prompt versus SFT versus DPO versus IPO; all-model calls versus CPU/GPU tiered service; cache/compile enabled versus disabled with cold costs charged. Compare end-to-end best systems AND component-fixed comparisons separately.

Stress axes: delay severity, temporary/permanent reporting loss, competition, budget tightness, new campaign, low support, no treatment heterogeneity, negative effects, supply shock, feature staleness, tool timeout, duplicate retry, stale state, prompt injection, malicious SQL and conflicting authorization. Primary vs exploratory slices are preregistered. Do not choose favorable slices after seeing results and call them confirmatory.

## 14. Metrics, analysis and decisions

Primary policy endpoint: completed-episode incremental value minus declared costs normalized by initial budget, in synthetic worlds with defined counterfactuals. Report gross response mode separately on observational replay. Main comparison is MSCP against the best validation-selected credible conventional policy (including delay-aware primal-dual bandit), not against random bidding only.

Proposed practical threshold:3% relative completed-episode utility improvement when baseline is positive/stable, otherwise a prespecified absolute normalized-unit threshold. Freeze threshold from task economics and independent pilot before final. Require a paired95%CI supporting improvement and non-regression of critical constraints. All safety/authorization/budget invariants are tested separately; statistical non-regression margins defined before freeze. No theoretical zero-risk claim from zero observed failures.

Statistical units: user/profile groups for uplift; user and time-block sensitivity for behavioral logs; independent world for interacting simulation episodes; semantic family for agent tasks; whole request windows for service quantiles. Use paired cluster/block bootstrap and report cluster counts, seed variation, absolute/relative effect, interval and raw metric. Independent implementation on a small frozen fixture should match means/estimands. Multiplicity: one policy primary contrast; secondary families Holm-adjusted or explicitly exploratory. Confidence intervals do not repair confounding or source selection bias.

Report actual numbers only from immutable result JSON/Parquet. Required comparative result statuses: SUPPORTED, NOT_ESTABLISHED, UNDERPOWERED, INVALID, BLOCKED_SOURCE, BLOCKED_HARDWARE. Engineering gates: PASS/FAIL/REVIEW independent of scientific status. A baseline can be the final selected system. Results analysis must answer which component helps, when it harms, whether constraints or information advantage explain the gain, whether the added compute is worth it, and which population is actually supported.

## 15. Serving experiments

Separate inference-only, feature-to-decision, network end-to-end and agent latency. Use identical model/features/requests and report CPU vs GPU curves atbatch1,32,256 and concurrency1,4,8 when memory permits. A trained GPU model may serve better on CPU atbatch1. Use CUDA synchronization for microbenchmarks; include warmup/compile/coldstart time separately.

Proposed local small-model data-plane engineering target: p95<=50ms at100 requests/s on a declared request/candidate payload, error rate<=0.1%, zero budget double-spend or unauthorized commits in the qualification suite. This is a project target, not Amazon's production SLO. Measure p50/p95/p99 plus SLO-compliant throughput, feature freshness and fallback rate. Load test with scheduled/open-loop arrivals to avoid hiding queue delay. Agent completion is seconds-scale, separately measured; never claim LLM bidding in50ms.

Default Hugging Face inference first; vLLM is a challenger only after lifecycle compatibility and bounded-memory smoke. Termination, cancellation, queue full, GPU OOM, stale model version, process restart, idempotent replay and artifact replacement must be tested. No training simultaneous with isolated service benchmarks.

## 16. Laptop resource contract

One heavy CUDA process at a time; GPU batching/vectorized simulation gives parallel numerical work without launching many competing trainers. CPU ingestion/simulation workers start2, maximum4 until qualified. Reserve OS headroom; on a32GiB host target data/ML application memory<=20GiB, adjusted after live discovery. Query both WSL filesystem and Windows backing-volume free space.

GPU: discover exact device/VRAM/driver with nvidia-smi; do not assume desktop24GiB. Default allow one workload with<=12GiB planned CUDA memory and>=2GiB headroom, then benchmark actual peak including CUDA context/KV cache. Mixed BF16 where supported; FP32 stable losses; CPUFP64 causal/statistical reductions with numerical reference tests. QLoRA4bit base and1,024-token starting context; move to2,048 only after preflight. Precompute reference log-probabilities where library and objective support it. No simultaneous teacher/reference model copies if avoidable.

Use Windows PowerShell for orchestration and WSL2 Linux for CUDA training where qualified. Windows driver is used through WSL; do not install a separate Linux display driver or alter BIOS/overclock/power settings. Freeze Python/PyTorch/CUDA/Transformers/TRL/PEFT/XGBoost versions after tiny compute qualification; never blindly install 'latest' into an existing research environment. Separate service environment if incompatible dependencies require it.

Given previously reported abrupt shutdowns, start with health inventory and a bounded low-load numerical test, then stepped10-30min qualification with telemetry. The supervisor must checkpoint and stop on device loss, repeated CUDA failures, thermal throttling outside the qualified envelope or abrupt restart evidence. Do not automatically repeat the failed heavy workload after a hard shutdown. Operating thresholds follow device guidance/current qualification, not a fabricated universal safe temperature.

Default storage growth ceiling60GiB for core work and minimum20GiB backing-disk reserve. Inspect preexisting source/model caches first. Full iPinYou/OBD expansions require separate quota admission. No automatic deletion of original inputs, old scientific artifacts or model caches. Keep only declared best/last checkpoints per active run and compact aggregate traces; record cleanup eligibility rather than auto-delete.

## 17. Software layout and Codex execution contracts

Proposed local root: C:\Users\bjw-0\Downloads\AURORA-Ads. Preferred heavy working directory/cache is WSL ext4 (for example~/projects/AURORA-Ads and~/datasets/aurora-ads). Do not maintain two unsynchronized Git worktrees; choose one canonical source and use Windows only as a launcher/export location when appropriate. This path is a proposal, not a claim that it exists.

src/aurora/{data,features,prediction,delay,causal,auction,policies,simulator,agent,serving,evaluation,reporting}
configs/{sources,schemas,splits,models,policies,agent,experiments,resources}
tests/{unit,numerical,contracts,integration,adversarial,gpu}
reports/{desktop_study,data_audit,modeling,experiments,analysis,systems,final}
artifacts/{manifests,checkpoints,predictions,metrics,figures,claim_ledger}

Every task has input hashes, config hash, code revision, seed, resource allocation, expected outputs, timeout, retry policy, status, logs and restart rule. State machine: PLANNED->READY->RUNNING->COMPLETE/FAILED/BLOCKED. Scientific result is a separate field. Stage completion requires actual artifact presence and semantic tests, not a green exit code alone. Use atomic temp writes and a process-safe ledger; resumed runs verify hashes before continuing. Deterministic CPU reference fixtures are part of CI; GPU runs are local evidence, not implied by CPU CI.

Future CLI interface to implement (NOT currently shipped as working pipeline):
python -m aurora preflight
python -m aurora data acquire --manifest ...
python -m aurora data audit
python -m aurora run --profile core --resume
python -m aurora freeze --contract ...
python -m aurora confirm --frozen-contract ...
python -m aurora report --from-artifacts ...

One Codex master instruction may execute the DAG, but it must stop at genuine blockers: source license/auth, incompatible hardware, data clock ambiguity, preregistration missing, or invalid result contract. It may continue independent valid tracks. It must not invent data, silently replace unavailable sources, remove failed experiments, or call a simulation a real online experiment.

## 18. Final deliverables and future work

Required reports: desktop/literature; dataset audit; label-clock/leakage; baseline modeling; delay/value calibration; causal/measurement; policy experiments; agent/post-training; ablations/OOD; systems/reliability; final limitations; claim ledger. Tables need baseline, candidate, population, N independent units, estimate, CI, practical threshold, training/latency cost and disposition. Figures: reliability diagrams, maturation curves, spend/utility trajectories, cost-risk frontier, OPE support/weight diagnostics, forest plots, ablation interactions, task success-error curves and throughput-latency plots. Text comes from data-backed report templates; an optional LLM may polish prose only after all values/evidence IDs are fixed and automatically checked.

Future work after v1: real prospective shadow operation with authorization; human operator study; stronger external action-effect data; repeated-purchase/refund GMV (TRACE, subject to terms); genuinely multi-GPU deployment when hardware exists. ToT and multi-agent remain excluded from the agreed AURORA scope. Video foundation models remain unclaimed.

A valid conclusion can be conditional: delay-aware policy helps slow-feedback regimes but not immediate-feedback regimes; uncertainty control reduces harmful interventions but loses some peak value; compact baseline remains best; fine-tuning does not improve frozen prompt baseline; or power/source limits prevent a conclusion. The objective is a defensible comparative result, not a forced winning model.
