"""Astralanx-faithful transaction-cost model.

The paper simulator charges the **same** costs Astralanx's backtest engine charges,
so a strategy's live paper curve is consistent with the backtest it was selected
on. Astralanx applies cost as a multiplicative **equity haircut at each rebalance**
(see `src/native/native_eval.c` and `src/backtest/cost_models.py` in the Astralanx
repo), not as per-share fill slippage. This module reproduces that exactly.

At a rebalance, with prior (drifted) weights `prev_w` and target weights
`target_w`, Astralanx computes:

    turnover  = Σ_j |target_w[j] − prev_w[j]|                       # gross; full rotation = 2.0

    # commission + price-scaled slippage, both scaled by a vol multiplier
    cost_bps_eff   = commission_bps × vol_cost_mult
    slip_bps_eff   = slippage_bps   × vol_cost_mult
    scale          = max(spread_ref_price / harmonic_mean_price, 0.1)   # cheaper books pay more
    eff_slippage   = slip_bps_eff × scale
    cs_fraction    = (cost_bps_eff + eff_slippage) / 1e4 × turnover

    # sqrt market-impact per traded name (NOT scaled by the vol multiplier)
    impact_j       = volume_impact_coef × sqrt(dw_j × portfolio_size / adv_j)
    vi_fraction    = Σ_j dw_j × impact_j         # dw_j missing adv → dw_j × 0.05

    equity        *= (1 − cs_fraction − vi_fraction)

where `harmonic_mean_price` is the harmonic mean of the **target-held** names'
prices on the review date, `adv_j` is that name's review-date dollar volume
(price × volume), and `vol_cost_mult` is a crisis-aware multiplier from realized
vs long-run market volatility. The Astralanx defaults below come from
`src/config/engine.py` (`FinancialRealism` + `BacktestDiag`).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "CostModel", "volatility_cost_multiplier", "rebalance_cost_fraction",
    "sliced_execution_cost",
]

# Astralanx defaults — keep in sync with Astralanx's src/config/engine.py.
DEFAULT_SPREAD_REF_PRICE = 50.0
DEFAULT_VOLUME_IMPACT_COEF = 0.5
DEFAULT_VOL_COST_K = 0.75
DEFAULT_VOL_COST_REALIZED_WINDOW = 63
DEFAULT_VOL_COST_LONG_WINDOW = 252
DEFAULT_VOL_COST_MULT_MAX = 3.0
# The book size the sqrt volume-impact term sizes trades against. Astralanx's
# backtests use FinancialRealism.portfolio_size ($1M), independent of the
# strategy's displayed/traded capital, so the live paper cost matches the
# backtest. Authoritative per-spec via cost_model.impact_portfolio_size.
DEFAULT_IMPACT_PORTFOLIO_SIZE = 1_000_000.0

MISSING_ADV_PENALTY = 0.05   # native_eval.c: traded name with no ADV → 5% slippage
MIN_PRICE_SCALE = 0.1        # native_eval.c: price-scale floor (no upper cap)


@dataclass(frozen=True)
class CostModel:
    """Cost parameters that mirror Astralanx's `FinancialRealism` + `BacktestDiag`.

    Only `commission_bps` and `slippage_bps` are required; the rest default to
    Astralanx's engine defaults so older specs keep working unchanged.
    """

    commission_bps: float
    slippage_bps: float
    spread_ref_price: float = DEFAULT_SPREAD_REF_PRICE
    volume_impact_coef: float = DEFAULT_VOLUME_IMPACT_COEF
    impact_portfolio_size: float = DEFAULT_IMPACT_PORTFOLIO_SIZE
    # Legacy field name for the invested-cap ceiling. `portfolio.py` scales
    # target weights so excess account equity remains cash.
    impact_book_cap: float = 0.0
    # Zero preserves legacy specs. Darwin's current exporter writes a positive
    # value and opts into the sliced-execution model.
    execution_max_days: int = 0
    execution_participation_rate: float = 0.01
    execution_delay_risk_coef: float = 0.25
    execution_overflow_penalty_bps: float = 500.0
    impact_lookback_days: int = 63
    vol_scaled_cost_enable: bool = True
    vol_cost_k: float = DEFAULT_VOL_COST_K
    vol_cost_realized_window: int = DEFAULT_VOL_COST_REALIZED_WINDOW
    vol_cost_long_window: int = DEFAULT_VOL_COST_LONG_WINDOW
    vol_cost_mult_max: float = DEFAULT_VOL_COST_MULT_MAX

    @classmethod
    def from_spec(cls, cm: dict) -> "CostModel":
        return cls(
            commission_bps=float(cm["commission_bps"]),
            slippage_bps=float(cm["slippage_bps"]),
            spread_ref_price=float(cm.get("spread_ref_price", DEFAULT_SPREAD_REF_PRICE)),
            volume_impact_coef=float(cm.get("volume_impact_coef", DEFAULT_VOLUME_IMPACT_COEF)),
            impact_portfolio_size=float(cm.get("impact_portfolio_size", DEFAULT_IMPACT_PORTFOLIO_SIZE)),
            impact_book_cap=float(cm.get("impact_book_cap", 0.0)),
            execution_max_days=int(cm.get("execution_max_days", 0)),
            execution_participation_rate=float(cm.get("execution_participation_rate", 0.01)),
            execution_delay_risk_coef=float(cm.get("execution_delay_risk_coef", 0.25)),
            execution_overflow_penalty_bps=float(cm.get("execution_overflow_penalty_bps", 500.0)),
            impact_lookback_days=int(cm.get("impact_lookback_days", 63)),
            vol_scaled_cost_enable=bool(cm.get("vol_scaled_cost_enable", True)),
            vol_cost_k=float(cm.get("vol_cost_k", DEFAULT_VOL_COST_K)),
            vol_cost_realized_window=int(cm.get("vol_cost_realized_window", DEFAULT_VOL_COST_REALIZED_WINDOW)),
            vol_cost_long_window=int(cm.get("vol_cost_long_window", DEFAULT_VOL_COST_LONG_WINDOW)),
            vol_cost_mult_max=float(cm.get("vol_cost_mult_max", DEFAULT_VOL_COST_MULT_MAX)),
        )


def volatility_cost_multiplier(market_returns: np.ndarray, cfg: CostModel) -> float:
    """Crisis-aware cost multiplier ``clip(1 + k·sqrt(realized/long), 1, max)``.

    `market_returns` is a 1-D array of the equal-weighted market's daily returns
    up to and including the review date. Mirrors Astralanx's
    `_compute_volatility_cost_multiplier`: realized vol over the last
    `vol_cost_realized_window` points vs long-run vol over the last
    `vol_cost_long_window` (sample std, ddof=1). Returns 1.0 when disabled or on
    insufficient data (need ≥5 realized and ≥20 long points).
    """
    if not cfg.vol_scaled_cost_enable or cfg.vol_cost_k <= 0.0:
        return 1.0

    r = np.asarray(market_returns, dtype=np.float64)
    r = r[np.isfinite(r)]

    realized_window = max(5, int(cfg.vol_cost_realized_window))
    long_window = max(realized_window, int(cfg.vol_cost_long_window))
    mult_max = max(1.0, float(cfg.vol_cost_mult_max))

    long_vals = r[-long_window:]
    realized_vals = r[-realized_window:]
    if realized_vals.size < 5 or long_vals.size < 20:
        return 1.0

    realized_vol = float(np.nanstd(realized_vals, ddof=1))
    long_term_vol = float(np.nanstd(long_vals, ddof=1))
    if not np.isfinite(realized_vol) or not np.isfinite(long_term_vol) or long_term_vol <= 0.0:
        return 1.0

    vol_ratio = max(realized_vol / long_term_vol, 1e-6)
    mult = 1.0 + cfg.vol_cost_k * float(np.sqrt(vol_ratio))
    if not np.isfinite(mult):
        return 1.0
    return float(np.clip(mult, 1.0, mult_max))


def rebalance_cost_fraction(
    prev_w: dict[str, float],
    target_w: dict[str, float],
    review_price: dict[str, float],
    review_dollar_volume: dict[str, float] | None,
    cfg: CostModel,
    vol_cost_mult: float = 1.0,
    impact_book: float | None = None,
    review_daily_volatility: dict[str, float] | None = None,
) -> dict:
    """Total equity-haircut fraction for one rebalance, Astralanx-faithful.

    Returns a breakdown dict with `turnover`, `effective_slippage_bps`,
    `commission_slippage_fraction`, `volume_impact_fraction`, and `total_fraction`
    (the fraction of equity to remove). Apply it as ``equity *= 1 - total_fraction``.

    `review_price` / `review_dollar_volume` are keyed by ticker at the review
    date. When `review_dollar_volume` is None the volume-impact term is skipped
    entirely (mirrors Astralanx running with no volume array), rather than charging
    the missing-ADV penalty.

    The volume-impact term sizes trades against `impact_book` when given, else
    `cfg.impact_portfolio_size`. The simulator passes the full compounded account
    book; target weights already encode any cash retained above capacity.
    """
    impact_portfolio_size = (
        float(impact_book) if impact_book is not None else cfg.impact_portfolio_size
    )
    names = set(prev_w) | set(target_w)
    turnover = sum(abs(target_w.get(t, 0.0) - prev_w.get(t, 0.0)) for t in names)

    cost_bps_eff = cfg.commission_bps * vol_cost_mult
    slip_bps_eff = cfg.slippage_bps * vol_cost_mult

    # Price-scaled slippage: cheaper portfolios pay proportionally more.
    effective_slippage = slip_bps_eff
    if cfg.spread_ref_price > 0.0 and turnover > 0.0:
        inv_prices = [
            1.0 / review_price[t]
            for t in target_w
            if target_w[t] > 0.0 and review_price.get(t, 0.0) > 0.0
        ]
        if inv_prices:
            harmonic_mean_price = len(inv_prices) / sum(inv_prices)
            scale = cfg.spread_ref_price / harmonic_mean_price
            if scale < MIN_PRICE_SCALE:
                scale = MIN_PRICE_SCALE
            effective_slippage = slip_bps_eff * scale

    commission_slippage_fraction = (cost_bps_eff + effective_slippage) / 1e4 * turnover

    # sqrt market impact per traded name. Skipped wholesale if no volume data.
    volume_impact_fraction = 0.0
    if cfg.volume_impact_coef > 0.0 and turnover > 0.0 and review_dollar_volume is not None:
        for t in names:
            dw = abs(target_w.get(t, 0.0) - prev_w.get(t, 0.0))
            if dw <= 0.0:
                continue
            adv = review_dollar_volume.get(t)
            if adv is not None and adv > 0.0 and np.isfinite(adv):
                if cfg.execution_max_days > 0:
                    sigma = 0.02
                    if review_daily_volatility is not None:
                        candidate = review_daily_volatility.get(t)
                        if candidate is not None and candidate > 0.0 and np.isfinite(candidate):
                            sigma = float(candidate)
                    execution = sliced_execution_cost(
                        trade_value=dw * impact_portfolio_size,
                        adv_dollars=adv,
                        daily_volatility=sigma,
                        cfg=cfg,
                    )
                    impact = execution["total_cost_fraction"]
                else:
                    impact = cfg.volume_impact_coef * float(
                        np.sqrt(dw * impact_portfolio_size / adv)
                    )
                volume_impact_fraction += dw * impact
            else:
                volume_impact_fraction += dw * MISSING_ADV_PENALTY

    total_fraction = commission_slippage_fraction + volume_impact_fraction
    return {
        "turnover": turnover,
        "effective_slippage_bps": effective_slippage,
        "commission_slippage_fraction": commission_slippage_fraction,
        "volume_impact_fraction": volume_impact_fraction,
        "total_fraction": total_fraction,
    }


def sliced_execution_cost(
    *,
    trade_value: float,
    adv_dollars: float,
    daily_volatility: float,
    cfg: CostModel,
) -> dict[str, float | int]:
    """Mirror Darwin's ``_execution_cost_per_dollar`` sliced-order model."""
    q = float(trade_value)
    adv = float(adv_dollars)
    sigma = float(daily_volatility)
    if q <= 0.0 or adv <= 0.0 or sigma <= 0.0:
        return {
            "execution_days": 0, "daily_participation_rate": 0.0,
            "impact_fraction": 0.0, "delay_risk_fraction": 0.0,
            "overflow_fraction": 0.0, "overflow_penalty_fraction": 0.0,
            "total_cost_fraction": 0.0,
        }
    days_cap = max(1, int(cfg.execution_max_days))
    participation = float(np.clip(cfg.execution_participation_rate, 1e-9, 1.0))
    daily_capacity = adv * participation
    required_days = max(1, int(np.ceil(q / daily_capacity)))
    execution_days = min(days_cap, required_days)
    daily_slice = q / execution_days
    impact = max(0.0, cfg.volume_impact_coef) * sigma * float(np.sqrt(daily_slice / adv))
    delay = (
        max(0.0, cfg.execution_delay_risk_coef)
        * sigma
        * float(np.sqrt(max(0, execution_days - 1) / 252.0))
    )
    executable = daily_capacity * days_cap
    overflow = float(np.clip((q - executable) / q, 0.0, 1.0))
    penalty = overflow * max(0.0, cfg.execution_overflow_penalty_bps) / 10000.0
    return {
        "execution_days": execution_days,
        "daily_participation_rate": daily_slice / adv,
        "impact_fraction": impact,
        "delay_risk_fraction": delay,
        "overflow_fraction": overflow,
        "overflow_penalty_fraction": penalty,
        "total_cost_fraction": impact + delay + penalty,
    }
