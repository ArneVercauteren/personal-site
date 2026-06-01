from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHARED_SOURCE = REPO_ROOT / "plans_and_text_files" / "AI_AGENT_SHARED_INSTRUCTIONS.md"


@dataclass(frozen=True)
class RenderTarget:
    path: Path
    title: str
    lead: str
    root_prefix: str


TARGETS = (
    RenderTarget(
        path=REPO_ROOT / "CLAUDE.md",
        title="personal-site — AI working agreement",
        lead=(
            "> **Read this every session.** Auto-loaded by Claude Code (`CLAUDE.md`) and Codex "
            "(`AGENTS.md`). Treat the contents as binding context."
        ),
        root_prefix="",
    ),
    RenderTarget(
        path=REPO_ROOT / "AGENTS.md",
        title="personal-site — AI working agreement",
        lead=(
            "> **Read this every session.** Auto-loaded by Claude Code (`CLAUDE.md`) and Codex "
            "(`AGENTS.md`). Treat the contents as binding context."
        ),
        root_prefix="",
    ),
    RenderTarget(
        path=REPO_ROOT / ".github" / "copilot-instructions.md",
        title="personal-site — GitHub Copilot instructions",
        lead=(
            "> Same agreement as [CLAUDE.md]({root_prefix}CLAUDE.md) and "
            "[AGENTS.md]({root_prefix}AGENTS.md). Keep all three in sync by editing the shared "
            "source and re-running `python scripts/sync_ai_docs.py`."
        ),
        root_prefix="../",
    ),
)

GENERATED_NOTE = (
    "> Generated from [plans_and_text_files/AI_AGENT_SHARED_INSTRUCTIONS.md]"
    "({root_prefix}plans_and_text_files/AI_AGENT_SHARED_INSTRUCTIONS.md) via "
    "`python scripts/sync_ai_docs.py`. Edit the shared source, then re-run the sync script. "
    "Do not hand-edit this file."
)


def _load_shared_body() -> str:
    body = SHARED_SOURCE.read_text(encoding="utf-8").rstrip()
    if "{{ROOT_PREFIX}}" not in body:
        raise ValueError("Shared instructions template must contain {{ROOT_PREFIX}} placeholders.")
    return body


def _render_target(target: RenderTarget, shared_body: str) -> str:
    lead = target.lead.format(root_prefix=target.root_prefix)
    generated_note = GENERATED_NOTE.format(root_prefix=target.root_prefix)
    body = shared_body.replace("{{ROOT_PREFIX}}", target.root_prefix)
    return f"# {target.title}\n\n{lead}\n\n{generated_note}\n\n{body}\n"


def _write_if_needed(target: RenderTarget, expected: str) -> bool:
    current = target.path.read_text(encoding="utf-8") if target.path.exists() else None
    if current == expected:
        return False
    target.path.parent.mkdir(parents=True, exist_ok=True)
    target.path.write_text(expected, encoding="utf-8")
    return True


def _check_target(target: RenderTarget, expected: str) -> bool:
    if not target.path.exists():
        print(f"Missing generated file: {target.path.relative_to(REPO_ROOT)}", file=sys.stderr)
        return False
    current = target.path.read_text(encoding="utf-8")
    if current == expected:
        return True
    print(
        f"Out of sync: {target.path.relative_to(REPO_ROOT)}. Run `python scripts/sync_ai_docs.py`.",
        file=sys.stderr,
    )
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Render and verify synced AI agent instruction docs.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify generated files are up to date without rewriting them.",
    )
    args = parser.parse_args()

    shared_body = _load_shared_body()
    rendered = {target: _render_target(target, shared_body) for target in TARGETS}

    if args.check:
        is_clean = all(_check_target(target, expected) for target, expected in rendered.items())
        return 0 if is_clean else 1

    changed_paths = []
    for target, expected in rendered.items():
        if _write_if_needed(target, expected):
            changed_paths.append(target.path.relative_to(REPO_ROOT).as_posix())

    if changed_paths:
        print("Updated AI agent docs:")
        for rel_path in changed_paths:
            print(f"- {rel_path}")
    else:
        print("AI agent docs already in sync.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
