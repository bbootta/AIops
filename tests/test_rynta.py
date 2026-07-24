"""RYNTA v9.0 요건 매니페스트 · 커버리지 추적 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from risk_lib import rynta

AGENTS = Path(__file__).resolve().parent.parent / ".claude" / "agents"


# ----- 매니페스트 무결성 ---------------------------------------------------

def test_manifest_has_126_requirements():
    reqs = rynta.load_requirements()
    assert len(reqs) == 126
    ids = [r["id"] for r in reqs]
    assert len(set(ids)) == 126, "요건 ID 중복"


def test_manifest_records_source_integrity():
    mf = rynta.load_manifest()
    assert mf["source_file"] == "RYNTA_RiskOps_v9.0_navigation.xlsx"
    # 원본 xlsx의 SHA-256 (SHA256SUMS_v9.0.txt 대조 완료값)
    assert mf["source_sha256"] == (
        "c3be97f9c110b4963dc48819083fdd776f049f40cf4f4952f2a814a8065cbcb6")
    assert len(mf["manifest_fingerprint_v8_4"]) == 64


def test_every_requirement_has_core_fields():
    for r in rynta.load_requirements():
        for field in ("id", "title", "priority", "stage", "type", "product"):
            assert r[field], f"{r['id']}: {field} 누락"


# ----- 분류체계 -------------------------------------------------------------

def test_twelve_products_map_into_six_suites():
    assert len(rynta.PRODUCTS) == 12
    assert len(rynta.SUITES) == 6
    assert {p.suite for p in rynta.PRODUCTS} == set(rynta.SUITES)


def test_every_requirement_product_is_canonical():
    known = {p.id for p in rynta.PRODUCTS}
    unknown = {r["product"] for r in rynta.load_requirements()} - known
    assert not unknown, f"미등록 Product ID: {unknown}"


# ----- 커버리지 -------------------------------------------------------------

def test_coverage_covers_every_requirement():
    df = rynta.coverage_frame()
    assert len(df) == 126
    assert df["status"].isin(
        {"covered", "partial", "platform", "backlog"}).all()


def test_partial_and_backlog_declare_a_gap():
    """미구현·부분구현은 gap을 반드시 명시 — 낙관적 표기 방지 (AIMS_POLICY §8-4)."""
    df = rynta.coverage_frame()
    missing = df[(df["status"].isin(["partial", "backlog"])) &
                 (df["gap"].str.strip() == "")]
    assert missing.empty, f"gap 미기재: {list(missing['id'])}"


def test_covered_requirements_cite_evidence():
    """구현 표기 요건은 모듈과 증빙 페이지를 모두 제시해야 한다."""
    df = rynta.coverage_frame()
    cov = df[df["status"] == "covered"]
    assert not cov.empty
    weak = cov[(cov["modules"].str.strip() == "") |
               (cov["pages"].str.strip() == "")]
    assert weak.empty, f"증빙 없는 covered: {list(weak['id'])}"


def test_covered_pages_exist_in_page_registry():
    """증빙으로 인용한 ops 페이지가 실제로 존재해야 한다."""
    import re
    from risk_lib.page_registry import PAGES
    known = {p.filename for p in PAGES}
    df = rynta.coverage_frame()
    bad = []
    for _, row in df.iterrows():
        for ref in re.findall(r"ops/([\w.]+)", row["pages"]):
            fn = ref if ref.endswith(".html") else ref + ".html"
            if fn not in known:
                bad.append((row["id"], fn))
    assert not bad, f"registry에 없는 증빙 페이지: {bad}"


def test_in_scope_ratio_excludes_platform():
    df = rynta.coverage_frame()
    scoped = df[df["status"] != "platform"]
    expected = (scoped["status"] == "covered").sum() / len(scoped)
    assert rynta.in_scope_ratio() == pytest.approx(expected)
    assert 0.0 < rynta.in_scope_ratio() < 1.0


# ----- 가드레일이 에이전트 정의에 실제로 반영됐는지 --------------------------

def test_all_agents_declare_rynta_product_and_guardrails():
    mds = list(AGENTS.glob("*.md"))
    assert len(mds) >= 11
    for p in mds:
        txt = p.read_text(encoding="utf-8")
        assert "RYNTA v9.0 정합" in txt, f"{p.name}: RYNTA 섹션 없음"
        assert "자동확정 금지" in txt, f"{p.name}: 자동확정 금지 목록 없음"
        assert "PRD-" in txt, f"{p.name}: Canonical Product 미표기"


def test_policy_documents_guardrails():
    pol = (Path(__file__).resolve().parent.parent / "AIMS_POLICY.md").read_text(
        encoding="utf-8")
    assert "RYNTA v9.0 정합" in pol
    for item in rynta.NO_AUTO_DECISION:
        assert item in pol, f"정책에 자동확정 금지 항목 누락: {item}"


# ----- 보고서 페이지 --------------------------------------------------------

def test_coverage_page_renders_with_honest_status(result):
    from risk_lib.ops_pages.governance import page_rynta_coverage
    html = page_rynta_coverage(result)
    assert "RYNTA 요건 커버리지" in html
    assert "AI 자동확정 금지" in html
    summ = rynta.coverage_summary()
    # 미구현 건수가 페이지에 그대로 노출되어야 한다
    assert f"{summ.get('backlog', 0)}건" in html
    assert rynta.load_manifest()["source_sha256"] in html


def test_coverage_page_registered():
    from risk_lib.page_registry import PAGES
    specs = [p for p in PAGES if p.filename == "63_rynta_coverage.html"]
    assert len(specs) == 1
    assert callable(specs[0].resolve())
