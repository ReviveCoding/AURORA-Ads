# AURORA implementation plan

Status: IMPLEMENTING. The separately submitted master prompt authorizes implementation.
The reviewed v2 contracts control all experiments. This plan is not evidence of execution.

| Milestone | Registry nodes and prerequisites | Acceptance/artifacts |
|---|---|---|
| Admission | E00; existing preparation checks | Current Windows/WSL inventory, original hash audit, runtime ownership, resource gates |
| Reproducible runtime | E00 qualification | Isolated Python 3.11 environment; finite pinned candidate matrix; CPU imports/numerics and bounded GPU update/reload; exact lock only after checks |
| Source capabilities | E01 <- E00 | Official metadata/revisions, authorized terms, bounded downloads, container/schema/clock/lineage reports and per-source capabilities |
| Prediction | E02 <- E01(R1), GPU qualification | Prior/FTRL/XGB/MLP/DCNv2 development; calibration and natural prevalence; frozen model identity |
| Delay/value | E03 <- E01(R3), GPU qualification | M41+C54; D0-D4 and value ladder; censored likelihood numerical references and temporal audit |
| Assignment | E04 <- E01(R2) | Response/T-learner/cross-fitted DR; source subsampling limitations and capacity policies |
| Logged OPE | E05 <- E01(R4) | Position/item identity, uniform control, DM/IPS/SNIPS/DR and support/ESS diagnostics |
| Optional replay | E06 <- E01(R5) | Manual terms gate; observed-auction set only; unavailable source cannot block core |
| Simulator | E07 <- E00 | Keyed exogenous streams; unique purchases; 14+7 clocks; evaluator isolation; independent reference and Monte Carlo controls |
| Incidents | E08 <- E07 | Rules, multi-signal/XGB/temporal comparison; interventions and missed-incident costs |
| Policy | E09 <- E07,E08 | Randomized warm-start; complete baseline roster; identical guards; observed matured-cohort learning |
| Tools/tasks | E10_TOOLS <- E07 | Nine typed interfaces, local transactional executor, one MCP server, executable family/split audit |
| Agent | E10 <- E10_TOOLS, GPU qualification | Pinned Qwen3 and tokenizer/context audit; prompt/SFT/same-SFT DPO/IPO; three finalist seeds |
| Optional GRPO | E11 <- E10 | Separate reward and remaining-resource gates |
| Integration | E12 <- E09,E10 | Policy x agent 2x2; common tools/guards |
| Development ablations | E13_POLICY <- E09; E13_AGENT <- E10 | Delay/support/uncertainty/dual and agent components; OOD mechanism blocks |
| Systems | E14 <- E10_TOOLS | Four latency domains, open-loop load, isolated GPU windows, startup/failure/recovery costs |
| Independent freezes | E15_POLICY_FREEZE <- E09,E13_POLICY; E15_AGENT_FREEZE <- E10,E13_AGENT; E15_R1_FREEZE <- E02; E15_R3_FREEZE <- E03 | Hash-bound selections; pilot-only N planning; no final outcomes inspected |
| Confirmation | E15_POLICY/E15_AGENT/E15_R1/E15_R3 <- corresponding freeze; E15_INTEGRATION <- E12,both policy/agent freezes | New independent worlds or held-out families; original contracts and unfavorable results retained |
| Reporting | E16: all declared tracks terminal | Required report families, immutable results/claims, technical/executive/resume/interview artifacts |

Execution state lives in `reports/state/experiment_state.json`, separate from the immutable design registry's PLANNED declarations. A completed engineering check is not a supported scientific hypothesis. Each source capability is admitted separately. Blockers record the failed gate, diagnostics, and concrete next action; dependent nodes stay pending while independent work continues. Runtime state/data/checkpoints remain in WSL ext4; small evidence exports are allowed in this repository.

Self-review: preserves M41+C54, half-open clocks, primary observed reward, exact executed propensities, complete-world inference, separate freezes, one application agent, one heavy CUDA owner, two initial CPU workers, no publication/global changes. No contract amendment is needed to keep execution state separate from the preparation registry.
