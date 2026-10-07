#!/usr/bin/env python3
"""Bounded current-device thermal/allocation/numerical/one-update qualification."""
from __future__ import annotations

import gc
import importlib
import importlib.metadata
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aurora.artifacts import atomic_json, digest
from aurora.resources import check_gpu_room, cuda_lease, telemetry
from aurora.studies import Study


def main() -> int:
    study = Study(ROOT, "e00_gpu_qualification")
    report = {"status": "RUNNING", "GPU_QUALIFIED": False, "telemetry": [], "checks": [], "qualification_scope": "bounded local core profile; planned own allocation<=8GiB plus>=2GiB device headroom", "no_universal_temperature_threshold": True}
    start = time.perf_counter()
    try:
        baseline = check_gpu_room(8.)
        report["telemetry"].append(baseline)
        guidance = subprocess.run(["nvidia-smi", "-q", "-d", "TEMPERATURE,POWER,PERFORMANCE"], text=True, capture_output=True, check=True).stdout
        (study.directory / "device_guidance.txt").write_text(guidance)
        target_lines = [line for line in guidance.splitlines() if "GPU Target Temperature Specification" in line]
        if len(target_lines) != 1:
            raise ValueError("Current device target guidance unresolved")
        device_target = float(target_lines[0].split(":")[-1].strip().split()[0])
        report["device_reported_target_c"] = device_target
        if baseline["temperature_c"] >= device_target:
            raise ValueError("No current thermal headroom below device-reported operating target")
        for module in ("torch", "transformers", "trl", "peft", "accelerate", "bitsandbytes", "xgboost"):
            imported = importlib.import_module(module)
            report.setdefault("versions", {})[module] = getattr(imported, "__version__", "imported")
        import numpy as np
        import torch
        from transformers import Qwen3Config, Qwen3ForCausalLM
        from peft import LoraConfig, get_peft_model
        if not torch.cuda.is_available():
            raise ValueError("CUDA unavailable in actual isolated environment")
        torch.set_num_threads(2)
        torch.manual_seed(71)
        with cuda_lease(study.runtime):
            torch.cuda.reset_peak_memory_stats()
            for side in (256, 512, 1024, 2048):
                before = time.perf_counter()
                x = torch.randn(side, side, device="cuda", requires_grad=True)
                y = torch.randn(side, side, device="cuda", requires_grad=True)
                for _ in range(3):
                    loss = ((x @ y) / side).square().mean()
                    loss.backward()
                    assert torch.isfinite(loss) and torch.isfinite(x.grad).all()
                    x.grad = y.grad = None
                torch.cuda.synchronize()
                value = telemetry()
                report["telemetry"].append(value)
                report["checks"].append({"stage": "stepped_matmul_backward", "side": side, "updates": 3, "wall_seconds": time.perf_counter() - before})
                if value["temperature_c"] >= device_target:
                    raise ValueError("Step reached device-reported target; sustained qualification unclear")
                del x, y, loss
                gc.collect()
                torch.cuda.empty_cache()
            for gib in (1, 2, 4, 8):
                buffer = torch.empty(gib * 1024**3, dtype=torch.uint8, device="cuda")
                buffer[::1024**2] = 17
                torch.cuda.synchronize()
                report["telemetry"].append(telemetry())
                report["checks"].append({"stage": "bounded_allocator", "gib": gib, "status": "PASSED_SPARSE_TOUCH_NOT_SUSTAINED_BANDWIDTH_STRESS"})
                del buffer
                torch.cuda.empty_cache()
            a = torch.arange(64, dtype=torch.float64).reshape(8, 8) / 31
            reference = (a @ a.T).numpy()
            actual = (a.float().cuda() @ a.float().cuda().T).cpu().numpy()
            error = float(np.max(np.abs(actual - reference)))
            assert error < 1e-4
            report["checks"].append({"stage": "independent_FP64_matmul_reference", "max_abs_error": error, "tolerance": 1e-4})
            config = Qwen3Config(vocab_size=64, hidden_size=64, intermediate_size=128, num_hidden_layers=1, num_attention_heads=4, num_key_value_heads=2, head_dim=16, max_position_embeddings=128)
            model = get_peft_model(Qwen3ForCausalLM(config).to("cuda", dtype=torch.bfloat16), LoraConfig(r=8, lora_alpha=16, target_modules=["q_proj", "v_proj"], task_type="CAUSAL_LM"), autocast_adapter_dtype=False)
            optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-3)
            tokens = torch.arange(2, 34, device="cuda").reshape(1, 32)
            loss = model(input_ids=tokens, labels=tokens).loss
            loss.backward()
            assert torch.isfinite(loss) and all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters())
            optimizer.step()
            model.eval()
            with torch.no_grad():
                original = model(tokens).logits.float().cpu()
            checkpoint = study.directory / "tiny_adapter"
            model.save_pretrained(checkpoint)
            # This fixture intentionally uses BF16 adapters on both sides.
            # Default reload downcasts FP32-trained adapter weights into the
            # BF16 base before upcasting, losing checkpoint precision.
            # FP32-adapter production checkpoints need a separate qualifier.
            model.load_adapter(checkpoint, adapter_name="reload", autocast_adapter_dtype=False)
            model.set_adapter("reload")
            # Newly inserted modules inherit their construction training mode,
            # not necessarily the already-evaluating parent's mode.
            model.eval()
            for name, parameter in model.named_parameters():
                if ".default." in name:
                    reloaded = dict(model.named_parameters())[name.replace(".default.", ".reload.")]
                    torch.testing.assert_close(parameter, reloaded, atol=0, rtol=0)
            with torch.no_grad():
                replay = model(tokens).logits.float().cpu()
            torch.testing.assert_close(original, replay, atol=0, rtol=0)
            report["checks"].append({"stage": "actual_Qwen3_tiny_LoRA_BF16_update_reload", "adapter_dtype": "bfloat16 explicit; FP32 adapter reload NOT qualified", "loss": float(loss.detach().cpu()), "status": "PASSED; not pretrained-model training"})
            del model, optimizer, tokens, loss
            torch.cuda.empty_cache()
            import xgboost as xgb
            generator = np.random.default_rng(11)
            x = generator.normal(size=(256, 8)).astype(np.float32)
            y = (x[:, 0] + x[:, 1] > 0).astype(np.float32)
            model = xgb.XGBClassifier(n_estimators=5, max_depth=2, tree_method="hist", device="cuda", random_state=11, n_jobs=2).fit(x, y)
            assert np.isfinite(model.predict_proba(x)).all()
            report["checks"].append({"stage": "actual_XGBoost_CUDA_fixture", "trees": 5, "status": "PASSED"})
            report["peak_cuda_allocated_bytes"] = torch.cuda.max_memory_allocated()
            report["peak_cuda_reserved_bytes"] = torch.cuda.max_memory_reserved()
            report["telemetry"].append(telemetry())
            if report["telemetry"][-1]["temperature_c"] >= device_target:
                raise ValueError("Qualification reached reported operating target")
        report.update(status="BOUNDED_GPU_CORE_QUALIFIED", GPU_QUALIFIED=True)
    except Exception as error:
        report.update(status="BLOCKED_HARDWARE_OR_ENVIRONMENT", diagnostic={"type": type(error).__name__, "message": str(error)[:800]})
    report["wall_seconds"] = time.perf_counter() - start
    report["peak_process_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report["packages"] = sorted(f"{distribution.metadata['Name']}=={distribution.version}" for distribution in importlib.metadata.distributions())
    atomic_json(study.directory / "qualification.json", report)
    export = ROOT / "reports/environment" / (study.name + ".json")
    atomic_json(export, report)
    atomic_json(ROOT / "reports/environment/GPU_QUALIFICATION.json", report | {"artifact": str(export), "artifact_sha256": digest(export)})
    if report["GPU_QUALIFIED"]:
        atomic_json(ROOT / "reports/environment/ENVIRONMENT_LOCK.json", {"packages": report["packages"], "python": sys.version, "qualified_scope": report["qualification_scope"], "qualification_sha256": digest(export)})
    state = study.ledger.read()
    previous = state["nodes"]["E00"]
    study.ledger.update("E00", "EXECUTED", artifacts=tuple(Path(item["path"]) for item in previous["artifacts"]) + (export,), reason="Current inventory plus bounded GPU qualification; read artifact scope/limitations", capabilities={"GPU_QUALIFIED": report["GPU_QUALIFIED"]})
    study.export_state()
    print(json.dumps({"status": report["status"], "artifact": str(export)}))
    return 0 if report["GPU_QUALIFIED"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
