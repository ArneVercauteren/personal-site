"""Shared base indicator/fundamental sets used across evolution modules.

Vendored verbatim from Astralanx `src/evolution/indicator_constants.py`.
"""

from __future__ import annotations

FUND_NAMES = frozenset({"fund_eps", "fund_assets", "fund_net_income", "pe"})

# Indicators that are inherently normalized (dimensionless ratios or percentages).
BASE_SELF_NORMALIZED_INDICATORS = frozenset(
    {
        "roc",
        "rsi",
        "volume_surge",
        "overnight_gap",
        "close_to_range",
        "mkt_corr",
        "mean_reversion",
        "drawdown",
        "skewness",
    }
)

BASE_WINDOWLESS_INDICATORS = frozenset(
    {
        "dollar_volume",
        "overnight_gap",
        "close_to_range",
        "market_volume",
        "fund_eps",
        "fund_assets",
        "fund_net_income",
        "pe",
    }
)

BASE_INDICATORS = frozenset(
    {
        "sma",
        "ema",
        "roc",
        "rsi",
        "atr",
        "hh",
        "ll",
        "market_sma",
        "market_ema",
        "market_roc",
        "market_rsi",
        "market_atr",
        "market_hh",
        "market_ll",
        "dollar_volume",
        "volume_surge",
        "overnight_gap",
        "close_to_range",
        "mean_reversion",
        "drawdown",
        "skewness",
        "amihud_illiquidity",
    }
)
