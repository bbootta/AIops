"""AI 리스크 업무요건 → 적합성검증 기준 항목 원장.

원장이 생성물과 같은지, 근거가 실재하는지, 원문 지문(문서 세트 manifest 대조)·
요건·규칙 문장·근거원장이 원문과 같은지를 고정한다. 음성 통제: 근거 파일 이름·
지문·규칙 문장을 바꾸면 잡혀야 한다.
"""

from __future__ import annotations

import copy
from collections import Counter
from pathlib import Path

from tools import ai_risk_criteria as ac
from tools import gen_ai_risk_criteria as gen

ROOT = Path(__file__).resolve().parent.parent


def _data():
    return ac.load()


def test_catalog_is_exactly_what_the_generator_builds():
    assert _data() == gen.build(), "원장을 손으로 고치지 말고 gen_ai_risk_criteria 를 다시 돌려라"


def test_no_violations():
    assert ac.violations(_data()) == []


def test_all_76_requirements_are_present_with_their_acceptance_ids():
    d = _data()
    ids = [c["req_id"] for c in d["criteria"]]
    assert len(ids) == 76 and len(set(ids)) == 76
    assert all(c["test_id"] == "AC-" + c["req_id"] for c in d["criteria"])
    assert Counter(c["priority"] for c in d["criteria"]) == {"P0": 70, "P1": 6}
    assert len(d["norms"]) == 27
    assert {n["source_id"] for n in d["norms"] if n["binding"]} == {"K02", "K03", "K04", "K05"}


def test_document_set_declares_what_it_did_not_verify():
    """문서 세트가 미수행이라고 밝힌 검증은 원장에 그대로 남아야 한다."""
    v = _data()["document_verification"]
    assert v["browser_visual_review"].startswith("NOT_RUN")
    assert v["database_runtime"] == "NOT_RUN" and v["bank_production_acceptance"] == "NOT_RUN"


def test_every_requirement_has_a_criterion_and_a_lens():
    for c in _data()["criteria"]:
        assert c["criterion"].endswith("가"), c["req_id"]
        assert c["lens"] and set(c["lens"]) <= set(gen.LENSES)
        assert c["section"] == "10" and c["related_sections"]


def test_automation_mix_and_evidence_scope():
    d = _data()
    auto = Counter(c["automation"] for c in d["criteria"])
    assert auto["automated"] >= 35 and auto["manual"] >= 25 and auto["out_of_scope"] >= 5
    for c in d["criteria"]:
        if c["automation"] != "automated":
            assert c["note"] and not c["evidence"], c["req_id"]
        else:
            assert c["evidence"], c["req_id"]
            for p in c["evidence"]:
                assert (ROOT / p).exists(), p


def test_generative_ai_evaluation_is_left_manual():
    """생성형 평가·공정성(07장)은 하니스에 통제가 없으므로 자동으로 주장하지 않는다."""
    d = _data()
    assert all(c["automation"] == "manual" for c in d["criteria"] if c["chapter"] == "07")


def test_no_long_dashes_in_generated_sentences():
    for c in _data()["criteria"]:
        for k in ("criterion", "note"):
            assert "\u2014" not in c[k] and "\u2013" not in c[k], (c["req_id"], k)


# ---- 음성 통제

def test_missing_evidence_file_is_a_violation():
    d = copy.deepcopy(_data())
    target = next(c for c in d["criteria"] if c["automation"] == "automated")
    target["evidence"][0] = "tools/does_not_exist.py"
    assert any("근거 파일 없음" in v for v in ac.violations(d))


def test_source_digest_drift_is_a_violation():
    d = copy.deepcopy(_data())
    d["sources"]["register"]["sha256"] = "0" * 64
    assert any("원문 지문 불일치" in v for v in ac.violations(d))


def test_rule_drift_and_dropped_requirement_are_violations():
    d = copy.deepcopy(_data())
    d["criteria"][0]["rule"] = "다른 규칙"
    assert any("rule 가 원문과 다르다" in v for v in ac.violations(d))
    d = copy.deepcopy(_data())
    d["criteria"].pop()
    assert any("원문 요건이 원장에 없다" in v for v in ac.violations(d))


def test_pinned_copies_match_the_document_set_manifest():
    import hashlib
    import json
    manifest = json.loads(gen.source_path("manifest").read_text(encoding="utf-8"))
    by_name = {f["file"]: f["sha256"] for f in manifest["files"]}
    assert hashlib.sha256(gen.source_path("manual").read_bytes()).hexdigest() == by_name["AI_Risk_Practitioner_Manual.html"]
    assert hashlib.sha256(gen.source_path("register").read_bytes()).hexdigest() == by_name["requirements.json"]


def test_cli_verify_report_norms(capsys):
    assert ac.main(["verify"]) == 0
    assert "AI 리스크 기준 항목 정상" in capsys.readouterr().out
    assert ac.main(["report"]) == 0
    assert ac.main(["norms"]) == 0
    assert ac.main(["list", "--chapter", "06"]) == 0
