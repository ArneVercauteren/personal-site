"""Operator dispatch tables for ``evaluate_tree``.

Vendored verbatim from Astralanx `src/backtest/tree_eval.py`. All operators accept
already-evaluated child values; control-flow constructs that need short-circuit
semantics stay in the dispatcher in ``select_on_date``.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np

_NAN = float("nan")


# ---------------------------------------------------------------------------
# Arithmetic operators
# ---------------------------------------------------------------------------


def _op_add(vals: list[float]) -> float:
    return sum(vals)


def _op_subtract(vals: list[float]) -> float:
    return vals[0] - vals[1] if len(vals) >= 2 else _NAN


def _op_multiply(vals: list[float]) -> float:
    r = 1.0
    for v in vals:
        r *= v
    return r


def _op_divide(vals: list[float]) -> float:
    if len(vals) < 2 or vals[1] == 0:
        return _NAN
    return vals[0] / vals[1]


def _op_minimum(vals: list[float]) -> float:
    return min(vals) if vals else _NAN


def _op_maximum(vals: list[float]) -> float:
    return max(vals) if vals else _NAN


def _op_abs_diff(vals: list[float]) -> float:
    return abs(vals[0] - vals[1]) if len(vals) >= 2 else _NAN


def _op_mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else _NAN


def _op_median(vals: list[float]) -> float:
    if not vals:
        return _NAN
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2
    return s[mid]


def _op_gate_pos(vals: list[float]) -> float:
    # NaN-tolerant by design: a NaN comparison falls through to 0.0,
    # matching the original interpreter behavior.
    if len(vals) < 2:
        return _NAN
    return 1.0 if vals[0] > vals[1] else 0.0


def _op_gate_neg(vals: list[float]) -> float:
    if len(vals) < 2:
        return _NAN
    return 1.0 if vals[0] < vals[1] else 0.0


def _op_log_ratio(vals: list[float]) -> float:
    if len(vals) >= 2 and vals[1] != 0:
        ratio = vals[0] / vals[1]
        if ratio > 0:
            return math.log(ratio)
    return _NAN


def _op_soft_clip(vals: list[float]) -> float:
    if len(vals) < 2:
        return _NAN
    x, lim = vals[0], abs(vals[1]) if vals[1] != 0 else 1.0
    return lim * math.tanh(x / lim) if lim != 0 else 0.0


def _op_atan2(vals: list[float]) -> float:
    return math.atan2(vals[0], vals[1]) if len(vals) >= 2 else _NAN


ARITHMETIC_OPS: dict[str, Callable[[list[float]], float]] = {
    "add": _op_add,
    "subtract": _op_subtract,
    "multiply": _op_multiply,
    "divide": _op_divide,
    "minimum": _op_minimum,
    "maximum": _op_maximum,
    "abs_diff": _op_abs_diff,
    "mean": _op_mean,
    "median": _op_median,
    "gate_pos": _op_gate_pos,
    "gate_neg": _op_gate_neg,
    "log_ratio": _op_log_ratio,
    "soft_clip": _op_soft_clip,
    "atan2": _op_atan2,
}

# Operators that handle NaN themselves (rather than propagating).
_ARITH_NAN_TOLERANT = {"gate_pos", "gate_neg"}


def eval_arithmetic(op: str, vals: list[float]) -> float:
    if op not in _ARITH_NAN_TOLERANT and any(math.isnan(v) for v in vals):
        return _NAN
    handler = ARITHMETIC_OPS.get(op)
    return handler(vals) if handler is not None else _NAN


# ---------------------------------------------------------------------------
# Comparison operators
# ---------------------------------------------------------------------------


def _cmp_greater_than(left: float, right: float, _node) -> float:
    return 1.0 if left > right else 0.0


def _cmp_less_than(left: float, right: float, _node) -> float:
    return 1.0 if left < right else 0.0


def _cmp_greater_or_equal(left: float, right: float, _node) -> float:
    return 1.0 if left >= right else 0.0


def _cmp_less_or_equal(left: float, right: float, _node) -> float:
    return 1.0 if left <= right else 0.0


def _cmp_greater_abs(left: float, right: float, _node) -> float:
    return 1.0 if abs(left) > abs(right) else 0.0


def _cmp_less_abs(left: float, right: float, _node) -> float:
    return 1.0 if abs(left) < abs(right) else 0.0


def _cmp_same_sign(left: float, right: float, _node) -> float:
    return 1.0 if (left * right) > 0.0 else 0.0


def _cmp_different_sign(left: float, right: float, _node) -> float:
    return 1.0 if (left * right) < 0.0 else 0.0


def _cmp_is_positive(left: float, _right, _node) -> float:
    return 1.0 if left > 0.0 else 0.0


def _cmp_is_negative(left: float, _right, _node) -> float:
    return 1.0 if left < 0.0 else 0.0


def _cmp_is_nonzero(left: float, _right, node) -> float:
    eps = float((node.get("params") or {}).get("eps", 0.01))
    return 1.0 if abs(left) > eps else 0.0


def _cmp_equal(left: float, right: float, node) -> float:
    tol = float((node.get("params") or {}).get("tol", 0.1))
    return 1.0 if abs(left - right) < tol else 0.0


def _cmp_not_equal(left: float, right: float, node) -> float:
    tol = float((node.get("params") or {}).get("tol", 0.1))
    return 1.0 if abs(left - right) >= tol else 0.0


SIMPLE_COMPARISON_OPS: dict[str, Callable] = {
    "greater_than": _cmp_greater_than,
    "less_than": _cmp_less_than,
    "greater_or_equal": _cmp_greater_or_equal,
    "less_or_equal": _cmp_less_or_equal,
    "greater_abs": _cmp_greater_abs,
    "less_abs": _cmp_less_abs,
    "same_sign": _cmp_same_sign,
    "different_sign": _cmp_different_sign,
    "is_positive": _cmp_is_positive,
    "is_negative": _cmp_is_negative,
    "is_nonzero": _cmp_is_nonzero,
    "equal": _cmp_equal,
    "almost_equal": _cmp_equal,
    "not_equal": _cmp_not_equal,
}


def eval_ternary_comparison(op: str, left: float, right: float, third: float) -> float:
    """Evaluate a 3-operand comparison (between, outside, in_band)."""
    if op == "between":
        return 1.0 if right <= left <= third else 0.0
    if op == "outside":
        if math.isnan(third):
            return 0.0
        return 1.0 if (left < right or left > third) else 0.0
    if op == "in_band":
        if math.isnan(third):
            return 0.0
        return 1.0 if abs(left - right) < third else 0.0
    return 0.0


TERNARY_COMPARISON_OPS = {"between", "outside", "in_band"}


# ---------------------------------------------------------------------------
# Logic operators (with already-evaluated child values)
# ---------------------------------------------------------------------------


def eval_logic(op: str, child_vals: list[float]) -> float:
    child_bools = [np.isfinite(v) and (v != 0.0) for v in child_vals]
    if op == "and":
        return 1.0 if all(child_bools) else 0.0
    if op == "nand":
        return 1.0 if not all(child_bools) else 0.0
    if op == "or":
        return 1.0 if any(child_bools) else 0.0
    if op == "nor":
        return 1.0 if not any(child_bools) else 0.0
    if op == "not":
        return 1.0 if child_vals and not child_bools[0] else 0.0
    if op == "implies":
        if len(child_bools) < 2:
            return 0.0
        return 1.0 if ((not child_bools[0]) or child_bools[1]) else 0.0
    if op == "if_bool":
        if len(child_vals) < 3:
            return _NAN
        return child_vals[1] if child_bools[0] else child_vals[2]
    return 0.0
