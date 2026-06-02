"""Integration tests for the DSL simulation path and state injection."""

from __future__ import annotations

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
