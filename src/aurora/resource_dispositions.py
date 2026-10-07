"""Terminal resource dispositions, not inference from failed semantic outcomes."""
from __future__ import annotations


def blocked_track_plan(state: dict, exhausted: dict) -> dict:
    if state["capabilities"].get("CURRENT_HEAVY_GPU_MONITOR_QUALIFIED") is not False:
        raise ValueError("Canonical current resource hold required")
    if exhausted["status"] != "ORIGINAL_SFT_INFERENCE_PROFILES_EXHAUSTED" or exhausted["qualification_passed"] or not exhausted["no_final_semantic_outcomes_loaded"]:
        raise ValueError("Verified resource-only exhaustion required; semantic failures are not hardware blockers")
    if [row["duty_pause_seconds"] for row in exhausted["attempts"]] != [5., 10., 30.]:
        raise ValueError("All original prospective duty profiles must be preserved")
    reasons = {
        "E03": "CPU prior/logistic/finite-H feedback-shift/value development executed; parametric D3 failed convergence. Required actual CUDA delay/prediction ladder cannot run under the current monitoring hold; no CPU neural substitution or post-result convergence rescue.",
        "E15_R3_FREEZE": "R3 is admitted, not source-blocked. Required GPU model ladder is unqualified; complete primary development selection cannot be frozen from partial CPU results.",
        "E15_R3": "No primary R3 freeze exists; no final R3 outcomes loaded or scored. Hardware-blocked development prevents frozen confirmation, not a measured null result.",
        "E10": "SFT/DPO/IPO training and restart compatibility preserved. All original SFT inference duty profiles failed resource qualification; common four-arm duty and executable development comparison unavailable. DPO/IPO inference unattempted; no semantic model failure invented.",
        "E13_AGENT": "Required four-arm development scoring unavailable under the hardware/monitor hold. No primary taxonomy repair, extra duty candidate or semantic ablation outcomes manufactured.",
        "E15_AGENT_FREEZE": "No trained finalist can be selected without qualified development comparison. Nine frozen dependence groups retained; prospective power UNDERPOWERED; no fabricated finalist/freeze.",
        "E15_AGENT": "No agent finalist freeze exists; final semantic groups remain unscored. Prospective nine-group power remains UNDERPOWERED separately from this execution blocker.",
        "E12": "Frozen 2x2 design requires prompt reference and development-selected trained agent. No trained agent finalist is qualified; do not omit MSCP cells, pick by training loss or substitute a scripted oracle.",
        "E15_INTEGRATION": "No E12 decomposition or agent freeze exists. Policy freeze alone does not qualify untouched integration; no invented 2x2 results.",
    }
    for node in reasons:
        if state["nodes"][node]["execution_status"] in {"EXECUTED", "RUNNING"}:
            raise ValueError("Cannot overwrite executed/active evidence: " + node)
    return {node: {"execution_status": "BLOCKED_HARDWARE", "scientific_outcome": "BLOCKED_HARDWARE", "reason": reason}
            for node, reason in reasons.items()}
