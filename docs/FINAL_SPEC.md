# AURORA-Ads v2.0: authoritative end-to-end research and implementation specification

Date: 2026-09-30. Status: DESIGN_READY_FOR_IMPLEMENTATION; not a completed ML experiment.
Scope: one project, one application LLM agent, one physical RTX 4090 Laptop GPU.
Canonical editable repository: `C:\Users\bjw-0\Downloads\AURORA-Ads`.
This specification supersedes conflicting text in BASELINE_V1_ARCHIVED.md. That file is history, not instructions.
The preparation package does not contain the implementation master prompt or a working AURORA ML pipeline.

## 0. Fixed scope and hierarchy

The application is an advertiser decision/research platform, not a general autonomous browser and not a production ad bidder. Exclude Tree-of-Thought, application multi-agent teams, recursive delegation, live advertising writes, real ad spend, paid cloud jobs, production/customer claims, and video recommendation. A deterministic verifier, a numerical optimizer, and Codex's own approval reviewer are not extra AURORA application agents.

Authority: explicit user scope > FINAL_SPEC.md + versioned contracts > experiment registry > work plans > archived v1. A conflict between active documents is a configuration error; do not silently choose whichever makes a test pass. Source schemas/terms can invalidate a proposed use, but cannot silently rewrite the intended estimand.

Deliver three separate answers:
1. Does MSCP improve the completed-episode decision objective over a strong conventional controller?
2. Does a single learned agent perform the requested, authorized workflow accurately?
3. Is the local implementation numerically and operationally qualified for its stated workload?
Do not merge these into one opaque AURORA score.

## 1. Scientific hypotheses and contribution

MSCP = Maturity- and Support-Aware Constrained Policy. It is a proposed integration of established delay prediction, supported action-value estimation, empirical uncertainty and resource control. No new regret theorem, calibrated safety guarantee or novel-method priority claim is presumed.

H_policy: in the predeclared synthetic world mixture, the paired completed-episode value difference over the validation-selected strongest qualified conventional controller exceeds a fixed practical margin under identical budgets, action bounds and mechanical guards.
H_agent: a validation-selected post-trained single-agent recipe improves family-averaged executable task success over the fixed prompt-only recipe while meeting separate proposal/commit integrity conditions.
H_delay: as-of delay modeling improves proper scoring of subsequently matured 7-day conversion outcomes versus the selected mature-only model. This is a separate real-data result, not proof of intervention efficacy.
Secondary questions cover detector observability, OPE support/identification, conditional auction replay, compute cost, and local serving.

Do not require the candidate to win. A retained baseline, conditional advantage, negative result, or an underpowered estimate is a valid completed scientific output. Implementation defects and identification failures are different outcomes.

## 2. Evidence domains and estimands

R1 Criteo Attribution: native impression CTR, descriptive conversion attribution and campaign observations. Costs/cpo are transformed. Do not turn them into currency or causal treatment labels. Criteo IDs are local to this source.
R2 Criteo Uplift v2.1: benchmark-population assignment ITT (visit primary, conversion secondary), and assignment-policy value. Source subsampling limits transport to the original platform population. Pretreatment f* only; exposure is post-assignment. No individual treatment-effect truth or invented timeline.
R3 Criteo Sponsored Search: post-click 7-day recorded conversion and attributed sales value. No impression denominator, raw creative text, purchase order identity or complete logging-arrival clock. Product title is hashed. Genuine conversion time and reporting arrival are not interchangeable: primary uses the explicit assumption received_at = click_time + observed_delay; add synthetic reporting delay as a distinct sensitivity, never a measured field.
R4 OBD men: position-conditional, fixed-policy OPE using documented action probabilities. A single-position marginal estimand is not whole-slate value. Target policy must be fixed before evaluation and use the same eligible item mapping.
R5 iPinYou: conditional observed-auction/replay study. No fabricated outcomes for newly won, historically unobserved auctions. Required only for the extended source-backed RTB module, not a dependency for every core track.
S1 Simulator: explicitly invented campaign budgets, counterfactual action effects, organic outcomes, marketplace dynamics, delays/reporting faults and authorization scenarios. Empirical marginal anchoring does not validate joint counterfactual realism.
A1 Agent tasks: executable tasks over S1; separate read-only descriptive analytical tasks over R1/R3. Source-derived figures and synthetic campaign actions have different evidence tags.

Every metric must include evidence_domain, population, unit, horizon, estimand, comparison_id, source/model/config IDs, sampling unit, missingness handling and uncertainty method. Incompatible units or evidence classes cannot be pooled. Reused public benchmark results are replication, not virgin external confirmation.

Source-exposure admission clarification (2026-10-01, before empirical model/policy evaluation): recover old source/split ledgers where available. If recorded scoped discovery does not recover them, conservatively flag the entire release potentially prior-exposed and admit freshly publisher/hash/license-verified data only for benchmark replication after other gates pass. Never reuse old metrics or assume virgin rows. An internal frozen evaluation remains replication, not unseen external confirmation. See reports/design/SPEC_AMENDMENT.md; this changes claim scope, not estimands, thresholds, payload identities, or held-out selection rules.

### 2.1 Primary policy objective: identifiable to evaluator, not leaked to learner

Use one synthetic account with 8 noncompeting campaigns in the primary environment; each opportunity belongs to one campaign and has a known eligible set. Campaigns share external shocks but have separate fixed budgets, and each controlled policy runs its own full account/world. This is not a multi-agent system. Cross-campaign competition and budget transfer are later sensitivity studies, not hidden properties of the primary world.

Decision horizon T = 14 simulated days, controller interval = 15 minutes, horizon H = 7 days for conversion maturation. Stop new decisions at T and flush outcomes through T+H. Synthetic reporting-lag sensitivities extend receipt flush separately. Endpoints never score pending nowcasts as realized value.

For world w define incremental net value against a paired no-ad world:
U(pi,w) = [Y(pi,w) - Y(no_ad,w) - Spend(pi,w) - OperationalCost(pi,w)] / B0(w).
Y is total unique simulated purchase value on the declared evaluation cohort/horizon, not impression credit. Organic and influenced purchases are represented by a single user-event ledger; no double-counting an organic purchase as an additional paid conversion. Units are synthetic cost units throughout. B0 is the same fixed initial budget for all arms.

The primary comparison is Delta_w = U(MSCP,w) - U(conventional,w). The no-ad term cancels in this contrast; neither learner is shown no-ad potential outcomes or true treatment effects. Include zero-spend/no-ad and no-change as references. If all ad policies destroy net value, abstention may be economically best and must not be hidden.

Fix the absolute practical margin to 0.01 normalized units (one percent of initial budget). This is a design choice, not a forecast or externally established economic threshold. Show relative effects only when the comparator is positive and not near zero. Do not switch between relative and absolute thresholds after seeing results.

## 3. Data procurement and data admission

Core required source capabilities: R1 impression response, R2 assignment replication, R3 temporal delay, R4 logged OPE. Acquire cache-first from the previously specified official sources; iPinYou is capability-gated optional. Failure to acquire one source blocks only its claims and dependent real-data modules. A synthetic stand-in cannot be called a completed real-data module.

`config/datasets.json` retains publisher locations and historical content hashes where present; resolve and store immutable publisher revision plus file metadata before payload. A known hash mismatch stops acquisition; never remove the hash to obtain a passing download. Existing local overrides are read-only inputs, not overwritten. Read exact source terms before license acknowledgment. Default publication excludes raw records, identifiers, derived source-grounded traces and adapters pending distribution review. No automatic GitHub publication.

Stream bounded chunks, never whole-source pandas load. Admission separates:
DOWNLOAD_COMPLETE -> CONTAINER_VALID -> SCHEMA_VALID -> CLOCK_VALID -> ANALYSIS_ADMITTED.
HTTP success or a locally computed SHA does not establish semantic correctness or publisher identity. CRC is not a cryptographic provenance proof. Quarantine malformed rows with reasons. Bound decompressed size, archive member count, compression ratio and extraction paths. Reject symlinks, absolute paths, traversal, duplicate normalized/case-insensitive members and Windows device names. No extraction into an existing nonempty workspace.

Record source and sampling funnels, missingness, categorical cardinality, label rates, valid time range, duplicate observations/conversions, support and split overlaps. Negative downsampling is allowed only with preserved sampling probabilities and loss/calibration corrections; evaluate natural prevalence. Fit imputation, clipping, hashing/vocabulary, scalers and calibrators on their permitted training partitions only. Retain raw-tail metrics beside robust sensitivity.

### 3.1 Availability clock and feature eligibility

origin_time: impression/click/decision time. information_time: earliest modeled availability of a feature. outcome_time: occurrence. received_at: arrival, observed or assumed with provenance. evaluation_available_at: when the horizon is complete.
For a snapshot t, all input information_time <= t; labels use only received_at <= t. Equal-time ordering is explicit: settle prior receipts, build snapshot, select action, reserve/commit, create new event. Features from the just-created outcome are unavailable to that action.
Forbidden R1 pre-impression fields include conversion, conversion timestamp/id, attribution, click, click_pos, click_nb and conversion-dependent cpo. Reconstruct click history as-of or exclude it. Cost is not a pre-bid feature unless its availability semantics are justified; default excludes realized cost.
R2 forbids treatment-derived exposure, visits and conversions in the feature vector. Grouping identical f* profiles prevents exact-profile leakage but does not prove different people are the same user.
R3 click_timestamp=0 and designated -1 values are missing, not actual zero time/value. Outcome fields are labels. nb_clicks_1week is used only under a documented as-of-history assumption and an exclusion sensitivity. Hashed product_gender/age_group are not used for sensitive targeting or decoded into individual attributes.

### 3.2 Locked temporal schedule for R3

Use half-open origin intervals and seconds internally. Day zero is derived from the first valid timestamp; unit conversion must be supported by README/schema checks, not just guessed by numeric magnitude.
Primary fixed model M41 is trained as-of day 41 on origins [0,41). Mature-only uses origins with origin+7 <= 41; delay models additionally use censored recent events. Calibrator C54 is fitted from M41 predictions for origins [41,47), with matured outcomes available by day54. Model/recipe selection uses origins [54,60), available by67. At day70 freeze the chosen M41+C54 pair and all settings. Final origins [70,82), fully evaluable by89. No primary refit at70: the v1 ambiguity about replacing model weights while keeping an old calibrator is removed.

A separately labeled refresh secondary may train M54 on permitted data as-of54 and calibrate it on origins [54,60) matured by67. It has its own model-calibrator ID and predeclared comparison; it is not mixed into the primary comparison. No test-informed refitting. An optional prequential secondary fixes an update rule beforehand and excludes evaluator feedback.

Main target is recorded conversion within H=7. Conversions after H are negatives for this target, not failed schema rows. Revenue label is attributed amount only for a within-H recorded conversion, zero after a complete horizon with none, and missing/censored beforehand. Do not infer unique purchase count from an unavailable order ID. H=30 is separate and only if adequate follow-up is actually established.

## 4. Modeling program

### 4.1 Predictive roster and search

P0 empirical prevalence; P1 hashed logistic/FTRL; P2 XGBoost hist/CUDA; P3 categorical embedding MLP; P4 DCNv2. Same eligible fields, natural evaluation prevalence and calibration choices. Use the development cohort (500k-2M deterministically selected eligible rows) to screen finite candidates, then scale only finalists. Up to 8 tabular configurations/family and 2 configurations/neural family; these are maximums, not promises that unequal algorithms receive equivalent optimization. Report total and per-method exposure, FLOP/time proxies and search cost.

Log loss primary; Brier, PR-AUC, AUROC, reliability curves and calibration error secondary. Proper scoring rules remain the selection basis. No use of test ECE to choose bins/calibration.

### 4.2 Delayed conversion likelihood

D0 pending-as-negative is an intentionally biased diagnostic, never the only baseline. D1 mature-only logistic/XGB is a serious candidate. D2 feedback-shift correction with documented observation assumptions. D3 logistic incidence plus conditional exponential delay. D4 neural finite-horizon discrete delay distribution.

D4: q(x)=P(C_H=1|x), f_k(x)=P(delay in bin k|C_H=1,x), sum f=1. Positive at bin k: q*f_k. No observed event by age u: 1-q*F(u). At H:1-q. For partial bins, use a fixed within-bin assumption or exact interval-censoring treatment consistently; no arbitrary floor/ceiling that systematically changes exposure time. Use stable log1p/logsumexp with tested mass/gradient limits. Define a time-zero bin if the source includes immediate conversions. Predeclared bin edges, not tuned on final delay outcomes.

D3 exponential must be conditional on H: F_H(u)=[1-exp(-lambda*u)]/[1-exp(-lambda*H)], u in[0,H], so F_H(H)=1. An untruncated exponential paired with q=P(C_H=1) is inconsistent. Verify this independently on analytical fixtures.

At a fitting cutoff, one origin contributes one likelihood, not multiple independent age snapshots. Data subsampling must retain appropriate weights. Outcome-dependent permanently missing conversions are not identified by delay correction; report recorded-outcome predictions and missingness sensitivity instead.

Value models: empirical positive-value mean; log/robust two-part model q*m; direct Tweedie or embedding regression. Log-transformed regression needs a train-estimated retransformation correction before calling exp(predicted_log) the expected monetary value. Score the full matured click cohort, not positives only. Heavy-tail clipping is sensitivity, not hidden deletion.

### 4.3 Causal replication

R2 benchmark: random allocation/response targeting, T-learner and cross-fitted DR learner; optional neural treatment-head only after core qualification. Assignment propensity status must be explicit (documented known vs estimated from released sample); no claim to recover original deployment ITT through source nonuniform subsampling. Primary capacity20%, 10%/40% secondary. Hold nuisance training, policy selection and evaluation apart. Report policy value and grouped treatment-effect calibration, never individual CATE RMSE without ground truth.

Binary R2 treatment heads cannot be relabeled as bid-up, pause or pacing causal effects. Multi-action estimates must come from randomized S1 action data with known support and the relevant state/action definition. There is no causal parameter transfer between unrelated data sources in the primary design.

## 5. Simulator, bidder and action controller

### 5.1 Transparent structural simulator

Primary weak/additive, nonlinear heterogeneous, fatigue/carryover, and reporting/competition-shift families. Include no-heterogeneity, zero-effect and negative-effect cases. All family mixture weights and parameter bounds are fixed before final. Public sources provide only permitted development anchors; synthetic joint relationships are declared assumptions.

At each opportunity draw context and exogenous competition from keyed counter-based streams. Keys contain world/opportunity/channel, not the order of policy calls. Policy state can diverge but exogenous realizations remain paired. Organic and advertised outcomes use explicit paired potential-outcome logic. Hidden oracle values, latent causes, generator coefficient identities and future outcomes are unavailable to predictors, policies, tools and the LLM.

Train/dev/calibration/test differ by entire parameter blocks; OOD mechanism tests are separate from in-mixture final confirmation. A model/simulator architecture match is not assumed. Negative-control generators include a simple parametric generator distinct from the trained candidate network. Validate source-supported marginals only; do not claim realistic causal fidelity from histogram agreement.

### 5.2 Fast bidder

Compare fixed bid, calibrated linear value bid and a grid utility optimizer. In second-price simulation expected gross value is v*F(b), expected payment E[M*1(M<=b)]; in first-price it is b*F(b). Keep floor/tie/payment rules explicit. R5 conditional replay cannot invent win labels or unseen click/conversion outcomes. Report which historical opportunity set is actually evaluated.

Scores and costs use one source-compatible unit system or pure synthetic units. Do not multiply one dataset's CTR by another dataset's post-click CVR and present it as calibrated impression value. Candidate counts/payload fixed for benchmarks. NO_BID is always mechanically available.

### 5.3 Slow campaign actions and persistence

At 15-minute intervals action set is NO_CHANGE, BID_MULTIPLIER_DOWN, BID_MULTIPLIER_UP, PACE_DOWN, PACE_UP, PAUSE_SEGMENT. Changes last one controller interval then expire to the selected default; this prevents PAUSE from becoming an accidental irreversible sink without a resume action. Bid multiplier step +/-10%, bounded[0.5,1.5]; pacing admission step +/-0.1, bounded[0,1]. Freeze these design constants before pilot outcomes. No budget increase. Cooldowns/masks identical across principal arms.

State uses budget, spend velocity, supply, eligibility, auction losses, calibrated response, age-stratified pending exposure, nowcast, detector score, freshness and action support. Detector does not secretly observe the fault label. Compare impression-only vs multi-signal rules vs XGBoost vs one compact temporal challenger. Include missed-incident cost and unnecessary-intervention cost; detected-case recovery success is a secondary conditional metric.

### 5.4 MSCP-v2 and strong baselines

Train an action-value model on randomized S1 controller decisions with finite-horizon gross observed outcomes and cost targets, using only available observation snapshots. This is a local controller surrogate, not a full-horizon causal certificate in a stateful environment.
MSCP score = predicted gross value - (1 + lambda_t)*predicted spend - action operational cost - beta*uncertainty.
This explicitly includes ordinary spend once; lambda is an EXTRA nonnegative scarcity shadow price. If Q is defined as net value in an alternative implementation, subtract lambda*spend only and declare that contract. Unit tests must prevent mixing these conventions.

Define action support using effective weighted sample size in a fixed pre-treatment representation neighborhood and OOD distance thresholds selected on validation. No raw count is called an overlap probability. Hard authorization/budget guards apply to every policy; MSCP-specific support/uncertainty selection is the component under study. Compare to a generic support-gated delay-aware conventional policy so the candidate does not win merely by receiving a unique fallback.

Separate exploration from conservative action scoring: the logging policy uses an explicit epsilon-mixture categorical distribution over currently feasible actions (epsilon fixed at0.1 for primary randomized collection). Known probabilities are those of the actually sampled categorical policy, conditional on current history. UCB can be deterministic. Thompson sampling performance can be measured prospectively without exact propensities; for OPE collect through a tractable categorical logging policy, not a Monte-Carlo frequency falsely called the original TS probability. If posterior samples form a probability vector first, then sample from it and log it, this is a DIFFERENT explicitly defined sampling policy.

No self-generated nowcast is counted as an observed reward in the primary posterior/model update. Primary observed-reward learner updates when real/horizon-mature outcomes arrive. Pending nowcasts inform state, pacing and action valuation, not independent pseudo-outcome evidence. A plug-in update variant is a secondary ablation with an event-keyed replacement ledger, unit tests and an explicit model-based label.

Pacing dual update: lambda_next = clip(lambda + eta*(actual_spend_this_interval-target_spend)/max(target_spend,unit_floor),0,lambda_max). Freeze eta/clipping schedule. Primary finite tuning grid eta {0.01,0.05,0.1}, lambda_max {2,5}; beta {0,0.5,1}; choose on development, never final. Same conservation/reservation constraints in all arms.

Baseline roster: no-ad, no-change, best safe static, rule/PID pacing, epsilon-greedy, LinUCB, neural-linear TS, delay-aware TS+primal-dual pacing, generic support-gated delay-aware controller, MPC-style pacing, MSCP. No exponential Cartesian product. Validation selects one conventional finalist; final reports both its selection rule and all predetermined reference arms.

## 6. Measurement and external policy checks

One-step DM/IPS/SNIPS/DR on fixed target policies only. Log final executed action probability after any deterministic projection: sum probability mass of ALL proposals mapping to that action. Cross-fit reward models; learned target policy is held fixed on an independent evaluation partition. Report support, clipped and unclipped estimates, effective sample size, tail weight and number of independent clusters. Reject unavailable support rather than output an impressive number. Outcome-dependent censoring can invalidate these estimators.

R4 protocol: pin one position and stable item mapping; verify propensity semantics from actual schema/official pipeline. First evaluate a fixed uniform target on the random logger as an identity/control. Use different folds for target/reward training. A contemporaneous BTS on-policy mean is NOT ground truth for an arbitrary AURORA policy. Only an exactly reconstructed documented BTS policy evaluated on matching populations can support that comparison; otherwise label cross-logger comparison diagnostic and restrict exact estimator-truth checks to S1.

R1 descriptive attribution: first-touch/last-touch/time decay plus optional Markov descriptive comparator. Deduplicate conversion ledger and show paths/impression denominators. No attribution weights as ground truth for incrementality. Root-cause prediction is predictive unless interventions identify cause.

Whole adaptive budget control is evaluated by independent prospective S1 episodes with frozen learning rules and matured outcomes. No one-step DR relabeling of a stateful horizon.

## 7. Agent architecture, training and evaluation

User continuation v2.1 prospective closure amendment (2026-10-02): the primary
four-arm development comparison uses the existing qualified Qwen3-1.7B recipes.
Retain prompt-only and at most one development-selected learned finalist, not an
extra SFT comparison when a preference recipe is selected. Same-seed SFT training
parents remain required. Core final closure defaults to qualified1.7B;4B is an
optional explicitly justified/resource-qualified selected-recipe transfer chosen
before final outcomes, not a mandatory four-arm transfer. Exact model/revision,
three finalist seeds and all inference/guard/cost/coverage gates must be frozen.
Nine frozen semantic dependence groups and UNDERPOWERED status do not change.
Historical admission code/protocols are archived; see reports/design/SPEC_AMENDMENT.md.

One Qwen3 model in a bounded single-path tool loop. Control plane only. Brief explicit plan, tool actions, observations, evidence IDs and final response are stored; no requirement to expose private chain-of-thought. No model-driven SQL outside allowlisted parameterized queries.

Nine tools retained: get_campaign_snapshot; query_metrics; estimate_outcomes; simulate_policy; recommend_action; validate_action; prepare_action; commit_mock_action; build_measurement_report. Every result carries evidence_domain, snapshot_version, unit/horizon, eligible use and artifact ID. Forbidden domain mixing is checked before report generation and commit.

Use a limited metric catalog rather than arbitrary prose calculation. Report compiler produces numbers/units/denominators from artifacts. LLM renders explanations referencing IDs; deterministic numerical/citation checks run on output. Ambiguous or unidentifiable questions return an explicit unsupported/clarify result, not a made-up lift.

Prepare binds tenant/account, campaign, version, canonical action payload, caller, expiration and evidence hash. Commit checks host-issued approval or preauthorized MOCK_ONLY policy; signatures/approval markers are unavailable to model generation. Version mismatch/retry cannot create extra spend. Use SQLite transactions on Linux ext4, one service-side writer, WAL/checkpoint tests and immutable audit events. An expiry does not release an unsettled possible spend without reconciliation. Idempotency key is caller+request contract; payload change with same key is a conflict.

Dataset targets:8000 SFT trajectories,2000 preference pairs,400 final tasks across80 semantic families. These are starting caps. Stratify analytic, diagnosis, proposal, authorized mock execution, refusal/clarification and recovery tasks. Gold traces are generated by executable public-information reference workflows, not hidden oracle best actions. Gold permits multiple valid plans. Keep all paraphrases, counterfactual variations of the same template and tightly shared schemas in one split. Test templates/scenarios never enter retrieval, corrective training or preferences.

Prompt-only baseline receives the same tools, metric documents, masks, decoding policy and context budget. Compare prompt-only, SFT, same-SFT DPO and same-SFT IPO. Preserve model/tokenizer/chat-template/revision and data hashes. Teacher/simulator gold access must not appear in the model prompt. Train assistant/tool-argument tokens only; tool observations/system context are masked. Prefix truncation that removes tool contracts or expected assistant targets is invalid, not a silently shorter example. Record dropped/truncated counts and task distribution.

Initial QLoRA rank8, sequence1024, microbatch1, accumulation16, BF16/NF4 if supported. Rank16 and length2048 are bounded development alternatives after memory qualification. Training and inference thinking mode are explicitly fixed (default non-thinking structured tool mode where supported). Completion budget is separate from context cap; bounded tool rounds8 and per-task total generated tokens2048 initially. No schema-size promise until tokenizer audit. If tools do not fit, use fixed turn-specific exposed tool subsets or a predeclared larger context, not hidden truncation.

Preference labels are lexicographic: invalid action/state first, successful task second, evidence/numeric correctness third, unnecessary calls/tokens fourth. Ties/ambiguous pairs are removed with counts. DPO and IPO use the actual documented loss; equal base/SFT/reference/pairs and token budgets. Auxiliary likelihood checks and effective optimizer-step counts are audited. GRPO is an optional separately budgeted extension after executable reward tests; not required for core completion.

Agent primary: family-macro task success, and harmful proposal rate as a separate endpoint. Also show prevented violations and committed violations so a host guard does not hide a bad model. Common guards apply to every deployed arm. Over-refusal, stale-state handling, wrong units, unsupported causal language, tool/time cost and authorized-action correctness are reported. Zero observed breaches is not zero population risk; confidence bounds and sample count required. Human-label study is optional, no human evaluation claim until completed.

Integration uses a 2x2: conventional/MSCP numerical policy x prompt-only/selected learned agent. Numeric policy comparison itself uses a deterministic workflow executor. This prevents attributing an LLM's formatting change to economic-policy improvement.

## 8. Experiment DAG and execution profiles

`config/experiments.json` is the machine-readable registry. Nodes have prerequisites by capability, permitted evidence class, resource envelope, actual completion tests and scientific outcome separate from execution status. The program is one DAG, not one uninterrupted monolithic process.

Profiles:
- smoke: pure synthetic fixtures, parsing/unit checks, tiny execution; no scientific performance claim.
- core: Criteo3 + OBD position study, small predictor ladder, delay/value, causal replication, simulator/incident/policy, SFT/DPO/IPO, integration, ablation, serving, locked confirmation, report.
- extended: admitted iPinYou replay, bounded GRPO, optional larger HPO/scale. None is required for core completion.

Phases preserve E00-E16, but E15 is split into freeze, policy confirmation, agent confirmation and empirical confirmation. The final reporting node accepts terminal outcomes of all declared tracks, including blocked/underpowered, and reports the coverage matrix. It never labels a partially executed project fully empirically validated. Core valid tracks continue if optional source acquisition fails. Agent tools can be built/tested with synthetic reference policies before numerical candidate selection; no unnecessary E09->every agent engineering dependency.

Frozen final comparisons cannot be rerun to seek a favorable seed or threshold. Legitimate evaluator bug repair retains immutable predictions, old results and an invalidation record. A changed scientific estimand/model requires a new study ID and newly qualified holdout, not overwriting the original result.

## 9. Statistical contract

One primary policy contrast, practical margin0.01 normalized utility, independent paired world mean. Report two-sided95% paired cluster/bootstrap interval, primary point estimate, absolute/relative where meaningful and distribution of world effects. Claim practical superiority only if the lower CI exceeds the practical margin; otherwise distinguish directional evidence from material superiority. No shifting to a larger/smaller margin after final.

Use20 independent pilot worlds, excluded from final, to estimate paired variability. Target final N within40-200; if power to distinguish Delta=0.02 from null boundary0.01 is inadequate at cap, run and report UNDERPOWERED (not a proof of no benefit). The effect0.02 is a planning alternative, not an expected outcome. Freeze N before final outcomes. Budget may change the labeled profile before final, not the evidence threshold afterward.

Worlds contain common campaign shocks; campaigns/events are not independent replicates. Multiple controller RNG seeds within one world are averaged before the world-level contrast or handled by a preregistered hierarchical analysis. Per-seed results are always shown. Agent CIs cluster by semantic family; three training seeds are separately reported and do not create1200 independent tasks. Real temporal analyses use user/time-block sensitivity; exact inferential assumptions and effective cluster count are reported. No causal identification claim from narrower bootstrap intervals.

H_policy and H_agent are separate primary families, no combined global superiority claim. Named secondary comparisons within each family use Holm or explicitly exploratory intervals. Ablations are predeclared component-fixed experiments: remove delay input, support gate, uncertainty penalty or dual pacing while keeping common mechanical guards. Add2x2 delay x reliability interaction. OOD shifts are either locked predetermined confirmation or explicitly post-final diagnostic, never both.

A/A and null calibration: test zero action effect, equal policies, known synthetic effects, label shuffle, support failure, receipt-time leakage traps, and duplicate reward/conversion traps. Compare independent reference estimators on small fixtures. Monte Carlo coverage tests are required during implementation; included preparation reference tests are algebraic sanity checks, not achieved coverage.

## 10. Engineering, testing and observability

CPU CI: lint/type/unit/schema/property/numerical/transaction tests, synthetic smoke integration, manifest integrity, source-contract validation. Local GPU: actual one-update/backward/checkpoint-reload tests, finite gradients, memory, numerical tolerances and device telemetry. Hosted CPU CI never claims it executed GPU training.

Test matrix includes: nonconversion likelihood limits, truncated exponential F(H)=1, loss masks, observed vs pending replacement, guard probability mass conservation, propensity normalization, DR oracle identities, counterfactual deduplication, budget reserve/settle under concurrent retries, stale prepare/commit, timeout after successful commit, allowed SQL only, tenant separation, prompt injection, future clock contamination, experiment-DAG independence, artifact hash mismatch and resume replay.

Every run records wall time, GPU lease occupancy, successful/failed attempts, effective tokens/examples, peak CUDA allocated/reserved plus device total used, RAM/disk, versions, seeds and origin/receipt cutoffs. Runtime degradation is not silently repaired by changing model/context precision during final.

Serving: inference-only, feature-to-decision, HTTP end-to-end and agent completion are separate. Open-loop scheduled requests; latency measured from scheduled arrival so queue delay/coordinated omission is visible. Rejections/timeouts counted in error/deadline rates, not removed from p95. Stable payload/candidate count, independent windows, startup/compile cost, cold/warm cache and shutdown metrics. Project target: fast path100RPS,p95<=50ms,error<=0.1%; no claim this is Amazon's SLO. LLM completion measured in its own scale. Isolated benchmark has no concurrent training; contention test is labeled separately.

Numerical GPU/CPU parity tolerances depend on operation, with FP64 reference for estimators. No universal bitwise GPU determinism claim; exact/approx replay contract is recorded per component.

## 11. Windows/WSL execution layout and safety

Canonical source is the requested Windows repo; no second editable clone in WSL. Heavy runtime is WSL ext4 at `$HOME/.local/share/aurora-ads`: data, caches, envs, runs, state and temp. Runtime marker binds repo identity. SQLite and active checkpoints stay ext4. Small reports/manifests are exported to Windows. Working source may be read via /mnt/c; editable install points to this canonical source. If immutable execution snapshots are used, they are hash-bound read-only artifacts, never a second development tree.

Native PowerShell7 launches native Codex; WSL Ubuntu-22.04 is for qualified Python/CUDA. Do not install a Linux NVIDIA display driver, change BIOS/power settings or reboot automatically. Python environment is new and project-scoped; no mutation of old project environments. No dependency 'latest' sweep. Build/pin exact requirements after smoke qualification; hashes and hardware version go into runtime lock.

2026-09-30 read-only local observation: PowerShell7.6.6; codex-cli0.155.1; help advertises --approve-for-me and --strict-config; Ubuntu-22.04 WSL2 present; GPU16376MiB total; temperature77C at the snapshot. This is installation/inventory evidence only, NOT a health or CUDA qualification. Prior abrupt GPU shutdown concerns require a explicit hardware qualification artifact. Do not start stress/training merely because a GPU is present. Current sensor values must be reread before future workloads.

One heavy GPU owner, batch/vectorized numerical parallelism, CPU workers2 initially maximum4 after qualification. Initial planned GPU allocation<=12GiB and headroom>=2GiB, application RAM target<=20GiB on32GiB host. Limit initial growth60GiB with20GiB backing-volume reserve; expanded artifacts require quota review. Device total includes display/other processes. Do not kill unrelated tasks to free VRAM. No silent CPU training fallback. CPU reference/statistics/ingestion remain allowed.

Recognize OOM vs device loss vs hard shutdown separately. A recoverable development OOM may lower batch under a new recorded runtime config; protected experiments cannot silently change effective protocol. Device loss, unexplained restart or thermal instability blocks heavy work pending renewed qualification. No repeated automatic retry of a shutdown-triggering run. Review logs without diagnosing a hardware cause from Kernel-Power alone.

GPU planning quotas retained:24h predictive/delay/causal,12hpolicy,36hagent,12heval/systems,optional12hGRPO. These are allocation caps, not a runtime promise. Microbenchmarks before full run. Duration includes failed attempts and reference generation. Rate/quota/session interruption yields checkpoint/resume, not hidden background execution or fabricated completion.

## 12. Interactive Codex boundary

The installed native CLI currently supports `--approve-for-me`: use it. It routes eligible approvals to automatic review while retaining workspace-write; it is not --yolo and not never-approval. The preparation script verifies local help again at execution. Unsupported flag/policy stops with a useful error, never silently switches to full access. Keep managed settings intact. Do not replace reviewer policy with 'approve everything'.

Preparation can create the specified empty repo, verify bundle hashes, initialize the scoped ext4 runtime and collect read-only inventory. It must not submit a prompt, run codex exec, train, download GB datasets or install ML packages. With -StartCodex it opens the native interactive TUI WITHOUT a positional prompt. Login/trust/UAC/managed-policy interactions may still require user action; zero interruption is not guaranteed.

Project docs are not an approval bypass. An escalated WSL command must be reviewed for its exact script, runtime target and side effects, not auto-allow the entire wsl.exe/python prefix. Existing user config/plugins are not rewritten. Model choice remains the user's current supported setting; local GPU is for AURORA open-model experiments, not necessarily Codex inference. No application multi-agent system is introduced by Codex's approval mechanism.

## 13. Complete output set and finish definition

Produce desktop/prior-art matrix, source and clock audit, EDA, sampling/exclusion funnels, model/delay/value comparisons, causal replication, OPE support/assumptions, optional replay, simulator qualification, detector policy study, single-agent post-training, integration factorial, ablations/OOD, serving/recovery, cost/reproducibility, and final technical report.

Result record fields: evidence_domain, primary/secondary/exploratory, estimand_id, population, independent_unit_count, method/comparator, metric/unit/horizon, estimate, difference, CI, margin, compute, constraints, scientific_outcome, execution_status, source/config/model hashes, limitations. Claim ledger may publish only artifact-backed claims. No numerical placeholder is a measured result.

Completion layers:
DESIGN_READY: specification, contracts and preparation tests consistent.
ENGINEERING_EXECUTED: real code, qualified synthetic smoke, typed tools, actual artifact pipeline.
CORE_TRACKS_CLOSED: every core track has a terminal disposition and a report, even if some are blocked.
CORE_EMPIRICAL_COMPLETE: every required empirical capability was actually executed with valid outputs; blocked/invalid required tracks forbid this label.
SCIENTIFIC_SUPPORTED: only named hypotheses with their own tests passed.
No layer implies production deployment or commercial experience.

Future work is driven by failure modes: genuinely new action-effect data; prospective shadow operation with authorization; real human operator labels; longer-horizon purchase/refund dynamics; external hardware. Do not add ToT/multi-agent/video scope automatically. Final result may preserve simpler policies and still be an excellent, bounded research artifact.


## Final DAG implementation note

The machine-readable `config/experiments.json` expands conceptual E13/E15 into independent POLICY, AGENT, R1 and R3 subtracks. In particular, an invalid agent reward function cannot block the numerical policy's separate freeze/confirmation, and an unavailable R3 source cannot block R1 confirmation. E15_INTEGRATION legitimately requires both qualified policy and agent freezes. E16 waits for actual terminal track dispositions, including blocked/invalid tracks, rather than requiring every result to be favorable. E01 publishes per-source admission capabilities; partial source admission does not invalidate unrelated sources. This final split supersedes any coarse E13/E15 dependency description above.


### Quantitative workload defaults and semantic-family admission

`config/simulator.json` supplies the initial finite workload: nominal32 opportunities per campaign per15-minute interval,8 campaigns,14 decision days, or344064 expected opportunities per world before shocks. Tight/balanced/loose initial campaign budgets are4000/10000/20000 synthetic cost units, not observed advertiser currency. Synthetic market-price median is one cost unit. Final family weights are initially equal. These are transparent design constants; development may version amendments before any final generation. Purchase-value scale, effect ranges, carryover, reporting process and operating costs must be frozen from development assumptions, not tuned to make MSCP win. No final realized future traffic is used to determine budgets.

The planned80 agent semantic families are an admission target, not permission to rename paraphrases as independent groups. The actual root-template/schema dependency audit determines cluster count. If only20 genuinely distinct families remain, report20 and redo pre-final power planning. Preserve shared-generator dependence in sensitivity analysis.

The explicit transparent S1 reference equations, auction conventions and timing defaults are in `docs/SIMULATOR_CONTRACT.md`. This document and the JSON simulator config must be versioned together before final generation.


### Matured-policy feedback schedule

The final primary decision horizon is14days plus7days of outcome flush, not the v1 seven-day decision horizon. With a7day outcome target, a seven-day episode would contain almost no fully matured self-generated negative/cohort feedback during decision making. The longer horizon makes an actual choose-observe-update comparison possible. Each action reward belongs to the disjoint set of opportunities ORIGINATING in that15minute action interval; its completed value is evaluated by the7day outcome cutoff for those occasions. Do not assign all purchases in an overlapping seven-day campaign window to each interval action.

Primary action-value/bandit posterior updates use fully matured interval cohorts, including completed zero values. Partial positive receipts and nowcasts update observable state but are not treated as completed cohort rewards. The separate delay predictor may refit a proper censored likelihood on one as-of snapshot per origin; it cannot count repeated age snapshots as independent data. A seven-day decision episode remains a development/smoke sensitivity, not the main claim of self-generated mature-feedback learning. Budget scale is correspondingly fixed at4000/10000/20000 synthetic units per campaign for tight/balanced/loose regimes before final generation.
