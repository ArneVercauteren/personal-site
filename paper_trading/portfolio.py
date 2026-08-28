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

from dataclasses import dataclass, field
import hashlib

import numpy as np
import pandas as pd

from . import costs
from . import portfolio_state as ps
from . import signals
from .contracts import CONTRACT_VERSION, ENGINE_VERSION, content_hash
from .ledger import make_event

__all__ = ["simulate", "simulate_incremental", "SimResult", "simulation_curve_start"]

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
    checkpoint: dict | None = None    # exact accounting state at ``as_of``
    ledger_events: list[dict] = field(default_factory=list)


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


def _impact_account_book(cfg, equity_now: float, base: float) -> float:
    """Total account book used to translate weight changes into trade dollars."""
    if base <= 0.0:
        return float(cfg.impact_portfolio_size)
    return float(cfg.impact_portfolio_size) * (float(equity_now) / float(base))


def _cap_target_weights(
    target: dict[str, float],
    cfg,
    equity_now: float,
    base: float,
) -> dict[str, float]:
    """Scale target weights so invested capital stays at or below capacity."""
    cap = float(getattr(cfg, "impact_book_cap", 0.0) or 0.0)
    if cap <= 0.0 or not target:
        return target
    invested_weight = sum(max(0.0, float(weight)) for weight in target.values())
    account_book = _impact_account_book(cfg, equity_now, base)
    target_dollars = invested_weight * account_book
    if target_dollars <= cap or target_dollars <= 0.0:
        return target
    scale = cap / target_dollars
    return {ticker: float(weight) * scale for ticker, weight in target.items()}


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


def _calendar_rebalance_dates(
    index: pd.DatetimeIndex,
    deployed_on: pd.Timestamp,
    cadence_days: int,
) -> list[pd.Timestamp]:
    """Legacy schedule: add calendar days, then snap to the next price bar."""
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


def _rebalance_dates(
    index: pd.DatetimeIndex,
    deployed_on: pd.Timestamp,
    cadence_days: int,
    *,
    cadence_unit: str = "calendar_days",
    transition_anchor: str | pd.Timestamp | None = None,
) -> list[pd.Timestamp]:
    """Return review dates on the supplied market-price index.

    ``calendar_days`` preserves the original behavior: add ordinary calendar
    days and snap weekends/holidays to the next available bar.

    ``trading_days`` counts entries in ``index``.  A strategy may supply a
    ``transition_anchor`` to preserve its already-published legacy schedule up
    to and including that review date, then count trading sessions from it.
    This makes cadence migrations forward-only instead of rewriting a live
    paper track record.
    """
    if cadence_days <= 0:
        raise ValueError("rebalance cadence must be positive")
    if len(index) == 0:
        return []
    if cadence_unit not in {"calendar_days", "trading_days"}:
        raise ValueError(
            "rebalance_cadence_unit must be 'calendar_days' or 'trading_days'"
        )
    if cadence_unit == "calendar_days":
        if transition_anchor is not None:
            raise ValueError(
                "rebalance_transition_anchor requires a trading_days cadence"
            )
        return _calendar_rebalance_dates(index, deployed_on, cadence_days)

    start_pos = int(index.searchsorted(deployed_on, side="left"))
    if start_pos >= len(index):
        return []
    if transition_anchor is None:
        return list(index[start_pos::cadence_days])

    anchor = pd.Timestamp(transition_anchor).normalize()
    anchor_pos = int(index.searchsorted(anchor, side="left"))
    if anchor_pos >= len(index) or index[anchor_pos].normalize() != anchor:
        raise ValueError(
            f"rebalance_transition_anchor {anchor.date()} is not in the price index"
        )

    legacy = _calendar_rebalance_dates(index, deployed_on, cadence_days)
    if anchor not in legacy:
        raise ValueError(
            f"rebalance_transition_anchor {anchor.date()} is not a legacy review date"
        )
    preserved = [day for day in legacy if day <= anchor]
    future = list(index[anchor_pos + cadence_days :: cadence_days])
    return preserved + future


def _strategy_rebalance_dates(
    index: pd.DatetimeIndex,
    sim_start: pd.Timestamp,
    strategy: dict,
) -> list[pd.Timestamp]:
    """Resolve a strategy's backward-compatible cadence configuration."""
    return _rebalance_dates(
        index,
        sim_start,
        int(strategy["rebalance_cadence_days"]),
        cadence_unit=strategy.get("rebalance_cadence_unit", "calendar_days"),
        transition_anchor=strategy.get("rebalance_transition_anchor"),
    )


def _market_returns(closes: pd.DataFrame) -> pd.Series:
    """Equal-weighted market daily-return proxy (mean across tickers).

    Feeds the volatility cost multiplier, mirroring Astralanx's market proxy
    (`nanmean` of per-ticker returns) in `cost_models.py`.
    """
    return closes.pct_change().mean(axis=1)


def _review_maps(day, names, raw_closes, closes, dollar_volume, impact_volatility=None):
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
    volatility = None
    if impact_volatility is not None:
        volatility = {}
        for ticker in names:
            if ticker in impact_volatility.columns and day in impact_volatility.index:
                value = impact_volatility.at[day, ticker]
                volatility[ticker] = float(value) if pd.notna(value) else None
            else:
                volatility[ticker] = None
    return price, dvol, volatility


def _impact_inputs(
    closes: pd.DataFrame,
    dollar_volume: pd.DataFrame | None,
    cfg: costs.CostModel,
) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Causal rolling ADV and daily volatility used by Darwin's impact model."""
    if dollar_volume is None:
        return None, None
    # Specs exported before the sliced-execution contract used review-day
    # dollar volume directly. Keep that path byte-for-byte compatible; only
    # an explicit positive execution_max_days opts a strategy into Darwin's
    # rolling, lagged liquidity and volatility inputs.
    if cfg.execution_max_days <= 0:
        return dollar_volume, None
    lookback = max(1, int(cfg.impact_lookback_days))
    adv = dollar_volume.rolling(window=lookback, min_periods=lookback).median().shift(1)
    volatility = (
        closes.pct_change(fill_method=None)
        .rolling(window=lookback, min_periods=lookback)
        .std()
        .shift(1)
    )
    return adv, volatility


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


def _price_snapshot_id(day: pd.Timestamp, row, tickers: list[str]) -> str:
    prices = {}
    for ticker in tickers:
        value = _finite_price(row, ticker)
        if value is not None:
            prices[ticker] = round(value, 8)
    return content_hash({"session": day.strftime("%Y-%m-%d"), "closes": prices})


class BoundaryPriceUnavailable(ValueError):
    """A held position lacks the accepted boundary price; a later retry may recover it."""


class BoundaryPriceRevision(ValueError):
    """Prices affecting accepted boundary accounting changed and need review."""

    def __init__(self, message: str, details: dict):
        super().__init__(message)
        self.details = details


def _held_checkpoint_tickers(checkpoint: dict) -> list[str]:
    return sorted(
        ticker
        for ticker, quantity in checkpoint.get("shares", {}).items()
        if abs(float(quantity)) > 1e-12
    )


def _verify_checkpoint_prices(checkpoint: dict, row, tolerance: float = 0.02) -> None:
    """Verify only prices that can affect the accepted account boundary.

    Legacy checkpoints hashed the entire research universe. If that broad hash
    changes, accept the transition only when every held price is present and the
    held book still reconciles exactly to accepted equity. New checkpoints hash
    held positions directly, so any mismatch is a genuine accounting revision.
    """

    held = _held_checkpoint_tickers(checkpoint)
    missing = [ticker for ticker in held if _finite_price(row, ticker) is None]
    if missing:
        raise BoundaryPriceUnavailable(
            "missing accepted-boundary prices for held positions: " + ", ".join(missing)
        )

    snapshot_tickers = list(checkpoint.get("price_tickers") or held)
    observed = _price_snapshot_id(
        pd.Timestamp(checkpoint["last_processed_session"]), row, snapshot_tickers,
    )
    if observed == checkpoint["price_snapshot_id"]:
        return

    if checkpoint.get("price_snapshot_scope") != "held_positions_v1":
        marked = float(checkpoint["cash"]) + _position_value(
            checkpoint["shares"], row, held,
        )
        if abs(marked - float(checkpoint["equity"])) <= tolerance:
            return
    else:
        marked = float(checkpoint["cash"]) + _position_value(
            checkpoint["shares"], row, held,
        )

    raise BoundaryPriceRevision(
        "held-position prices no longer reconcile to the accepted boundary",
        {
            "kind": "price_revision",
            "expected_price_snapshot_id": checkpoint["price_snapshot_id"],
            "observed_price_snapshot_id": observed,
            "accepted_equity": float(checkpoint["equity"]),
            # Rounded so the proposal payload — and therefore its stable event id —
            # is identical across runs. Summation order over the held book is not
            # bit-stable, and raw floats made two identical revisions look like two
            # distinct proposals.
            "observed_equity": round(marked, 6),
            "price_snapshot_scope": checkpoint.get(
                "price_snapshot_scope", "legacy_universe_v1"
            ),
        },
    )


def _review_price_snapshot_id(
    day: pd.Timestamp,
    close_row,
    tickers: list[str],
    prices_long: pd.DataFrame | None,
) -> str:
    """Hash the exact causal OHLCV frame supplied to a formula review."""
    if prices_long is None:
        return _price_snapshot_id(day, close_row, tickers)
    columns = [
        column for column in ("date", "ticker", "open", "high", "low", "close", "adj_close", "volume")
        if column in prices_long.columns
    ]
    frame = prices_long[
        (prices_long["date"] <= day) & prices_long["ticker"].isin(tickers)
    ][columns].sort_values(["date", "ticker"], kind="stable").copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    digest = hashlib.sha256()
    digest.update("ohlcv-v1\n".encode())
    digest.update("|".join(columns).encode())
    digest.update(pd.util.hash_pandas_object(frame, index=False).to_numpy().tobytes())
    return digest.hexdigest()


def _nonzero_shares(shares: dict[str, float]) -> dict[str, float]:
    return {
        ticker: round(float(quantity), 12)
        for ticker, quantity in sorted(shares.items())
        if abs(float(quantity)) > 1e-12
    }


def _checkpoint(
    strategy: dict,
    *,
    day: pd.Timestamp,
    cash: float,
    shares: dict[str, float],
    equity: float,
    peak_equity: float,
    state: ps.PortfolioState,
    pending_target: dict[str, float] | None,
    pending_cost: float,
    equity_at_prev_rebal: float | None,
    last_review: str | None,
    sessions_until_review: int | None,
    universe: list[str],
    price_row,
    universe_snapshot_id: str | None = None,
) -> dict:
    formula = strategy.get("formula") or strategy.get("signal") or {}
    held_tickers = sorted(_nonzero_shares(shares))
    return {
        "schema_version": CONTRACT_VERSION,
        "strategy_id": strategy["id"],
        "last_processed_session": day.strftime("%Y-%m-%d"),
        "cash": float(cash),
        "shares": {
            ticker: float(quantity)
            for ticker, quantity in sorted(shares.items())
            if abs(float(quantity)) > 1e-12
        },
        "equity": float(equity),
        "peak_equity": float(peak_equity),
        "portfolio_state": state.to_dict(),
        "pending_target": dict(sorted((pending_target or {}).items())),
        "pending_cost_fraction": float(pending_cost),
        "equity_at_previous_review": equity_at_prev_rebal,
        "last_review_session": last_review,
        "sessions_until_review": sessions_until_review,
        "deployment_hash": content_hash({
            key: strategy.get(key)
            for key in (
                "id", "visibility", "deployed_on", "portfolio_size", "base_currency",
                "rebalance_cadence_days", "rebalance_cadence_unit",
                "rebalance_transition_anchor", "cost_model", "formula", "signal",
            )
        }),
        "formula_hash": content_hash(formula),
        "universe_snapshot_id": (
            universe_snapshot_id
            or strategy.get("_universe_snapshot_id")
            or content_hash(sorted(universe))
        ),
        "price_snapshot_id": _price_snapshot_id(day, price_row, held_tickers),
        "price_snapshot_scope": "held_positions_v1",
        "price_tickers": held_tickers,
        "cost_model_hash": content_hash(strategy["cost_model"]),
        "engine_version": ENGINE_VERSION,
    }


def _sessions_until_next_review(
    sim_index: pd.DatetimeIndex,
    rebal_dates: list[pd.Timestamp],
    cadence_days: int,
    cadence_unit: str,
) -> int | None:
    if cadence_unit != "trading_days" or not rebal_dates:
        return None
    last_review = rebal_dates[-1]
    observed_after = int((sim_index > last_review).sum())
    return max(0, cadence_days - observed_after)


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

    When the spec's `cost_model` carries `impact_book_cap`, target weights are
    scaled so invested capital stays at or below capacity and excess equity
    remains cash, matching how Astralanx generated the curve prefix.
    """
    if "formula" in strategy:
        if prices_long is None:
            raise ValueError(
                f"{strategy['id']}: DSL strategies require prices_long (long OHLCV)."
            )
        return _simulate_dsl(strategy, opens, closes, prices_long, dollar_volume, raw_closes)
    return _simulate_signal(strategy, opens, closes, dollar_volume, raw_closes)


def simulate_incremental(
    strategy: dict,
    checkpoint: dict,
    prior_curve: list[dict],
    opens: pd.DataFrame,
    closes: pd.DataFrame,
    prices_long: pd.DataFrame | None = None,
    dollar_volume: pd.DataFrame | None = None,
    raw_closes: pd.DataFrame | None = None,
    active_universe: list[str] | None = None,
) -> SimResult:
    """Advance an accepted checkpoint across unseen sessions only.

    Historical accounting comes exclusively from ``checkpoint`` and
    ``prior_curve``.  Older bars may be supplied as causal feature warm-up, but
    are never replayed or rewritten.  A same-session price revision is rejected
    so the caller can publish a correction proposal instead of silently
    mutating the record.
    """
    if checkpoint.get("strategy_id") != strategy["id"]:
        raise ValueError("checkpoint strategy does not match spec")
    if strategy.get("rebalance_cadence_unit", "calendar_days") != "trading_days":
        raise ValueError("incremental updates require a trading_days cadence")
    if "formula" in strategy and prices_long is None:
        raise ValueError(f"{strategy['id']}: DSL strategies require prices_long")

    expected = _checkpoint_hashes(strategy)
    for key, value in expected.items():
        if checkpoint.get(key) != value:
            raise ValueError(f"{strategy['id']}: accepted checkpoint {key} no longer matches spec")

    last = pd.Timestamp(checkpoint["last_processed_session"])
    if last not in closes.index:
        raise ValueError(f"{strategy['id']}: checkpoint session {last.date()} is absent from prices")
    _verify_checkpoint_prices(checkpoint, closes.loc[last])

    existing = list(prior_curve)
    if not existing or existing[-1]["d"] != last.strftime("%Y-%m-%d"):
        raise ValueError("published curve does not end at the accepted checkpoint")

    new_index = closes.index[closes.index > last]
    tickers = list(closes.columns)
    decision_universe = list(active_universe or tickers)
    cash = float(checkpoint["cash"])
    shares = {ticker: float(checkpoint["shares"].get(ticker, 0.0)) for ticker in tickers}
    pending_target = {
        ticker: float(weight) for ticker, weight in checkpoint.get("pending_target", {}).items()
    }
    pending_cost = float(checkpoint.get("pending_cost_fraction", 0.0))
    equity_at_prev_rebal = checkpoint.get("equity_at_previous_review")
    state = ps.PortfolioState.from_dict(checkpoint["portfolio_state"])
    account_peak = float(checkpoint["peak_equity"])
    last_review = checkpoint.get("last_review_session")
    decision_universe_snapshot_id = checkpoint["universe_snapshot_id"]
    remaining = checkpoint.get("sessions_until_review")
    if remaining is None:
        raise ValueError("incremental trading-day checkpoint lacks sessions_until_review")
    remaining = int(remaining)
    cadence = int(strategy["rebalance_cadence_days"])
    cfg = costs.CostModel.from_spec(strategy["cost_model"])
    impact_base = float(strategy["portfolio_size"])
    market_rets = _market_returns(closes)
    impact_adv, impact_volatility = _impact_inputs(closes, dollar_volume, cfg)
    needed_state = signals.formula_state_features(strategy["formula"]) if "formula" in strategy else set()
    live_since = pd.Timestamp(strategy["deployed_on"])
    ledger_events: list[dict] = []
    tail: list[dict] = []
    last_trades: list[dict] = []
    final_equity = float(checkpoint["equity"])

    for day in new_index:
        session = day.strftime("%Y-%m-%d")
        if pending_target:
            equity_open = cash + _position_value(shares, opens.loc[day], tickers)
            shares, cash, trades = _apply_targets(
                pending_target, shares, cash, opens.loc[day], equity_open, tickers,
            )
            cash -= equity_open * pending_cost
            if trades:
                last_trades = [dict(d=session, **trade) for trade in trades]
                ledger_events.append(make_event(
                    strategy["id"], "fills_applied", session,
                    {
                        "trades": last_trades, "equity_open": round(equity_open, 8),
                        "cash_after": round(cash, 8), "shares_after": _nonzero_shares(shares),
                    },
                ))
            if pending_cost:
                ledger_events.append(make_event(
                    strategy["id"], "costs_charged", session,
                    {"fraction": pending_cost, "amount": equity_open * pending_cost},
                ))
            pending_target = {}
            pending_cost = 0.0

        remaining -= 1
        if remaining <= 0:
            equity_now = cash + _position_value(shares, closes.loc[day], tickers)
            prior_w = _current_weights(shares, closes.loc[day], equity_now, tickers)
            if "formula" in strategy:
                if equity_at_prev_rebal is not None and float(equity_at_prev_rebal) > 0:
                    state.push_period_return(equity_now / float(equity_at_prev_rebal) - 1.0)
                    state.update_peak(equity_now)
                override = state.scalars_for(needed_state, equity=equity_now, weights=prior_w)
                evaluated = signals.evaluate_formula(
                    strategy["formula"], prices_long=prices_long, asof=day,
                    universe=decision_universe, portfolio_size=float(strategy["portfolio_size"]),
                    prior_weights=prior_w, prior_holdings=list(prior_w),
                    portfolio_state_override=override,
                )
                target = {
                    ticker: float(weight)
                    for ticker, weight in evaluated["final_weights"].items()
                    if weight > 0
                }
                state.push_turnover(target, prior_w)
            else:
                target = signals.evaluate(strategy["signal"], closes[decision_universe], day)
            target = _cap_target_weights(target, cfg, equity_now, impact_base)
            names = set(prior_w) | set(target)
            review_price, review_adv, review_vol = _review_maps(
                day, names, raw_closes, closes, impact_adv, impact_volatility,
            )
            multiplier = costs.volatility_cost_multiplier(market_rets.loc[:day].to_numpy(), cfg)
            pending_cost = costs.rebalance_cost_fraction(
                prior_w, target, review_price, review_adv, cfg, multiplier,
                impact_book=_impact_account_book(cfg, equity_now, impact_base),
                review_daily_volatility=review_vol,
            )["total_fraction"]
            pending_target = target
            equity_at_prev_rebal = equity_now
            last_review = session
            remaining = cadence
            decision_universe_snapshot_id = (
                strategy.get("_universe_snapshot_id")
                or content_hash(sorted(decision_universe))
            )
            common = {
                "formula_hash": expected["formula_hash"],
                "cost_model_hash": expected["cost_model_hash"],
                "universe_snapshot_id": decision_universe_snapshot_id,
                "price_snapshot_id": _review_price_snapshot_id(
                    day, closes.loc[day], decision_universe, prices_long,
                ),
            }
            ledger_events.append(make_event(strategy["id"], "rebalance_reviewed", session, common))
            ledger_events.append(make_event(
                strategy["id"], "targets_computed", session,
                {**common, "weights": dict(sorted(target.items()))},
            ))

        equity_close = cash + _position_value(shares, closes.loc[day], tickers)
        final_equity = equity_close
        account_peak = max(account_peak, equity_close)
        tail.append({"d": session, "v": round(equity_close, 2)})
        ledger_events.append(make_event(
            strategy["id"], "session_marked", session,
            {
                "equity": round(equity_close, 8), "cash": round(cash, 8),
                "shares": _nonzero_shares(shares),
                "price_snapshot_id": _price_snapshot_id(
                    day, closes.loc[day], sorted(_nonzero_shares(shares)),
                ),
            },
        ))

    curve = existing + tail
    equity = pd.Series(
        [float(point["v"]) for point in curve],
        index=pd.DatetimeIndex([pd.Timestamp(point["d"]) for point in curve]),
    )
    final_day = new_index[-1] if len(new_index) else last
    final_checkpoint = dict(checkpoint)
    if len(new_index):
        final_checkpoint = _checkpoint(
            strategy, day=final_day, cash=cash, shares=shares, equity=final_equity,
            peak_equity=account_peak, state=state, pending_target=pending_target,
            pending_cost=pending_cost, equity_at_prev_rebal=equity_at_prev_rebal,
            last_review=last_review, sessions_until_review=remaining,
            universe=tickers,
            price_row=closes.loc[final_day],
            universe_snapshot_id=decision_universe_snapshot_id,
        )
    positions = _latest_positions(shares, closes.loc[final_day], final_equity, tickers)
    stats_backtest, stats_live = _split_stats(equity, live_since)
    return SimResult(
        equity_curve=curve, stats=_stats(equity), positions=positions,
        trades=last_trades, as_of=final_day.strftime("%Y-%m-%d"),
        stats_backtest=stats_backtest, stats_live=stats_live,
        checkpoint=final_checkpoint, ledger_events=ledger_events,
    )


def _checkpoint_hashes(strategy: dict) -> dict[str, str]:
    formula = strategy.get("formula") or strategy.get("signal") or {}
    return {
        "deployment_hash": content_hash({
            key: strategy.get(key)
            for key in (
                "id", "visibility", "deployed_on", "portfolio_size", "base_currency",
                "rebalance_cadence_days", "rebalance_cadence_unit",
                "rebalance_transition_anchor", "cost_model", "formula", "signal",
            )
        }),
        "formula_hash": content_hash(formula),
        "cost_model_hash": content_hash(strategy["cost_model"]),
        "engine_version": ENGINE_VERSION,
    }


def _simulate_signal(
    strategy: dict,
    opens: pd.DataFrame,
    closes: pd.DataFrame,
    dollar_volume: pd.DataFrame | None = None,
    raw_closes: pd.DataFrame | None = None,
) -> SimResult:
    darwin_curve = _darwin_equity_curve(strategy)
    capital = _starting_capital(strategy, darwin_curve)
    impact_base = float(strategy["portfolio_size"])
    sim_start = pd.Timestamp(simulation_curve_start(strategy))
    live_since = pd.Timestamp(strategy["deployed_on"])
    cfg = costs.CostModel.from_spec(strategy["cost_model"])
    signal = strategy["signal"]
    tickers = list(closes.columns)
    market_rets = _market_returns(closes)
    impact_adv, impact_volatility = _impact_inputs(closes, dollar_volume, cfg)

    sim_index = closes.loc[sim_start:].index
    if len(sim_index) == 0:
        raise ValueError(
            f"{strategy['id']}: no price bars on/after curve start {sim_start.date()}"
        )

    review_dates = _strategy_rebalance_dates(sim_index, sim_start, strategy)
    rebal_dates = set(review_dates)

    cash = capital
    shares = {t: 0.0 for t in tickers}
    pending_target: dict[str, float] = {}
    pending_cost = 0.0
    last_trades: list[dict] = []
    state = ps.PortfolioState(capital)
    account_peak = capital
    ledger_events: list[dict] = []

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
                if day >= live_since:
                    ledger_events.append(make_event(
                        strategy["id"], "fills_applied", day.strftime("%Y-%m-%d"),
                        {
                            "trades": last_trades, "equity_open": round(equity_open, 8),
                            "cash_after": round(cash, 8), "shares_after": _nonzero_shares(shares),
                        },
                    ))
            if pending_cost and day >= live_since:
                ledger_events.append(make_event(
                    strategy["id"], "costs_charged", day.strftime("%Y-%m-%d"),
                    {"fraction": pending_cost, "amount": equity_open * pending_cost},
                ))
            pending_target = {}
            pending_cost = 0.0

        # Decide a new target on rebalance days (filled next open).
        if day in rebal_dates:
            target = signals.evaluate(signal, closes, day)
            equity_now = cash + _position_value(shares, closes.loc[day], tickers)
            target = _cap_target_weights(target, cfg, equity_now, impact_base)
            prior_w = _current_weights(shares, closes.loc[day], equity_now, tickers)
            names = set(prior_w) | set(target)
            price, dvol, daily_vol = _review_maps(
                day, names, raw_closes, closes, impact_adv, impact_volatility,
            )
            vol_mult = costs.volatility_cost_multiplier(market_rets.loc[:day].to_numpy(), cfg)
            pending_cost = costs.rebalance_cost_fraction(
                prior_w, target, price, dvol, cfg, vol_mult,
                impact_book=_impact_account_book(cfg, equity_now, impact_base),
                review_daily_volatility=daily_vol,
            )["total_fraction"]
            pending_target = target
            if day >= live_since:
                session = day.strftime("%Y-%m-%d")
                common = {
                    "formula_hash": content_hash(strategy.get("formula") or strategy.get("signal")),
                    "cost_model_hash": content_hash(strategy["cost_model"]),
                    "universe_snapshot_id": strategy.get("_universe_snapshot_id") or content_hash(sorted(tickers)),
                    "price_snapshot_id": _review_price_snapshot_id(
                        day, closes.loc[day], tickers, None,
                    ),
                }
                ledger_events.append(make_event(
                    strategy["id"], "rebalance_reviewed", session, common,
                ))
                ledger_events.append(make_event(
                    strategy["id"], "targets_computed", session,
                    {**common, "weights": dict(sorted(target.items()))},
                ))

        equity_close = cash + _position_value(shares, closes.loc[day], tickers)
        account_peak = max(account_peak, equity_close)
        equity_values.append(equity_close)
        curve.append({"d": day.strftime("%Y-%m-%d"), "v": round(equity_close, 2)})
        if day >= live_since:
            ledger_events.append(make_event(
                strategy["id"], "session_marked", day.strftime("%Y-%m-%d"),
                {
                    "equity": round(equity_close, 8),
                    "cash": round(cash, 8), "shares": _nonzero_shares(shares),
                    "price_snapshot_id": _price_snapshot_id(
                        day, closes.loc[day], sorted(_nonzero_shares(shares)),
                    ),
                },
            ))

    curve, equity = _stitch_curve(darwin_curve, curve)
    stats = _stats(equity)
    stats_backtest, stats_live = _split_stats(equity, live_since)
    positions = _latest_positions(shares, closes.iloc[-1], equity_values[-1], tickers)

    final_day = sim_index[-1]
    checkpoint = _checkpoint(
        strategy,
        day=final_day,
        cash=cash,
        shares=shares,
        equity=equity_values[-1],
        peak_equity=account_peak,
        state=state,
        pending_target=pending_target,
        pending_cost=pending_cost,
        equity_at_prev_rebal=None,
        last_review=review_dates[-1].strftime("%Y-%m-%d") if review_dates else None,
        sessions_until_review=_sessions_until_next_review(
            sim_index, review_dates, int(strategy["rebalance_cadence_days"]),
            strategy.get("rebalance_cadence_unit", "calendar_days"),
        ),
        universe=tickers,
        price_row=closes.loc[final_day],
    )
    return SimResult(
        equity_curve=curve,
        stats=stats,
        positions=positions,
        trades=last_trades,
        as_of=equity.index[-1].strftime("%Y-%m-%d"),
        stats_backtest=stats_backtest,
        stats_live=stats_live,
        checkpoint=checkpoint,
        ledger_events=ledger_events,
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
    impact_base = float(strategy["portfolio_size"])
    sim_start = pd.Timestamp(simulation_curve_start(strategy))
    live_since = pd.Timestamp(strategy["deployed_on"])
    cfg = costs.CostModel.from_spec(strategy["cost_model"])
    formula = strategy["formula"]
    universe = list(closes.columns)
    market_rets = _market_returns(closes)
    impact_adv, impact_volatility = _impact_inputs(closes, dollar_volume, cfg)

    sim_index = closes.loc[sim_start:].index
    if len(sim_index) == 0:
        raise ValueError(
            f"{strategy['id']}: no price bars on/after curve start {sim_start.date()}"
        )

    review_dates = _strategy_rebalance_dates(sim_index, sim_start, strategy)
    rebal_set = set(review_dates)
    needed_state = signals.formula_state_features(formula)

    state = ps.PortfolioState(capital)
    cash = capital
    shares = {t: 0.0 for t in universe}
    pending_target: dict[str, float] | None = None
    pending_cost = 0.0
    equity_at_prev_rebal: float | None = None
    last_trades: list[dict] = []
    account_peak = capital
    ledger_events: list[dict] = []

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
                if day >= live_since:
                    ledger_events.append(make_event(
                        strategy["id"], "fills_applied", day.strftime("%Y-%m-%d"),
                        {
                            "trades": last_trades, "equity_open": round(equity_open, 8),
                            "cash_after": round(cash, 8), "shares_after": _nonzero_shares(shares),
                        },
                    ))
            if pending_cost and day >= live_since:
                ledger_events.append(make_event(
                    strategy["id"], "costs_charged", day.strftime("%Y-%m-%d"),
                    {"fraction": pending_cost, "amount": equity_open * pending_cost},
                ))
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
            target = _cap_target_weights(target, cfg, equity_now, impact_base)
            state.push_turnover(target, prior_w)

            names = set(prior_w) | set(target)
            price, dvol, daily_vol = _review_maps(
                day, names, raw_closes, closes, impact_adv, impact_volatility,
            )
            vol_mult = costs.volatility_cost_multiplier(market_rets.loc[:day].to_numpy(), cfg)
            pending_cost = costs.rebalance_cost_fraction(
                prior_w, target, price, dvol, cfg, vol_mult,
                impact_book=_impact_account_book(cfg, equity_now, impact_base),
                review_daily_volatility=daily_vol,
            )["total_fraction"]
            pending_target = target
            equity_at_prev_rebal = equity_now
            if day >= live_since:
                session = day.strftime("%Y-%m-%d")
                common = {
                    "formula_hash": content_hash(formula),
                    "cost_model_hash": content_hash(strategy["cost_model"]),
                    "universe_snapshot_id": strategy.get("_universe_snapshot_id") or content_hash(sorted(universe)),
                    "price_snapshot_id": _review_price_snapshot_id(
                        day, closes.loc[day], universe, prices_long,
                    ),
                }
                ledger_events.append(make_event(
                    strategy["id"], "rebalance_reviewed", session, common,
                ))
                ledger_events.append(make_event(
                    strategy["id"], "targets_computed", session,
                    {**common, "weights": dict(sorted(target.items()))},
                ))

        equity_close = cash + _position_value(shares, closes.loc[day], universe)
        account_peak = max(account_peak, equity_close)
        equity_values.append(equity_close)
        curve.append({"d": day.strftime("%Y-%m-%d"), "v": round(equity_close, 2)})
        if day >= live_since:
            ledger_events.append(make_event(
                strategy["id"], "session_marked", day.strftime("%Y-%m-%d"),
                {
                    "equity": round(equity_close, 8),
                    "cash": round(cash, 8), "shares": _nonzero_shares(shares),
                    "price_snapshot_id": _price_snapshot_id(
                        day, closes.loc[day], sorted(_nonzero_shares(shares)),
                    ),
                },
            ))

    curve, equity = _stitch_curve(darwin_curve, curve)
    stats = _stats(equity)
    stats_backtest, stats_live = _split_stats(equity, live_since)
    positions = _latest_positions(shares, closes.iloc[-1], equity_values[-1], universe)

    final_day = sim_index[-1]
    checkpoint = _checkpoint(
        strategy,
        day=final_day,
        cash=cash,
        shares=shares,
        equity=equity_values[-1],
        peak_equity=account_peak,
        state=state,
        pending_target=pending_target,
        pending_cost=pending_cost,
        equity_at_prev_rebal=equity_at_prev_rebal,
        last_review=review_dates[-1].strftime("%Y-%m-%d") if review_dates else None,
        sessions_until_review=_sessions_until_next_review(
            sim_index, review_dates, int(strategy["rebalance_cadence_days"]),
            strategy.get("rebalance_cadence_unit", "calendar_days"),
        ),
        universe=universe,
        price_row=closes.loc[final_day],
    )
    return SimResult(
        equity_curve=curve,
        stats=stats,
        positions=positions,
        trades=last_trades,
        as_of=equity.index[-1].strftime("%Y-%m-%d"),
        stats_backtest=stats_backtest,
        stats_live=stats_live,
        checkpoint=checkpoint,
        ledger_events=ledger_events,
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

        trades.append({
            "ticker": t,
            "side": side,
            "weight": round(abs(delta_w), 4),
            "target_weight": round(float(tgt_w), 8),
            "quantity": round(float(qty), 12),
            "price": round(float(px), 8),
            "notional": round(abs(float(delta_val)), 8),
        })

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
