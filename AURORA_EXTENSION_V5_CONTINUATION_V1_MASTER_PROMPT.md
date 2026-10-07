# AURORA Extension V5 Continuation V1
# Bounded-memory telemetry reader repair and scientific continuation

Repository:
C:\Users\bjw-0\Downloads\AURORA-Ads

Immutable terminal histories:
- AURORA E00-E16
- POST_CLOSURE_DIAGNOSTICS_V1
- AURORA_EXTENSION_V1
- GPU_ADMISSION_V2/V3/V4
- GPU_ADMISSION_V5
- reports/extension_v5 as produced by V5

Do not edit, overwrite, relabel, or delete any of those files.

V5 facts that must be preserved:
- 120s direct-NVML readiness PASS.
- Synthetic A/B PASS.
- All 24 Qwen3-1.7B stress decodes PASS across prompt-only/SFT/DPO/IPO, two frozen TRAIN cases, 128/256/512 tokens.
- V5 stopped during supplemental semantic development after 19 valid prompt-only development cases.
- Development case index 19 failed BEFORE generation with errno12 Cannot allocate memory in the local admission observer while qualify.Watch.check() called stream.read_bytes().
- Held-out Agent outcomes and R3 final outcomes remain unopened.
- V5 status BLOCKED_WITH_REASON remains unchanged.

Current independent read-only state before this request:
- frozen development task count: 48
- held-out task count: 44
- independent held-out groups: 9
- valid carried-forward prompt-only development indices: 0..18
- failed index19 generated no semantic output and must NOT count as an observation
- GPU approximately68C, low utilization
- Windows free RAM approximately12.7GiB
- WSL MemAvailable approximately15GiB

This is a NEW supplemental program:
AURORA_EXTENSION_V5_CONTINUATION_V1

Create:
extensions/extension_v5_continuation_v1/
reports/extension_v5_continuation_v1/

Do not reopen or rewrite reports/extension_v5.


## 1. Root-cause repair scope

The observed V5 failure path repeatedly did:

raw = stream.read_bytes()
complete = raw[:raw.rfind(b'\n') + 1].splitlines()

on every safety check.

By V5 closeout the telemetry file had 13,325 records and was approximately multi-megabyte. This design allocates the entire stream plus split-line objects repeatedly, including inside a model-bearing child-side admission/cooling observer.

The continuation repair MUST be outcome-independent and limited to monitoring/resource plumbing. Do not modify:
- model/checkpoint identities,
- tokenizer/render/tool contracts,
- semantic tasks,
- semantic evaluator,
- task order,
- selection rule,
- generation settings,
- safety thresholds,
- final/held-out definitions.

Do not modify old qualify.py. Implement a new bounded reader in the continuation namespace.


## 2. Incremental critical telemetry reader

Implement IncrementalWatch using a NEW telemetry stream for this continuation.

The safety-critical reader must:
- open the stream once in binary mode;
- maintain current byte offset;
- maintain expected next seq;
- read only bytes appended since the prior check;
- keep only a bounded partial-line buffer;
- never call Path.read_bytes(), read_text(), splitlines() on the whole live stream;
- never retain an unbounded in-memory list of all historical samples.

Recommended design:
- chunk size <=256 KiB;
- partial-line buffer hard cap <=64 KiB;
- deque/ring buffer of recent parsed samples maxlen <=128;
- monotonically increasing total_sample_count;
- last sample and heartbeat state;
- exact strict sequence validation;
- parse every newly committed record so transient thermal breaches cannot be skipped.

If file shrinks, inode/file identity unexpectedly changes, seq regresses/jumps, line exceeds cap, JSON is malformed, required fields fail, or heartbeat stalls, fail closed.

For scientific receipts:
- save start_seq/end_seq and raw stream reference;
- save only four admission samples plus bounded recent stop context in JSON receipts;
- if a per-case telemetry extract is desired, stream-copy the seq interval to a separate JSONL file after the case without materializing the whole source in RAM.

Never embed the entire growing telemetry history in every case receipt.

The critical sidecar remains persistent direct Windows NVML at 0.5s cadence.
Safety limits remain exactly:
- <=75C fresh admission envelope,
- >=2GiB free VRAM,
- 84C soft stop,
- 86C owned-child hard stop,
- >=87C failure,
- >3s no sequence advancement failure.


## 3. Reader memory/fault qualification before CUDA

Before any CUDA continuation workload, freeze the continuation protocol and run CPU-only reader qualification.

Required fixtures:
1. partial final JSON line must not be parsed until newline commit;
2. malformed JSON fails closed;
3. non-dict record fails closed;
4. duplicate/regressed/skipped seq fails closed;
5. thermal breach followed by cool record is still detected;
6. VRAM reserve breach detected;
7. UUID mismatch detected;
8. stale heartbeat detected;
9. file truncation/rotation detected;
10. oversized line/partial buffer fails closed;
11. injected OSError/MemoryError fails closed without CUDA;
12. bounded-memory large-stream test.

Large-stream test:
- generate a synthetic telemetry stream materially larger than the V5 5.8MB live file, preferably >=128MB if disk/time permits;
- consume it incrementally;
- measure process RSS before/peak/after;
- require bounded reader incremental RSS growth <=32MiB attributable to the reader;
- do not retain all parsed rows;
- verify every seq exactly once.

Also run a NEW live 120-second direct-NVML readiness soak with the new reader:
- >=235 successful samples,
- no required NVML call failure,
- no seq anomaly,
- max no-advance <3s,
- exact UUID,
- >=2GiB free VRAM,
- no >=84C,
- reader process remains within its bounded-memory target.

Do not rerun the 24-model stress ladder merely to recreate already-qualified V5 evidence. V5 qualification is an immutable prerequisite reference, not a result to overwrite.


## 4. Contemporaneous host-memory tracing

The V5 post-exit memory snapshot was insufficient for causality. Add independent, bounded resource tracing without changing system policies.

During every new case and every fresh admission record at least once per second:

WSL/system:
- MemAvailable
- MemFree
- SwapFree/SwapTotal
- CommitLimit
- Committed_AS
- vm.overcommit_memory
- cgroup memory.current and memory.max where available

Parent/child:
- PID
- RSS
- VMS
- peak RSS if available
- thread count
- child process tree aggregate RSS/VMS where practical

Windows:
Use a persistent read-only Windows-side resource observer, preferably Python ctypes GlobalMemoryStatusEx and optionally GetPerformanceInfo, no package install.
Record:
- available physical memory
- total physical memory
- available pagefile/commit information where the API exposes it
- timestamp/sequence

Do not change pagefile, WSL memory, overcommit settings, process limits, or power settings.

Before launching each semantic/model CUDA child require:
- current GPU admission passes;
- WSL MemAvailable >=4GiB;
- Windows available physical >=4GiB.
If either host-memory envelope is temporarily below 4GiB, wait passively up to30 minutes while monitoring; do not kill unrelated apps. If never available, stop with BLOCKED_CURRENT_HOST_MEMORY_BASELINE.

This host-memory envelope is a new continuation engineering safety criterion, not a reinterpretation of V5.


## 5. Preserve and resume the frozen semantic development study

Prospectively bind by hash before reading any additional semantic output:
- V5 MODEL_STRESS_PROTOCOL.json
- V5 MODEL_STRESS_QUALIFICATION.json
- reports/extension_v5/EXTENSION_PROTOCOL.json
- Extension V1 A1_EXTENSION_V1_FREEZE.json
- all 19 valid prompt-only development result/receipt artifacts for indices0..18
- failed prompt_only index19 receipt proving no generation output
- semantic_case_v2 and all model/checkpoint/tokenizer hashes

Create a continuation carry-forward manifest.

Scientific rule:
- indices0..18 prompt-only are FIXED carried-forward observations;
- do NOT rerun them;
- index19 from V5 is NOT an observation because generation never began;
- resume prompt-only at index19 under the repaired monitor;
- then execute prompt-only through index47;
- then execute SFT0..47, DPO0..47, IPO0..47 exactly once in frozen order.

No task reordering, dropping, replacement, easier prompts, or outcome-dependent retry.

Aggregate complete development as exactly:
48 prompt-only + 48 SFT + 48 DPO + 48 IPO = 192 fixed development cases,
where the first19 prompt-only come only from immutable V5 artifacts and the remaining173 come only from the continuation.

Selection must use the exact frozen V5 selection rule.
No held-out outcomes may be loaded before complete development and finalist freeze.


## 6. Failure semantics and implementation repairs

A true thermal/device/VRAM/critical-monitor failure during a new CUDA case stops that scientific attempt. Do not retry that case in the same attempt.

If a new failure is demonstrably an implementation-only bug independent of semantic/model outcome:
- preserve the failed receipt/code hash;
- prove generation/semantic output was not produced or was not admitted;
- repair under a new versioned implementation ID;
- keep safety/scientific gates unchanged.

Never classify a host-monitor failure as model safety success or model failure.

No automatic retry of a case that generated a semantic result.


## 7. After complete development

If all192 development cases are available and verified:
- compute four-arm summaries using the existing frozen family-macro executable-success endpoint;
- integrity endpoints remain separate;
- apply the exact frozen selection rule;
- select at most one trained finalist;
- save/freeze DEVELOPMENT_SELECTION before any held-out outcome access.

If no trained arm is eligible, record that faithfully and make finalist-dependent tracks NOT_APPLICABLE as appropriate.

If a trained finalist is selected:
- run only prospectively required additional seeds if the old frozen rule actually requires them and resource budget admits them;
- freeze final selected checkpoint before held-out scoring.

Then run the frozen held-out comparison once:
- prompt-only versus selected trained finalist,
- 44 held-out tasks,
- nine independent dependence groups,
- preserve UNDERPOWERED designation,
- no task replacement or repeat based on outcomes.


## 8. R3 D4 continuation

After Agent development is terminal and no CUDA owner overlaps, continue the already prepared supplemental R3 D4 track.

Preserve:
- M41 training
- C54 calibration
- [54,60) development
- no access to [70,82) final origins before model/calibrator freeze
- no D3 rescue
- same safe direct-NVML monitor and host-memory envelope

Use the continuation IncrementalWatch, never old whole-stream Watch.

Run development recipes prospectively as already frozen/prepared.
Select/freeze supplemental D4 model/calibrator without final outcomes.
Only then score untouched [70,82) once.

Report negative/null results honestly.


## 9. Integration and serving

Only if prerequisites exist:
- supplemental policy x agent 2x2 if a trained finalist exists;
- GPU/full-agent serving with prompt-only and finalist if available;
- retry/restart/cancellation;
- bounded recovery/OOM only if separately safe.

All new GPU work uses:
- new continuation sidecar/stream,
- IncrementalWatch,
- fresh <=75C admission,
- >=4GiB host-memory envelopes on both Windows and WSL,
- unchanged thermal/VRAM safety limits.

Do not alter historical E10/E12/E14/E15 statuses.


## 10. Evidence, validation, closeout

Create:
reports/extension_v5_continuation_v1/CONTINUATION_PROTOCOL.json
reports/extension_v5_continuation_v1/PROTECTED_HISTORY_SNAPSHOT.json
reports/extension_v5_continuation_v1/CARRY_FORWARD_MANIFEST.json
reports/extension_v5_continuation_v1/state/CONTINUATION_STATUS.json
reports/extension_v5_continuation_v1/CONTINUATION_LOG.md

Maintain immutable events and code/input/output hashes.

Validation before semantic CUDA:
- old protected hashes unchanged;
- V5 24/24 stress PASS artifact hashes verified;
- 19 carry-forward results independently rehashed;
- failed case19 has no admitted generation output;
- bounded-reader fixtures pass;
- >=128MB synthetic reader memory test passes;
- 120s live readiness passes;
- no old Watch/read_bytes whole-live-stream dependency in continuation runtime code;
- scoped lint/design validation.

Final validation:
- full CPU regression;
- continuation fixtures;
- independent saved-file verification;
- all protected histories unchanged;
- canonical generation91 unchanged;
- no owned sidecar/CUDA process;
- semantic/held-out/final outcome access ledger consistent with freeze chronology.

Do not rewrite reports/extension_v5 or GPU_ADMISSION_V5.

Start now without routine user questions:
1. freeze continuation protocol and hashes;
2. implement IncrementalWatch and host-memory observers;
3. run CPU/fault/large-stream reader qualification;
4. start fresh direct-NVML sidecar and run 120s readiness;
5. bind 19 carried-forward prompt observations;
6. resume at prompt-only development index19;
7. complete all four development arms if safely possible;
8. freeze selection, then held-out once;
9. continue R3 D4, integration and serving where prerequisites permit;
10. close only when every runnable continuation track is terminal.
