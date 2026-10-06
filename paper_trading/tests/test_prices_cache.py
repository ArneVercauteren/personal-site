"""Tests for resumable Yahoo chunk caching."""

from __future__ import annotations

import pandas as pd
import pytest

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


def test_partial_batch_retries_only_missing_symbols_and_caches_recovery(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPER_TRADING_SYNTHETIC", raising=False)
    calls = []
    sleeps = []

    def fetch(tickers, *args, **kwargs):
        calls.append(list(tickers))
        return _bars(["AAA"] if len(calls) == 1 else tickers)

    monkeypatch.setattr(prices, "get_ohlcv", fetch)
    monkeypatch.setattr(prices.time, "sleep", sleeps.append)
    for _ in range(2):
        result = prices.get_ohlcv_chunked(
            ["AAA", "BBB"], "2026-01-01", "2026-01-06", chunk=2,
            pause=0, cache_dir=tmp_path,
        )
        assert set(result["ticker"]) == {"AAA", "BBB"}
        assert not result.duplicated(["ticker", "date"]).any()
    assert calls == [["AAA", "BBB"], ["BBB"]]
    assert sleeps == [2.0]


def test_exhausted_partial_failure_is_reported_and_not_cached(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("PAPER_TRADING_SYNTHETIC", raising=False)
    calls = []

    def fetch(tickers, *args, **kwargs):
        calls.append(list(tickers))
        if tickers == ["BBB"]:
            raise RuntimeError("temporary Yahoo error")
        return _bars(["AAA"])

    monkeypatch.setattr(prices, "get_ohlcv", fetch)
    result = prices.get_ohlcv_chunked(
        ["AAA", "BBB"], "2026-01-01", "2026-01-06", pause=0,
        retry_pause=0, cache_dir=tmp_path,
    )
    assert set(result["ticker"]) == {"AAA"}
    assert calls == [["AAA", "BBB"], ["BBB"], ["BBB"], ["BBB"]]
    assert "unresolved prices after retries: BBB" in capsys.readouterr().out
    assert not list(tmp_path.glob("*.csv.gz"))


def test_empty_batch_is_retried(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING_PRICE_CACHE", "0")
    calls = []

    def fetch(tickers, *args, **kwargs):
        calls.append(list(tickers))
        if len(calls) == 1:
            raise RuntimeError("no data")
        return _bars(tickers)

    monkeypatch.setattr(prices, "get_ohlcv", fetch)
    result = prices.get_ohlcv_chunked(["AAA"], "2026-01-01", "2026-01-06", retry_pause=0)
    assert len(calls) == 2
    assert not result.empty


def test_review_date_gap_bypasses_historical_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPER_TRADING_SYNTHETIC", raising=False)
    partial = _bars(["AAA"])
    partial = partial[partial["date"] < pd.Timestamp("2026-01-05")]
    prices._write_chunk_cache(["AAA"], "2026-01-01", "2026-01-06", partial, tmp_path)
    calls = []

    def fetch(tickers, *args, **kwargs):
        calls.append(list(tickers))
        return _bars(tickers)

    monkeypatch.setattr(prices, "get_ohlcv", fetch)
    result = prices.get_ohlcv_chunked(
        ["AAA"], "2026-01-01", "2026-01-06", cache_dir=tmp_path,
        required_dates=("2026-01-05",), retry_pause=0,
    )
    assert calls == [["AAA"]]
    assert not prices.missing_price_tickers(result, ["AAA"], ("2026-01-05",))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 0.0, -1.0])
def test_unusable_bars_do_not_count_as_returned_prices(bad):
    bars = _bars(["AAA", "BBB"])
    bars.loc[bars["ticker"] == "BBB", "adj_close"] = bad
    assert prices.missing_price_tickers(bars, ["AAA", "BBB"]) == ["BBB"]
