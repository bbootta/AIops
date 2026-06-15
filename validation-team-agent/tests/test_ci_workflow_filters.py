from pathlib import Path

import pytest

from tools.ci_workflow_filters import (
    NEGATED_PATHS,
    POSITIVE_PATHS,
    _negate_path_line,
    check_text,
    fix_text,
)

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "validation-team-agent-ci.yml"


INVALID_WORKFLOW = '''name: validation-team-agent CI

on:
  push:
    branches: ["**"]
    paths:
      - "validation-team-agent/**"
      - ".github/workflows/validation-team-agent-ci.yml"
    paths-ignore:
      - "validation-team-agent/docs/**"
      - "validation-team-agent/examples/**"
      - "validation-team-agent/skills/**"
      - "validation-team-agent/subagents/**"
      - "validation-team-agent/README.md"
      - "validation-team-agent/CLAUDE.md"
  pull_request:
    paths:
      - "validation-team-agent/**"
      - ".github/workflows/validation-team-agent-ci.yml"
    paths-ignore:
      - "validation-team-agent/docs/**"
      - "validation-team-agent/examples/**"
      - "validation-team-agent/skills/**"
      - "validation-team-agent/subagents/**"
      - "validation-team-agent/README.md"
      - "validation-team-agent/CLAUDE.md"

concurrency:
  group: validation-team-agent-${{ github.ref }}
'''


def test_validation_team_agent_workflow_uses_negated_paths_only():
    assert check_text(WORKFLOW_PATH.read_text(encoding="utf-8")) == []


def test_fix_text_converts_paths_ignore_to_negated_paths():
    fixed = fix_text(INVALID_WORKFLOW)

    assert "paths-ignore:" not in fixed
    assert check_text(fixed) == []
    for path in POSITIVE_PATHS + NEGATED_PATHS:
        assert fixed.count(path) == 2


REVERSED_ORDER_WORKFLOW = '''name: validation-team-agent CI

on:
  push:
    branches: ["**"]
    paths-ignore:
      - "validation-team-agent/docs/**"
    paths:
      - "validation-team-agent/**"
  pull_request:
    paths:
      - "validation-team-agent/**"
      - ".github/workflows/validation-team-agent-ci.yml"

concurrency:
  group: validation-team-agent-${{ github.ref }}
'''


def test_fix_refuses_reversed_order():
    with pytest.raises(ValueError):
        fix_text(REVERSED_ORDER_WORKFLOW)


def test_negate_path_handles_single_quotes():
    assert _negate_path_line("      - 'docs/**'") == '      - "!docs/**"'


def test_fix_is_idempotent():
    fixed_once = fix_text(INVALID_WORKFLOW)
    fixed_twice = fix_text(fixed_once)
    assert fixed_once == fixed_twice
