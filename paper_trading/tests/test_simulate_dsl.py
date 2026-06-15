"""Integration tests for the DSL simulation path and state injection."""

from __future__ import annotations

import logging

import pytest

from paper_trading import portfolio, prices, signals
from paper_trading.darwin_eval.select_on_date import select_tickers_on_date


def _spec(universe, formula):
    return {
        "id": "dsl_test",
        "name": "DSL test",
        "visibility": "open",
        "deployed_on": "2023-06-01",
        "portfolio_size": 100000,
        "base_currency": "USD",
        "rebalance_cadence_days": 30,
        "cost_model": {"commission_bps": 1.0, "slippage_bps": 5.0},
        "universe": universe,
        "formula": formula,
    }


def _roc_topn(top_n=4, window=40):
    return {"mode": "top_n", "top_n": top_n, "kind": "indicator", "name": "roc", "params": {"window": window}}


def test_simulate_runs_and_is_sane(universe, long_prices):
    opens, closes = prices.long_to_wide(long_prices)
    res = portfolio.simulate(_spec(universe, _roc_topn()), opens, closes, prices_long=long_prices)

    # Curve spans every bar from deployed_on to the last available date.
    sim_index = closes.loc["2023-06-01":].index
    assert len(res.equity_curve) == len(sim_index)
    assert res.as_of == sim_index[-1].strftime("%Y-%m-%d")
    # Dates are strictly increasing.
    dates = [p["d"] for p in res.equity_curve]
    assert dates == sorted(dates)
    # No leverage: held weights stay near 100% of the book (they drift above the
    # target sum between rebalances as winners grow, so allow modest slack).
    assert sum(p["weight"] for p in res.positions) <= 1.05
    assert all(0.0 < p["weight"] <= 1.0 for p in res.positions)
    for k in ("cagr", "sharpe", "max_dd"):
        assert k in res.stats


def test_simulate_is_deterministic(universe, long_prices):
    opens, closes = prices.long_to_wide(long_prices)
    spec = _spec(universe, _roc_topn())
    r1 = portfolio.simulate(spec, opens, closes, prices_long=long_prices)
    r2 = portfolio.simulate(spec, opens, closes, prices_long=long_prices)
    assert r1.equity_curve == r2.equity_curve
    assert r1.positions == r2.positions
    assert r1.stats == r2.stats
    assert r1.trades == r2.trades


def test_backfill_start_extends_curve_and_splits_stats(universe, long_prices):
    """`backfill_start` starts the curve before the live date and splits stats."""
    opens, closes = prices.long_to_wide(long_prices)
    spec = _spec(universe, _roc_topn())
    spec["deployed_on"] = "2024-06-01"   # live marker
    spec["backfill_start"] = "2022-06-01"  # one-time historical backfill
    res = portfolio.simulate(spec, opens, closes, prices_long=long_prices)

    # The curve starts at the backfill date, well before the live date.
    assert res.equity_curve[0]["d"] >= "2022-06-01"
    assert res.equity_curve[0]["d"] < "2024-06-01"

    # Both pre-live (backtest) and post-live (live) segments are well-formed.
    for seg in (res.stats_backtest, res.stats_live):
        assert set(seg) == {"cagr", "sharpe", "max_dd"}

    # The live window covers exactly the same trading days as a deployed-only run
    # from that date (backfill only adds earlier history, never changes the live
    # date grid).
    live_only = {k: v for k, v in spec.items() if k != "backfill_start"}
    res_live = portfolio.simulate(live_only, opens, closes, prices_long=long_prices)
    live_dates = [p["d"] for p in res.equity_curve if p["d"] >= "2024-06-01"]
    assert live_dates[0] == res_live.equity_curve[0]["d"]
    assert live_dates[-1] == res_live.equity_curve[-1]["d"]


def test_darwin_equity_curve_is_authoritative_prefix(universe, long_prices):
    opens, closes = prices.long_to_wide(long_prices)
    spec = _spec(universe, _roc_topn())
    available = closes.loc["2023-06-01":].index
    prefix_dates = available[:3]
    assert len(prefix_dates) == 3
    spec["deployed_on"] = available[10].strftime("%Y-%m-%d")
    spec["darwin_equity_curve"] = [
        {"d": prefix_dates[0].strftime("%Y-%m-%d"), "v": 100000.0},
        {"d": prefix_dates[1].strftime("%Y-%m-%d"), "v": 101000.0},
        {"d": prefix_dates[2].strftime("%Y-%m-%d"), "v": 102500.0},
    ]

    assert portfolio.simulation_curve_start(spec) == spec["darwin_equity_curve"][-1]["d"]
    res = portfolio.simulate(spec, opens, closes, prices_long=long_prices)

    assert res.equity_curve[:3] == spec["darwin_equity_curve"]
    dates = [p["d"] for p in res.equity_curve]
    assert dates == sorted(dates)
    assert len(dates) == len(set(dates))
    assert all(p["d"] > spec["darwin_equity_curve"][-1]["d"] for p in res.equity_curve[3:])
    assert res.stats_backtest["cagr"] != 0.0


def test_invested_book_cap_scales_targets_and_leaves_cash():
    """Capacity scales invested weights while trade dollars use the full book."""
    from paper_trading import costs

    capped = costs.CostModel.from_spec(
        {"commission_bps": 1.0, "slippage_bps": 5.0,
         "impact_portfolio_size": 1_000_000.0, "impact_book_cap": 2_000_000.0}
    )
    target = {"A": 0.6, "B": 0.4}
    assert portfolio._impact_account_book(capped, 150_000.0, 100_000.0) == pytest.approx(
        1_500_000.0
    )
    assert portfolio._cap_target_weights(target, capped, 150_000.0, 100_000.0) == target

    account_book = portfolio._impact_account_book(capped, 5_000_000.0, 100_000.0)
    scaled = portfolio._cap_target_weights(target, capped, 5_000_000.0, 100_000.0)
    assert sum(scaled.values()) * account_book == pytest.approx(2_000_000.0)

    uncapped = costs.CostModel.from_spec({"commission_bps": 1.0, "slippage_bps": 5.0})
    assert portfolio._cap_target_weights(target, uncapped, 5_000_000.0, 100_000.0) == target


def test_different_capacity_caps_change_cash_allocation(universe, long_prices):
    """Different invested-cap ceilings produce different cash allocations."""
    opens, closes = prices.long_to_wide(long_prices)
    raw_closes, dollar_volume = prices.wide_raw_and_dollar_volume(long_prices)
    available = closes.loc["2023-06-01":].index
    prefix = available[:3]
    base_spec = _spec(universe, _roc_topn())
    base_spec["deployed_on"] = available[10].strftime("%Y-%m-%d")
    # A prefix that compounds ~50x so both runs retain cash above capacity.
    base_spec["darwin_equity_curve"] = [
        {"d": prefix[0].strftime("%Y-%m-%d"), "v": 100_000.0},
        {"d": prefix[1].strftime("%Y-%m-%d"), "v": 3_000_000.0},
        {"d": prefix[2].strftime("%Y-%m-%d"), "v": 5_000_000.0},
    ]

    def run(cap: float):
        spec = {**base_spec, "cost_model": {
            "commission_bps": 1.0, "slippage_bps": 5.0,
            "volume_impact_coef": 0.5, "impact_portfolio_size": 1_000_000.0,
            "impact_book_cap": cap,
        }}
        return portfolio.simulate(
            spec, opens, closes, prices_long=long_prices,
            dollar_volume=dollar_volume, raw_closes=raw_closes,
        )

    low_cap = run(1_500_000.0)
    high_cap = run(10_000_000.0)
    # Same prefix; the lower cap leaves more cash and changes subsequent returns.
    assert low_cap.equity_curve[:3] == high_cap.equity_curve[:3]
    assert low_cap.equity_curve[-1]["v"] != high_cap.equity_curve[-1]["v"]


def test_darwin_prefix_continuation_survives_sparse_yahoo_ticker(universe, long_prices):
    """One sparse universe member must not erase the Yahoo continuation dates."""
    spec = _spec(universe, _roc_topn())
    available = long_prices["date"].drop_duplicates().sort_values().tolist()
    prefix_dates = available[:3]
    cutoff = prefix_dates[2]
    spec["deployed_on"] = available[10].strftime("%Y-%m-%d")
    spec["darwin_equity_curve"] = [
        {"d": prefix_dates[0].strftime("%Y-%m-%d"), "v": 100000.0},
        {"d": prefix_dates[1].strftime("%Y-%m-%d"), "v": 101000.0},
        {"d": prefix_dates[2].strftime("%Y-%m-%d"), "v": 102500.0},
    ]

    sparse = long_prices[
        ~((long_prices["ticker"] == universe[-1]) & (long_prices["date"] > cutoff))
    ]
    opens, closes = prices.long_to_wide(sparse)
    res = portfolio.simulate(spec, opens, closes, prices_long=sparse)

    tail_dates = [p["d"] for p in res.equity_curve[3:]]
    assert len(tail_dates) > 10
    assert tail_dates[0] > spec["darwin_equity_curve"][-1]["d"]
    assert tail_dates[-1] == closes.index[-1].strftime("%Y-%m-%d")


def test_no_backfill_leaves_backtest_segment_empty(universe, long_prices):
    """Without `backfill_start` the curve is all-live; backtest stats are zeros."""
    opens, closes = prices.long_to_wide(long_prices)
    res = portfolio.simulate(_spec(universe, _roc_topn()), opens, closes, prices_long=long_prices)
    assert res.stats_backtest == {"cagr": 0.0, "sharpe": 0.0, "max_dd": 0.0}
    # The live segment then equals the full-curve stats.
    assert res.stats_live == res.stats


def test_dsl_requires_prices_long(universe, long_prices):
    opens, closes = prices.long_to_wide(long_prices)
    with pytest.raises(ValueError, match="prices_long"):
        portfolio.simulate(_spec(universe, _roc_topn()), opens, closes)


def test_formula_state_features_detected():
    formula = {
        "kind": "arithmetic",
        "name": "add",
        "children": [
            {"kind": "indicator", "name": "roc", "params": {"window": 20}},
            {"kind": "indicator", "name": "invested_fraction", "params": {}},
            {"kind": "indicator", "name": "trailing_portfolio_turnover", "params": {"window": 6}},
        ],
    }
    feats = signals.formula_state_features(formula)
    assert "invested_fraction" in feats
    assert "trailing_portfolio_turnover_6" in feats
    assert "roc_20" not in feats


def test_state_override_flows_into_scores(universe, long_prices):
    """Injecting a different portfolio-state value changes evaluated scores."""
    formula = {
        "mode": "top_n",
        "top_n": 3,
        "kind": "arithmetic",
        "name": "add",
        "children": [
            {"kind": "indicator", "name": "roc", "params": {"window": 20}},
            {"kind": "indicator", "name": "invested_fraction", "params": {}},
        ],
    }
    common = dict(
        strat_dict=formula, target_date="2024-06-03", tickers=universe,
        prices_override=long_prices, min_price=0.0, min_adv=0.0, portfolio_size=1_000_000.0,
    )
    lo = select_tickers_on_date(**common, portfolio_state_override={"invested_fraction": 0.2})
    hi = select_tickers_on_date(**common, portfolio_state_override={"invested_fraction": 0.9})

    # Every ticker's score should be lifted by exactly the override delta (0.7).
    common_tickers = set(lo["scores"]) & set(hi["scores"])
    assert common_tickers
    for t in common_tickers:
        assert hi["scores"][t] == pytest.approx(lo["scores"][t] + 0.7, abs=1e-9)


def test_state_dependent_formula_simulates(universe, long_prices):
    """A formula that references portfolio state runs without NaN-crashing."""
    formula = {
        "mode": "top_n",
        "top_n": 4,
        "kind": "arithmetic",
        "name": "add",
        "children": [
            {"kind": "transform", "name": "z_score", "params": {"window": 60},
             "child": {"kind": "indicator", "name": "roc", "params": {"window": 40}}},
            {"kind": "indicator", "name": "current_portfolio_drawdown", "params": {}},
        ],
    }
    opens, closes = prices.long_to_wide(long_prices)
    res = portfolio.simulate(_spec(universe, formula), opens, closes, prices_long=long_prices)
    assert len(res.positions) > 0
    assert all(p["weight"] > 0 for p in res.positions)


@pytest.mark.parametrize("indicator", ["beta", "mkt_corr"])
def test_benchmark_dependent_features_without_market_series_do_not_warn(
    universe, long_prices, caplog, indicator
):
    formula = {
        "mode": "top_n",
        "top_n": 3,
        "kind": "indicator",
        "name": indicator,
        "params": {"window": 5},
    }

    with caplog.at_level(logging.WARNING):
        select_tickers_on_date(
            strat_dict=formula,
            target_date="2024-06-03",
            tickers=universe,
            prices_override=long_prices,
            min_price=0.0,
            min_adv=0.0,
            portfolio_size=1_000_000.0,
            market_series_override=None,
        )

    assert not any("Could not compute feature" in record.message for record in caplog.records)
