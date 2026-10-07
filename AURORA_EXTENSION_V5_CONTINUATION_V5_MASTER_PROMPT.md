# AURORA Extension V5 Continuation V5
# Dedicated native sampling processes + observed-process identity registration

Repository:
C:\Users\bjw-0\Downloads\AURORA-Ads

NEW independent continuation:
AURORA_EXTENSION_V5_CONTINUATION_V5

Create persistent artifacts only under:
extensions/extension_v5_continuation_v5/
reports/extension_v5_continuation_v5/

Runtime temporaries may use the existing AURORA runtime area only under unique continuation_v5 names.

All historical namespaces through continuation_v4 are immutable. Do not overwrite, relabel, delete, or reinterpret any previous terminal result.

======================================================================
0. AUTHORITATIVE STARTING STATE
======================================================================

Preserve exactly:

- canonical generation = 91
- V5 historical representative Qwen stress qualification = 24/24 PASS
- exactly 37 valid prompt-only development observations exist, indices 0..36
- V3 prompt-only index37 remains an engineering-censored NON-OBSERVATION
- V3 generation_started for failed index37 remains UNDETERMINED
- V4 produced ZERO new semantic development observations
- Agent held-out outcomes remain unopened
- R3 final [70,82) outcomes remain unopened

Frozen development target remains:
48 tasks x 4 arms = 192 observations

Remaining exact order:
prompt_only 37..47
sft 0..47
dpo 0..47
ipo 0..47

Do not rerun 0..36.

V4 closeout compute ledger:
- cap_seconds = 129600
- used_seconds = 54489.88155990301
- remaining_seconds = 75110.118440097

Do NOT reset compute budget.
Preserve exact previous accounting semantics.

======================================================================
1. WHAT V4 PROVED AND WHAT V5 MUST REPAIR
======================================================================

V4 successfully established:
- no /mnt/c file polling in the live GPU safety path
- Windows-native direct-NVML guardian
- bidirectional local TCP guardian <-> WSL parent
- independent WSL-local watchdog over local IPC
- decoupled evidence persistence
- 50 CPU/fault fixtures PASS
- targeted-kill dummy/sentinel qualification PASS after versioned registration transport repair
- 120-second CUDA-free readiness PASS

V4 then failed during the SINGLE frozen 600-second TRAIN-only model-load endurance attempt.

Frozen V4 failure:
NATIVE_GPU_SOURCE_STALE

Observed during endurance:
- GPU native source max gap = 3.125 s
- frozen GPU source heartbeat threshold = 3 s
- Windows-memory source max gap = ~2.781 s
- WSL watchdog max gap = ~1.123 s
- GPU temperature = 65..71 C
- minimum free VRAM = ~11322 MiB
- thermal failure = false
- semantic scoring = false
- no development index37 execution

Do not claim a proven scheduler/API root cause.
Precise cause remains unidentified.

V4 actual-load out-of-band broker also attempted a kill and the WSL verifier refused:
OWNED_TOKEN_MISMATCH

No successful actual-model out-of-band termination was proven.
The scientific parent cleanup succeeded and all owned processes were absent at closeout.

V5 repair goals:
A. make native GPU sampling independent of guardian/network/logger Python scheduling;
B. make owned-process registration derive from the ACTUAL spawned process identity rather than reconstructing intended argv;
C. qualify out-of-band kill using an actual loaded model before scientific continuation.

Do not loosen any safety threshold.


======================================================================
2. DEDICATED WINDOWS NATIVE SAMPLER PROCESSES
======================================================================

Do NOT perform direct NVML calls inside the same process that handles:
- WSL TCP traffic
- ACK parsing
- kill brokering
- evidence persistence
- report generation

Create at least these independent Windows-native processes:

1. GPU_SAMPLER
2. WINDOWS_MEMORY_SAMPLER
3. GUARDIAN_CONTROL
4. EVIDENCE_LOGGER

GPU_SAMPLER responsibilities ONLY:
- initialize direct NVML
- bind exact frozen GPU UUID
- sample every 0.5 s
- maintain strict source sequence
- measure source monotonic timestamp
- measure query duration
- publish bounded state to guardian control through Windows-local IPC
- never touch report files
- never hash files
- never launch subprocesses
- never perform WSL IPC directly
- never perform semantic work

WINDOWS_MEMORY_SAMPLER responsibilities ONLY:
- GlobalMemoryStatusEx
- 1 s cadence
- strict sequence/source monotonic
- bounded Windows-local IPC to guardian
- no disk/network/report/subprocess work

GUARDIAN_CONTROL responsibilities:
- receive GPU and Windows-memory state
- apply unchanged safety rules
- communicate live frames to WSL parent
- supervise ACK freshness
- request targeted kill
- never call NVML itself

EVIDENCE_LOGGER:
- separate PROCESS, not a guardian thread
- receive duplicate bounded telemetry asynchronously
- persist evidence
- no blocking dependency from sampler/control safety path

Use bounded queues/buffers everywhere.
No unbounded lists.

======================================================================
3. WINDOWS SCHEDULING ROBUSTNESS
======================================================================

Prospectively configure only these V5-owned monitoring processes.

Allowed if supported without elevation/global changes:
- ABOVE_NORMAL_PRIORITY_CLASS for GPU sampler and guardian control
- THREAD_PRIORITY_HIGHEST for the GPU sampling thread/main thread

Forbidden:
- REALTIME_PRIORITY_CLASS
- THREAD_PRIORITY_TIME_CRITICAL
- global Windows scheduling changes
- power-plan changes
- driver settings
- GPU clocks/power changes
- unrelated-process priority changes

If priority APIs fail, record it and fail the engineering qualification rather than silently pretending they were applied.

Use a deadline-driven GPU cadence:
next_deadline += 0.5 s

Do not merely sleep 0.5 seconds after work.

Record:
- scheduled deadline
- actual sample start
- deadline lateness
- query duration
- inter-source gap

Frozen GPU safety source heartbeat remains >3 s failure.

Do NOT widen it.

======================================================================
4. SAMPLER-TO-GUARDIAN WINDOWS-LOCAL IPC
======================================================================

Use Windows-local IPC that does NOT involve WSL for native sampler delivery.

Acceptable examples:
- loopback TCP bound to 127.0.0.1
- Windows named pipe
- fixed-size shared memory + explicit bounded synchronization

Freeze the chosen transport before readiness.

Requirements:
- local only
- fresh session nonce
- protocol version
- strict sequence
- bounded message/frame size
- reject duplicate/regressed/skipped frames
- reject wrong nonce/schema
- sampler process death fails closed
- GPU sampler state stale >3 s fails closed
- Windows sampler stale >5 s fails closed

The guardian -> WSL live channel from V4 may be reused conceptually, but all implementation hashes must be V5-owned/frozen.

No mounted-file polling anywhere in the live path.

======================================================================
5. EVIDENCE MUST NOT DELAY LIVE SAFETY
======================================================================

Sampling/control must remain live even if evidence persistence stalls.

Architecture:
sampler/control live path
    -> bounded nonblocking evidence handoff
    -> separate logger PROCESS

Inject in CPU/fault tests:
- logger sleeps 10 s
- logger blocks
- queue fills
- logger exits

Expected behavior:
- GPU sampler cadence remains within source-heartbeat requirement
- live safety still runs
- evidence failure latches
- if a workload is active, stop it safely
- do not classify as model failure

No fsync/hash/report writing in the sampler process.

======================================================================
6. ACTUAL PROCESS IDENTITY REGISTRATION
======================================================================

Replace V4's intended-argv reconstruction with a single shared registration implementation.

After spawning an owned WSL child:

1. read the ACTUAL live process from /proc/<pid>
2. independently validate that it is the exact expected V5-owned child
3. build the registration from this observed identity
4. use this exact registration for:
   - WSL parent
   - WSL watchdog
   - Windows guardian
   - targeted kill broker

Registration must include at least:
- pid
- pgid
- uid
- /proc start_ticks
- raw cmdline SHA256
- executable identity (resolved /proc/<pid>/exe and/or device+inode)
- expected V5 script identity
- run_nonce
- run_directory
- generation

The registration builder must validate before admitting:
- exact script belongs to extension_v5_continuation_v5
- exact run_nonce appears exactly once in actual cmdline
- exact run_directory appears exactly once
- PGID == owned child PID where required
- current user owns process
- no unrelated process can be registered

Kill helper must verify CURRENT process identity against the frozen OBSERVED snapshot:
- start_ticks
- pgid
- uid
- cmdline SHA256
- executable identity
- run nonce / run directory
- expected V5 script

Do not reconstruct what argv "should" be at kill time.

If identity differs:
refuse kill and record severe control failure.
Never kill another process.

======================================================================
7. ACTUAL-SHAPE KILL QUALIFICATION
======================================================================

The V4 dummy qualification was useful but did not prove the exact actual-model registration path.

V5 requires two stages.

A. CPU dummy/sentinel trials
- >=3 deterministic trials
- use the SAME registration builder used by the real model child
- target dies
- sentinel survives
- stale/wrong identity refused

B. ACTUAL LOADED-MODEL kill qualification
- frozen TRAIN-only model input only
- NO semantic scoring
- load exact frozen Qwen/checkpoint/tokenizer
- do not perform development/held-out inference
- register using actual observed process identity
- keep unrelated sentinel alive
- intentionally stop parent ACKs after model reports LOADED
- guardian must detect >3 s ACK lapse
- guardian must invoke out-of-band broker
- exact model child must terminate
- sentinel must survive
- broker request -> confirmed child exit <=2 s AFTER kill request
- no fallback broad cleanup can count as broker qualification

This model-bearing kill qualification is charged to the existing compute budget.

If actual-model broker qualification fails:
STOP.
Do not proceed to endurance.


======================================================================
8. PRE-CUDA / PRE-SCIENTIFIC QUALIFICATION
======================================================================

Before any model-bearing workload:

Freeze:
- V5 protocol
- protected-history snapshot
- carry-forward manifest for exactly37 observations
- V4 failed endurance/non-semantic evidence references
- compute budget ledger
- sampler/control architecture
- Windows-local sampler transport
- WSL live transport
- registration schema

CPU/fault tests must include at minimum:
- all V4 50 fixtures
- dedicated sampler duplicate/regressed/skipped seq
- sampler process exit
- guardian process delay
- guardian GIL/CPU stall simulation while sampler runs separately
- logger process stall/exit/queue-full
- Windows-local IPC disconnect
- wrong nonce/schema/oversized frame
- WSL parent disconnect
- WSL watchdog disconnect
- actual registration snapshot mismatch
- PID reuse/stale start_ticks
- cmdline hash mismatch
- exe identity mismatch
- wrong UID/PGID
- wrong sentinel target
- broker timeout

Run a dedicated CPU-only scheduler-isolation test:
- deliberately stall GUARDIAN_CONTROL for >5 seconds
- GPU sampler process must continue its own source sequence/cadence independently
- no fake source records
- guardian must observe backlog/recovery according to bounded protocol
- no silent data loss

If this cannot be demonstrated, STOP.

======================================================================
9. READINESS AND MODEL-LOAD QUALIFICATION ORDER
======================================================================

Only after CPU/fault PASS.

A. 120-second CUDA-free readiness
Require:
- dedicated GPU sampler healthy
- dedicated Windows sampler healthy
- guardian live
- WSL parent live
- WSL watchdog live
- exact sequences
- no required-call failure
- no source gap > frozen heartbeat
- no IPC heartbeat failure
- no evidence loss
- no observer restart

B. Actual loaded-model broker qualification
As section 7B.

C. Frozen 600-second resident-model endurance
Use exactly one prospectively frozen TRAIN-only engineering protocol.

Allowed:
- repeated frozen TRAIN-only greedy 128-token decodes
- no semantic scoring
- same exact model/checkpoint/tokenizer

Require full 600 seconds loaded-model duration.

Require throughout:
- GPU native source gap <=3 s
- guardian -> WSL frame gap <=3 s
- WSL parent ACK gap <=3 s while active
- Windows memory source <=5 s
- WSL watchdog <=5 s
- no queue loss
- no evidence failure
- no safety threshold breach
- no false targeted kill

One endurance attempt only unless a failure is DEMONSTRABLY implementation-only before any scientific outcome and a new versioned implementation is prospectively requalified.

Do not search for a passing load pattern.

D. Exact launch/recovery TRAIN-only canary
- 128 forced greedy tokens
- exact semantic-child registration/launch/unregister path
- no semantic scoring
- must PASS

Only after A+B+C+D PASS may development resume.

======================================================================
10. UNCHANGED SAFETY GATES
======================================================================

GPU launch:
temperature <=75 C
free VRAM >=2 GiB

Runtime:
84 C soft stop
86 C hard owned-child stop
>=87 C automatic failure

GPU source heartbeat:
>3 s failure

Guardian -> WSL live heartbeat:
>3 s failure

WSL parent ACK while child active:
>3 s => targeted kill

Windows-memory source:
>5 s failure

WSL watchdog:
>5 s failure

Windows launch available physical:
>=7 GiB

WSL launch MemAvailable:
>=8 GiB

Windows runtime:
<2 GiB for 2 consecutive samples => graceful stop
<1 GiB any sample => immediate stop

WSL runtime:
<4 GiB for 2 consecutive samples => graceful stop
<2 GiB any sample => immediate stop

One heavy CUDA owner only.

No global settings changes.

======================================================================
11. COMPUTE BUDGET
======================================================================

Start from V4 closeout:
used_seconds = 54489.88155990301
remaining_seconds = 75110.118440097
cap_seconds = 129600

Independently verify source hashes.

Charge model-bearing V5 engineering qualification consistently with prior frozen accounting:
- actual-loaded-model kill qualification
- endurance
- launch/recovery canary
- subsequent Agent workload

Do not charge CPU-only implementation/fault/readiness work if historical accounting did not.

Continuously expose:
used / remaining / cap.

If Agent budget is exhausted:
terminalize honestly.

======================================================================
12. SCIENTIFIC DEVELOPMENT RESUME
======================================================================

After all engineering gates PASS:

Carry forward exactly:
prompt_only 0..36 = 37 valid observations

Resume exactly:
prompt_only index37

Then:
prompt_only37..47
sft0..47
dpo0..47
ipo0..47

Do not rerun0..36.

Do not use any V3 failed index37 artifact as a semantic outcome.

For every scientific case:
- stable admission
- actual-process identity snapshot registration
- single owned model child
- dedicated native samplers
- guardian/WSL ACK
- WSL watchdog
- exact unchanged model/task/evaluator/decoding
- immutable case receipt
- confirmed child exit/unregister
- resource recovery
- checkpoint

Checkpoint every admitted case and compact checkpoint every4 new V5 observations.

No optional CPU shadow/preflight/report work while a model child is active.

======================================================================
13. DOWNSTREAM ORDER
======================================================================

Only after exactly192 development observations:
- compute frozen four-arm summaries
- apply exact pre-existing selection rule
- freeze at most one trained finalist
- only then open held-out

Held-out if finalist exists:
- prompt_only vs selected trained finalist
- exactly44 frozen tasks
- exactly9 dependence groups
- UNDERPOWERED remains explicit
- no outcome-driven reruns

R3 D4 after Agent terminal:
- M41
- C54
- [54,60) development
- freeze
- then untouched [70,82) once
- no D3 rescue

Integration/serving only when prerequisites exist.

No historical status rewriting.

======================================================================
14. PROGRESS VISIBILITY
======================================================================

Maintain:
state/CONTINUATION_STATUS.json
state/LIVE_CHECKPOINT.json
agent/DEVELOPMENT_PROGRESS.json when scientific work begins

Expose at least:
- terminal/running
- active phase
- admitted counts
- current index
- compute used/remaining
- GPU sampler process health
- GPU source max gap
- guardian frame max gap
- parent ACK max gap
- Windows memory
- WSL memory
- temperature
- free VRAM
- last receipt
- heldout outcomes loaded
- R3 final outcomes loaded

Progress reporting is not itself safety-critical.

======================================================================
15. CLOSEOUT
======================================================================

At terminal success or genuine blocker:
- stop every owned model child
- stop guardian/control
- stop GPU sampler
- stop Windows memory sampler
- stop WSL watchdog
- stop logger
- verify no orphan processes

Run:
- standard CPU regression
- V5 fault tests
- sampler-isolation tests
- actual-process identity tests
- kill isolation tests
- scoped Ruff
- design validation
- independent saved-file/hash verification
- protected-history verification
- canonical generation91 verification
- compute-ledger verification
- outcome-access chronology verification

Produce:
CONTINUATION_TECHNICAL_REPORT.md
CONTINUATION_LIMITATIONS.md
state/CONTINUATION_COMPLETION_AUDIT.json
state/OUTPUT_MANIFEST.json

Never infer model failure from monitoring failure.
Never infer scientific success from engineering integrity.

======================================================================
16. EXECUTION ORDER
======================================================================

Proceed now without routine questions:

1. verify V4 terminal evidence and hashes
2. carry forward37 observations
3. freeze V5 and compute ledger
4. implement dedicated GPU sampler process
5. implement dedicated Windows-memory sampler process
6. implement guardian control + logger process
7. implement observed-process registration builder
8. implement V5 targeted broker verifier
9. CPU/fault and scheduler-isolation qualification
10. three dummy/sentinel targeted-kill trials
11. 120 s CUDA-free readiness
12. actual loaded-model ACK-loss targeted-kill qualification
13. one frozen 600 s endurance
14. one exact launch/recovery 128-token canary
15. if all PASS, execute prompt_only index37 exactly once under V5
16. continue frozen development order
17. finalist freeze only at192/192
18. held-out/R3/integration/serving only under prerequisites
19. independent closeout

Stop only for a genuine frozen safety, scientific-integrity, budget, or prerequisite blocker.

Begin now.
