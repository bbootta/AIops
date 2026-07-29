"""검증 산출물의 보관 위치 — 정본은 검증팀 하위 경로에 둔다.

사용자 지시: **검증 산출물은 반드시 적합성검증 팀에이전트의 하위 경로에 저장한다.**

그런데 2선 게이트(`risk_lib.validation.independent.check_gate`)는 응답 파일을
저장소 루트의 교환 디렉터리에서만 찾는다 (`DEFAULT_DIR =
docs/independent_validation`). 정본을 옮기면 게이트가 응답을 못 찾아 `응답대기`가
되고 교환이 끊긴다.

## 왜 사본이 아니라 심볼릭 링크인가

두 곳에 같은 내용을 **복사해 두면 반드시 갈라진다.** 이 교환에서 문서 수치가
코드 사실과 어긋난 지적이 일곱 번 반복됐고(F-103 → F-201 → F-401 → F-501 →
F-B01 → F-C01 → F-D01), 원인은 매번 "같은 사실이 두 곳에 손으로 적혀 있다"는
것이었다. 스스로 그 결함을 만들 수는 없다.

심볼릭 링크는 실체가 하나뿐이라 갈라질 수 없고, 링크가 깨지면 게이트가
`응답대기`로 **막는다**(fail-closed). 낡은 사본을 읽고 통과하는 것보다 안전하다.

이 검사는 배치가 조용히 되돌아가는 것을 막는다 — 특히 누군가 링크를 실제 파일로
바꾸면 실패한다. 그것이 바로 막으려는 상태이기 때문이다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

AGENT_ROOT = Path(__file__).resolve().parent.parent
SSOT_DIR = AGENT_ROOT / "docs" / "independent_validation"
MAILBOX = AGENT_ROOT.parent / "docs" / "independent_validation"

RESPONSE = "RUN-20260630-42.response.json"
DELIVERABLES = (
    RESPONSE,
    "RUN-20260630-42.opinion.md",
    "RUN-20260630-42.approval.md",
    "RUN-20260630-42.conditional_approval.json",
)


def test_deliverables_live_under_the_validation_team_path():
    """네 산출물 모두 검증팀 하위 경로에 실체가 있어야 한다."""
    missing = [n for n in DELIVERABLES if not (SSOT_DIR / n).is_file()]
    assert not missing, (
        f"검증 산출물이 검증팀 하위 경로에 없다: {missing}\n"
        f"  기대 위치: {SSOT_DIR}")


def test_gate_mailbox_points_at_the_ssot_not_a_copy():
    """교환 디렉터리의 응답 파일은 **링크**여야 한다 — 사본이면 갈라진다."""
    if not (SSOT_DIR / RESPONSE).is_file():
        pytest.skip("정본이 없다 — test_deliverables_live_under… 가 먼저 잡는다")
    link = MAILBOX / RESPONSE
    assert link.exists(), (
        f"게이트가 읽는 경로에 응답이 없다: {link}\n"
        f"  2선 check_gate 는 이 경로만 본다 (DEFAULT_DIR)")
    assert link.is_symlink(), (
        f"{link} 가 실제 파일이다 — 정본과 갈라진다.\n"
        f"  같은 사실을 두 곳에 두는 것이 F-501 계열 결함의 원인이었다.")
    assert link.resolve() == (SSOT_DIR / RESPONSE).resolve(), (
        f"링크가 정본을 가리키지 않는다: {link.resolve()}")


def test_response_read_through_the_link_is_the_gate_payload():
    """링크를 통해 읽은 내용이 게이트가 요구하는 형태여야 한다."""
    link = MAILBOX / RESPONSE
    if not link.exists():
        pytest.skip("링크 없음 — 앞 검사가 먼저 잡는다")
    d = json.loads(link.read_text(encoding="utf-8"))
    for key in ("request_id", "run_id", "verdict", "recalc_matches", "findings"):
        assert key in d, f"응답에 게이트 필수 항목이 없다: {key}"
    assert d["verdict"] in ("적합", "경부적합", "중부적합"), d["verdict"]
    assert d["run_id"] == "RUN-20260630-42"
    # 링크를 통해 읽은 것과 정본이 같은 바이트여야 한다 (사본화 방지의 이중 확인).
    assert link.read_bytes() == (SSOT_DIR / RESPONSE).read_bytes()
