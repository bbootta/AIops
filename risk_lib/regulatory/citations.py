"""규정 인용 실태 — 통제가 무엇을 덮고 무엇을 안 덮는가.

`tests/test_citations.py`가 인용 집합을 기준선에 고정한다. 그 통제의 **한계**를
요청서에 싣기 위한 산출 쪽 진입점이다 — 테스트 안에만 두면 산출에서 부를 수
없어 애초에 공시가 불가능하다 (독립검증 지적 F-B01).
"""

from __future__ import annotations

import re

# 국내 규정 인용 — 조·항까지 뽑는다.
_KR = re.compile(
    r"(은행업감독규정|은행법|여신전문금융업법|여신전문금융업감독규정|"
    r"자본시장법|전자금융거래법)\s*제(\d+)조(?:의(\d+))?(?:\s*제(\d+)항)?")


def stats(built: list) -> dict:
    lines = [ln for b in built for ln in b.lines]
    cited = [ln for ln in lines if ln.citation]
    uniq = {ln.citation for ln in cited}
    no_clause = sum(1 for ln in cited for m in _KR.finditer(ln.citation)
                    if not m.group(4))
    seen: dict[tuple[str, str], set[str]] = {}
    for ln in cited:
        for m in _KR.finditer(ln.citation):
            law, art, sub, clause = m.groups()
            key = (ln.line_name,
                   f"{law} 제{art}조" + (f"의{sub}" if sub else ""))
            seen.setdefault(key, set()).add(clause or "—")
    return {
        "n_lines": len(lines), "n_cited": len(cited), "n_unique": len(uniq),
        "n_no_clause": no_clause,
        "n_clause_conflict": sum(1 for v in seen.values() if len(v) > 1),
    }


def coverage_sentence(built: list) -> str:
    """등록 통제가 덮는 범위 — 요청서에 생성해 싣는다."""
    st = stats(built)
    return (
        f"규정 인용은 라인 {st['n_lines']:,}건 중 {st['n_cited']:,}건에 있고 "
        f"고유 문자열은 {st['n_unique']:,}종이다. 그 {st['n_unique']:,}종을 "
        f"기준선에 등록해 새 인용이 검토 없이 들어오는 것을 막지만, **인용이 "
        f"규정 원문과 맞는지는 검증하지 않는다** — 규정 텍스트가 저장소에 없다. "
        f"통과가 곧 정확성이 아니다. 국내 규정 인용 중 항 표기가 없는 것이 "
        f"{st['n_no_clause']:,}건, 같은 라인명에 같은 조의 다른 항이 붙은 것이 "
        f"{st['n_clause_conflict']}건이며 후자는 등록만 하고 정당성은 판단하지 "
        f"않았다 (지적 F-A02 · F-B01)."
    )
