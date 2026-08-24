"""Build a content-addressed, validated public snapshot and publish its manifest last."""

from __future__ import annotations

import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .contracts import CONTRACT_VERSION, canonical_json, content_hash, file_hash, validate_public_files
from .publish_sanitize import assert_no_internal_paths

MAX_CHART_POINTS = 900


def downsample(points: list[dict], limit: int = MAX_CHART_POINTS) -> list[dict]:
    """Deterministic min/max bucket sampling that preserves endpoints and extremes."""
    if len(points) <= limit:
        return points
    bucket_count = max(1, (limit - 2) // 2)
    interior = points[1:-1]
    bucket_size = len(interior) / bucket_count
    chosen: list[dict] = [points[0]]
    for bucket in range(bucket_count):
        start = int(math.floor(bucket * bucket_size))
        end = int(math.floor((bucket + 1) * bucket_size))
        values = interior[start:max(start + 1, end)]
        low = min(values, key=lambda point: point["v"])
        high = max(values, key=lambda point: point["v"])
        chosen.extend(sorted({low["d"]: low, high["d"]: high}.values(), key=lambda point: point["d"]))
    chosen.append(points[-1])
    return list({point["d"]: point for point in chosen}.values())


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _write_json(path: Path, payload: dict, *, pretty: bool = False) -> None:
    serialized = (
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if pretty
        else canonical_json(payload) + "\n"
    )
    _atomic_write(path, serialized)


def _live_points(strategy: dict) -> list[dict]:
    live_since = strategy.get("live_since")
    if not live_since:
        return strategy["equity_curve"]
    return [point for point in strategy["equity_curve"] if point["d"] >= live_since]


def _summary(strategy: dict, meta: dict | None, trades: list[dict]) -> dict:
    live = _live_points(strategy)
    start_value = float(live[0]["v"]) if live else 0.0
    end_value = float(live[-1]["v"]) if live else 0.0
    peak = max((float(point["v"]) for point in live), default=0.0)
    invested = None
    if strategy["visibility"] == "open":
        invested = sum(float(position["weight"]) for position in strategy.get("positions", []))
    out = {
        "id": strategy["id"],
        "name": strategy["name"],
        "visibility": strategy["visibility"],
        "live_since": strategy.get("live_since"),
        "live_curve": downsample(live, 260),
        "live_observations": len(live),
        "live_total_return": end_value / start_value - 1.0 if start_value > 0 else 0.0,
        "current_drawdown": end_value / peak - 1.0 if peak > 0 else 0.0,
        "stats_live": strategy.get("stats_live"),
        "stats_backtest": strategy.get("stats_backtest"),
        "invested_weight": invested,
        "recent_trades": trades[-20:],
    }
    if meta:
        for key in (
            "blurb", "portfolio_size", "base_currency", "rebalance_cadence_days",
            "rebalance_cadence_unit", "deployed_on", "cost_model", "next_review_date",
            "last_review_date", "last_fill_date", "sessions_until_review",
            "thesis", "expected_behavior", "risks", "failure_modes",
        ):
            if meta.get(key) is not None:
                out[key] = meta[key]
    return out


def build_snapshot_payloads(data_dir: Path) -> tuple[str, dict[str, dict]]:
    legacy = {
        name: json.loads((data_dir / name).read_text(encoding="utf-8"))
        for name in ("portfolio.json", "strategies.json", "trades.json", "benchmark.json")
    }
    validate_public_files(legacy)
    assert_no_internal_paths(legacy)
    portfolio = legacy["portfolio.json"]
    meta_by_id = {item["id"]: item for item in legacy["strategies.json"].get("strategies", [])}
    trades_by_id: dict[str, list[dict]] = {}
    for trade in legacy["trades.json"].get("trades", []):
        trades_by_id.setdefault(trade["strategy_id"], []).append(trade)

    payloads: dict[str, dict] = {}
    index_strategies = []
    for strategy in portfolio["strategies"]:
        strategy_id = strategy["id"]
        meta = meta_by_id.get(strategy_id)
        trades = sorted(trades_by_id.get(strategy_id, []), key=lambda item: item["d"])
        summary = _summary(strategy, meta, trades)
        checkpoint_path = data_dir.parents[1] / "paper_state" / f"{strategy_id}.json"
        provenance = None
        if checkpoint_path.exists():
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            provenance = {
                key: checkpoint[key]
                for key in (
                    "last_processed_session", "deployment_hash", "formula_hash",
                    "universe_snapshot_id", "price_snapshot_id", "cost_model_hash",
                    "engine_version",
                )
            }
            summary["provenance"] = provenance
        index_strategies.append(summary)

        detail = {key: value for key, value in strategy.items() if key != "equity_curve"}
        detail["equity_curve"] = downsample(strategy["equity_curve"])
        detail["meta"] = {
            key: value for key, value in (meta or {}).items() if key != "performance"
        }
        payloads[f"strategies/{strategy_id}/summary.json"] = {
            "schema_version": CONTRACT_VERSION,
            "as_of": portfolio["as_of"],
            "strategy": detail,
        }
        payloads[f"strategies/{strategy_id}/live.json"] = {
            "schema_version": CONTRACT_VERSION,
            "as_of": portfolio["as_of"],
            "strategy_id": strategy_id,
            "equity_curve": _live_points(strategy),
            "positions": strategy.get("positions"),
            "exposure": strategy.get("exposure"),
            "trades": trades,
        }
        payloads[f"strategies/{strategy_id}/analytics.json"] = {
            "schema_version": CONTRACT_VERSION,
            "as_of": portfolio["as_of"],
            "strategy_id": strategy_id,
            "performance": (meta or {}).get("performance"),
            "active_share": (meta or {}).get("active_share"),
            "capacity": (meta or {}).get("capacity"),
        }
        ledger_path = data_dir.parents[1] / "paper_ledger" / f"{strategy_id}.jsonl"
        ledger_events = []
        if ledger_path.exists():
            ledger_events = [
                json.loads(line)
                for line in ledger_path.read_text(encoding="utf-8").splitlines()
                if line
            ]
        payloads[f"strategies/{strategy_id}/rebalances.json"] = {
            "schema_version": CONTRACT_VERSION,
            "as_of": portfolio["as_of"],
            "strategy_id": strategy_id,
            "events": [
                event for event in ledger_events
                if event.get("event_type") in {
                    "rebalance_reviewed", "targets_computed", "fills_applied",
                    "costs_charged", "correction_proposed", "correction_accepted",
                }
            ],
        }
        payloads[f"strategies/{strategy_id}/provenance.json"] = {
            "schema_version": CONTRACT_VERSION,
            "as_of": portfolio["as_of"],
            "strategy_id": strategy_id,
            "provenance": provenance,
        }
        payloads[f"strategies/{strategy_id}/research-full.json"] = {
            "schema_version": CONTRACT_VERSION,
            "as_of": portfolio["as_of"],
            "strategy_id": strategy_id,
            "equity_curve": strategy["equity_curve"],
            "stats": strategy["stats"],
            "stats_backtest": strategy.get("stats_backtest"),
            "performance": (meta or {}).get("performance"),
        }

    index = {
        "schema_version": CONTRACT_VERSION,
        "as_of": portfolio["as_of"],
        "base_currency": portfolio["base_currency"],
        "strategies": index_strategies,
    }
    payloads["index.json"] = index
    for benchmark in legacy["benchmark.json"].get("benchmarks", []):
        payloads[f"benchmarks/{benchmark['id']}.json"] = {
            "schema_version": CONTRACT_VERSION,
            "as_of": legacy["benchmark.json"]["as_of"],
            **benchmark,
        }
    snapshot_id = content_hash(payloads)
    return snapshot_id, payloads


def publish_snapshot(data_dir: Path) -> dict:
    snapshot_id, payloads = build_snapshot_payloads(data_dir)
    snapshot_root = data_dir / "snapshots" / snapshot_id
    for relative, payload in payloads.items():
        _write_json(snapshot_root / relative, payload)

    files = {
        relative: {
            "sha256": file_hash(snapshot_root / relative),
            "bytes": (snapshot_root / relative).stat().st_size,
        }
        for relative in sorted(payloads)
    }
    as_of = payloads["index.json"]["as_of"]
    generated_at = datetime.combine(
        datetime.fromisoformat(as_of).date(), datetime.min.time(), tzinfo=timezone.utc
    ).isoformat().replace("+00:00", "Z")
    manifest = {
        "schema_version": CONTRACT_VERSION,
        "snapshot_id": snapshot_id,
        "as_of": as_of,
        "generated_at": generated_at,
        "files": files,
    }
    assert_no_internal_paths(manifest)
    _write_json(data_dir / "manifest.json", manifest, pretty=True)
    return manifest


def main() -> None:
    data_dir = Path(__file__).resolve().parents[1] / "public" / "data"
    manifest = publish_snapshot(data_dir)
    print(f"published {manifest['snapshot_id']} as of {manifest['as_of']}")


if __name__ == "__main__":
    main()
