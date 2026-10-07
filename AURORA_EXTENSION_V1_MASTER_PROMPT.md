# AURORA-Ads Extension V1 Master Prompt
# Close the remaining technically feasible gaps without rewriting the closed primary study

Repository: C:\Users\bjw-0\Downloads\AURORA-Ads

AURORA E00-E16 and POST_CLOSURE_DIAGNOSTICS_V1 are already terminal.
This is a NEW supplemental engineering/research program named AURORA_EXTENSION_V1.

The purpose is to execute every remaining technically feasible gap on the current local machine and admitted public data while preserving the closed primary evidence exactly.

Hard invariants:
- E00_E16_STATUS_UNCHANGED = true
- POSTHOC_V1_STATUS_UNCHANGED = true
- PRIMARY_RESULTS_CHANGED = false
- PRIMARY_HYPOTHESES_REWRITTEN = false
- FINAL_OUTCOME_TUNING = false
- PRIMARY_MODEL_RESELECTION = false
- PRIMARY_POLICY_RESELECTION = false
- NO_PRODUCTION_CLAIM_UPGRADE = true
- NO_LIVE_AD_WRITES = true
- NO_REAL_AD_SPEND = true

Do not edit or overwrite reports/final/*, reports/posthoc/*, historical primary result artifacts, frozen ledgers, or old failure artifacts.
All new work lives under extensions/aurora_v1/, reports/extension_v1/, and an independent extension state ledger.

## 0. Source of truth and startup

Before any mutation:
1. read WORK_STATE.md;
2. read FINAL_SPEC.md and SIMULATOR_CONTRACT.md;
3. read reports/final/FINAL_STATUS.json, FINAL_TECHNICAL_REPORT.md, REQUIREMENT_COVERAGE.md;
4. read reports/posthoc/state/POSTHOC_STATUS.json and POSTHOC_MODEL_RISK_REPORT.md;
5. verify final/posthoc hashes and canonical generation91 identities;
6. inspect actual owned processes, Windows/WSL disk/RAM, GPU temperature/VRAM/utilization;
7. inspect existing frozen policy receipts, agent checkpoints, R3 cohorts, OBD source, serving artifacts.

Create:
reports/extension_v1/EXTENSION_PROTOCOL.md
reports/extension_v1/PRIMARY_AND_POSTHOC_SNAPSHOT.json
reports/extension_v1/state/EXTENSION_STATUS.json
reports/extension_v1/EXTENSION_LOG.md

Freeze the extension protocol and all slice/evaluation/admission rules before opening NEW extension semantic or R3 final outcomes.

The historical status BLOCKED_HARDWARE means the old resource contract failed. It is not proof of physical GPU damage.
No historical blocker may be relabeled; extension evidence gets new IDs and new status.

## 1. Resource scheduler and safety

Do CPU-safe work first while GPU headroom is uncertain.
Do not kill unrelated applications or jobs.
Do not change BIOS, NVIDIA driver, Windows power mode, global WSL configuration, or unrelated environments.

Preserve the historical safety limits unless the extension protocol is MORE conservative:
- device-reported target <= 87C;
- >= 2 GiB free VRAM;
- one heavy AURORA CUDA owner;
- no silent CPU substitute for a CUDA-specific extension claim.

Before every GPU workload require a fresh preflight with:
- exact GPU UUID/device identity;
- Windows-native temperature, VRAM, utilization, power;
- WSL CUDA visibility;
- no existing AURORA heavy CUDA process;
- sufficient thermal headroom defined prospectively in EXTENSION_PROTOCOL.md.

If current temperature/headroom is unsuitable, continue CPU work and defer CUDA work.
A detected thermal/device-loss/instrumentation failure ends that workload and is preserved.

Do not automatically retry a hardware-risk failure.

## 2. Extension GPU Monitor V2

The original SFT 10s/30s failures were synchronous WSL nvidia-smi timeout failures, while the 5s profile also reached the thermal target.
NVIDIA documents that NVML/nvidia-smi under WSL does not support all queries. Treat that as engineering context, not proof of causality.

Build an independent monitoring design that removes synchronous WSL nvidia-smi calls from the token-generation critical path.

Preferred architecture:
Windows-native telemetry sidecar -> append-only timestamped telemetry stream -> independent AURORA safety watcher -> WSL CUDA workload.

Use only officially supported local telemetry interfaces already present, such as Windows-native nvidia-smi/NVML.
Do not install or change a driver.

The sidecar must:
- sample temperature, VRAM, power and available supported fields at a prospectively fixed cadence;
- bind exact GPU UUID;
- write monotonic timestamps and query duration;
- latch any missing/stale sample beyond a predeclared heartbeat bound;
- latch >=87C or <2GiB reserve;
- terminate only the owned extension workload on breach;
- preserve the telemetry before raising failure.

First qualify the monitor under bounded CUDA load with NO semantic model scoring.
Require enough sustained samples to demonstrate monitor availability under load.
Create MONITOR_V2_PROTOCOL.md, MONITOR_V2_QUALIFICATION.json and raw telemetry.
Only a PASS may unlock later CUDA extension phases.

## 3. CPU deterministic policy trace replay

This phase is immediately eligible and must not wait for GPU qualification.

Goal: recover final-world action/forecast diagnostics that were unavailable because trajectories were not saved, without changing the original E15 result.

Create a separate trace replay runner that imports or calls frozen policy/simulator code read-only.
Do not modify frozen controller/simulator source used by E15.

Step A: exact replay validation.
For a prospectively fixed small stratified subset of final worlds, replay both static_bid0.25 and locked MSCP with the exact frozen world/config/seed identities.
Require exact or contract-permitted numerical equality of terminal episode metrics to the original saved receipt before using any newly captured trace.

Step B: if replay validation passes, instrument externally and record:
- per-interval state;
- selected action;
- candidate scores;
- first/second decision margin;
- support/ESS;
- uncertainty;
- dual/pacing variables;
- budget/spend trajectory;
- action-value/gross/spend forecasts if observable to the original policy;
- action masks and reasons.

Step C: run the full 200 frozen worlds if resource/time admission permits.
If full 200 is impractical under the extension resource cap, use a prospectively frozen stratified subset and label it descriptive.

Never use newly recorded final traces to change the primary policy or threshold.

## 4. Policy trace and calibration outputs

From validated extension traces produce:
- action frequencies and transition matrix;
- NO_CHANGE persistence;
- bid-up/down/pace/pause use;
- action churn and reversal;
- budget exhaustion timing;
- support-gate activation;
- uncertainty and dual trajectories;
- decision-margin distribution;
- margin vs realized paired utility diagnostics;
- final nuisance/gross/spend calibration where the frozen policy actually produced those forecasts;
- calibration intercept/slope, deciles and heteroscedastic residual slices;
- support/uncertainty/action/budget/mechanism calibration slices;
- support/uncertainty/margin threshold sensitivity curves as retrospective diagnostics only.

Create:
reports/extension_v1/policy/TRACE_REPLAY_VALIDATION.json
POLICY_FINAL_TRACE_DIAGNOSTICS.json
POLICY_ACTION_TRANSITIONS.csv
POLICY_DECISION_MARGIN.csv
POLICY_FINAL_NUISANCE_CALIBRATION.csv
POLICY_MONITOR_REFERENCE_DISTRIBUTIONS.json

If exact replay cannot be established, preserve the failure and do not fabricate traces.

## 5. Expanded CPU serving study

The previous CPU serving study used only 10/100/200 RPS.
Run a new isolated extension benchmark on the same frozen numerical component with a denser prospectively frozen rate grid sufficient to locate a descriptive saturation region, for example a bounded grid spanning below and above the observed target crossing.

Before measurement freeze:
- offered rates;
- concurrency levels;
- window count/duration;
- payload;
- warm/cold/compiled conditions;
- latency/error definitions;
- resource sampling cadence.

Add request-aligned resource timestamps where possible so resource/latency correlation is measurable.
Report p50/p95/p99, queue, backend, HTTP residual, errors/timeouts, throughput, resource usage, and confidence limitations.

This is local CPU component evidence only.
Do not call the detected crossing a universal production saturation point.

Create CPU_SATURATION_EXTENSION.json, CPU_RATE_CURVE.csv, CPU_RESOURCE_LATENCY.csv.

## 6. OBD seven-day OPE stability extension

The official Open Bandit Dataset documents a 7-day experiment.
Audit the locally admitted OBD payload to determine how many distinct UTC/calendar days are actually present and whether all seven source days are available under the existing publisher/hash/license admission.

If seven days are available, define BEFORE computing new extension outcomes a SECONDARY_OPE_7DAY_STABILITY study using the already frozen action mapping and a fixed evaluation protocol.

Use the full seven-day release only for:
- day-by-day estimator stability;
- leave-one-day or rolling sensitivity where methodologically valid;
- ESS/support/weight concentration by day;
- estimator spread across days;
- behavior-policy/campaign stability if the exact local source supports it.

Do not relabel this as an untouched primary confirmation if development/final chronology overlaps.
It is a secondary multi-day stability study.

If additional official campaign/policy files are already locally admitted, they may be analyzed as separate populations, never pooled silently.
If acquisition or terms would require new manual acceptance, stop that subtrack as BLOCKED_EXTERNAL_ACTION.

## 7. Agent extension benchmark freeze

Do this before any new extension semantic model output is scored.

Audit the existing frozen nine dependence groups and executable task generator.
Create A1_EXTENSION_V1 with:
- prompt-only;
- SFT seed41;
- DPO seed41;
- IPO seed41;
- identical tools, host guards, tokenizer, context and generation budget;
- no hidden oracle information.

If enough task definitions already exist, freeze them.
If the original benchmark lacks adequate independent workflows, create SECONDARY_AGENT_BENCHMARK_V2 only from genuinely distinct root workflow/scenario generators BEFORE any model is scored.
Paraphrases, retries and seeds are not new semantic families.

Record exact family count and prospective power.
Do not promise 80 families unless the dependency audit supports them.

Freeze:
- task IDs and family IDs;
- scoring rubric;
- integrity endpoints;
- selection/tie rule;
- extension inference duty rule;
- exact checkpoint hashes;
- case count and resource budget.

## 8. Agent inference qualification under Monitor V2

Only after MONITOR_V2_QUALIFICATION PASS.

Do not replay historical 5/10/30 profiles as if they were the primary study.
This is a new extension protocol.

Use a conservative extension cadence prospectively frozen before outcome scoring.
Start with a cadence that provides at least the historical 30-second cooling envelope; add a larger cadence only if the extension protocol predeclares it before any semantic outputs.

Qualify prompt-only, SFT, DPO and IPO on TRAIN-only longest-prefix stress cases under Monitor V2.
Require:
- exact model/checkpoint/tokenizer/tool identities;
- full attended context;
- no semantic evaluation cases;
- no resource breach;
- no monitor heartbeat failure;
- all required forced decodes complete.

Choose one common extension duty profile from resource evidence only.
If any trained arm cannot qualify, preserve the failure and do not create a semantic ranking that omits it unless the extension protocol explicitly defines a reduced secondary comparison.

## 9. Agent semantic evaluation and finalist

If all four arms qualify:
run the frozen extension development semantic benchmark for prompt/SFT/DPO/IPO.

Primary extension endpoint:
family-macro executable task success.

Separate integrity endpoints:
harmful/invalid proposal rate;
host-blocked model-error rate;
wrong committed-action rate;
authorization/state/version/unit/evidence errors;
unnecessary refusal;
tool count/tokens/latency.

Host prevention is not model success.

Select at most one trained extension finalist by the frozen rule.
Keep prompt-only as fixed reference.

If required by the extension protocol and within the remaining historical 36h agent compute envelope, run additional seeds only for the selected finalist.
Do not multiply seeds into independent semantic families.

Then freeze EXT_AGENT_FINALIST before any extension held-out scoring.
Run held-out extension confirmation once.
Report UNDERPOWERED if family count remains inadequate.

## 10. R3 D4 neural delay extension

Only after Monitor V2 qualification.

The R3 final origins [70,82) were never scored in the primary closure.
Preserve M41+C54 and all existing source/clock assumptions.

Implement/qualify the originally specified D4 finite-horizon neural delay model:
q(x)=P(C_H=1|x)
f_k(x)=P(delay bin k | C_H=1,x)
with proper no-event likelihood and F(H)=1.

Use only M41 training, C54 calibration and [54,60) development selection according to the existing temporal contract.
No final [70,82) access during development.

Compare the complete eligible R3 development roster including mature-only CPU baseline, D2, eligible D3 only if convergence rules permit, and D4.
A failed historical D3 remains failed; do not extend its optimizer cap.

If D4/model ladder completes, freeze a NEW extension model/calibrator based only on development.
Then materialize/score [70,82) exactly once as AURORA_EXTENSION_V1 R3 confirmation.
This does not retroactively change historical E03/E15_R3 BLOCKED_HARDWARE.

## 11. Extension policy x agent integration

Only if an extension trained-agent finalist has been frozen.

Execute a supplemental 2x2:
1. static conventional x prompt-only;
2. static conventional x extension trained finalist;
3. locked MSCP x prompt-only;
4. locked MSCP x extension trained finalist.

Use identical host guards/tool contracts/action/budget mechanics.
Keep the already-known negative policy evidence visible.
The purpose is decomposition of numerical-policy and agent-execution effects.

Do not replace historical blocked E12/E15_INTEGRATION.
Write EXTENSION_INTEGRATION_2X2.json and family-level tables.

## 12. GPU and complete-agent serving extension

Only after Monitor V2 qualification and only when isolated from training/simulation.

Run:
- matched frozen numerical component CPU vs CUDA latency;
- CUDA startup/warm/steady latency;
- CUDA memory and profiler evidence where supported;
- complete prompt-only agent task latency;
- complete trained-finalist agent task latency if finalist exists;
- full host tool loop latency where executable;
- local concurrency/queue sensitivity;
- restart/retry/cancellation;
- bounded CUDA OOM/recovery fixture in a disposable child process.

The OOM fixture must be intentionally bounded and recoverable, must not threaten the display/system process, and must never weaken the 2GiB reserve for normal benchmarks.
If a safe OOM fixture cannot be isolated, mark it BLOCKED_WITH_REASON.

PyTorch profiler may be used for CUDA operator/memory timing if supported on this WSL configuration.
No production/Amazon-scale SLO claim.

## 13. Monitoring threshold completion

Use newly captured extension development/reference distributions to fill monitoring thresholds that were null in POST_CLOSURE_DIAGNOSTICS_V1 where evidence now exists.

Examples:
- policy support/uncertainty/margin/action mix;
- final/extension nuisance calibration;
- agent latency/resource/semantic-integrity reference distributions;
- GPU serving latency/VRAM/temperature;
- expanded CPU saturation monitors.

All new limits remain EXTENSION_PROVISIONAL_OFFLINE_NOT_PRODUCTION_SLO.
Do not overwrite reports/posthoc/MONITORING_THRESHOLDS.*.
Create separate extension threshold and runbook addenda.

## 14. Optional additional feasible gap audit

Before declaring extension terminal, audit these currently external/evidence-limited gaps:

R5/iPinYou:
- read-only availability/terms audit only;
- no click-through acceptance or substitute mirror;
- if new explicit user/legal acceptance is required, mark BLOCKED_EXTERNAL_ACTION.

R4:
- use the 7-day local OBD stability extension if feasible;
- do not claim more untouched independent final days than actually exist.

Agent:
- secondary independent workflow expansion is allowed only if genuinely distinct scenario generators can be prospectively frozen before scoring.

Human/operator evaluation, live ads, real spend, commercial lift and external production validation remain OUT_OF_SCOPE_EXTERNAL_EVIDENCE and should not be simulated as substitutes.

## 15. Reproducibility and independent extension ledger

Do not mutate config/experiments.json or the historical E00-E16 ledger to mark extension work complete.

Maintain:
reports/extension_v1/state/EXTENSION_STATUS.json
reports/extension_v1/state/EXTENSION_EVENTS/
reports/extension_v1/EXTENSION_EVIDENCE_LEDGER.csv

Every run records:
input hashes, source/config/model/checkpoint hashes, argv, start/end UTC, wall time,
CPU/RAM/disk/GPU telemetry, seed, output hashes, evidence class and limitations.

Snapshot and verify hashes for reports/final/* and reports/posthoc/* at extension start and end.
Any unexpected mutation stops the extension until reconciled.

Preserve every failed attempt.
No deletion to make the extension look cleaner.

## 16. Final extension deliverables

Create:
reports/extension_v1/EXTENSION_TECHNICAL_REPORT.md
reports/extension_v1/EXTENSION_EXECUTIVE_SUMMARY.md
reports/extension_v1/EXTENSION_RESULTS_MATRIX.csv
reports/extension_v1/EXTENSION_CLAIM_LEDGER.csv
reports/extension_v1/EXTENSION_REQUIREMENT_COVERAGE.csv
reports/extension_v1/EXTENSION_RESUME_SUPPLEMENT.md
reports/extension_v1/EXTENSION_INTERVIEW_SUPPLEMENT.md
reports/extension_v1/EXTENSION_LIMITATIONS.md
reports/extension_v1/EXTENSION_MONITORING_ADDENDUM.md
reports/extension_v1/state/EXTENSION_COMPLETION_AUDIT.json

Report old historical results and new extension results in separate columns/namespaces.
Never say the original primary study had completed work that occurred only in this extension.

## 17. Terminal conditions

AURORA_EXTENSION_V1 is terminal when every currently feasible extension track is:
EXECUTED, BLOCKED_WITH_REASON, BLOCKED_EXTERNAL_ACTION, or NOT_APPLICABLE.

Required completion checks:
- primary final/posthoc hashes unchanged;
- no E00-E16 or POSTHOC_V1 status change;
- CPU trace replay either verified/executed or explicitly failed;
- CPU serving extension terminal;
- OBD 7-day stability audit/study terminal;
- Monitor V2 terminal;
- if Monitor V2 passes, agent/R3/GPU-serving eligible branches executed to terminal state;
- if agent finalist exists, integration executed;
- monitoring addendum completed for all newly supported references;
- tests/lint/semantic validators pass;
- independent saved-file verification passes;
- no owned extension process remains active.

Do not keep searching for favorable results.
Do not weaken safety or scientific gates to improve coverage.

Start now with immutable snapshot + CPU-safe work. Defer heavy GPU work until the prospectively frozen Monitor V2 preflight and thermal headroom gates pass.
Continue autonomously until this extension program is terminal or a genuinely non-delegable external/legal/user action is required.
