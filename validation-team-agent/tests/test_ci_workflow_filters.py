from pathlib import Path

from tools.ci_workflow_filters import NEGATED_PATHS, POSITIVE_PATHS, check_text, fix_text

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
