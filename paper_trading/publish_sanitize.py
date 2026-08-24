"""Publish-time scrub of internal filesystem paths from open-strategy JSON.

The Astralanx exporter (Tier 3, `docs/subsystems/darwin-publish.md`) attaches
per-run `open_diagnostics` to each open strategy spec. Some of those provenance
strings — notably `sector_neutrality.sector_map_source` — are **absolute paths
inside the private Darwin repo**, e.g. ``C:\\Users\\<user>\\Projects\\Darwin\\...``.
The open updater (`paper_trading/update.py`) projects the `performance` block
onto the fields consumed by the site and scrubs all retained values. Without
that boundary, exporter-only artifacts and paths could land in public,
CDN-served JSON — leaking the OS username and internal Darwin layout. That
violates the separation-from-Darwin / no-internal-paths invariant
(`docs/concepts/separation-from-darwin.md`).

The site never renders `sector_map_source` (the analytics page intentionally
ignores it and `lib/data.ts` leaves it untyped), so redacting it is
display-safe. This module is the open-side analogue of
`paper_trading/secured.py::assert_sanitized`: `scrub_internal_paths` produces a
clean copy and `assert_no_internal_paths` is the defense-in-depth guard that
fails the updater rather than letting a path reach the public repo.
"""

from __future__ import annotations

import re

__all__ = [
    "InternalPathLeakError",
    "SECTOR_MAP_LABEL",
    "looks_like_internal_path",
    "project_public_performance",
    "scrub_internal_paths",
    "assert_no_internal_paths",
]

# Non-path provenance label that replaces `sector_map_source`. The neighbouring
# `methodology` string already documents the real provenance ("Estimated using
# current SEC SIC-derived sectors"), so this just keeps the field meaningful
# without naming a filesystem path.
SECTOR_MAP_LABEL = "SEC SIC-derived"

_REDACTED = "[redacted internal path]"

# The site renders only this subset of the exporter diagnostics.  Keeping an
# explicit allowlist prevents large, duplicate raw artifacts from quietly
# becoming part of the public contract just because Darwin added them to an
# internal result object.  Nested metric objects remain extensible and are
# still path-scrubbed recursively.
_PERFORMANCE_SEGMENTS = ("training", "oos", "combined")
_RUN_FIELDS = ("start", "end", "windows", "equity_curve", "stats", "open_diagnostics")
_OPEN_DIAGNOSTIC_FIELDS = (
    "annual_returns",
    "max_drawdown",
    "sector_neutrality",
    "capacity_analysis",
    "fama_french_regression",
    "rolling_3y_sharpe",
    "rolling_3y_sharpe_series",
    "picks_records",
)

# Matches the start of an absolute filesystem path that should never appear in
# public JSON: a Windows drive letter (``C:\`` / ``C:/``), a UNC share
# (``\\server\``), or a POSIX home directory (``/home/`` / ``/Users/``).
_INTERNAL_PATH_RE = re.compile(
    r"""(?:
          [A-Za-z]:[\\/]      # Windows drive letter:  C:\  or  C:/
        | \\\\[^\\]+\\        # UNC path:  \\server\share
        | /(?:home|Users)/   # POSIX home directory
    )""",
    re.VERBOSE,
)


class InternalPathLeakError(Exception):
    """Raised when a publishable payload still contains an internal path."""


def looks_like_internal_path(value: str) -> bool:
    """True if `value` contains an absolute drive-letter / home-dir / UNC path."""
    return bool(_INTERNAL_PATH_RE.search(value))


def scrub_internal_paths(obj):
    """Return a deep copy of `obj` with internal filesystem paths removed.

    `sector_map_source` is relabelled to `SECTOR_MAP_LABEL` (the field is a
    provenance tag, not data the site reads); any *other* string that looks like
    an absolute path is replaced with a redaction placeholder. Dicts and lists
    are walked recursively; everything else is returned unchanged.
    """
    if isinstance(obj, dict):
        cleaned = {}
        for key, value in obj.items():
            if key == "sector_map_source" and isinstance(value, str):
                cleaned[key] = SECTOR_MAP_LABEL
            else:
                cleaned[key] = scrub_internal_paths(value)
        return cleaned
    if isinstance(obj, list):
        return [scrub_internal_paths(item) for item in obj]
    if isinstance(obj, str) and looks_like_internal_path(obj):
        return _REDACTED
    return obj


def project_public_performance(performance: dict) -> dict:
    """Return the allowlisted performance payload consumed by the site.

    Darwin's internal diagnostics can contain raw CSV-style ``artifacts``, a
    duplicate daily ``holdings`` series, and other analysis blocks the site
    neither types nor renders.  Publishing those fields inflated the static
    metadata by several megabytes and made internal exporter additions public
    by default.  This projection makes the boundary opt-in instead.
    """
    if not isinstance(performance, dict):
        raise TypeError("performance must be an object")

    public: dict = {}
    for segment in _PERFORMANCE_SEGMENTS:
        raw_run = performance.get(segment)
        if raw_run is None:
            continue
        if not isinstance(raw_run, dict):
            raise TypeError(f"performance.{segment} must be an object")

        run = {field: raw_run[field] for field in _RUN_FIELDS if field in raw_run}
        diagnostics = raw_run.get("open_diagnostics")
        if diagnostics is not None:
            if not isinstance(diagnostics, dict):
                raise TypeError(
                    f"performance.{segment}.open_diagnostics must be an object"
                )
            run["open_diagnostics"] = {
                field: diagnostics[field]
                for field in _OPEN_DIAGNOSTIC_FIELDS
                if field in diagnostics
            }
        public[segment] = run

    return assert_no_internal_paths(scrub_internal_paths(public))


def assert_no_internal_paths(obj, *, _path: str = "$"):
    """Guard: raise `InternalPathLeakError` if any string is an internal path.

    Defense in depth for the Tier 3 → Tier 1 pass-through — call it after
    `scrub_internal_paths` so a missed path fails the updater loudly instead of
    being committed. Returns `obj` so it can be used inline.
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            assert_no_internal_paths(value, _path=f"{_path}.{key}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            assert_no_internal_paths(item, _path=f"{_path}[{i}]")
    elif isinstance(obj, str) and looks_like_internal_path(obj):
        raise InternalPathLeakError(
            f"internal filesystem path would be published at {_path}: {obj!r}"
        )
    return obj
