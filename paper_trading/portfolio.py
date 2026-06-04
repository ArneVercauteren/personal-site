"""Paper-portfolio simulator — deterministic, re-runnable, no broker.

Walks a strategy forward from its simulation start to the last available bar.
The start is `backfill_start` / `deployed_on`, or the final date of an
authoritative Astralanx `darwin_equity_curve` prefix when provided:

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

from . import costs
from . import portfolio_state as ps
from . import signals

__all__ = ["simulate", "SimResult", "simulation_curve_start"]

TRADING_DAYS = 252


@dataclass
class SimResult:
    equity_curve: list[dict]          # [{"d": "YYYY-MM-DD", "v": float}, ...]
    stats: dict                       # {"cagr", "sharpe", "max_dd"} over the full curve
    positions: list[dict]             # [{"ticker", "weight"}, ...] (latest)
    trades: list[dict]                # most-recent rebalance's trades
    as_of: str                        # latest bar date, ISO
    # Split stats around `live_since` (= deployed_on). The curve can start
    # earlier than the live date (a one-time backfill), so the pre-live segment
    # is an out-of-sample backtest and the post-live segment is real forward
    # paper-trading. Either may be all-zeros when its segment has < 2 points.
    stats_backtest: dict = None       # [curve start, live_since)
    stats_live: dict = None           # [live_since, last bar]


def _darwin_equity_curve(strategy: dict) -> list[dict]:
    raw = strategy.get("darwin_equity_curve") or []
    if not raw:
        return []
    curve: list[dict] = []
    prev: pd.Timestamp | None = None
    for point in raw:
        day = pd.Timestamp(point["d"]).normalize()
        value = float(point["v"])
        if value <= 0 or not np.isfinite(value):
            raise ValueError(f"{strategy['id']}: darwin_equity_curve has invalid value {value!r}")
        if prev is not None and day <= prev:
            raise ValueError(f"{strategy['id']}: darwin_equity_curve dates must be strictly increasing")
        curve.append({"d": day.strftime("%Y-%m-%d"), "v": round(value, 2)})
        prev = day
    return curve


def simulation_curve_start(strategy: dict) -> str:
    """First date the Yahoo-backed simulator must cover for this spec.

    Astralanx can export the authoritative training+OOS prefix. When present, the
    site only needs Yahoo data from that prefix's last date onward.
    """
    curve = _darwin_equity_curve(strategy)
    if curve:
        return curve[-1]["d"]
    return strategy.get("backfill_start") or strategy["deployed_on"]


def _starting_capital(strategy: dict, darwin_curve: list[dict]) -> float:
    if darwin_curve:
        return float(darwin_curve[-1]["v"])
    return float(strategy["portfolio_size"])


def _stitch_curve(darwin_curve: list[dict], continuation: list[dict]) -> tuple[list[dict], pd.Series]:
    if not darwin_curve:
        dates = [pd.Timestamp(p["d"]) for p in continuation]
        equity = pd.Series([float(p["v"]) for p in continuation], index=pd.DatetimeIndex(dates))
        return continuation, equity
    cutoff = darwin_curve[-1]["d"]
    tail = [p for p in continuation if p["d"] > cutoff]
    stitched = darwin_curve + tail
    dates = [pd.Timestamp(p["d"]) for p in stitched]
    equity = pd.Series([float(p["v"]) for p in stitched], index=pd.DatetimeIndex(dates))
    return stitched, equity


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


def _market_returns(closes: pd.DataFrame) -> pd.Series:
    """Equal-weighted market daily-return proxy (mean across tickers).

    Feeds the volatility cost multiplier, mirroring Astralanx's market proxy
    (`nanmean` of per-ticker returns) in `cost_models.py`.
    """
    return closes.pct_change().mean(axis=1)


def _review_maps(day, names, raw_closes, closes, dollar_volume):
    """Per-ticker review-date `(price, dollar_volume)` for the cost model.

    Price uses nominal (raw) close when available — the price-scaled slippage is
    a nominal-price notion — else the adjusted close. Dollar volume is None when
    no volume frame was supplied, which makes the cost model skip the impact term.
    """
    price = {}
    for t in names:
        if raw_closes is not None and t in raw_closes.columns and day in raw_closes.index:
            v = raw_closes.at[day, t]
            price[t] = float(v) if pd.notna(v) else float(closes.at[day, t])
        else:
            price[t] = float(closes.at[day, t])

    dvol = None
    if dollar_volume is not None:
        dvol = {}
        for t in names:
            if t in dollar_volume.columns and day in dollar_volume.index:
                val = dollar_volume.at[day, t]
                dvol[t] = float(val) if pd.notna(val) else None
            else:
                dvol[t] = None
    return price, dvol


def _finite_price(row, ticker: str) -> float | None:
    try:
        value = float(row[ticker])
    except Exception:
        return None
    return value if np.isfinite(value) and value > 0.0 else None


def _position_value(shares: dict[str, float], prices, tickers: list[str]) -> float:
    total = 0.0
    for t in tickers:
        qty = float(shares.get(t, 0.0))
        if abs(qty) <= 1e-12:
            continue
        px = _finite_price(prices, t)
        if px is not None:
            total += qty * px
    return total


def _current_weights(
    shares: dict[str, float],
    prices,
    equity: float,
    tickers: list[str],
) -> dict[str, float]:
    if equity <= 0:
        return {}
    out: dict[str, float] = {}
    for t in tickers:
        qty = float(shares.get(t, 0.0))
        if abs(qty) <= 1e-12:
            continue
        px = _finite_price(prices, t)
        if px is None:
            continue
        val = qty * px
        if val > 0:
            out[t] = val / equity
    return out


def simulate(
    strategy: dict,
    opens: pd.DataFrame,
    closes: pd.DataFrame,
    prices_long: pd.DataFrame | None = None,
    dollar_volume: pd.DataFrame | None = None,
    raw_closes: pd.DataFrame | None = None,
) -> SimResult:
    """Simulate a strategy. Dispatches on the spec:

    * ``formula`` (a DSL tree) → the real vendored Astralanx evaluator, with
      engine-faithful portfolio-state threading. Requires ``prices_long``.
    * ``signal`` (a momentum block) → the lightweight built-in path.

    Costs are charged the Astralanx way (see `costs.py`): a per-rebalance equity
    haircut from turnover-scaled commission + price-scaled slippage + sqrt volume
    impact. `dollar_volume` (review-date `price × volume`) and `raw_closes`
    (nominal price) feed that model; both are optional — without `dollar_volume`
    the impact term is skipped, and without `raw_closes` the adjusted close is
    used for price scaling.
    """
    if "formula" in strategy:
        if prices_long is None:
            raise ValueError(
                f"{strategy['id']}: DSL strategies require prices_long (long OHLCV)."
            )
        return _simulate_dsl(strategy, opens, closes, prices_long, dollar_volume, raw_closes)
    return _simulate_signal(strategy, opens, closes, dollar_volume, raw_closes)


def _simulate_signal(
    strategy: dict,
    opens: pd.DataFrame,
    closes: pd.DataFrame,
    dollar_volume: pd.DataFrame | None = None,
    raw_closes: pd.DataFrame | None = None,
) -> SimResult:
    darwin_curve = _darwin_equity_curve(strategy)
    capital = _starting_capital(strategy, darwin_curve)
    sim_start = pd.Timestamp(simulation_curve_start(strategy))
    live_since = pd.Timestamp(strategy["deployed_on"])
    cadence = int(strategy["rebalance_cadence_days"])
    cfg = costs.CostModel.from_spec(strategy["cost_model"])
    signal = strategy["signal"]
    tickers = list(closes.columns)
    market_rets = _market_returns(closes)

    sim_index = closes.loc[sim_start:].index
    if len(sim_index) == 0:
        raise ValueError(
            f"{strategy['id']}: no price bars on/after curve start {sim_start.date()}"
        )

    rebal_dates = set(_rebalance_dates(sim_index, sim_start, cadence))

    cash = capital
    shares = {t: 0.0 for t in tickers}
    pending_target: dict[str, float] = {}
    pending_cost = 0.0
    last_trades: list[dict] = []

    curve: list[dict] = []
    equity_values: list[float] = []

    for i, day in enumerate(sim_index):
        # Execute the previous rebalance's target at today's open, then charge
        # the Astralanx equity haircut computed on the review date.
        if pending_target and i > 0:
            equity_open = cash + _position_value(shares, opens.loc[day], tickers)
            shares, cash, trades = _apply_targets(
                pending_target, shares, cash, opens.loc[day], equity_open, tickers,
            )
            cash -= equity_open * pending_cost
            if trades:
                last_trades = [dict(d=day.strftime("%Y-%m-%d"), **tr) for tr in trades]
            pending_target = {}
            pending_cost = 0.0

        # Decide a new target on rebalance days (filled next open).
        if day in rebal_dates:
            target = signals.evaluate(signal, closes, day)
            equity_now = cash + _position_value(shares, closes.loc[day], tickers)
            prior_w = _current_weights(shares, closes.loc[day], equity_now, tickers)
            names = set(prior_w) | set(target)
            price, dvol = _review_maps(day, names, raw_closes, closes, dollar_volume)
            vol_mult = costs.volatility_cost_multiplier(market_rets.loc[:day].to_numpy(), cfg)
            pending_cost = costs.rebalance_cost_fraction(
                prior_w, target, price, dvol, cfg, vol_mult
            )["total_fraction"]
            pending_target = target

        equity_close = cash + _position_value(shares, closes.loc[day], tickers)
        equity_values.append(equity_close)
        curve.append({"d": day.strftime("%Y-%m-%d"), "v": round(equity_close, 2)})

    curve, equity = _stitch_curve(darwin_curve, curve)
    stats = _stats(equity)
    stats_backtest, stats_live = _split_stats(equity, live_since)
    positions = _latest_positions(shares, closes.iloc[-1], equity_values[-1], tickers)

    return SimResult(
        equity_curve=curve,
        stats=stats,
        positions=positions,
        trades=last_trades,
        as_of=equity.index[-1].strftime("%Y-%m-%d"),
        stats_backtest=stats_backtest,
        stats_live=stats_live,
    )


def _simulate_dsl(
    strategy: dict,
    opens: pd.DataFrame,
    closes: pd.DataFrame,
    prices_long: pd.DataFrame,
    dollar_volume: pd.DataFrame | None = None,
    raw_closes: pd.DataFrame | None = None,
) -> SimResult:
    """Simulate a real DSL king via the vendored evaluator.

    At each rebalance the formula is evaluated with the **drifted actual** prior
    weights and engine-faithful portfolio-state features (drawdown, trailing
    turnover/volatility/hit-rate), matching how Astralanx's backtest engine carries
    state. The returned `final_weights` are the target; fills happen at the next
    open under our cost model. See docs/subsystems/paper-trading-updater.md.
    """
    darwin_curve = _darwin_equity_curve(strategy)
    capital = _starting_capital(strategy, darwin_curve)
    sim_start = pd.Timestamp(simulation_curve_start(strategy))
    live_since = pd.Timestamp(strategy["deployed_on"])
    cadence = int(strategy["rebalance_cadence_days"])
    cfg = costs.CostModel.from_spec(strategy["cost_model"])
    formula = strategy["formula"]
    universe = list(closes.columns)
    market_rets = _market_returns(closes)

    sim_index = closes.loc[sim_start:].index
    if len(sim_index) == 0:
        raise ValueError(
            f"{strategy['id']}: no price bars on/after curve start {sim_start.date()}"
        )

    rebal_set = set(_rebalance_dates(sim_index, sim_start, cadence))
    needed_state = signals.formula_state_features(formula)

    state = ps.PortfolioState(capital)
    cash = capital
    shares = {t: 0.0 for t in universe}
    pending_target: dict[str, float] | None = None
    pending_cost = 0.0
    equity_at_prev_rebal: float | None = None
    last_trades: list[dict] = []

    curve: list[dict] = []
    equity_values: list[float] = []

    for i, day in enumerate(sim_index):
        # Execute the previous rebalance's target at today's open, then charge
        # the Astralanx equity haircut computed on the review date.
        if pending_target is not None and i > 0:
            equity_open = cash + _position_value(shares, opens.loc[day], universe)
            shares, cash, trades = _apply_targets(
                pending_target, shares, cash, opens.loc[day], equity_open, universe,
            )
            cash -= equity_open * pending_cost
            if trades:
                last_trades = [dict(d=day.strftime("%Y-%m-%d"), **tr) for tr in trades]
            pending_target = None
            pending_cost = 0.0

        # Rebalance decision on review days (filled at next open).
        if day in rebal_set:
            equity_now = cash + _position_value(shares, closes.loc[day], universe)

            # Close out the prior holding period's return + peak BEFORE reading
            # state, mirroring native_eval.c (peak updates at period end).
            if equity_at_prev_rebal is not None and equity_at_prev_rebal > 0:
                state.push_period_return(equity_now / equity_at_prev_rebal - 1.0)
                state.update_peak(equity_now)

            prior_w = _current_weights(shares, closes.loc[day], equity_now, universe)
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

            names = set(prior_w) | set(target)
            price, dvol = _review_maps(day, names, raw_closes, closes, dollar_volume)
            vol_mult = costs.volatility_cost_multiplier(market_rets.loc[:day].to_numpy(), cfg)
            pending_cost = costs.rebalance_cost_fraction(
                prior_w, target, price, dvol, cfg, vol_mult
            )["total_fraction"]
            pending_target = target
            equity_at_prev_rebal = equity_now

        equity_close = cash + _position_value(shares, closes.loc[day], universe)
        equity_values.append(equity_close)
        curve.append({"d": day.strftime("%Y-%m-%d"), "v": round(equity_close, 2)})

    curve, equity = _stitch_curve(darwin_curve, curve)
    stats = _stats(equity)
    stats_backtest, stats_live = _split_stats(equity, live_since)
    positions = _latest_positions(shares, closes.iloc[-1], equity_values[-1], universe)

    return SimResult(
        equity_curve=curve,
        stats=stats,
        positions=positions,
        trades=last_trades,
        as_of=equity.index[-1].strftime("%Y-%m-%d"),
        stats_backtest=stats_backtest,
        stats_live=stats_live,
    )


def _apply_targets(targets, shares, cash, open_px, equity, tickers):
    """Move holdings toward `targets` at today's open (cost-free fills).

    Fills happen at the open with no per-share slippage or commission — costs are
    charged separately as a Astralanx-style equity haircut (see `costs.py`), so the
    fill itself is equity-neutral. Returns (new_shares, new_cash, trades) where
    each trade records the *change in weight* for the ticker.
    """
    new_shares = dict(shares)
    trades: list[dict] = []

    for t in tickers:
        px = _finite_price(open_px, t)
        if px is None:
            continue
        cur_val = shares[t] * px
        cur_w = cur_val / equity if equity > 0 else 0.0
        tgt_w = targets.get(t, 0.0)
        delta_w = tgt_w - cur_w
        if abs(delta_w) < 1e-6:
            continue

        target_val = tgt_w * equity
        delta_val = target_val - cur_val
        qty = delta_val / px
        new_shares[t] = shares[t] + qty
        cash -= qty * px
        side = "buy" if delta_val > 0 else "sell"

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


def _split_stats(equity: pd.Series, live_since: pd.Timestamp) -> tuple[dict, dict]:
    """Stats for the pre-live (backtest) and post-live segments of the curve.

    The boundary point `live_since` is included in both segments as their anchor.
    A segment with fewer than 2 points yields all-zeros (see `_stats`).
    """
    backtest = _stats(equity.loc[:live_since])
    live = _stats(equity.loc[live_since:])
    return backtest, live


def _latest_positions(shares, close_px, equity, tickers) -> list[dict]:
    out = []
    for t in tickers:
        px = _finite_price(close_px, t)
        if px is None:
            continue
        val = shares[t] * px
        w = val / equity if equity > 0 else 0.0
        if w > 1e-4:
            out.append({"ticker": t, "weight": round(w, 4)})
    out.sort(key=lambda p: p["weight"], reverse=True)
    return out
