# AURORA Extension V5 Continuation V3
# Stable-admission continuation using the qualified V2 three-observer architecture

Repository:
C:\Users\bjw-0\Downloads\AURORA-Ads

Immutable terminal histories:
- AURORA E00-E16
- POST_CLOSURE_DIAGNOSTICS_V1
- AURORA_EXTENSION_V1
- GPU_ADMISSION_V2/V3/V4/V5
- reports/extension_v5
- reports/extension_v5_continuation_v1
- reports/extension_v5_continuation_v2

Do not overwrite, relabel, delete, or mutate any historical result.

Preserve these facts:
- V5 representative Qwen qualification passed 24/24 stress decodes.
- Whole-stream read_bytes ENOMEM is resolved.
- Continuation V1 bounded reader passed 128MiB/95,214-record qualification and prompt-only index19 completed.
- V1 index20 stopped before generation and is not an observation.
- Continuation V2 three independent observers and 38 CPU/fault fixtures passed.
- V2 stopped before CUDA only because soak-end Windows available physical was 6.887402GiB against a prospectively frozen >=7GiB launch gate.
- V2 CUDA launched=false and created zero new semantic observations.
- Exactly20 prompt-only development observations are valid and immutable: V5 indices0..18 plus V1 index19.
- Held-out Agent and R3 final outcomes remain unopened.

Current read-only resource snapshot before this request:
- Windows free RAM ~11.63GiB
- WSL MemAvailable ~11.1GiB
- WSL SwapFree ~3.86GiB
- GPU ~69C
- GPU free VRAM ~14.7GB
- GPU utilization 0%
- no active AURORA semantic/R3 continuation process

New program:
AURORA_EXTENSION_V5_CONTINUATION_V3

Create only:
extensions/extension_v5_continuation_v3/
reports/extension_v5_continuation_v3/


## 1. Scientific carry-forward

Before reading any new development/held-out/final outcome, prospectively hash-bind:
- V5 model-stress protocol and 24/24 qualification;
- Extension V1 frozen A1 tasks and selection rule;
- Extension V5 protocol;
- Continuation V1 carry-forward, index19 result, and failed index20 non-observation receipt;
- Continuation V2 protocol, reader qualification, readiness result, completion audit.

Carry forward exactly20 valid prompt-only observations, indices0..19.
Do not rerun them.

Resume exactly at prompt-only development index20.
Then preserve frozen order:
prompt-only20..47,
SFT0..47,
DPO0..47,
IPO0..47.

Complete development target remains exactly192 fixed observations.
No task reorder, substitution, dropping, easier prompt, output-dependent retry, model/checkpoint/tokenizer/render/tool change.


## 2. Reuse the V2 qualified monitor architecture

Use the Continuation V2 design:
A. Windows-native direct-NVML observer, 0.5s cadence, safety-critical.
B. Windows GlobalMemoryStatusEx observer, 1s cadence, safety-critical.
C. WSL /proc/meminfo observer, 1s cadence, safety-critical.

Use bounded incremental readers only:
- one open descriptor;
- appended reads only;
- <=256KiB chunks;
- <=64KiB partial line;
- <=128 recent rows;
- strict sequence validation;
- no whole-stream read_bytes/read_text/splitlines;
- no unbounded telemetry accumulation.

Optional process-tree diagnostics remain non-safety-critical and may fail without stopping an owned CUDA workload.

GPU safety remains unchanged:
- <=75C admission;
- >=2GiB free VRAM;
- 84C soft stop;
- 86C owned-child hard stop;
- >=87C failure;
- GPU observer stale >3s => stop.

Host observer stale >5s => stop.


## 3. Separate observer readiness from workload admission

Do NOT repeat V2's single-point soak-end admission rule.

Readiness asks only whether monitoring is healthy.
Admission asks whether resources are currently sufficient for a model child.

### Readiness
Run a fresh 120s CUDA-free triple-observer soak.

PASS requires:
- all three observers alive without restart;
- exact sequences, no schema/I/O errors;
- NVML required calls successful;
- GPU no thermal/VRAM breach;
- GPU max no-advance <3s;
- Windows and WSL observer max no-advance <5s;
- streams independently parse and hash;
- no CUDA launched.

Do NOT fail readiness merely because one final Windows/WSL memory sample is below the model launch threshold.

### Post-readiness stable admission
After readiness PASS, enter passive admission wait up to60 minutes.

Require simultaneously for FOUR observations at least5s apart:
- Windows available physical >=7GiB;
- WSL MemAvailable >=8GiB;
- GPU temperature <=75C;
- GPU free VRAM >=2GiB;
- all three observer heartbeats fresh;
- no other AURORA heavy CUDA owner.

Only then launch a model-bearing child.

If the envelope never appears within60 minutes, terminalize as BLOCKED_CURRENT_HOST_MEMORY_BASELINE or BLOCKED_CURRENT_THERMAL_BASELINE without CUDA.

This is a new prospective V3 rule and does not reinterpret V2.


## 4. Runtime host-memory gates

During every model-bearing child:

Windows:
- available physical <2GiB for two consecutive 1s samples => graceful resource stop;
- <1GiB on any sample => immediate owned-child stop.

WSL:
- MemAvailable <4GiB for two consecutive 1s samples => graceful resource stop;
- <2GiB on any sample => immediate owned-child stop.

Observers:
- Windows/WSL stream stale >5s => stop;
- GPU stream stale >3s => stop;
- observer process exit or malformed/sequence failure => stop.

Do not modify pagefile, WSL memory, overcommit, driver, BIOS, NVIDIA global settings, power plan, or unrelated applications.

After each model child exits, require a fresh four-observation admission envelope before the next model child.
This provides memory and thermal recovery between cases.


## 5. Pre-CUDA engineering validation

Because V2 monitor code passed 38 fault fixtures and the 128MiB reader test, V3 may reuse byte-identical logic where possible.

Before CUDA:
- verify V2 code hashes for copied/reused bounded-reader and observer logic;
- run all V2 monitor/fault fixtures against the V3 namespace;
- run scoped lint/design validation;
- run at least a32MiB streaming smoke test if runtime path code changed;
- if bounded-reader semantics changed materially, rerun the full >=128MiB test.

Then run the120s triple-observer readiness soak and stable admission wait.

After stable admission, run ONE TRAIN-only engineering canary:
- frozen V5 TRAIN case;
- prompt-only base;
- 128 forced greedy tokens;
- full frozen context;
- no development/held-out semantic outcome;
- all three observers active;
- complete decode required;
- no safety/resource stop.

Only canary PASS admits scientific semantic continuation.


## 6. Development continuation

Carry forward20 prompt-only observations.
Start new work exactly at prompt-only index20.

For every new case:
1. stable admission envelope;
2. immutable pre-case resource receipt;
3. exactly one owned model child;
4. triple-observer monitoring;
5. bounded telemetry receipt using stream refs/start_seq/end_seq plus recent context only;
6. child exit;
7. immutable semantic result and receipt;
8. development progress update;
9. memory/thermal recovery admission before next case.

Checkpoint after every successful case.
Also save a compact aggregate checkpoint every4 new cases.

No automatic retry of a case that generated an admitted semantic result.
If an implementation-only failure occurs before generation, preserve it, prove no semantic output was admitted, version the repair, rerun affected CPU/fault validation, and resume under a new implementation-attempt ID without weakening gates.


## 7. Development completion and finalist freeze

When exactly192 development observations exist and all hashes verify:
- aggregate carried + new observations;
- compute exact frozen four-arm summaries;
- family-macro executable success remains primary supplemental endpoint;
- integrity endpoints remain separate;
- apply the existing frozen selection rule;
- select at most one trained finalist;
- write immutable DEVELOPMENT_SELECTION before any held-out outcome access.

If no trained arm is eligible, record honestly and mark finalist-dependent tracks NOT_APPLICABLE where appropriate.


## 8. Held-out Agent confirmation

Only after complete development and immutable finalist freeze.

If a trained finalist exists:
- compare prompt-only vs selected trained finalist;
- exactly44 frozen held-out tasks;
- exactly9 dependence groups;
- frozen order/contracts;
- no reruns based on outcomes;
- preserve prospective UNDERPOWERED designation.

Use the same V3 stable admission and triple-observer runtime gates.


## 9. R3 D4

After Agent development is terminal and no CUDA owner overlaps:
- M41 training;
- C54 calibration;
- [54,60) development only;
- no [70,82) access before D4 model/calibrator freeze;
- no D3 rescue;
- select/freeze on development only;
- score untouched [70,82) once after freeze.

Use the same V3 monitor architecture and resource gates.
Do not rewrite old E03/E15_R3 status.


## 10. Integration and GPU serving

Only if prerequisites exist:
- supplemental policy x agent 2x2 if trained finalist exists;
- GPU/full-agent serving for prompt-only and finalist if available;
- retry/restart/cancellation;
- bounded recovery only when separately safe.

No historical E10/E12/E14/E15 status rewrite.


## 11. Closeout and evidence

Create:
reports/extension_v5_continuation_v3/CONTINUATION_PROTOCOL.json
reports/extension_v5_continuation_v3/PROTECTED_HISTORY_SNAPSHOT.json
reports/extension_v5_continuation_v3/CARRY_FORWARD_MANIFEST.json
reports/extension_v5_continuation_v3/state/CONTINUATION_STATUS.json
reports/extension_v5_continuation_v3/CONTINUATION_LOG.md

Final validation:
- full CPU regression;
- V3 monitor/fault fixtures;
- scoped lint;
- design validation;
- independent saved-file verification;
- all protected histories unchanged;
- canonical generation91 unchanged;
- outcome-access chronology verified;
- no owned observers/CUDA child left.

Do not rewrite V1/V2/V5 reports.

Start now without routine questions:
1. freeze V3 and hash-bind20 carried observations;
2. validate reused three-observer architecture;
3. run120s readiness;
4. wait prospectively for stable admission envelope;
5. run one TRAIN-only128-token canary;
6. resume at prompt-only index20;
7. complete development if safely possible;
8. freeze finalist, held-out once, R3 D4, integration, serving as prerequisites allow;
9. stop only for a genuine frozen safety/scientific blocker.
