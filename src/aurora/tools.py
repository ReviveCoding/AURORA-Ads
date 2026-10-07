"""Nine bounded application interfaces. Missing models return explicit unavailability."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .artifacts import immutable_json
from .state import Action, ActionRequest, StateHost, hash_payload


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    campaign: str = Field(min_length=1)


class MetricArguments(Arguments):
    metric: Literal["spent", "reserved", "remaining", "initial_budget"]


class ActionArguments(Arguments):
    snapshot_version: int = Field(ge=0)
    action: Literal["NO_CHANGE", "BID_MULTIPLIER_DOWN", "BID_MULTIPLIER_UP", "PACE_DOWN", "PACE_UP", "PAUSE_SEGMENT"]


class CommitArguments(ActionArguments):
    prepared_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_domain: str
    snapshot_version: int
    unit: str
    horizon: str
    artifact_id: str
    permitted_use: str
    status: str
    data: dict


@dataclass(frozen=True)
class HostContext:
    tenant: str
    caller: str
    mock_pre_authorized: bool = False


CATALOG = {
    "get_campaign_snapshot": Arguments,
    "query_metrics": MetricArguments,
    "estimate_outcomes": Arguments,
    "simulate_policy": Arguments,
    "recommend_action": Arguments,
    "validate_action": ActionArguments,
    "prepare_action": ActionArguments,
    "commit_mock_action": CommitArguments,
    "build_measurement_report": Arguments,
}


class ToolHost:
    def __init__(self, state: StateHost, context: HostContext, artifacts: Path, *, models=None, model_artifact: str | None = None):
        self.state = state
        self.context = context
        self.artifacts = artifacts
        self.models = models
        self.model_artifact = model_artifact

    def request(self, args: ActionArguments) -> ActionRequest:
        # Economic amounts come from the deterministic S1 operational-cost rule,
        # never from model-generated numeric quantities. This tool is local mock
        # control only; auctions have separate maximum-bid reservations.
        action = Action(args.action)
        overhead_units = 0 if action == Action.NO_CHANGE else 100
        evidence = hash_payload({"domain": "S1_MOCK", "campaign": args.campaign, "snapshot_version": args.snapshot_version, "action": action.value, "overhead_units": overhead_units})
        return ActionRequest(self.context.tenant, args.campaign, self.context.caller, args.snapshot_version, action, overhead_units, evidence)

    def call(self, name: str, payload: dict) -> ToolResult:
        if name not in CATALOG:
            raise ValueError("Unknown/forbidden tool")
        args = CATALOG[name].model_validate(payload)
        snapshot = self.state.snapshot(self.context.tenant, args.campaign)
        status = "OK"
        domain = "S1_MOCK"
        unit = "synthetic cost units; integers scaled by10000"
        horizon = "current local snapshot; action duration15min"
        permitted = "local authorized mock workflow only; not simulator truth or production evidence"
        if name == "get_campaign_snapshot":
            data = dict(snapshot)
            data["execution_authorization"] = {"mock_pre_authorized": self.context.mock_pre_authorized, "scope": "MOCK_ONLY", "source": "host context, not user/model assertion"}
            from .state import Conflict
            try:
                public = self.state.public_observation(self.context.tenant, args.campaign, snapshot["version"])
            except Conflict:
                data["public_outcome_state_status"] = "UNAVAILABLE_OR_STALE"
            else:
                data["public_outcome_state_status"] = "FRESH_VERSION_MATCHED"
                data["public_outcome_state"] = asdict(public)
        elif name == "query_metrics":
            metric = args.metric
            catalog = {"spent": snapshot["spent"], "reserved": snapshot["reserved"], "remaining": snapshot["budget"] - snapshot["spent"] - snapshot["reserved"], "initial_budget": snapshot["budget"]}
            data = {"metric": metric, "value_units_1e4": catalog[metric], "denominator": "one local synthetic campaign"}
        elif name in {"estimate_outcomes", "simulate_policy", "recommend_action"}:
            if self.models is None:
                status = "MODEL_NOT_QUALIFIED"
                data = {"reason": "No admitted, qualified predictive/policy model is registered. Counterfactual truth is evaluator-only.", "estimate": None}
            else:
                from .state import Conflict
                try:
                    public = self.state.public_observation(self.context.tenant, args.campaign, snapshot["version"])
                except Conflict:
                    status = "MODEL_STATE_UNAVAILABLE"
                    data = {"reason": "Hash-verified public S1 observation must match version and freshness; no invented feature fallback", "estimate": None}
                else:
                    import numpy as np
                    gross, spend, uncertainty, support, _ = self.models.estimates(public)
                    if not all(np.isfinite(value).all() for value in (gross, spend, uncertainty)):
                        raise ValueError("Nonfinite registered economic estimate")
                    domain = "S1_OBSERVED_MATURED"
                    unit = "synthetic cost units (not units1e4)"
                    horizon = "next15min origin interval; recorded exposed purchase value by7days plus declared receipt maturity"
                    permitted = "shadow/local observed-gross forecast; not incremental effect or adaptive full-episode certification"
                    status = "QUALIFIED_SURROGATE_NOT_CONFIRMED_POLICY"
                    rows = [{"action": action.value, "expected_observed_gross": float(gross[i]), "expected_spend": float(spend[i]), "heuristic_uncertainty": float(uncertainty[i]), "local_support_count": int(support[i])} for i, action in enumerate(Action)]
                    data = {"model_artifact": self.model_artifact, "action_estimates": rows, "estimand": "recorded exposed purchase value; not causal incremental value", "support_and_uncertainty_not_confidence_certificate": True}
                    if name == "recommend_action":
                        score = gross - spend - uncertainty * .5 - np.array([0., .01, .01, .01, .01, .01])
                        default = score[0]
                        score[support < 2] = -np.inf
                        score[0] = default
                        for i, action in enumerate(Action):
                            try:
                                self.state.validate(self.request(ActionArguments(campaign=args.campaign, snapshot_version=snapshot["version"], action=action.value)), snapshot)
                            except Conflict:
                                score[i] = -np.inf
                        data.update(action=tuple(Action)[int(np.argmax(score))].value, authorization="NOT_GRANTED_BY_RECOMMENDATION", recipe="provisional observed-only support-gated shadow recommendation; final adaptive policy unconfirmed")
                    if name == "simulate_policy":
                        data["simulation_scope"] = "one-interval learned surrogate, not structural oracle truth or full adaptive rollout"
        elif name == "validate_action":
            request = self.request(args)
            self.state.validate(request, snapshot)
            data = {"valid": True, "canonical_action": request.payload(), "authorization": "NOT_GRANTED_BY_VALIDATION"}
        elif name == "prepare_action":
            request = self.request(args)
            prepared = self.state.prepare(request)
            data = {"prepared_id": prepared, "canonical_action": request.payload(), "authorization": "HOST_REQUIRED", "duration_seconds": 900}
        elif name == "commit_mock_action":
            if not self.context.mock_pre_authorized:
                raise ValueError("Host MOCK_ONLY preauthorization is required")
            request = self.request(args)
            # Authorization is issued inside the host and never enters observations.
            # Replays after a completed commit work without issuing a fresh expired
            # approval; the committed row still binds caller+tenant+payload.
            existing_connection = self.state.connect()
            try:
                existing = existing_connection.execute("SELECT prepared_id FROM committed WHERE tenant=? AND caller=? AND idempotency_key=?", (self.context.tenant, self.context.caller, args.idempotency_key)).fetchone()
            finally:
                existing_connection.close()
            token = "replay-only" if existing else self.state.issue_mock_authorization(args.prepared_id, self.context.tenant, self.context.caller)
            self.state.commit(args.prepared_id, request, args.idempotency_key, token)
            data = self.state.settle(self.context.tenant, self.context.caller, args.idempotency_key, request.max_spend_units)
            snapshot = self.state.snapshot(self.context.tenant, args.campaign)
        else:
            data = {"metrics": {"spent_units_1e4": snapshot["spent"], "reserved_units_1e4": snapshot["reserved"], "remaining_units_1e4": snapshot["budget"] - snapshot["spent"] - snapshot["reserved"]}, "unsupported_claims": ["production impact", "incremental lift", "model superiority"], "integrity": self.state.verify()}
        record = {"tool": name, "status": status, "evidence_domain": domain, "snapshot_version": snapshot["version"], "data": data}
        artifact = immutable_json(self.artifacts, record)
        return ToolResult(evidence_domain=domain, snapshot_version=snapshot["version"], unit=unit, horizon=horizon, artifact_id=artifact.stem, permitted_use=permitted, status=status, data=data)
