"""Helpers extracted from ``select_tickers_on_date``.

Vendored verbatim from Astralanx `src/backtest/select_helpers.py`. Each function
captures one phase of per-date selection (pivots, eligibility, selection by
mode, prior-holdings exit logic). No `src.` imports — numpy/pandas/stdlib only.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Price pivots
# ---------------------------------------------------------------------------


@dataclass
class _PricePivots:
    pivot_adj_raw: pd.DataFrame
    pivot_adj: pd.DataFrame
    pivot_raw: pd.DataFrame | None
    pivot_raw_nofill: pd.DataFrame | None
    pivot_vol: pd.DataFrame | None
    pivot_open: pd.DataFrame | None
    pivot_high: pd.DataFrame | None
    pivot_low: pd.DataFrame | None


def build_price_pivots(prices_df: pd.DataFrame) -> _PricePivots:
    """Pivot prices into adj_close / close / volume / OHLC matrices, all
    aligned to the same date×ticker grid."""
    pivot_adj_raw = prices_df.pivot_table(
        index="date",
        columns="ticker",
        values="adj_close",
    ).sort_index()
    pivot_adj = pivot_adj_raw.ffill()

    pivot_raw = None
    pivot_raw_nofill = None
    if "close" in prices_df.columns:
        pivot_raw_nofill = prices_df.pivot_table(
            index="date",
            columns="ticker",
            values="close",
        ).sort_index()
        pivot_raw = pivot_raw_nofill.ffill()

    def _opt(col: str) -> pd.DataFrame | None:
        if col not in prices_df.columns:
            return None
        return prices_df.pivot_table(index="date", columns="ticker", values=col).sort_index().ffill()

    pivot_vol = _opt("volume")
    pivot_open = _opt("open")
    pivot_high = _opt("high")
    pivot_low = _opt("low")

    # Align all matrices to the same date×ticker grid.
    grid_index = pivot_adj.index
    grid_columns = pivot_adj.columns
    pivots = _PricePivots(
        pivot_adj_raw=pivot_adj_raw.reindex(index=grid_index, columns=grid_columns),
        pivot_adj=pivot_adj.reindex(index=grid_index, columns=grid_columns),
        pivot_raw=pivot_raw.reindex(index=grid_index, columns=grid_columns)
        if pivot_raw is not None
        else None,
        pivot_raw_nofill=pivot_raw_nofill.reindex(index=grid_index, columns=grid_columns)
        if pivot_raw_nofill is not None
        else None,
        pivot_vol=pivot_vol.reindex(index=grid_index, columns=grid_columns)
        if pivot_vol is not None
        else None,
        pivot_open=pivot_open.reindex(index=grid_index, columns=grid_columns)
        if pivot_open is not None
        else None,
        pivot_high=pivot_high.reindex(index=grid_index, columns=grid_columns)
        if pivot_high is not None
        else None,
        pivot_low=pivot_low.reindex(index=grid_index, columns=grid_columns)
        if pivot_low is not None
        else None,
    )
    return pivots


# ---------------------------------------------------------------------------
# Eligibility mask
# ---------------------------------------------------------------------------


def build_eligibility_mask_df(
    *,
    pivots: _PricePivots,
    max_stale_days: int,
    min_price: float,
    min_adv: float,
    adv_window: int,
    build_eligibility_mask_fn: Callable,
) -> pd.DataFrame:
    """Build the causal eligibility mask aligned to the price grid."""
    grid_index = pivots.pivot_adj.index
    grid_columns = pivots.pivot_adj.columns
    n_dates = len(grid_index)
    n_tickers = len(grid_columns)

    adj_raw_np = pivots.pivot_adj_raw.to_numpy(dtype=np.float32, copy=False)
    raw_notna = np.isfinite(adj_raw_np) & (adj_raw_np > 0)

    first_obs_idx = np.full(n_tickers, n_dates, dtype=np.int64)
    last_raw_obs_idx = np.full(n_tickers, -1, dtype=np.int64)
    for j in range(n_tickers):
        valid_idx = np.flatnonzero(raw_notna[:, j])
        if valid_idx.size:
            first_obs_idx[j] = int(valid_idx[0])
            last_raw_obs_idx[j] = int(valid_idx[-1])

    real_obs_row_idx = np.where(raw_notna, np.arange(n_dates)[:, None], -1)
    np.maximum.accumulate(real_obs_row_idx, axis=0, out=real_obs_row_idx)
    days_since_real = np.arange(n_dates)[:, None] - real_obs_row_idx
    days_since_real[real_obs_row_idx < 0] = n_dates
    gap_mask = days_since_real > int(max_stale_days)

    raw_close_np = (
        pivots.pivot_raw.to_numpy(dtype=np.float32, copy=False) if pivots.pivot_raw is not None else None
    )
    volume_np = (
        pivots.pivot_vol.to_numpy(dtype=np.float32, copy=False) if pivots.pivot_vol is not None else None
    )
    px_np = pivots.pivot_adj.to_numpy(dtype=np.float32, copy=False)

    mask_np = build_eligibility_mask_fn(
        n_dates=n_dates,
        n_tickers=n_tickers,
        first_obs_idx=first_obs_idx,
        last_raw_obs_idx=last_raw_obs_idx,
        gap_mask=gap_mask,
        raw_close=raw_close_np,
        volume=volume_np,
        adj_close=px_np,
        min_price=float(min_price),
        min_adv=float(min_adv),
        adv_window=int(adv_window),
    )
    return pd.DataFrame(mask_np, index=grid_index, columns=grid_columns)


# ---------------------------------------------------------------------------
# Feature matrices
# ---------------------------------------------------------------------------


def compute_feature_matrices(
    *,
    needed: list[str],
    pivots: _PricePivots,
    market_series: pd.Series | None,
    eligibility_mask_df: pd.DataFrame,
    rank_segment_ids: Any,
    compute_feature_matrix_fn: Callable,
    portfolio_state_features: set,
) -> dict[str, pd.DataFrame]:
    """Compute every non-portfolio-state feature listed in ``needed``."""
    feature_cache: dict[str, pd.DataFrame] = {}
    feature_matrices: dict[str, pd.DataFrame] = {}
    for fname in sorted(needed):
        if fname in portfolio_state_features:
            continue
        mat = compute_feature_matrix_fn(
            fname,
            pivots.pivot_adj,
            volume_aligned=pivots.pivot_vol,
            open_aligned=pivots.pivot_open,
            high_aligned=pivots.pivot_high,
            low_aligned=pivots.pivot_low,
            market_series=market_series,
            eligibility_mask=eligibility_mask_df,
            rank_segment_ids=rank_segment_ids,
            _cache=feature_cache,
        )
        if mat is not None:
            feature_matrices[fname] = mat
        else:
            _log.warning("  [WARN] Could not compute feature: %s", fname)
    return feature_matrices


# ---------------------------------------------------------------------------
# Per-ticker scoring
# ---------------------------------------------------------------------------


@dataclass
class _ScoringResult:
    eligible_tickers: list[str]
    ticker_scores: dict[str, float]
    ticker_filter_pass: dict[str, bool]
    ticker_features: dict[str, dict[str, float]]
    ticker_prices: dict[str, float]


def score_all_tickers(
    *,
    all_tickers: list[str],
    eligibility_mask_df: pd.DataFrame,
    eval_date: pd.Timestamp,
    feature_matrices: dict[str, pd.DataFrame],
    portfolio_state_values: dict[str, float],
    strat_dict: dict,
    mode: str,
    pivots: _PricePivots,
    build_feature_values_fn: Callable,
    evaluate_tree_fn: Callable,
) -> _ScoringResult:
    """Compute per-ticker features and main-tree / filter-tree scores."""
    eligible_tickers: list[str] = []
    ticker_scores: dict[str, float] = {}
    ticker_filter_pass: dict[str, bool] = {}
    ticker_features: dict[str, dict[str, float]] = {}
    ticker_prices: dict[str, float] = {}

    pivot_raw = pivots.pivot_raw
    pivot_adj = pivots.pivot_adj
    if pivot_raw is not None and eval_date in pivot_raw.index:
        price_row = pivot_raw.loc[eval_date]
    else:
        price_row = pivot_adj.loc[eval_date] if eval_date in pivot_adj.index else pd.Series(dtype=float)

    for ticker in all_tickers:
        px_val = price_row.get(ticker, float("nan"))
        ticker_prices[ticker] = float(px_val) if np.isfinite(px_val) else float("nan")

    for ticker in all_tickers:
        if ticker.startswith("^"):
            continue  # skip benchmark
        if ticker not in eligibility_mask_df.columns:
            continue
        if not bool(eligibility_mask_df.at[eval_date, ticker]):
            continue
        eligible_tickers.append(ticker)

        feat_values = build_feature_values_fn(
            ticker,
            eval_date,
            feature_matrices,
            portfolio_state_values,
        )
        ticker_features[ticker] = feat_values

        score = evaluate_tree_fn(strat_dict, feat_values)
        ticker_scores[ticker] = score

        if mode == "filter_then_rank" and strat_dict.get("filter_root"):
            fval = evaluate_tree_fn(strat_dict["filter_root"], feat_values)
            ticker_filter_pass[ticker] = fval != 0.0 and not math.isnan(fval)
        else:
            ticker_filter_pass[ticker] = True

    return _ScoringResult(
        eligible_tickers=eligible_tickers,
        ticker_scores=ticker_scores,
        ticker_filter_pass=ticker_filter_pass,
        ticker_features=ticker_features,
        ticker_prices=ticker_prices,
    )


# ---------------------------------------------------------------------------
# Selection by mode
# ---------------------------------------------------------------------------


@dataclass
class _SelectionResult:
    selected: list[str]
    score_candidates: dict[str, float]
    selection_weights: dict[str, float]


def resolve_dynamic_top_n(
    *,
    base_top_n: int,
    candidates: list[str],
    ticker_features: dict[str, dict[str, float]],
    strat_dict: dict,
    evaluate_tree_fn: Callable,
    strategy_switch_topn_threshold: float,
) -> int:
    """Resolve a dynamic top_n by evaluating ``dynamic_top_n_formula``."""
    dyn_formula = strat_dict.get("dynamic_top_n_formula")
    if not dyn_formula:
        return int(base_top_n)
    dyn_vals: list[float] = []
    for tkr in candidates:
        feats = ticker_features.get(tkr, {})
        v = evaluate_tree_fn(dyn_formula, feats)
        if np.isfinite(v):
            dyn_vals.append(float(v))
    if not dyn_vals:
        return int(base_top_n)
    dyn_n_float = float(np.nanmean(np.asarray(dyn_vals, dtype=np.float64)))
    if dyn_n_float <= strategy_switch_topn_threshold:
        return -1
    dyn_n = int(np.rint(dyn_n_float))
    return max(0, min(dyn_n, len(candidates)))


def select_by_mode(
    *,
    mode: str,
    top_n: int,
    scoring: _ScoringResult,
    strat_dict: dict,
    eval_date: pd.Timestamp,
    feature_matrices: dict[str, pd.DataFrame],
    portfolio_state_values: dict[str, float],
    build_feature_values_fn: Callable,
    evaluate_tree_fn: Callable,
    selection_weights_fn: Callable,
    resolve_dynamic_fn: Callable[[int, list[str]], int],
) -> _SelectionResult:
    """Apply the strategy's selection mode to the scored ticker set."""
    eligible_tickers = scoring.eligible_tickers
    ticker_scores = scoring.ticker_scores
    ticker_filter_pass = scoring.ticker_filter_pass

    selected: list[str] = []
    score_candidates: dict[str, float] = {}
    selection_weights: dict[str, float] = {}

    if mode == "filter_then_rank":
        survivors = [t for t in eligible_tickers if ticker_filter_pass.get(t, False)]
        score_tree = strat_dict.get("score_root", strat_dict)
        if score_tree is not strat_dict and score_tree is not None:
            for t in survivors:
                feat_vals = scoring.ticker_features.get(t) or build_feature_values_fn(
                    t,
                    eval_date,
                    feature_matrices,
                    portfolio_state_values,
                )
                ticker_scores[t] = evaluate_tree_fn(score_tree, feat_vals)

        valid_survivors = [
            (t, ticker_scores.get(t, float("nan")))
            for t in survivors
            if np.isfinite(ticker_scores.get(t, float("nan")))
        ]
        valid_survivors.sort(key=lambda x: x[1], reverse=True)
        score_candidates = {t: float(score) for t, score in valid_survivors}
        eff_top_n = resolve_dynamic_fn(top_n, [t for t, _ in valid_survivors])
        if eff_top_n > 0:
            selected = [t for t, _ in valid_survivors[:eff_top_n]]
            selection_weights = selection_weights_fn(selected, use_rank_weights=True)
        elif eff_top_n == 0:
            selected = []
        else:
            selected = [t for t, score in valid_survivors if np.isfinite(score) and score != 0.0]
            selection_weights = selection_weights_fn(selected, use_rank_weights=False)

    elif mode == "top_n" and top_n > 0:
        valid = [
            (t, ticker_scores.get(t, float("nan")))
            for t in eligible_tickers
            if np.isfinite(ticker_scores.get(t, float("nan")))
        ]
        valid.sort(key=lambda x: x[1], reverse=True)
        score_candidates = {t: float(score) for t, score in valid}
        eff_top_n = resolve_dynamic_fn(top_n, [t for t, _ in valid])
        if eff_top_n > 0:
            selected = [t for t, _ in valid[:eff_top_n]]
            selection_weights = selection_weights_fn(selected, use_rank_weights=True)

    elif mode == "boolean":
        selected = [
            t
            for t in eligible_tickers
            if ticker_scores.get(t, 0.0) != 0.0 and np.isfinite(ticker_scores.get(t, float("nan")))
        ]
        score_candidates = {
            t: float(ticker_scores[t])
            for t in eligible_tickers
            if np.isfinite(ticker_scores.get(t, float("nan")))
        }
        selection_weights = selection_weights_fn(selected, use_rank_weights=False)

    else:
        valid = [
            (t, ticker_scores.get(t, float("nan")))
            for t in eligible_tickers
            if np.isfinite(ticker_scores.get(t, float("nan")))
        ]
        valid.sort(key=lambda x: x[1], reverse=True)
        score_candidates = {t: float(score) for t, score in valid}
        if top_n > 0:
            selected = [t for t, _ in valid[:top_n]]
            selection_weights = selection_weights_fn(selected, use_rank_weights=True)
        else:
            selected = [t for t, score in valid if score != 0.0]
            selection_weights = selection_weights_fn(selected, use_rank_weights=False)

    return _SelectionResult(
        selected=selected,
        score_candidates=score_candidates,
        selection_weights=selection_weights,
    )


# ---------------------------------------------------------------------------
# Exit handling for prior holdings
# ---------------------------------------------------------------------------


@dataclass
class _ExitOutcome:
    final_selected: list[str]
    final_weights: dict[str, float]
    exit_values: dict[str, float]
    exit_triggered: list[str]
    carried: list[str]
    action_rows: list[dict[str, Any]]


def apply_exit_logic(
    *,
    selection: _SelectionResult,
    scoring: _ScoringResult,
    prior_holdings: list[str],
    prior_weight_map: dict[str, float],
    strat_dict: dict,
    eval_date: pd.Timestamp,
    feature_matrices: dict[str, pd.DataFrame],
    portfolio_state_values: dict[str, float],
    pivots: _PricePivots,
    prices_df: pd.DataFrame,
    portfolio_size: float,
    build_feature_values_fn: Callable,
    evaluate_tree_fn: Callable,
    resolve_position_size_fn: Callable,
    target_share_delta_fn: Callable,
    target_share_count_fn: Callable,
) -> _ExitOutcome:
    """Apply exit_root + prior-holdings carry/exit logic and emit action rows."""
    selected = selection.selected
    selection_weights = selection.selection_weights
    final_selected = list(selected)
    final_weights = dict(selection_weights)
    exit_values: dict[str, float] = {}
    exit_triggered: list[str] = []
    carried: list[str] = []
    action_rows: list[dict[str, Any]] = []

    if not prior_holdings:
        return _ExitOutcome(
            final_selected=final_selected,
            final_weights=final_weights,
            exit_values=exit_values,
            exit_triggered=exit_triggered,
            carried=carried,
            action_rows=action_rows,
        )

    exit_tree = strat_dict.get("exit_root")
    pivot_adj = pivots.pivot_adj

    if exit_tree:
        selected_set = set(selected)
        survivor_weights: dict[str, float] = {}
        for ticker in prior_holdings:
            if ticker in selected_set:
                continue
            force_exit = False
            eval_available = ticker in pivot_adj.columns
            if eval_available:
                last_obs = prices_df.loc[prices_df["ticker"].astype(str) == ticker, "date"].max()
                if pd.isna(last_obs) or pd.Timestamp(last_obs).normalize() < eval_date:
                    force_exit = True
            else:
                force_exit = True

            if not force_exit:
                feat_values = scoring.ticker_features.get(ticker)
                if feat_values is None:
                    feat_values = build_feature_values_fn(
                        ticker,
                        eval_date,
                        feature_matrices,
                        portfolio_state_values,
                    )
                exit_val = evaluate_tree_fn(exit_tree, feat_values)
                exit_val = float(exit_val) if np.isfinite(exit_val) else float("nan")
                exit_values[ticker] = exit_val
                if not np.isfinite(exit_val) or exit_val != 0.0:
                    force_exit = True
            else:
                exit_values[ticker] = float("nan")

            if force_exit:
                exit_triggered.append(ticker)
                continue

            prev_weight = float(prior_weight_map.get(ticker, 0.0))
            if prev_weight > 0.0:
                survivor_weights[ticker] = prev_weight
                carried.append(ticker)

        merged_weights = {**survivor_weights, **selection_weights}
        total_weight = float(sum(merged_weights.values()))
        if total_weight > 1e-12:
            merged_weights = {t: w / total_weight for t, w in merged_weights.items()}
        final_selected = list(survivor_weights.keys()) + list(selected)
        final_weights = {t: float(merged_weights.get(t, 0.0)) for t in final_selected}

    if final_weights:
        invested_fraction = resolve_position_size_fn(
            strat_dict,
            eval_date,
            feature_matrices,
            portfolio_state_values,
        )
        final_weights = {t: float(w * invested_fraction) for t, w in final_weights.items()}

    final_set = set(final_selected)
    for ticker in prior_holdings:
        prior_weight = float(prior_weight_map.get(ticker, 0.0))
        final_weight = float(final_weights.get(ticker, 0.0))
        price = scoring.ticker_prices.get(ticker, float("nan"))
        share_delta, shares_to_buy = target_share_delta_fn(
            prior_weight=prior_weight,
            final_weight=final_weight,
            price=price,
            portfolio_size=float(portfolio_size),
        )
        if ticker not in final_set:
            action = "exit"
        elif ticker in selected and prior_weight <= 0.0:
            action = "buy"
        elif ticker in selected and final_weight > prior_weight + 1e-12:
            action = "add"
        elif ticker in selected and final_weight < prior_weight - 1e-12:
            action = "trim"
        elif ticker in carried:
            action = "keep"
        else:
            action = "hold"
        action_rows.append(
            {
                "ticker": ticker,
                "prior_weight": prior_weight,
                "target_weight": final_weight,
                "score": scoring.ticker_scores.get(ticker, float("nan")),
                "exit_value": exit_values.get(ticker, float("nan")),
                "action": action,
                "trade_price": price if np.isfinite(price) else None,
                "share_delta": share_delta,
                "shares_to_buy": shares_to_buy,
                "shares_to_hold": target_share_count_fn(
                    final_weight=final_weight,
                    price=price,
                    portfolio_size=float(portfolio_size),
                ),
                "selected_today": ticker in selected,
            }
        )

    for ticker in final_selected:
        if ticker in prior_weight_map:
            continue
        price = scoring.ticker_prices.get(ticker, float("nan"))
        share_delta, shares_to_buy = target_share_delta_fn(
            prior_weight=0.0,
            final_weight=float(final_weights.get(ticker, 0.0)),
            price=price,
            portfolio_size=float(portfolio_size),
        )
        action_rows.append(
            {
                "ticker": ticker,
                "prior_weight": 0.0,
                "target_weight": float(final_weights.get(ticker, 0.0)),
                "score": scoring.ticker_scores.get(ticker, float("nan")),
                "exit_value": exit_values.get(ticker, float("nan")),
                "action": "buy",
                "trade_price": price if np.isfinite(price) else None,
                "share_delta": share_delta,
                "shares_to_buy": shares_to_buy,
                "shares_to_hold": target_share_count_fn(
                    final_weight=float(final_weights.get(ticker, 0.0)),
                    price=price,
                    portfolio_size=float(portfolio_size),
                ),
                "selected_today": True,
            }
        )

    return _ExitOutcome(
        final_selected=final_selected,
        final_weights=final_weights,
        exit_values=exit_values,
        exit_triggered=exit_triggered,
        carried=carried,
        action_rows=action_rows,
    )
