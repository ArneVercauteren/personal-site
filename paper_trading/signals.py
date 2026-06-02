"""Signal evaluation — the pure-Python "option A" evaluator.

Given a strategy's published `signal` block and price history up to a rebalance
date, return target ticker weights. This is a lightweight re-implementation of
the deployed formula's semantics, not an import of the Darwin engine — see
`docs/concepts/separation-from-darwin.md` and the plan's §7 "option A".

Only `visibility: "open"` strategies are evaluated here; their formulas are
public by design. Secured formulas never enter this repo.
"""

from __future__ import annotations

import pandas as pd

from . import portfolio_state as ps
from .darwin_eval.select_on_date import collect_all_needed_features, select_tickers_on_date

__all__ = [
    "evaluate",
    "evaluate_formula",
    "formula_state_features",
    "SignalError",
]


class SignalError(ValueError):
    """A strategy's signal block is malformed or unsupported."""


# ---------------------------------------------------------------------------
# DSL path — delegate to the vendored Darwin evaluator (real king formulas).
# ---------------------------------------------------------------------------


def formula_state_features(formula: dict) -> set[str]:
    """Portfolio-state feature names a DSL formula references.

    The simulator computes these (engine-faithful) and injects them at each
    rebalance — see `paper_trading.portfolio_state`.
    """
    needed = collect_all_needed_features(formula, include_exit_root=True)
    return {f for f in needed if ps.is_portfolio_state_feature(f)}


def evaluate_formula(
    formula: dict,
    *,
    prices_long: pd.DataFrame,
    asof: pd.Timestamp,
    universe: list[str],
    portfolio_size: float,
    prior_weights: dict[str, float] | None = None,
    prior_holdings: list[str] | None = None,
    portfolio_state_override: dict[str, float] | None = None,
    market_series: pd.Series | None = None,
    min_adv: float | None = None,
) -> dict:
    """Evaluate a real Darwin DSL formula on `asof` via the vendored evaluator.

    Returns the evaluator's full result dict (`final_weights`, `selected`,
    `scores`, ...). `prior_weights`/`prior_holdings` are the drifted actual
    holdings going into the rebalance; `portfolio_state_override` carries the
    engine-computed path-dependent features.
    """
    return select_tickers_on_date(
        strat_dict=formula,
        target_date=asof,
        tickers=universe,
        prices_override=prices_long,
        prior_weights=prior_weights or None,
        apply_exit_root_to=prior_holdings or None,
        portfolio_state_override=portfolio_state_override or None,
        portfolio_size=portfolio_size,
        market_series_override=market_series,
        min_adv=min_adv,
    )


def evaluate(signal: dict, closes: pd.DataFrame, asof: pd.Timestamp) -> dict[str, float]:
    """Evaluate `signal` using closes up to and including `asof`.

    Returns a mapping of ticker -> target weight (weights sum to <= 1.0; any
    remainder is implicitly held as cash). Returns an empty dict when no name
    qualifies (e.g. nothing has positive momentum), i.e. go to cash.
    """
    stype = signal.get("type")
    if stype == "cross_sectional_momentum":
        return _cross_sectional_momentum(signal, closes, asof)
    raise SignalError(f"unsupported signal type: {stype!r}")


def _cross_sectional_momentum(
    signal: dict, closes: pd.DataFrame, asof: pd.Timestamp
) -> dict[str, float]:
    """Rank the universe by trailing return and hold the top names.

    momentum(t) = close[asof - skip] / close[asof - skip - lookback] - 1

    The optional `skip_days` excludes the most recent bars (a standard momentum
    refinement that skips short-term reversal). Names with momentum below
    `min_momentum` are dropped; the survivors are taken `top_n` deep and weighted
    per `weighting` ("equal" or "proportional" to momentum).
    """
    lookback = int(signal["lookback_days"])
    skip = int(signal.get("skip_days", 0))
    top_n = int(signal["top_n"])
    min_mom = float(signal.get("min_momentum", 0.0))
    weighting = signal.get("weighting", "equal")

    hist = closes.loc[:asof]
    end_i = len(hist) - 1 - skip
    start_i = end_i - lookback
    if start_i < 0:
        # Not enough history yet — hold cash.
        return {}

    end_px = hist.iloc[end_i]
    start_px = hist.iloc[start_i]
    momentum = (end_px / start_px - 1.0).dropna()
    momentum = momentum[momentum > min_mom]
    if momentum.empty:
        return {}

    winners = momentum.sort_values(ascending=False).head(top_n)
    if weighting == "proportional":
        total = winners.sum()
        weights = winners / total if total > 0 else winners * 0
    elif weighting == "equal":
        weights = pd.Series(1.0 / len(winners), index=winners.index)
    else:
        raise SignalError(f"unsupported weighting: {weighting!r}")

    return {t: round(float(w), 6) for t, w in weights.items()}
