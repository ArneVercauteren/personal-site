"""Minimal DSL compatibility shim — the one generator function the evaluator needs.

`select_on_date._flatten_name` calls `wrapping_transform_allowed_for_feature_name`
to decide whether a transform wrapper (z/rank/log/qbin/lag/diff) applies to a
feature or is stripped. The full `src/dsl/generator.py` is a 2000-line evolution
module with config/feature-store dependencies; only this decision is needed for
evaluation, so it is vendored here with its exact helpers and constants copied
from Astralanx's generator.py (the parts that build `_SELF_NORMALIZED_INDICATORS`
and the fundamental / portfolio-state name sets).
"""

from __future__ import annotations

import re

from .indicator_constants import (
    BASE_SELF_NORMALIZED_INDICATORS as _SHARED_BASE_SELF_NORMALIZED_INDICATORS,
)
from .indicator_constants import (
    FUND_NAMES as _SHARED_FUND_NAMES,
)

_FUND_NAMES = set(_SHARED_FUND_NAMES)

# --- constant assembly, mirroring src/dsl/generator.py exactly ---------------

_SELF_NORMALIZED_INDICATORS = set(_SHARED_BASE_SELF_NORMALIZED_INDICATORS)
_SELF_NORMALIZED_INDICATORS.update({"rvol", "beta"})

_MARKET_INTERNAL_WINDOWED = [
    "market_breadth_above_sma",
    "market_breadth_above_ema",
    "market_breadth_positive_roc",
    "market_new_high_frac",
    "market_new_low_frac",
    "market_net_new_highs",
    "market_ad_momentum",
    "market_cross_sectional_return_dispersion",
    "market_eqw_minus_benchmark",
    "market_cross_sectional_skew",
    "market_median_return",
    "market_percentile_spread",
    "market_volume_surge_breadth",
    "market_drawdown_breadth",
    "market_avg_beta",
    "market_beta_dispersion",
    "market_corr_dispersion",
    "market_liquidity_stress",
    "market_leadership_concentration",
]

_MARKET_INTERNAL_WINDOWLESS = [
    "market_advance_decline_count",
    "market_advance_decline_ratio",
    "market_ad_line",
    "market_eqw_return",
    "market_up_volume_frac",
    "market_up_down_volume_ratio",
    "market_gap_breadth",
    "market_close_to_range_breadth",
]

_PORTFOLIO_STATE_WINDOWLESS = [
    "current_portfolio_drawdown",
    "current_holdings_count",
    "invested_fraction",
    "cash_fraction",
]

_PORTFOLIO_STATE_WINDOWED = [
    "trailing_portfolio_turnover",
    "trailing_portfolio_volatility",
    "recent_hit_rate",
]

_MARKET_INTERNAL_WINDOWED_SET = frozenset(_MARKET_INTERNAL_WINDOWED)
_MARKET_INTERNAL_WINDOWLESS_SET = frozenset(_MARKET_INTERNAL_WINDOWLESS)
_SELF_NORMALIZED_INDICATORS.update(_MARKET_INTERNAL_WINDOWED_SET)
_SELF_NORMALIZED_INDICATORS.update(_MARKET_INTERNAL_WINDOWLESS_SET)
_SELF_NORMALIZED_INDICATORS.update(_PORTFOLIO_STATE_WINDOWLESS)
_SELF_NORMALIZED_INDICATORS.update(_PORTFOLIO_STATE_WINDOWED)


# --- helpers, copied verbatim from src/dsl/generator.py ---------------------


def _is_fundamental_name(ind_name: str) -> bool:
    try:
        return str(ind_name) in _FUND_NAMES
    except (TypeError, ValueError):
        return False


def _is_portfolio_state_name(ind_name: str) -> bool:
    name = str(ind_name)
    return name in _PORTFOLIO_STATE_WINDOWLESS or name in _PORTFOLIO_STATE_WINDOWED


def _base_feature_name(name: str) -> str:
    """Strip wrappers and window suffixes to reveal the underlying feature base."""
    n = str(name or "")
    if n.startswith("quantile_bin_"):
        n = "qbin5_" + n[len("quantile_bin_") :]
    if n.startswith("lag_"):
        n = "lag1_" + n[len("lag_") :]
    if n.startswith("diff_"):
        n = "diff1_" + n[len("diff_") :]
    while True:
        if n.startswith("z") and not n.startswith("z_"):
            prefix, _, rest = n.partition("_")
            if prefix[1:].isdigit() and rest:
                n = rest
                continue
        elif n.startswith("rank"):
            prefix, _, rest = n.partition("_")
            if prefix[4:].isdigit() and rest:
                n = rest
                continue
        elif n.startswith("log_"):
            n = n[4:]
            continue
        elif n.startswith("quantile_bin_"):
            n = n[len("quantile_bin_") :]
            continue
        elif n.startswith("qbin"):
            prefix, _, rest = n.partition("_")
            if prefix[4:].isdigit() and rest:
                n = rest
                continue
        elif n.startswith("lag"):
            prefix, _, rest = n.partition("_")
            if prefix[3:].isdigit() and rest:
                n = rest
                continue
        elif n.startswith("diff"):
            prefix, _, rest = n.partition("_")
            if prefix[4:].isdigit() and rest:
                n = rest
                continue
        break
    m = re.match(r"^(.*)_(\d+)$", n)
    if m:
        n = m.group(1)
    return n


def wrapping_transform_allowed_for_feature_name(name: str) -> bool:
    """Return True when a feature may be wrapped by DSL transform nodes.

    Fundamentals, portfolio-state features, and self-normalized/date-level
    breadth metrics should remain raw. Wrapping them in z/rank/log/qbin/lag/diff
    produces noisy or meaningless feature requests and can drift from the store's
    intended feature surface.
    """
    base_name = _base_feature_name(name)
    if not base_name:
        return False
    if _is_fundamental_name(base_name) or _is_portfolio_state_name(base_name):
        return False
    return base_name not in _SELF_NORMALIZED_INDICATORS
