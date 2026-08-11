"""규제 기준 검증 항목 원장 검사: 기준 스택 3층(규정·세칙·바젤).

인용이 원문에서 해석되는지, 규정 임계와 하니스 임계가 어긋나면 드러나는지,
그리고 **그 검사들이 실패할 수 있는지**를 함께 고정한다 (ADV-CALC-06).
"""

from __future__ import annotations

import hashlib
import json

import pytest

from tools import gen_regulatory_criteria as gen
from tools import regulatory_criteria as dc


@pytest.fixture(scope="module")
def data():
    return dc.load()


@pytest.fixture(scope="module")
def lines(data):
    return dc._source_lines(data, dc.ROOT)


def test_all_sources_are_committed_and_pinned(data):
    assert set(data["sources"]) == {"규정", "세칙", "바젤"}
    for key, meta in data["sources"].items():
        src = dc.ROOT / meta["path"]
        assert src.exists(), f"[{key}] 근거 원문이 저장소에 있어야 인용을 대조할 수 있다"
        assert hashlib.sha256(src.read_bytes()).hexdigest() == meta["sha256"], key


def test_no_violations(data):
    assert dc.violations(data) == []


def test_every_citation_resolves_in_its_own_source(data, lines):
    for c in data["criteria"]:
        ln = gen.resolve(c["citation"], lines[c["source_key"]])
        assert ln is not None, (c["source_key"], c["citation"])
        assert ln == c["source_line"], c["citation"]
        assert gen.heading_of(ln, lines[c["source_key"]]) == c["source_heading"]


def test_committed_catalog_matches_the_generator(data):
    assert data == json.loads(json.dumps(gen.build(), ensure_ascii=False))


def test_automated_items_have_existing_evidence(data):
    for c in data["criteria"]:
        if c["automation"] == "automated":
            assert c["evidence"], c["rule_id"]
            for p in c["evidence"]:
                assert (dc.ROOT / p).exists(), f'{c["rule_id"]} → {p}'


def test_gaps_are_named_not_hidden(data):
    for c in data["criteria"]:
        if c["automation"] == "manual":
            assert c["note"], c["rule_id"]
            assert c["evidence"] == [], c["rule_id"]


def test_source_index_is_counted_not_asserted(data, lines):
    """별표·조문·Chapter 수는 원문에서 세서 쓴다: 손으로 적으면 낡는다."""
    import re
    for key, meta in data["sources"].items():
        ls = lines[key]
        if key == "바젤":
            assert meta["n_current_chapters"] == gen.count_current_chapters(ls)
            # 문서가 스스로 밝힌 현행 Chapter 수와 대사한다: 세는 범위가
            # 이름과 어긋나면 여기서 깨진다.
            assert "| Current Chapter | 124 |" in "\n".join(ls).replace(" |", " |")
            assert meta["n_current_chapters"] == 124
        else:
            assert meta["n_schedules"] == sum(1 for l in ls if l.startswith("## [별표"))
            assert meta["n_article_headings"] == sum(
                1 for l in ls if l.startswith("##### 제"))


# ---- 기준 스택 (국내 우선 · 모호하면 바젤)

def test_governing_is_derived_from_the_precedence_policy(data):
    """지배기준은 손으로 적지 않는다: 근거와 모호성에서 파생된다."""
    for c in data["criteria"]:
        assert c["governing"] == gen.governing_of(
            c["source_key"], c["ambiguous_domestic"]), c["rule_id"]
        assert c["governing"] in data["precedence"]["governing_values"]


def test_domestic_takes_precedence_over_basel(data):
    """국내 근거 항목은 국내가 지배한다: 바젤이 국내를 밀어내지 못한다."""
    for c in data["criteria"]:
        if c["source_key"] in ("규정", "세칙"):
            assert c["governing"] != "바젤", c["rule_id"]
            assert c["basis_level"] == "국내구속"


def test_basel_governs_only_where_domestic_is_silent(data):
    for c in data["criteria"]:
        if c["governing"] == "바젤":
            assert c["source_key"] == "바젤", c["rule_id"]
            assert c["basis_level"] == "국제권고"
            assert c["basel_ref"] == gen.basel_chapter(c["citation"])


def test_ambiguous_domestic_items_point_at_a_basel_chapter(data):
    """규칙 ③: 모호하면 바젤로 보충하되, 보충할 Chapter 가 실재해야 한다."""
    amb = [c for c in data["criteria"] if c["ambiguous_domestic"]]
    assert amb
    for c in amb:
        assert c["governing"] == "국내+바젤보충", c["rule_id"]
        assert c["basel_ref"], c["rule_id"]


def test_every_basel_ref_resolves_to_a_current_chapter(data, lines):
    for c in data["criteria"]:
        if c["basel_ref"]:
            assert gen.resolve(c["basel_ref"], lines["바젤"]) is not None, c["basel_ref"]


def test_basel_paragraph_citation_resolves_to_its_chapter(lines):
    """소스북은 Chapter 색인이라 paragraph 는 Chapter 로 절단해 해석한다."""
    assert gen.basel_chapter("CRE20.1") == "CRE20"
    assert gen.resolve("CRE20.1", lines["바젤"]) == gen.resolve("CRE20", lines["바젤"])


# ---- 계량 임계

def test_threshold_quotes_exist_in_the_source(data, lines):
    for t in data["thresholds"]:
        assert any(t["quote"] in l for l in lines[t["source_key"]]), t["key"]


def test_harness_thresholds_are_not_looser_than_the_regulation(data):
    """하니스 임계가 규정보다 느슨하면 규제 미달을 통과시킨다."""
    for t in data["thresholds"]:
        actual = gen.dig(
            json.loads((dc.ROOT / t["harness_file"]).read_text(encoding="utf-8")),
            t["harness_path"])
        assert actual is not None, t["key"]
        assert gen.compare(t["regulated_value"], actual, t["direction"]) != "looser", t["key"]


# ---- 통제가 실패할 수 있는가 (음성 통제)

def test_unresolvable_citation_is_detected(data):
    broken = json.loads(json.dumps(data, ensure_ascii=False))
    broken["criteria"][0]["citation"] = "별표 99의9"
    assert any("해석되지 않음" in b for b in dc.violations(broken))


def test_hand_edited_governing_is_detected(data):
    """'이건 바젤을 따른다'고 손으로 적으면 정책과 어긋나 잡힌다."""
    broken = json.loads(json.dumps(data, ensure_ascii=False))
    target = next(c for c in broken["criteria"] if c["governing"] == "국내")
    target["governing"] = "바젤"
    assert any("지배기준이 우선순위 정책과 다름" in b for b in dc.violations(broken))


def test_unresolvable_basel_ref_is_detected(data):
    broken = json.loads(json.dumps(data, ensure_ascii=False))
    target = next(c for c in broken["criteria"] if c["basel_ref"])
    target["basel_ref"] = "XXX99"
    assert any("대응 바젤 Chapter" in b for b in dc.violations(broken))


def test_wrong_line_is_detected(data):
    broken = json.loads(json.dumps(data, ensure_ascii=False))
    broken["criteria"][0]["source_line"] += 1
    assert any("기록 라인이 원문과 다름" in b for b in dc.violations(broken))


def test_stale_source_digest_is_detected(data):
    for key in data["sources"]:
        broken = json.loads(json.dumps(data, ensure_ascii=False))
        broken["sources"][key]["sha256"] = "0" * 64
        assert any("원문 지문 불일치" in b for b in dc.violations(broken)), key


def test_missing_evidence_is_detected(data):
    broken = json.loads(json.dumps(data, ensure_ascii=False))
    target = next(c for c in broken["criteria"] if c["automation"] == "automated")
    target["evidence"] = ["harness/없는파일.json"]
    assert any("근거 파일 없음" in b for b in dc.violations(broken))


def test_looser_harness_threshold_is_detected(data):
    """규정 최소보다 낮은 임계를 심으면 위반으로 잡혀야 한다."""
    broken = json.loads(json.dumps(data, ensure_ascii=False))
    t = next(x for x in broken["thresholds"] if x["direction"] == "min")
    t["harness_value"] = t["regulated_value"] / 2
    t["status"] = "looser"
    bad = dc.violations(broken)
    assert any("하니스 값이 기록과 다름" in b for b in bad)


def test_fabricated_quote_is_detected(data):
    broken = json.loads(json.dumps(data, ensure_ascii=False))
    broken["thresholds"][0]["quote"] = "이 문장은 규정에 없다"
    assert any("원문 발췌가" in b for b in dc.violations(broken))


def test_governing_of_semantics():
    assert gen.governing_of("규정", False) == "국내"
    assert gen.governing_of("세칙", False) == "국내"
    assert gen.governing_of("세칙", True) == "국내+바젤보충"
    assert gen.governing_of("바젤", False) == "바젤"


def test_compare_semantics():
    assert gen.compare(0.045, 0.045, "min") == "ok"
    assert gen.compare(0.045, 0.050, "min") == "stricter"
    assert gen.compare(0.045, 0.040, "min") == "looser"
    assert gen.compare(0.25, 0.20, "max") == "stricter"
    assert gen.compare(0.25, 0.30, "max") == "looser"
    assert gen.compare(0.25, None, "max") == "missing"
