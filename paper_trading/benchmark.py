"""Build the public S&P 500 benchmark snapshot.

The public site is static-first, so the benchmark overlay is a committed JSON
snapshot rather than a browser-side market-data fetch. The default source is
the same keyless Yahoo-backed price adapter used by the open-strategy updater,
with a CSV path kept for one-off historical imports.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import pandas as pd

from . import prices

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "public" / "data" / "benchmark.json"
DEFAULT_INITIAL_VALUE = 1_000_000.0
DEFAULT_BENCHMARK_TICKER = "SPY"
DEFAULT_START = "1993-01-29"


def _price(row: dict[str, str]) -> float | None:
    for key in ("adj_close", "adjclose", "close", "Close"):
        raw = row.get(key)
        if raw not in (None, ""):
            value = float(raw)
            return value if value > 0 else None
    return None


def build_benchmark_snapshot(
    csv_path: str | Path,
    *,
    benchmark_id: str = "sp500",
    name: str = "S&P 500",
    base_currency: str = "USD",
    initial_value: float = DEFAULT_INITIAL_VALUE,
) -> dict:
    """Return a `public/data/benchmark.json` payload from a local CSV."""

    path = Path(csv_path)
    rows: list[tuple[str, float]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "date" not in {c.strip() for c in reader.fieldnames}:
            raise ValueError(f"{path}: expected a 'date' column")
        for row in reader:
            date = (row.get("date") or "").strip()[:10]
            price = _price(row)
            if not date or price is None:
                continue
            rows.append((date, price))

    if not rows:
        raise ValueError(f"{path}: no usable benchmark rows")

    return build_benchmark_snapshot_from_rows(
        rows,
        benchmark_id=benchmark_id,
        name=name,
        base_currency=base_currency,
        initial_value=initial_value,
    )


def build_benchmark_snapshot_from_rows(
    rows: list[tuple[str, float]],
    *,
    benchmark_id: str = "sp500",
    name: str = "S&P 500",
    base_currency: str = "USD",
    initial_value: float = DEFAULT_INITIAL_VALUE,
) -> dict:
    """Return a benchmark snapshot from `(date, adjusted_price)` rows."""

    rows.sort(key=lambda r: r[0])
    deduped: dict[str, float] = {}
    for date, price in rows:
        if price > 0:
            deduped[date] = price

    if not deduped:
        raise ValueError("no usable benchmark rows")

    base = next(iter(deduped.values()))
    points = [
        {"d": date, "v": round(price / base * initial_value, 2)}
        for date, price in deduped.items()
    ]

    return {
        "as_of": points[-1]["d"],
        "base_currency": base_currency,
        "benchmarks": [
            {
                "id": benchmark_id,
                "name": name,
                "equity_curve": points,
            }
        ],
    }


def build_live_benchmark_snapshot(
    *,
    start: str = DEFAULT_START,
    end: str | None = None,
    ticker: str = DEFAULT_BENCHMARK_TICKER,
    benchmark_id: str = "sp500",
    name: str = "S&P 500",
    base_currency: str = "USD",
    initial_value: float = DEFAULT_INITIAL_VALUE,
) -> dict:
    """Fetch and normalize the S&P 500 benchmark proxy through `end`.

    SPY is used because the existing published curve begins at SPY inception
    (1993-01-29) and is adjusted for distributions via `adj_close`.
    """

    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    df = prices.get_ohlcv([ticker], start, end, session=prices.make_limiter_session())
    rows = [
        (pd.Timestamp(row.date).strftime("%Y-%m-%d"), float(row.adj_close))
        for row in df.itertuples(index=False)
        if row.ticker == ticker
    ]
    if not rows:
        raise ValueError(f"{ticker}: no usable benchmark rows")
    return build_benchmark_snapshot_from_rows(
        rows,
        benchmark_id=benchmark_id,
        name=name,
        base_currency=base_currency,
        initial_value=initial_value,
    )


def extend_existing_benchmark_snapshot(existing: dict, fetched: dict) -> dict:
    """Preserve an existing benchmark prefix and append newly fetched bars."""

    existing_benchmarks = existing.get("benchmarks") or []
    fetched_benchmarks = fetched.get("benchmarks") or []
    if not existing_benchmarks or not fetched_benchmarks:
        return fetched

    existing_benchmark = existing_benchmarks[0]
    fetched_benchmark = fetched_benchmarks[0]
    existing_curve = existing_benchmark.get("equity_curve") or []
    fetched_curve = fetched_benchmark.get("equity_curve") or []
    if not existing_curve or not fetched_curve:
        return fetched

    last_existing = existing_curve[-1]
    last_date = last_existing["d"]
    fetched_by_date = {point["d"]: point for point in fetched_curve}
    anchor = fetched_by_date.get(last_date)
    if anchor is None:
        prior = [point for point in fetched_curve if point["d"] <= last_date]
        if not prior:
            return fetched
        anchor = prior[-1]

    if anchor["v"] <= 0:
        return fetched

    scale = float(last_existing["v"]) / float(anchor["v"])
    appended = [
        {"d": point["d"], "v": round(float(point["v"]) * scale, 2)}
        for point in fetched_curve
        if point["d"] > last_date
    ]
    if not appended:
        return existing

    out = dict(existing)
    benchmark = dict(existing_benchmark)
    benchmark["equity_curve"] = existing_curve + appended
    out["benchmarks"] = [benchmark, *existing_benchmarks[1:]]
    out["as_of"] = appended[-1]["d"]
    return out


def write_benchmark_snapshot(csv_path: str | Path, output_path: str | Path = DEFAULT_OUTPUT) -> dict:
    payload = build_benchmark_snapshot(csv_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def write_live_benchmark_snapshot(
    output_path: str | Path = DEFAULT_OUTPUT,
    *,
    start: str = DEFAULT_START,
    end: str | None = None,
    ticker: str = DEFAULT_BENCHMARK_TICKER,
    preserve_existing: bool = True,
) -> dict:
    payload = build_live_benchmark_snapshot(start=start, end=end, ticker=ticker)
    out = Path(output_path)
    if preserve_existing and out.exists():
        existing = json.loads(out.read_text(encoding="utf-8"))
        payload = extend_existing_benchmark_snapshot(existing, payload)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build public/data/benchmark.json.")
    parser.add_argument(
        "csv",
        nargs="?",
        help="Optional S&P 500 benchmark CSV with date and adj_close/close.",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT), help="Output JSON path.")
    parser.add_argument("--start", default=DEFAULT_START, help="Live fetch start date.")
    parser.add_argument("--end", help="Live fetch end date; defaults to today.")
    parser.add_argument("--ticker", default=DEFAULT_BENCHMARK_TICKER, help="Yahoo ticker.")
    parser.add_argument(
        "--no-preserve-existing",
        action="store_true",
        help="Regenerate the whole live benchmark instead of appending to the existing file.",
    )
    args = parser.parse_args(argv)

    if args.csv:
        payload = write_benchmark_snapshot(args.csv, args.out)
    else:
        payload = write_live_benchmark_snapshot(
            args.out,
            start=args.start,
            end=args.end,
            ticker=args.ticker,
            preserve_existing=not args.no_preserve_existing,
        )
    print(
        f"wrote {args.out} ({len(payload['benchmarks'][0]['equity_curve'])} points, "
        f"as_of={payload['as_of']})"
    )


if __name__ == "__main__":
    main()
