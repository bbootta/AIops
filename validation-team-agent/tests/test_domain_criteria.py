"""도메인 업무요건 → 적합성검증 기준 항목 원장 검사.

근거 실재성이 강제되는지, 그리고 그 검사가 **실패할 수 있는지**를 함께 고정한다
(적대적 검증 ADV-CALC-06: 항상 참인 검증은 통제가 아니다).
"""

from __future__ import annotations

import json

import pytest

from tools import domain_criteria as dc
from tools import gen_domain_criteria as gen


@pytest.fixture(scope="module")
def data():
    return dc.load()


def test_catalog_covers_the_whole_register(data):
    ids = [c["req_id"] for c in data["criteria"]]
    assert len(ids) == len(gen.REGISTER)
    assert set(ids) == {r[0] for r in gen.REGISTER}
    assert len(set(ids)) == len(ids)


def test_committed_catalog_matches_the_generator(data):
    """손으로 고치면 깨진다: 원문이 바뀌면 생성기를 다시 돌린다."""
    assert data == json.loads(json.dumps(gen.build(), ensure_ascii=False))


def test_no_violations(data):
    assert dc.violations(data) == []


def test_evidence_files_exist(data):
    for c in data["criteria"]:
        if c["automation"] == "automated":
            assert c["evidence"], c["req_id"]
            for p in c["evidence"]:
                assert (dc.ROOT / p).exists(), f'{c["req_id"]} → {p}'


def test_manual_and_out_of_scope_carry_a_reason_and_claim_nothing(data):
    for c in data["criteria"]:
        if c["automation"] in ("manual", "out_of_scope"):
            assert c["note"], c["req_id"]
            assert c["evidence"] == [], c["req_id"]


def test_every_criterion_has_a_section_and_a_lens(data):
    for c in data["criteria"]:
        assert c["section"] in data["sections"], c["req_id"]
        assert c["lens"], c["req_id"]
        for l in c["lens"]:
            assert l in data["lenses"], c["req_id"]
        assert c["criterion"].strip(), c["req_id"]


def test_securities_requirements_are_declared_out_of_scope(data):
    """본 하니스의 검증 범위는 은행 8부문이다 (CLAUDE.md §2)."""
    sec = [c for c in data["criteria"] if c["scope"] == "증권"]
    assert sec
    assert all(c["automation"] == "out_of_scope" for c in sec)


# ---- 통제가 실패할 수 있는가 (음성 통제)

def test_missing_evidence_is_detected(data):
    broken = json.loads(json.dumps(data, ensure_ascii=False))
    target = next(c for c in broken["criteria"] if c["automation"] == "automated")
    target["evidence"] = ["harness/파일이_없다.json"]
    bad = dc.violations(broken)
    assert any("근거 파일 없음" in b for b in bad)


def test_automated_without_evidence_is_detected(data):
    broken = json.loads(json.dumps(data, ensure_ascii=False))
    target = next(c for c in broken["criteria"] if c["automation"] == "manual")
    target["automation"] = "automated"
    target["evidence"] = []
    bad = dc.violations(broken)
    assert any("automated 인데 근거가 0건" in b for b in bad)


def test_unexplained_gap_is_detected(data):
    broken = json.loads(json.dumps(data, ensure_ascii=False))
    target = next(c for c in broken["criteria"] if c["automation"] == "manual")
    target["note"] = ""
    bad = dc.violations(broken)
    assert any("사유(note)가 비어 있다" in b for b in bad)
