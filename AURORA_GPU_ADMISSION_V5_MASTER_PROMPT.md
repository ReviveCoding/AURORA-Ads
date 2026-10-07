# AURORA GPU Admission V5
# Workload-representative Qwen qualification after V4 synthetic-C soft thermal stop

Repository:
C:\Users\bjw-0\Downloads\AURORA-Ads

Historical programs are immutable and terminal:
- AURORA E00-E16
- POST_CLOSURE_DIAGNOSTICS_V1
- AURORA_EXTENSION_V1
- AURORA_GPU_ADMISSION_V2
- AURORA_GPU_ADMISSION_V3
- AURORA_GPU_ADMISSION_V4

V2 remains HARD_THERMAL_STOP at 86C during synthetic Stage B.
V3 remains pre-CUDA INSTRUMENTATION_FAILURE from per-sample nvidia-smi process timeout.
V4 established that persistent direct NVML works: 600s soak passed with 636/636 successful records, A and B passed, but synthetic Stage C hit SOFT_THERMAL_STOP with an observed 85C sample and stopped safely.

Do not relabel or overwrite any prior result.

This new study is AURORA_GPU_ADMISSION_V5.

Current read-only snapshot before this request observed approximately:
- 72C
- ~14.6GiB free VRAM
- 2% utilization
Re-read actual state before freeze.

Purpose:
1. preserve the validated persistent direct-NVML safety monitor;
2. keep all existing thermal/VRAM limits unchanged;
3. retain light/moderate synthetic A/B only as engineering sanity checks;
4. replace synthetic Stage C as a mandatory admission gate with a workload-representative Qwen3-1.7B inference stress ladder;
5. if the representative workload qualifies, reopen only new supplemental Agent/R3/integration/serving branches under V5 namespaces.


## 0. Hard invariants

Never change or overwrite historical status/results/claims.

No weakening of safety limits:
- start envelope <=75C;
- >=2GiB free VRAM;
- 84C soft stop;
- 86C owned-child hard stop;
- any observed >=87C automatic failure;
- one heavy AURORA CUDA owner;
- direct NVML heartbeat fail-closed;
- no driver/BIOS/global power/NVIDIA global/WSL global changes;
- no unrelated process termination;
- no live ads or real spend;
- no final-outcome tuning.

Create:
reports/gpu_admission_v5/
extensions/gpu_admission_v5/
and only after qualification:
reports/extension_v5/
extensions/extension_v5/ if needed.

Snapshot/hash protected histories from final, posthoc, extension_v1, gpu_admission_v2/v3/v4, and canonical generation/state before CUDA.

A V5 thermal/device/monitor/reserve failure is terminal for the corresponding qualification attempt. Do not loosen gates after seeing results.


## 1. Monitoring architecture

Reuse the V4 direct Windows-native NVML design, not per-sample nvidia-smi processes.

Critical channel:
- persistent Windows-native process;
- direct nvml.dll calls;
- exact GPU UUID;
- temperature;
- memory free/used/total;
- required API return codes;
- append-only newline-committed JSONL;
- flush every record.

Use 0.5-second critical sampling cadence for V5.
The purpose is to reduce the blind interval observed in V4 where temperature rose from 81C to 85C between 1-second samples.

Do not claim continuous-temperature observation.

WSL watcher:
- local monotonic sequence advancement only;
- no cross-OS wall-clock heartbeat;
- >3 seconds without critical sequence advancement is a monitor failure in V5;
- required NVML-call failure, UUID mismatch, malformed sample, or reserve breach fails closed.

Optional utilization/power/pstate remains observational and must not block solely because optional metrics are unavailable.


## 2. Telemetry readiness

Because the same direct-NVML architecture passed a 600-second V4 soak, do not require another 10-minute soak unless implementation changes materially alter the sidecar.

Before CUDA, run a fresh 120-second V5 readiness soak with the 0.5-second cadence.

Pass criteria:
- >=235 successful committed records;
- zero required NVML-call failures;
- zero sequence regression/duplication;
- max WSL no-advance <3s;
- exact UUID throughout;
- >=2GiB free VRAM;
- no temperature >=84C;
- sidecar stays alive without restart.

If the new 0.5s implementation fails this readiness soak, stop V5 before CUDA.


## 3. Start and cooldown envelope

Before each CUDA stage/decode, require four fresh direct-NVML samples >=5 seconds apart:
- every sample <=75C;
- no successive temperature rise >1C;
- first-to-last rise <=1C;
- >=2GiB free VRAM;
- heartbeat fresh;
- exact UUID;
- no other AURORA heavy CUDA owner;
- no clearly identified unrelated heavy compute workload.

Maximum passive cooling/admission wait: 30 minutes per stage/decode.

Utilization is observational.

Do not automatically close Chrome, overlays, desktop processes, or unrelated applications.


## 4. Runtime safety

Every V5 CUDA child:
- monitored at 0.5s critical cadence;
- 84C -> create graceful-stop signal immediately;
- owned workload checks safe-stop signal at synchronized decode/compute boundaries;
- allow at most 1.5 seconds to exit after soft stop;
- 86C -> SIGKILL only the owned unreaped POSIX child process group;
- any observed >=87C -> automatic V5 qualification failure;
- free VRAM <2GiB -> stop;
- heartbeat >3s -> stop;
- required NVML failure -> stop;
- UUID mismatch/device loss/CUDA fatal -> stop.

Preserve telemetry and stop latch.
Never kill unrelated workloads.


## 5. Synthetic sanity checks only

Run only V4-comparable Stage A and B:

A:
- 15s
- n=256 FP32
- compute/rest .10/.90
- seed41
- TF32 off
- <=1GiB allocator cap

B:
- 60s
- n=1024 FP32
- compute/rest .25/.75
- same deterministic checksum rules

Require fresh <=75C admission before each.
Both must pass with zero sample >=84C and all monitoring/resource rules satisfied.

Do NOT run the prior synthetic C as a mandatory qualification gate.
Preserve V4 C failure as evidence that a 2048 FP32 50% duty synthetic stress is not sustainable under the frozen local thermal envelope.

Optionally calculate what V4 C represented, but do not rerun it in V5.


## 6. Workload-representative Qwen3-1.7B qualification

Only after readiness + A + B PASS.

Before loading any model:
freeze a V5 MODEL_STRESS_PROTOCOL.json containing:
- exact Qwen3-1.7B base revision;
- prompt-only base identity;
- SFT seed41 adapter hash;
- DPO seed41 adapter hash;
- IPO seed41 adapter hash;
- tokenizer revision;
- render/tool contract hashes;
- exact TRAIN-only stress task IDs selected without semantic outcomes;
- generation settings;
- token ladder;
- common pass/fail rule;
- cooldown rule.

Do not load Agent development/final semantic outcomes.

Stress tasks:
Freeze TWO TRAIN-only cases:
1. longest attended-context case;
2. highest tool-contract/context complexity case.
If they are the same case, freeze the next-longest distinct case as the second.

All four arms use identical cases and generation settings.

Token ladder per arm:
- 128 forced new tokens;
- cooldown/re-admission;
- 256 forced new tokens;
- cooldown/re-admission;
- 512 forced new tokens.

No sampling. Deterministic/greedy generation.
Preserve full context and tool schema.
Do not shorten context to make thermal qualification easier.

After each completed safe decode:
- require temperature recovery to the <=75C admission envelope;
- nominal passive cooldown target 60s;
- 90s may be used only if the GPU is still above the start envelope after a completed safe decode;
- 90s is not a retry after a thermal/device/monitor failure.

A decode PASS requires:
- full requested tokens completed unless a deterministic EOS is explicitly disallowed by forced-token harness;
- zero sample >=84C;
- no safety/resource/monitor failure;
- exact model/checkpoint identity;
- telemetry covers load and immediate post-load recovery;
- output finite and decodable.

If any arm or token level hits a safety failure, stop the model-stress program. Do not retry or omit that arm.

All four arms must pass through 512 tokens before semantic scoring is admitted.


## 7. If representative model stress passes

Create reports/extension_v5/ only after all four arms pass.

Then execute the remaining supplemental scientific branches while preserving all historical statuses:

### Agent development
- reuse frozen Extension V1 semantic task IDs and nine dependence groups;
- prompt-only vs SFT vs DPO vs IPO;
- identical host/tool/validation contracts;
- family-macro executable success primary supplemental endpoint;
- integrity/numeric/tool metrics separately reported;
- keep UNDERPOWERED designation where required.

### Agent finalist
- select at most one trained finalist by the existing frozen rule;
- additional seeds only for the selected finalist if predeclared and resource-qualified;
- freeze finalist before held-out confirmation;
- one held-out supplemental confirmation.

### R3 D4
- M41 train;
- C54 calibration;
- [54,60) development only;
- no [70,82) access before V5 model/calibrator freeze;
- untouched [70,82) scored once after freeze;
- no D3 rescue.

### Integration
- supplemental policy x agent 2x2 only if a trained finalist exists.

### Serving
- isolated matched CPU/CUDA numerical serving;
- complete prompt-only task;
- complete finalist task if available;
- full host/tool loop;
- retry/restart/cancellation;
- bounded recovery/OOM only if separately safe and never violates 2GiB reserve.

All GPU workloads use the V5 direct-NVML watcher and fresh <=75C admissions.
No historical E10/E12/E14/E15 status is rewritten.


## 8. Evidence and terminalization

Save:
- V5 protocol;
- protected-history snapshot;
- direct-NVML readiness stream/result;
- A/B receipts;
- MODEL_STRESS_PROTOCOL.json;
- per-arm/per-token telemetry and decode receipts;
- all safety stop latches;
- exact model/checkpoint/input/code hashes;
- extension_v5 results if reached;
- completion audit;
- technical report/limitations.

If V5 model stress fails:
- distinguish thermal vs monitoring vs VRAM vs device/CUDA vs harness failure;
- keep semantic and R3 final outcomes unopened;
- terminalize honestly;
- do not weaken thresholds.

Closeout:
- all protected histories unchanged;
- canonical generation unchanged;
- raw telemetry independently parsed;
- no owned CUDA/sidecar processes;
- regression tests, safety fixtures, design validation, scoped lint;
- independent saved-file verification.

Terminal status:
PASSED_AND_SUPPLEMENTAL_BRANCHES_TERMINAL
or
BLOCKED_WITH_REASON.

Start now:
1. verify V4 terminal state and current cooler GPU baseline;
2. snapshot protected histories;
3. implement 0.5s persistent direct-NVML V5 watcher;
4. freeze V5 protocol before CUDA;
5. run 120s telemetry readiness;
6. run A/B;
7. freeze representative Qwen stress manifest;
8. execute 128->256->512 ladder across prompt/SFT/DPO/IPO;
9. only on all-four PASS open extension_v5 and continue the remaining feasible branches without routine user questions.
