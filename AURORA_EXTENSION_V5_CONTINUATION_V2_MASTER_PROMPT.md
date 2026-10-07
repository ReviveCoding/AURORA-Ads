# AURORA Extension V5 Continuation V2
# Independent host-memory sidecars, bounded incremental readers, and scientific resume

Repository:
C:\Users\bjw-0\Downloads\AURORA-Ads

Immutable terminal histories:
- AURORA E00-E16
- POST_CLOSURE_DIAGNOSTICS_V1
- AURORA_EXTENSION_V1
- GPU_ADMISSION_V2/V3/V4/V5
- reports/extension_v5
- reports/extension_v5_continuation_v1

Do not overwrite, relabel, delete, or mutate any historical result.

Facts to preserve:
- V5 representative Qwen qualification passed 24/24 stress decodes.
- V5 whole-stream read_bytes ENOMEM is resolved by the incremental-reader architecture.
- Continuation V1 validated the bounded reader on a 134,218,410-byte stream with 95,214 records and ~69 KiB incremental RSS growth.
- V1 prompt-only development index19 completed successfully.
- V1 index20 stopped before generation with HOST_RESOURCE_OBSERVER_HEARTBEAT and is NOT an observation.
- Held-out Agent outcomes and R3 final outcomes remain unopened.
- V1 post-stop CPU-only IncrementalWatch V3 passed 23 fault fixtures.
- Do not reinterpret V1 as passed.

Current read-only resource snapshot before this request:
- Windows free RAM ~7.96 GiB
- WSL MemAvailable ~10.85 GiB
- WSL SwapFree ~3.97 GiB
- GPU ~72C
- GPU free VRAM ~14.5 GiB
- GPU utilization 0%
- no active AURORA semantic/R3 continuation process

This is a NEW program:
AURORA_EXTENSION_V5_CONTINUATION_V2

Create only:
extensions/extension_v5_continuation_v2/
reports/extension_v5_continuation_v2/


## 1. Scientific carry-forward and exact resume point

Before loading any new semantic outcome, prospectively hash-bind:
- V5 MODEL_STRESS_PROTOCOL and MODEL_STRESS_QUALIFICATION;
- Extension V1 frozen task definitions and selection rule;
- Extension V5 frozen protocol;
- Continuation V1 protocol, completion audit, stop diagnosis;
- prompt-only indices0..18 from V5;
- prompt-only index19 from Continuation V1;
- failed Continuation V1 index20 receipt proving no generation/executable result.

Carry forward exactly20 valid prompt-only development observations: indices0..19.
Do not rerun them.

Continuation V1 index20 is not an observation.
Resume exactly at prompt-only development index20.

Then preserve frozen order:
prompt-only20..47,
SFT0..47,
DPO0..47,
IPO0..47.

Complete development target remains exactly192 observations:
48 x 4 arms.

No task reordering, substitution, dropping, easier prompt, output-dependent retry, or model/checkpoint change.


## 2. Separate safety-critical monitors by risk class

Do NOT reuse Continuation V1 ResourceTrace thread as a safety-critical heartbeat source.

Use three independent persistent observer processes:

A. GPU critical observer
- Windows-native direct NVML
- 0.5s cadence
- UUID, temperature, free/used/total VRAM
- exact existing thermal/VRAM gates
- safety-critical
- heartbeat threshold remains >3s

B. Windows host-memory observer
- independent Windows-native Python process
- ctypes GlobalMemoryStatusEx, 1s cadence
- available/total physical
- available/total pagefile/commit-related values exposed by API
- append-only JSONL
- no psutil process-tree recursion
- safety-critical host-memory source
- heartbeat threshold >5s

C. WSL host-memory observer
- independent lightweight WSL Python process
- 1s cadence
- parse /proc/meminfo: MemAvailable, MemFree, SwapTotal, SwapFree, CommitLimit, Committed_AS
- cgroup memory.current/memory.max where available
- append-only JSONL under WSL-local runtime filesystem, not /mnt/c when practical
- no psutil process-tree recursion
- safety-critical host-memory source
- heartbeat threshold >5s

The semantic parent must only read these streams with bounded incremental readers.
No safety-critical observer may execute recursive process-tree scans, whole-file reads, shell subprocesses, or heavy artifact hashing inside its cadence loop.

Process-tree RSS/VMS diagnostics may run as a separate best-effort diagnostic observer every5s. Its failure must be recorded but must NOT itself stop a CUDA workload.


## 3. Bounded reader implementation

Use the stricter IncrementalWatch V3 logic from Continuation V1 as a reference, but copy/version it into V2 and hash-freeze it.

For every live stream reader:
- one open file descriptor;
- offset-based appended reads only;
- chunk <=256 KiB;
- partial buffer <=64 KiB;
- ring buffer <=128 recent rows;
- strict sequence validation;
- no Path.read_bytes/read_text/splitlines on a whole live stream;
- never retain the entire stream in RAM;
- file truncation/rotation/schema/sequence/I/O/MemoryError fail closed.

Keep GPU critical reader and host-memory readers independent so one stream cannot mask another.


## 4. Host-memory admission and runtime floors

This V2 is prospectively stricter at launch because V1 observed severe Windows memory compression during model load.

Before EVERY model-bearing semantic/R3/serving child, require simultaneously:
- GPU admission <=75C and >=2GiB free VRAM;
- Windows available physical >=7GiB;
- WSL MemAvailable >=8GiB;
- both host-memory sidecars fresh;
- NVML sidecar fresh;
- no other AURORA heavy CUDA owner.

Passive wait up to60 minutes for launch admission. Do not kill unrelated apps.

During a running model child:
- GPU limits unchanged: 84C soft, 86C owned-child hard stop, >=87C failure.
- If Windows available physical <2GiB for two consecutive host samples, graceful resource stop.
- If Windows available physical <1GiB on any sample, immediate owned-child stop.
- If WSL MemAvailable <4GiB for two consecutive samples, graceful resource stop.
- If WSL MemAvailable <2GiB on any sample, immediate owned-child stop.
- host-memory observer stale >5s => owned-child stop.
- GPU critical observer stale >3s => owned-child stop.
- do not change pagefile, WSL memory, overcommit, driver, BIOS, power, or global settings.

After every child exits, wait for launch admission thresholds to recover before the next semantic case.
This creates a natural memory-recovery boundary after every case.


## 5. Pre-CUDA qualification of the new architecture

Freeze V2 protocol before any CUDA.

CPU/fault fixtures must cover:
- all prior IncrementalWatch V3 failures;
- independent GPU/Windows/WSL stream sequence handling;
- stale GPU stream while host streams stay fresh;
- stale Windows stream while GPU/WSL stay fresh;
- stale WSL stream while GPU/Windows stay fresh;
- memory floor crossings;
- partial lines;
- malformed lines;
- stream truncation/rotation;
- injected OSError/MemoryError;
- observer process exit.

Run >=128MiB synthetic reader test again only for new V2 runtime code and require <=32MiB reader RSS growth.

Run a fresh 120s CUDA-free triple-observer soak:
- NVML 0.5s, Windows memory 1s, WSL memory 1s;
- no required-call failures;
- sequence exact;
- no heartbeat failure;
- no thermal/VRAM breach;
- host-memory observers remain responsive;
- current host-memory launch envelope must be satisfied at soak end.

Then run ONE engineering canary using an already frozen V5 TRAIN-only case:
- prompt-only base
- 128 forced greedy tokens
- no semantic-development or held-out outcome
- full context unchanged
- use all three new V2 observers
- require complete decode, no safety stop, and memory observers responsive.
This canary validates the new host-monitor architecture under actual model load without rescoring semantic development.

Do not rerun the full 24 stress ladder.


## 6. Semantic continuation execution

Only after triple-observer soak and TRAIN-only canary PASS.

Start development exactly at prompt-only index20.

For every case:
1. recover launch admission thresholds;
2. freeze pre-case receipt including current GPU/Windows/WSL resource samples;
3. launch exactly one owned model child;
4. monitor via independent persistent sidecars;
5. write only bounded telemetry references/start_seq/end_seq/recent context to receipt;
6. child exits;
7. save immutable semantic result and receipt;
8. update development progress;
9. recover memory thresholds before next case.

Never put full telemetry history into a case receipt.

Checkpoint progress after every successful case.
Additionally save a compact checkpoint after every4 successful new cases so a future engineering blocker does not require rescoring prior outcomes.

No automatic retry of any case that generated an admitted semantic result.


## 7. Complete development and freeze selection

When exactly192 development observations exist and all hashes verify:
- aggregate the20 carried prompt-only observations plus new observations;
- compute the frozen four-arm summaries;
- use the exact frozen family-macro executable-success primary endpoint;
- keep integrity endpoints separate;
- apply the exact pre-existing frozen selection rule;
- select at most one trained finalist;
- write an immutable DEVELOPMENT_SELECTION freeze before held-out access.

If no trained arm is eligible, record that honestly and mark finalist-dependent tracks NOT_APPLICABLE.

Do not open held-out outcomes before this freeze.


## 8. Held-out Agent confirmation

If a trained finalist exists:
- prompt-only vs selected trained finalist only;
- exactly44 frozen held-out tasks;
- exactly9 dependence groups;
- same tasks/order/contracts;
- no reruns based on outcome;
- preserve prospective UNDERPOWERED designation.

Use the same V2 triple-observer architecture and launch/runtime memory thresholds.
If monitoring/resource conditions are temporarily below launch gate, wait passively rather than changing the experiment.


## 9. R3 D4

After Agent development is terminal and no CUDA owner overlaps:
- continue supplemental R3 D4 with M41 training, C54 calibration, [54,60) development;
- no final [70,82) access before D4 model/calibrator freeze;
- no D3 rescue;
- use the V2 triple-observer architecture and same host-memory gates;
- train/select/freeze on development only;
- then score untouched [70,82) once.

Do not claim old E03/E15_R3 status changed.


## 10. Integration and serving

Only if prerequisites exist:
- supplemental policy x agent 2x2 if trained finalist exists;
- GPU/full-agent serving for prompt-only and finalist if available;
- restart/retry/cancellation;
- bounded recovery only if safe.

Use V2 monitors and memory gates for every GPU workload.
No historical E10/E12/E14/E15 status rewrite.


## 11. Implementation-error policy

If a failure occurs BEFORE generation and is demonstrably an implementation-only bug:
- preserve failed receipt/code hashes;
- prove no semantic result was admitted;
- repair under a new versioned implementation ID;
- rerun CPU/fault qualification for changed monitoring code;
- do not weaken scientific or GPU safety gates.

A failure in the optional process-tree diagnostic observer is NOT a safety failure.
A failure/staleness in one of the three required persistent safety observers IS a safety failure.

Never classify a host-monitor failure as model success/failure.


## 12. Closeout

Create:
reports/extension_v5_continuation_v2/CONTINUATION_PROTOCOL.json
reports/extension_v5_continuation_v2/PROTECTED_HISTORY_SNAPSHOT.json
reports/extension_v5_continuation_v2/CARRY_FORWARD_MANIFEST.json
reports/extension_v5_continuation_v2/state/CONTINUATION_STATUS.json
reports/extension_v5_continuation_v2/CONTINUATION_LOG.md

Final validation:
- full CPU regression;
- V2 monitor/fault fixtures;
- scoped lint;
- design validation;
- independent saved-file verification;
- protected histories unchanged;
- generation91 unchanged;
- outcome-access chronology verified;
- no owned sidecars/CUDA children left.

Do not rewrite V1/V5 reports.

Start now without routine user questions:
1. snapshot/freeze V2;
2. implement three independent sidecars and bounded readers;
3. run CPU/fault/128MiB qualification;
4. run 120s triple-observer soak;
5. run one TRAIN-only 128-token canary;
6. carry forward exactly20 prompt-only observations;
7. resume at prompt-only index20;
8. complete development, freeze selection, held-out, R3, integration, serving where prerequisites permit;
9. stop only for a genuine frozen safety/scientific blocker, not an optional diagnostic observer failure.
