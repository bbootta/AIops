"""AI 리스크관리 요건 추적(BR 76건), 증빙 없는 반영 표시가 불가능하게 고정한다.

tests/test_req_trace.py 와 같은 규칙을 기후 레지스터에 적용한다.

    module → import 가능해야 한다
    table  → 정규 카탈로그에 있어야 한다
    screen → 화면 소스(app.py)에 그 문자열이 있어야 한다
    test   → tests/ 아래에 그 테스트 함수가 있어야 한다

한 가지가 더 있다. 해설서가 정한 엔티티 테이블 43장은 이 하네스의
카탈로그에 아직 없다. 그 사실을 화면이 세어 보여 주므로, 카탈로그에 등재되는
날 화면 숫자도 같이 움직여야 한다(고정값 금지).
"""

from __future__ import annotations

import collections
import importlib
from pathlib import Path

from risk_lib.datamodel import catalog as cat
from risk_lib.regulatory import requirements_air as reg
from risk_lib.ui_studio.req_trace_air import (
    STATUSES, TRACE, UNASSESSED, build_trace, coverage,
)

TESTS_DIR = Path(__file__).parent
_APP_SRC = (TESTS_DIR.parent / "risk_lib/ui_studio/app.py").read_text(encoding="utf-8")
_TEST_SRC = "\n".join(p.read_text(encoding="utf-8")
                      for p in TESTS_DIR.glob("test_*.py"))
_TABLES = {sp.name for sp in cat.ALL_TABLES}


def test_register_has_all_76_requirements():
    rows = build_trace()
    assert len(rows) == 76
    assert len({r["id"] for r in rows}) == 76
    # 요건마다 인수시험 하나가 붙는다. 우선순위는 전건 P0 다.
    assert {r["n_ac"] for r in rows} == {1}
    assert {r["priority"] for r in rows} == {"P0", "P1"}
    assert all(r["area"] == reg.CHAPTER_OF[r["id"]] for r in rows)


def test_register_carries_the_package_fingerprints():
    """세트(zip)·요건 원장·개요·해설서·SQL·OpenAPI 의 SHA-256 이 레지스터에 있어야
    어느 판인지 재확인된다."""
    roles = [r for r, _, _ in reg.SOURCES]
    assert roles == ["package", "register", "overview", "manual", "schema", "openapi"]
    for _, title, sha in reg.SOURCES:
        assert title and len(sha) == 64
    assert reg.SOURCE_SHA256 == reg.SOURCES[3][2]
    assert len(reg.CHAPTERS) == 17
    assert set(reg.CHAPTER_OF.values()) == {no for no, _ in reg.CHAPTERS}
    assert set(reg.CHAPTER_OF) == {r[0] for r in reg.REQUIREMENTS}
    assert reg.N_API_PATHS == 32


def test_every_mapped_id_exists_in_the_register():
    ids = {r["id"] for r in build_trace()}
    ghost = set(TRACE) - ids
    assert not ghost, f"레지스터에 없는 요건 ID: {sorted(ghost)}"


def test_status_requires_evidence():
    for r in build_trace():
        assert r["status"] in STATUSES, r["id"]
        if r["status"] in ("반영", "부분"):
            assert r["evidence"], f"{r['id']}: 증빙 없이 '{r['status']}' 표시"
            assert r["note"], f"{r['id']}: 부분이면 무엇이 빠졌는지 note 에 적어야 한다"
        else:
            assert not r["evidence"], f"{r['id']}: 미반영인데 증빙이 있다"


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
    assert c["반영"] + c["부분"] + c["미반영"] == c["n"] == 76
    assert c["미반영"] > 0, "미반영 0건, 커버리지가 재고조사가 아니라 자랑이 됐다"


def test_every_requirement_is_either_traced_or_declared_unassessed():
    ids = {r[0] for r in reg.REQUIREMENTS}
    judged = set(TRACE) | set(UNASSESSED)
    assert not (ids - judged), f"판정도 사유도 없는 요건 {sorted(ids - judged)}"
    assert not (judged - ids), f"레지스터에 없는 id: {sorted(judged - ids)}"
    assert not (set(TRACE) & set(UNASSESSED))


def test_unassessed_reasons_are_specific():
    blank = [k for k, v in UNASSESSED.items() if len(v.strip()) < 10]
    assert not blank, f"사유가 너무 짧다: {blank}"
    dup = [r for r, n in collections.Counter(UNASSESSED.values()).items() if n > 1]
    assert not dup, f"여러 요건이 같은 사유를 복사해 쓴다: {dup}"


def test_ledger_registration_count_is_read_from_the_catalog():
    """해설서 엔티티 테이블의 등재 수는 카탈로그에서 센다. 등재하면 화면 숫자가 따라 움직인다."""
    c = coverage()
    assert c["n_tables"] == len(reg.TABLES) == 43
    assert c["n_tables_registered"] == sum(1 for n, _ in reg.TABLES if n in _TABLES)
    # 등재된 원장이 생기면 그 원장을 증빙으로 든 요건이 있어야 한다.
    registered = {n for n, _ in reg.TABLES if n in _TABLES}
    cited = {e["ref"] for r in build_trace() for e in r["evidence"] if e["kind"] == "table"}
    assert not (registered - cited), f"등재됐는데 어느 요건도 증빙으로 들지 않은 원장: {sorted(registered - cited)}"


def test_fully_implemented_items_are_the_deterministic_calculation_ones():
    """'반영'은 이 하네스가 원래 하던 일(결정론 계산 고정·대사·제출 묶음)에만 붙는다.
    언어모형 운영을 전제한 요건에 '반영'이 붙으면 증빙이 아니라 주장이다."""
    done = {r["id"] for r in build_trace() if r["status"] == "반영"}
    assert done == {"BR-061", "BR-062", "BR-064"}
