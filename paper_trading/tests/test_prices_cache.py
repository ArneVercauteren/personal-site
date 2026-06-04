"""Tests for resumable Yahoo chunk caching."""

from __future__ import annotations

import pandas as pd

from paper_trading import prices


def _bars(tickers: list[str]) -> pd.DataFrame:
    rows = []
    for ticker in tickers:
        for day in pd.date_range("2026-01-02", "2026-01-05", freq="B"):
            rows.append(
                {
                    "date": day,
                    "ticker": ticker,
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.0,
                    "close": 10.5,
                    "adj_close": 10.5,
                    "volume": 1000,
                }
            )
    return pd.DataFrame(rows)


def test_get_ohlcv_chunked_reuses_completed_chunk_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPER_TRADING_SYNTHETIC", raising=False)
    calls: list[tuple[str, ...]] = []

    def fake_get_ohlcv(tickers, start, end, *, session=None, threads=True):
        calls.append(tuple(tickers))
        return _bars(list(tickers))

    monkeypatch.setattr(prices, "get_ohlcv", fake_get_ohlcv)

    first = prices.get_ohlcv_chunked(
        ["AAA", "BBB"],
        "2026-01-01",
        "2026-01-06",
        chunk=2,
        pause=0,
        cache_dir=tmp_path,
    )
    second = prices.get_ohlcv_chunked(
        ["AAA", "BBB"],
        "2026-01-01",
        "2026-01-06",
        chunk=2,
        pause=0,
        cache_dir=tmp_path,
    )

    assert calls == [("AAA", "BBB")]
    pd.testing.assert_frame_equal(first.reset_index(drop=True), second.reset_index(drop=True))
