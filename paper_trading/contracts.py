"""Versioned contracts and deterministic provenance helpers.

The JSON Schema documents in ``schemas/`` are the portable contract.  These
small runtime guards deliberately cover the safety-critical invariants without
requiring a second schema library in the updater process.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date
from pathlib import Path
from typing import Any

CONTRACT_VERSION = 1
ENGINE_VERSION = "paper-runtime-v1"
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ContractError(ValueError):
    """Raised before invalid data may enter state or publication."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_date(value: Any, label: str) -> str:
    if not isinstance(value, str) or not ISO_DATE.fullmatch(value):
        raise ContractError(f"{label} must be an ISO date")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError(f"{label} is not a valid date") from exc
    return value


def _finite(value: Any, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise ContractError(f"{label} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{label} must be numeric") from exc
    if not math.isfinite(number) or (positive and number <= 0):
        qualifier = "positive and finite" if positive else "finite"
        raise ContractError(f"{label} must be {qualifier}")
    return number


def validate_strategy_spec(spec: dict) -> dict:
    required = {
        "id", "name", "visibility", "deployed_on", "portfolio_size",
        "base_currency", "rebalance_cadence_days", "cost_model",
    }
    missing = sorted(required - set(spec))
    if missing:
        raise ContractError(f"strategy spec missing: {', '.join(missing)}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", str(spec["id"])):
        raise ContractError("strategy id is not portable")
    if spec["visibility"] != "open":
        raise ContractError("only open strategies belong in the public updater")
    _require_date(spec["deployed_on"], "deployed_on")
    _finite(spec["portfolio_size"], "portfolio_size", positive=True)
    cadence = int(spec["rebalance_cadence_days"])
    if cadence <= 0:
        raise ContractError("rebalance cadence must be positive")
    unit = spec.get("rebalance_cadence_unit", "calendar_days")
    if unit not in {"calendar_days", "trading_days"}:
        raise ContractError("invalid rebalance cadence unit")
    if spec.get("rebalance_transition_anchor") is not None:
        if unit != "trading_days":
            raise ContractError("a cadence transition anchor requires trading_days")
        _require_date(spec["rebalance_transition_anchor"], "rebalance_transition_anchor")
    if spec.get("next_review_date") is not None:
        _require_date(spec["next_review_date"], "next_review_date")
    costs = spec["cost_model"]
    if not isinstance(costs, dict):
        raise ContractError("cost_model must be an object")
    for key in ("commission_bps", "slippage_bps"):
        _finite(costs.get(key), f"cost_model.{key}")
    if "formula" not in spec and "signal" not in spec:
        raise ContractError("strategy requires formula or signal")
    return spec


def validate_equity_curve(points: Any, label: str = "equity_curve") -> list[dict]:
    if not isinstance(points, list) or not points:
        raise ContractError(f"{label} must be a non-empty array")
    previous = ""
    for index, point in enumerate(points):
        if not isinstance(point, dict):
            raise ContractError(f"{label}[{index}] must be an object")
        day = _require_date(point.get("d"), f"{label}[{index}].d")
        if day <= previous:
            raise ContractError(f"{label} dates must be strictly increasing")
        _finite(point.get("v"), f"{label}[{index}].v", positive=True)
        previous = day
    return points


def validate_public_strategy(strategy: dict) -> dict:
    for key in ("id", "name", "visibility", "equity_curve", "stats"):
        if key not in strategy:
            raise ContractError(f"public strategy missing {key}")
    validate_equity_curve(strategy["equity_curve"])
    visibility = strategy["visibility"]
    if visibility == "open":
        if not isinstance(strategy.get("positions"), list):
            raise ContractError("open strategy requires positions")
    elif visibility == "secured":
        if "positions" in strategy or "formula" in strategy:
            raise ContractError("secured strategy leaked positions or formula")
        if not isinstance(strategy.get("exposure"), list):
            raise ContractError("secured strategy requires exposure")
    else:
        raise ContractError("unknown strategy visibility")
    for key in ("cagr", "sharpe", "max_dd"):
        _finite(strategy["stats"].get(key), f"stats.{key}")
    return strategy


def validate_public_files(files: dict[str, dict]) -> None:
    portfolio = files["portfolio.json"]
    _require_date(portfolio.get("as_of"), "portfolio.as_of")
    strategies = portfolio.get("strategies")
    if not isinstance(strategies, list):
        raise ContractError("portfolio.strategies must be an array")
    ids: set[str] = set()
    for strategy in strategies:
        validate_public_strategy(strategy)
        if strategy["id"] in ids:
            raise ContractError(f"duplicate strategy id {strategy['id']}")
        ids.add(strategy["id"])

    trades = files["trades.json"]
    _require_date(trades.get("as_of"), "trades.as_of")
    for trade in trades.get("trades", []):
        _require_date(trade.get("d"), "trade.d")
        if trade.get("side") not in {"buy", "sell"}:
            raise ContractError("invalid trade side")
        _finite(trade.get("weight"), "trade.weight")

    benchmark = files["benchmark.json"]
    _require_date(benchmark.get("as_of"), "benchmark.as_of")
    for item in benchmark.get("benchmarks", []):
        validate_equity_curve(item.get("equity_curve"), "benchmark.equity_curve")
