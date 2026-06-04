"""Engine-faithful portfolio-state features.

Path-dependent DSL features (drawdown, invested fraction, trailing turnover /
volatility / hit-rate, ...) are computed at runtime during a backtest, not
stored in the feature store. The authoritative implementation is Astralanx's
native engine (`src/native/native_eval.c`); this module ports its exact
semantics into Python so the paper simulator feeds a deployed king the same
state inputs the engine would.

Ported definitions (native_eval.c):
  * ring buffers cap at `HISTORY_CAP = 64`; window stats look back
    `min(window, count)` entries (`_history_mean_last` / `_history_std_last` /
    `_history_hit_rate_last`).
  * `trailing_portfolio_turnover_N`  = mean of last N period turnovers.
  * `trailing_portfolio_volatility_N`= sample std (÷(n−1)) of last N period returns.
  * `recent_hit_rate_N`              = fraction of last N period returns > 0.
  * `current_portfolio_drawdown`     = (peak−equity)/peak if equity<peak else 0.
  * `invested_fraction`              = Σ positive weights, clamped [0,1].
  * `cash_fraction`                  = 1 − invested, clamped ≥ 0.
  * `current_holdings_count`         = # positions with positive weight.

Turnover for a period is Σ|curr_w − prev_w| over the union of tickers, pushed at
the rebalance; the period return is pushed when the holding period closes; the
equity peak updates at period end. The "prior weights" into each rebalance are
the buy-and-hold *drifted* weights, exactly as the engine carries them.
"""

from __future__ import annotations

import math
import re
from collections import deque

HISTORY_CAP = 64

_TURNOVER_RE = re.compile(r"^trailing_portfolio_turnover_(\d+)$")
_VOLATILITY_RE = re.compile(r"^trailing_portfolio_volatility_(\d+)$")
_HIT_RATE_RE = re.compile(r"^recent_hit_rate_(\d+)$")

_WINDOWLESS = {
    "current_portfolio_drawdown",
    "current_holdings_count",
    "invested_fraction",
    "cash_fraction",
}


def is_portfolio_state_feature(name: str) -> bool:
    """True if `name` is any portfolio-state feature (windowless or windowed)."""
    return (
        name in _WINDOWLESS
        or _TURNOVER_RE.match(name) is not None
        or _VOLATILITY_RE.match(name) is not None
        or _HIT_RATE_RE.match(name) is not None
    )


def _mean_last(buf: deque[float], window: int) -> float:
    n = len(buf)
    if n <= 0 or window <= 0:
        return 0.0
    use_n = min(window, n)
    vals = list(buf)[-use_n:]
    return math.fsum(vals) / use_n


def _std_last(buf: deque[float], window: int) -> float:
    n = len(buf)
    if n <= 1 or window <= 1:
        return 0.0
    use_n = min(window, n)
    if use_n <= 1:
        return 0.0
    vals = list(buf)[-use_n:]
    mean = math.fsum(vals) / use_n
    sum_sq = math.fsum((v - mean) ** 2 for v in vals)
    return math.sqrt(sum_sq / (use_n - 1))


def _hit_rate_last(buf: deque[float], window: int) -> float:
    n = len(buf)
    if n <= 0 or window <= 0:
        return 0.0
    use_n = min(window, n)
    vals = list(buf)[-use_n:]
    hits = sum(1 for v in vals if v > 0.0)
    return hits / use_n


class PortfolioState:
    """Carries the engine-style portfolio state across a simulation."""

    def __init__(self, initial_equity: float) -> None:
        self.peak_equity = float(initial_equity)
        self.turnover_hist: deque[float] = deque(maxlen=HISTORY_CAP)
        self.period_return_hist: deque[float] = deque(maxlen=HISTORY_CAP)

    # -- updates (called by the simulator) ---------------------------------

    def push_turnover(self, curr_w: dict[str, float], prev_w: dict[str, float]) -> float:
        """Push this period's turnover = Σ|curr_w − prev_w| and return it."""
        tickers = set(curr_w) | set(prev_w)
        turnover = math.fsum(abs(curr_w.get(t, 0.0) - prev_w.get(t, 0.0)) for t in tickers)
        self.turnover_hist.append(turnover)
        return turnover

    def push_period_return(self, period_return: float) -> None:
        self.period_return_hist.append(float(period_return))

    def update_peak(self, equity: float) -> None:
        if equity > self.peak_equity:
            self.peak_equity = float(equity)

    # -- feature reads (injected into the evaluator) -----------------------

    def drawdown(self, equity: float) -> float:
        if self.peak_equity > 1e-12 and equity < self.peak_equity:
            return (self.peak_equity - equity) / self.peak_equity
        return 0.0

    def scalars_for(
        self,
        needed: set[str],
        *,
        equity: float,
        weights: dict[str, float],
    ) -> dict[str, float]:
        """Compute the requested portfolio-state features by exact name.

        `weights` are the *actual* (un-normalized, drifted) holdings going into
        the rebalance — matching the engine, where invested_fraction can be < 1.
        Only the names present in `needed` are computed.
        """
        invested = math.fsum(w for w in weights.values() if math.isfinite(w) and w > 0.0)
        invested = min(max(invested, 0.0), 1.0)
        holdings_count = float(sum(1 for w in weights.values() if math.isfinite(w) and w > 0.0))

        out: dict[str, float] = {}
        for name in needed:
            if name == "current_portfolio_drawdown":
                out[name] = self.drawdown(equity)
            elif name == "invested_fraction":
                out[name] = invested
            elif name == "cash_fraction":
                out[name] = max(0.0, 1.0 - invested)
            elif name == "current_holdings_count":
                out[name] = holdings_count
            else:
                m = _TURNOVER_RE.match(name)
                if m:
                    out[name] = _mean_last(self.turnover_hist, int(m.group(1)))
                    continue
                m = _VOLATILITY_RE.match(name)
                if m:
                    out[name] = _std_last(self.period_return_hist, int(m.group(1)))
                    continue
                m = _HIT_RATE_RE.match(name)
                if m:
                    out[name] = _hit_rate_last(self.period_return_hist, int(m.group(1)))
        return out
