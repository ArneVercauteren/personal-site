import json
from pathlib import Path

import pandas as pd
import pytest

from paper_trading import benchmark
from paper_trading.benchmark import build_benchmark_snapshot


def test_build_benchmark_snapshot_normalizes_prices(tmp_path: Path):
    csv_path = tmp_path / "sp500.csv"
    csv_path.write_text(
        "date,adj_close,volume\n"
        "2026-01-02,100,10\n"
        "2026-01-05,110,12\n",
        encoding="utf-8",
    )

    payload = build_benchmark_snapshot(csv_path, initial_value=1_000_000)

    assert payload["as_of"] == "2026-01-05"
    assert payload["base_currency"] == "USD"
    benchmark = payload["benchmarks"][0]
    assert benchmark["id"] == "sp500"
    assert benchmark["name"] == "S&P 500"
    assert benchmark["equity_curve"] == [
        {"d": "2026-01-02", "v": 1_000_000.0},
        {"d": "2026-01-05", "v": 1_100_000.0},
    ]


def test_build_benchmark_snapshot_rejects_empty_input(tmp_path: Path):
    csv_path = tmp_path / "sp500.csv"
    csv_path.write_text("date,adj_close\n2026-01-02,\n", encoding="utf-8")

    with pytest.raises(ValueError, match="no usable benchmark rows"):
        build_benchmark_snapshot(csv_path)


def test_build_live_benchmark_snapshot_uses_adjusted_spy_prices(monkeypatch):
    def fake_get_ohlcv(tickers, start, end, session=None):
        assert tickers == ["SPY"]
        assert start == "1993-01-29"
        assert end == "2026-01-05"
        assert session == "session"
        return pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-01-02", "2026-01-05"]),
                "ticker": ["SPY", "SPY"],
                "open": [100.0, 200.0],
                "high": [100.0, 200.0],
                "low": [100.0, 200.0],
                "close": [100.0, 200.0],
                "adj_close": [50.0, 55.0],
                "volume": [10, 12],
            }
        )

    monkeypatch.setattr(benchmark.prices, "make_limiter_session", lambda: "session")
    monkeypatch.setattr(benchmark.prices, "get_ohlcv", fake_get_ohlcv)

    payload = benchmark.build_live_benchmark_snapshot(end="2026-01-05")

    assert payload["as_of"] == "2026-01-05"
    assert payload["benchmarks"][0]["equity_curve"] == [
        {"d": "2026-01-02", "v": 1_000_000.0},
        {"d": "2026-01-05", "v": 1_100_000.0},
    ]


def test_write_live_benchmark_snapshot_preserves_existing_prefix(monkeypatch, tmp_path: Path):
    out = tmp_path / "benchmark.json"
    out.write_text(
        json.dumps(
            {
                "as_of": "2026-01-05",
                "base_currency": "USD",
                "benchmarks": [
                    {
                        "id": "sp500",
                        "name": "S&P 500",
                        "equity_curve": [
                            {"d": "2026-01-02", "v": 1_000_000.0},
                            {"d": "2026-01-05", "v": 1_123_456.0},
                        ],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        benchmark,
        "build_live_benchmark_snapshot",
        lambda start, end, ticker: {
            "as_of": "2026-01-06",
            "base_currency": "USD",
            "benchmarks": [
                {
                    "id": "sp500",
                    "name": "S&P 500",
                    "equity_curve": [
                        {"d": "2026-01-02", "v": 1_000_000.0},
                        {"d": "2026-01-05", "v": 1_100_000.0},
                        {"d": "2026-01-06", "v": 1_210_000.0},
                    ],
                }
            ],
        },
    )

    payload = benchmark.write_live_benchmark_snapshot(out, end="2026-01-06")

    assert payload["as_of"] == "2026-01-06"
    assert payload["benchmarks"][0]["equity_curve"] == [
        {"d": "2026-01-02", "v": 1_000_000.0},
        {"d": "2026-01-05", "v": 1_123_456.0},
        {"d": "2026-01-06", "v": 1_235_801.6},
    ]
