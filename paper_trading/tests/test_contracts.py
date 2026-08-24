from __future__ import annotations

import pytest

from paper_trading.contracts import ContractError, content_hash, validate_equity_curve, validate_strategy_spec


def _spec():
    return {
        "id": "open_v1", "name": "Open", "visibility": "open",
        "deployed_on": "2026-01-02", "portfolio_size": 100_000,
        "base_currency": "USD", "rebalance_cadence_days": 42,
        "rebalance_cadence_unit": "trading_days",
        "cost_model": {"commission_bps": 1.0, "slippage_bps": 5.0},
        "formula": {"kind": "number", "value": 1.0},
    }


def test_strategy_contract_accepts_explicit_open_spec():
    assert validate_strategy_spec(_spec())["id"] == "open_v1"


def test_strategy_contract_rejects_anchor_on_calendar_cadence():
    spec = _spec()
    spec["rebalance_cadence_unit"] = "calendar_days"
    spec["rebalance_transition_anchor"] = "2026-01-02"
    with pytest.raises(ContractError, match="requires trading_days"):
        validate_strategy_spec(spec)


def test_equity_contract_rejects_rewritten_date_order():
    with pytest.raises(ContractError, match="strictly increasing"):
        validate_equity_curve([{"d": "2026-01-03", "v": 1}, {"d": "2026-01-02", "v": 2}])


def test_content_hash_is_key_order_independent():
    assert content_hash({"a": 1, "b": 2}) == content_hash({"b": 2, "a": 1})

