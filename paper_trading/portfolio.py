"""Paper-portfolio simulator — deterministic, re-runnable, no broker.

Walks a strategy forward from `deployed_on` to the last available bar:

  * On each rebalance date, evaluate the signal (`signals.evaluate`) to get
    target weights and execute the implied trades at the **next** bar's open,
    charging commission + slippage (the cost model).
  * Every trading day, mark holdings to that day's close and record an equity
    point.
  * From the daily equity series, compute CAGR / Sharpe / max-drawdown.

This is paper only: it never places an order, holds no credentials, and the
whole curve is recomputed from price history on every run, so a given price
history always yields the same result (see `docs/concepts/paper-trading-only.md`).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import portfolio_state as ps
from . import signals

__all__ = ["simulate", "SimResult"]

TRADING_DAYS = 252


@dataclass
class SimResult:
    equity_curve: list[dict]          # [{"d": "YYYY-MM-DD", "v": float}, ...]
    stats: dict                       # {"cagr", "sharpe", "max_dd"}
    positions: list[dict]             # [{"ticker", "weight"}, ...] (latest)
    trades: list[dict]                # most-recent rebalance's trades
    as_of: str                        # latest bar date, ISO


def _rebalance_dates(index: pd.DatetimeIndex, deployed_on: pd.Timestamp, cadence_days: int):
    """Trading days on or after each scheduled rebalance, from `deployed_on`."""
    target = deployed_on
    last = index[-1]
    out: list[pd.Timestamp] = []
    while target <= last:
        # Snap to the first trading day on/after the target calendar date.
        pos = index.searchsorted(target, side="left")
        if pos < len(index):
            d = index[pos]
            if not out or d != out[-1]:
                out.append(d)
        target = target + pd.Timedelta(days=cadence_days)
    return out


def simulate(
    strategy: dict,
    opens: pd.DataFrame,
    closes: pd.DataFrame,
    prices_long: pd.DataFrame | None = None,
) -> SimResult:
    """Simulate a strategy. Dispatches on the spec:

    * ``formula`` (a DSL tree) → the real vendored Darwin evaluator, with
      engine-faithful portfolio-state threading. Requires ``prices_long``.
    * ``signal`` (a momentum block) → the lightweight built-in path.
    """
    if "formula" in strategy:
        if prices_long is None:
            raise ValueError(
                f"{strategy['id']}: DSL strategies require prices_long (long OHLCV)."
            )
        return _simulate_dsl(strategy, opens, closes, prices_long)
    return _simulate_signal(strategy, opens, closes)


def _simulate_signal(strategy: dict, opens: pd.DataFrame, closes: pd.DataFrame) -> SimResult:
    capital = float(strategy["portfolio_size"])
    deployed_on = pd.Timestamp(strategy["deployed_on"])
    cadence = int(strategy["rebalance_cadence_days"])
    cm = strategy["cost_model"]
    commission = float(cm["commission_bps"]) / 1e4
    slippage = float(cm["slippage_bps"]) / 1e4
    signal = strategy["signal"]
    tickers = list(closes.columns)

    sim_index = closes.loc[deployed_on:].index
    if len(sim_index) == 0:
        raise ValueError(
            f"{strategy['id']}: no price bars on/after deployed_on {deployed_on.date()}"
        )

    rebal_dates = set(_rebalance_dates(sim_index, deployed_on, cadence))

    cash = capital
    shares = {t: 0.0 for t in tickers}
    target_weights: dict[str, float] = {}
    last_trades: list[dict] = []

    curve: list[dict] = []
    equity_values: list[float] = []

    for i, day in enumerate(sim_index):
        # Execute the previous rebalance's target at today's open.
        if target_weights and i > 0:
            equity_open = cash + sum(
                shares[t] * opens.at[day, t] for t in tickers
            )
            new_shares, cash, trades = _apply_targets(
                target_weights, shares, cash, opens.loc[day],
                equity_open, commission, slippage, tickers,
            )
            shares = new_shares
            if trades:
                last_trades = [dict(d=day.strftime("%Y-%m-%d"), **tr) for tr in trades]
            target_weights = {}

        # Decide a new target on rebalance days (filled next open).
        if day in rebal_dates:
            target_weights = signals.evaluate(signal, closes, day)

        equity_close = cash + sum(shares[t] * closes.at[day, t] for t in tickers)
        equity_values.append(equity_close)
        curve.append({"d": day.strftime("%Y-%m-%d"), "v": round(equity_close, 2)})

    equity = pd.Series(equity_values, index=sim_index)
    stats = _stats(equity)
    positions = _latest_positions(shares, closes.iloc[-1], equity_values[-1], tickers)

    return SimResult(
        equity_curve=curve,
        stats=stats,
        positions=positions,
        trades=last_trades,
        as_of=sim_index[-1].strftime("%Y-%m-%d"),
    )


def _simulate_dsl(
    strategy: dict,
    opens: pd.DataFrame,
    closes: pd.DataFrame,
    prices_long: pd.DataFrame,
) -> SimResult:
    """Simulate a real DSL king via the vendored evaluator.

    At each rebalance the formula is evaluated with the **drifted actual** prior
    weights and engine-faithful portfolio-state features (drawdown, trailing
    turnover/volatility/hit-rate), matching how Darwin's backtest engine carries
    state. The returned `final_weights` are the target; fills happen at the next
    open under our cost model. See docs/subsystems/paper-trading-updater.md.
    """
    capital = float(strategy["portfolio_size"])
    deployed_on = pd.Timestamp(strategy["deployed_on"])
    cadence = int(strategy["rebalance_cadence_days"])
    cm = strategy["cost_model"]
    commission = float(cm["commission_bps"]) / 1e4
    slippage = float(cm["slippage_bps"]) / 1e4
    formula = strategy["formula"]
    universe = list(closes.columns)

    sim_index = closes.loc[deployed_on:].index
    if len(sim_index) == 0:
        raise ValueError(
            f"{strategy['id']}: no price bars on/after deployed_on {deployed_on.date()}"
        )

    rebal_set = set(_rebalance_dates(sim_index, deployed_on, cadence))
    needed_state = signals.formula_state_features(formula)

    state = ps.PortfolioState(capital)
    cash = capital
    shares = {t: 0.0 for t in universe}
    pending_target: dict[str, float] | None = None
    equity_at_prev_rebal: float | None = None
    last_trades: list[dict] = []

    curve: list[dict] = []
    equity_values: list[float] = []

    for i, day in enumerate(sim_index):
        # Execute the previous rebalance's target at today's open.
        if pending_target is not None and i > 0:
            equity_open = cash + sum(shares[t] * opens.at[day, t] for t in universe)
            shares, cash, trades = _apply_targets(
                pending_target, shares, cash, opens.loc[day],
                equity_open, commission, slippage, universe,
            )
            if trades:
                last_trades = [dict(d=day.strftime("%Y-%m-%d"), **tr) for tr in trades]
            pending_target = None

        # Rebalance decision on review days (filled at next open).
        if day in rebal_set:
            equity_now = cash + sum(shares[t] * closes.at[day, t] for t in universe)

            # Close out the prior holding period's return + peak BEFORE reading
            # state, mirroring native_eval.c (peak updates at period end).
            if equity_at_prev_rebal is not None and equity_at_prev_rebal > 0:
                state.push_period_return(equity_now / equity_at_prev_rebal - 1.0)
                state.update_peak(equity_now)

            prior_w = {
                t: (shares[t] * closes.at[day, t]) / equity_now
                for t in universe
                if equity_now > 0 and shares[t] * closes.at[day, t] > 0
            }
            prior_holdings = list(prior_w)
            override = state.scalars_for(needed_state, equity=equity_now, weights=prior_w)

            res = signals.evaluate_formula(
                formula,
                prices_long=prices_long,
                asof=day,
                universe=universe,
                portfolio_size=capital,
                prior_weights=prior_w,
                prior_holdings=prior_holdings,
                portfolio_state_override=override,
            )
            target = {t: float(w) for t, w in res["final_weights"].items() if w > 0}
            state.push_turnover(target, prior_w)
            pending_target = target
            equity_at_prev_rebal = equity_now

        equity_close = cash + sum(shares[t] * closes.at[day, t] for t in universe)
        equity_values.append(equity_close)
        curve.append({"d": day.strftime("%Y-%m-%d"), "v": round(equity_close, 2)})

    equity = pd.Series(equity_values, index=sim_index)
    stats = _stats(equity)
    positions = _latest_positions(shares, closes.iloc[-1], equity_values[-1], universe)

    return SimResult(
        equity_curve=curve,
        stats=stats,
        positions=positions,
        trades=last_trades,
        as_of=sim_index[-1].strftime("%Y-%m-%d"),
    )


def _apply_targets(targets, shares, cash, open_px, equity, commission, slippage, tickers):
    """Move holdings toward `targets` at today's open, charging costs.

    Buys fill at open*(1+slippage), sells at open*(1-slippage); commission is
    charged on traded notional. Returns (new_shares, new_cash, trades) where each
    trade records the *change in weight* for the ticker.
    """
    new_shares = dict(shares)
    trades: list[dict] = []

    for t in tickers:
        px = float(open_px[t])
        cur_val = shares[t] * px
        cur_w = cur_val / equity if equity > 0 else 0.0
        tgt_w = targets.get(t, 0.0)
        delta_w = tgt_w - cur_w
        if abs(delta_w) < 1e-6:
            continue

        target_val = tgt_w * equity
        delta_val = target_val - cur_val
        if delta_val > 0:  # buy
            fill = px * (1 + slippage)
            qty = delta_val / fill
            new_shares[t] = shares[t] + qty
            cash -= qty * fill
            cash -= abs(qty * fill) * commission
            side = "buy"
        else:  # sell
            fill = px * (1 - slippage)
            qty = (-delta_val) / fill
            new_shares[t] = shares[t] - qty
            cash += qty * fill
            cash -= abs(qty * fill) * commission
            side = "sell"

        trades.append(
            {"ticker": t, "side": side, "weight": round(abs(delta_w), 4)}
        )

    return new_shares, cash, trades


def _stats(equity: pd.Series) -> dict:
    """CAGR, annualized Sharpe (rf=0), and max drawdown from a daily curve."""
    if len(equity) < 2:
        return {"cagr": 0.0, "sharpe": 0.0, "max_dd": 0.0}

    start_v, end_v = float(equity.iloc[0]), float(equity.iloc[-1])
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (end_v / start_v) ** (1 / years) - 1 if years > 0 and start_v > 0 else 0.0

    rets = equity.pct_change().dropna()
    if rets.std(ddof=0) > 0:
        sharpe = (rets.mean() / rets.std(ddof=0)) * np.sqrt(TRADING_DAYS)
    else:
        sharpe = 0.0

    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    max_dd = float(drawdown.min())

    return {
        "cagr": round(float(cagr), 4),
        "sharpe": round(float(sharpe), 2),
        "max_dd": round(max_dd, 4),
    }


def _latest_positions(shares, close_px, equity, tickers) -> list[dict]:
    out = []
    for t in tickers:
        val = shares[t] * float(close_px[t])
        w = val / equity if equity > 0 else 0.0
        if w > 1e-4:
            out.append({"ticker": t, "weight": round(w, 4)})
    out.sort(key=lambda p: p["weight"], reverse=True)
    return out
