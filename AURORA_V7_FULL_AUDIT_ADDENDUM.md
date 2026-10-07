# AURORA V7 Full End-to-End Audit Addendum

This addendum is authoritative before any V7 CUDA/scientific execution.
Do not weaken any frozen safety threshold or reinterpret V6 evidence.

The timestamp/catch-up defect has a real reproduction and a validated candidate fix, but the end-to-end audit found additional integration risks. Resolve and test ALL items below before opening CUDA.

## A. Second canary plumbing is incomplete
- qualify.py requires phase l2 for CANARY_2.
- phase_prepare.py must support l2.
- verify_gates.py must independently verify l2, not only k0/k1/k2/rd/mk/en/lc.
- model/input metadata must state two canaries.
- Add a test proving l2 cannot be skipped and its closed streams/hashes are verified.

## B. Launch admission must use the newest replayed Windows-memory source row
client.py currently assigns session.last['windows'] from the GPU payload snapshot while separately consuming windows_records.
The admission 7 GiB launch gate must use the newest strictly replayed/validated Windows-memory source observation, not a potentially queued older snapshot.

Required tests:
1. GPU frame carries an old >7 GiB snapshot but windows_records contains a newer <7 GiB row: launch admission must NOT pass.
2. Two consecutive low runtime memory rows in replay must trigger the frozen soft stop even if the attached snapshot is high.
3. Replay duplicates/retransmissions must not double-count the low-memory streak.
4. Snapshot and replay semantics must be explicitly distinguished in receipts.

## C. Bound transport jitter without coupling sampling correctness to a 0.2 s send timeout
The sampler process still performs sensor query and socket sendall in the same loop. A local receiver delay greater than the socket timeout can terminate the sampler well before the frozen 3 s heartbeat threshold.

Do not relax the 3 s heartbeat.
Prospectively choose and freeze a transport behavior that tolerates bounded local jitter while still failing closed before/at the frozen heartbeat. Options include a bounded local sender handoff or a justified bounded send timeout below the heartbeat.

Required production-path tests:
- receiver pause ~0.25 s, ~0.75 s, ~1.5 s: no false sampler death if source/delivery heartbeat remains valid.
- true >3 s GPU observation/delivery failure: registered dummy is terminated.
- no unbounded queue and no fabricated timestamps/samples.

## D. Scientific monitoring lifetime must be bounded
scientific.py currently opens one Session('dv') across all remaining development cases. Engineering endurance is ~10 minutes, while development may run many hours.

Before CUDA, either:
1. Preferably create a fresh independently bound guardian/watchdog/logger/sampler monitor epoch at every scientific case boundary (or another prospectively fixed short epoch) while no model child is active, OR
2. provide a prospectively frozen long-duration monitor qualification covering the intended maximum epoch and explicit state-reset tests.

No monitor restart may depend on semantic outcome.
No failed/censored case may be automatically retried.
A fresh epoch must preserve fixed scientific order and budget accounting.

Tests must prove:
- registration/reason/ACK/freshness/memory-low streak/replay state cannot leak across epochs/cases;
- exact child ownership and cleanup before epoch rotation;
- case transition with cooling and memory pressure remains deterministic.

## E. Remove safety/integrity dependence on production asserts
Tests may use assert. Production safety/integrity paths must use explicit named checks/errors so behavior does not disappear under -O or environment changes.

At minimum audit and convert:
- kill_helper.py payload/schema/size checks
- model_bind.py frozen hash checks
- owned_child.py checkpoint/GPU UUID/context/generated-token checks
- budget.py duplicate-charge guard
- common.py protected-history/canonical-generation checks
- watchdog.py close-registration check
- readiness/verification prerequisites if they can affect execution permission

Also explicitly forbid optimized model execution as already intended.

## F. Final architecture metadata must describe V7, not V5/V6
Before final architecture freeze:
- architecture_freeze.py must not say DEDICATED_NATIVE_V5 or "V6 owned_child.py".
- update stale V6 production docstrings/metadata where they can enter evidence.
- execute architecture freeze only AFTER final runtime code is complete.
- independently verify frozen hashes against the exact executed code.

## G. Make queue/backpressure failures explicit
- guardian outgoing queue full must latch an explicit LIVE_IPC_QUEUE_FULL (or equivalent), not be ambiguously reported as a sampler-source failure.
- kill queue insertion must be guarded/named.
- rejected source diagnostic persistence must precede the latch where possible and must be bounded.
- evidence queue failure remains a safety stop but must not be confused with model failure.

## H. Frame-size and replay worst-case tests
Test encode() on the largest legitimate safety frame:
- GPU row
- Windows snapshot
- maximum replay batch
- registration
- health metadata
Must remain <= frozen frame limit.
If not, reduce bounded batch size prospectively; do not truncate evidence silently.

## I. Independent gate verification must understand V7 diagnostics
verify_gates.py must:
- include CANARY_2/l2;
- explicitly reject unexpected rejecting_source_diagnostic rows in a supposedly PASS gate with a named result, not accidental KeyError;
- verify clock_id/source_time_ns sequence/gaps using V7 timing contract;
- verify memory replay acknowledgement reaches the last Windows source row;
- verify no evidence/logger/sampler/guardian/watchdog orphan.

## J. Progress/accounting consistency
- qualify.py progress currently hardcodes admitted_count=37; V7 carry is 38. Fix metadata.
- all status/progress counts must derive from carry manifest, not hardcoded prior counts.
- budget prior remains exactly 56115.874679132015 s unless a newly charged model-bearing artifact is added.
- heldout and R3 final remain unopened.

## K. Scientific result non-admission guarantees
For any failure after START:
- preserve raw partial outputs;
- no EXECUTABLE_RESULT means non-observation;
- if EXECUTABLE_RESULT exists but monitor/ownership/exit integrity fails, still do not admit;
- do not update selection summaries/checkpoints/counts until receipt is fully admitted;
- index38 V6 partial outputs remain quarantined and unused.

## Required order before V7 index38
1. Resolve A-K.
2. Run expanded CPU/fault/static tests and lint/design validation.
3. Freeze final code hashes.
4. Production native delayed-sampler tests.
5. True >3 s source/delivery stall dummy-target termination.
6. Three CPU broker trials.
7. 120 s readiness.
8. Actual loaded-model broker.
9. 600 s endurance.
10. CANARY_1.
11. CANARY_2.
12. Independently verify ALL closed streams including l2.
13. Only then execute V7 index38 once.

Do not report "all errors fixed" before these gates pass.