# AURORA GPU Admission V2 Master Prompt
# Prospective monitor qualification and conditional reopening of supplemental CUDA work

Repository:
C:\Users\bjw-0\Downloads\AURORA-Ads

Historical AURORA E00-E16, POST_CLOSURE_DIAGNOSTICS_V1, and AURORA_EXTENSION_V1 are terminal.
Do not rewrite, reopen, relabel, or overwrite them.

This is a NEW supplemental engineering study:
AURORA_GPU_ADMISSION_V2

Purpose:
1. prospectively qualify a safer and more reliable Windows-native GPU monitor;
2. determine whether the current RTX 4090 Laptop GPU can safely sustain the required AURORA CUDA workloads;
3. only if qualification passes, continue the previously blocked supplemental Agent, R3 D4, integration, and GPU-serving branches under new extension IDs.

Hard invariants:
- historical E00-E16 status unchanged;
- POST_CLOSURE_DIAGNOSTICS_V1 unchanged;
- AURORA_EXTENSION_V1 unchanged;
- no primary result/model/policy/calibrator/threshold changes;
- no final-outcome tuning;
- no live advertising writes or real spend;
- no driver/BIOS/global power/WSL configuration changes;
- no unrelated process termination;
- no lowering the existing 2 GiB VRAM reserve;
- never allow the owned workload to reach the historical 87C project ceiling.

Create a separate namespace:
reports/gpu_admission_v2/
extensions/gpu_admission_v2/


## 0. Verify and snapshot before work

Before mutation:
- read WORK_STATE.md;
- read reports/final/FINAL_STATUS.json;
- read reports/posthoc/state/POSTHOC_STATUS.json;
- read reports/extension_v1/state/EXTENSION_STATUS.json;
- read Extension V1 Monitor V2 protocol, preflight, telemetry and qualification artifacts;
- read historical SFT inference-duty failures and monitor-timeout diagnosis;
- inspect actual active AURORA processes;
- inspect Windows-native GPU identity, temperature, free/used VRAM, utilization, power and pstate;
- verify WSL CUDA sees the same physical GPU UUID.

Snapshot hashes for:
reports/final/
reports/posthoc/
reports/extension_v1/
and the historical primary state.

Create:
reports/gpu_admission_v2/GPU_ADMISSION_V2_PROTOCOL.md
reports/gpu_admission_v2/PROTECTED_HISTORY_SNAPSHOT.json
reports/gpu_admission_v2/state/GPU_ADMISSION_V2_STATUS.json
reports/gpu_admission_v2/GPU_ADMISSION_V2_LOG.md

Freeze all admission thresholds and pass/fail criteria before the first V2 CUDA load.


## 1. Engineering rationale

The historical SFT 5-second profile reached the thermal target.
The historical 10/30-second SFT profiles failed because synchronous WSL nvidia-smi queries exceeded their 3-second instrumentation timeout.
Extension V1 moved telemetry to Windows-native sampling but used a prospectively frozen <=75C and <=10% utilization start envelope that did not occur within 15 minutes, so no CUDA workload launched.

Do not convert either historical result into a pass.

NVIDIA documents that NVML/nvidia-smi under WSL does not support every query, including some utilization/process queries.
Therefore V2 must keep Windows-native telemetry outside the token-generation critical path.

Utilization is observational in V2, not a hard admission threshold.
Safety gates use direct temperature, temperature trend, VRAM reserve, heartbeat freshness, GPU identity, and owned-workload state.


## 2. V2 monitoring architecture

Use:
Windows-native nvidia-smi/NVML sidecar
-> append-only JSONL telemetry
-> independent WSL safety watcher
-> owned WSL CUDA child process.

Do not query WSL nvidia-smi synchronously from generation callbacks.

Sidecar fixed cadence:
2 seconds unless a more conservative cadence is prospectively frozen before any CUDA start.

Each committed record:
sequence integer,
Windows UTC timestamp,
GPU UUID,
temperature C,
memory free/used/total MiB,
utilization percent if available,
power draw if available,
pstate if available,
native query wall duration,
query success/error.

Atomic/append-safe record commitment required.

For heartbeat safety, do NOT depend on Windows-vs-WSL wall-clock subtraction.
The WSL watcher must track sequence advancement using its own monotonic clock.
If sequence does not advance within 6 seconds, latch instrumentation failure and stop the owned workload.

Bind the GPU UUID exactly.


## 3. Prospectively freeze the V2 start envelope

Before any CUDA workload, require four consecutive successful Windows-native samples 5 seconds apart satisfying:

- GPU UUID matches the frozen RTX 4090 Laptop GPU;
- temperature <=79C on every sample;
- no sample-to-sample rise >1C;
- first-to-last temperature does not rise by more than1C;
- free VRAM >=2 GiB on every sample;
- telemetry sequence remains fresh;
- no other AURORA heavy CUDA owner exists.

GPU utilization is recorded but is NOT a hard admission criterion because Windows desktop/display activity can produce nonzero utilization without establishing unsafe CUDA contention.

If a clearly identifiable unrelated heavy compute workload is present, do not terminate it; defer admission and keep monitoring.

Allow a maximum 30-minute passive admission window.
No CUDA is started until the four-sample envelope passes.

If it never passes, record BLOCKED_CURRENT_THERMAL_BASELINE and stop all dependent CUDA branches.


## 4. Runtime safety gates

For every V2 CUDA child:

- normal VRAM reserve must remain >=2 GiB;
- telemetry heartbeat must remain <=6 seconds stale by local monotonic sequence tracking;
- 84C is the V2 soft-stop threshold: request graceful termination at the next safe Python boundary;
- 86C is the V2 hard-stop threshold: terminate only the owned CUDA child/process group immediately;
- any observed >=87C is an automatic V2 qualification failure;
- device loss, CUDA fatal error, monitor failure, UUID mismatch, or reserve breach is a qualification failure.

Do not raise any threshold because a run almost passes.
Do not close unrelated applications automatically.
Do not modify driver/power settings.

Preserve all raw telemetry and partial run evidence before failure whenever possible.


## 5. Bounded CUDA ramp qualification

No model, semantic task, final outcome, or R3 final data may be used here.

Use an extension-only deterministic CUDA compatibility load with fixed seeds and bounded memory.
Freeze exact tensor sizes and compute recipe before execution.

Run sequentially only after the start envelope passes:

Stage A: 15-second low-load CUDA exercise.
Cooldown/passive monitoring until start envelope is re-established.

Stage B: 60-second moderate-load CUDA exercise.
Cooldown until start envelope is re-established.

Stage C: 180-second sustained bounded CUDA exercise.

Pass criteria for each stage:
- child exits normally;
- no monitor/heartbeat/UUID/reserve failure;
- no sample >=84C;
- no device loss;
- expected deterministic numerical checksum finite and repeatable;
- telemetry covers the whole workload.

Do not auto-retry a failed stage.
A failure terminalizes V2 unless it is an implementation bug demonstrably independent of GPU outcome; if so preserve the failed attempt, repair prospectively, and run under a new attempt ID without weakening gates.


## 6. Actual 1.7B inference stress qualification

Only if all bounded ramp stages pass.

Use exact existing Qwen3-1.7B identities and TRAIN-only longest-prefix cases.
Do not load development/final semantic outcomes.

Create a new V2 inference-duty protocol separate from historical primary/Extension V1.

Freeze before generation:
- prompt-only/SFT/DPO/IPO checkpoint hashes;
- context/tool/tokenizer/render identities;
- stress case IDs;
- forced decode length;
- cooling cadence candidates;
- common-duty selection rule.

Use a conservative cadence schedule predeclared as:
60 seconds, then 90 seconds if needed.
Do not use semantic performance to choose cadence.

For each arm:
- perform required full forced decodes under the V2 watcher;
- preserve full context;
- no truncation of tool contract;
- require all decodes complete;
- require no runtime gate breach.

If all four arms pass, freeze one common V2 duty profile as the maximum required passing cadence.

If any arm fails safely, preserve the failure and do not silently omit it from a four-arm comparison.


## 7. Conditional continuation if GPU Admission V2 passes

If bounded ramp and four-arm inference stress qualification pass:

Create a new supplemental namespace:
reports/extension_v2/

Do NOT alter historical blocked statuses.

Then execute the remaining technically feasible CUDA-dependent branches in this order:

1. Agent semantic development comparison:
prompt-only vs SFT vs DPO vs IPO using the already prospectively frozen extension benchmark and identical host/tool contracts.
Primary supplemental endpoint: family-macro executable success.
Integrity metrics remain separate.

2. Select at most one trained supplemental finalist by the pre-frozen rule.
If additional seeds are required and within resource budget, run only the selected finalist.
Freeze the supplemental finalist before held-out confirmation.
Run held-out supplemental confirmation once.

3. R3 D4 neural finite-horizon delay model:
use M41 training, C54 calibration, [54,60) development selection;
do not access [70,82) during development;
freeze the selected supplemental R3 model/calibrator;
then score untouched [70,82) once.

4. Supplemental policy x agent 2x2 only if a trained finalist exists.

5. Isolated GPU/full-agent serving:
matched numerical CPU/CUDA,
prompt-only complete task,
trained-finalist complete task if available,
full host-tool loop,
restart/retry/cancellation,
safe bounded OOM/recovery only if it can be isolated without violating normal 2GiB reserve.

Every result is supplemental and must never be written back as historical E10/E12/E14/E15 completion.


## 8. If GPU Admission V2 does not pass

Do not keep experimenting with looser gates.

Record exactly why:
- start envelope unavailable;
- bounded stage thermal stop;
- heartbeat/telemetry failure;
- VRAM reserve breach;
- CUDA/device failure;
- actual-model stress failure.

Generate:
GPU_ADMISSION_V2_TECHNICAL_REPORT.md
GPU_ADMISSION_V2_STATUS.json
GPU_ADMISSION_V2_TELEMETRY_SUMMARY.csv
GPU_ADMISSION_V2_LIMITATIONS.md

Mark dependent supplemental GPU branches BLOCKED_WITH_REASON.

The historical project and Extension V1 remain valid and unchanged.


## 9. Validation and closeout

Maintain a separate V2 event ledger and input/output hashes.

Before terminal status:
- verify reports/final hashes unchanged;
- verify reports/posthoc hashes unchanged;
- verify reports/extension_v1 hashes unchanged;
- run extension safety fixtures;
- run relevant CPU regression/lint/semantic validation;
- verify telemetry JSONL sequence integrity and UUID;
- verify no owned V2 process remains active;
- independently verify saved CSV/JSON artifacts.

Terminal statuses:
PASSED_AND_SUPPLEMENTAL_BRANCHES_TERMINAL
or
BLOCKED_WITH_REASON.

Do not claim production qualification.

Start now:
1. create/freeze V2 protocol and protected snapshot;
2. collect passive Windows-native baseline;
3. wait for the prospectively frozen start envelope;
4. only then run bounded CUDA ramp;
5. proceed conditionally as specified above without asking routine questions.
