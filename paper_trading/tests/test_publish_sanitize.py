"""Tests for the open-strategy publish sanitizer (Tier 3 → Tier 1 boundary).

These pin the no-internal-paths invariant: the public, CDN-served JSON must
never embed an absolute filesystem path (OS username + internal Darwin layout).
See docs/concepts/separation-from-darwin.md and paper_trading/publish_sanitize.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from paper_trading.publish_sanitize import (
    SECTOR_MAP_LABEL,
    InternalPathLeakError,
    assert_no_internal_paths,
    looks_like_internal_path,
    project_public_performance,
    scrub_internal_paths,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "public" / "data"
STRATEGY_DIR = Path(__file__).resolve().parents[1] / "strategies"
MAX_STRATEGIES_JSON_BYTES = 4 * 1024 * 1024


@pytest.mark.parametrize(
    "value",
    [
        "C:\\Users\\arnev\\Projects\\Darwin\\data\\reference\\mappings\\sec_sector_map.csv",
        "C:/Users/arnev/Projects/Darwin/x.csv",
        "/home/runner/work/Darwin/map.csv",
        "/Users/arnev/Projects/Darwin/map.csv",
        "\\\\fileserver\\share\\map.csv",
    ],
)
def test_looks_like_internal_path_flags_absolute_paths(value):
    assert looks_like_internal_path(value)


@pytest.mark.parametrize(
    "value",
    ["SEC SIC-derived", "ok", "Information Technology", "2008-11-20", ""],
)
def test_looks_like_internal_path_ignores_plain_strings(value):
    assert not looks_like_internal_path(value)


def test_scrub_relabels_sector_map_source():
    block = {
        "sector_neutrality": {
            "status": "ok",
            "sector_map_source": "C:\\Users\\arnev\\Projects\\Darwin\\map.csv",
        }
    }
    cleaned = scrub_internal_paths(block)
    assert cleaned["sector_neutrality"]["sector_map_source"] == SECTOR_MAP_LABEL
    # original is untouched (deep copy)
    assert "C:\\" in block["sector_neutrality"]["sector_map_source"]


def test_scrub_redacts_other_paths_in_nested_structures():
    block = {
        "runs": [
            {"artifact": "/home/runner/Darwin/out.json", "value": 1.0},
            {"note": "no path here"},
        ]
    }
    cleaned = scrub_internal_paths(block)
    assert cleaned["runs"][0]["artifact"] == "[redacted internal path]"
    assert cleaned["runs"][0]["value"] == 1.0
    assert cleaned["runs"][1]["note"] == "no path here"


def test_scrub_output_passes_the_guard():
    block = {"sector_map_source": "C:\\Users\\x\\map.csv", "list": ["/Users/x/a"]}
    assert_no_internal_paths(scrub_internal_paths(block))


def test_assert_no_internal_paths_raises_on_leak():
    with pytest.raises(InternalPathLeakError, match="sector_map_source"):
        assert_no_internal_paths({"sector_map_source": "C:\\Users\\x\\map.csv"})


def test_project_public_performance_is_an_explicit_allowlist():
    payload = {
        "training": {
            "start": "2020-01-01",
            "end": "2021-01-01",
            "stats": {"cagr": 0.1, "sharpe": 1.0, "max_dd": -0.2},
            "equity_curve": [{"d": "2020-01-02", "v": 100.0}],
            "advanced_stats": {"duplicate": True},
            "annual_vs_bench": {"duplicate": True},
            "open_diagnostics": {
                "annual_returns": {"2020": 0.1},
                "rolling_3y_sharpe_series": [{"date": "2020-01-02", "sharpe": 1.0}],
                "picks_records": [{"date": "2020-01-02", "tickers": ["A"]}],
                "artifacts": {"raw.csv": [{"ticker": "A"}]},
                "holdings": [{"ticker": "A", "weight": 1.0}],
                "sector_neutrality": {
                    "sector_map_source": "C:\\Users\\x\\private.csv",
                },
            },
        }
    }

    public = project_public_performance(payload)
    run = public["training"]
    diagnostics = run["open_diagnostics"]

    assert "advanced_stats" not in run
    assert "annual_vs_bench" not in run
    assert "artifacts" not in diagnostics
    assert "holdings" not in diagnostics
    assert diagnostics["annual_returns"] == {"2020": 0.1}
    assert diagnostics["picks_records"][0]["tickers"] == ["A"]
    assert diagnostics["sector_neutrality"]["sector_map_source"] == SECTOR_MAP_LABEL


def test_project_public_performance_rejects_wrong_shapes():
    with pytest.raises(TypeError, match="performance must be an object"):
        project_public_performance([])
    with pytest.raises(TypeError, match="performance.training"):
        project_public_performance({"training": []})


@pytest.mark.parametrize(
    "name",
    [p.name for p in sorted(DATA_DIR.glob("*.json"))] if DATA_DIR.exists() else [],
)
def test_committed_public_json_has_no_internal_paths(name):
    """No JSON published under public/data may carry an absolute path."""
    payload = json.loads((DATA_DIR / name).read_text(encoding="utf-8"))
    assert_no_internal_paths(payload)


@pytest.mark.parametrize(
    "path",
    sorted(STRATEGY_DIR.glob("*.json")),
    ids=lambda path: path.name,
)
def test_committed_open_strategy_sources_have_no_internal_paths(path):
    """The source spec is public too; scrub before it enters this repository."""
    assert_no_internal_paths(json.loads(path.read_text(encoding="utf-8")))


def test_committed_public_performance_matches_the_allowlist():
    payload = json.loads((DATA_DIR / "strategies.json").read_text(encoding="utf-8"))
    for strategy in payload.get("strategies", []):
        performance = strategy.get("performance")
        if performance is not None:
            assert performance == project_public_performance(performance)


def test_strategy_metadata_stays_within_the_migration_size_budget():
    """Catch accidental republication of multi-megabyte raw diagnostics."""
    size = (DATA_DIR / "strategies.json").stat().st_size
    assert size <= MAX_STRATEGIES_JSON_BYTES
