# AURORA-Ads v2 design review

**Review date:** September 30, 2026. This document records design choices, not model-performance results. The governing current research contract is [FINAL_SPEC.md](FINAL_SPEC.md); the earlier v1 material is historical.

The v2 review preserved one project, one application LLM agent, separation of numerical decisions from tool execution, public data versus synthetic interventions, strong conventional comparators, delayed conversion and a single-GPU execution envelope. The changes below remove ambiguities that could otherwise invalidate a comparison.

| Concern | Risk in an underspecified protocol | v2 decision |
|---|---|---|
| Predictor and calibrator | Refit M41 at day 70 after using C54 calibration | Keep a frozen M41+C54 pair for the primary test; no day-70 refit |
| Conversion and reporting clock | Treat delayed conversions as measured ingestion latency | State the `received_at` assumption; treat extra reporting lag as synthetic sensitivity |
| Seven-day incidence | Exponential tail not normalized to the finite horizon | Horizon-condition the exponential CDF and check `F(H)=1` |
| Policy learning episode | Seven-day episode receives almost no matured self-policy feedback | Use 14 decision days plus seven-day flush; update fully matured origin-interval cohorts |
| Reward double counting | Mix pending estimates and actual conversions in the learner | Primary learner updates from realized matured reward only |
| Self-reinforcing estimates | Train the posterior on its own nowcast | Restrict nowcast to state/value/pacing; pseudo-updates require separate study |
| Cost calculation | Scarcity penalty hides actual spending | Apply `gross-(1+lambda)*spend-operating_cost-beta*uncertainty` |
| Practical improvement | Change absolute/relative margin depending on baseline sign | Freeze a 0.01 normalized utility threshold |
| Pause action | Permanent pause without an explicit resume mechanism | Expire the action after one 15-minute interval |
| Propensity | Log proposals before guard filtering | Store the final executed-action probability distribution |
| Thompson sampling | Report Monte Carlo action frequency as exact propensity | Use an explicit epsilon-categorical off-policy logger |
| Causal action semantics | Extrapolate R2 binary uplift to S1 multi-action controls | Separate R2 binary assignment and randomized S1 action effects |
| Stateful policy inference | Generalize one-step DR to an adaptive budget trajectory | Compare fully matured, completed independent worlds |
| Organic purchases | Count purchase and impression credit twice | Use a unique synthetic event ledger and paired no-ad control |
| Open Bandit Dataset | Treat BTS average as arbitrary target-policy ground truth | Begin with uniform identity control; otherwise report diagnostics |
| Agent safety | Attribute successful host guard interception to safe model behavior | Distinguish proposals, prevented violations and committed violations |
| SFT masks | Train the model to reproduce tool responses | Train on assistant/tool arguments; mask system/tool observations |
| Context window | Silently truncate a 1,024-token execution contract | Audit tokenization, reduce tool subset or qualify a larger context |
| Agent data leakage | Split semantically equivalent paraphrases across train/test | Group by semantic family, task template and tool schema |
| DPO/IPO fairness | Different reference, pairs and token budgets | Match SFT reference and pairs; report objectives and token cost |
| Single physical GPU | Treat simultaneous trainers as useful parallelism | One heavy-GPU lease; vectorize numerical work instead |
| Windows/WSL files | Allow divergent editable clones | One canonical Windows source, isolated WSL runtime |
| Optional stages | Make iPinYou or GRPO block core confirmation | Remove optional stages from core freeze dependencies |
| Independent confirmation | Let agent failures block otherwise valid real-data studies | Separate POLICY, AGENT, R1 and R3 freezes |
| Completion status | Describe blocked empirical tracks as completed evidence | Distinguish track closure from empirical completeness |
| Reproducibility | Treat CPU helper tests as GPU training proof | Record parser, environment, network, GPU and experiment evidence separately |
| Downloads | Overlook EOF, Range, path or failed-byte quota handling | Bound paths and symlinks; validate Content-Range, EOF, quotas and locks |
| Approval | Substitute unbounded access for interactive user approval | Respect the supported host/CLI approval flow without weakening its sandbox |

The central change is not feature count. V2 fixes the comparison units, observation clocks, action semantics, cost accounting and evidence boundaries *before* looking at results.

Pure policy studies use a deterministic executor without an LLM. A separate numerical-policy × agent 2×2 experiment attributes integration effects. Every policy gets the same budget and mechanical guards. MSCP-specific uncertainty/support logic also faces a strong conventional policy with a matched basic support gate.

## Qualification still required

Actual source payloads, timestamp units, duplicate rates, horizon coverage, license rights, qualified Python/PyTorch/TRL/PEFT/XGBoost versions, GPU stability, task-schema context fit, the correctness of reward and completion oracles, and pilot power estimates must be measured. The planned 400 tasks across 80 families are not observations.

A failed admission leaves its evidence scope `BLOCKED`, `INVALID` or `UNDERPOWERED`; independent tracks can continue. Do not quietly substitute synthetic observations for a failed external validation and call it complete.
