# AURORA GPU Admission V4
# Persistent direct-NVML monitor qualification and conditional CUDA extension

Repository:
C:\Users\bjw-0\Downloads\AURORA-Ads

Historical programs are immutable and terminal:
- AURORA E00-E16
- POST_CLOSURE_DIAGNOSTICS_V1
- AURORA_EXTENSION_V1
- AURORA_GPU_ADMISSION_V2
- AURORA_GPU_ADMISSION_V3

V2 remains a failed Stage-B qualification with HARD_THERMAL_STOP at 86C.
V3 remains a failed pre-CUDA qualification because one native nvidia-smi query took 3.039726s against the prospectively fixed 3s process-query timeout.
Do not relabel, overwrite, reinterpret, or delete either failure.

This is a new independent engineering study:
AURORA_GPU_ADMISSION_V4

Current pre-request read-only snapshot observed approximately 71C, ~14.4GiB free VRAM, low power/P8.
Re-read actual state yourself before freezing V4.

Purpose:
1. eliminate per-sample nvidia-smi process invocation from the safety-critical telemetry path;
2. prospectively qualify a persistent Windows-native direct-NVML monitor before any CUDA workload;
3. retain the same thermal/VRAM safety limits;
4. if monitoring and bounded CUDA qualification pass, conditionally reopen only new supplemental GPU branches under V4 namespaces.


## 0. Hard invariants

- Never change historical E00-E16/posthoc/Extension V1/V2/V3 results or statuses.
- No primary-result/model/policy/calibrator/threshold changes.
- No final-outcome tuning.
- No live-ad writes or real spend.
- No driver, BIOS, Windows power-plan, NVIDIA global setting, or WSL global setting changes.
- Do not terminate unrelated processes.
- Keep >=2GiB free-VRAM reserve.
- 84C soft stop, 86C owned-child hard stop, any observed >=87C automatic failure.
- One heavy AURORA CUDA owner at a time.
- No automatic retry after a V4 hardware-risk failure.
- No semantic Agent outcomes or R3 final outcomes before their required freezes.

Create only:
reports/gpu_admission_v4/
extensions/gpu_admission_v4/
and, only after all qualification gates pass:
reports/extension_v4/
extensions/extension_v4/ if needed.

Before mutation, hash/snapshot protected evidence from:
reports/final/
reports/posthoc/
reports/extension_v1/
reports/gpu_admission_v2/
reports/gpu_admission_v3/
plus canonical generation/state pointers.


## 1. Replace the safety-critical telemetry architecture

The safety-critical path MUST NOT start a fresh nvidia-smi.exe process for every sample.

Use a single persistent Windows-native process that talks directly to NVIDIA NVML.
NVIDIA documents NVML as the underlying programmatic library used by nvidia-smi and documents the Windows NVML library location, including DCH installs under Windows System32.

Preferred implementation:
- existing Windows Python + ctypes.WinDLL direct loading of nvml.dll, with no package install;
- if a suitable existing Windows Python is unavailable, use PowerShell Add-Type / C# P/Invoke to nvml.dll;
- do not install a driver, SDK, pip package, or system-wide dependency merely to make V4 work.

Critical NVML channel queries only the minimum safety set:
- nvmlInit_v2 / cleanup;
- exact device handle / UUID identity;
- temperature;
- memory info (free/used/total).

The critical sidecar is long-lived for the entire qualification.
It writes newline-committed append-only JSONL with:
seq,
sidecar monotonic seconds,
Windows UTC descriptive timestamp,
UUID,
temperature_c,
free_mib,
used_mib,
total_mib,
per-cycle query wall duration,
success/error,
API return codes where available.

Use 1-second sampling for the critical channel.
Flush after every complete newline record.

Do not use cross-OS wall-clock subtraction for heartbeat.
WSL safety watcher tracks strictly advancing sequence with its own monotonic timer.
If critical sequence does not advance for >6 seconds, latch MONITOR_HEARTBEAT_FAILURE and stop only the owned CUDA child.

A single failed required NVML call during an active CUDA workload is fail-closed.
Before CUDA, a required-call failure fails the telemetry-only qualification and no CUDA starts.


## 2. Optional observational channel

Utilization, power, pstate, graphics/compute process information are NOT safety gates.

If useful, collect them from:
- separate direct NVML calls in a noncritical observer, or
- a lower-rate persistent/read-only nvidia-smi diagnostic process.

The optional observer may fail without itself stopping a CUDA child.
Record its availability and failures, but never let utilization/power/pstate availability determine safety admission.

Do not claim absence of unrelated GPU work from unsupported WSL process queries alone.
Use Windows process/context inspection plus critical resource state conservatively.


## 3. Telemetry-only qualification before any CUDA

Freeze the V4 telemetry reliability protocol before starting the direct NVML sidecar.

Run a 10-minute telemetry-only soak with ZERO AURORA CUDA workload.

Prospective pass criteria:
- persistent critical sidecar stays alive without restart;
- exact GPU UUID on every successful record;
- >=590 committed successful critical records over approximately 600 seconds;
- zero required NVML-call failures;
- zero sequence regressions/duplicates;
- max WSL-observed no-advance interval <6 seconds;
- >=2GiB free VRAM throughout;
- no temperature >=84C;
- raw stream parses independently after close;
- per-cycle latency distribution and maximum are reported, but no arbitrary 3-second per-query process timeout exists.

If this telemetry-only soak fails, terminalize V4 as MONITOR_QUALIFICATION_FAILURE.
Do not run CUDA and do not loosen criteria in the same attempt.

A one-off nvidia-smi command may be used only as an external read-only cross-check, not as the safety source of truth.


## 4. Cooler-baseline start envelope

Only after telemetry-only qualification passes, require four fresh critical-NVML samples >=5 seconds apart satisfying:

- exact UUID;
- temperature <=75C on every sample;
- no successive increase >1C;
- first-to-last temperature increase <=1C;
- free VRAM >=2GiB;
- critical heartbeat fresh;
- no other AURORA heavy CUDA owner;
- no clearly identified unrelated heavy compute workload.

Utilization is observational only.

Maximum passive start/cooldown wait per stage: 30 minutes.
If the <=75C envelope never appears, record BLOCKED_CURRENT_THERMAL_BASELINE and stop.


## 5. Runtime safety rules

For every V4 CUDA child:
- critical telemetry continues at 1-second cadence;
- >=2GiB free VRAM required;
- heartbeat no-advance >6s -> stop owned child;
- required NVML call failure -> stop owned child;
- UUID mismatch -> stop owned child;
- 84C -> request graceful soft stop at the next synchronized Python boundary;
- allow at most 2 seconds for graceful stop;
- 86C -> immediately terminate only the newly launched owned POSIX child process group;
- any observed >=87C -> automatic V4 failure;
- CUDA fatal/device loss -> failure.

Never terminate unrelated Windows/WSL workloads.
Preserve latch and raw telemetry before/while terminating when possible.


## 6. Bounded CUDA ramp, same recipe for comparability

Use the exact V2/V3 deterministic recipe and seed 41:
- Stage A: 15s, n=256 FP32, compute/rest 0.10/0.90
- Stage B: 60s, n=1024 FP32, compute/rest 0.25/0.75
- Stage C: 180s, n=2048 FP32, compute/rest 0.50/0.50
- TF32 disabled
- <=1GiB allocator cap
- CPU workers 2
- deterministic finite checksum rules unchanged.

Sequence:
fresh <=75C admission -> A -> cooldown/re-admission -> B -> cooldown/re-admission -> C.

Each stage must:
- exit normally;
- have continuous critical telemetry coverage;
- have no sample >=84C;
- have no heartbeat/NVML/UUID/VRAM/device failure;
- produce the deterministic checksum/result;
- satisfy the pre-frozen minimum telemetry coverage.

No stage retry after a thermal/device/monitor/reserve failure.
Implementation-only bugs may be repaired only with the failed attempt preserved and a new explicit attempt ID, without changing gates.


## 7. Conditional Qwen3-1.7B stress qualification

Only if telemetry soak AND A/B/C all pass.

Freeze a separate V4 model-stress manifest before any generation:
- exact Qwen3-1.7B base/revision;
- prompt-only, SFT, DPO, IPO seed41 adapter hashes;
- tokenizer/render/tool identities;
- eight TRAIN-only longest-prefix cases;
- full attended context;
- forced 512-token decode requirement;
- cadence candidates 60s then 90s;
- common-duty selection rule.

Do not inspect Agent semantic outcomes.

Every decode runs under the direct-NVML critical watcher.
Require fresh <=75C admission before each decode.
90s cooling may be used only for passive-cooling insufficiency after a completed safe decode, never to retry a thermal/device/monitor failure.

All four arms must qualify.
No omitted arm and no semantic-performance-based cadence choice.


## 8. Conditional supplemental empirical extension

Only if all four model-stress arms qualify, create reports/extension_v4/.

Then proceed without changing old blocked statuses:

1. Agent semantic development comparison
   - prompt-only vs SFT vs DPO vs IPO
   - reuse already frozen Extension V1 task IDs, nine dependence groups, identical host/tool contracts
   - primary supplemental endpoint remains family-macro executable success
   - integrity metrics separate
   - preserve UNDERPOWERED status when appropriate.

2. Supplemental trained finalist
   - select at most one trained finalist using the already frozen rule
   - any additional seeds only for the selected finalist and only if predeclared/resource-qualified
   - freeze finalist before held-out confirmation
   - held-out supplemental confirmation once.

3. R3 D4
   - M41 train
   - C54 calibration
   - [54,60) development
   - no access to [70,82) until new V4 model/calibrator freeze
   - score [70,82) once after freeze
   - no D3 rescue.

4. Supplemental policy x agent 2x2 only if trained finalist exists.

5. Isolated GPU/full-agent serving
   - matched numerical CPU/CUDA
   - prompt-only complete task
   - trained-finalist complete task if available
   - full host-tool loop
   - restart/retry/cancellation
   - bounded recovery/OOM only if safe and independently qualified.

Everything remains supplemental.
Never rewrite historical E10/E12/E14/E15 statuses.


## 9. Evidence, validation and closeout

Create:
reports/gpu_admission_v4/GPU_ADMISSION_V4_PROTOCOL.md
reports/gpu_admission_v4/PROTECTED_HISTORY_SNAPSHOT.json
reports/gpu_admission_v4/GPU_ADMISSION_V4_LOG.md
reports/gpu_admission_v4/state/GPU_ADMISSION_V4_STATUS.json

Save:
- critical NVML raw stream
- optional observer stream separately
- telemetry soak qualification
- stage admissions/results
- ownership receipts
- model-stress freeze/results if reached
- exact code/input/output hashes
- completion audit
- technical report and limitations.

Before terminal closeout:
- protected histories unchanged;
- canonical generation unchanged;
- critical stream independently parsed;
- sequence/UUID/memory/temperature rules verified;
- relevant regression tests/safety fixtures/design validation/scoped lint pass;
- no owned sidecar or CUDA workload remains.

Terminal status:
PASSED_AND_SUPPLEMENTAL_BRANCHES_TERMINAL
or
BLOCKED_WITH_REASON.

Do not claim production qualification.

Start now:
1. inspect current processes/resources and protected histories;
2. implement and independently test direct-NVML critical sidecar without CUDA;
3. freeze the V4 protocol;
4. run the 10-minute telemetry-only soak;
5. only on soak PASS, wait for <=75C start envelope and run A/B/C;
6. proceed conditionally through model stress and extension_v4 without routine user questions.
