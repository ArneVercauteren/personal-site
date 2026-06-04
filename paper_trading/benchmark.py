"""Build the public S&P 500 benchmark snapshot.

The public site is static-first, so the benchmark overlay is a committed JSON
snapshot rather than a browser-side market-data fetch. The source CSV is an
S&P 500 / SPY proxy with at least ``date`` and ``adj_close`` columns.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "public" / "data" / "benchmark.json"
DEFAULT_INITIAL_VALUE = 1_000_000.0


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

    rows.sort(key=lambda r: r[0])
    deduped: dict[str, float] = {}
    for date, price in rows:
        deduped[date] = price

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


def write_benchmark_snapshot(csv_path: str | Path, output_path: str | Path = DEFAULT_OUTPUT) -> dict:
    payload = build_benchmark_snapshot(csv_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build public/data/benchmark.json.")
    parser.add_argument("csv", help="S&P 500 benchmark CSV with date and adj_close/close.")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT), help="Output JSON path.")
    args = parser.parse_args(argv)

    payload = write_benchmark_snapshot(args.csv, args.out)
    print(
        f"wrote {args.out} ({len(payload['benchmarks'][0]['equity_curve'])} points, "
        f"as_of={payload['as_of']})"
    )


if __name__ == "__main__":
    main()
