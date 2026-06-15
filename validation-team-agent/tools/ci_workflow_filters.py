"""Check and repair validation-team-agent CI path filters.

GitHub Actions does not allow `paths` and `paths-ignore` on the same event.
This helper keeps the workflow on the supported `paths` + negated `!` pattern.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "validation-team-agent-ci.yml"

POSITIVE_PATHS = [
    '      - "validation-team-agent/**"',
    '      - ".github/workflows/validation-team-agent-ci.yml"',
]
NEGATED_PATHS = [
    '      - "!validation-team-agent/docs/**"',
    '      - "!validation-team-agent/examples/**"',
    '      - "!validation-team-agent/skills/**"',
    '      - "!validation-team-agent/subagents/**"',
    '      - "!validation-team-agent/README.md"',
    '      - "!validation-team-agent/CLAUDE.md"',
]


def _event_block(text: str, event: str) -> str:
    if event == "push":
        return text[text.index("  push:") : text.index("  pull_request:")]
    return text[text.index("  pull_request:") : text.index("\n\nconcurrency:")]


def check_text(text: str) -> list[str]:
    """Return validation errors for the workflow trigger path filters."""
    errors: list[str] = []
    if "paths-ignore:" in text:
        errors.append("paths-ignore must not be combined with paths")
    for event in ("push", "pull_request"):
        block = _event_block(text, event)
        for path in POSITIVE_PATHS:
            if path not in block:
                errors.append(f"{event} missing {path.strip()}")
        for path in NEGATED_PATHS:
            if path not in block:
                errors.append(f"{event} missing {path.strip()}")
        if all(path in block for path in (POSITIVE_PATHS[-1], NEGATED_PATHS[0])):
            if block.index(NEGATED_PATHS[0]) < block.index(POSITIVE_PATHS[-1]):
                errors.append(f"{event} negated paths must follow positive includes")
    return errors


def _negate_path_line(line: str) -> str:
    value = line.strip()[2:].strip().strip('"')
    return f'      - "!{value}"'


def _fix_event_block(block: str) -> str:
    if "paths-ignore:" not in block:
        return block

    lines = block.splitlines()
    paths_idx = lines.index("    paths:")
    ignore_idx = lines.index("    paths-ignore:")
    if ignore_idx < paths_idx:
        raise ValueError(
            f"Unexpected ordering: paths-ignore at line {ignore_idx} precedes paths at line {paths_idx}. Refusing to fix."
        )
    prefix = lines[: paths_idx + 1]
    positive = lines[paths_idx + 1 : ignore_idx]
    ignored = [_negate_path_line(line) for line in lines[ignore_idx + 1 :] if line.strip().startswith("-")]
    return "\n".join(prefix + positive + ignored) + "\n"


def fix_text(text: str) -> str:
    """Convert paths-ignore blocks to negated paths for both workflow events."""
    push = _event_block(text, "push")
    pull_request = _event_block(text, "pull_request")
    text = text.replace(push, _fix_event_block(push))
    text = text.replace(pull_request, _fix_event_block(pull_request))
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["check", "fix"])
    parser.add_argument("--workflow", type=Path, default=WORKFLOW_PATH)
    args = parser.parse_args(argv)

    text = args.workflow.read_text(encoding="utf-8")
    if args.command == "fix":
        try:
            fixed = fix_text(text)
        except ValueError as exc:
            print(f"refusing to fix: {exc}", file=sys.stderr)
            return 2
        if fixed != text:
            args.workflow.write_text(fixed, encoding="utf-8")
        text = fixed

    errors = check_text(text)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2
    print("validation-team-agent CI path filters valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
