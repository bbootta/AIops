"""국내 감독규정 검증 항목 원장 검사 — 근거 2층(규정·세칙).

인용이 원문에서 해석되는지, 규정 임계와 하니스 임계가 어긋나면 드러나는지,
그리고 **그 검사들이 실패할 수 있는지**를 함께 고정한다 (ADV-CALC-06).
"""

from __future__ import annotations

import hashlib
import json

import pytest

from tools import domestic_criteria as dc
from tools import gen_domestic_criteria as gen


@pytest.fixture(scope="module")
def data():
    return dc.load()


@pytest.fixture(scope="module")
def lines(data):
    return dc._source_lines(data, dc.ROOT)


def test_both_sources_are_committed_and_pinned(data):
    assert set(data["sources"]) == {"규정", "세칙"}
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
    """별표·조문 수는 원문에서 세서 쓴다 — 손으로 적으면 낡는다."""
    for key, meta in data["sources"].items():
        ls = lines[key]
        assert meta["n_schedules"] == sum(1 for l in ls if l.startswith("## [별표"))
        assert meta["n_article_headings"] == sum(1 for l in ls if l.startswith("##### 제"))


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


def test_compare_semantics():
    assert gen.compare(0.045, 0.045, "min") == "ok"
    assert gen.compare(0.045, 0.050, "min") == "stricter"
    assert gen.compare(0.045, 0.040, "min") == "looser"
    assert gen.compare(0.25, 0.20, "max") == "stricter"
    assert gen.compare(0.25, 0.30, "max") == "looser"
    assert gen.compare(0.25, None, "max") == "missing"
