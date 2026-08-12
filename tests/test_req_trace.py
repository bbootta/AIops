"""요건 추적 — 증빙 없는 반영 표시가 불가능하게 고정한다.

요건 추적표는 "우리가 무엇을 했다"는 주장의 목록이다. 이 저장소에서 문서의
주장이 코드와 갈라진 유형(F-103·F-201·F-401·F-501·F-B02)이 다섯 번 났으므로,
추적표의 모든 증빙 참조는 **기계가 실재를 확인**한다:

    module → import 가능해야 한다
    table  → 정규 카탈로그에 있어야 한다
    screen → 화면 소스(app.py)에 그 문자열이 있어야 한다
    test   → tests/ 아래에 그 테스트 함수가 있어야 한다

참조가 하나라도 죽으면(모듈 개명·테이블 삭제·화면 문구 변경) 여기서 실패한다
— 추적표가 낡은 채로 화면에 계속 뜨는 일이 없다.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from risk_lib.datamodel import catalog as cat
from risk_lib.ui_studio.req_trace import (
    STATUSES, TRACE, build_trace, coverage,
)

TESTS_DIR = Path(__file__).parent
_APP_SRC = (Path(__file__).parent.parent
            / "risk_lib/ui_studio/app.py").read_text(encoding="utf-8")
_TEST_SRC = "\n".join(p.read_text(encoding="utf-8")
                      for p in TESTS_DIR.glob("test_*.py"))
_TABLES = {sp.name for sp in cat.ALL_TABLES}


def test_register_has_all_131_requirements():
    rows = build_trace()
    assert len(rows) == 131
    assert len({r["id"] for r in rows}) == 131


def test_every_mapped_id_exists_in_the_register():
    """레지스터에 없는 ID 에 매핑을 달면 오타다 — 커버리지가 조용히 샌다."""
    ids = {r["id"] for r in build_trace()}
    ghost = set(TRACE) - ids
    assert not ghost, f"레지스터에 없는 요건 ID: {sorted(ghost)}"


def test_status_requires_evidence():
    """반영·부분은 증빙 1건 이상 — 증빙 없는 반영 표시는 주장일 뿐이다."""
    for r in build_trace():
        assert r["status"] in STATUSES, r["id"]
        if r["status"] in ("반영", "부분"):
            assert r["evidence"], f"{r['id']} — 증빙 없이 '{r['status']}' 표시"
        else:
            assert not r["evidence"], f"{r['id']} — 미반영인데 증빙이 있다"


def test_every_evidence_reference_exists():
    dead = []
    for r in build_trace():
        for e in r["evidence"]:
            k, ref = e["kind"], e["ref"]
            if k == "module":
                try:
                    importlib.import_module(ref)
                except ImportError:
                    dead.append(f"{r['id']}: module {ref}")
            elif k == "table":
                if ref not in _TABLES:
                    dead.append(f"{r['id']}: table {ref}")
            elif k == "screen":
                if ref not in _APP_SRC:
                    dead.append(f"{r['id']}: screen '{ref}'")
            elif k == "test":
                if f"def {ref}(" not in _TEST_SRC:
                    dead.append(f"{r['id']}: test {ref}")
            else:
                dead.append(f"{r['id']}: 알 수 없는 kind {k}")
    assert not dead, "죽은 증빙 참조:\n  " + "\n  ".join(dead)


def test_coverage_sums_to_register_size():
    c = coverage()
    assert c["반영"] + c["부분"] + c["미반영"] == c["n"] == 131
    # 미반영이 0이면 의심하라 — 131건 전부를 이 하네스가 구현했을 리 없다.
    assert c["미반영"] > 0, "미반영 0건 — 커버리지가 재고조사가 아니라 자랑이 됐다"


def test_every_requirement_is_either_traced_or_declared_unassessed():
    """131건 중 어느 것도 조용히 '미반영'으로 떨어지지 않는다.

    예전에는 `TRACE.get(rid, ("미반영", (), ""))`가 매핑에 없는 요건을 전부
    미반영으로 만들었다. 그러면 **판정해서 미반영**과 **아무도 안 봐서 미반영**이
    같은 칸에 들어간다. 실제로 구현이 멀쩡히 있는 9건이 그렇게 묻혀 있었고
    (DAT-006·PLT-015·SEC-PRC-001·SEC-PRC-004·BNK-ST-006·BNK-CRM-001 등),
    그중 DAT-006은 같은 저장소의 `rynta.py`가 이미 covered로 적고 있었다.

    커버리지는 재고조사다. 재고를 세지 않은 칸이 '없음'으로 보고되면 재고조사가
    아니다.
    """
    from risk_lib.regulatory.requirements_v960 import REQUIREMENTS
    from risk_lib.ui_studio.req_trace import UNASSESSED

    ids = {r[0] for r in REQUIREMENTS}
    judged = set(TRACE) | set(UNASSESSED)
    assert not (ids - judged), (
        f"판정도 사유도 없는 요건 {sorted(ids - judged)} — TRACE에 넣거나 "
        f"UNASSESSED에 사유를 적어라")
    assert not (judged - ids), f"레지스터에 없는 id: {sorted(judged - ids)}"
    assert not (set(TRACE) & set(UNASSESSED)), (
        f"TRACE와 UNASSESSED에 동시에 있는 id: "
        f"{sorted(set(TRACE) & set(UNASSESSED))}")


def test_unassessed_reasons_are_specific():
    """사유가 비어 있거나 서로 복사된 문구면 목록이 다시 무의미해진다."""
    from risk_lib.ui_studio.req_trace import UNASSESSED
    import collections

    blank = [k for k, v in UNASSESSED.items() if len(v.strip()) < 10]
    assert not blank, f"사유가 너무 짧다: {blank}"
    dup = [r for r, n in collections.Counter(UNASSESSED.values()).items() if n > 1]
    assert not dup, f"여러 요건이 같은 사유를 복사해 쓴다: {dup}"


def test_trace_does_not_contradict_the_rynta_coverage_table():
    """같은 저장소의 추적표 둘이 정반대를 말하지 않는다.

    `req_trace.TRACE`와 `risk_lib.rynta`의 커버리지 표가 각각 독립으로 관리되고
    있었고, DAT-006에서 한쪽은 '미반영' 다른 쪽은 'covered'였다. 어느 쪽이 결재
    근거인지 물어야 하는 상태였다 — 두 화면이 같은 원장을 각자 그리는 것과 같은
    결함이다.
    """
    from risk_lib import rynta
    from risk_lib.ui_studio.req_trace import UNASSESSED

    cov = getattr(rynta, "COVERAGE", None)
    if cov is None:
        pytest.skip("rynta에 커버리지 표가 없다")

    bad = []
    for rid, entry in cov.items():
        state = getattr(entry, "status", None)
        if state != "covered":
            continue
        if rid in UNASSESSED:
            bad.append(f"{rid}: rynta=covered vs req_trace=판정보류")
        elif rid in TRACE and TRACE[rid][0] == "미반영":
            bad.append(f"{rid}: rynta=covered vs req_trace=미반영")
    assert not bad, "두 추적표가 어긋난다:\n  " + "\n  ".join(bad)
