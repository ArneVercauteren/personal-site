"""Bit-exact parity: vendored evaluator vs Darwin's own select_tickers_on_date.

Skipped when the Darwin repo isn't importable (CI in the public repo), so it is
a local correctness gate. Strategies here use NO portfolio-state features, which
isolates evaluator-copy fidelity (state injection is tested separately).

Set DARWIN_REPO to point at the Darwin checkout to enable.
"""

from __future__ import annotations

import math

import pytest

from paper_trading.darwin_eval.select_on_date import select_tickers_on_date as ours
from paper_trading.tests.conftest import darwin_select_fn

TARGET_DATE = "2024-06-03"


@pytest.fixture(scope="module")
def darwin_select():
    fn = darwin_select_fn()
    if fn is None:
        pytest.skip("Darwin repo not available (set DARWIN_REPO to enable parity tests)")
    return fn


def _indicator(name, window=None):
    node = {"kind": "indicator", "name": name, "params": {}}
    if window is not None:
        node["params"]["window"] = window
    return node


def _transform(name, child, **params):
    return {"kind": "transform", "name": name, "child": child, "params": params}


STRATEGIES = {
    "top_n_roc": {"mode": "top_n", "top_n": 4, **_indicator("roc", 40)},
    "top_n_zscore_roc": {
        "mode": "top_n",
        "top_n": 3,
        **_transform("z_score", _indicator("roc", 20), window=60),
    },
    "top_n_rank_sma": {
        "mode": "top_n",
        "top_n": 5,
        **_transform("rank", _indicator("sma", 30), window=60),
    },
    "boolean_roc_positive": {
        "mode": "boolean",
        "kind": "comparison",
        "name": "greater_than",
        "left": _indicator("roc", 20),
        "right": {"kind": "number", "value": 0.0},
    },
    "filter_then_rank": {
        "mode": "filter_then_rank",
        "top_n": 4,
        "filter_root": {
            "kind": "comparison",
            "name": "greater_than",
            "left": _indicator("roc", 40),
            "right": {"kind": "number", "value": 0.0},
        },
        "score_root": _indicator("sma", 20),
    },
    "arithmetic_combo": {
        "mode": "top_n",
        "top_n": 3,
        "kind": "arithmetic",
        "name": "subtract",
        "children": [_indicator("roc", 20), _indicator("rsi", 14)],
    },
}

COMMON = dict(min_price=0.0, min_adv=0.0, portfolio_size=1_000_000.0, market_series_override=None)


def _assert_same(a: dict, b: dict):
    assert a["selected"] == b["selected"]
    assert set(a["final_weights"]) == set(b["final_weights"])
    for t in a["final_weights"]:
        assert a["final_weights"][t] == pytest.approx(b["final_weights"][t], abs=1e-9, rel=1e-9)
    assert set(a["scores"]) == set(b["scores"])
    for t in a["scores"]:
        av, bv = a["scores"][t], b["scores"][t]
        if isinstance(av, float) and math.isnan(av):
            assert math.isnan(bv)
        else:
            assert av == pytest.approx(bv, abs=1e-9, rel=1e-9)


@pytest.mark.parametrize("name", list(STRATEGIES))
def test_parity_no_priors(darwin_select, long_prices, universe, name):
    strat = STRATEGIES[name]
    res_ours = ours(
        strat_dict=strat, target_date=TARGET_DATE, tickers=universe,
        prices_override=long_prices, **COMMON,
    )
    res_dar = darwin_select(
        strat_dict=strat, target_date=TARGET_DATE, tickers=universe,
        prices_override=long_prices, **COMMON,
    )
    _assert_same(res_ours, res_dar)


def test_parity_with_prior_weights_and_exit(darwin_select, long_prices, universe):
    """Carry/exit logic with prior holdings must also match exactly."""
    strat = {
        "mode": "top_n",
        "top_n": 4,
        **_indicator("roc", 40),
        "exit_root": {
            "kind": "comparison",
            "name": "less_than",
            "left": _indicator("roc", 20),
            "right": {"kind": "number", "value": -5.0},
        },
    }
    prior = {universe[0]: 0.3, universe[1]: 0.3, universe[2]: 0.4}
    kwargs = dict(
        strat_dict=strat, target_date=TARGET_DATE, tickers=universe,
        prices_override=long_prices, apply_exit_root_to=list(prior),
        prior_weights=prior, **COMMON,
    )
    _assert_same(ours(**kwargs), darwin_select(**kwargs))
