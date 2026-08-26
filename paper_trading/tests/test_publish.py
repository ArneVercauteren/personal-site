from __future__ import annotations

import json

from paper_trading.publish import _chart_curve, downsample, publish_snapshot


def _write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_downsample_preserves_endpoints_and_extreme():
    points = [{"d": f"2026-01-{i:02d}", "v": float(i)} for i in range(1, 21)]
    points[10]["v"] = -100.0
    sampled = downsample(points, 8)
    assert sampled[0] == points[0]
    assert sampled[-1] == points[-1]
    assert points[10] in sampled
    assert len(sampled) <= 10


def test_chart_curve_keeps_every_live_session():
    curve = [{"d": f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", "v": float(i)} for i in range(600)]
    live_since = curve[-40]["d"]
    sampled = _chart_curve({"equity_curve": curve, "live_since": live_since}, limit=100)
    live = [point for point in sampled if point["d"] >= live_since]
    assert live == curve[-40:]
    assert len(sampled) <= 100
    assert sampled[0] == curve[0]


def test_chart_curve_without_live_since_downsamples_whole_curve():
    curve = [{"d": f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", "v": float(i)} for i in range(600)]
    sampled = _chart_curve({"equity_curve": curve}, limit=100)
    assert sampled == downsample(curve, 100)


def test_publish_snapshot_writes_manifest_last_contract(tmp_path):
    curve = [{"d": "2026-01-02", "v": 100.0}, {"d": "2026-01-05", "v": 101.0}]
    _write(tmp_path / "portfolio.json", {
        "as_of": "2026-01-05", "base_currency": "USD", "strategies": [{
            "id": "s", "name": "S", "visibility": "open", "equity_curve": curve,
            "stats": {"cagr": 0.1, "sharpe": 1.0, "max_dd": 0.0},
            "stats_live": {"cagr": 0.1, "sharpe": 1.0, "max_dd": 0.0},
            "live_since": "2026-01-02", "positions": [{"ticker": "A", "weight": 0.8}],
        }],
    })
    _write(tmp_path / "strategies.json", {"as_of": "2026-01-05", "strategies": [{
        "id": "s", "name": "S", "visibility": "open", "portfolio_size": 100.0,
        "base_currency": "USD", "rebalance_cadence_days": 42,
        "deployed_on": "2026-01-02", "cost_model": {"commission_bps": 1, "slippage_bps": 5},
        "blurb": "test",
    }]})
    _write(tmp_path / "trades.json", {"as_of": "2026-01-05", "trades": []})
    _write(tmp_path / "benchmark.json", {"as_of": "2026-01-05", "base_currency": "USD", "benchmarks": [{
        "id": "sp500", "name": "S&P 500", "equity_curve": curve,
    }]})

    manifest = publish_snapshot(tmp_path)
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "snapshots" / manifest["snapshot_id"] / "index.json").exists()
    assert "strategies/s/analytics.json" in manifest["files"]
