"""Self-refreshing tradable universe — keyless, Darwin-independent.

The paper sim needs a *current* set of tickers each deployed strategy picks from.
Snapshotting Darwin's curated universe would inherit Darwin's data age (a king
deployed off six-month-old data could never hold anything newer), so instead this
builds a fresh universe from public, keyless sources and the same filters Darwin
uses:

1. **Listings** — the Nasdaq Trader symbol directory (`nasdaqlisted.txt` +
   `otherlisted.txt`): every NYSE / NASDAQ / AMEX symbol, updated each trading
   day, free and keyless, with ETF / test-issue flags. This is "the same
   exchanges", sourced from the exchanges (yfinance has no listing endpoint).
2. **Symbol filters** — drop test issues, warrants / units / rights / preferred,
   and leveraged / inverse products (regexes vendored from Darwin's
   `src/data/ticker_filtering.py`).
3. **Liquidity / price** — keep names with last close ≥ `min_price` and trailing
   median dollar volume ≥ `min_adv`, ranked by liquidity and capped to `cap` so
   the daily sim's yfinance fetches stay bounded. These are Darwin's
   `FinancialRealism` thresholds, the same ones `darwin_eval/eligibility.py`
   re-applies at every rebalance.

The heavy step (3) runs **monthly** in its own workflow and commits
`public/data/universe.json`; the daily updater just reads it via
`resolve_universe`. A deployed strategy with an explicit non-empty `universe`
keeps it; one that omits it (or leaves it empty) resolves to this shared file.
See `docs/subsystems/universe.md`.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from . import prices

__all__ = [
    "DEFAULT_UNIVERSE_PATH",
    "fetch_symbol_directory",
    "filter_common_symbols",
    "rank_by_liquidity",
    "build_universe",
    "load_universe",
    "resolve_universe",
]

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_UNIVERSE_PATH = REPO_ROOT / "public" / "data" / "universe.json"

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

# Darwin FinancialRealism defaults (src/config/engine.py).
DEFAULT_MIN_PRICE = 10.0
DEFAULT_MIN_ADV = 5_000_000.0
DEFAULT_CAP = 1200
DEFAULT_LOOKBACK_DAYS = 120  # ~63 trading days of history for the median

# --- symbol filters (vendored from Darwin src/data/ticker_filtering.py) -------
_NON_COMMON_SUFFIXES: set[str] = {
    "-WS", "-WS-A", "-WS-B", "-W", "-U", "-R", "-R-W", "-WD", "-CL",
}
_PREFERRED_RE = re.compile(r"-P(?:-[A-Z])?(?:-CL)?$")
# SPAC-style non-common tails on 5+ char tickers: warrants/units/rights.
_NON_COMMON_TAIL_RE = re.compile(r"(?:WS[AB]?|W|U|R)$")
_LEVERAGED_INVERSE_TEXT_RE = re.compile(
    r"(?:\b(?:2x|3x|4x|5x|ultra(?:pro)?|leveraged|inverse|bear(?:ish)?)\b)",
    re.IGNORECASE,
)


def normalize_ticker(value: str) -> str:
    """Upper-case; map share-class separators to yfinance's hyphen form."""
    return str(value or "").strip().upper().replace(".", "-").replace("/", "-")


def _is_non_common(symbol: str, name: str) -> bool:
    """True for warrants / units / rights / preferred / leveraged / inverse."""
    if "$" in symbol:  # CQS preferred / when-issued marker
        return True
    if symbol in _NON_COMMON_SUFFIXES or any(symbol.endswith(s) for s in _NON_COMMON_SUFFIXES):
        return True
    if _PREFERRED_RE.search(symbol):
        return True
    # The bare W/U/R tail only flags 5+ char SPAC-style symbols; real common
    # stocks that short (e.g. "U", "F") are kept.
    if len(symbol) >= 5 and _NON_COMMON_TAIL_RE.search(symbol):
        return True
    if _LEVERAGED_INVERSE_TEXT_RE.search(name or ""):
        return True
    return False


# --- (1) listings -------------------------------------------------------------
def _parse_pipe_table(text: str, symbol_col: str, name_col: str, etf_col: str, test_col: str):
    """Parse a Nasdaq Trader pipe-delimited directory into row dicts.

    The last line ("File Creation Time: …") and any short/blank lines are skipped.
    """
    lines = [ln for ln in text.splitlines() if ln and "|" in ln]
    if not lines:
        return []
    header = lines[0].split("|")
    idx = {col: header.index(col) for col in (symbol_col, name_col, etf_col, test_col) if col in header}
    if symbol_col not in idx:
        return []
    rows = []
    for ln in lines[1:]:
        if ln.startswith("File Creation Time"):
            continue
        parts = ln.split("|")
        if len(parts) <= idx[symbol_col]:
            continue
        rows.append(
            {
                "symbol": parts[idx[symbol_col]].strip(),
                "name": parts[idx[name_col]].strip() if name_col in idx and len(parts) > idx[name_col] else "",
                "etf": parts[idx[etf_col]].strip() if etf_col in idx and len(parts) > idx[etf_col] else "",
                "test": parts[idx[test_col]].strip() if test_col in idx and len(parts) > idx[test_col] else "",
            }
        )
    return rows


def parse_symbol_directory(nasdaq_text: str, other_text: str) -> list[dict]:
    """Combine the two Nasdaq Trader files into a list of listing rows."""
    rows = _parse_pipe_table(nasdaq_text, "Symbol", "Security Name", "ETF", "Test Issue")
    rows += _parse_pipe_table(other_text, "ACT Symbol", "Security Name", "ETF", "Test Issue")
    return rows


def _http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "personal-site-universe/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (trusted host)
        return resp.read().decode("utf-8", errors="replace")


def fetch_symbol_directory() -> list[dict]:
    """Download + parse the live Nasdaq Trader symbol directory."""
    return parse_symbol_directory(_http_get(NASDAQ_LISTED_URL), _http_get(OTHER_LISTED_URL))


# --- (2) symbol filters -------------------------------------------------------
def filter_common_symbols(rows: list[dict], *, exclude_etf: bool = False) -> list[str]:
    """Keep tradable common stocks (and plain ETFs unless excluded).

    Drops test issues, warrants/units/rights/preferred, and leveraged/inverse
    products. Returns a sorted, de-duplicated list of normalized symbols.
    """
    out: set[str] = set()
    for row in rows:
        if (row.get("test") or "").upper() == "Y":
            continue
        if exclude_etf and (row.get("etf") or "").upper() == "Y":
            continue
        symbol = normalize_ticker(row.get("symbol", ""))
        if not symbol or not re.fullmatch(r"[A-Z][A-Z\-]{0,9}", symbol):
            continue
        if _is_non_common(symbol, row.get("name", "")):
            continue
        out.add(symbol)
    return sorted(out)


# --- (3) liquidity / price ----------------------------------------------------
def rank_by_liquidity(
    dollar_volume: dict[str, float],
    last_price: dict[str, float],
    *,
    min_price: float = DEFAULT_MIN_PRICE,
    min_adv: float = DEFAULT_MIN_ADV,
    cap: int = DEFAULT_CAP,
) -> list[str]:
    """Filter by price + median dollar volume, rank by liquidity, cap to `cap`.

    Pure (takes precomputed maps) so it is unit-testable without the network.
    """
    eligible = [
        t
        for t, adv in dollar_volume.items()
        if adv is not None
        and np.isfinite(adv)
        and adv >= min_adv
        and last_price.get(t, 0.0) >= min_price
    ]
    eligible.sort(key=lambda t: dollar_volume[t], reverse=True)
    return eligible[:cap]


def _fetch_liquidity(
    symbols: list[str], lookback_days: int, chunk: int = 150
) -> tuple[dict[str, float], dict[str, float]]:
    """Trailing median dollar volume + last close per symbol, fetched in chunks.

    Per-chunk failures are skipped so one bad symbol can't sink the whole build.
    """
    start = (pd.Timestamp.today() - pd.Timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    end = pd.Timestamp.today().strftime("%Y-%m-%d")
    dollar_volume: dict[str, float] = {}
    last_price: dict[str, float] = {}
    for i in range(0, len(symbols), chunk):
        group = symbols[i : i + chunk]
        try:
            df = prices.get_ohlcv(group, start, end)
        except Exception as exc:  # noqa: BLE001 — robustness over a few thousand symbols
            print(f"  chunk {i // chunk}: skipped ({exc})")
            continue
        df = df.assign(dv=df["adj_close"] * df["volume"])
        med = df.groupby("ticker")["dv"].median()
        last = df.sort_values("date").groupby("ticker")["close"].last()
        for t in group:
            if t in med.index and np.isfinite(med[t]):
                dollar_volume[t] = float(med[t])
                last_price[t] = float(last.get(t, 0.0))
    return dollar_volume, last_price


def build_universe(
    *,
    min_price: float = DEFAULT_MIN_PRICE,
    min_adv: float = DEFAULT_MIN_ADV,
    cap: int = DEFAULT_CAP,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    exclude_etf: bool = False,
    out_path: Path | None = None,
) -> dict:
    """Build + write the shared universe (the monthly job's entry point)."""
    rows = fetch_symbol_directory()
    commons = filter_common_symbols(rows, exclude_etf=exclude_etf)
    print(f"listings: {len(rows)} rows → {len(commons)} common symbols")
    dollar_volume, last_price = _fetch_liquidity(commons, lookback_days)
    tickers = rank_by_liquidity(
        dollar_volume, last_price, min_price=min_price, min_adv=min_adv, cap=cap
    )
    payload = {
        "as_of": dt.date.today().isoformat(),
        "source": "nasdaqtrader",
        "filters": {
            "min_price": min_price,
            "min_median_dollar_volume": min_adv,
            "cap": cap,
            "exclude_etf": exclude_etf,
        },
        "count": len(tickers),
        "tickers": tickers,
    }
    path = out_path or DEFAULT_UNIVERSE_PATH
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(REPO_ROOT)} — {len(tickers)} tickers")
    return payload


# --- reader (used by the daily updaters) --------------------------------------
def load_universe(path: Path | None = None) -> list[str]:
    """Load the shared universe ticker list. Raises if it hasn't been built."""
    p = path or DEFAULT_UNIVERSE_PATH
    if not p.exists():
        raise FileNotFoundError(
            f"shared universe not found at {p}; run `python -m paper_trading.update_universe` "
            f"(or wait for the monthly universe-refresh workflow)"
        )
    return list(json.loads(p.read_text(encoding="utf-8")).get("tickers", []))


def resolve_universe(spec: dict, path: Path | None = None) -> list[str]:
    """Universe for a strategy: its explicit `universe`, else the shared file.

    A spec with a non-empty `universe` list uses it verbatim (e.g. the open
    momentum demo). A spec that omits it or leaves it empty — the normal case for
    a deployed king — resolves to the shared, self-refreshing universe.
    """
    explicit = spec.get("universe")
    if isinstance(explicit, list) and explicit:
        return [normalize_ticker(t) for t in explicit]
    return load_universe(path)
