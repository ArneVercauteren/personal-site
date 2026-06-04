"""Unified causal eligibility mask for cross-sectional computations.

Vendored from Astralanx `src/backtest/eligibility.py`. The only change from the
original is that the `min_price` / `min_adv` fallback reads vendored module
constants instead of `src.config.get_config()` (callers in `select_on_date`
always pass explicit values, so this fallback is for safety only).
"""

from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# Eligibility thresholds (constants; override via function args if needed)
# ---------------------------------------------------------------------------
_ADV_WINDOW_DEFAULT: int = 63  # trailing median window
# Mirrors Astralanx src/config/engine.py realism defaults.
_MIN_PRICE_DEFAULT: float = 10.0
_MIN_MEDIAN_DOLLAR_VOLUME_DEFAULT: float = 5_000_000.0


def build_eligibility_mask(
    *,
    n_dates: int,
    n_tickers: int,
    first_obs_idx: np.ndarray,
    last_raw_obs_idx: np.ndarray,
    gap_mask: np.ndarray,
    raw_close: np.ndarray | None = None,
    volume: np.ndarray | None = None,
    adj_close: np.ndarray | None = None,
    min_price: float | None = None,
    min_adv: float | None = None,
    adv_window: int = _ADV_WINDOW_DEFAULT,
) -> np.ndarray:
    """Build the unified eligibility mask.

    Parameters
    ----------
    n_dates, n_tickers : int
        Shape of the date × ticker grid.
    first_obs_idx : (n_tickers,) int64
        First master-grid date index where ticker has valid data.
    last_raw_obs_idx : (n_tickers,) int64
        Last date index with a real (non-ffilled) observation.
    gap_mask : (n_dates, n_tickers) bool
        True where price is stale / gap-filled beyond threshold.
    raw_close : (n_dates, n_tickers) float32, optional
        Unadjusted close prices (ffilled).  Used for the min-price rule.
    volume : (n_dates, n_tickers) float32, optional
        Adjusted volume.  Combined with *adj_close* for dollar-volume.
    adj_close : (n_dates, n_tickers) float32, optional
        Adjusted close prices.  Used with *volume* for dollar-volume.
    min_price : float
        Minimum unadjusted close to be eligible.
    min_adv : float
        Minimum 63-day trailing median dollar volume (shifted by 1 day).
    adv_window : int
        Window for the trailing median dollar volume.

    Returns
    -------
    eligible : (n_dates, n_tickers) bool
        True = ticker is eligible on that date.
    """
    if min_price is None:
        min_price = _MIN_PRICE_DEFAULT
    if min_adv is None:
        min_adv = _MIN_MEDIAN_DOLLAR_VOLUME_DEFAULT

    # Start with all-True and progressively mask out.
    eligible = np.ones((n_dates, n_tickers), dtype=bool)

    # -- 1. Has started trading: d >= first_obs_idx[ticker] ----------------
    date_idx = np.arange(n_dates, dtype=np.int64)[:, None]  # (n_dates, 1)
    eligible &= date_idx >= first_obs_idx[None, :]  # broadcast (n_dates, n_tickers)

    # -- 2. Has not passed last raw observation: d <= last_raw_obs_idx[ticker]
    eligible &= date_idx <= last_raw_obs_idx[None, :]

    # -- 3. Not stale / gap-filled -----------------------------------------
    gm = np.asarray(gap_mask, dtype=bool)
    if gm.shape == (n_dates, n_tickers):
        eligible &= ~gm
    elif gm.shape[0] >= n_dates and gm.shape[1] >= n_tickers:
        eligible &= ~gm[:n_dates, :n_tickers]

    # -- 4. Min unadjusted-close price rule --------------------------------
    if raw_close is not None and min_price > 0:
        rc = np.asarray(raw_close, dtype=np.float32)
        if rc.shape == (n_dates, n_tickers):
            eligible &= np.isfinite(rc) & (rc >= min_price)

    # -- 5. Trailing 63-day median dollar volume, shifted by 1 day ---------
    if volume is not None and adj_close is not None and min_adv > 0:
        eligible &= _adv_filter(
            adj_close=adj_close,
            volume=volume,
            n_dates=n_dates,
            n_tickers=n_tickers,
            window=adv_window,
            min_adv=min_adv,
        )

    return eligible


def _adv_filter(
    *,
    adj_close: np.ndarray,
    volume: np.ndarray,
    n_dates: int,
    n_tickers: int,
    window: int,
    min_adv: float,
) -> np.ndarray:
    """Compute trailing *window*-day median dollar volume, shifted by 1 day.

    Dollar volume = adj_close × volume.
    The shift-by-1 ensures the ADV filter is strictly causal: the eligibility
    decision on date d uses information available at end of day d-1.

    Returns a (n_dates, n_tickers) bool mask (True = passes the filter).
    """
    ac = np.asarray(adj_close, dtype=np.float64)
    vol = np.asarray(volume, dtype=np.float64)

    # Guard bad shapes
    if ac.shape != (n_dates, n_tickers) or vol.shape != (n_dates, n_tickers):
        return np.ones((n_dates, n_tickers), dtype=bool)

    dv = ac * vol  # (n_dates, n_tickers)
    dv[~np.isfinite(dv)] = np.nan

    # Rolling median via a stride-trick sliding window.
    # For very large matrices we use a column-chunked approach to keep memory
    # bounded and avoid materialising a (n_dates, n_tickers, window) tensor.
    median_dv = _rolling_median_2d(dv, window)

    # Shift by 1 day (row 0 becomes NaN).
    shifted = np.empty_like(median_dv)
    shifted[0, :] = np.nan
    shifted[1:, :] = median_dv[:-1, :]

    return np.isfinite(shifted) & (shifted >= min_adv)


def _rolling_median_2d(arr: np.ndarray, window: int) -> np.ndarray:
    """Row-wise rolling median with min_periods=window.

    Uses column-chunked pandas rolling for efficiency on large matrices.
    """
    import pandas as pd

    _n_rows, n_cols = arr.shape
    out = np.full_like(arr, np.nan, dtype=np.float64)
    CHUNK = 512
    for j0 in range(0, n_cols, CHUNK):
        j1 = min(n_cols, j0 + CHUNK)
        chunk_df = pd.DataFrame(arr[:, j0:j1])
        rolled = chunk_df.rolling(window=window, min_periods=window).median()
        out[:, j0:j1] = rolled.to_numpy(dtype=np.float64, copy=False)
    return out
