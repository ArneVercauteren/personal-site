"""Tests for the open-strategy updater entry point."""

from __future__ import annotations

import json

import pytest

from paper_trading import update


def _write_spec(directory, strategy_id: str) -> None:
    payload = {
        "id": strategy_id,
        "name": strategy_id,
        "visibility": "open",
        "deployed_on": "2026-01-02",
        "portfolio_size": 100_000,
        "base_currency": "USD",
        "rebalance_cadence_days": 42,
        "rebalance_cadence_unit": "trading_days",
        "cost_model": {"commission_bps": 1.0, "slippage_bps": 5.0},
        "formula": {"kind": "number", "value": 1.0},
    }
    (directory / f"{strategy_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_load_strategy_specs_can_filter_to_one_open_strategy(tmp_path, monkeypatch):
    _write_spec(tmp_path, "gen0194")
    _write_spec(tmp_path, "open_momentum_v1")
    monkeypatch.setattr(update, "STRATEGY_DIR", tmp_path)

    specs = update.load_strategy_specs({"gen0194"})

    assert [s["id"] for s in specs] == ["gen0194"]


def test_load_strategy_specs_rejects_unknown_filter_id(tmp_path, monkeypatch):
    _write_spec(tmp_path, "gen0194")
    monkeypatch.setattr(update, "STRATEGY_DIR", tmp_path)

    with pytest.raises(ValueError, match="unknown open strategy"):
        update.load_strategy_specs({"missing"})


def test_split_strategy_ids_accepts_cli_and_env(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING_STRATEGIES", "env_a, env_b")
    monkeypatch.delenv("PAPER_TRADING_STRATEGY", raising=False)

    assert update._split_strategy_ids(["cli_a,cli_b", "cli_c"]) == {
        "cli_a",
        "cli_b",
        "cli_c",
        "env_a",
        "env_b",
    }
