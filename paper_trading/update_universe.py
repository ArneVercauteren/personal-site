"""Entry point — rebuild the shared tradable universe.

    python -m paper_trading.update_universe

Heavy (fetches the full symbol directory + bars for a few thousand names), so
it runs **monthly** in its own workflow, not on the daily mark. Writes
`public/data/universe.json`; the daily updaters read it via
`universe.resolve_universe`. See `docs/subsystems/universe.md`.

Env overrides (all optional):
  UNIVERSE_CAP, UNIVERSE_MIN_PRICE, UNIVERSE_MIN_ADV, UNIVERSE_EXCLUDE_ETF,
  UNIVERSE_FETCH_CHUNK, UNIVERSE_FETCH_PAUSE  (politeness toward the price API)
"""

from __future__ import annotations

import argparse
import os

from . import universe


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-current", action="store_true")
    args = parser.parse_args(argv)
    if args.archive_current:
        path = universe.archive_current_universe()
        print(f"archived {path.relative_to(universe.REPO_ROOT)}")
        return
    payload = universe.build_universe(
        min_price=_env_float("UNIVERSE_MIN_PRICE", universe.DEFAULT_MIN_PRICE),
        min_adv=_env_float("UNIVERSE_MIN_ADV", universe.DEFAULT_MIN_ADV),
        cap=_env_int("UNIVERSE_CAP", universe.DEFAULT_CAP),
        exclude_etf=os.environ.get("UNIVERSE_EXCLUDE_ETF", "") not in ("", "0", "false"),
        fetch_chunk=_env_int("UNIVERSE_FETCH_CHUNK", universe.DEFAULT_FETCH_CHUNK),
        fetch_pause=_env_float("UNIVERSE_FETCH_PAUSE", universe.DEFAULT_FETCH_PAUSE),
    )
    print(f"done; as_of={payload['as_of']} count={payload['count']}")


if __name__ == "__main__":
    main()
