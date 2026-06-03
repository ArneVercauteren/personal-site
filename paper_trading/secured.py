"""Secured-strategy sanitization — the Tier 2a boundary, in the shared engine.

The simulator (`portfolio.simulate`) produces full ticker-level `positions` for
every strategy. For **secured** strategies those weights are secret and must
never leave the private updater repo. This module turns a sim result into the
*sanitized* secured entry the public site is allowed to show: equity curve +
stats + **aggregate sector exposure only**, with no `positions` and no formula.

It lives in the public engine on purpose. The aggregation/sanitization logic is
not secret — only the formulas and weights are — and the data contract requires
the sanitizer to stay in lockstep with `lib/data.ts` (the secured entry shape).
Keeping it here means it is unit-tested in the open and version-locked to the
contract; the private repo's `daily.yml` just imports and calls it. See
`docs/concepts/data-contract.md`, `docs/concepts/open-vs-secured-strategies.md`,
and `docs/subsystems/secured-updater.md`.

Also holds the per-strategy cadence helpers Tier 2a uses to decide which kings
are due for a rebalance on a given day (see `docs/subsystems/secured-updater.md`,
"Per-strategy cadence").
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

__all__ = [
    "SecuredLeakError",
    "load_sector_map",
    "aggregate_exposure",
    "build_secured_entry",
    "assert_sanitized",
    "is_rebalance_due",
    "advance_next_rebalance",
]

CASH_GROUP = "Cash"
# Bucket for tickers we have no sector for. The exposure donut is an
# **approximation** — the public site says so — so an unknown stock falls here
# rather than failing the whole update. See docs/subsystems/secured-updater.md.
OTHER_GROUP = "Other"

# Bundled ticker → sector map (non-secret, SEC-derived, imported from Darwin).
# Lives in the public engine so both the open updater and the private secured
# updater can share one source of truth.
DEFAULT_SECTOR_MAP_PATH = Path(__file__).resolve().parent / "ticker_sectors.json"

# Sectors the bundled map records as unknown also fall into OTHER_GROUP.
_UNKNOWN_SECTORS = {"Unknown", ""}

# Fields that must NEVER appear on a secured entry — the security boundary.
_FORBIDDEN_SECURED_FIELDS = ("positions", "formula", "formula_ref")


class SecuredLeakError(Exception):
    """Raised when a secured entry would expose ticker weights or a formula."""


def load_sector_map(path: str | Path | None = None) -> dict[str, str]:
    """Load the bundled ticker → sector map (or one at `path`).

    Tickers are normalized to upper-case with ``.`` → ``-`` so lookups match the
    simulator's symbols. Callers can pass their own map; the default is the
    non-secret SEC-derived map shipped at `DEFAULT_SECTOR_MAP_PATH`.
    """
    p = Path(path) if path is not None else DEFAULT_SECTOR_MAP_PATH
    raw = json.loads(p.read_text(encoding="utf-8"))
    return {str(k).strip().upper().replace(".", "-"): str(v).strip() for k, v in raw.items()}


def _get(sim, key):
    """Read a field from a SimResult dataclass or a plain dict."""
    if isinstance(sim, dict):
        return sim[key]
    return getattr(sim, key)


def _get_opt(sim, key):
    """Read an optional field, returning None when absent."""
    if isinstance(sim, dict):
        return sim.get(key)
    return getattr(sim, key, None)


def aggregate_exposure(
    positions: list[dict],
    sector_map: dict[str, str] | None = None,
    *,
    include_cash: bool = True,
    min_weight: float = 0.0,
) -> list[dict]:
    """Collapse ticker-level `positions` into sector/asset-class exposure.

    `positions` is ``[{"ticker", "weight"}, ...]`` (as produced by the
    simulator); `sector_map` maps each ticker to its group label. Weights are
    summed per group and the ticker-level vector is dropped — that drop *is* the
    security boundary, so this never returns a ticker.

    * `sector_map` defaults to the bundled SEC-derived map (`load_sector_map()`).
    * A ticker with no known sector (absent, or mapped to "Unknown") falls into
      the ``"Other"`` bucket — the donut is a published **approximation**, so one
      unmapped stock never fails the update or understates total exposure.
    * If `include_cash`, the uninvested residual (``1 - sum(weights)``) is added
      as a ``"Cash"`` slice so the exposure donut sums to ~100%.
    * Groups with weight below `min_weight` are dropped.

    Returns ``[{"group", "weight"}, ...]`` sorted by descending weight.
    """
    if sector_map is None:
        sector_map = load_sector_map()

    grouped: dict[str, float] = {}
    invested = 0.0
    for pos in positions:
        ticker = pos["ticker"]
        weight = float(pos["weight"])
        group = sector_map.get(ticker)
        if not group or group in _UNKNOWN_SECTORS:
            group = OTHER_GROUP
        if group in _FORBIDDEN_SECURED_FIELDS or group == ticker:
            # Defensive: a group label must be a sector, never a ticker symbol.
            raise SecuredLeakError(
                f"sector label {group!r} for {ticker!r} looks like a ticker, not a group"
            )
        grouped[group] = grouped.get(group, 0.0) + weight
        invested += weight

    if include_cash:
        cash = 1.0 - invested
        if cash > 1e-4:
            grouped[CASH_GROUP] = grouped.get(CASH_GROUP, 0.0) + cash

    exposure = [
        {"group": g, "weight": round(w, 4)}
        for g, w in grouped.items()
        if w >= min_weight
    ]
    exposure.sort(key=lambda e: e["weight"], reverse=True)
    return exposure


def build_secured_entry(
    sim, spec: dict, sector_map: dict[str, str] | None = None, **kwargs
) -> dict:
    """Build the sanitized `portfolio.json` entry for a secured strategy.

    `sim` is a `portfolio.SimResult` (or a dict with the same fields). The result
    carries equity curve + stats + aggregate exposure and is run through
    `assert_sanitized` before return, so a leak fails the updater rather than
    reaching the public repo. `sector_map` defaults to the bundled map. Extra
    kwargs pass through to `aggregate_exposure` (e.g. `include_cash`, `min_weight`).
    """
    if sector_map is None:
        sector_map = load_sector_map()
    entry = {
        "id": spec["id"],
        "name": spec["name"],
        "visibility": "secured",
        "equity_curve": _get(sim, "equity_curve"),
        "stats": _get(sim, "stats"),
        "exposure": aggregate_exposure(_get(sim, "positions"), sector_map, **kwargs),
    }
    # Optional split-stats + live marker (one-time backfill). Aggregate-safe:
    # these are performance numbers, never positions, so they pass the boundary.
    if spec.get("deployed_on"):
        entry["live_since"] = spec["deployed_on"]
    for opt in ("stats_backtest", "stats_live"):
        val = _get_opt(sim, opt)
        if val is not None:
            entry[opt] = val
    assert_sanitized(entry, sector_map=sector_map)
    return entry


def assert_sanitized(entry: dict, sector_map: dict[str, str] | None = None) -> dict:
    """Guard: confirm `entry` is a safe secured entry, else raise.

    Defense in depth for the Tier 2a → Tier 1 push. Checks that visibility is
    secured, that none of `positions`/`formula`/`formula_ref` are present, that
    exposure exists, and (when `sector_map` is given) that every exposure group
    is a known sector label rather than a ticker symbol. Returns `entry` so it
    can be used inline.
    """
    if entry.get("visibility") != "secured":
        raise SecuredLeakError(
            f"assert_sanitized expects a secured entry; got visibility="
            f"{entry.get('visibility')!r}"
        )
    leaked = [f for f in _FORBIDDEN_SECURED_FIELDS if f in entry]
    if leaked:
        raise SecuredLeakError(
            f"secured entry {entry.get('id')!r} would leak {leaked}; "
            f"secured strategies publish exposure only"
        )
    exposure = entry.get("exposure")
    if not exposure:
        raise SecuredLeakError(
            f"secured entry {entry.get('id')!r} has no exposure; "
            f"performance-only with empty exposure is not a valid secured entry"
        )
    if sector_map is not None:
        allowed = set(sector_map.values()) | {CASH_GROUP, OTHER_GROUP}
        tickers = set(sector_map)
        for slice_ in exposure:
            group = slice_["group"]
            if group in tickers or group not in allowed:
                raise SecuredLeakError(
                    f"secured entry {entry.get('id')!r} exposure group {group!r} "
                    f"is not a known sector label"
                )
    return entry


def is_rebalance_due(next_rebalance_date: str, today: str | pd.Timestamp) -> bool:
    """True if `today` has reached the strategy's scheduled `next_rebalance_date`.

    Tier 2a's `rebalance.yml` runs daily and rebalances exactly the strategies
    for which this is true (see `docs/subsystems/secured-updater.md`).
    """
    return pd.Timestamp(today).normalize() >= pd.Timestamp(next_rebalance_date).normalize()


def advance_next_rebalance(
    next_rebalance_date: str,
    cadence_days: int,
    today: str | pd.Timestamp,
) -> str:
    """Advance `next_rebalance_date` past `today` by whole cadence steps.

    Stepping by `cadence_days` (rather than `today + cadence`) keeps the schedule
    on its original phase, and the loop tolerates a missed run (e.g. a skipped CI
    day) by catching up to the next future date. Returns an ISO date string.
    """
    nxt = pd.Timestamp(next_rebalance_date)
    today = pd.Timestamp(today)
    step = pd.Timedelta(days=int(cadence_days))
    while nxt <= today:
        nxt = nxt + step
    return nxt.strftime("%Y-%m-%d")
