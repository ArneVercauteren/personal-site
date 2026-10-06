"""Tests for the open-strategy updater entry point."""

from __future__ import annotations

from datetime import datetime, timezone
import json

import pandas as pd
import pytest

from paper_trading import benchmark, portfolio, prices, update
from paper_trading.deployment import deployment_bundle_hash
from paper_trading.ledger import LedgerStore, make_event
from paper_trading.tests.test_contracts import _spec
from paper_trading.tests.test_corrections import _minor_checkpoint
from paper_trading.tests.test_prices_cache import _bars


def _write_spec(directory, strategy_id: str) -> None:
    payload = _spec()
    payload["id"] = strategy_id
    payload["name"] = strategy_id
    payload["deployment"]["strategy_id"] = strategy_id
    payload["deployment"]["display_name"] = strategy_id
    payload["deployment"]["bundle_hash"] = deployment_bundle_hash(payload)
    (directory / f"{strategy_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_load_strategy_specs_can_filter_to_one_open_strategy(tmp_path, monkeypatch):
    _write_spec(tmp_path, "gen0194")
    _write_spec(tmp_path, "open_momentum_v1")
    monkeypatch.setattr(update, "STRATEGY_DIR", tmp_path)

    specs = update.load_strategy_specs({"gen0194"})

    assert [s["id"] for s in specs] == ["gen0194"]


def test_load_strategy_specs_rejects_unknown_filter_id(tmp_path, monkeypatch):
    _write_spec(tmp_path, "gen0194")
    monkeypatch.setattr(update, "STRATEGY_DIR", tmp_path)

    with pytest.raises(ValueError, match="unknown open strategy"):
        update.load_strategy_specs({"missing"})


def test_split_strategy_ids_accepts_cli_and_env(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING_STRATEGIES", "env_a, env_b")
    monkeypatch.delenv("PAPER_TRADING_STRATEGY", raising=False)

    assert update._split_strategy_ids(["cli_a,cli_b", "cli_c"]) == {
        "cli_a",
        "cli_b",
        "cli_c",
        "env_a",
        "env_b",
    }


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        # 16:59 and 17:00 in New York during daylight-saving time.
        (datetime(2026, 9, 10, 20, 59, tzinfo=timezone.utc), "2026-09-09"),
        (datetime(2026, 9, 10, 21, 0, tzinfo=timezone.utc), "2026-09-10"),
        # A Monday run before finalization falls back past the weekend.
        (datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc), "2026-09-11"),
        # The same rule follows standard time without a hard-coded UTC hour.
        (datetime(2026, 12, 10, 21, 59, tzinfo=timezone.utc), "2026-12-09"),
        (datetime(2026, 12, 10, 22, 0, tzinfo=timezone.utc), "2026-12-10"),
    ],
)
def test_latest_safe_price_date_waits_for_finalized_session(now, expected):
    assert update._latest_safe_price_date(now) == expected


def test_latest_safe_price_date_requires_timezone():
    with pytest.raises(ValueError, match="timezone-aware"):
        update._latest_safe_price_date(datetime(2026, 9, 10, 18, 0))


def _live_spec():
    return {
        "id": "s", "name": "Test", "visibility": "open", "deployed_on": "2026-01-02",
        "portfolio_size": 1_000_000, "base_currency": "USD", "blurb": "Test",
        "rebalance_cadence_days": 2, "rebalance_cadence_unit": "trading_days",
        "cost_model": {"commission_bps": 0.0, "slippage_bps": 0.0},
        "universe": ["A", "B"],
        "signal": {"type": "cross_sectional_momentum", "lookback_days": 1, "top_n": 1},
    }


def _live_checkpoint(spec, remaining=1):
    return {**_minor_checkpoint(), **portfolio._checkpoint_hashes(spec),
            "sessions_until_review": remaining, "pending_target": {},
            "pending_cost_fraction": 0.0, "last_review_session": "2026-01-02"}


def _prices_at_boundary():
    bars = _bars(["A", "B"])
    for ticker, value in {"A": 10.0, "B": 20.0}.items():
        for field in ("open", "high", "low", "close", "adj_close"):
            bars.loc[bars["ticker"] == ticker, field] = value
    return bars


def test_review_sessions_count_observed_market_bars_and_catch_up():
    spec = _live_spec()
    index = pd.DatetimeIndex(["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-08"])
    assert update._upcoming_review_sessions(spec, _live_checkpoint(spec), index) == (
        "2026-01-05", "2026-01-08",
    )
    assert update._upcoming_review_sessions(spec, _live_checkpoint(spec, 5), index) == ()


@pytest.mark.parametrize("recover", [True, False])
def test_fetch_retries_stale_review_symbols_and_blocks_unresolved(monkeypatch, recover):
    spec = _live_spec()
    checkpoint = _live_checkpoint(spec)
    full = _prices_at_boundary()
    partial = full[~((full["ticker"] == "B") & (full["date"] == pd.Timestamp("2026-01-05")))]
    calls = []

    def fetch(tickers, start, end, **kwargs):
        calls.append((tickers, kwargs))
        return (full if recover else partial)[lambda frame: frame["ticker"].isin(tickers)] if kwargs.get("required_dates") else partial

    monkeypatch.setattr(update.LEDGER_STORE, "load_checkpoint", lambda strategy_id: checkpoint)
    monkeypatch.setattr(prices, "get_ohlcv_chunked", fetch)
    monkeypatch.setattr(prices, "make_limiter_session", lambda: None)
    if recover:
        result = update._fetch_all_prices([spec], "2026-01-05")
        assert not prices.missing_price_tickers(result, ["A", "B"], ("2026-01-05",))
    else:
        with pytest.raises(portfolio.BoundaryPriceUnavailable, match="2026-01-05.*B"):
            update._fetch_all_prices([spec], "2026-01-05")
    assert calls[1][0] == ["B"]
    assert calls[1][1]["required_dates"] == ("2026-01-05",)


def test_non_review_day_can_continue_with_unheld_universe_gap(monkeypatch):
    spec = _live_spec()
    checkpoint = _live_checkpoint(spec, 5)
    partial = _prices_at_boundary().query("ticker == 'A'")
    monkeypatch.setattr(update.LEDGER_STORE, "load_checkpoint", lambda strategy_id: checkpoint)
    monkeypatch.setattr(prices, "get_ohlcv_chunked", lambda *args, **kwargs: partial)
    monkeypatch.setattr(prices, "make_limiter_session", lambda: None)
    assert set(update._fetch_all_prices([spec], "2026-01-05")["ticker"]) == {"A"}


def test_simulator_rejects_forward_filled_candidate_on_catch_up_review():
    spec = _live_spec()
    # B has old bars and therefore remains in the wide frame via forward fill.
    partial = _prices_at_boundary().query("ticker == 'A' or date < '2026-01-05'")
    opens, closes = prices.long_to_wide(partial)
    raw, dv = prices.wide_raw_and_dollar_volume(partial)
    checkpoint = _live_checkpoint(spec)
    with pytest.raises(portfolio.BoundaryPriceUnavailable, match="2026-01-05.*B"):
        portfolio.simulate_incremental(
            spec, checkpoint, [{"d": "2026-01-02", "v": checkpoint["equity"]}],
            opens, closes, prices_long=partial, raw_closes=raw, dollar_volume=dv,
            active_universe=["A", "B"],
        )


def test_updater_runs_minor_correction_through_publication_and_second_run_is_idempotent(tmp_path, monkeypatch):
    spec = _live_spec()
    checkpoint = _live_checkpoint(spec, 5)
    store = LedgerStore(tmp_path)
    store.commit("s", [make_event("s", "session_marked", "2026-01-02", {
        "equity": checkpoint["equity"], "cash": checkpoint["cash"], "shares": checkpoint["shares"],
    })], checkpoint)
    data = tmp_path / "public/data"
    data.mkdir(parents=True)
    curve = [{"d": "2026-01-02", "v": checkpoint["equity"]}]
    (data / "portfolio.json").write_text(json.dumps({
        "as_of": "2026-01-02", "base_currency": "USD",
        "strategies": [{"id": "s", "equity_curve": curve}],
    }))
    revised = _prices_at_boundary()
    for field in ("open", "high", "low", "close", "adj_close"):
        revised.loc[(revised["ticker"] == "A") & (revised["date"] == pd.Timestamp("2026-01-02")), field] = 10.005
    monkeypatch.setattr(update, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(update, "DATA_DIR", data)
    monkeypatch.setattr(update, "LEDGER_STORE", store)
    monkeypatch.setattr(update, "load_strategy_specs", lambda strategy_ids: [spec])
    monkeypatch.setattr(update, "_latest_safe_price_date", lambda: "2026-01-05")
    monkeypatch.setattr(update, "_fetch_all_prices", lambda specs, end: revised)
    monkeypatch.setattr(benchmark, "build_live_benchmark_snapshot", lambda **kwargs:
        benchmark.build_benchmark_snapshot_from_rows([("2026-01-02", 100.0), ("2026-01-05", 101.0)]))
    assert update.run() == "2026-01-05"
    published = json.loads((data / "portfolio.json").read_text())
    assert published["strategies"][0]["equity_curve"][0] == curve[0]
    assert (data / "manifest.json").exists()
    accepted = store.load_checkpoint("s")
    assert "automatic_revision_usage" not in accepted  # reset on the next mark
    assert accepted["shares"] == checkpoint["shares"]
    events = store.read_events("s")
    assert any(event["payload"].get("acceptance") == "automatic_minor_price_revision" for event in events)
    assert update.run() == "2026-01-05"
    assert store.read_events("s") == events
