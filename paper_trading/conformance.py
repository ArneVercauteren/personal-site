"""Required, Darwin-independent deployment conformance-vector runner."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from . import portfolio, prices
from .contracts import ContractError
from .costs import CostModel, sliced_execution_cost
from .darwin_eval.select_on_date import select_tickers_on_date
from .deployment import DEPLOYMENT_SCHEMA_VERSION, validate_deployment_bundle

ROOT = Path(__file__).resolve().parents[1]
VECTOR_DIR = Path(__file__).resolve().parent / "conformance_vectors"
STRATEGY_DIR = Path(__file__).resolve().parent / "strategies"


def _close(left: float, right: float, label: str, tolerance: float = 1e-10) -> None:
    if not math.isclose(float(left), float(right), rel_tol=tolerance, abs_tol=tolerance):
        raise ContractError(f"conformance mismatch for {label}: {left} != {right}")


def _validate_selection(vector: dict, spec: dict) -> None:
    generator = vector["generator"]
    if generator.get("version") != "synthetic-ohlcv-v1":
        raise ContractError("unsupported conformance price generator")
    tickers = list(generator["tickers"])
    frame = prices._synthetic_ohlcv(tickers, generator["start"], generator["end"])
    result = select_tickers_on_date(
        strat_dict=spec["formula"], target_date=vector["target_session"],
        tickers=tickers, prices_override=frame,
        min_price=float(vector["eligibility"]["min_price"]),
        min_adv=float(vector["eligibility"]["min_adv"]),
        portfolio_size=float(spec["portfolio_size"]), market_series_override=None,
    )
    expected = vector["expected"]
    if result["eligible_count"] != expected["eligible_count"]:
        raise ContractError("conformance eligibility count changed")
    eligible = sorted(result["all_scores"])
    if eligible != expected["eligible"]:
        raise ContractError("conformance eligible membership changed")
    if result["selected"] != expected["selected"]:
        raise ContractError("conformance selection changed")
    for ticker, score in expected["scores"].items():
        _close(result["all_scores"][ticker], score, f"score.{ticker}")
    if set(result["final_weights"]) != set(expected["weights"]):
        raise ContractError("conformance weight membership changed")
    for ticker, weight in expected["weights"].items():
        _close(result["final_weights"][ticker], weight, f"weight.{ticker}")


def _validate_cost(vector: dict, spec: dict) -> None:
    actual = sliced_execution_cost(cfg=CostModel.from_spec(spec["cost_model"]), **vector["inputs"])
    for key, expected in vector["expected"].items():
        if key == "execution_days":
            if actual[key] != expected:
                raise ContractError("conformance execution-day count changed")
        else:
            _close(actual[key], expected, f"cost.{key}")


def _validate_schedule(vector: dict, spec: dict) -> None:
    generator = vector["generator"]
    if generator.get("version") != "observed-business-days-v1":
        raise ContractError("unsupported conformance session generator")
    sessions = pd.bdate_range(generator["start"], generator["end"])
    excluded = {pd.Timestamp(day) for day in generator.get("excluded_sessions", [])}
    sessions = sessions[~sessions.isin(excluded)]
    reviews = portfolio._rebalance_dates(
        sessions, pd.Timestamp(generator["simulation_start"]),
        int(spec["rebalance_cadence_days"]),
        cadence_unit=spec["rebalance_cadence_unit"],
        transition_anchor=spec["rebalance_transition_anchor"],
    )
    review_days = [day.strftime("%Y-%m-%d") for day in reviews]
    if review_days != vector["expected"]["review_sessions"]:
        raise ContractError("conformance review schedule changed")
    review_set = set(reviews)
    fills = [
        sessions[index + 1].strftime("%Y-%m-%d")
        for index, day in enumerate(sessions[:-1]) if day in review_set
    ]
    if fills != vector["expected"]["next_open_fill_sessions"]:
        raise ContractError("conformance next-open fill schedule changed")


def validate_vector(path: Path) -> None:
    vector = json.loads(path.read_text(encoding="utf-8"))
    if vector.get("schema_version") != DEPLOYMENT_SCHEMA_VERSION:
        raise ContractError(f"{path.name}: unsupported conformance schema version")
    strategy_id = vector.get("strategy_id")
    spec_path = STRATEGY_DIR / f"{strategy_id}.json"
    if not spec_path.is_file():
        raise ContractError(f"{path.name}: strategy bundle is missing")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    validate_deployment_bundle(spec)
    if vector.get("bundle_hash") != spec["deployment"]["bundle_hash"]:
        raise ContractError(f"{path.name}: vector belongs to a different deployment bundle")
    _validate_selection(vector["selection"], spec)
    _validate_cost(vector["cost"], spec)
    _validate_schedule(vector["schedule"], spec)


def validate_all() -> int:
    paths = sorted(VECTOR_DIR.glob("*.json"))
    if not paths:
        raise ContractError("required deployment conformance vectors are missing")
    for path in paths:
        validate_vector(path)
    print(f"validated {len(paths)} required deployment conformance vector(s)")
    return len(paths)


if __name__ == "__main__":
    validate_all()
