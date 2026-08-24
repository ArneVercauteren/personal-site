"""Shared fixtures for the paper_trading test suite."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from paper_trading import prices

# Default location of the Astralanx repo for parity tests; override with DARWIN_REPO.
_DARWIN_DEFAULT = r"C:\Users\arnev\Projects\Darwin"


@pytest.fixture
def universe() -> list[str]:
    # Synthetic ticker names (not real symbols) so Astralanx's segment map never
    # matches them — keeps both evaluators on global (unsegmented) rank.
    return [f"T{i:02d}" for i in range(12)]


@pytest.fixture
def long_prices(universe):
    """Deterministic long-format OHLCV covering a multi-year window."""
    return prices._synthetic_ohlcv(universe, "2022-01-01", "2025-06-02")


def darwin_select_fn():
    """Return Astralanx's own `select_tickers_on_date`, or None if unavailable.

    Parity tests skip only when the optional checkout is absent. A checkout that
    exists but cannot import is a broken local gate and must raise its real error.
    """
    repo = os.environ.get("DARWIN_REPO", _DARWIN_DEFAULT)
    if not Path(repo).exists():
        return None
    if repo not in sys.path:
        sys.path.insert(0, repo)
    from src.backtest.select_on_date import select_tickers_on_date

    return select_tickers_on_date
