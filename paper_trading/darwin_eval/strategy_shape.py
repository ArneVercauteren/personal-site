"""Structural measurements for scrubbed Astralanx strategy JSON.

These helpers intentionally do not evaluate a formula. They only walk the same
AST links the evaluator understands, so complexity gates can count every real
DSL node without depending on price data.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyShape:
    """Formula complexity summary.

    `node_count` counts only DSL AST nodes, i.e. dicts carrying a `kind`. The
    top-level selection wrapper (`mode`, `top_n`, cadence metadata, etc.) is not
    a node unless it also carries `kind`, which top-N score roots usually do.
    `max_depth` is the longest root-to-leaf path across score/filter/exit/nested
    roots, with a leaf depth of 1.
    """

    node_count: int
    max_depth: int


def measure_formula_node(node: dict | None) -> StrategyShape:
    """Measure one FormulaNode subtree."""
    if not isinstance(node, dict) or "kind" not in node:
        return StrategyShape(0, 0)

    children = list(_formula_children(node))
    child_shapes = [measure_formula_node(child) for child in children]
    node_count = 1 + sum(shape.node_count for shape in child_shapes)
    max_child_depth = max((shape.max_depth for shape in child_shapes), default=0)
    return StrategyShape(node_count=node_count, max_depth=1 + max_child_depth)


def measure_strategy_formula(strategy: dict | None, *, include_exit_root: bool = True) -> StrategyShape:
    """Measure all FormulaNode roots attached to a strategy payload.

    Supports the common root-as-score shape (`{"mode": "top_n", "kind": ...}`),
    split filter/score roots, dynamic top-N / position sizing roots, optional
    exit roots, and nested strategy-switch cases.
    """
    if not isinstance(strategy, dict):
        return StrategyShape(0, 0)

    roots: list[dict] = []
    if "kind" in strategy:
        roots.append(strategy)
    for key in ("filter_root", "score_root", "dynamic_top_n_formula", "position_size_root"):
        sub = strategy.get(key)
        if isinstance(sub, dict):
            roots.append(sub)
    if include_exit_root and isinstance(strategy.get("exit_root"), dict):
        roots.append(strategy["exit_root"])

    shapes = [measure_formula_node(root) for root in roots]

    for case in strategy.get("cases", []):
        if not isinstance(case, dict):
            continue
        if isinstance(case.get("condition"), dict):
            shapes.append(measure_formula_node(case["condition"]))
        for sub_key in ("strategy", "else"):
            sub = case.get(sub_key)
            if isinstance(sub, dict):
                shapes.append(measure_strategy_formula(sub, include_exit_root=include_exit_root))

    return StrategyShape(
        node_count=sum(shape.node_count for shape in shapes),
        max_depth=max((shape.max_depth for shape in shapes), default=0),
    )


def _formula_children(node: dict) -> Iterable[dict]:
    for key in ("child", "left", "right", "third"):
        child = node.get(key)
        if isinstance(child, dict):
            yield child

    for key in ("children", "clauses"):
        for child in node.get(key) or []:
            if isinstance(child, dict):
                yield child

    for case in node.get("cases") or []:
        if not isinstance(case, dict):
            continue
        for key in ("condition", "result", "else"):
            child = case.get(key)
            if isinstance(child, dict):
                yield child
