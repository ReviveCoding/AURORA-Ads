# AURORA GPU Admission V3
# Cooler-baseline independent retry after V2 hard thermal stop

Repository: C:\Users\bjw-0\Downloads\AURORA-Ads

Historical E00-E16, POST_CLOSURE_DIAGNOSTICS_V1, AURORA_EXTENSION_V1, and GPU_ADMISSION_V2 are immutable and terminal.
Do not relabel or overwrite V2. V2 remains a failed qualification with Stage B HARD_THERMAL_STOP at 86C.

This is a new independent attempt, AURORA_GPU_ADMISSION_V3, authorized because the GPU is now at a materially cooler baseline after the prior external workload ended.

Preserve the same safety philosophy and do not loosen runtime limits:
- Windows-native telemetry sidecar, no synchronous WSL nvidia-smi in the generation path;
- same GPU UUID binding;
- >=2 GiB free VRAM;
- 84C soft stop;
- 86C owned-child hard stop;
- any >=87C automatic failure;
- heartbeat <=6s by local monotonic sequence advancement;
- no driver/BIOS/power/global WSL changes;
- do not terminate unrelated processes;
- one heavy AURORA CUDA owner;
- no automatic retry after a V3 hardware-risk failure.

Create reports/gpu_admission_v3/ and extensions/gpu_admission_v3/.
Snapshot and hash reports/final/, reports/posthoc/, reports/extension_v1/, and reports/gpu_admission_v2/ before CUDA.

Freeze V3 protocol before work. Use the same bounded ramp recipe as V2 for comparability:
A: 15s n=256, 0.10/0.90 compute/rest;
B: 60s n=1024, 0.25/0.75;
C: 180s n=2048, 0.50/0.50.
Same deterministic checksum rules.

V3 start envelope:
- four successful native samples >=5s apart;
- each temperature <=75C;
- first-to-last rise <=1C;
- no successive rise >1C;
- >=2 GiB free VRAM;
- fresh heartbeat and exact UUID;
- no other AURORA heavy CUDA owner.
Utilization is observational only.
Maximum passive admission window 30 minutes.

Reason for <=75C here: the current baseline is now ~70C, so V3 can require materially more initial thermal headroom than V2 without weakening any runtime gate.

Run A -> cooldown/re-admission -> B -> cooldown/re-admission -> C.
No stage retry after thermal/device/monitor/reserve failure.

If and only if A/B/C all pass:
1. freeze a V3 1.7B TRAIN-only model-stress protocol;
2. qualify prompt-only, SFT, DPO, IPO with exact existing identities and full context;
3. use prospectively fixed cooling candidates 60s then 90s only for passive-cooling insufficiency, never to retry a thermal/device failure;
4. require all four arms to pass before semantic comparison.

If all four model-stress arms pass, continue under reports/extension_v3/:
- frozen four-arm Agent development semantic comparison;
- select at most one trained finalist by the already frozen extension rule;
- optional required finalist seeds within resource budget;
- freeze then one held-out supplemental confirmation;
- R3 D4 using M41/C54/[54,60) only for development, then freeze and untouched [70,82) once;
- supplemental policy x agent 2x2 only if a trained finalist exists;
- isolated GPU/full-agent serving and safe bounded recovery/OOM only if independently qualified.

Do not alter historical blocked statuses. Everything is supplemental.
Do not inspect Agent semantic or R3 final outcomes before their respective freezes.

If V3 fails at any resource gate, terminalize V3 honestly and stop dependent branches.
Generate V3 technical report, telemetry summary, completion audit, and verify all protected hashes unchanged.

Start now by verifying the cooler baseline, freezing V3, and running the bounded ramp only when the <=75C start envelope passes.