"""Tests for the Astralanx-faithful cost model.

Numbers are hand-derived from the formulas in `paper_trading/costs.py`, which
mirror Astralanx's `native_eval.c` cost block and `cost_models.py` multiplier.
"""

from __future__ import annotations

import numpy as np
import pytest

from paper_trading import prices
from paper_trading.costs import (
    CostModel,
    rebalance_cost_fraction,
    volatility_cost_multiplier,
)
from paper_trading import portfolio


def _cfg(**kw) -> CostModel:
    base = dict(commission_bps=0.0, slippage_bps=0.0, spread_ref_price=0.0, volume_impact_coef=0.0)
    base.update(kw)
    return CostModel(**base)


# --- rebalance_cost_fraction ----------------------------------------------

def test_flat_commission_and_slippage():
    cfg = _cfg(commission_bps=10.0, slippage_bps=5.0)  # spread_ref=0 → no price scaling
    res = rebalance_cost_fraction(
        {"A": 0.5, "B": 0.5}, {"A": 0.7, "B": 0.3},
        {"A": 100.0, "B": 100.0}, None, cfg, vol_cost_mult=1.0,
    )
    assert res["turnover"] == pytest.approx(0.4)
    assert res["effective_slippage_bps"] == pytest.approx(5.0)
    # (10 + 5)/1e4 * 0.4
    assert res["total_fraction"] == pytest.approx(0.0006)
    assert res["volume_impact_fraction"] == 0.0


def test_price_scaled_slippage_cheap_book_pays_more():
    cfg = _cfg(slippage_bps=5.0, spread_ref_price=50.0)
    res = rebalance_cost_fraction(
        {}, {"A": 0.5, "B": 0.5}, {"A": 25.0, "B": 25.0}, None, cfg, 1.0,
    )
    # harmonic mean price = 25 → scale = 50/25 = 2 → eff slippage 10 bps; turnover 1.0
    assert res["effective_slippage_bps"] == pytest.approx(10.0)
    assert res["total_fraction"] == pytest.approx(0.001)


def test_price_scale_floor_at_0_1():
    cfg = _cfg(slippage_bps=5.0, spread_ref_price=50.0)
    res = rebalance_cost_fraction(
        {}, {"A": 1.0}, {"A": 1000.0}, None, cfg, 1.0,
    )
    # scale = 50/1000 = 0.05 < 0.1 → floored to 0.1 → eff slippage 0.5 bps
    assert res["effective_slippage_bps"] == pytest.approx(0.5)


def test_volume_impact_sqrt_term():
    cfg = _cfg(volume_impact_coef=0.5, impact_portfolio_size=100_000.0)
    res = rebalance_cost_fraction(
        {}, {"A": 0.5}, {"A": 100.0}, {"A": 5e8}, cfg, 1.0,
    )
    # dw=0.5, trade_value=50_000, adv=5e8 → impact=0.5*sqrt(1e-4)=0.005 → 0.5*0.005
    assert res["volume_impact_fraction"] == pytest.approx(0.0025)
    assert res["commission_slippage_fraction"] == 0.0


def test_impact_portfolio_size_sizes_trades():
    # Same trade, 4× the impact book → 2× the impact (sqrt scaling).
    small = _cfg(volume_impact_coef=0.5, impact_portfolio_size=100_000.0)
    big = _cfg(volume_impact_coef=0.5, impact_portfolio_size=400_000.0)
    args = ({}, {"A": 0.5}, {"A": 100.0}, {"A": 5e8})
    r_small = rebalance_cost_fraction(*args, small, 1.0)["volume_impact_fraction"]
    r_big = rebalance_cost_fraction(*args, big, 1.0)["volume_impact_fraction"]
    assert r_big == pytest.approx(2.0 * r_small)


def test_impact_portfolio_size_defaults_to_darwin_1m():
    from paper_trading.costs import CostModel, DEFAULT_IMPACT_PORTFOLIO_SIZE
    cfg = CostModel.from_spec({"commission_bps": 1.0, "slippage_bps": 5.0})
    assert cfg.impact_portfolio_size == DEFAULT_IMPACT_PORTFOLIO_SIZE == 1_000_000.0


def test_missing_adv_penalty():
    cfg = _cfg(volume_impact_coef=0.5)
    res = rebalance_cost_fraction(
        {}, {"A": 0.4}, {"A": 100.0}, {"A": 0.0}, cfg, 1.0,
    )
    # adv 0 → penalty dw * 0.05 = 0.4 * 0.05
    assert res["volume_impact_fraction"] == pytest.approx(0.02)


def test_no_volume_frame_skips_impact():
    cfg = _cfg(volume_impact_coef=0.5)
    res = rebalance_cost_fraction(
        {}, {"A": 1.0}, {"A": 100.0}, None, cfg, 1.0,
    )
    assert res["volume_impact_fraction"] == 0.0


def test_vol_mult_scales_commission_slippage_but_not_impact():
    cfg = _cfg(commission_bps=10.0, slippage_bps=10.0, volume_impact_coef=0.5,
               impact_portfolio_size=100_000.0)
    res = rebalance_cost_fraction(
        {}, {"A": 1.0}, {"A": 100.0}, {"A": 1e7}, cfg, vol_cost_mult=2.0,
    )
    # commission+slippage scaled ×2: (20 + 20)/1e4 * 1.0 = 0.004
    assert res["commission_slippage_fraction"] == pytest.approx(0.004)
    # impact NOT scaled: dw=1, trade_value=100_000, adv=1e7 → 0.5*sqrt(0.01)=0.05
    assert res["volume_impact_fraction"] == pytest.approx(0.05)
    assert res["total_fraction"] == pytest.approx(0.054)


# --- volatility_cost_multiplier -------------------------------------------

def test_vol_mult_disabled_returns_one():
    cfg = _cfg(vol_scaled_cost_enable=False)
    assert volatility_cost_multiplier(np.random.randn(300) * 0.01, cfg) == 1.0


def test_vol_mult_k_zero_returns_one():
    cfg = _cfg(vol_cost_k=0.0)
    assert volatility_cost_multiplier(np.random.randn(300) * 0.01, cfg) == 1.0


def test_vol_mult_insufficient_data_returns_one():
    cfg = _cfg(vol_cost_k=0.75)
    assert volatility_cost_multiplier(np.array([0.01, -0.01, 0.02]), cfg) == 1.0


def test_vol_mult_ratio_one_gives_one_plus_k():
    # realized window == long window == 20, exactly 20 points → identical slices
    # → realized/long vol ratio = 1 → multiplier = 1 + k.
    cfg = _cfg(vol_cost_k=0.75, vol_cost_realized_window=20, vol_cost_long_window=20)
    rng = np.random.default_rng(0)
    r = rng.normal(0, 0.01, size=20)
    assert volatility_cost_multiplier(r, cfg) == pytest.approx(1.75)


def test_vol_mult_clamped_to_max():
    cfg = _cfg(vol_cost_k=0.75, vol_cost_realized_window=5, vol_cost_long_window=20, vol_cost_mult_max=1.2)
    # 15 tiny then 5 huge returns → realized vol >> long vol → mult hits the cap.
    r = np.concatenate([np.full(15, 1e-5) * np.array([1, -1] * 8)[:15],
                        np.array([0.5, -0.5, 0.5, -0.5, 0.5])])
    assert volatility_cost_multiplier(r, cfg) == pytest.approx(1.2)


# --- integration: higher costs → lower terminal equity --------------------

def _momentum_spec(universe, cost_model):
    return {
        "id": "m", "name": "m", "visibility": "open",
        "deployed_on": "2023-06-01", "portfolio_size": 100_000,
        "base_currency": "USD", "rebalance_cadence_days": 30,
        "cost_model": cost_model,
        "universe": universe,
        "signal": {"type": "cross_sectional_momentum", "lookback_days": 90,
                   "skip_days": 5, "top_n": 4, "min_momentum": 0.0, "weighting": "equal"},
    }


def test_costs_reduce_terminal_equity(universe, long_prices):
    opens, closes = prices.long_to_wide(long_prices)
    raw_closes, dollar_volume = prices.wide_raw_and_dollar_volume(long_prices)
    kw = dict(dollar_volume=dollar_volume, raw_closes=raw_closes)

    free = portfolio.simulate(
        _momentum_spec(universe, {"commission_bps": 0.0, "slippage_bps": 0.0,
                                  "spread_ref_price": 0.0, "volume_impact_coef": 0.0}),
        opens, closes, **kw,
    )
    costly = portfolio.simulate(
        _momentum_spec(universe, {"commission_bps": 50.0, "slippage_bps": 50.0,
                                  "volume_impact_coef": 1.0}),
        opens, closes, **kw,
    )
    assert costly.equity_curve[-1]["v"] < free.equity_curve[-1]["v"]
