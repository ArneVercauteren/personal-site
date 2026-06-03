"""Tests for the secured-strategy sanitizer (Tier 2a boundary).

These pin the security boundary: a secured entry must carry aggregate exposure
only and can never expose ticker weights or a formula. See
docs/concepts/open-vs-secured-strategies.md and docs/concepts/data-contract.md.
"""

from __future__ import annotations

import pytest

from paper_trading.secured import (
    OTHER_GROUP,
    SecuredLeakError,
    advance_next_rebalance,
    aggregate_exposure,
    assert_sanitized,
    build_secured_entry,
    is_rebalance_due,
    load_sector_map,
)

SECTOR_MAP = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "JPM": "Financials",
    "XOM": "Energy",
}


# --- aggregate_exposure ----------------------------------------------------

def test_aggregate_sums_weights_per_group():
    positions = [
        {"ticker": "AAPL", "weight": 0.30},
        {"ticker": "MSFT", "weight": 0.20},
        {"ticker": "JPM", "weight": 0.50},
    ]
    exp = aggregate_exposure(positions, SECTOR_MAP, include_cash=False)
    # Fully invested → groups sum to 1.0, no Cash slice.
    assert exp == [
        {"group": "Technology", "weight": 0.50},
        {"group": "Financials", "weight": 0.50},
    ]


def test_aggregate_drops_tickers_entirely():
    positions = [{"ticker": "AAPL", "weight": 0.4}]
    exp = aggregate_exposure(positions, SECTOR_MAP)
    # No object anywhere may carry a ticker key.
    assert all("ticker" not in slice_ for slice_ in exp)
    assert all(slice_["group"] not in SECTOR_MAP for slice_ in exp if slice_["group"] != "Cash")


def test_aggregate_adds_cash_residual():
    positions = [
        {"ticker": "AAPL", "weight": 0.30},
        {"ticker": "JPM", "weight": 0.30},
    ]
    exp = aggregate_exposure(positions, SECTOR_MAP, include_cash=True)
    groups = {s["group"]: s["weight"] for s in exp}
    assert groups["Cash"] == pytest.approx(0.40)
    assert sum(s["weight"] for s in exp) == pytest.approx(1.0)


def test_aggregate_sorted_descending():
    positions = [
        {"ticker": "AAPL", "weight": 0.10},
        {"ticker": "JPM", "weight": 0.50},
        {"ticker": "XOM", "weight": 0.20},
    ]
    exp = aggregate_exposure(positions, SECTOR_MAP, include_cash=False)
    weights = [s["weight"] for s in exp]
    assert weights == sorted(weights, reverse=True)


def test_aggregate_unmapped_ticker_buckets_to_other():
    positions = [
        {"ticker": "AAPL", "weight": 0.6},
        {"ticker": "TSLA", "weight": 0.4},  # not in SECTOR_MAP
    ]
    exp = aggregate_exposure(positions, SECTOR_MAP, include_cash=False)
    groups = {s["group"]: s["weight"] for s in exp}
    assert groups[OTHER_GROUP] == pytest.approx(0.4)
    assert groups["Technology"] == pytest.approx(0.6)


def test_default_sector_map_loads_and_is_used():
    m = load_sector_map()
    assert isinstance(m, dict) and len(m) > 1000
    # AAPL is Information Technology in the SEC-derived map.
    assert m["AAPL"] == "Information Technology"
    # With no sector_map argument, the bundled map is used.
    exp = aggregate_exposure([{"ticker": "AAPL", "weight": 1.0}], include_cash=False)
    assert exp == [{"group": "Information Technology", "weight": 1.0}]


def test_aggregate_min_weight_drops_dust():
    positions = [
        {"ticker": "AAPL", "weight": 0.95},
        {"ticker": "JPM", "weight": 0.005},
    ]
    exp = aggregate_exposure(positions, SECTOR_MAP, include_cash=False, min_weight=0.01)
    assert [s["group"] for s in exp] == ["Technology"]


# --- assert_sanitized ------------------------------------------------------

def _valid_entry():
    return {
        "id": "balanced_king_v3",
        "name": "Balanced King",
        "visibility": "secured",
        "equity_curve": [{"d": "2026-01-02", "v": 100000.0}],
        "stats": {"cagr": 0.09, "sharpe": 0.7, "max_dd": -0.05},
        "exposure": [{"group": "Technology", "weight": 0.6}, {"group": "Cash", "weight": 0.4}],
    }


def test_assert_sanitized_passes_valid_entry():
    assert assert_sanitized(_valid_entry(), sector_map=SECTOR_MAP) is not None


@pytest.mark.parametrize("field", ["positions", "formula", "formula_ref"])
def test_assert_sanitized_rejects_leaked_field(field):
    entry = _valid_entry()
    entry[field] = [{"ticker": "AAPL", "weight": 0.4}] if field == "positions" else "secret"
    with pytest.raises(SecuredLeakError, match=field):
        assert_sanitized(entry)


def test_assert_sanitized_rejects_open_visibility():
    entry = _valid_entry()
    entry["visibility"] = "open"
    with pytest.raises(SecuredLeakError):
        assert_sanitized(entry)


def test_assert_sanitized_rejects_empty_exposure():
    entry = _valid_entry()
    entry["exposure"] = []
    with pytest.raises(SecuredLeakError):
        assert_sanitized(entry)


def test_assert_sanitized_rejects_ticker_group():
    entry = _valid_entry()
    entry["exposure"] = [{"group": "AAPL", "weight": 1.0}]
    with pytest.raises(SecuredLeakError):
        assert_sanitized(entry, sector_map=SECTOR_MAP)


# --- build_secured_entry ---------------------------------------------------

class _FakeSim:
    equity_curve = [{"d": "2026-01-02", "v": 100000.0}, {"d": "2026-02-02", "v": 101000.0}]
    stats = {"cagr": 0.09, "sharpe": 0.7, "max_dd": -0.05}
    positions = [
        {"ticker": "AAPL", "weight": 0.30},
        {"ticker": "MSFT", "weight": 0.20},
        {"ticker": "JPM", "weight": 0.25},
    ]


def test_build_secured_entry_shape_and_no_leak():
    spec = {"id": "balanced_king_v3", "name": "Balanced King"}
    entry = build_secured_entry(_FakeSim(), spec, SECTOR_MAP)
    assert entry["visibility"] == "secured"
    assert set(entry) == {"id", "name", "visibility", "equity_curve", "stats", "exposure"}
    # No ticker-level data survived anywhere.
    assert "positions" not in entry
    assert all("ticker" not in s for s in entry["exposure"])
    groups = {s["group"]: s["weight"] for s in entry["exposure"]}
    assert groups["Technology"] == pytest.approx(0.50)
    assert groups["Financials"] == pytest.approx(0.25)
    assert groups["Cash"] == pytest.approx(0.25)


def test_build_secured_entry_passes_through_split_stats():
    """Backfill split-stats + live marker are aggregate-safe and flow through."""
    sim = {
        "equity_curve": _FakeSim.equity_curve,
        "stats": _FakeSim.stats,
        "stats_backtest": {"cagr": 0.05, "sharpe": 0.40, "max_dd": -0.20},
        "stats_live": {"cagr": 0.12, "sharpe": 0.90, "max_dd": -0.03},
        "positions": _FakeSim.positions,
    }
    spec = {"id": "k", "name": "K", "deployed_on": "2026-01-02"}
    entry = build_secured_entry(sim, spec, SECTOR_MAP)
    assert entry["live_since"] == "2026-01-02"
    assert entry["stats_live"]["cagr"] == 0.12
    assert entry["stats_backtest"]["max_dd"] == -0.20
    # Still no ticker-level leak alongside the new fields.
    assert "positions" not in entry


def test_build_secured_entry_omits_split_stats_when_absent():
    """No live marker / split stats unless the writer provides them."""
    spec = {"id": "balanced_king_v3", "name": "Balanced King"}
    entry = build_secured_entry(_FakeSim(), spec, SECTOR_MAP)
    assert "live_since" not in entry
    assert "stats_live" not in entry
    assert "stats_backtest" not in entry


def test_build_secured_entry_accepts_dict_sim():
    sim = {
        "equity_curve": _FakeSim.equity_curve,
        "stats": _FakeSim.stats,
        "positions": [{"ticker": "AAPL", "weight": 1.0}],
    }
    spec = {"id": "k", "name": "K"}
    entry = build_secured_entry(sim, spec, SECTOR_MAP)
    assert entry["exposure"] == [{"group": "Technology", "weight": 1.0}]


# --- cadence helpers -------------------------------------------------------

def test_is_rebalance_due():
    assert is_rebalance_due("2026-06-01", "2026-06-01") is True
    assert is_rebalance_due("2026-06-01", "2026-06-02") is True
    assert is_rebalance_due("2026-06-01", "2026-05-31") is False


def test_advance_next_rebalance_single_step():
    assert advance_next_rebalance("2026-06-01", 42, "2026-06-01") == "2026-07-13"


def test_advance_next_rebalance_catches_up_missed_runs():
    # next was long ago; advancing by 30-day steps lands on the first future date.
    out = advance_next_rebalance("2026-01-01", 30, "2026-06-02")
    assert out == "2026-06-30"


def test_advance_keeps_cadence_phase():
    # Two consecutive advances stay exactly cadence_days apart.
    first = advance_next_rebalance("2026-06-01", 42, "2026-06-01")
    second = advance_next_rebalance(first, 42, first)
    import pandas as pd
    assert (pd.Timestamp(second) - pd.Timestamp(first)).days == 42
