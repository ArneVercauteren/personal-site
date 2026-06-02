"""Vendored Darwin DSL evaluator (scrubbed copy — Tier 2b).

This subpackage is a self-contained, scrubbed copy of Darwin's pure-Python
single-date selection evaluator (`src/backtest/select_on_date.py` and its
helpers). It executes a deployed king's DSL formula tree to produce target
ticker weights, using keyless daily prices supplied by the caller.

It is a COPY, not an import: nothing here reaches into the Darwin source tree,
and no secret (formula/weights of secured kings, `src/config/secrets.py`) lives
here. See docs/concepts/separation-from-darwin.md. Parity with Darwin's own
evaluator is enforced by paper_trading/tests/test_evaluator_parity.py.
"""
