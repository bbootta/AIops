"""규정 인용 등록 — 인용 문자열을 열거 가능한 상태로 유지한다.

지금까지 인용 오류는 **3선이 표본에서 찾을 때마다 하나씩** 고쳤다.

    F-801  값은 고쳤는데 산출근거를 안 고침
    F-901  편집이 인용을 뒤바꿈 (제29조 → CRE22)
    F-A02  순차액에 제1항(최저적립률)이 붙음 — 3선이 8건 표본에서 발견

F-A02 시정 때 검사를 조항까지 보도록 넓혔더니 **같은 유형이 5건 더** 나왔다.
표본에서 하나 나오면 모집단에 더 있다는 뜻이고, 실제로 그랬다. 결함을 만난
자리에만 검사를 붙이는 것은 통제가 아니라 사후 대응이다.

    조항 정정 8건 (제1항↔제2항) · 조항 명시화 9건 (항 표기 없음 → 제1항)

처음에는 이것을 "9건 정정"이라고 적었는데 **틀렸다** — 3선이 표본에서 찾은 2건이
내가 센 7건에 이미 포함돼 있는데 다시 더했다 (지적 F-B02). 명제는 맞았으나
셈이 틀렸고, 그 셈이 커밋 메시지와 시정 문서에 그대로 실렸다.

## 이 검사가 하는 일과 하지 않는 일

**한다** — 서식이 쓰는 고유 인용 문자열 전부를 기준선에 고정한다. 새 인용이
생기거나 기존 인용이 바뀌면 실패하고, 기준선 갱신 diff가 곧 "이 인용을
검토했다"는 기록이 된다. 5,397라인은 통독할 수 없지만 473종은 통독할 수 있다.

**하지 않는다** — 인용이 규정 원문과 맞는지는 **검증하지 않는다**. 규정 텍스트가
저장소에 없기 때문이다. 이 검사가 통과한다고 인용이 옳은 것이 아니라, 인용
집합이 **누구도 본 적 없는 채로 늘어나지 않는다**는 것뿐이다. 그 차이를 흐리면
안 된다 (3선 ADV-PROC-08 — 통제가 있는 것과 통제가 덮는 것은 다르다).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from risk_lib.regulatory.forms import build_forms

BASELINE = Path(__file__).parent / "citation_baseline.json"
CLAUSE_BASELINE = Path(__file__).parent / "citation_clause_baseline.json"

# 국내 규정 인용 — 조·항까지 뽑는다.
_KR = re.compile(
    r"(은행업감독규정|은행법|여신전문금융업법|여신전문금융업감독규정|"
    r"자본시장법|전자금융거래법)\s*제(\d+)조(?:의(\d+))?(?:\s*제(\d+)항)?")


@pytest.fixture(scope="module")
def built(result, portfolio):
    from risk_lib.ui_studio.studio import build_studio
    studio = build_studio(result, portfolio)
    return build_forms(result, portfolio, studio.tables)


def _citations(built: list) -> list[str]:
    return sorted({ln.citation for b in built for ln in b.lines if ln.citation})


def test_every_citation_is_declared(built):
    """서식이 쓰는 인용은 전부 기준선에 있어야 한다.

    새 인용이 검토 없이 들어오는 것을 막는다. 옳은지는 보지 않는다 — 그건
    사람이 기준선 diff를 읽고 판단할 몫이다.
    """
    if not BASELINE.exists():
        pytest.skip("기준선 없음 — python3 -m tests.test_citations 로 생성한다")
    base = set(json.loads(BASELINE.read_text(encoding="utf-8")))
    now = set(_citations(built))
    added = sorted(now - base)
    assert not added, (
        f"등록되지 않은 인용 {len(added)}종 — 규정 근거를 확인하고 기준선을 "
        f"갱신하라:\n  " + "\n  ".join(added[:20]))


def test_removed_citations_are_declared(built):
    """사라진 인용도 보여야 한다 — 편집이 인용을 지운 적이 있다 (F-901)."""
    if not BASELINE.exists():
        pytest.skip("기준선 없음")
    base = set(json.loads(BASELINE.read_text(encoding="utf-8")))
    gone = sorted(base - set(_citations(built)))
    assert not gone, (
        f"인용 {len(gone)}종이 사라졌다 — 의도한 변경이면 기준선을 갱신하라:\n  "
        + "\n  ".join(gone[:20]))


def test_same_article_is_not_cited_with_conflicting_clauses(built):
    """같은 라인 개념에 같은 조의 다른 항이 **새로** 붙는 것을 잡는다.

    F-A02가 그것이다 — 대손준비금 순차액에 국내 서식은 제29조 제2항, 해외
    서식은 제1항을 달았다.

    단언이 아니라 **증분 탐지**다. "비고" · "한도금액" 같은 일반 라인명은 서식이
    다르면 항이 다른 것이 정당하고, 그것까지 실패로 만들면 거짓 경보가 되어
    다음 사람이 검사를 끈다. 기존 조합은 기준선에 등록해 두고 **새로 생기는
    것만** 잡는다 — 등록된 것이 옳다는 뜻은 아니며, 기준선 자체가 검토 대상이다.
    """
    seen: dict[tuple[str, str], set[str]] = {}
    for b in built:
        for ln in b.lines:
            if not ln.citation:
                continue
            for m in _KR.finditer(ln.citation):
                law, art, sub, clause = m.groups()
                key = (ln.line_name, f"{law} 제{art}조" + (f"의{sub}" if sub else ""))
                seen.setdefault(key, set()).add(clause or "—")
    conflict = {f"{name} / {art}": sorted(cl)
                for (name, art), cl in seen.items() if len(cl) > 1}
    if not CLAUSE_BASELINE.exists():
        pytest.skip("기준선 없음 — python3 -m tests.test_citations 로 생성한다")
    known = json.loads(CLAUSE_BASELINE.read_text(encoding="utf-8"))
    new = {k: v for k, v in conflict.items()
           if k not in known or known[k] != v}
    assert not new, (
        f"같은 조의 다른 항이 새로 붙었다 {len(new)}건 — F-A02와 같은 유형이다. "
        f"정당하면 기준선을 갱신하고 사유를 커밋에 남겨라:\n  "
        + "\n  ".join(f"{k} → 제{'·'.join(v)}항"
                       for k, v in list(new.items())[:20]))


def test_citation_coverage_is_reported(built):
    """인용 없는 라인이 과반이 되지 않는다 — 근거 없는 제출본은 성립하지 않는다."""
    total = sum(len(b.lines) for b in built)
    with_cite = sum(1 for b in built for ln in b.lines if ln.citation)
    assert with_cite / total > 0.8, (
        f"인용 있는 라인 {with_cite:,}/{total:,} ({with_cite/total:.1%})")


def _main() -> None:
    from risk_lib.data_gen import generate_portfolio
    from risk_lib.pipeline import run_pipeline
    from risk_lib.ui_studio.studio import build_studio
    p = generate_portfolio(seed=42)
    r = run_pipeline(p, asof="2026-06-11", seed=42)
    s = build_studio(r, p)
    built = build_forms(r, p, s.tables)
    cites = _citations(built)
    BASELINE.write_text(json.dumps(cites, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    seen: dict[tuple[str, str], set[str]] = {}
    for b in built:
        for ln in b.lines:
            for m in _KR.finditer(ln.citation or ""):
                law, art, sub, clause = m.groups()
                key = (ln.line_name,
                       f"{law} 제{art}조" + (f"의{sub}" if sub else ""))
                seen.setdefault(key, set()).add(clause or "—")
    conflict = {f"{n} / {a}": sorted(c) for (n, a), c in seen.items() if len(c) > 1}
    CLAUSE_BASELINE.write_text(
        json.dumps(conflict, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8")
    print(f"{BASELINE} 갱신 — 고유 인용 {len(cites)}종")
    print(f"{CLAUSE_BASELINE} 갱신 — 조·항 혼용 {len(conflict)}건 (검토 대상)")


if __name__ == "__main__":
    _main()
