"""국내 감독규정 검증 항목 원장 검사.

인용이 원문에서 해석되는지, 그리고 **그 검사가 실패할 수 있는지**를 함께
고정한다 (ADV-CALC-06). 원문 지문이 어긋나면 카탈로그가 낡았다는 뜻이다.
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
def lines():
    return gen.SOURCE.read_text(encoding="utf-8").splitlines()


def test_source_is_committed_and_pinned(data):
    src = dc.ROOT / data["source"]["path"]
    assert src.exists(), "근거 원문이 저장소에 있어야 인용을 대조할 수 있다"
    assert hashlib.sha256(src.read_bytes()).hexdigest() == data["source"]["sha256"]


def test_no_violations(data):
    assert dc.violations(data) == []


def test_every_citation_resolves_in_the_source(data, lines):
    for c in data["criteria"]:
        ln = gen.resolve(c["citation"], lines)
        assert ln is not None, c["citation"]
        assert ln == c["source_line"], c["citation"]
        assert gen.heading_of(ln, lines) == c["source_heading"], c["citation"]


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
    assert data["source"]["n_schedules"] == sum(
        1 for l in lines if l.startswith("## [별표"))
    assert data["source"]["n_article_headings"] == sum(
        1 for l in lines if l.startswith("##### 제"))


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
    broken = json.loads(json.dumps(data, ensure_ascii=False))
    broken["source"]["sha256"] = "0" * 64
    assert any("원문 지문 불일치" in b for b in dc.violations(broken))


def test_missing_evidence_is_detected(data):
    broken = json.loads(json.dumps(data, ensure_ascii=False))
    target = next(c for c in broken["criteria"] if c["automation"] == "automated")
    target["evidence"] = ["harness/없는파일.json"]
    assert any("근거 파일 없음" in b for b in dc.violations(broken))
