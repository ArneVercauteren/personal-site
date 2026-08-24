from __future__ import annotations

import pytest

from paper_trading.contracts import ContractError, content_hash, validate_equity_curve, validate_strategy_spec
from paper_trading.deployment import deployment_bundle_hash


def _spec():
    spec = {
        "schema_version": 1,
        "id": "open_v1", "name": "Open", "visibility": "open",
        "deployed_on": "2026-01-02", "portfolio_size": 100_000,
        "base_currency": "USD", "rebalance_cadence_days": 42,
        "rebalance_cadence_unit": "trading_days",
        "rebalance_transition_anchor": "2026-01-02",
        "cost_model": {
            "commission_bps": 1.0, "slippage_bps": 5.0,
            "spread_ref_price": 50.0, "volume_impact_coef": 0.5,
            "impact_portfolio_size": 1_000_000.0, "execution_max_days": 3,
            "execution_participation_rate": 0.01, "execution_delay_risk_coef": 0.25,
            "execution_overflow_penalty_bps": 500.0, "vol_scaled_cost_enable": True,
            "vol_cost_k": 0.75, "vol_cost_realized_window": 63,
            "vol_cost_long_window": 252, "vol_cost_mult_max": 3.0,
        },
        "formula": {"kind": "number", "value": 1.0},
    }
    spec["deployment"] = {
        "schema_version": 1, "strategy_id": spec["id"], "display_name": spec["name"],
        "formula_hash": content_hash(spec["formula"]),
        "cost_model_hash": content_hash(spec["cost_model"]),
        "engine_build_id": "test-build", "evaluator_version": "darwin-dsl-v1",
        "cost_model_version": "darwin-sliced-execution-v1",
        "calendar_version": "observed-us-sessions-v1",
        "eligibility_version": "causal-us-equities-v1", "training_cutoff": "2024-12-31",
        "oos_window": {"start": "2025-01-02", "end": "2025-12-31"},
        "deployment_session": spec["deployed_on"], "generated_at": "2026-01-02T00:00:00Z",
        "data_sources": {"research": "test", "forward_paper": "test"},
        "cadence": {
            "unit": "trading_sessions", "interval": 42,
            "anchor_review_session": "2026-01-02", "execution": "next_session_open",
        },
        "bundle_hash": "0" * 64,
    }
    spec["deployment"]["bundle_hash"] = deployment_bundle_hash(spec)
    return spec


def test_strategy_contract_accepts_explicit_open_spec():
    assert validate_strategy_spec(_spec())["id"] == "open_v1"


def test_strategy_contract_rejects_anchor_on_calendar_cadence():
    spec = _spec()
    spec["rebalance_cadence_unit"] = "calendar_days"
    spec["rebalance_transition_anchor"] = "2026-01-02"
    with pytest.raises(ContractError, match="requires trading_days"):
        validate_strategy_spec(spec)


def test_strategy_contract_rejects_unsupported_evaluator_version():
    spec = _spec()
    spec["deployment"]["evaluator_version"] = "darwin-dsl-v999"
    spec["deployment"]["bundle_hash"] = deployment_bundle_hash(spec)
    with pytest.raises(ContractError, match="unsupported evaluator"):
        validate_strategy_spec(spec)


def test_strategy_contract_rejects_bundle_tampering():
    spec = _spec()
    spec["formula"]["value"] = 2.0
    with pytest.raises(ContractError, match="formula hash"):
        validate_strategy_spec(spec)


def test_equity_contract_rejects_rewritten_date_order():
    with pytest.raises(ContractError, match="strictly increasing"):
        validate_equity_curve([{"d": "2026-01-03", "v": 1}, {"d": "2026-01-02", "v": 2}])


def test_content_hash_is_key_order_independent():
    assert content_hash({"a": 1, "b": 2}) == content_hash({"b": 2, "a": 1})
