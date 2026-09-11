"""Tests for the open-strategy updater entry point."""

from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest

from paper_trading import update
from paper_trading.deployment import deployment_bundle_hash
from paper_trading.tests.test_contracts import _spec


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
