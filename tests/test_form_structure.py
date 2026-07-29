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
import re
from pathlib import Path

import pytest

from risk_lib.regulatory.forms import build_forms

BASELINE = Path(__file__).parent / "form_structure_baseline.json"

# 라인명에 박힌 날짜. 일별 서식(B2316 일별 트레이딩·B2602-2 일별 LCR 등)은
# 라인명이 날짜라 기준일이 바뀌면 이름도 개수도 달라진다.
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}월\s*\d{1,2}일|\d{4}Q[1-4]")


def _structure(built: list) -> dict[str, list[str]]:
    """서식 → 라인 목록. 값은 담지 않고, **기준일에 독립**이어야 한다.

    독립검증 지적 F-A01: 기준선을 시험 고정일(2026-06-11)에서 만들었더니 제출
    실행(2026-06-30)에는 52라인이 더 있어 통제를 제출물에 돌릴 수 없었다.
    라인명이 날짜를 담으므로 **어떤 기준일에서도 FAIL**한다 — 통제가 있는 것과
    통제가 제출물을 덮는 것은 다르다(3선 ADV-PROC-08).

    그래서 날짜를 `<date>`로 바꾸고, 그 결과 같아진 연속 라인은 **하나로 접는다**.
    월마다 영업일 수가 달라 개수까지 같게 만들 수는 없기 때문이다.

    한계 — 일별 계열 **안에서** 라인 하나가 사라지는 것은 잡지 못한다. 그
    라인들은 루프로 생성되므로 손으로 쓴 라인이 사라지는 것(F-901의 실제 양상)
    보다 위험이 낮다고 보고 이 절충을 택했다. 요청서에 공시한다.
    """
    out: dict[str, list[str]] = {}
    for b in built:
        keys: list[str] = []
        for ln in b.lines:
            k = _DATE.sub("<date>", f"{ln.line_code}|{ln.line_name}")
            # 코드도 날짜 계열이면 연번이 붙으므로 이름만으로 접는다.
            name = k.split("|", 1)[1] if "|" in k else k
            if "<date>" in name:
                k = f"<daily>|{name}"
            if keys and keys[-1] == k:
                continue
            keys.append(k)
        out[b.spec.form_id] = keys
    return out


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
    """라인명과 규정 인용의 짝 — **조항까지** 본다.

    F-901에서 편집이 `citation=_C29`를 지우면서 다음 라인의 `citation=_CRE22`가
    대손준비금 라인에 붙었다. 그래서 이 검사를 만들었는데, "제29조" 포함만 보아
    **항의 차이를 구분하지 못했다** — 해외 서식이 순차액에 제1항(최저적립률)을
    달고 있는 것을 놓쳤고 3선이 열 회차 만에 찾았다 (지적 F-A02).

    제29조 제1항은 최저적립률을, **제2항이 "미달하는 경우 그 차액"**을 정한다.
    같은 항목에 다른 항이 붙으면 근거가 틀린 것이다. 통제가 한 단계 성기면
    그 한 단계만큼 결함이 산다.
    """
    bad: list[str] = []
    for b in built:
        for ln in b.lines:
            c = ln.citation or ""
            name = ln.line_name
            if "대손준비금" in name and ("순차액" in name or "소요액" in name):
                if "제29조 제2항" not in c:
                    bad.append(f"{b.spec.form_id}/{ln.line_code} {name} → {c}")
            elif "최저적립" in name and "제29조" in c:
                if "제29조 제1항" not in c:
                    bad.append(f"{b.spec.form_id}/{ln.line_code} {name} → {c}")
    assert not bad, (
        "대손준비금 라인의 조항이 어긋난다 (제1항=최저적립률 · 제2항=차액):\n  "
        + "\n  ".join(bad[:20]))


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
