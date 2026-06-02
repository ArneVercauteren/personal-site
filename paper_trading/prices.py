"""Price-data adapter — keyless daily bars.

Two views of the same data:
  * `get_ohlcv(...)` → a long-format OHLCV frame (date, ticker, open, high, low,
    close, adj_close, volume) — what the vendored DSL evaluator consumes.
  * `get_price_history(...)` → `(opens, closes)` wide frames on an adjusted basis
    — what the simulator's fill/mark accounting uses.

The default source is yfinance (keyless; daily bars are all the paper sim needs).
No API key is ever read here — see `docs/concepts/separation-from-darwin.md`.

Determinism: historical daily bars are fixed once published, so re-running the
sim on a past date reproduces the same curve up to that date. The price source
is the only point of non-determinism, and only at the moving "today" edge.

Offline mode: set `PAPER_TRADING_SYNTHETIC=1` to generate deterministic
synthetic bars instead of hitting the network. For local development and tests
only — CI never sets it, so committed data always comes from real prices.
"""

from __future__ import annotations

import hashlib
import os

import numpy as np
import pandas as pd

__all__ = [
    "get_ohlcv",
    "get_price_history",
    "long_to_wide",
    "wide_raw_and_dollar_volume",
    "use_synthetic",
]

_OHLCV_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]


def use_synthetic() -> bool:
    """True when the synthetic offline source is requested via env."""
    return os.environ.get("PAPER_TRADING_SYNTHETIC", "") not in ("", "0", "false")


def get_ohlcv(
    tickers: list[str],
    start: str,
    end: str,
    *,
    session=None,
    threads: bool = True,
) -> pd.DataFrame:
    """Long-format daily OHLCV for `tickers` over [start, end].

    Columns: date, ticker, open, high, low, close, adj_close, volume. `close` is
    the raw (unadjusted) close used for the min-price eligibility rule; `adj_close`
    is split/dividend-adjusted and drives feature computation. This matches the
    schema the vendored Darwin evaluator expects.

    `session` (a rate-limited/cached requests session) and `threads` are passed to
    yfinance — the bulk universe build uses them to stay under Yahoo's rate limit
    (see `universe.py`); normal strategy fetches leave the defaults.
    """
    if use_synthetic():
        df = _synthetic_ohlcv(tickers, start, end)
    else:
        df = _yfinance_ohlcv(tickers, start, end, session=session, threads=threads)
    df = df.dropna(subset=["adj_close"]).sort_values(["ticker", "date"]).reset_index(drop=True)
    return df[_OHLCV_COLUMNS]


def long_to_wide(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Adjusted `(opens, closes)` wide frames from a long OHLCV frame.

    Both are on an adjusted basis: `closes` = adj_close; `opens` = the raw open
    scaled by the day's adjustment factor (adj_close / close), so opens and
    closes stay consistent across splits/dividends. Rows with any missing ticker
    are dropped so the simulator never marks against a NaN.
    """
    work = df.copy()
    factor = np.where(work["close"] > 0, work["adj_close"] / work["close"], 1.0)
    work["adj_open"] = work["open"] * factor
    opens = work.pivot_table(index="date", columns="ticker", values="adj_open").sort_index()
    closes = work.pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
    common = opens.dropna(how="any").index.intersection(closes.dropna(how="any").index)
    tickers = list(closes.columns)
    return opens.loc[common, tickers], closes.loc[common, tickers]


def wide_raw_and_dollar_volume(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """`(raw_close, dollar_volume)` wide frames for the Darwin cost model.

    The cost model scales slippage by **nominal** share price and sizes market
    impact against **review-date dollar volume** — both of which are raw-price
    notions, so this returns the *unadjusted* close and `close × volume` (the
    same `adv = price × volume` Darwin's engine uses). Indexed by date, columns
    by ticker; callers align to the simulator's trading-day index.
    """
    raw_close = df.pivot_table(index="date", columns="ticker", values="close").sort_index()
    dv = df.copy()
    dv["dollar_volume"] = dv["close"] * dv["volume"]
    dollar_volume = dv.pivot_table(
        index="date", columns="ticker", values="dollar_volume"
    ).sort_index()
    return raw_close, dollar_volume


def get_price_history(
    tickers: list[str], start: str, end: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch daily adjusted `(opens, closes)` for `tickers` over [start, end].

    Columns are ordered to match `tickers`. Convenience wrapper over `get_ohlcv`
    + `long_to_wide` used by the momentum (non-DSL) path.
    """
    df = get_ohlcv(tickers, start, end)
    opens, closes = long_to_wide(df)
    cols = [t for t in tickers if t in closes.columns]
    return opens[cols], closes[cols]


def _yfinance_ohlcv(
    tickers: list[str], start: str, end: str, *, session=None, threads: bool = True
) -> pd.DataFrame:
    import yfinance as yf

    # `end` is exclusive in yfinance; bump by a day so today's bar is included.
    end_excl = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    kwargs = dict(threads=threads)
    if session is not None:
        kwargs["session"] = session
    try:
        raw = yf.download(
            tickers, start=start, end=end_excl,
            auto_adjust=False, progress=False, group_by="column", **kwargs,
        )
    except TypeError:
        # Older/newer yfinance may not accept `session`/`threads` on download.
        raw = yf.download(
            tickers, start=start, end=end_excl,
            auto_adjust=False, progress=False, group_by="column",
        )
    return _frame_from_yf(raw, tickers)


def _frame_from_yf(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """Reshape a yfinance download into the long OHLCV frame."""
    if raw.empty:
        raise RuntimeError(f"yfinance returned no data for {tickers}")

    fields = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "adj_close": "Adj Close",
        "volume": "Volume",
    }
    frames = {col: _field(raw, yf_name, tickers) for col, yf_name in fields.items()}

    records = []
    for t in tickers:
        sub = pd.DataFrame({col: frames[col][t] for col in fields})
        sub.index = pd.to_datetime(sub.index)
        sub = sub.dropna(subset=["adj_close"])
        sub["ticker"] = t
        sub["date"] = sub.index
        records.append(sub)
    return pd.concat(records, ignore_index=True)


def _field(raw: pd.DataFrame, field: str, tickers: list[str]) -> pd.DataFrame:
    """Extract one OHLC field as a ticker-columned frame.

    Handles both the multi-ticker (MultiIndex columns) and single-ticker (flat
    columns) shapes yfinance returns.
    """
    if isinstance(raw.columns, pd.MultiIndex):
        df = raw[field].copy()
        if isinstance(df, pd.Series):
            df = df.to_frame(tickers[0])
    else:
        df = raw[[field]].copy()
        df.columns = [tickers[0]]
    return df.reindex(columns=tickers)


def _synthetic_ohlcv(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """Deterministic geometric-random-walk OHLCV seeded per ticker.

    Each ticker's path depends only on its symbol and the date range, so runs are
    perfectly reproducible. close == adj_close (no synthetic splits). Used for
    offline dev / tests only.
    """
    dates = pd.bdate_range(start=start, end=end)
    records = []
    n = len(dates)
    for t in tickers:
        seed = int(hashlib.sha256(t.encode()).hexdigest(), 16) % (2**32)
        rng = np.random.default_rng(seed)
        drift = rng.uniform(0.0001, 0.0006)
        vol = rng.uniform(0.010, 0.022)
        rets = rng.normal(drift, vol, size=n)
        start_px = rng.uniform(40, 400)
        close = start_px * np.exp(np.cumsum(rets))
        prev_close = np.concatenate([[start_px], close[:-1]])
        gaps = rng.normal(0.0, vol * 0.4, size=n)
        open_ = prev_close * np.exp(gaps)
        hi_extra = np.abs(rng.normal(0.0, vol, size=n))
        lo_extra = np.abs(rng.normal(0.0, vol, size=n))
        high = np.maximum(open_, close) * (1.0 + hi_extra)
        low = np.minimum(open_, close) * (1.0 - lo_extra)
        # Liquid synthetic volume so the ADV filter never spuriously excludes.
        volume = rng.uniform(2e6, 8e6, size=n) * 1e3 / np.maximum(close, 1.0)
        records.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": t,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "adj_close": close,
                    "volume": volume,
                }
            )
        )
    return pd.concat(records, ignore_index=True)
