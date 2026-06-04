from __future__ import annotations

from paper_trading.darwin_eval.strategy_shape import (
    StrategyShape,
    measure_formula_node,
    measure_strategy_formula,
)


def _indicator(name: str = "roc", window: int = 20) -> dict:
    return {"kind": "indicator", "name": name, "params": {"window": window}}


def _number(value: float = 0.0) -> dict:
    return {"kind": "number", "value": value}


def test_measure_formula_node_counts_every_ast_link_type() -> None:
    formula = {
        "kind": "conditional",
        "cases": [
            {
                "condition": {
                    "kind": "logic",
                    "name": "and",
                    "clauses": [
                        {
                            "kind": "comparison",
                            "name": "between",
                            "left": _indicator("roc", 40),
                            "right": _number(-5.0),
                            "third": _number(5.0),
                        },
                        {
                            "kind": "transform",
                            "name": "rank",
                            "params": {"window": 60},
                            "child": _indicator("sma", 30),
                        },
                    ],
                },
                "result": {
                    "kind": "arithmetic",
                    "name": "add",
                    "children": [_indicator("rsi", 14), _number(1.0)],
                },
            },
            {"else": _number(-1.0)},
        ],
    }

    assert measure_formula_node(formula) == StrategyShape(node_count=12, max_depth=4)


def test_measure_strategy_formula_counts_roots_and_nested_strategy_cases() -> None:
    strategy = {
        "mode": "strategy_switch",
        "cases": [
            {
                "condition": {
                    "kind": "comparison",
                    "name": "greater_than",
                    "left": _indicator("roc", 20),
                    "right": _number(0.0),
                },
                "strategy": {
                    "mode": "filter_then_rank",
                    "filter_root": {
                        "kind": "comparison",
                        "name": "greater_than",
                        "left": _indicator("dollar_volume", 20),
                        "right": _number(5_000_000.0),
                    },
                    "score_root": {
                        "kind": "transform",
                        "name": "z_score",
                        "params": {"window": 60},
                        "child": _indicator("sma", 30),
                    },
                    "exit_root": {
                        "kind": "logic",
                        "name": "not",
                        "children": [_indicator("invested_fraction", 1)],
                    },
                },
            },
            {
                "else": {
                    "mode": "top_n",
                    "kind": "arithmetic",
                    "name": "subtract",
                    "children": [_indicator("roc", 40), _number(0.0)],
                    "dynamic_top_n_formula": _indicator("current_holdings_count", 1),
                    "position_size_root": _number(1.0),
                }
            },
        ],
    }

    assert measure_strategy_formula(strategy) == StrategyShape(node_count=15, max_depth=2)
    assert measure_strategy_formula(strategy, include_exit_root=False) == StrategyShape(
        node_count=13,
        max_depth=2,
    )


def test_measure_strategy_formula_does_not_count_selection_metadata_as_nodes() -> None:
    assert measure_strategy_formula({"mode": "top_n", "top_n": 8}) == StrategyShape(
        node_count=0,
        max_depth=0,
    )
