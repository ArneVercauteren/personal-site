"""Tests for the self-refreshing universe (pure functions, no network)."""

from __future__ import annotations

import json

import pytest

from paper_trading import universe

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
