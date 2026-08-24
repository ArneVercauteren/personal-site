"""Self-refreshing tradable universe — keyless, Astralanx-independent.

The paper sim needs a *current* set of tickers each deployed strategy picks from.
Snapshotting Astralanx's curated universe would inherit Astralanx's data age (a king
deployed off six-month-old data could never hold anything newer), so instead this
builds a fresh universe from public, keyless sources and the same filters Astralanx
uses:

1. **Listings** — the Nasdaq Trader symbol directory (`nasdaqlisted.txt` +
   `otherlisted.txt`): every NYSE / NASDAQ / AMEX symbol, updated each trading
   day, free and keyless, with ETF / test-issue flags. This is "the same
   exchanges", sourced from the exchanges (yfinance has no listing endpoint).
2. **Symbol filters** — drop test issues, warrants / units / rights / preferred,
   and leveraged / inverse products (regexes vendored from Astralanx's
   `src/data/ticker_filtering.py`).
3. **Liquidity / price** — keep names with last close ≥ `min_price` and trailing
   median dollar volume ≥ `min_adv`, ranked by liquidity and capped to `cap` so
   the daily sim's yfinance fetches stay bounded. These are Astralanx's
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
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from . import prices
from .contracts import content_hash

__all__ = [
    "DEFAULT_UNIVERSE_PATH",
    "fetch_symbol_directory",
    "filter_common_symbols",
    "rank_by_liquidity",
    "build_universe",
    "load_universe",
    "resolve_universe",
    "resolve_universe_snapshot_id",
    "load_universe_snapshot",
    "archive_current_universe",
]

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_UNIVERSE_PATH = REPO_ROOT / "public" / "data" / "universe.json"

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

# Astralanx FinancialRealism defaults (src/config/engine.py).
DEFAULT_MIN_PRICE = 10.0
DEFAULT_MIN_ADV = 5_000_000.0
DEFAULT_CAP = 1200
DEFAULT_LOOKBACK_DAYS = 120  # ~63 trading days of history for the median

# Be a polite client to the (free, keyless) price API: batch per request, pause
# between batches, and back off on failure instead of hammering / silently
# dropping. Tunable via update_universe env vars.
DEFAULT_FETCH_CHUNK = 120     # tickers per yfinance batch request
DEFAULT_FETCH_PAUSE = 1.5     # seconds between batches
DEFAULT_FETCH_RETRIES = 3     # attempts to recover missing/rate-limited names per batch
DEFAULT_REQUESTS_PER_SEC = 4  # global cap via a rate-limited session (if available)

# Persistent skip-list of symbols that returned no data (delisted / preferred /
# bad symbols), so we don't re-fetch known-dead names every month. Entries carry
# the date they last failed and are re-checked after SKIP_TTL_DAYS in case a
# symbol relists.
DEFAULT_SKIP_PATH = REPO_ROOT / "public" / "data" / "universe_skip.json"
SKIP_TTL_DAYS = 180

# Safety: never overwrite a good universe with a husk from a rate-limited run.
MIN_RETENTION = 0.6

# --- symbol filters (vendored from Astralanx src/data/ticker_filtering.py) -------
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


def _make_session():
    """A rate-limited requests session so yfinance stays under Yahoo's cap.

    Uses `requests_ratelimiter` if installed (the yfinance-recommended way to
    avoid `YFRateLimitError`). Returns None if it isn't — the fetch then falls
    back to sequential requests + inter-batch pauses, which is gentler but slower.
    """
    try:
        from requests_ratelimiter import LimiterSession

        return LimiterSession(per_second=DEFAULT_REQUESTS_PER_SEC)
    except Exception as exc:  # noqa: BLE001
        print(f"  (no rate-limited session — pip install requests-ratelimiter; {exc})")
        return None


# --- persistent skip-list -----------------------------------------------------
def load_skip(path: Path | None = None) -> dict[str, str]:
    """Load the `{symbol: last_failed_date}` skip-list (empty if none yet)."""
    p = path or DEFAULT_SKIP_PATH
    if not p.exists():
        return {}
    try:
        return dict(json.loads(p.read_text(encoding="utf-8")).get("symbols", {}))
    except (ValueError, OSError):
        return {}


def save_skip(skip: dict[str, str], path: Path | None = None) -> None:
    p = path or DEFAULT_SKIP_PATH
    payload = {"as_of": dt.date.today().isoformat(), "count": len(skip), "symbols": dict(sorted(skip.items()))}
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def active_skips(skip: dict[str, str], today: dt.date | None = None) -> set[str]:
    """Symbols whose last failure is still within SKIP_TTL_DAYS (so still skipped)."""
    today = today or dt.date.today()
    out: set[str] = set()
    for sym, when in skip.items():
        try:
            age = (today - dt.date.fromisoformat(when)).days
        except (TypeError, ValueError):
            age = 0
        if age < SKIP_TTL_DAYS:
            out.add(sym)
    return out


def _prune_skip(skip: dict[str, str], today: dt.date | None = None) -> dict[str, str]:
    """Drop expired entries so relisted symbols get re-checked next run."""
    keep = active_skips(skip, today)
    return {s: w for s, w in skip.items() if s in keep}


def _fetch_one_batch(group, start, end, *, session, pause, max_retries, label):
    """Fetch a batch, retrying the *missing* (often rate-limited) subset.

    yfinance doesn't raise on per-ticker rate-limits — it just returns those
    names empty — so we detect which requested symbols are missing and re-fetch
    only those with back-off. Returns `{ticker: (median_dollar_volume, last_close)}`.
    """
    out: dict[str, tuple[float, float]] = {}
    pending = list(group)
    for attempt in range(max_retries):
        df = None
        try:
            df = prices.get_ohlcv(pending, start, end, session=session, threads=False)
        except Exception as exc:  # noqa: BLE001 — hard failure (network); retry below
            print(f"  batch {label}: request failed ({exc})")
        if df is not None and not df.empty:
            df = df.assign(dv=df["adj_close"] * df["volume"])
            med = df.groupby("ticker")["dv"].median()
            last = df.sort_values("date").groupby("ticker")["close"].last()
            for t in list(pending):
                if t in med.index and np.isfinite(med[t]):
                    out[t] = (float(med[t]), float(last.get(t, 0.0)))
            pending = [t for t in pending if t not in out]
        if not pending or attempt == max_retries - 1:
            break
        backoff = pause * (2 ** attempt)
        print(f"  batch {label}: {len(pending)} missing/limited; retry in {backoff:.1f}s")
        time.sleep(backoff)
    return out


def _fetch_liquidity(
    symbols: list[str],
    lookback_days: int,
    *,
    session=None,
    chunk: int = DEFAULT_FETCH_CHUNK,
    pause: float = DEFAULT_FETCH_PAUSE,
    max_retries: int = DEFAULT_FETCH_RETRIES,
) -> tuple[dict[str, float], dict[str, float], set[str]]:
    """Trailing median dollar volume + last close per symbol, fetched politely.

    Batched and rate-limited (via `session`), sequential within a batch, with a
    `pause` between batches and a back-off retry of any missing/rate-limited
    names. Returns `(dollar_volume, last_price, failed)` where `failed` are the
    symbols that never returned usable data (recorded to the skip-list).
    """
    start = (pd.Timestamp.today() - pd.Timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    end = pd.Timestamp.today().strftime("%Y-%m-%d")
    dollar_volume: dict[str, float] = {}
    last_price: dict[str, float] = {}
    failed: set[str] = set()

    batches = list(range(0, len(symbols), chunk))
    for bi, i in enumerate(batches):
        group = symbols[i : i + chunk]
        got = _fetch_one_batch(
            group, start, end, session=session, pause=pause,
            max_retries=max_retries, label=f"{bi + 1}/{len(batches)}",
        )
        for t, (m, p) in got.items():
            dollar_volume[t] = m
            last_price[t] = p
        failed.update(t for t in group if t not in got)
        if bi < len(batches) - 1:
            time.sleep(pause)
    return dollar_volume, last_price, failed


def build_universe(
    *,
    min_price: float = DEFAULT_MIN_PRICE,
    min_adv: float = DEFAULT_MIN_ADV,
    cap: int = DEFAULT_CAP,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    exclude_etf: bool = False,
    fetch_chunk: int = DEFAULT_FETCH_CHUNK,
    fetch_pause: float = DEFAULT_FETCH_PAUSE,
    out_path: Path | None = None,
    skip_path: Path | None = None,
) -> dict:
    """Build + write the shared universe (the monthly job's entry point).

    Reuses a persistent skip-list so known-dead symbols aren't re-fetched every
    month, fetches through a rate-limited session, and refuses to overwrite a good
    universe with a rate-limited husk (the retention guard).
    """
    path = out_path or DEFAULT_UNIVERSE_PATH
    skip_path = skip_path or DEFAULT_SKIP_PATH
    today = dt.date.today()

    skip = load_skip(skip_path)
    skipped = active_skips(skip, today)

    rows = fetch_symbol_directory()
    commons = filter_common_symbols(rows, exclude_etf=exclude_etf)
    candidates = [s for s in commons if s not in skipped]
    print(f"listings: {len(rows)} rows → {len(commons)} common; "
          f"{len(skipped)} known-dead skipped → {len(candidates)} to fetch")

    session = _make_session()
    dollar_volume, last_price, failed = _fetch_liquidity(
        candidates, lookback_days, session=session, chunk=fetch_chunk, pause=fetch_pause
    )
    tickers = rank_by_liquidity(
        dollar_volume, last_price, min_price=min_price, min_adv=min_adv, cap=cap
    )

    # Retention guard: a sharp drop vs the last good universe means the run was
    # likely rate-limited — fail loudly instead of clobbering the committed file.
    prior = _prior_count(path)
    if prior and len(tickers) < MIN_RETENTION * prior:
        raise RuntimeError(
            f"new universe has {len(tickers)} tickers vs prior {prior} "
            f"(< {MIN_RETENTION:.0%}); likely a rate-limited run — keeping the existing "
            f"universe.json. Re-run, or lower UNIVERSE_FETCH rate, then retry."
        )

    # Remember this run's failures so next month skips them (within TTL).
    for sym in failed:
        skip[sym] = today.isoformat()
    skip = _prune_skip(skip, today)
    save_skip(skip, skip_path)

    payload = {
        "as_of": today.isoformat(),
        "source": "nasdaqtrader",
        "filters": {
            "min_price": min_price,
            "min_median_dollar_volume": min_adv,
            "cap": cap,
            "exclude_etf": exclude_etf,
        },
        "count": len(tickers),
        "skipped": len(skip),
        "tickers": tickers,
    }
    snapshot_id = content_hash(payload)
    payload["snapshot_id"] = snapshot_id
    snapshot_dir = path.parent / "universe_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / f"{today.isoformat()}-{snapshot_id[:16]}.json"
    snapshot_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(REPO_ROOT)} — {len(tickers)} tickers "
          f"({len(failed)} new dead symbols recorded; {len(skip)} skipped total)")
    return payload


def _prior_count(path: Path) -> int:
    """Ticker count in the existing universe.json, or 0 if none/unreadable."""
    if not path.exists():
        return 0
    try:
        return int(json.loads(path.read_text(encoding="utf-8")).get("count", 0))
    except (ValueError, OSError):
        return 0


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


def resolve_universe_snapshot_id(spec: dict, path: Path | None = None) -> str:
    """Stable id of the exact membership supplied to a strategy review."""
    explicit = spec.get("universe")
    if isinstance(explicit, list) and explicit:
        return content_hash(sorted(normalize_ticker(ticker) for ticker in explicit))
    payload = json.loads((path or DEFAULT_UNIVERSE_PATH).read_text(encoding="utf-8"))
    return str(payload.get("snapshot_id") or content_hash({
        key: value for key, value in payload.items() if key != "snapshot_id"
    }))


def load_universe_snapshot(snapshot_id: str, spec: dict | None = None) -> list[str]:
    """Resolve an immutable universe id to the exact historical membership."""
    explicit = (spec or {}).get("universe")
    if isinstance(explicit, list) and explicit:
        members = sorted(normalize_ticker(ticker) for ticker in explicit)
        if content_hash(members) == snapshot_id:
            return members

    candidates = [DEFAULT_UNIVERSE_PATH]
    candidates.extend(sorted((DEFAULT_UNIVERSE_PATH.parent / "universe_snapshots").glob("*.json")))
    for candidate in candidates:
        if not candidate.is_file():
            continue
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        observed = str(payload.get("snapshot_id") or content_hash({
            key: value for key, value in payload.items() if key != "snapshot_id"
        }))
        if observed == snapshot_id:
            return list(payload.get("tickers", []))
    raise ValueError(f"universe snapshot {snapshot_id} is not archived")


def archive_current_universe(path: Path | None = None) -> Path:
    """Materialize the current pointer as its immutable date/hash snapshot."""
    current = path or DEFAULT_UNIVERSE_PATH
    payload = json.loads(current.read_text(encoding="utf-8"))
    snapshot_id = str(payload.get("snapshot_id") or content_hash(payload))
    payload["snapshot_id"] = snapshot_id
    target = current.parent / "universe_snapshots" / (
        f"{payload['as_of']}-{snapshot_id[:16]}.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and json.loads(target.read_text(encoding="utf-8")) != payload:
        raise ValueError(f"universe snapshot collision at {target}")
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target
