from pathlib import Path

import pytest

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
