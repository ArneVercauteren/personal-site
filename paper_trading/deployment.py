"""Versioned Darwin-to-paper deployment bundle contract.

The strategy JSON is the immutable deployment bundle.  Darwin writes it; this
module rejects missing or unsupported semantics before the updater can fetch
prices, advance a checkpoint, or publish data.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from .contracts import ContractError, content_hash, _finite, _require_date

DEPLOYMENT_SCHEMA_VERSION = 1
SUPPORTED_EVALUATOR_VERSIONS = {"darwin-dsl-v1"}
SUPPORTED_COST_MODEL_VERSIONS = {"darwin-sliced-execution-v1"}
SUPPORTED_CALENDAR_VERSIONS = {"observed-us-sessions-v1"}
SUPPORTED_ELIGIBILITY_VERSIONS = {"causal-us-equities-v1"}

REQUIRED_COST_PARAMETERS = {
    "commission_bps",
    "slippage_bps",
    "spread_ref_price",
    "volume_impact_coef",
    "impact_portfolio_size",
    "execution_max_days",
    "execution_participation_rate",
    "execution_delay_risk_coef",
    "execution_overflow_penalty_bps",
    "vol_scaled_cost_enable",
    "vol_cost_k",
    "vol_cost_realized_window",
    "vol_cost_long_window",
    "vol_cost_mult_max",
}


def deployment_bundle_hash(spec: dict[str, Any]) -> str:
    """Hash every bundle field except the self-referential bundle hash."""
    candidate = copy.deepcopy(spec)
    deployment = candidate.get("deployment")
    if isinstance(deployment, dict):
        deployment.pop("bundle_hash", None)
    candidate.pop("_universe_snapshot_id", None)
    return content_hash(candidate)


def _require_version(value: Any, supported: set[str], label: str) -> str:
    if not isinstance(value, str) or value not in supported:
        versions = ", ".join(sorted(supported))
        raise ContractError(f"unsupported {label}: {value!r}; supported: {versions}")
    return value


def validate_deployment_bundle(spec: dict[str, Any]) -> dict[str, Any]:
    if spec.get("schema_version") != DEPLOYMENT_SCHEMA_VERSION:
        raise ContractError("unsupported or missing deployment schema version")
    deployment = spec.get("deployment")
    if not isinstance(deployment, dict):
        raise ContractError("strategy is not a versioned deployment bundle")

    required = {
        "schema_version", "strategy_id", "display_name", "formula_hash",
        "cost_model_hash", "engine_build_id", "evaluator_version",
        "cost_model_version", "calendar_version", "eligibility_version",
        "training_cutoff", "oos_window", "deployment_session", "generated_at",
        "data_sources", "cadence", "bundle_hash",
    }
    missing = sorted(required - set(deployment))
    if missing:
        raise ContractError(f"deployment metadata missing: {', '.join(missing)}")
    if deployment["schema_version"] != DEPLOYMENT_SCHEMA_VERSION:
        raise ContractError("unsupported nested deployment schema version")
    if deployment["strategy_id"] != spec.get("id"):
        raise ContractError("deployment strategy_id does not match strategy id")
    if deployment["display_name"] != spec.get("name"):
        raise ContractError("deployment display_name does not match public name")
    if not isinstance(deployment["engine_build_id"], str) or not deployment["engine_build_id"].strip():
        raise ContractError("deployment engine_build_id is required")

    _require_version(
        deployment["evaluator_version"], SUPPORTED_EVALUATOR_VERSIONS, "evaluator version",
    )
    _require_version(
        deployment["cost_model_version"], SUPPORTED_COST_MODEL_VERSIONS, "cost-model version",
    )
    _require_version(
        deployment["calendar_version"], SUPPORTED_CALENDAR_VERSIONS, "calendar version",
    )
    _require_version(
        deployment["eligibility_version"], SUPPORTED_ELIGIBILITY_VERSIONS,
        "eligibility version",
    )

    formula = spec.get("formula")
    if not isinstance(formula, dict):
        raise ContractError("versioned Darwin deployments require a public formula object")
    if deployment["formula_hash"] != content_hash(formula):
        raise ContractError("deployment formula hash does not match formula")
    costs = spec.get("cost_model")
    if not isinstance(costs, dict):
        raise ContractError("deployment cost_model must be an object")
    missing_costs = sorted(REQUIRED_COST_PARAMETERS - set(costs))
    if missing_costs:
        raise ContractError(f"deployment cost model is incomplete: {', '.join(missing_costs)}")
    if deployment["cost_model_hash"] != content_hash(costs):
        raise ContractError("deployment cost-model hash does not match parameters")
    for key in REQUIRED_COST_PARAMETERS - {"vol_scaled_cost_enable"}:
        _finite(costs[key], f"cost_model.{key}")
    if not isinstance(costs["vol_scaled_cost_enable"], bool):
        raise ContractError("cost_model.vol_scaled_cost_enable must be boolean")
    if int(costs["execution_max_days"]) <= 0:
        raise ContractError("sliced execution requires execution_max_days > 0")
    participation = float(costs["execution_participation_rate"])
    if not 0 < participation <= 1:
        raise ContractError("execution participation rate must be in (0, 1]")

    cadence = deployment["cadence"]
    if not isinstance(cadence, dict):
        raise ContractError("deployment cadence must be an object")
    if cadence.get("unit") != "trading_sessions":
        raise ContractError("deployment cadence must use trading_sessions")
    if cadence.get("execution") != "next_session_open":
        raise ContractError("deployment execution must be next_session_open")
    if cadence.get("interval") != spec.get("rebalance_cadence_days"):
        raise ContractError("deployment cadence interval does not match strategy")
    if spec.get("rebalance_cadence_unit") != "trading_days":
        raise ContractError("versioned deployments require trading_days cadence")
    if cadence.get("anchor_review_session") != spec.get("rebalance_transition_anchor"):
        raise ContractError("deployment cadence anchor does not match strategy")
    _require_date(cadence.get("anchor_review_session"), "cadence.anchor_review_session")

    if deployment["deployment_session"] != spec.get("deployed_on"):
        raise ContractError("deployment session does not match deployed_on")
    _require_date(deployment["training_cutoff"], "deployment.training_cutoff")
    _require_date(deployment["deployment_session"], "deployment.deployment_session")
    oos = deployment["oos_window"]
    if not isinstance(oos, dict):
        raise ContractError("deployment oos_window must be an object")
    start = _require_date(oos.get("start"), "deployment.oos_window.start")
    end = _require_date(oos.get("end"), "deployment.oos_window.end")
    if end < start or deployment["training_cutoff"] >= start:
        raise ContractError("deployment training/OOS chronology is invalid")
    if not isinstance(deployment["generated_at"], str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", deployment["generated_at"]
    ):
        raise ContractError("deployment generated_at must be UTC ISO seconds")
    sources = deployment["data_sources"]
    if not isinstance(sources, dict) or not all(
        isinstance(sources.get(key), str) and sources[key].strip()
        for key in ("research", "forward_paper")
    ):
        raise ContractError("deployment must identify research and forward-paper data sources")

    if not re.fullmatch(r"[a-f0-9]{64}", str(deployment["bundle_hash"])):
        raise ContractError("deployment bundle_hash must be SHA-256")
    if deployment["bundle_hash"] != deployment_bundle_hash(spec):
        raise ContractError("deployment bundle hash does not match bundle content")
    return spec
