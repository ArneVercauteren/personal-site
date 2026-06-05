"""Pure-Python single-date ticker selection (vendored, scrubbed).

Vendored from Astralanx `src/backtest/select_on_date.py`. Computes the exact
features a strategy AST references, evaluates the tree in Python, applies the
same eligibility restrictions as the backtest, and returns the selected tickers
and target weights.

Changes from the Astralanx original (all behavior-preserving for evaluation):
  * imports rewired to the vendored siblings (`dsl_compat`, `eligibility`,
    `tree_eval`, `select_helpers`); no `src.` imports.
  * realism defaults are module constants (mirroring Astralanx engine.py) instead
    of `src.config.get_config()`.
  * all yfinance download/cache, benchmark-CSV, and CLI code removed — the
    caller always supplies `prices_override` (and optionally a market series).
  * `_load_market_segment_ids` always returns None (no per-segment rank in the
    public engine; our universes are unsegmented).
  * `select_tickers_on_date` gains `portfolio_state_override` so the simulator
    can inject engine-computed portfolio-state features (drawdown, trailing
    turnover/volatility/hit-rate, etc.) that the pure-Python path doesn't track.
"""

from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import dsl_compat as dsl_gen
from . import select_helpers as _sh
from .eligibility import build_eligibility_mask

_log = logging.getLogger(__name__)

# Realism defaults — mirror Astralanx src/config/engine.py.
MIN_PRICE = 10.0
MIN_MEDIAN_DOLLAR_VOLUME = 5_000_000.0
DEFAULT_PORTFOLIO_SIZE = 1_000_000.0
ADV_WINDOW_DEFAULT = 63

# ---------------------------------------------------------------------------
# Strategy JSON loading
# ---------------------------------------------------------------------------


def load_strategy_json(path_or_string: str) -> dict:
    """Load a strategy JSON from a file path or inline JSON string.

    Returns the strategy payload dict (unwraps ``{"strategy": ...}`` wrappers).
    """
    p = Path(path_or_string)
    if p.exists():
        raw = p.read_text(encoding="utf-8")
    else:
        raw = path_or_string
    parsed = json.loads(raw)
    if isinstance(parsed, dict) and "strategy" in parsed:
        return parsed["strategy"]
    return parsed


# ---------------------------------------------------------------------------
# AST helpers - walk the tree, collect needed feature column names,
# and evaluate the tree on a per-ticker feature dict.
# ---------------------------------------------------------------------------


def _flatten_name(node: dict) -> str:
    """Flatten a DSL node dict into a feature column name.

    Mirrors ``src.evolution.compiler._flatten_name`` logic.
    """
    kind = node.get("kind")
    if kind == "indicator":
        name = node["name"]
        # Aliases
        if name == "highest_high":
            name = "hh"
        elif name == "lowest_low":
            name = "ll"
        elif name == "market_highest_high":
            name = "market_hh"
        elif name == "market_lowest_low":
            name = "market_ll"
        _WINDOWLESS = {
            "dollar_volume",
            "overnight_gap",
            "close_to_range",
            "pe",
            "fund_eps",
            "fund_assets",
            "fund_net_income",
            "market_advance_decline_count",
            "market_advance_decline_ratio",
            "market_ad_line",
            "market_eqw_return",
            "market_up_volume_frac",
            "market_up_down_volume_ratio",
            "market_gap_breadth",
            "market_close_to_range_breadth",
            "market_volume",
            "current_portfolio_drawdown",
            "current_holdings_count",
            "invested_fraction",
            "cash_fraction",
        }
        # Strip trailing window on windowless indicators
        for base in _WINDOWLESS:
            if name.startswith(f"{base}_") and name[len(base) + 1 :].isdigit():
                name = base
                break
        if name in _WINDOWLESS:
            return name
        win = (node.get("params") or {}).get("window")
        if win is not None:
            return f"{name}_{int(win)}"
        return name

    if kind == "transform":
        child_name = _flatten_name(node["child"])
        params = node.get("params") or {}
        tname = node["name"]

        if child_name in _PORTFOLIO_STATE_FEATURES or any(
            child_name.startswith(prefix) for prefix in _PORTFOLIO_STATE_FEATURE_PREFIXES
        ):
            return child_name
        if not dsl_gen.wrapping_transform_allowed_for_feature_name(str(child_name)):
            return child_name

        if tname in ("z_score", "rank"):
            if tname == "rank" and child_name.startswith("market_"):
                tname = "z_score"
            win = params.get("window", 60)
            prefix = "z" if tname == "z_score" else "rank"
            return f"{prefix}{int(win)}_{child_name}"

        if tname == "quantile_bin":
            if child_name.startswith("market_"):
                return f"z60_{child_name}"
            n_bins = params.get("n_bins", 5)
            return f"qbin{int(n_bins)}_{child_name}"

        if tname in ("lag", "diff"):
            periods = params.get("periods", 1)
            return f"{tname}{int(periods)}_{child_name}"

        if tname == "log":
            return f"log_{child_name}"

        win = params.get("window")
        if win is not None:
            return f"{tname}{int(win)}_{child_name}"
        return f"{tname}_{child_name}"

    raise ValueError(f"Not a feature node: {kind}")


def collect_needed_features(node: dict) -> set[str]:
    """Recursively collect all feature column names referenced by a strategy tree."""
    kind = node.get("kind")
    if kind == "number":
        return set()
    if kind in ("indicator", "transform"):
        return {_flatten_name(node)}
    if kind == "arithmetic":
        result: set[str] = set()
        for child in node.get("children", []):
            result |= collect_needed_features(child)
        return result
    if kind == "comparison":
        result = collect_needed_features(node["left"])
        result |= collect_needed_features(node["right"])
        if node.get("third"):
            result |= collect_needed_features(node["third"])
        return result
    if kind == "logic":
        result = set()
        logic_children = node.get("children")
        if logic_children is None:
            logic_children = node.get("clauses", [])
        for child in logic_children:
            result |= collect_needed_features(child)
        return result
    if kind == "conditional":
        result = set()
        for case in node.get("cases", []):
            if case.get("condition"):
                result |= collect_needed_features(case["condition"])
            if "result" in case:
                result |= collect_needed_features(case["result"])
            elif "else" in case:
                result |= collect_needed_features(case["else"])
        return result
    return set()


def collect_all_needed_features(strat_dict: dict, *, include_exit_root: bool = False) -> set[str]:
    """Collect features needed for single-date selection evaluation.

    By default, ``exit_root`` is excluded because it does not participate in
    entry-time ticker scoring/selection.
    """
    result = collect_needed_features(strat_dict)
    keys = ["filter_root", "score_root"]
    if include_exit_root:
        keys.append("exit_root")
    for key in keys:
        sub = strat_dict.get(key)
        if sub:
            result |= collect_needed_features(sub)
    if strat_dict.get("dynamic_top_n_formula"):
        result |= collect_needed_features(strat_dict["dynamic_top_n_formula"])
    if strat_dict.get("position_size_root"):
        result |= collect_needed_features(strat_dict["position_size_root"])
    for case in strat_dict.get("cases", []):
        if isinstance(case, dict):
            for sub_key in ("condition", "strategy", "else"):
                sub = case.get(sub_key)
                if isinstance(sub, dict):
                    result |= collect_all_needed_features(sub, include_exit_root=include_exit_root)
    return result


# ---------------------------------------------------------------------------
# Pure-Python AST evaluator
# ---------------------------------------------------------------------------


def _eval_indicator(node: dict, features: dict[str, float]) -> float:
    val = features.get(_flatten_name(node))
    if val is None or not np.isfinite(val):
        return float("nan")
    return float(val)


def _eval_comparison(node: dict, features: dict[str, float]) -> float:
    from .tree_eval import (
        SIMPLE_COMPARISON_OPS,
        TERNARY_COMPARISON_OPS,
        eval_ternary_comparison,
    )

    op = node["name"]
    left = evaluate_tree(node["left"], features)
    right = evaluate_tree(node["right"], features)
    if math.isnan(left) or math.isnan(right):
        return 0.0  # NaN comparison → False
    if op in TERNARY_COMPARISON_OPS:
        third = evaluate_tree(node["third"], features) if node.get("third") else right
        return eval_ternary_comparison(op, left, right, third)
    handler = SIMPLE_COMPARISON_OPS.get(op)
    return handler(left, right, node) if handler is not None else 0.0


def _eval_conditional(node: dict, features: dict[str, float]) -> float:
    for case in node.get("cases", []):
        cond = case.get("condition")
        if cond is None or evaluate_tree(cond, features) != 0.0:
            if "result" in case:
                return evaluate_tree(case["result"], features)
            if "else" in case:
                return evaluate_tree(case["else"], features)
            return float("nan")
    return float("nan")


def evaluate_tree(node: dict, features: dict[str, float]) -> float:
    """Evaluate a strategy AST node given a feature dict for one ticker.

    ``features`` maps column names (e.g. ``z60_sma_130``) to scalar float
    values. Returns a scalar score / signal value.
    """
    kind = node.get("kind")

    if kind == "number":
        return float(node["value"])
    if kind in ("indicator", "transform"):
        return _eval_indicator(node, features)
    if kind == "arithmetic":
        from .tree_eval import eval_arithmetic

        children = node.get("children", [])
        vals = [evaluate_tree(ch, features) for ch in children]
        return eval_arithmetic(node["name"], vals)
    if kind == "comparison":
        return _eval_comparison(node, features)
    if kind == "logic":
        from .tree_eval import eval_logic

        children = node.get("children") or node.get("clauses", [])
        child_vals = [evaluate_tree(ch, features) for ch in children]
        return eval_logic(node["name"], child_vals)
    if kind == "conditional":
        return _eval_conditional(node, features)

    return float("nan")


# ---------------------------------------------------------------------------
# Feature computation from a prices DataFrame
# ---------------------------------------------------------------------------

_RE_Z = re.compile(r"^z(\d+)_(.+)$")
_RE_RANK = re.compile(r"^rank(\d+)_(.+)$")
_RE_QBIN = re.compile(r"^qbin(\d+)_(.+)$")
_RE_LAG = re.compile(r"^lag(\d+)_(.+)$")
_RE_DIFF = re.compile(r"^diff(\d+)_(.+)$")

_PORTFOLIO_STATE_FEATURES = {
    "current_portfolio_drawdown",
    "current_holdings_count",
    "invested_fraction",
    "cash_fraction",
}
_PORTFOLIO_STATE_FEATURE_PREFIXES = (
    "trailing_portfolio_turnover_",
    "trailing_portfolio_volatility_",
    "recent_hit_rate_",
)
_STRATEGY_SWITCH_BOOLEAN_TOPN_THRESHOLD = -999999.0


def _base_windowed_name(name: str, prefix: str) -> int | None:
    """If ``name`` matches ``prefix_<int>``, return the window."""
    if name.startswith(prefix + "_"):
        tail = name[len(prefix) + 1 :]
        if tail.isdigit():
            return int(tail)
    return None


def _rank_pct_np(arr: np.ndarray) -> np.ndarray:
    m_rows, n_cols = arr.shape
    out = np.full((m_rows, n_cols), np.nan, dtype=np.float32)
    valid = np.isfinite(arr)
    n_valid = valid.sum(axis=1)
    arr_safe = np.where(valid, arr, np.inf).astype(np.float32, copy=False)
    order = np.argsort(arr_safe, axis=1, kind="quicksort")
    rank_vals = np.arange(1, n_cols + 1, dtype=np.float32)[None, :]
    np.put_along_axis(out, order, rank_vals, axis=1)
    nv = n_valid.astype(np.float32)[:, None]
    nv = np.where(nv == 0, 1.0, nv)
    out /= nv
    out[~valid] = np.nan
    return out


def _rank_pct_df(inner_df: pd.DataFrame, rank_segment_ids: np.ndarray | None) -> pd.DataFrame:
    arr = inner_df.to_numpy(dtype=np.float32, copy=False)
    if rank_segment_ids is None or rank_segment_ids.shape[0] != arr.shape[1]:
        out = _rank_pct_np(arr)
        return pd.DataFrame(out, index=inner_df.index, columns=inner_df.columns)

    out = np.full(arr.shape, np.nan, dtype=np.float32)
    for seg_id in np.unique(rank_segment_ids):
        seg_cols = np.flatnonzero(rank_segment_ids == seg_id)
        if seg_cols.size == 0:
            continue
        seg_rank = _rank_pct_np(arr[:, seg_cols])
        out[:, seg_cols] = seg_rank
    return pd.DataFrame(out, index=inner_df.index, columns=inner_df.columns)


def _nan_feature_like(prices_aligned: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(np.nan, index=prices_aligned.index, columns=prices_aligned.columns)


def _compute_transformed_feature(
    name: str,
    *,
    resolve: Any,
    eligibility_mask: pd.DataFrame | None,
    rank_segment_ids: np.ndarray | None,
) -> pd.DataFrame | None:
    match = _RE_Z.match(name)
    if match:
        win = int(match.group(1))
        inner = resolve(match.group(2))
        if inner is None:
            return None
        window = max(win, 1)
        roll_mean = inner.rolling(window=window, min_periods=window).mean()
        roll_std = inner.rolling(window=window, min_periods=window).std().replace(0, np.nan)
        return (inner - roll_mean) / roll_std

    match = _RE_RANK.match(name)
    if match:
        win = int(match.group(1))
        inner = resolve(match.group(2))
        if inner is None:
            return None
        window = max(win, 1)
        roll_mean = inner.rolling(window=window, min_periods=window).mean()
        if eligibility_mask is not None:
            roll_mean = roll_mean.mask(~eligibility_mask.reindex_like(roll_mean).fillna(False))
        return _rank_pct_df(roll_mean, rank_segment_ids)

    match = _RE_QBIN.match(name)
    if match:
        n_bins = int(match.group(1))
        inner = resolve(match.group(2))
        if inner is None or n_bins < 2:
            return None
        if eligibility_mask is not None:
            inner = inner.mask(~eligibility_mask.reindex_like(inner).fillna(False))
        rank_pct = _rank_pct_df(inner, rank_segment_ids)
        bins = np.floor(rank_pct.values * float(n_bins)).clip(0, n_bins - 1)
        return pd.DataFrame(bins / float(n_bins - 1), index=inner.index, columns=inner.columns)

    match = _RE_LAG.match(name)
    if match:
        periods = int(match.group(1))
        inner = resolve(match.group(2))
        return None if inner is None else inner.shift(periods)

    match = _RE_DIFF.match(name)
    if match:
        periods = int(match.group(1))
        inner = resolve(match.group(2))
        return None if inner is None else inner.diff(periods)

    if name.startswith("log_"):
        inner = resolve(name[4:])
        return None if inner is None else np.sign(inner) * np.log1p(np.abs(inner))

    return None


def _compute_price_indicator_feature(
    name: str,
    *,
    prices_aligned: pd.DataFrame,
    high_aligned: pd.DataFrame | None,
    low_aligned: pd.DataFrame | None,
) -> pd.DataFrame | None:
    window = _base_windowed_name(name, "sma")
    if window is not None:
        return prices_aligned.rolling(window=window, min_periods=window).mean().shift(1)

    window = _base_windowed_name(name, "ema")
    if window is not None:
        return prices_aligned.ewm(span=window, adjust=False).mean().shift(1)

    window = _base_windowed_name(name, "roc")
    if window is not None:
        denom = prices_aligned.shift(window).replace(0, np.nan)
        return (((prices_aligned / denom) - 1) * 100).shift(1)

    window = _base_windowed_name(name, "hh")
    if window is not None:
        return prices_aligned.rolling(window=window).max().shift(1)

    window = _base_windowed_name(name, "ll")
    if window is not None:
        return prices_aligned.rolling(window=window).min().shift(1)

    window = _base_windowed_name(name, "rsi")
    if window is not None:
        delta = prices_aligned.diff()
        gain = delta.where(delta > 0, 0).rolling(window=window).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=window).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        flat = (gain == 0) & (loss == 0)
        rsi[flat] = 50.0
        return rsi.shift(1)

    window = _base_windowed_name(name, "atr")
    if window is not None:
        high = high_aligned if high_aligned is not None else prices_aligned
        low = low_aligned if low_aligned is not None else prices_aligned
        prev_close = prices_aligned.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.DataFrame(
            np.nanmax(np.stack([tr1.values, tr2.values, tr3.values], axis=0), axis=0),
            index=prices_aligned.index,
            columns=prices_aligned.columns,
        )
        return tr.ewm(alpha=1.0 / window, adjust=False).mean().shift(1)

    return None


def _compute_self_normalized_feature(
    name: str,
    *,
    prices_aligned: pd.DataFrame,
    volume_aligned: pd.DataFrame | None,
    market_series: pd.Series | None,
) -> pd.DataFrame | None:
    window = _base_windowed_name(name, "rvol")
    if window is not None:
        px = prices_aligned.replace(0, np.nan)
        daily_rets = px.pct_change()
        return daily_rets.rolling(window=window, min_periods=window).std().shift(1)

    window = _base_windowed_name(name, "beta")
    if window is not None:
        if market_series is None:
            return _nan_feature_like(prices_aligned)
        px = prices_aligned.replace(0, np.nan)
        daily_rets = px.pct_change()
        mkt_rets = market_series.replace(0, np.nan).pct_change().reindex(daily_rets.index)
        cov = daily_rets.rolling(window, min_periods=window).cov(mkt_rets)
        mkt_var = market_series.replace(0, np.nan).pct_change().reindex(daily_rets.index)
        mkt_var = mkt_var.rolling(window, min_periods=window).var().replace(0, np.nan)
        if isinstance(cov, pd.DataFrame) and isinstance(mkt_var, pd.Series):
            return cov.div(mkt_var, axis=0).shift(1)
        return (cov / mkt_var).shift(1)

    window = _base_windowed_name(name, "mkt_corr")
    if window is not None:
        if market_series is None:
            return _nan_feature_like(prices_aligned)
        px = prices_aligned.replace(0, np.nan)
        daily_rets = px.pct_change()
        mkt_rets = market_series.replace(0, np.nan).pct_change().reindex(daily_rets.index)
        return daily_rets.rolling(window, min_periods=window).corr(mkt_rets).shift(1)

    window = _base_windowed_name(name, "mean_reversion")
    if window is not None:
        sma = prices_aligned.rolling(window=window, min_periods=window).mean().replace(0, np.nan)
        return (prices_aligned / sma - 1).shift(1)

    window = _base_windowed_name(name, "drawdown")
    if window is not None:
        roll_max = prices_aligned.rolling(window=window, min_periods=window).max().replace(0, np.nan)
        return (prices_aligned / roll_max - 1).shift(1)

    window = _base_windowed_name(name, "skewness")
    if window is not None:
        px = prices_aligned.replace(0, np.nan)
        daily_rets = px.pct_change()
        return daily_rets.rolling(window=window, min_periods=window).skew().shift(1)

    window = _base_windowed_name(name, "amihud_illiquidity")
    if window is not None and volume_aligned is not None:
        px = prices_aligned.replace(0, np.nan)
        daily_rets = px.pct_change().abs()
        dollar_volume = (px * volume_aligned).replace(0, np.nan)
        ratio = daily_rets / dollar_volume
        return ratio.rolling(window=window, min_periods=window).mean().shift(1)

    window = _base_windowed_name(name, "volume_surge")
    if window is not None and volume_aligned is not None:
        vol_sma = volume_aligned.rolling(window=window, min_periods=window).mean().replace(0, np.nan)
        return (volume_aligned / vol_sma - 1).shift(1)

    return None


def _compute_windowless_feature(
    name: str,
    *,
    prices_aligned: pd.DataFrame,
    volume_aligned: pd.DataFrame | None,
    open_aligned: pd.DataFrame | None,
    high_aligned: pd.DataFrame | None,
    low_aligned: pd.DataFrame | None,
) -> pd.DataFrame | None:
    if name == "dollar_volume" and volume_aligned is not None:
        return (prices_aligned * volume_aligned).shift(1)

    if name == "overnight_gap" and open_aligned is not None:
        prev_close = prices_aligned.shift(1).replace(0, np.nan)
        return (open_aligned / prev_close - 1).shift(1)

    if name == "close_to_range" and high_aligned is not None and low_aligned is not None:
        rng = (high_aligned - low_aligned).replace(0, np.nan)
        return ((prices_aligned - low_aligned) / rng).clip(0, 1).shift(1)

    return None


def _normalize_ticker_key(ticker: str) -> str:
    return str(ticker).strip().upper().replace(" ", "").replace(".", "-")


def _dedupe_tickers(tickers: list[str] | None) -> list[str]:
    if not tickers:
        return []
    ordered: list[str] = []
    seen: set[str] = set()
    for ticker in tickers:
        norm = str(ticker).strip().upper()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        ordered.append(norm)
    return ordered


def _normalize_prior_weights(
    prior_holdings: list[str],
    prior_weights: dict[str, float] | None,
) -> dict[str, float]:
    holdings = _dedupe_tickers(prior_holdings)
    if not holdings:
        return {}
    if not prior_weights:
        ew = 1.0 / float(len(holdings))
        return dict.fromkeys(holdings, ew)

    clean: dict[str, float] = {}
    for ticker in holdings:
        raw = prior_weights.get(ticker)
        if raw is None:
            continue
        try:
            weight = float(raw)
        except Exception:
            continue
        if np.isfinite(weight) and weight > 0.0:
            clean[ticker] = weight

    if not clean:
        ew = 1.0 / float(len(holdings))
        return dict.fromkeys(holdings, ew)

    total = float(sum(clean.values()))
    if total <= 1e-12:
        ew = 1.0 / float(len(holdings))
        return dict.fromkeys(holdings, ew)
    return {ticker: weight / total for ticker, weight in clean.items()}


def _build_portfolio_state_values(
    prior_holdings: list[str],
    prior_weights: dict[str, float],
) -> dict[str, float]:
    invested = float(sum(weight for weight in prior_weights.values() if np.isfinite(weight) and weight > 0.0))
    invested = min(max(invested, 0.0), 1.0)
    return {
        "current_holdings_count": float(
            len([ticker for ticker in prior_holdings if prior_weights.get(ticker, 0.0) > 0.0])
        ),
        "invested_fraction": invested,
        "cash_fraction": float(max(0.0, 1.0 - invested)),
        "current_portfolio_drawdown": float("nan"),
    }


def _build_feature_values_for_ticker(
    ticker: str,
    eval_date: pd.Timestamp,
    feature_matrices: dict[str, pd.DataFrame],
    portfolio_state_values: dict[str, float],
) -> dict[str, float]:
    feat_values = dict(portfolio_state_values)
    for fname, mat in feature_matrices.items():
        if ticker in mat.columns and eval_date in mat.index:
            val = mat.at[eval_date, ticker]
            feat_values[fname] = float(val) if np.isfinite(val) else float("nan")
        else:
            feat_values[fname] = float("nan")
    return feat_values


def _build_date_level_feature_values(
    eval_date: pd.Timestamp,
    feature_matrices: dict[str, pd.DataFrame],
    portfolio_state_values: dict[str, float],
) -> dict[str, float]:
    feat_values = dict(portfolio_state_values)
    for fname, mat in feature_matrices.items():
        if eval_date not in mat.index or mat.empty:
            feat_values[fname] = float("nan")
            continue
        row = mat.loc[eval_date]
        if isinstance(row, pd.Series):
            finite_mask = np.isfinite(row.to_numpy(dtype=float, copy=False))
            if np.any(finite_mask):
                feat_values[fname] = float(row.iloc[int(np.flatnonzero(finite_mask)[0])])
            else:
                feat_values[fname] = float("nan")
        else:
            feat_values[fname] = float("nan")
    return feat_values


def _resolve_position_size_fraction(
    strat_dict: dict,
    eval_date: pd.Timestamp,
    feature_matrices: dict[str, pd.DataFrame],
    portfolio_state_values: dict[str, float],
) -> float:
    position_size_root = strat_dict.get("position_size_root")
    if not position_size_root:
        return 1.0
    feat_values = _build_date_level_feature_values(eval_date, feature_matrices, portfolio_state_values)
    raw_value = evaluate_tree(position_size_root, feat_values)
    if not np.isfinite(raw_value):
        fallback = portfolio_state_values.get("invested_fraction", 1.0)
        raw_value = fallback if np.isfinite(fallback) else 1.0
    return float(min(1.0, max(0.0, raw_value)))


def _compute_rank_weights_py(k: int) -> list[float]:
    if k <= 0:
        return []
    if k == 1:
        return [1.0]

    weight_sum = float(k * (k + 1)) / 2.0
    weights = [float(k - i) / weight_sum for i in range(k)]
    max_w = min(2.5 / float(k), 0.05)

    for _ in range(3):
        if not any(weight > max_w for weight in weights):
            break
        capped_sum = 0.0
        uncapped_sum = 0.0
        capped_weights: list[float] = []
        for weight in weights:
            if weight > max_w:
                capped_weights.append(max_w)
                capped_sum += max_w
            else:
                capped_weights.append(weight)
                uncapped_sum += weight
        target_uncapped = 1.0 - capped_sum
        if uncapped_sum > 1e-12:
            scale = target_uncapped / uncapped_sum
            for idx, weight in enumerate(capped_weights):
                if weight < max_w:
                    capped_weights[idx] = weight * scale
        weights = capped_weights

    total = float(sum(weights))
    if total > 1e-12 and abs(total - 1.0) > 1e-6:
        weights = [weight / total for weight in weights]
    return weights


def _selection_weights_for_ordered_tickers(
    ordered_tickers: list[str],
    *,
    use_rank_weights: bool,
) -> dict[str, float]:
    if not ordered_tickers:
        return {}
    if use_rank_weights:
        weights = _compute_rank_weights_py(len(ordered_tickers))
    else:
        ew = 1.0 / float(len(ordered_tickers))
        weights = [ew] * len(ordered_tickers)
    return {ticker: float(weight) for ticker, weight in zip(ordered_tickers, weights, strict=False)}


def _target_share_delta(
    *,
    prior_weight: float,
    final_weight: float,
    price: float | None,
    portfolio_size: float,
) -> tuple[float | None, int | None]:
    has_valid_price = price is not None and np.isfinite(price) and price > 0.0
    has_valid_portfolio_size = np.isfinite(portfolio_size) and portfolio_size > 0.0
    if not has_valid_price or not has_valid_portfolio_size:
        return None, None
    dollar_delta = (float(final_weight) - float(prior_weight)) * float(portfolio_size)
    share_delta = dollar_delta / float(price)
    shares_to_buy = math.floor(share_delta) if share_delta > 0.0 else 0
    return float(share_delta), shares_to_buy


def _target_share_count(
    *,
    final_weight: float,
    price: float | None,
    portfolio_size: float,
) -> int | None:
    has_valid_price = price is not None and np.isfinite(price) and price > 0.0
    has_valid_portfolio_size = np.isfinite(portfolio_size) and portfolio_size > 0.0
    if not has_valid_price or not has_valid_portfolio_size:
        return None
    target_shares = (float(final_weight) * float(portfolio_size)) / float(price)
    if target_shares <= 0.0:
        return 0
    return math.floor(target_shares)


def _load_market_segment_ids(columns: pd.Index) -> np.ndarray | None:
    """No per-segment ranking in the public engine.

    Astralanx loads per-ticker market segment ids from universe metadata; the
    public paper-trading engine runs unsegmented universes, so segmentation is
    disabled (global cross-sectional rank). Documented parity boundary.
    """
    return None


def compute_feature_matrix(
    name: str,
    prices_aligned: pd.DataFrame,
    *,
    volume_aligned: pd.DataFrame | None = None,
    open_aligned: pd.DataFrame | None = None,
    high_aligned: pd.DataFrame | None = None,
    low_aligned: pd.DataFrame | None = None,
    market_series: pd.Series | None = None,
    eligibility_mask: pd.DataFrame | None = None,
    rank_segment_ids: np.ndarray | None = None,
    _cache: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame | None:
    """Compute a single feature matrix (dates x tickers).

    Mirrors the formulas in ``precompute_feature_blobs`` but computes only the
    requested feature on-demand. Intermediate results are cached in ``_cache``.
    """
    if _cache is None:
        _cache = {}
    if name in _cache:
        return _cache[name]

    def _resolve(inner_name: str) -> pd.DataFrame | None:
        return compute_feature_matrix(
            inner_name,
            prices_aligned,
            volume_aligned=volume_aligned,
            open_aligned=open_aligned,
            high_aligned=high_aligned,
            low_aligned=low_aligned,
            market_series=market_series,
            eligibility_mask=eligibility_mask,
            rank_segment_ids=rank_segment_ids,
            _cache=_cache,
        )

    result = _compute_transformed_feature(
        name,
        resolve=_resolve,
        eligibility_mask=eligibility_mask,
        rank_segment_ids=rank_segment_ids,
    )
    if result is not None:
        _cache[name] = result
        return result

    result = _compute_price_indicator_feature(
        name,
        prices_aligned=prices_aligned,
        high_aligned=high_aligned,
        low_aligned=low_aligned,
    )
    if result is not None:
        _cache[name] = result
        return result

    result = _compute_self_normalized_feature(
        name,
        prices_aligned=prices_aligned,
        volume_aligned=volume_aligned,
        market_series=market_series,
    )
    if result is not None:
        _cache[name] = result
        return result

    result = _compute_windowless_feature(
        name,
        prices_aligned=prices_aligned,
        volume_aligned=volume_aligned,
        open_aligned=open_aligned,
        high_aligned=high_aligned,
        low_aligned=low_aligned,
    )
    if result is not None:
        _cache[name] = result
        return result

    if name.startswith("market_") and market_series is not None:
        mkt_result = _compute_market_feature(
            name,
            market_series,
            prices_aligned.index,
            prices_aligned.columns,
        )
        if mkt_result is not None:
            _cache[name] = mkt_result
            return mkt_result

    return None


def _compute_market_feature(
    name: str,
    market_series: pd.Series,
    index: pd.DatetimeIndex,
    columns: pd.Index,
) -> pd.DataFrame | None:
    """Compute a market-level indicator and broadcast across all ticker columns."""

    def _broadcast(series: pd.Series) -> pd.DataFrame:
        s = series.reindex(index).ffill()
        arr = np.broadcast_to(s.values[:, None], (len(index), len(columns))).copy()
        return pd.DataFrame(arr, index=index, columns=columns)

    def _match(prefix: str) -> int | None:
        if name.startswith(prefix + "_"):
            tail = name[len(prefix) + 1 :]
            if tail.isdigit():
                return int(tail)
        return None

    w = _match("market_sma")
    if w is not None:
        s = market_series.rolling(window=w, min_periods=w).mean().shift(1)
        return _broadcast(s)

    w = _match("market_ema")
    if w is not None:
        s = market_series.ewm(span=w, adjust=False).mean().shift(1)
        return _broadcast(s)

    w = _match("market_roc")
    if w is not None:
        denom = market_series.shift(w).replace(0, np.nan)
        s = ((market_series / denom) - 1) * 100
        return _broadcast(s.shift(1))

    w = _match("market_rsi")
    if w is not None:
        delta = market_series.diff()
        gain = delta.where(delta > 0, 0).rolling(window=w).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=w).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        flat = (gain == 0) & (loss == 0)
        rsi[flat] = 50.0
        return _broadcast(rsi.shift(1))

    w = _match("market_atr")
    if w is not None:
        prev_c = market_series.shift(1)
        tr = pd.concat(
            [
                (market_series - market_series).abs(),  # H-L placeholder
                (market_series - prev_c).abs(),
                (market_series - prev_c).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.ewm(alpha=1.0 / w, adjust=False).mean().shift(1)
        return _broadcast(atr)

    w = _match("market_hh")
    if w is not None:
        return _broadcast(market_series.rolling(window=w).max().shift(1))

    w = _match("market_ll")
    if w is not None:
        return _broadcast(market_series.rolling(window=w).min().shift(1))

    if name == "market_volume":
        return _broadcast(market_series.shift(1))

    return None


# ---------------------------------------------------------------------------
# Required history (days of price data needed)
# ---------------------------------------------------------------------------


def required_history_days(feature_names: set[str]) -> int:
    """Estimate how many trading days of history we need for the given features."""
    max_pts = 1
    for name in feature_names:
        pts = _required_points(name)
        if pts > max_pts:
            max_pts = pts
    # Add generous margin for weekends/holidays
    return int(max_pts * 1.6) + 30


def _required_points(name: str) -> int:
    if name.startswith("log_"):
        return _required_points(name[4:])

    m = _RE_QBIN.match(name)
    if m:
        return _required_points(m.group(2))

    m = _RE_LAG.match(name)
    if m:
        return int(m.group(1)) + _required_points(m.group(2))

    m = _RE_DIFF.match(name)
    if m:
        return int(m.group(1)) + _required_points(m.group(2))

    m = _RE_Z.match(name)
    if m:
        return int(m.group(1)) + _required_points(m.group(2))

    m = _RE_RANK.match(name)
    if m:
        return int(m.group(1)) + _required_points(m.group(2))

    # Base indicators with trailing window
    for prefix in (
        "sma",
        "ema",
        "hh",
        "ll",
        "roc",
        "rsi",
        "atr",
        "market_sma",
        "market_ema",
        "market_hh",
        "market_ll",
        "market_roc",
        "market_rsi",
        "market_atr",
        "volume_surge",
        "rvol",
        "beta",
        "mkt_corr",
        "mean_reversion",
        "drawdown",
        "skewness",
        "amihud_illiquidity",
    ):
        if name.startswith(prefix + "_"):
            tail = name[len(prefix) + 1 :]
            if tail.isdigit():
                return int(tail) + 1
    return 1


# ---------------------------------------------------------------------------
# Eligibility check (mirrors src/eligibility.build_eligibility_mask)
# ---------------------------------------------------------------------------


def is_eligible(
    ticker: str,
    raw_close: float | None,
    adj_close: float | None,
    is_stale: bool,
    first_trade_date: pd.Timestamp | None,
    last_trade_date: pd.Timestamp | None,
    target_date: pd.Timestamp,
    *,
    min_price: float | None = None,
) -> bool:
    """Check if a single ticker is eligible on the target date."""
    if min_price is None:
        min_price = MIN_PRICE

    # Pre-IPO
    if first_trade_date is not None and target_date < first_trade_date:
        return False
    # Delisted
    if last_trade_date is not None and target_date > last_trade_date:
        return False
    # Stale / gap
    if is_stale:
        return False
    # Min price on *raw* (unadjusted) close
    return not (
        raw_close is not None and min_price > 0 and (not np.isfinite(raw_close) or raw_close < min_price)
    )


# ---------------------------------------------------------------------------
# Top-level selection function
# ---------------------------------------------------------------------------


def select_tickers_on_date(
    *,
    strat_dict: dict,
    target_date: str | pd.Timestamp,
    tickers: list[str],
    prices_override: pd.DataFrame,
    min_price: float | None = None,
    min_adv: float | None = None,
    adv_window: int = ADV_WINDOW_DEFAULT,
    max_stale_days: int = 5,
    market_series_override: pd.Series | None = None,
    apply_exit_root_to: list[str] | None = None,
    prior_weights: dict[str, float] | None = None,
    portfolio_size: float | None = None,
    portfolio_state_override: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Select tickers on a single date using pure Python.

    1. Parses the strategy JSON to find needed features.
    2. Uses the caller-supplied ``prices_override`` (long format with columns
       date, ticker, adj_close[, close, volume, open, high, low]).
    3. Computes features in Python, evaluates the AST, applies eligibility.
    4. Returns the selected tickers and target weights.

    ``portfolio_state_override`` lets the simulator inject engine-computed
    portfolio-state features (drawdown, trailing turnover/volatility/hit-rate)
    by exact flattened name; values are merged over the internally derived
    invested/cash/holdings state.
    """
    if min_price is None:
        min_price = MIN_PRICE
    if min_adv is None:
        min_adv = MIN_MEDIAN_DOLLAR_VOLUME
    if portfolio_size is None:
        portfolio_size = DEFAULT_PORTFOLIO_SIZE
    if prices_override is None:
        raise ValueError("select_tickers_on_date requires prices_override (long-format prices).")

    target = pd.Timestamp(target_date).normalize()

    prior_holdings = _dedupe_tickers(apply_exit_root_to)
    prior_weight_map = _normalize_prior_weights(prior_holdings, prior_weights)
    portfolio_state_values = _build_portfolio_state_values(prior_holdings, prior_weight_map)
    if portfolio_state_override:
        portfolio_state_values = {**portfolio_state_values, **portfolio_state_override}

    mode = strat_dict.get("mode", "")
    top_n = int(strat_dict.get("top_n", 0))
    if not mode:
        mode = "top_n" if top_n > 0 else "boolean"

    needed = collect_all_needed_features(
        strat_dict,
        include_exit_root=bool(apply_exit_root_to),
    )
    if not needed:
        raise ValueError("Strategy references no features.")

    prices_df = prices_override.copy()

    market_series = market_series_override if market_series_override is not None else None

    if prices_df.empty:
        return {
            "date": target,
            "mode": mode,
            "top_n": top_n,
            "selected": [],
            "scores": {},
            "eligible_count": 0,
        }

    # Normalize + pivot prices
    prices_df["date"] = pd.to_datetime(prices_df["date"], errors="coerce")
    prices_df = prices_df.dropna(subset=["date"]).sort_values("date")
    all_tickers = sorted(prices_df["ticker"].astype(str).unique())

    pivots = _sh.build_price_pivots(prices_df)
    rank_segment_ids = _load_market_segment_ids(pivots.pivot_adj.columns)

    # Eligibility mask
    eligibility_mask_df = _sh.build_eligibility_mask_df(
        pivots=pivots,
        max_stale_days=max_stale_days,
        min_price=min_price,
        min_adv=min_adv,
        adv_window=adv_window,
        build_eligibility_mask_fn=build_eligibility_mask,
    )

    # Feature matrices
    feature_matrices = _sh.compute_feature_matrices(
        needed=needed,
        pivots=pivots,
        market_series=market_series,
        eligibility_mask_df=eligibility_mask_df,
        rank_segment_ids=rank_segment_ids,
        compute_feature_matrix_fn=compute_feature_matrix,
        portfolio_state_features=_PORTFOLIO_STATE_FEATURES,
    )

    # Snap to closest available date
    avail_dates = pivots.pivot_adj.index
    if target in avail_dates:
        eval_date = target
    else:
        earlier = avail_dates[avail_dates <= target]
        if earlier.empty:
            return {
                "date": target,
                "mode": mode,
                "top_n": top_n,
                "selected": [],
                "scores": {},
                "eligible_count": 0,
            }
        eval_date = earlier[-1]

    # Per-ticker eligibility + scoring
    scoring = _sh.score_all_tickers(
        all_tickers=all_tickers,
        eligibility_mask_df=eligibility_mask_df,
        eval_date=eval_date,
        feature_matrices=feature_matrices,
        portfolio_state_values=portfolio_state_values,
        strat_dict=strat_dict,
        mode=mode,
        pivots=pivots,
        build_feature_values_fn=_build_feature_values_for_ticker,
        evaluate_tree_fn=evaluate_tree,
    )

    def _resolve_dyn(base_top_n: int, candidates: list[str]) -> int:
        return _sh.resolve_dynamic_top_n(
            base_top_n=base_top_n,
            candidates=candidates,
            ticker_features=scoring.ticker_features,
            strat_dict=strat_dict,
            evaluate_tree_fn=evaluate_tree,
            strategy_switch_topn_threshold=_STRATEGY_SWITCH_BOOLEAN_TOPN_THRESHOLD,
        )

    selection = _sh.select_by_mode(
        mode=mode,
        top_n=top_n,
        scoring=scoring,
        strat_dict=strat_dict,
        eval_date=eval_date,
        feature_matrices=feature_matrices,
        portfolio_state_values=portfolio_state_values,
        build_feature_values_fn=_build_feature_values_for_ticker,
        evaluate_tree_fn=evaluate_tree,
        selection_weights_fn=_selection_weights_for_ordered_tickers,
        resolve_dynamic_fn=_resolve_dyn,
    )

    exit_outcome = _sh.apply_exit_logic(
        selection=selection,
        scoring=scoring,
        prior_holdings=prior_holdings,
        prior_weight_map=prior_weight_map,
        strat_dict=strat_dict,
        eval_date=eval_date,
        feature_matrices=feature_matrices,
        portfolio_state_values=portfolio_state_values,
        pivots=pivots,
        prices_df=prices_df,
        portfolio_size=portfolio_size,
        build_feature_values_fn=_build_feature_values_for_ticker,
        evaluate_tree_fn=evaluate_tree,
        resolve_position_size_fn=_resolve_position_size_fraction,
        target_share_delta_fn=_target_share_delta,
        target_share_count_fn=_target_share_count,
    )

    final_selected = exit_outcome.final_selected
    final_weights = exit_outcome.final_weights

    holding_summary = [
        {
            "ticker": ticker,
            "score": scoring.ticker_scores.get(ticker, float("nan")),
            "target_weight": float(final_weights.get(ticker, 0.0)),
            "trade_price": (
                scoring.ticker_prices.get(ticker, float("nan"))
                if np.isfinite(scoring.ticker_prices.get(ticker, float("nan")))
                else None
            ),
            "shares_to_hold": _target_share_count(
                final_weight=float(final_weights.get(ticker, 0.0)),
                price=scoring.ticker_prices.get(ticker, float("nan")),
                portfolio_size=float(portfolio_size),
            ),
        }
        for ticker in final_selected
    ]

    return {
        "date": eval_date,
        "mode": mode,
        "top_n": top_n,
        "selected": final_selected,
        "scores": {t: scoring.ticker_scores.get(t, float("nan")) for t in final_selected},
        "eligible_count": len(scoring.eligible_tickers),
        "all_scores": selection.score_candidates,
        "selection_scores": {t: scoring.ticker_scores.get(t, float("nan")) for t in selection.selected},
        "rebalance_selected": selection.selected,
        "selection_weights": selection.selection_weights,
        "final_weights": final_weights,
        "prior_holdings": prior_holdings,
        "prior_weights": prior_weight_map,
        "carried_holdings": exit_outcome.carried,
        "exit_triggered": exit_outcome.exit_triggered,
        "exit_values": exit_outcome.exit_values,
        "rebalance_rows": exit_outcome.action_rows,
        "holding_summary": holding_summary,
        "portfolio_state": portfolio_state_values,
    }
