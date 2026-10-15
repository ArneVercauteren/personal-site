"""Tests for the self-refreshing universe (pure functions, no network)."""

from __future__ import annotations

import json

import pytest

from paper_trading import universe
from paper_trading.contracts import content_hash

NASDAQ_TXT = """Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N
MSFT|Microsoft Corporation - Common Stock|Q|N|N|100|N|N
ZTEST|Nasdaq Test Issue|Q|Y|N|100|N|N
TQQQ|ProShares UltraPro QQQ|Q|N|N|100|Y|N
ABCDW|Some SPAC - Warrant|Q|N|N|100|N|N
GRABU|Some SPAC - Unit|Q|N|N|100|N|N
U|Unity Software Inc. - Common Stock|Q|N|N|100|N|N
File Creation Time: 0102202612:00|||||||
"""

OTHER_TXT = """ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
BRK.A|Berkshire Hathaway Inc.|N|BRK.A|N|1|N|BRK.A
JPM-P-C|JPMorgan Preferred|N|JPM$C|N|100|N|
SPY|SPDR S&P 500 ETF Trust|P|SPY|Y|100|N|SPY
File Creation Time: 0102202612:00|||||||
"""


def test_parse_symbol_directory():
    rows = universe.parse_symbol_directory(NASDAQ_TXT, OTHER_TXT)
    symbols = {r["symbol"] for r in rows}
    assert "AAPL" in symbols and "BRK.A" in symbols
    # The "File Creation Time" trailer line is skipped.
    assert not any(r["symbol"].startswith("File Creation") for r in rows)


def test_filter_common_symbols_keeps_common_drops_junk():
    rows = universe.parse_symbol_directory(NASDAQ_TXT, OTHER_TXT)
    out = universe.filter_common_symbols(rows, exclude_etf=False)
    assert "AAPL" in out and "MSFT" in out
    assert "U" in out                  # short legit ticker kept
    assert "BRK-A" in out              # dotted share class normalized
    assert "ZTEST" not in out          # test issue
    assert "TQQQ" not in out           # leveraged (by name)
    assert "ABCDW" not in out          # warrant (5+ char W tail)
    assert "GRABU" not in out          # unit (5+ char U tail)
    assert "JPM-P-C" not in out        # preferred
    assert "SPY" in out                # plain ETF kept when not excluded


def test_filter_common_symbols_exclude_etf():
    rows = universe.parse_symbol_directory(NASDAQ_TXT, OTHER_TXT)
    out = universe.filter_common_symbols(rows, exclude_etf=True)
    assert "SPY" not in out
    assert "AAPL" in out


def test_rank_by_liquidity_filters_and_caps():
    dv = {"AAA": 9e6, "BBB": 8e6, "CCC": 4e6, "DDD": 20e6}
    px = {"AAA": 50.0, "BBB": 5.0, "CCC": 100.0, "DDD": 200.0}
    # min_adv=5e6 drops CCC; min_price=10 drops BBB; ranked by dollar volume.
    out = universe.rank_by_liquidity(dv, px, min_price=10.0, min_adv=5e6, cap=10)
    assert out == ["DDD", "AAA"]
    # cap truncates after ranking.
    assert universe.rank_by_liquidity(dv, px, min_price=10.0, min_adv=5e6, cap=1) == ["DDD"]


def test_resolve_universe_prefers_explicit():
    spec = {"universe": ["aapl", "msft"]}
    assert universe.resolve_universe(spec) == ["AAPL", "MSFT"]


def test_resolve_universe_falls_back_to_shared(tmp_path):
    shared = tmp_path / "universe.json"
    shared.write_text(json.dumps({"tickers": ["NVDA", "AMD"]}), encoding="utf-8")
    assert universe.resolve_universe({}, path=shared) == ["NVDA", "AMD"]
    assert universe.resolve_universe({"universe": []}, path=shared) == ["NVDA", "AMD"]


def test_resolve_universe_missing_shared_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="shared universe not found"):
        universe.resolve_universe({}, path=tmp_path / "nope.json")


def test_load_universe_snapshot_resolves_archived_membership(tmp_path, monkeypatch):
    current = tmp_path / "universe.json"
    archive = tmp_path / "universe_snapshots"
    archive.mkdir()
    historical = {"as_of": "2026-01-02", "tickers": ["AAPL", "MSFT"]}
    snapshot_id = content_hash(historical)
    historical["snapshot_id"] = snapshot_id
    (archive / f"2026-01-02-{snapshot_id[:16]}.json").write_text(
        json.dumps(historical), encoding="utf-8",
    )
    current.write_text(json.dumps({"snapshot_id": "new", "tickers": ["NVDA"]}), encoding="utf-8")
    monkeypatch.setattr(universe, "DEFAULT_UNIVERSE_PATH", current)

    assert universe.load_universe_snapshot(snapshot_id) == ["AAPL", "MSFT"]
    with pytest.raises(ValueError, match="is not archived"):
        universe.load_universe_snapshot("missing")


# --- skip-list (known-dead symbols, with TTL) -----------------------------

def test_active_skips_respects_ttl():
    import datetime as dt
    today = dt.date(2026, 6, 3)
    skip = {
        "DEAD": (today - dt.timedelta(days=10)).isoformat(),    # recent → still skipped
        "OLD": (today - dt.timedelta(days=200)).isoformat(),    # > 180d → expired
    }
    active = universe.active_skips(skip, today)
    assert active == {"DEAD"}


def test_skip_roundtrip_and_prune(tmp_path):
    import datetime as dt
    today = dt.date(2026, 6, 3)
    skip = {
        "DEAD": (today - dt.timedelta(days=10)).isoformat(),
        "OLD": (today - dt.timedelta(days=300)).isoformat(),
    }
    p = tmp_path / "universe_skip.json"
    universe.save_skip(skip, p)
    loaded = universe.load_skip(p)
    assert loaded == skip
    pruned = universe._prune_skip(loaded, today)
    assert "OLD" not in pruned and "DEAD" in pruned


def test_skipped_symbols_excluded_from_candidates():
    # filter_common_symbols output minus active skips is what gets fetched.
    rows = universe.parse_symbol_directory(NASDAQ_TXT, OTHER_TXT)
    commons = universe.filter_common_symbols(rows)
    import datetime as dt
    skip = {"AAPL": dt.date.today().isoformat()}
    skipped = universe.active_skips(skip)
    candidates = [s for s in commons if s not in skipped]
    assert "AAPL" not in candidates and "MSFT" in candidates


def test_sharded_refresh_allows_intentional_cap_below_prior_retention(tmp_path, monkeypatch):
    current = tmp_path / "universe.json"
    current.write_text(json.dumps({
        "count": 4, "tickers": ["AAA", "BBB", "CCC", "DDD"],
    }), encoding="utf-8")
    candidates = ["AAA", "BBB", "CCC", "DDD"]
    monkeypatch.setattr(universe, "_candidates", lambda *args: candidates)
    monkeypatch.setattr(universe, "_make_session", lambda: None)

    def fetch(symbols, *args, **kwargs):
        return ({s: 10_000_000.0 + candidates.index(s) for s in symbols},
                {s: 20.0 for s in symbols}, set())

    monkeypatch.setattr(universe, "_fetch_liquidity", fetch)
    shards = tmp_path / "shards"
    for index in range(2):
        universe.build_universe_shard(index, 2, shards, cap=2)
    payload = universe.publish_universe_shards(
        shards, out_path=current, skip_path=tmp_path / "skip.json",
    )
    assert payload["count"] == 2
    assert payload["tickers"] == ["DDD", "CCC"]
    assert json.loads(current.read_text())["snapshot_id"] == payload["snapshot_id"]


def test_sharded_refresh_rejects_incomplete_or_provider_degraded_results(tmp_path, monkeypatch):
    current = tmp_path / "universe.json"
    original = json.dumps({"count": 4, "tickers": ["AAA", "BBB", "CCC", "DDD"]})
    current.write_text(original, encoding="utf-8")
    candidates = ["AAA", "BBB", "CCC", "DDD"]
    monkeypatch.setattr(universe, "_candidates", lambda *args: candidates)
    monkeypatch.setattr(universe, "_make_session", lambda: None)
    monkeypatch.setattr(universe, "_fetch_liquidity", lambda symbols, *args, **kwargs: (
        {s: 10_000_000.0 for s in symbols if s == "AAA"},
        {s: 20.0 for s in symbols if s == "AAA"},
        set(symbols) - {"AAA"},
    ))
    shards = tmp_path / "shards"
    universe.build_universe_shard(0, 2, shards)
    with pytest.raises(ValueError, match="incomplete"):
        universe.publish_universe_shards(shards, out_path=current)
    universe.build_universe_shard(1, 2, shards)
    with pytest.raises(RuntimeError, match="price source returned only"):
        universe.publish_universe_shards(shards, out_path=current)
    assert current.read_text() == original


def test_make_session_defers_to_yfinance_on_modern_versions(monkeypatch):
    # A plain requests session is rate-limited on every call by yfinance >= 0.2.66.
    monkeypatch.setattr(universe.prices, "use_synthetic", lambda: False)
    monkeypatch.setattr(
        universe.prices, "_package_version_at_least",
        lambda package, minimum: package == "yfinance",
    )
    assert universe._make_session() is None
