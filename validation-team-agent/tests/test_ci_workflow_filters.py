from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "validation-team-agent-ci.yml"

NEGATED_PATHS = [
    '      - "!validation-team-agent/docs/**"',
    '      - "!validation-team-agent/examples/**"',
    '      - "!validation-team-agent/skills/**"',
    '      - "!validation-team-agent/subagents/**"',
    '      - "!validation-team-agent/README.md"',
    '      - "!validation-team-agent/CLAUDE.md"',
]


def _push_block(text: str) -> str:
    return text[text.index("  push:") : text.index("  pull_request:")]


def _pull_request_block(text: str) -> str:
    return text[text.index("  pull_request:") : text.index("\n\nconcurrency:")]


def test_validation_team_agent_workflow_uses_negated_paths_only():
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "paths-ignore:" not in text
    for block in (_push_block(text), _pull_request_block(text)):
        assert "paths:" in block
        assert '      - "validation-team-agent/**"' in block
        assert '      - ".github/workflows/validation-team-agent-ci.yml"' in block
        for path in NEGATED_PATHS:
            assert path in block
        assert block.index('      - ".github/workflows/validation-team-agent-ci.yml"') < block.index(
            NEGATED_PATHS[0]
        )
