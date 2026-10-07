# AURORA Continuation V6: verified pre-START repair and gated continuation

Repository: `C:\Users\bjw-0\Downloads\AURORA-Ads`
Program: `AURORA_EXTENSION_V5_CONTINUATION_V6`
New code: `extensions/extension_v5_continuation_v6/`
New reports: `reports/extension_v5_continuation_v6/`

The user authorizes the repair and continuation described here. Work in the existing interactive AURORA session. Do not start a duplicate controller. Do not change global settings, weaken approval/sandbox controls, or interrupt another project. Respect all applicable repository instructions and existing scientific contracts.

## 1. Objective and scope

Finish the targeted pre-START registration repair, qualify the real model launch/control path, then resume the frozen scientific sequence. Do NOT redesign the entire monitor stack again. Reuse V5's dedicated native samplers, guardian, bounded logger and WSL-local watchdog unless a demonstrated implementation defect requires a narrowly versioned change.

The existing V6 directory is a partially implemented, CPU-tested repair candidate, NOT an empty namespace and NOT a completed qualification. Inspect and continue it. Do not rerun the create-only preparation script or overwrite its diagnostics.

## 2. Verified starting evidence

Preserve all historical reports AND executed code through Continuation V5, canonical generation 91, and all unfavorable results.

Scientific state:
- Exactly 37 admitted prompt-only observations, indices 0..36.
- These are completed evaluations, NOT 37 task successes. Preserve the actual negative outcomes.
- V3 index37 remains an engineering-censored non-observation; its generation_started remains UNDETERMINED.
- Continuations V4 and V5 each added zero semantic observations.
- No Agent held-out or R3 final outcome may be opened before its original prerequisite freeze.
- Historical GPU-admission V5 24/24 stress PASS remains a historical prerequisite, not new V6 execution evidence.

Budget starting checkpoint, verify against V5 closeout rather than blindly hardcoding:
- cap_seconds: 129600
- used_seconds: 54505.598924737016
- remaining_seconds: 75094.40107526298
No reset, omission, or double charging. Follow prior accounting semantics. Explicit CPU-only, no-START diagnostics do not newly consume model-workload budget. Charge actual-model engineering attempts and Agent work consistently with the frozen ledger.

V5 did NOT validate its dedicated samplers under sustained model load. It stopped before START. Its idle/isolation PASS cannot establish that the prior actual-load sampling issue is resolved.

## 3. New direct diagnostic evidence: read before editing

All paths below are relative to the V6 report directory:

- `diagnostics/PLAN_1791166821474999801.json`
- `diagnostics/SUMMARY_1791166821474999801.json`
- `diagnostics/TRIAL_1791166821474999801_021.json`
- `diagnostics/READY_REGRESSION_1791167054166243144.json`
- `diagnostics/READY_REGRESSION_1791167119043982510.json`
- `diagnostics/STARTUP_REPAIR_SOURCE_SNAPSHOT/SOURCE_HASHES.json`

The unchanged V5 registration predicates were exercised in 40 CPU-only trials. Assertion messages were instrumented in memory; predicate semantics were not relaxed. One of 30 immediate post-Popen registrations failed at V5 registration.py line31. The observed process was live, state R, with matching PID/PGID/UID and executable, but cmdline was empty: argv=[""] and SHA256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855. Ten predefined 100ms-delay controls passed. Every child remained before START and Torch import.

This reproduces a real startup-availability failure in the old path. It does not prove the exact predicate of the historical V5 failure, whose traceback was missing. Preserve this distinction. Do not replace the root-cause statement with an unsupported Windows/WSL/kernel explanation.

The new candidate uses a child READY barrier, two matching post-READY identity snapshots and named explicit errors. The exact V6 owned_child.py, not a substitute dummy, passed 100/100 no-START registration/abort trials plus 13 rejection checks. A further 20/20 trials and the same 13 checks passed under Python -O. No trial sent START, imported Torch, initialized CUDA, or accessed semantic outcomes.

Candidate hashes at these tests:
- startup_registration.py: 768768dcf5c91a442c6893f77a927f1ba1bf5fb8655ef295ebfe4cfc4b97a0bb
- registration.py: 46925c2c9fef902858f03888e53acb4f328da5a2e673c19ebd7797c703135d73
- owned_child.py: c9c1284c817754fede1325c59a6db523b52ed2e465e487c037ed7ea2cd8a7c20
- wire.py: 31ca29651840dbd22a36f54df11e331e73feb66fc886b6e5f9fd35702e1ed0fb

These are CPU startup results only. They do not qualify actual-model termination, endurance or scientific execution.

## 4. Minimal runtime integration

Keep the tested `startup_registration.register_ready_child` behavior and integrate it into ALL relevant V6 model-bearing entry points: model-broker qualification, endurance, launch/recovery canary, and scientific model launcher. Do not leave one entry point using immediate `build(child.pid,...)` after Popen.

Required state sequence:
SPAWNED -> READY_FOR_REGISTRATION -> IDENTITY_VERIFIED -> GUARDIAN_ACKED + WATCHDOG_ACKED -> START_AUTHORIZED -> MODEL_LOADING -> LOADED -> GENERATING -> COMPLETED -> EXIT_CONFIRMED -> UNREGISTERED.

Before READY, the child may run only stdlib/bootstrap/control code. It must not import Torch/Transformers, load a model, initialize CUDA, or read development/held-out outcomes.

READY travels over the private inherited socket with the fresh run nonce. Validate child PID against the exact Popen child, PGID, UID, run directory, protocol, sequence and pre-CUDA flags. Child assertions are not a substitute for independent parent /proc checks.

Then obtain two matching /proc snapshots and verify the frozen script, nonce, directory, PID/PGID/UID/start_ticks, cmdline hash and executable identity. Do not change expected identity to match arbitrary observations. Empty cmdline or mismatched identity after READY is an explicit failure, not permission to use a weaker check.

Maintain `session.check()` during every wait. Use bounded monotonic deadlines, not an arbitrary sleep as the correctness mechanism. The tested helper has a 30s CPU startup deadline and bounded control writes. This startup deadline does NOT extend any GPU/ACK/memory heartbeat.

IMPORTANT: `register_ready_child` returns the worker Decoder after consuming READY sequence0. Retain that SAME decoder for subsequent LOADED and DECODE events. Reinitializing it after START would incorrectly reject LOADED sequence1. Keep parent permission sequence and worker event sequence separate.

The helper NEVER sends START. Send START only after both guardian and watchdog acknowledge the exact registration. Record the registration identity/digest in the start authorization. Production model execution must use normal Python optimization settings so legacy model assertions are not silently removed; do not change global Python configuration.

## 5. Diagnostics that identify the actual failing condition

Replace message-less runtime assertions on V6 identity, handshake, authorization and cleanup paths with explicit named checks. Test assertions may remain in tests.

On failure, capture bounded evidence including:
- error_code and exact check/predicate identifier;
- expected and observed values, sanitized and limited to owned processes;
- Python traceback with source file/line;
- PID, process state, start_ticks, cmdline length/hash, executable identity;
- lifecycle stage, READY observed, guardian/watchdog acknowledgement, START sent;
- Torch-import/CUDA-init/LOADED/decode/admitted-result flags separately;
- primary failure and all secondary cleanup/evidence failures without overwriting the primary cause.

Do not label sending START itself as proof that CUDA was initialized. Do not infer no generation solely from a missing result file. Preserve evidence of what was actually observed.

No full-file reads of growing telemetry. No report hashing, source scans or synchronous diagnostic export in the critical loop. Keep bounded in-memory failure context, secure the child first, then export it.

## 6. Termination and lifecycle correctness

Retain strict targeted ownership checks. Never use broad process cleanup, WSL shutdown, distro termination, VmmemWSL termination, unrelated Python termination, or removal of a mismatched target.

Fix the pre-registration cleanup hole: if registration fails, the parent must still clean up its exact directly spawned NO-START child using its owned process handle/control socket and confirm exit. It must not call targeted_kill(None), lose the original exception, or unregister a live process prematurely.

Use lifecycle-aware dispositions:
- KILLED_AND_CONFIRMED: this broker actually terminated the registered target.
- ALREADY_EXITED_CONFIRMED: independently confirmed same registered process already exited; this is NOT broker-kill qualification PASS.
- IDENTITY_MISMATCH: refuse any signal; severe control failure.
- EXIT_UNCONFIRMED: do not report successful cleanup.

An empty cmdline for an exited/zombie process is not itself evidence of a different live target. Conversely, a failed exe/cmdline read is not by itself proof the process/group is gone. Use anchored identity, Popen/pidfd where supported and explicit process-group membership/exit verification. Do not weaken identity checks or claim PID-race immunity that the implementation does not provide.

Qualify stale PID/start_ticks, changed identity, parent/broker simultaneous completion, already-exited targets, and sentinel isolation using CPU-only fixtures. The real loaded-model broker test must establish termination by the native broker, not a parent/watchdog fallback.

## 7. Preserve the V5 monitor and safety contract

Reuse the dedicated Windows GPU sampler, Windows memory sampler, guardian control and separate evidence logger. Reuse nonce-bound local IPC and the WSL-native watchdog. No /mnt/c polling in live safety. No optional shadow CPU jobs during model-bearing work.

Unchanged limits:
- GPU launch <=75C, free VRAM >=2GiB; four fresh valid observations >=5s apart with the previously frozen temperature-stability rule.
- Windows launch available physical >=7GiB; WSL launch MemAvailable >=8GiB.
- GPU soft stop 84C, grace <=1.5s; hard stop 86C; observed >=87C failure.
- GPU source/frame heartbeat >3s failure; active parent ACK >3s failure.
- Windows memory source/WSL watchdog >5s failure.
- Windows runtime <2GiB twice => soft; <1GiB once => hard.
- WSL runtime <4GiB twice => soft; <2GiB once => hard.
- one heavy CUDA owner; passive admission waits follow the frozen contract.
- No driver/BIOS/clock/power/pagefile/overcommit/global environment changes.

Retain V5's prospectively configured priorities for its owned monitors only. Do not add further scheduling changes to obtain a PASS.

## 8. Qualification sequence, without another architecture rewrite

1. Verify V5 terminal state, code/report hashes, all37 carried observations, canonical91 and the budget.
2. Preserve the existing V6 diagnostic/candidate snapshots. Create the V6 protocol, carry-forward manifest, protected-history snapshot, budget ledger and current state. Do not treat preparation as empirical qualification.
3. Integrate READY into the actual launchers and perform scoped review/lint. Preserve the tested candidate snapshots before changing root candidate sources. Hash-freeze the integrated runtime before model use.
4. Run existing applicable V5 fault tests against V6 plus READY/decoder/cleanup tests. Ensure they exercise production code, not only legacy_cpu_helper or a different dummy code path. Re-run exact-child no-START tests after behavioral changes.
5. Verify native sampler isolation and three dummy/sentinel native broker trials with the integrated registration path. Reuse historical evidence only where the exact code/runtime binding and protocol explicitly allow it; do not relabel old results as new.
6. Run fresh120s CUDA-free readiness.
7. Run the real loaded-model broker qualification using the exact frozen TRAIN-only input/model/checkpoint/tokenizer. After LOADED, intentionally withhold ONLY guardian ACKs, keep the WSL watchdog serviced, and require native broker request-to-confirmed exit <=2s with sentinel alive. Intentional injected ACK loss is the specified test stimulus, not an unexpected model failure. No fallback termination can count as PASS.
8. Only after broker PASS, execute the existing frozen600s resident-model endurance recipe, without choosing easier input/load after a failure. Charge the budget.
9. Run the exact launch/recovery128-token TRAIN-only canary. Charge the budget.
10. Only after all required gates PASS, admit prompt_only index37.

Keep complete failure receipts and exact source hashes for all attempts. A V5 idle sampler PASS does not replace V6 real-load qualification. A safe abort is not evidence of an agent task succeeding.

## 9. Bounded repair policy

Do not terminalize the entire project merely for an unused import, message-less CPU assertion, missing fixture filename, or demonstrated pre-START bootstrap bug that can be repaired without touching scientific outcomes.

For a proven CPU/pre-START implementation defect: save the failure, verify no START/model/CUDA/semantic activity, create a new implementation-attempt ID, perform a narrow fix and re-run affected tests within V6. Do not overwrite executed snapshots. Limit to two automatic repair revisions per identified defect before producing a precise actionable blocker.

Unexpected thermal, reserve, device, monitor, ownership or actual-load termination failures still stop the affected model attempt. Do not silently retry it, loosen thresholds, change the test input, or falsely classify it as pre-START. A model-bearing engineering repair requires an evidence-backed classification and a prospectively versioned requalification plan, not retries until PASS.

Never automatically retry an admitted semantic observation. Partial scientific outcomes remain preserved and are not used to tune the repair.

## 10. Frozen scientific continuation

Carry forward exactly37 prompt_only observations0..36 with original result hashes and values. Resume:
`prompt_only37..47 -> sft0..47 -> dpo0..47 -> ipo0..47`.
This is155 remaining development observations, not172.

No model/checkpoint/tokenizer/task/evaluator/seed/scientific decoding changes. No task dropping, easier prompts, outcome-driven retry, reinterpretation of failures or selective replacement. Preserve exact frozen order, resource recovery, per-case checkpoint and four-new-case compact checkpoints.

Only at exactly192/192 verified development observations: compute the frozen summaries, preserve negative results, apply the original selection rule and freeze at most one trained finalist. A missing eligible finalist must be reported honestly.

Only after finalist freeze: prompt-only vs finalist on44 frozen held-out tasks per arm, nine dependence groups, UNDERPOWERED retained. Do not turn44 rows into44 independent groups.

R3 D4 remains M41 training, C54 calibration, [54,60) development, then model/calibrator freeze before untouched[70,82) final once. No D3 rescue. Run only when its own scientific and shared engineering prerequisites are satisfied. Integration and serving remain conditional on actual prerequisites. Do not rewrite historical E-track status.

## 11. Accurate progress and closeout

Maintain small atomic state/LIVE_CHECKPOINT and per-case progress artifacts outside the critical path. Show phase, attempt, admitted count, current arm/index, budget used/remaining, last completed receipt and observed safety state. Distinguish queued, implementing, CPU-qualified, actual-load-qualified, scientific-running, waiting and terminal.

Do not claim active work from a Codex PID alone. Do not estimate total experiment completion from idle canary timings. Status "PASS" must name what passed.

At terminal closeout: verify no owned model, guardian, sampler, watchdog, logger or broker remains; run CPU regression, relevant fault/lifecycle tests, scoped lint, design checks, independent file/sequence/hash verification, all protected history and canonical91 checks, budget reconciliation and outcome-access chronology.

Deliver technical report, limitations, completion audit and output manifest. Every assertion about performance must point to actual scientific evidence. No production, learned-safety or business-lift claim from engineering fixtures.

## 12. Start here

Read the diagnostic evidence and current V6 source snapshots. Continue from the already-tested READY repair, not from a blank project. Integrate the helper into the actual broker/engineering launchers, fix lifecycle diagnostics, qualify the frozen path and proceed through the listed gates without routine user questions. Report a genuine blocker precisely if one remains; never state that this repair is infallible or sustained-load qualification is already complete.
