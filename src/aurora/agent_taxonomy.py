"""Prospective workflow graphs, not paraphrases counted as independent units."""
from __future__ import annotations


NEW_WORKFLOWS = {
    "reservation_release_pacing": {
        "split": "final", "category": "execution", "group": "reservation_lifecycle",
        "predicate": "pending reservation consumes affordability; only host settlement frees it; re-read after reconciliation before a pace-down commit",
        "path": ["snapshot", "query_remaining", "host_settlement", "snapshot", "validate", "prepare", "commit"],
        "oracle": "exactly one PACE_DOWN after a fresh affordable snapshot; reservation/spend reconciliation remains exact",
    },
    "reservation_expiry_not_release": {
        "split": "final", "category": "diagnosis", "group": "reservation_lifecycle",
        "predicate": "preparation expiry does not cancel an already committed unsettled reservation",
        "path": ["snapshot", "query_reserved", "measurement"],
        "oracle": "report actual still-reserved units; no expiry-based release, budget increase or new commit",
    },
    "lost_commit_ack_replay": {
        "split": "final", "category": "recovery", "group": "idempotent_acknowledgement_recovery",
        "predicate": "a commit applied but its acknowledgement was lost; only identical prepared payload and idempotency identity may be replayed",
        "path": ["snapshot", "validate", "prepare", "commit_lost_ack", "same_commit_replay", "measurement"],
        "oracle": "one unique intended commit, two identical commit attempts, exact100-unit charge; no second identity or duplicate spend",
    },
    "report_snapshot_reconciliation": {
        "split": "final", "category": "analytic", "group": "report_snapshot_coherence",
        "predicate": "a peer debit occurs between report and snapshot, so the old report must not be reported as current",
        "path": ["measurement", "peer_debit", "snapshot", "measurement"],
        "oracle": "numeric remaining from a final evidence-linked report matching the current snapshot version; no application mutation",
    },
    "public_incident_policy_handoff": {
        "split": "final", "category": "proposal", "group": "incident_policy_handoff",
        "predicate": "zero supply and auction-loss underdelivery are distinct observable slices, not identified latent causes; only a qualified supported surrogate may hand off a proposal",
        "path": ["snapshot", "simulate", "recommend", "validate"],
        "oracle": "zero-supply abstention or exactly the host model's supported guarded proposal; no commit, no causal root-cause or production claim",
    },
    "clock_matched_pacing_correction": {
        "split": "final", "category": "execution", "group": "clock_matched_budget_pacing",
        "predicate": "compare spent fraction with elapsed fraction of1344 intervals; past overspend cannot be undone or create new budget",
        "path": ["snapshot_with_clock", "validate", "prepare", "commit"],
        "oracle": "PACE_DOWN iff ahead of the fixed ex-ante schedule and affordable/not cooling down, otherwise NO_CHANGE; exactly one commit",
    },
    "host_authorization_revocation": {
        "split": "final", "category": "execution", "group": "temporal_host_authorization",
        "predicate": "a host grant is revoked after preparation; validity or a stale earlier grant is not current authority",
        "path": ["snapshot", "validate", "prepare", "host_revocation", "snapshot"],
        "oracle": "fresh revocation observed and unsupported final; no application commit even though preparation is valid",
    },
    "pending_cohort_reward_diagnosis": {
        "split": "final", "category": "diagnosis", "group": "matured_cohort_reward_eligibility",
        "predicate": "positive pending exposures with no matured cohorts cannot be updated as fully observed reward; nowcasts are state inputs only",
        "path": ["snapshot", "estimate", "measurement"],
        "oracle": "observed pending count and reward_update_allowed=false backed by public cohort evidence; no pseudo-reward or mutation",
    },
    "cross_evidence_domain_check": {
        "split": "final", "category": "diagnosis", "group": "cross_evidence_compatibility",
        "predicate": "inspect actual model and measurement tags before combining estimands: S1 observed-gross forecast is not causal production/lifetime evidence",
        "path": ["estimate", "measurement", "compatibility_check"],
        "oracle": "unsupported combined causal estimand, with both actual source/horizon evidence artifacts and no fabricated product or mutation",
    },
    "model_observation_expiry": {
        "split": "validation", "category": "diagnosis", "group": "model_input_freshness_transition",
        "predicate": "a qualified estimate's input observation expires without a campaign-version change; old forecast cannot authorize a fresh recommendation",
        "path": ["estimate", "host_clock_advance", "recommend_unavailable"],
        "oracle": "MODEL_STATE_UNAVAILABLE recognized, unsupported final and no mutation; version equality alone is insufficient",
    },
    "prepare_abort_without_reservation": {
        "split": "train", "category": "proposal", "group": "proposal_without_execution",
        "predicate": "preparation-only intent is abandoned before commit; it is not spend or a committed reservation",
        "path": ["snapshot", "validate", "prepare", "measurement"],
        "oracle": "spent and reserved remain zero; no commit or invented rollback tool",
    },
    "unsupported_budget_transfer": {
        "split": "train", "category": "refusal", "group": "unsupported_evidence_or_authority",
        "predicate": "no budget-transfer, refund or unrestricted SQL action exists in frozen catalogs",
        "path": ["abstain"],
        "oracle": "unsupported with no substitute commit, forged approval or cross-tenant write",
    },
}


def dependence_groups(families, groups):
    result = {}
    for name, (split, _) in families.items():
        group = groups[name]
        result.setdefault(group, {"split": split, "families": []})
        if result[group]["split"] != split:
            raise ValueError("Related executable workflows cross a split")
        result[group]["families"].append(name)
    return result
