"""기후리스크 업무요건 → 적합성검증 기준 항목 원장.

원장이 생성물과 같은지, 근거가 실재하는지, 원문 지문·요건·제목·인수시험·결정이
원문과 같은지를 고정한다. 음성 통제: 근거 파일 이름·지문·제목을 바꾸면 잡혀야 한다.
"""

from __future__ import annotations

import copy
from collections import Counter
from pathlib import Path

from tools import climate_criteria as cc
from tools import gen_climate_criteria as gen

ROOT = Path(__file__).resolve().parent.parent


def _data():
    return cc.load()


def test_catalog_is_exactly_what_the_generator_builds():
    assert _data() == gen.build(), "원장을 손으로 고치지 말고 gen_climate_criteria 를 다시 돌려라"


def test_no_violations():
    assert cc.violations(_data()) == []


def test_all_72_requirements_and_their_acceptance_tests_are_present():
    d = _data()
    ids = [c["req_id"] for c in d["criteria"]]
    assert len(ids) == 72 and len(set(ids)) == 72
    assert {c["acceptance_test"] for c in d["criteria"]} == {a["at_id"] for a in d["acceptance_tests"]}
    assert all(c["priority"] == "P0" for c in d["criteria"])
    assert len(d["decisions"]) == 20 and [x["dec_id"] for x in d["decisions"]][0] == "DEC-01"
    assert len(d["norms"]) == 13
    assert sum(1 for n in d["norms"] if n["binding"]) == 2, "구속 근거는 규정 제30조·세칙 별표 3의9·19 뿐"


def test_every_requirement_has_a_criterion_and_a_lens():
    for c in _data()["criteria"]:
        assert c["criterion"].endswith("가"), c["req_id"]
        assert c["lens"] and set(c["lens"]) <= set(gen.LENSES)
        assert c["section"] == "09" and c["related_sections"]


def test_automation_mix_and_evidence_scope_notes():
    d = _data()
    auto = Counter(c["automation"] for c in d["criteria"])
    assert auto["automated"] >= 30 and auto["manual"] >= 25 and auto["out_of_scope"] >= 8
    for c in d["criteria"]:
        if c["automation"] != "automated":
            assert c["note"] and not c["evidence"], c["req_id"]
        else:
            assert c["evidence"], c["req_id"]
            for p in c["evidence"]:
                assert (ROOT / p).exists(), p


def test_chapter_14_validation_requirements_are_automated():
    d = _data()
    ch14 = {c["req_id"]: c["automation"] for c in d["criteria"] if c["chapter"] == "14"}
    assert ch14["CLR-14-01"] == "automated" and ch14["CLR-14-04"] == "automated"
    assert ch14["CLR-14-02"] == "manual", "사건 귀속·비교집단 설계는 사람 몫으로 남긴다"


def test_no_long_dashes_in_generated_sentences():
    d = _data()
    for c in d["criteria"]:
        for k in ("criterion", "note"):
            assert "\u2014" not in c[k] and "\u2013" not in c[k], (c["req_id"], k)


# ---- 음성 통제

def test_missing_evidence_file_is_a_violation():
    d = copy.deepcopy(_data())
    target = next(c for c in d["criteria"] if c["automation"] == "automated")
    target["evidence"][0] = "tools/does_not_exist.py"
    assert any("근거 파일 없음" in v for v in cc.violations(d))


def test_source_digest_drift_is_a_violation():
    d = copy.deepcopy(_data())
    d["sources"]["detail"]["sha256"] = "0" * 64
    assert any("원문 지문 불일치" in v for v in cc.violations(d))


def test_title_drift_and_dropped_requirement_are_violations():
    d = copy.deepcopy(_data())
    d["criteria"][0]["title"] = "다른 제목"
    assert any("제목이 원문과 다르다" in v for v in cc.violations(d))
    d = copy.deepcopy(_data())
    d["criteria"].pop()
    assert any("원문 요건이 원장에 없다" in v for v in cc.violations(d))


def test_source_parsers_are_deterministic_against_the_pinned_html():
    raw = gen.source_path("detail").read_text(encoding="utf-8")
    reqs = gen.parse_requirements(raw)
    assert [r["req_id"] for r in reqs][:2] == ["CLR-01-01", "CLR-01-02"]
    assert reqs[0]["title"] == "범위·목적·결과 사용범위"
    assert reqs[0]["sources"] == ["S01", "S02"]
    assert len(gen.parse_acceptance_tests(raw)) == 72


def test_cli_verify_and_report(capsys):
    assert cc.main(["verify"]) == 0
    assert "기후리스크 기준 항목 정상" in capsys.readouterr().out
    assert cc.main(["report"]) == 0
    assert cc.main(["decisions"]) == 0
