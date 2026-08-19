"""이 저장소의 리스크 에이전트 명부.

`.claude/agents/` 는 여러 팀 하네스가 함께 쓴다. 리스크·법무·번역·데이터·
디자인·연구 에이전트가 한 디렉터리에 있으므로, 리스크 규약(3선 위임 문구,
RYNTA 제품 표기, 자동확정 금지)을 검사할 때 전체를 훑으면 번역 에이전트가
리스크 검증팀을 인용해야 하는 셈이 된다.

명부를 손으로 유지하는 것은 의도다. glob 으로 잡으면 새 리스크 에이전트가
규약 문구 없이 들어와도 조용히 통과한다. `assert_roster_is_current()` 가
디스크와 명부의 어긋남을 잡는다.
"""

from __future__ import annotations

from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "agents"

# 리스크 산출 도메인 에이전트. 규약 문구를 모두 달아야 한다.
RISK_DOMAIN_AGENTS = (
    "bis-ratio-analyst",
    "credit-rating-modeler",
    "delinquency-pd-lgd-monitor",
    "ifrs9-ecl-analyst",
    "limit-manager",
    "macro-indicator-monitor",
    "market-risk-analyst",
    "prudential-capital-analyst",
    "rapm-analyst",
    "rwa-calculator",
    "stress-test-engineer",
)

# 리스크 하네스이되 역할이 달라 따로 검사하는 것들.
RISK_ROLE_AGENTS = (
    "risk-orchestrator",        # 코디네이터. 위임을 강제하는 쪽
    "risk-validator",           # 자체검증(2선). 독립검증이 아니라고 선언해야 한다
    "aims-compliance-auditor",  # 내부심사자 (ISO/IEC 42001 조항 9.2)
)

# 다른 팀 하네스. 접두어로 갈리지 않는 것만 이름으로 적는다.
_OTHER_TEAM_PREFIXES = ("legal-", "rp-", "translation-")
_OTHER_TEAM_NAMES = frozenset({
    # 세일즈팀 (2026-08 신설)
    "channel-strategist", "cold-email-writer", "deal-strategist",
    "deliverability-engineer", "outreach-qa", "prospect-researcher",
    "sales-compliance-officer", "sales-lead", "sales-ops-analyst",
    "accuracy-reviewer", "analytics-engineer", "brand-designer",
    "data-engineering-lead", "data-quality-engineer", "design-director",
    "design-reviewer", "dimensional-data-modeler", "doc-analyst",
    "fact-data-modeler", "fluency-editor", "marketing-designer",
    "pipeline-ops-engineer", "presentation-designer", "spark-engineer",
    "streaming-engineer", "terminology-curator", "translator", "ui-designer",
})


def risk_agents_on_disk() -> set[str]:
    """다른 팀 것을 걷어내고 남은 리스크 에이전트 이름."""
    out = set()
    for f in sorted(AGENTS_DIR.glob("*.md")):
        stem = f.stem
        if stem.startswith(_OTHER_TEAM_PREFIXES) or stem in _OTHER_TEAM_NAMES:
            continue
        out.add(stem)
    return out


def assert_roster_is_current() -> None:
    """리스크 에이전트가 새로 들어오거나 사라지면 실패한다."""
    known = set(RISK_DOMAIN_AGENTS) | set(RISK_ROLE_AGENTS)
    seen = risk_agents_on_disk()
    assert seen == known, (
        f"명부 밖 {sorted(seen - known)} · 사라진 것 {sorted(known - seen)} "
        "(리스크 에이전트면 tests/risk_agents.py 에 넣고, 다른 팀 것이면 "
        "_OTHER_TEAM_NAMES 에 넣는다)")
