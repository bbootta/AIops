"""서식 구조 회귀 — 라인이 조용히 사라지지 않게 한다.

독립검증 지적 F-901: 산출근거 문자열을 고치는 편집이 `BF202`의 공시 라인 2건
(담보평가액·담보인정액)을 함께 지웠고, **어떤 통제도 잡지 못했다**.

    서식검증 1,735건       실패 0
    교차 서식 대사 9건      전부 PASS
    자체검증               PASS 60 · FAIL 0
    테스트                 1,049 passed — 직전 회차와 건수·결과 동일

값을 보는 검증은 전부 무사했다. 사라진 라인은 대사에 참여하지 않으므로
아무 데도 걸리지 않는다. 값이 아니라 **구조**를 봐야 잡힌다.

## 왜 값이 아니라 구조인가

값은 매 회차 바뀐다(포트폴리오·시정·기준일). 그래서 값 기반 지문은 회차마다
다시 고정해야 하고, 다시 고정하는 순간 사라진 라인도 함께 승인된다 — 실제로
문서 생성 구간 대조가 라인 수 감소를 FAIL로 알렸는데 값을 갱신하는 것으로
끝냈다. 구조(서식 → 라인코드·라인명)는 의도적으로 바꿀 때만 바뀌므로 기준선을
두고 **차이를 설명하게** 할 수 있다.

기준선은 `tests/form_structure_baseline.json`이며, 서식을 의도적으로 바꿨다면
`python3 -m tests.test_form_structure --update`로 갱신한다. 갱신 커밋의 diff가
곧 "무엇을 왜 바꿨는가"의 기록이 된다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from risk_lib.regulatory.forms import build_forms

BASELINE = Path(__file__).parent / "form_structure_baseline.json"


def _structure(built: list) -> dict[str, list[str]]:
    """서식 → 라인코드 목록. 값은 담지 않는다."""
    return {b.spec.form_id: [f"{ln.line_code}|{ln.line_name}" for ln in b.lines]
            for b in built}


@pytest.fixture(scope="module")
def built(result, portfolio):
    from risk_lib.ui_studio.studio import build_studio
    studio = build_studio(result, portfolio)
    return build_forms(result, portfolio, studio.tables)


def test_no_form_line_disappears(built):
    """기준선에 있던 라인이 사라지면 실패한다 — 가장 위험한 방향이다."""
    if not BASELINE.exists():
        pytest.skip("기준선 없음 — --update 로 생성한다")
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    now = _structure(built)

    gone_forms = sorted(set(base) - set(now))
    assert not gone_forms, f"서식이 사라졌다: {gone_forms}"

    removed: list[str] = []
    for form_id, lines in base.items():
        missing = [ln for ln in lines if ln not in set(now.get(form_id, []))]
        removed += [f"{form_id}/{ln}" for ln in missing]
    assert not removed, (
        f"공시 라인 {len(removed)}건이 사라졌다 — 의도한 변경이면 기준선을 "
        f"갱신하고 그 커밋에 사유를 남겨라:\n  " + "\n  ".join(removed[:20]))


def test_added_lines_are_declared(built):
    """새 라인은 허용하되 기준선 갱신을 요구한다 — 증가도 눈에 보여야 한다."""
    if not BASELINE.exists():
        pytest.skip("기준선 없음")
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    now = _structure(built)
    added: list[str] = []
    for form_id, lines in now.items():
        known = set(base.get(form_id, []))
        added += [f"{form_id}/{ln}" for ln in lines if ln not in known]
    assert not added, (
        f"라인 {len(added)}건이 늘었다 — 의도한 변경이면 기준선을 갱신하라:\n  "
        + "\n  ".join(added[:20]))


def test_citation_survives_edits(built):
    """대손준비금 라인에 담보 규정이 붙는 식의 인용 뒤바뀜을 막는다.

    F-901에서 편집이 `citation=_C29`를 지우면서 다음 라인의 `citation=_CRE22`가
    대손준비금 라인에 붙었다. 라인명과 인용의 짝은 규정 근거 그 자체다.
    """
    for b in built:
        for ln in b.lines:
            if "대손준비금" not in ln.line_name or not ln.citation:
                continue
            assert "제29조" in ln.citation, (
                f"{b.spec.form_id}/{ln.line_code} 대손준비금 라인에 "
                f"엉뚱한 인용: {ln.citation}")


def _main() -> None:
    """기준선 갱신 — 서식을 의도적으로 바꿨을 때만 쓴다."""
    from risk_lib.data_gen import generate_portfolio
    from risk_lib.pipeline import run_pipeline
    from risk_lib.ui_studio.studio import build_studio
    p = generate_portfolio(seed=42)
    r = run_pipeline(p, asof="2026-06-11", seed=42)
    s = build_studio(r, p)
    struct = _structure(build_forms(r, p, s.tables))
    BASELINE.write_text(
        json.dumps(struct, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8")
    print(f"{BASELINE} 갱신 — 서식 {len(struct)} · 라인 "
          f"{sum(len(v) for v in struct.values()):,}")


if __name__ == "__main__":
    _main()
