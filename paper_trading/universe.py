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
from dataclasses import dataclass
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
    "ReviewUniverse",
    "snapshot_for_session",
    "load_delistings",
    "load_symbol_changes",
    "review_universe",
    "review_members_between",
]

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_UNIVERSE_PATH = REPO_ROOT / "public" / "data" / "universe.json"
DEFAULT_SNAPSHOT_DIR = DEFAULT_UNIVERSE_PATH.parent / "universe_snapshots"
# Reviewed last trading sessions for members that stopped trading (acquired,
# delisted). A provider "possibly delisted" warning never creates an entry.
DEFAULT_DELISTINGS_PATH = REPO_ROOT / "paper_trading" / "delistings.json"

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
MIN_PRIOR_PRICE_COVERAGE = 0.9

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
    """The shared yfinance session policy from `prices.make_limiter_session`.

    Modern yfinance needs its own curl_cffi session: a plain `requests` session
    (which `LimiterSession` is) gets `YFRateLimitError` on every request, which
    stalled every monthly refresh from July to October 2026. That helper returns None for
    those versions; the fetch then relies on sequential batches + pauses.
    """
    return prices.make_limiter_session(DEFAULT_REQUESTS_PER_SEC)


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
    candidates = _candidates(exclude_etf, skip_path, today)

    session = _make_session()
    dollar_volume, last_price, failed = _fetch_liquidity(
        candidates, lookback_days, session=session, chunk=fetch_chunk, pause=fetch_pause
    )
    return _publish_universe(
        candidates, dollar_volume, last_price, failed, today=today,
        min_price=min_price, min_adv=min_adv, cap=cap, exclude_etf=exclude_etf,
        path=path, skip_path=skip_path,
    )


def _candidates(exclude_etf: bool, skip_path: Path, today: dt.date) -> list[str]:
    skipped = active_skips(load_skip(skip_path), today)
    rows = fetch_symbol_directory()
    commons = filter_common_symbols(rows, exclude_etf=exclude_etf)
    candidates = [symbol for symbol in commons if symbol not in skipped]
    print(f"listings: {len(rows)} rows → {len(commons)} common; "
          f"{len(skipped)} known-dead skipped → {len(candidates)} to fetch")
    return candidates


def _publish_universe(
    candidates: list[str], dollar_volume: dict[str, float],
    last_price: dict[str, float], failed: set[str], *, today: dt.date,
    min_price: float, min_adv: float, cap: int, exclude_etf: bool,
    path: Path, skip_path: Path,
) -> dict:
    if cap < 1:
        raise ValueError("universe cap must be positive")
    # Compare the *eligible* pool before the intentional cap. The June snapshot
    # has 3,472 names, so comparing a 1,200-name cap to 60% of that snapshot
    # made every future refresh impossible even with perfect price data.
    eligible = rank_by_liquidity(
        dollar_volume, last_price, min_price=min_price, min_adv=min_adv,
        cap=max(len(dollar_volume), 1),
    )
    prior_payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    prior_tickers = set(prior_payload.get("tickers", []))
    prior_candidates = prior_tickers & set(candidates)
    covered = prior_candidates & set(dollar_volume)
    if prior_candidates and len(covered) < MIN_PRIOR_PRICE_COVERAGE * len(prior_candidates):
        raise RuntimeError(
            f"price source returned only {len(covered)}/{len(prior_candidates)} "
            "still-listed prior universe members; keeping the existing universe"
        )
    prior = int(prior_payload.get("count", 0))
    if not eligible or (prior and len(eligible) < MIN_RETENTION * min(prior, len(candidates))):
        raise RuntimeError(
            f"new universe has only {len(eligible)} eligible names before the cap "
            f"(prior {prior}); keeping the existing universe"
        )
    tickers = eligible[:cap]

    skip = load_skip(skip_path)
    for symbol in failed:
        skip[symbol] = today.isoformat()
    skip = _prune_skip(skip, today)
    save_skip(skip, skip_path)
    payload = {
        "as_of": today.isoformat(), "source": "nasdaqtrader",
        "filters": {
            "min_price": min_price, "min_median_dollar_volume": min_adv,
            "cap": cap, "exclude_etf": exclude_etf,
        },
        "count": len(tickers), "skipped": len(skip), "tickers": tickers,
    }
    snapshot_id = content_hash(payload)
    payload["snapshot_id"] = snapshot_id
    snapshot_dir = path.parent / "universe_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / f"{today.isoformat()}-{snapshot_id[:16]}.json"
    snapshot_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path} — {len(tickers)} tickers "
          f"({len(failed)} missing symbols recorded; {len(skip)} skipped total)")
    return payload


def build_universe_shard(
    shard_index: int, shard_count: int, out_dir: Path, *,
    min_price: float = DEFAULT_MIN_PRICE, min_adv: float = DEFAULT_MIN_ADV,
    cap: int = DEFAULT_CAP, lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    exclude_etf: bool = False, fetch_chunk: int = DEFAULT_FETCH_CHUNK,
    fetch_pause: float = DEFAULT_FETCH_PAUSE,
    skip_path: Path | None = None,
) -> Path:
    """Fetch one bounded slice of the monthly symbol directory for CI."""
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ValueError("invalid universe shard index/count")
    today = dt.date.today()
    candidates = _candidates(exclude_etf, skip_path or DEFAULT_SKIP_PATH, today)
    selected = candidates[shard_index::shard_count]
    dollar_volume, last_price, failed = _fetch_liquidity(
        selected, lookback_days, session=_make_session(),
        chunk=fetch_chunk, pause=fetch_pause,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"shard-{shard_index:02d}.json"
    path.write_text(json.dumps({
        "as_of": today.isoformat(), "shard_index": shard_index,
        "shard_count": shard_count, "candidate_snapshot_id": content_hash(candidates),
        "settings": {
            "min_price": min_price, "min_adv": min_adv, "cap": cap,
            "exclude_etf": exclude_etf, "lookback_days": lookback_days,
        },
        "candidates": selected, "dollar_volume": dollar_volume,
        "last_price": last_price, "failed": sorted(failed),
    }, sort_keys=True), encoding="utf-8")
    print(f"wrote {path} — {len(dollar_volume)}/{len(selected)} symbols returned prices")
    return path


def publish_universe_shards(
    shard_dir: Path, *, out_path: Path | None = None,
    skip_path: Path | None = None,
) -> dict:
    """Validate all shard artifacts, then publish one complete universe."""
    paths = sorted(shard_dir.glob("shard-*.json"))
    if not paths:
        raise ValueError("no universe shard artifacts found")
    shards = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    first = shards[0]
    count = int(first["shard_count"])
    if len(shards) != count or {s["shard_index"] for s in shards} != set(range(count)):
        raise ValueError("universe shard artifacts are incomplete")
    if any(s["as_of"] != first["as_of"] or
           s["candidate_snapshot_id"] != first["candidate_snapshot_id"] or
           s["settings"] != first["settings"] or
           s["shard_count"] != count for s in shards):
        raise ValueError("universe shard artifacts disagree on source or settings")
    candidates = sorted(symbol for shard in shards for symbol in shard["candidates"])
    if len(candidates) != len(set(candidates)) or content_hash(candidates) != first["candidate_snapshot_id"]:
        raise ValueError("universe shard candidates are incomplete or duplicated")
    dollar_volume: dict[str, float] = {}
    last_price: dict[str, float] = {}
    failed: set[str] = set()
    for shard in shards:
        expected = set(shard["candidates"])
        got = set(shard["dollar_volume"])
        if got - expected or set(shard["last_price"]) != got or set(shard["failed"]) != expected - got:
            raise ValueError("universe shard prices do not match its candidates")
        dollar_volume.update(shard["dollar_volume"])
        last_price.update(shard["last_price"])
        failed.update(shard["failed"])
    settings = first["settings"]
    return _publish_universe(
        candidates, dollar_volume, last_price, failed,
        today=dt.date.fromisoformat(first["as_of"]),
        min_price=float(settings["min_price"]), min_adv=float(settings["min_adv"]),
        cap=int(settings["cap"]), exclude_etf=bool(settings["exclude_etf"]),
        path=out_path or DEFAULT_UNIVERSE_PATH,
        skip_path=skip_path or DEFAULT_SKIP_PATH,
    )


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


# --- point-in-time review membership ------------------------------------------
@dataclass(frozen=True)
class ReviewUniverse:
    """The membership a review session may see, and the names removed from it."""

    snapshot_id: str
    members: tuple[str, ...]
    excluded: tuple[str, ...]
    renamed: tuple[tuple[str, str], ...] = ()


def _archived_snapshots(snapshot_dir: Path | None = None) -> list[tuple[str, str, list[str]]]:
    """`(as_of, snapshot_id, tickers)` for every archived shared snapshot."""
    directory = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    out = []
    for candidate in sorted(directory.glob("*.json")):
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        snapshot_id = str(payload.get("snapshot_id") or content_hash({
            key: value for key, value in payload.items() if key != "snapshot_id"
        }))
        out.append((str(payload["as_of"]), snapshot_id, list(payload.get("tickers", []))))
    return out


def snapshot_for_session(
    spec: dict, session: str, snapshot_dir: Path | None = None,
) -> tuple[str, list[str]]:
    """The newest shared snapshot built strictly before `session`.

    A refresh fetches prices through its own `as_of` day, so it may only inform
    reviews on later sessions. Using the moving `universe.json` instead would
    hand a catch-up review a membership ranked on bars after that review.
    """
    explicit = spec.get("universe")
    if isinstance(explicit, list) and explicit:
        members = [normalize_ticker(t) for t in explicit]
        return content_hash(sorted(members)), members
    usable = [item for item in _archived_snapshots(snapshot_dir) if item[0] < session]
    if not usable:
        raise ValueError(f"no archived universe snapshot predates review session {session}")
    latest = max(as_of for as_of, _, _ in usable)
    chosen = [item for item in usable if item[0] == latest]
    if len({snapshot_id for _, snapshot_id, _ in chosen}) != 1:
        raise ValueError(f"several different universe snapshots are dated {latest}")
    _, snapshot_id, members = chosen[0]
    return snapshot_id, members


def _load_listing_records(path: Path | None) -> dict:
    p = path or DEFAULT_DELISTINGS_PATH
    if not p.exists():
        return {}
    payload = json.loads(p.read_text(encoding="utf-8"))
    for section in ("delistings", "symbol_changes"):
        for ticker, record in payload.get(section, {}).items():
            if not record.get("source"):
                raise ValueError(f"{section} record for {ticker} has no source")
    return payload


def load_delistings(path: Path | None = None) -> dict[str, str]:
    """Reviewed `{ticker: last_trading_session}` records (see delistings.json)."""
    out: dict[str, str] = {}
    for ticker, record in _load_listing_records(path).get("delistings", {}).items():
        last = str(record["last_trading_session"])
        dt.date.fromisoformat(last)
        out[normalize_ticker(ticker)] = last
    return out


def load_symbol_changes(path: Path | None = None) -> dict[str, tuple[str, str]]:
    """Reviewed `{old: (new, first_session_under_new)}` ticker changes.

    The same security kept trading under a new symbol, so it is not delisted:
    a later review sees it under the new symbol, whose history the provider
    carries back across the change.
    """
    out: dict[str, tuple[str, str]] = {}
    for ticker, record in _load_listing_records(path).get("symbol_changes", {}).items():
        effective = str(record["effective_session"])
        dt.date.fromisoformat(effective)
        out[normalize_ticker(ticker)] = (normalize_ticker(record["new_symbol"]), effective)
    return out


def review_universe(
    spec: dict, session: str, *,
    snapshot_dir: Path | None = None, delistings_path: Path | None = None,
) -> ReviewUniverse:
    """Point-in-time candidates for a review on `session`.

    Members whose reviewed last trading session is strictly before `session`
    had stopped trading by then, so the review cannot see them. A member that
    still traded on `session` stays and must have a real bar, whatever a price
    provider now says about it.
    """
    snapshot_id, members = snapshot_for_session(spec, session, snapshot_dir)
    delisted = load_delistings(delistings_path)
    changes = load_symbol_changes(delistings_path)
    excluded = {ticker for ticker in members if delisted.get(ticker, "9999-12-31") < session}
    renamed = {
        ticker: changes[ticker][0]
        for ticker in members
        if ticker in changes and changes[ticker][1] <= session
    }
    kept = [renamed.get(ticker, ticker) for ticker in members if ticker not in excluded]
    if len(set(kept)) != len(kept):
        raise ValueError(f"symbol changes collide with other members on {session}")
    return ReviewUniverse(
        snapshot_id=snapshot_id,
        members=tuple(kept),
        excluded=tuple(sorted(excluded)),
        renamed=tuple(sorted(renamed.items())),
    )


def review_members_between(
    spec: dict, after: str, through: str, snapshot_dir: Path | None = None,
) -> set[str]:
    """Every snapshot member a review in (`after`, `through`] could use."""
    explicit = spec.get("universe")
    if isinstance(explicit, list) and explicit:
        members = set(snapshot_for_session(spec, through, snapshot_dir)[1])
    else:
        snapshots = _archived_snapshots(snapshot_dir)
        # The snapshot in force on the first unseen session, plus any built later.
        first = [item for item in snapshots if item[0] <= after]
        floor = max((as_of for as_of, _, _ in first), default="")
        members = {
            ticker
            for as_of, _, tickers in snapshots
            if floor <= as_of < through
            for ticker in tickers
        }
    changes = load_symbol_changes()
    return members | {changes[t][0] for t in members if t in changes}


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
