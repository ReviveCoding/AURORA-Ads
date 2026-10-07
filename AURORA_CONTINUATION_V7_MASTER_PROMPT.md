# AURORA Continuation V7: evidence-backed source-clock and scheduling repair

Repository: C:\Users\bjw-0\Downloads\AURORA-Ads
New independent continuation: AURORA_EXTENSION_V5_CONTINUATION_V7.
The user explicitly authorized root-cause analysis, repair, qualification and continuation. Preserve the sandbox and scoped approvals. Do not bypass a tool/sandbox denial. Do not publish, incur cloud cost, change global settings, kill unrelated processes or operate another project.

## 1. First verify current state and ownership
Read AGENTS.md and the authoritative existing project contracts. Check that V6 is terminal, no other AURORA model owner is active, and this V7 instruction has not already been started. Do not enqueue or spawn a duplicate controller.

V6 authoritative closeout:
- reports/extension_v5_continuation_v6/state/CONTINUATION_COMPLETION_AUDIT.json
- reports/extension_v5_continuation_v6/state/ADMITTED_OBSERVATIONS_MANIFEST.json
- reports/extension_v5_continuation_v6/state/STOP_DIAGNOSIS.json
- reports/extension_v5_continuation_v6/CONTINUATION_TECHNICAL_REPORT.md
Exactly 38 admitted prompt_only observations, indices 0..37, exist. Admitted does not mean task success. V6 added index37 once. Keep all 38 unchanged and do not rerun/rescore them.
V6 index38 STARTED GENERATION and has two completed partial generation files, but no admitted executable result. Preserve the censored attempt. Do not open its generated text or use partial outputs for selection, retries, prompts, seed choices or model changes.
V3 index37 remains a separate historical non-observation with generation_started=UNDETERMINED.
Agent held-out and R3 final outcomes remain unopened.
Canonical generation91 and all historical artifacts through V6 are immutable.
Budget cap=129600s; V6 used=56115.874679132015s; remaining=73484.12532086798s. Verify the source ledger instead of merely trusting these literals.

## 2. Evidence already established in THIS request
Inspect and hash-verify:
- reports/extension_v5_continuation_v7/diagnostics/CLOCK_REPRODUCTION_PLAN_1791172985485947100.json
- reports/extension_v5_continuation_v7/diagnostics/CLOCK_REPRODUCTION_1791172985485947100.json
- reports/extension_v5_continuation_v7/diagnostics/TIMING_REPAIR_PLAN_1791173245378359700.json
- reports/extension_v5_continuation_v7/diagnostics/TIMING_REPAIR_VALIDATION_1791173245378359700.json
Preserve these records and their executed source snapshots; do not overwrite them or present them as full-runtime qualification.

Confirmed code defect:
V6 Control.source() raises the SAME SAMPLER_SOURCE_STALE when gap<=0 OR gap>3 (GPU). It discards the rejecting row before evidence.submit(). Therefore that error does not uniquely establish a >3s native source gap.
V6 dedicated.sampler() uses time.monotonic() plus deadline += cadence, with wait(max(0,deadline-now)). When late by multiple slots it performs catch-up reads without waiting.
The actual Windows Python is 3.11.9. get_clock_info reports monotonic=GetTickCount64(), resolution0.015625s, perf_counter=QueryPerformanceCounter(), resolution1e-7s.
Three predeclared native Windows trials ran the EXACT historical sampler function, with genuine read-only NVML calls and real local TCP, injecting only an extra1.1s test-owned wait. ALL THREE produced equal consecutive source timestamps. The largest positive gap was approximately1.61s, below3s. Feeding captured frames into the exact historical Control.source() produced the identical SAMPLER_SOURCE_STALE error in3/3 trials. No model/Torch/CUDA execution occurred.
The last saved V6 GPU row had source_time13476.625, scheduled_deadline13475.703, lateness0.922; the next old deadline13476.203 was already0.422s in the past. That is consistent with the reproduced catch-up mechanism. HOWEVER, the historical rejected frame was discarded, so do not claim unique proof of the original V6 cause.
This is a confirmed reproducible code defect and a strongly supported historical explanation, not a proven hardware/driver defect.

Candidate repair already implemented and tested:
- extensions/extension_v5_continuation_v7/sampling_timing.py
- extensions/extension_v5_continuation_v7/sampler_candidate.py
- extensions/extension_v5_continuation_v7/validate_sampler_candidate.py
The candidate passed18 named timing/schema checks,10000 predetermined deadline cases and3/3 native NVML delayed-sampling trials with24 genuine sensor samples, zero equal timestamps, and maximum gap approximately1.606s. The true3s+1ns failure boundary remains enforced. These are candidate tests, NOT whole-program/endurance/semantic qualification.

## 3. Scope and minimal integration
New runtime/reports only under extensions/extension_v5_continuation_v7/ and reports/extension_v5_continuation_v7/. Runtime directories use unique continuation_v7 names on the existing WSL-native runtime filesystem. Master instruction at repo root is allowed. No editable duplicate repository.
Reuse V6's successfully qualified architecture: separate Windows GPU sampler, Windows memory sampler, guardian control, logger process, WSL-local watchdog, local TCP/Unix IPC, READY registration and targeted ownership-based termination. Do not build another entirely new monitoring architecture.
Archive the tested candidate sources and their hashes before changing/integrating them. Copy/retarget only necessary V6 runtime files; do not overwrite historical source or evidence.
Preserve the READY handshake, two identity observations, retained READY decoder, guardian/watchdog registration ACKs, PID/start_ticks/UID/PGID/nonce identities and registration-bound START permission. No CUDA/Torch/model loading before START.

## 4. Required clock/scheduling repair
Integrate sampling_timing.SkipMissedCadence and sampler_candidate.run_sampler, or a byte-bound reviewed equivalent with the same tested semantics.
Use genuine time.perf_counter_ns() for native sampler timestamps and query/send durations. Record clock implementation, resolution, unit, platform and session. Do not use a global monkeypatch of time.monotonic. Change only matching clock pairs; never subtract Windows and Linux clocks or mix GetTickCount64 and QPC epochs.
Maintain0.5s GPU and1s Windows-memory target periods. After a late cycle advance to the next FUTURE scheduled slot instead of immediately replaying missed slots. Record missed_schedule_slots separately. Produced-sample sequence numbers remain contiguous. A missed scheduled slot is NOT a lost or fabricated source record.
Never clamp timestamps, add epsilon, relabel scheduled time as actual time, coalesce a real observation gap into a healthy one, reset a stale latch when delayed data arrives, or silently discard late samples.
Keep the actual >3s GPU source cutoff. A real >3s gap must still stop the owned workload. The repair prevents false classification caused by coarse equal timestamps; it does not excuse genuine monitoring unavailability.
The candidate does NOT resend on a socket after failed sendall, because part of a frame may already have been sent. Preserve explicit disconnect/failure behavior.

## 5. Do not lose the next failure's cause
Integrate validate_source_row/source_gap_ns into the native receiver before promoting a sample to healthy state.
Use distinct named failures for nonadvancing clock, regressed clock, actual gap exceeded, source-clock-domain mismatch, invalid source schema, API failure, source disconnect and IPC delivery timeout.
Before rejecting a bounded frame, preserve via the existing bounded asynchronous evidence path: prior accepted sequence/time, offending sequence/time, integer delta, threshold, source/query/send timing, scheduled deadline, missed slots, clock metadata, and source error details. Record rejected evidence in a separate diagnostic event/channel; it is NOT an accepted GPU sample.
Keep primary and secondary failures separate. Socket10053 during shutdown must not replace an earlier clock/validation fault. Likewise cooling/cleanup errors must not hide the initiating source error.
Track maximum accepted gap and rejecting gap as DIFFERENT fields. Never report accepted-only maximum as the maximum over an unobserved interval.
NVML calls should have high-resolution start/end/duration diagnostics, including which required call failed or was pending, with bounded state and no blocking disk work inside sampling.
Do not introduce source-loop disk writes or unbounded queues to improve diagnostics.

## 6. Audit dependent stream contracts before model execution
A latest Windows-memory SNAPSHOT carried on GPU frames is not necessarily a complete Windows-memory SOURCE stream. V6's Safety.memory() requires consecutive source sequences, while GPU frames can skip over intermediate memory snapshots during a legitimate GPU delay below3s.
Write a deterministic integration test: delay GPU delivery by1.1s while independent Windows memory continues at1s, and verify that valid intermediate memory samples are not falsely classified as lost and that two consecutive low-memory samples still trigger a stop.
Preserve strict sequence enforcement on the actual source. Prefer bounded replay of not-yet-acknowledged Windows source samples or an explicit independent source channel. Do NOT simply ignore sequence gaps or lose low-memory events. Retain latest snapshot fields for existing resource-admission readers, but name source-vs-snapshot semantics explicitly. Test missing/duplicate/tampered/out-of-order source records, buffer overflow and startup bootstrap.
Audit affected verifier/schema consumers so new diagnostic channels and integer timestamps are parsed correctly. Do not modify scientific model/evaluator schemas.

## 7. Freeze and validation matrix
Create V7 protocol, protected-history snapshot including V6,38-observation carry-forward manifest, source/architecture freeze, clock/IPC binding, compute ledger and live status. Preserve prior statuses as failed where they failed.
Reuse existing tests only with source identity/compatibility checks. Test the final integrated production paths, not just a separate helper.
Required CPU/sensor-only checks before model loading:
- Existing V6 safety/READY/identity/launcher/scientific contract checks.
- High-resolution clock schema and domain handling, duplicate/nonadvancing/regressed/true-late source cases; exact3s and3s+1ns boundaries.
- No catch-up burst and honest missed-slot accounting under delayed sampling/query/send.
- Original false-positive reproduction plus the same fixed delay on final repaired native code; retain all trials, no search for a convenient passing case.
- Guardian receives a genuine >3s source stall and targets only a dummy owned group; sentinel survives. No real model active in this injected fault.
- Logger slow/blocked/full/exited, IPC partial-frame/disconnect, and malformed/duplicate/regressed/missing sequence cases.
- Preserve the first rejecting sample and primary exception through cleanup.
- Memory-source/snapshot delayed-GPU tests from section6.
- READY/no-START checks on the final integrated dispatcher, including optimized test mode; actual model processes are NOT optimized.
- Scoped lint with no unexplained exclusions, design validation and cumulative budget checks.

Before scientific index38:
1. Fresh120s CUDA-free readiness.
2. One actual frozen TRAIN-only loaded-model broker qualification; guardian-initiated exact termination, unrelated sentinel survives; request-to-confirmed-exit <=2s. Parent cleanup cannot substitute for native broker proof.
3. One fixed600s resident-model endurance with the existing frozen TRAIN input/128 greedy-token engineering recipe and unchanged cooling gates. Do not choose an easier input or alter scientific decoding.
4. Two consecutive exact TRAIN-only launch/recovery canaries, with monitored cooling/resource recovery between them, to exercise case-to-case lifetime transitions. Fixed prospectively, not repeated until success.
5. Validate saved evidence and source compatibility before scientific access.
Do not rerun the historical24/24 stress ladder or all historical semantic observations.

## 8. Safety and resources unchanged
GPU launch<=75C; free VRAM>=2GiB. Runtime84C soft stop,86C owned-child hard stop,>=87C failure. Actual GPU source/guardian-to-WSL/active parent ACK gaps>3s stop. Windows memory and WSL watchdog stale>5s stop.
Windows launch available>=7GiB; WSL launch MemAvailable>=8GiB; require four fresh qualifying observations at least5s apart. Passive admission wait<=60minutes, not a single-point readiness-memory failure.
Windows runtime<2GiB for two consecutive source samples soft stop,<1GiB immediate. WSL runtime<4GiB for two consecutive source samples soft stop,<2GiB immediate.
One heavy CUDA owner. No optional CPU shadow jobs, hashing sweeps or report generation during active model execution. Preserve existing owned-process priority settings; do not escalate to REALTIME/TIME_CRITICAL or change affinity, BIOS, driver, clocks, power plan, WSL global memory/pagefile, or unrelated apps.

## 9. Bounded engineering repair and retry policy
Preserve versioned failed implementation receipts. A demonstrably pre-START implementation defect with no CUDA/generation/output access may be corrected inside V7 under a new implementation ID after affected tests and a new source freeze; do not close the entire project for an unused import or create unbounded continuation versions.
Use at most3 documented pre-START implementation repair revisions before reporting a real blocker. Never retry the same failed scientific outcome to select a better result.
This user request authorizes ONE new V7 evaluation of index38 AFTER the required repair qualification. Record its prior V6 engineering censoring and generation_started=true; never call it never-run. Freeze this replacement policy before V7 generation. Keep the exact original task/model/seed/decoding/evaluator. Partial V6 outputs remain quarantined and unused. Report the repeated exposure/censoring transparently as a limitation.
Any V7 post-START scientific monitor failure is preserved, safely stopped and not automatically rerun. No in-place model swap, hidden seed search, partial-result salvage or removal of unfavorable tasks.

## 10. Resume scientific work and dependent branches
After all prerequisites pass, resume EXACTLY:
prompt_only38..47 -> sft0..47 -> dpo0..47 -> ipo0..47.
38 observations are carried;154 new development observations remain for192 total.
Checkpoint each admitted completed case immediately, with atomic progress; compact checkpoint every4 new cases. Preserve receipts for engineering-censored cases separately.
Do not confuse execution completion with model task success.
At exactly192/192, aggregate under the existing selection/tie/eligibility rules, freeze at most one trained finalist, then evaluate held-out only if allowed:44 frozen tasks,9 dependence groups, UNDERPOWERED preserved.
R3 D4: M41 training,C54 calibration,[54,60) development,freeze before untouched[70,82) final once. No D3 rescue or historical status rewrite. Integration/serving only when prerequisites permit and no concurrent CUDA owner.
Do not let an unrelated optional preflight block an independent valid track, but all new model-bearing tracks must use qualified safety controls.

## 11. Accounting, visibility, closeout
Preserve original129600s accounting semantics and all prior charges. Charge new model-bearing engineering/scientific parent wall consistently. Do not reset because of a new namespace; do not double-count prior gates. CPU/sensor-only diagnosis/readiness is not newly charged if it was not historically charged.
CONTINUATION_STATUS and LIVE_CHECKPOINT must show the REAL active phase/arm/index/lifecycle and refresh time, not IMPLEMENTING/READY_INTEGRATION while scientific generation runs. Progress writing must not block safety loops. Distinguish candidate-validated, runtime-qualified, scientific-running and terminal.
Verify no owned orphan child/guardian/sampler/logger/watchdog at closeout; do not kill unrelated processes. Independently verify raw streams including rejected diagnostics, source archives, protected histories/generation91,38 carried observations, new results, compute ledger and outcome-access chronology. Produce an evidence-backed technical report and limitations.

Execute now: verify the saved diagnosis/candidate tests; integrate the focused clock/scheduling repair and dependent contracts; run the qualification matrix; proceed to index38 and the frozen continuation only after every prerequisite actually passes. Do not claim perfect reliability from finite tests or confuse a model-quality result with monitor integrity.
