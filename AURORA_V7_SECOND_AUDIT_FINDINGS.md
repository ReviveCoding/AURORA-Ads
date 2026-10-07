# AURORA V7 second audit: reproduced failure-path defects

Review handoff, not a claim of applied repair. Read at the next safe boundary. Do not edit active model code, stop unrelated processes, duplicate work, weaken frozen thresholds, or rerun admitted observations. Archive any already-executed source before a prospective repair attempt.

## Provenance and scope
Source checked read-only at 2026-10-05T04:40:00Z and 04:44:26Z. Ten scenarios ran in the assistant's isolated container, NOT on this PC. Fourteen production definitions were AST-matched to the current source; Python 3.13 AST dump formatting was normalized to the source runtime's 3.11 format. Some transport/memory/disk boundaries were mocked. Local socket tests were real container-local sockets. No actual Windows/GPU failure reproduction or historical root-cause claim follows.

## Six distinct defects reproduced

1. Graceful STOP is blocked by its triggering alarm.
   launcher.py Launch.permission passes session.check into startup_registration.send_frame. service_tick raises PRESTART_MONITOR_FAILURE on the already-latched SOFT_THERMAL_STOP or HOST_MEMORY_SOFT_STOP before sending a byte. Both conditions reproduced with bytes_sent=0. Healthy-monitor STOP succeeded. Preserve strict START/DECODE admission, but allow bounded stop-only delivery under a known alarm, with hard conditions retaining immediate targeted termination. Keep the original alarm, not a misleading PRESTART label.

2. Child-control EOF is treated as temporarily no frames.
   Launch.frames returns [] on recv()==b'' even when child.poll() is None. An alive child with a closed control channel can remain in the controller loop until a different timeout/budget event. Add named unexpected-EOF handling, distinguish expected terminal exit, and verify bounded loading/decode/control waits under unchanged scientific rules.

3. Failed partial ACK send can be resent on a corrupted stream.
   Session.check catches sendall failure but does not poison/disable the socket. A subsequent check, including cleanup, retries the entire ACK with unchanged sequence. A 12-byte partial-send timeout followed by another check reproduced identical-frame retransmission and a receiver decode error. sendall does not reveal how much was sent on failure. Use bounded offset-tracked writes or permanently fail that channel and rely on qualified independent cleanup. Audit every sender including watchdog; do not keep resending on an indeterminate stream.

4. Unregistered watchdog does not exit after parent EOF.
   The exact watchdog.main ran on a real local Unix socket with fake memory/evidence. Normal CLOSE exited. Parent disconnect with registration=None recorded WATCHDOG_IPC_FAILURE: CONNECTION_CLOSED but kept looping; the test harness had to set the stop event. Source has no unregistered terminal-disconnect exit path. Exit/flush/join when no owned child exists; with a registered child secure only that group first. Also inspect run_phase.py timeout cleanup, which currently reports failure without proving all created observers are gone.

5. Concurrent VRAM and >=87 C conditions lose thermal classification.
   Safety.gpu with temperature_c=87 and free_mib=1024 returns only VRAM_RESERVE_BREACH. Thermal-only control returns AUTOMATIC_THERMAL_FAILURE. This is NOT proof that stopping fails; both trigger a stop. It is loss of the required automatic thermal-failure event. Latch all hazards and preserve severity precedence.

6. Ledger/status partial commit is not idempotently recoverable.
   A fake status write failed after ledger replacement. Ledger used=110, status used=100. Identical retry raised duplicate-charge AssertionError and did not repair derived status. The guard correctly prevented double charging. Use authoritative ledger plus exact matching receipt/hash/duration reconciliation; reject mismatched duplicates. Audit crash recovery before the final phase charge so consumed work cannot disappear.

## Additional integration risk
Windows memory replay does not fix WSL latest-only forwarding. watchdog.py still keeps only the latest memory snapshot and rejects skipped sent_memory sequence. Actual Safety.memory rejects delivered [0,2] even when true source records were [0,1,2]. No native OS scheduling event was injected here. Add/test lossless bounded WSL source delivery and retention of brief low-memory episodes; do not weaken continuity or discard low samples. Check the previously reported Windows admission snapshot-versus-replay freshness issue too.

## Corrections to avoid needless redesign
A 0.2 s send timeout alone does NOT imply a 0.25/1.5 s receiver pause breaks sampling: OS buffers can absorb it. Test actual full-buffer backpressure before asserting failure. A long-lived monitor is not inherently a defect; it is a lifetime/coverage question. Neither is a reason to introduce an untested large architecture rewrite.

## Source fingerprints at audit
startup_registration.py 768768dcf5c91a442c6893f77a927f1ba1bf5fb8655ef295ebfe4cfc4b97a0bb (service_tick/send_frame lines21-42)
launcher.py f65eee92c0989b9f3de14b3554d657dd11f3a55555ebc22cd83174c81ad53286 (permission/frames lines76-108)
client.py e5d93b4521cee3ea674127f7e9968ee88a17c9d5b8b6f53a06a7f159aef626bd (check lines55-109)
safety.py eafcf6a741dac0ec9c835e155ee951dc584192480e4dbcfcf3c3104d4e8bed47 (Safety lines17-59)
budget.py 9bddc44d7b5129de322b08fda2c2adb9d14244aaccda66ec00b98b5cbf812c90 (charge lines5-14)
watchdog.py cfc97ce6f593b71cda2d73d998ad5c94ff952e3ae23f2b9bc419c3c1e23fd40a (main lines37-160)

## Required follow-through
First acknowledge receipt of this review and AURORA_V7_FULL_AUDIT_ADDENDUM.md. Queue acceptance alone is NOT proof of current-turn consumption or an enforced launch gate. Compare findings to the CURRENT source; report already-fixed items with exact regression evidence. Do not edit files used by an active child. At a safe boundary prospectively repair only the affected paths, add focused negative/positive tests, preserve executed source hashes and all 38 admitted observations, retain quarantined V6 index38 partials, and requalify the changed paths before scientific execution. Keep held-out/R3 final unopened and cumulative compute accounting unchanged. Do not call these findings fixed just because existing tests or an unrelated endurance run passed.
