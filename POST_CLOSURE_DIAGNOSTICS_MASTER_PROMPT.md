# AURORA-Ads Post-Closure Diagnostics Master Prompt v1
# Production-style validation, calibration, model-risk, monitoring, and materiality analysis

Repository: C:\Users\bjw-0\Downloads\AURORA-Ads

AURORA-Ads E00-E16 is already closed. Do NOT reopen or mutate the closed primary research program.
The authoritative final state is CLOSED_WITH_DOCUMENTED_EVIDENCE_LIMITS and the primary completion audit is true.

This is a new, explicitly separate POST_CLOSURE_DIAGNOSTICS_V1 program.
Its purpose is to explain, validate, stress, monitor, and operationalize the already-frozen evidence.
It must never rescue, rewrite, reselect, recalibrate, or relabel the closed primary results.

Hard invariants:
- PRIMARY_RESULTS_CHANGED = false
- MODEL_RESELECTION = false
- PRIMARY_CALIBRATOR_REFIT = false
- PRIMARY_THRESHOLD_RESELECTION = false
- FINAL_OUTCOME_TUNING = false
- PRIMARY_E00_E16_LEDGER_MUTATION = false
- PRODUCTION_CLAIM_UPGRADE = false
- BLOCKED_TRACK_REOPEN = false

Create a separate state namespace:
- reports/posthoc/
- reports/posthoc/state/POSTHOC_STATUS.json
- reports/posthoc/POSTHOC_DIAGNOSTIC_LOG.md
- reports/posthoc/POSTHOC_EVIDENCE_LEDGER.csv

Do not change the meaning or status of any E00-E16 node.
## 0. Resume and evidence rules

Before writing code or analysis:
1. read WORK_STATE.md;
2. read reports/final/FINAL_TECHNICAL_REPORT.md;
3. read reports/final/FINAL_STATUS.json;
4. read reports/final/RESULTS_MATRIX.csv and CLAIM_EVIDENCE_LEDGER.csv;
5. read reports/final/LIMITATIONS_THREATS_TO_VALIDITY.md;
6. read model/policy/causal/OPE/R3/serving primary artifacts;
7. inspect existing raw prediction, trace, receipt, trajectory, bootstrap, and telemetry files;
8. inspect actual processes and resource state.

Source precedence:
canonical immutable artifacts > final pointers/hashes > current files > historical narratives.

Prefer saved predictions/traces/receipts.
If a diagnostic requires predictions that were not saved, frozen deterministic rescoring is allowed ONLY when all model/data/transform identities are verified and unchanged.
Label every such run POSTHOC_DIAGNOSTIC_RESCORE_ONLY.
Never use diagnostic rescoring to alter selection, calibration, thresholds, or primary claims.

Do not recreate a final experiment merely to obtain a more convenient diagnostic.
No new primary training.
No new primary policy search.
No new final sample size.
No reopening blocked agent/R3/GPU confirmation tracks.

Confidence intervals are allowed only when the independent unit is defensible.
Otherwise report descriptive distributions and explicitly state the dependence limitation.
## 1. Freeze a post-closure diagnostic protocol before inspecting new post-hoc outputs

Create:
reports/posthoc/POSTHOC_DIAGNOSTIC_PROTOCOL.md
reports/posthoc/PRIMARY_CLOSURE_SNAPSHOT.json

Snapshot and hash:
- FINAL_STATUS.json
- FINAL_TECHNICAL_REPORT.md
- RESULTS_MATRIX.csv
- CLAIM_EVIDENCE_LEDGER.csv
- R1 freeze/confirmation
- R2 causal artifact
- R4 OPE artifact
- E09 corrected development selection
- E13 diagnosis/ablation artifacts
- E15 policy freeze/confirmation
- R3 CPU development artifacts
- agent training/restart/resource artifacts
- E14 CPU serving/recovery artifact

The protocol must define all slices, metrics, bootstrap/block units, materiality measures, and monitoring-threshold construction BEFORE computing diagnostic outputs.

External framing may cite:
- Federal Reserve model-risk guidance: conceptual soundness, outcome analysis, benchmarking/challengers, ongoing monitoring, materiality, limitations;
- NIST AI RMF as general lifecycle risk framing;
- scikit-learn probability calibration guidance for reliability diagnostics;
- Google production ML monitoring guidance for skew/drift monitoring.

Do not claim regulatory compliance. These are validation-design references only.
## 2. D01: model inventory and materiality map

Build reports/posthoc/MODEL_INVENTORY.csv and MATERIALITY_MAP.csv.

Inventory every material model/controller/component:
- R1 prior/FTRL/logistic/XGBoost/MLP/DCNv2 and calibrators;
- R2 response/T-learner/DR nuisance and policy scorers;
- R4 DM/IPS/SNIPS/DR estimators;
- S1 nuisance/value/support models and conventional/MSCP controllers;
- R3 mature incidence, feedback-shift, value, failed D3 candidate;
- SFT/DPO/IPO adapters as trained-but-semantically-unscored components;
- serving frozen observed-only numerical mean component.

For each record include:
purpose, evidence domain, inputs, outputs, training population, evaluation population,
materiality/exposure proxy, primary metric, challenger, validation status, calibration status,
stability status, implementation risk, data risk, extrapolation risk, monitoring risk,
allowed use, prohibited use, known limitations, and evidence pointer.

Materiality proxies must be domain-appropriate and evidence-backed:
population share, spend share, predicted/observed value share, utility contribution,
loss contribution, traffic/load share, or unavailable.
Never invent commercial exposure.
## 3. D02: R1 predictive calibration, residual, challenger, and stability diagnostics

Use the frozen final R1 population and frozen predictions if saved; otherwise verified frozen diagnostic-only rescoring.

For every serious R1 candidate, especially development-selected DCNv2 and conventional XGBoost:
- equal-width reliability diagrams: 10 and 20 bins;
- equal-frequency/adaptive reliability diagrams: 10 and 20 bins;
- calibration-in-the-large / intercept;
- calibration slope;
- ECE, adaptive ECE, MCE;
- Brier score decomposition into reliability/resolution/uncertainty where mathematically valid;
- high-confidence tail calibration;
- bootstrap/block uncertainty using the same defensible dependence units as the primary study.

Residual diagnostics:
signed residual y-p, absolute residual, per-example logloss contribution, Brier contribution,
entropy, overprediction tail, underprediction tail, top 1/5/10% loss contributors.

Pre-freeze slicing roster:
score decile; native time block; campaign or documented group; prevalence regime;
major feature quantile/category slices where interpretable; sparse-support vs dense-support;
prediction-entropy bucket; extreme-score tails.

Create:
R1_CALIBRATION_DIAGNOSTICS.json
R1_CALIBRATION_SLICES.csv
R1_RESIDUAL_SLICES.csv
R1_CALIBRATION_FIGURES/
R1_MATERIALITY_SLICES.csv
## 4. D03: R1 challenger disagreement attribution and stability

Compare DCNv2 against XGBoost, MLP, logistic/FTRL, and prior where frozen predictions exist.

Compute:
prediction correlation; absolute score disagreement; disagreement deciles;
ranking inversion rate; model-consensus dispersion; challenger win rate by slice;
incremental logloss and Brier contribution by disagreement bucket;
share of total selected-vs-challenger loss difference explained by top disagreement buckets;
high-materiality disagreement by population/value/spend proxy where valid.

Stability:
time-block metric stability; calibration-slope/intercept stability; score-quantile stability;
top-decile membership stability; bootstrap prediction/rank stability; challenger ordering stability.

For linear/logistic models only, add coefficient/sign stability if frozen coefficients and valid resampling are available.
For deep/tree models, prefer functional/output stability over parameter-weight stability.

Create:
R1_CHALLENGER_DISAGREEMENT.csv
R1_DISAGREEMENT_ATTRIBUTION.json
R1_STABILITY_DIAGNOSTICS.json
## 5. D04: R2 causal/uplift model-risk diagnostics

Keep released-sample and replication limitations intact.

Analyze:
- estimated propensity distribution and overlap;
- propensity deciles and tail concentration;
- ESS overall and by relevant slice;
- treatment/control support imbalance;
- CATE/uplift calibration using cross-fitted DR pseudo-outcomes on diagnostic holdout only;
- predicted-CATE deciles versus mean DR pseudo-outcome;
- monotonicity and sign consistency;
- policy value/materiality at 10%, 20%, 40% capacities;
- overlap-sensitive slices;
- policy disagreement sets:
  both selected, DR-only, response-only, neither;
- value attribution of those disagreement sets;
- stability across frozen feature-profile clusters or other defensible units.

Do not claim individual treatment-effect truth.
Do not reconstruct undocumented original assignment probabilities.

Create:
R2_PROPENSITY_OVERLAP.csv
R2_UPLIFT_CALIBRATION.csv
R2_POLICY_DISAGREEMENT.csv
R2_CAUSAL_MODEL_RISK.json
## 6. D05: R4 OPE risk and influence diagnostics

Using the frozen logged-policy artifact and saved row/weight evidence where available:
- raw importance-weight distribution;
- clipped-weight distribution;
- p50/p90/p95/p99/p99.9/max weights;
- ESS overall, per action, and per UTC day;
- fraction of total weight from top 0.1/1/5%;
- support-violation and near-zero-support rates;
- DM vs IPS vs SNIPS vs DR estimator disagreement;
- clipping-threshold sensitivity curve as POST_HOC sensitivity only;
- day-by-day estimator drift;
- influential-observation or influence-concentration analysis where saved evidence permits;
- action-frequency mismatch.

Because only two final UTC days exist, never manufacture population inference from row count.
Separate estimator-instability risk from calendar-power risk.

Create:
R4_WEIGHT_RISK.csv
R4_ESTIMATOR_DISAGREEMENT.csv
R4_OPE_MODEL_RISK.json
## 7. D06: frozen policy final-world regime, materiality, and decision diagnostics

Use the saved 200-world final confirmation and its verified arm receipts.
Do NOT change H_policy or rerun final selection.

Slice the frozen contrast by the predeclared/observable dimensions available in receipts:
simulator family; parameter block; budget tier; horizon phase; campaign;
incident state; support regime; uncertainty regime; supply/scarcity regime;
predicted-value regime; action family where available.

For each slice report:
n defensible units; population/world share; baseline mean; MSCP mean; paired difference;
purchase-value contribution; spend contribution; operational/intervention-cost contribution;
share of total utility gap; tail-loss contribution.

Action diagnostics where saved trajectories exist:
action frequencies; transition matrix; NO_CHANGE persistence; bid-up/down/pause use;
action churn; reversal rate; budget exhaustion timing; pacing pressure; support-gate activation.

Decision-margin diagnostics only if frozen score traces or exact deterministic stored-state replay permit it.
Never rerun stochastic final worlds merely to create margins.
If unavailable, mark unavailable.

Create:
POLICY_FINAL_REGIME_SLICES.csv
POLICY_MATERIALITY_ATTRIBUTION.csv
POLICY_ACTION_DIAGNOSTICS.json
POLICY_DECISION_MARGIN.json
## 8. D07: policy nuisance/value calibration and development-to-final stability

Evaluate frozen nuisance/value predictions against matured observed synthetic outcomes with correct target semantics:
- gross-value calibration;
- spend calibration;
- action-specific outcome calibration where observed support permits;
- calibration intercept/slope;
- reliability by prediction decile;
- residual heteroscedasticity;
- calibration by support/ESS, uncertainty, action, budget, and mechanism family;
- development vs final calibration/stability comparisons.

Never relabel gross purchase value as incremental value.
Never use evaluator oracle truth that the deployed policy would not observe.

Add:
POLICY_NUISANCE_CALIBRATION.csv
POLICY_RESIDUAL_SLICES.csv
POLICY_DEV_FINAL_STABILITY.json

Also quantify whether the MSCP loss is primarily:
model bias, cost/objective mismatch, default-bid exposure, support gating, uncertainty penalty,
dual/pacing behavior, or interaction.
This is attribution/diagnosis, not causal identification unless the design supports it.
## 9. D08: R3 post-hoc source/model diagnostics

Use development/selection evidence only. No blocked GPU ladder reopening and no final R3 scoring.

Analyze:
delay-label missingness by time/origin and feature regime;
known-vs-unknown outcome materiality;
delay buckets and tail behavior;
amount/value tail concentration;
exact-record duplicate sensitivity;
origin-time stability;
mature-logistic versus feedback-shift disagreement;
value-model disagreement;
calibration on mature known-outcome subsets;
partial-identification bounds across meaningful slices.

For failed D3 fits, analyze only recorded optimizer traces/checkpoints:
gradient norm, objective path, parameter magnitude, convergence diagnostics, conditioning if available.
Do not extend iteration limits to rescue convergence.

Create:
R3_MISSINGNESS_SLICES.csv
R3_VALUE_TAIL_RISK.csv
R3_MODEL_DISAGREEMENT.csv
R3_POSTHOC_MODEL_RISK.json
## 10. D09: agent training/resource diagnostics only

Agent semantic outcomes remain UNSCORED and BLOCKED_HARDWARE.
Do not reopen semantic tasks.

Analyze saved SFT/DPO/IPO training/restart/resource artifacts only:
loss trajectory; update stability; checkpoint integrity; adapter norms if safely available;
training wall time; VRAM; temperature; power; restart reproducibility;
resource-stop chronology; duty-profile evidence; monitoring timeout behavior.

Distinguish:
training success, restart reproducibility, inference resource qualification, and semantic performance.

No semantic ranking among SFT/DPO/IPO.

Create:
AGENT_TRAINING_STABILITY.json
AGENT_RESOURCE_RISK.csv
AGENT_MODEL_RISK_NOTES.md
## 11. D10: serving tail/saturation and reliability analysis

Use both preserved E14 attempts.
Attribute latency into component compute, feature/provisional ranking, HTTP, queue, startup/compile, and recovery overhead where measured.

Analyze:
offered rate vs p50/p95/p99; concurrency vs tail latency; queue amplification;
cold vs warm; eager vs compiled; batch scaling; saturation knee;
latency coefficient of variation; worst-window attribution;
resource usage vs latency; HTTP error/timeout counts;
retry/restart/cancellation overhead; failed first attempt cost.

Do not infer GPU, complete-agent, full-policy, or production SLO performance.

Create:
SERVING_LATENCY_SLICES.csv
SERVING_SATURATION_CURVE.csv
SERVING_TAIL_ATTRIBUTION.json
SERVING_POSTHOC_RISK_REPORT.md
## 12. D11: post-hoc threshold sensitivity, monitoring thresholds, and runbook

Primary thresholds remain frozen. This section does NOT choose new primary thresholds.

For relevant model/policy thresholds, create sensitivity curves:
coverage vs error/loss; support threshold vs coverage/utility; uncertainty threshold vs coverage/risk;
decision-margin threshold vs abstention/utility where evidence exists.

Then design PROVISIONAL OFFLINE monitoring thresholds using frozen reference/development distributions.
Prefer bootstrap/control-limit or reference-quantile construction over arbitrary numbers.

Monitor at minimum:
Data: schema failures, missingness, unseen categories, feature quantile drift, PSI/JS where valid.
Prediction: mean, variance, p10/p50/p90/p99, entropy, score drift.
Outcome: prevalence, logloss, Brier, ECE, calibration slope/intercept.
Causal/OPE: propensity tails, ESS, weight concentration, estimator spread.
Policy: action mix, support-gate rate, uncertainty penalty, budget exhaustion, action churn, realized utility.
Systems: p50/p95/p99 latency, queue delay, error rate, timeout/restart, RAM/VRAM/temperature.

For each metric define:
reference population/window, warning threshold, action threshold, cadence, owner role,
diagnostic action, remediation/escalation, and limitation.

Label all thresholds PROVISIONAL_OFFLINE_NOT_PRODUCTION_SLO unless already frozen otherwise.

Create:
THRESHOLD_SENSITIVITY.csv
MONITORING_THRESHOLDS.csv
MONITORING_THRESHOLDS.json
MONITORING_RUNBOOK.md
## 13. D12: model-risk register and challenger matrix

Create MODEL_RISK_REGISTER.csv with one row per material component.

Columns:
model_id, purpose, evidence_class, materiality, inherent_risk, data_risk, calibration_risk,
stability_risk, extrapolation_risk, implementation_risk, monitoring_risk,
challenger_id, challenger_disagreement, validation_status, residual_risk,
allowed_use, prohibited_use, key_limitations, monitoring_metrics,
warning_thresholds, action_thresholds, remediation, evidence_pointer.

Use transparent ordinal ratings such as LOW/MEDIUM/HIGH only when backed by documented criteria.
Write the rating rubric before assigning ratings.

Create CHALLENGER_MATRIX.csv:
primary/challenger, metric gap, calibration gap, disagreement rate, high-materiality disagreement,
stability gap, operational complexity, evidence strength, recommended role.

Do not recommend production use.
The output is a research model-risk package, not a regulatory certification.
## 14. D13: portfolio materiality slicing

For every domain where valid, quantify not just slice performance but slice contribution to portfolio risk.

Each materiality table should include:
slice, population share, spend/exposure proxy share, observed/predicted value share,
total loss contribution, excess-loss contribution versus challenger,
calibration-error contribution, utility-gap contribution, tail-risk contribution.

Produce Pareto summaries identifying slices that are small in population but large in loss/risk contribution.

Create:
PORTFOLIO_MATERIALITY_SLICES.csv
MATERIALITY_PARETO.json
figures/materiality_*.png or .svg

No commercial-dollar translation unless directly supported by the evidence.
## 15. Final post-closure deliverables

Create:
reports/posthoc/POSTHOC_MODEL_RISK_REPORT.md
reports/posthoc/POSTHOC_EXECUTIVE_SUMMARY.md
reports/posthoc/POSTHOC_EVIDENCE_LEDGER.csv
reports/posthoc/MODEL_RISK_REGISTER.csv
reports/posthoc/CHALLENGER_MATRIX.csv
reports/posthoc/MONITORING_THRESHOLDS.csv
reports/posthoc/MONITORING_THRESHOLDS.json
reports/posthoc/MONITORING_RUNBOOK.md
reports/posthoc/PORTFOLIO_MATERIALITY_SLICES.csv
reports/posthoc/POSTHOC_RESUME_SUPPLEMENT.md
reports/posthoc/POSTHOC_INTERVIEW_SUPPLEMENT.md
reports/posthoc/state/POSTHOC_STATUS.json
reports/posthoc/figures/

The final report must explicitly state:
PRIMARY_RESULTS_CHANGED=false
MODEL_RESELECTION=false
PRIMARY_CALIBRATOR_REFIT=false
PRIMARY_THRESHOLD_RESELECTION=false
FINAL_OUTCOME_TUNING=false
E00_E16_STATUS_UNCHANGED=true

Do not overwrite reports/final/*.
Post-hoc outputs are supplements, not replacements.
## 16. Validation and completion

For every analysis:
- bind input artifact hashes;
- bind code/config hashes;
- save exact argv and timestamps;
- retain failures;
- validate schemas and numeric ranges;
- use deterministic seeds where needed;
- never silently drop missing/unavailable slices;
- distinguish row count from independent-unit count;
- distinguish descriptive uncertainty from population inference.

Run appropriate unit tests, semantic checks, lint, and independent saved-file verification.

Create a post-hoc completion audit that checks:
all declared diagnostic tracks are EXECUTED, BLOCKED_WITH_REASON, or NOT_APPLICABLE;
all required deliverables exist;
all source hashes resolve;
no primary final artifact changed;
reports/final hashes remain identical to the closure snapshot;
no E00-E16 ledger status changed;
no primary claim was upgraded.

Stop when POST_CLOSURE_DIAGNOSTICS_V1 is terminal.
Do not expand scope indefinitely.

Begin by freezing the protocol and closure snapshot, then execute the diagnostics autonomously.
