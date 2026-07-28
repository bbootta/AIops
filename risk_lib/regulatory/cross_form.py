"""서식 간 대사 — 같은 수치가 여러 서식에서 같은 값인가.

서식검증(`FormCheck`)은 **한 서식 안에서만** 대사한다. 그래서 같은 수치가 서식
A에서는 맞고 서식 B에서는 틀려도 둘 다 통과한다. 실제로 그랬다 — 대손준비금
소요액을 합계 기준으로 고치면서 BR-11만 고치고 제출 서식 5종을 놓쳤는데,
같은 팩 안에서 **같은 라인명·같은 규정 인용으로 2.41배 차이**가 나는 상태로
"서식검증 1,735건 실패 0"이 나왔다 (독립검증 지적 F-701).

시정 확인은 "고친 곳"이 아니라 **"쓰는 곳 전부"** 에서 해야 한다. 이 모듈이
그 전부를 한 자리에 모은다.

## 왜 자동 탐지가 아니라 등록인가

라인명으로 자동 묶으면 부문별 표의 동명 라인이 전부 걸려 거짓 경보가 된다
(예: "대손준비금 순차액"은 여신종별·가계·주담대에 각각 다른 값으로 실린다).
전행 수준에서 **같아야만 하는** 수치를 명시적으로 등록하는 편이 정확하고,
등록되지 않은 수치가 있으면 그 사실 자체가 보인다.
"""

from __future__ import annotations

from dataclasses import dataclass

from risk_lib.validation.consistency import ConsistencyCheck


@dataclass(frozen=True)
class CrossFormInvariant:
    """여러 서식에 실리는 전행 수준 수치 하나."""
    name: str
    lines: tuple[tuple[str, str], ...]   # (form_id, line_code)
    tolerance: float = 1.0
    note: str = ""


# 전행 수준에서 서식 간에 같아야 하는 수치. 부문별 분해는 여기 넣지 않는다 —
# 값이 다른 것이 정상이기 때문이다.
INVARIANTS: tuple[CrossFormInvariant, ...] = (
    CrossFormInvariant(
        "대손준비금 소요액",
        (("BR-11", "3000"), ("B2402", "4000"), ("B2506", "4000")),
        note="은행업감독규정 제29조 제2항 — 합계 기준. 지적 F-601·F-701",
    ),
    CrossFormInvariant(
        "감독규정 최저적립액 합계",
        (("BR-11", "1000"), ("B2402", "2000")),
        note="은행업감독규정 제29조 제1항",
    ),
    CrossFormInvariant(
        "위험가중자산 합계",
        (("BR-01", "2000"), ("BR-20", "5000"), ("B2311", "2000"), ("B2312", "4000")),
        note="CRE20.1 · RBC20.11 — 총괄·종합요약·연결이 같아야 한다",
    ),
    CrossFormInvariant(
        "보통주자본비율",
        (("BR-01", "3100"), ("BR-21", "1000"), ("BR-14", "2100")),
        tolerance=1e-9, note="은행업감독규정 제26조",
    ),
    CrossFormInvariant(
        "총자본비율",
        (("BR-01", "3300"), ("BR-31", "1110"), ("B2311", "3000")),
        tolerance=1e-9, note="은행업감독규정 제26조",
    ),
    CrossFormInvariant(
        "레버리지비율",
        (("BR-07", "3000"), ("B5101", "3040"), ("BF605", "3000")),
        tolerance=1e-9, note="LEV20.1 — 단순기본자본비율",
    ),
    CrossFormInvariant(
        "기대신용손실 합계",
        (("BR-11", "2000"), ("B2402", "3000"), ("B2403", "1020"),
         ("B2431", "1020")),
        note="IFRS 9 5.5",
    ),
    CrossFormInvariant(
        "유동성커버리지비율",
        (("BR-08", "5000"), ("BR-31", "1510")),
        tolerance=1e-9, note="LCR20.1",
    ),
    CrossFormInvariant(
        "순안정자금조달비율",
        (("BR-09", "3000"), ("B2913", "3300"), ("B2916", "2000")),
        tolerance=1e-9, note="NSF20.1",
    ),
)


def _value(built: list, form_id: str, line_code: str) -> float | None:
    for b in built:
        if b.spec.form_id != form_id:
            continue
        for ln in b.lines:
            if ln.line_code == line_code:
                return None if ln.value is None else float(ln.value)
    return None


def cross_form_checks(built: list) -> list[ConsistencyCheck]:
    """등록된 수치가 전 서식에서 일치하는지 대사한다."""
    out: list[ConsistencyCheck] = []
    for inv in INVARIANTS:
        found = {f"{fid}/{lc}": _value(built, fid, lc) for fid, lc in inv.lines}
        missing = [k for k, v in found.items() if v is None]
        if missing:
            # 라인이 사라진 것과 값이 같은 것은 다르다 — 사라지면 대사가
            # 조용히 통과하므로 그것부터 막는다.
            out.append(ConsistencyCheck(
                f"cross_form_{inv.name}", "FAIL",
                f"대사 대상 라인 없음: {', '.join(missing)} — "
                f"서식이 바뀌면 등록도 따라 바뀌어야 한다",
                metric=float(len(missing))))
            continue
        vals = list(found.values())
        spread = max(vals) - min(vals)
        if spread > inv.tolerance:
            detail = " · ".join(f"{k} {v:,.2f}" for k, v in found.items())
            out.append(ConsistencyCheck(
                f"cross_form_{inv.name}", "FAIL",
                f"서식 간 불일치 (최대차 {spread:,.2f}) — {detail}"
                + (f" [{inv.note}]" if inv.note else ""),
                metric=spread))
        else:
            out.append(ConsistencyCheck(
                f"cross_form_{inv.name}", "PASS",
                f"{len(vals)}개 서식 일치 ({vals[0]:,.2f})", metric=spread))
    return out
