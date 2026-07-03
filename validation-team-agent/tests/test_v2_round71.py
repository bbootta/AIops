"""Round 71 — 인쇄 미디어 쿼리 + sticky TOC + 잔여 차트 토큰 정비."""

from __future__ import annotations

import re

import pytest


# ---------- _inject_toc 단위 ----------

def test_inject_toc_skips_short_pages():
    from tools.report_pack import _inject_toc

    body = "<h2>하나</h2><p>x</p><h2>둘</h2>"
    assert _inject_toc(body) == body  # h2 < 3 → 변경 없음


def test_inject_toc_adds_nav_and_ids():
    from tools.report_pack import _inject_toc

    body = "<h2>요약</h2><h2>상세 분석</h2><h2>해석</h2>"
    out = _inject_toc(body)
    assert '<nav class="toc">' in out
    assert out.count("<h2 id=") == 3
    # anchor 3개
    assert out.count('href="#') == 3


def test_inject_toc_unique_ids_for_duplicate_heads():
    from tools.report_pack import _inject_toc

    body = "<h2>결과</h2><h2>결과</h2><h2>결과</h2>"
    out = _inject_toc(body)
    ids = re.findall(r'<h2 id="([^"]+)"', out)
    assert len(set(ids)) == 3  # 중복 없이 고유


def test_slugify_korean_preserved():
    from tools.report_pack import _slugify

    used: set[str] = set()
    slug = _slugify("자본 buffer 분해", used)
    assert "자본" in slug
    assert " " not in slug


# ---------- 팩 통합 ----------

@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r71")
    demo = run_demo(800, True, 42, out / "logs")
    request = build_request(800, stress=True, seed=42)
    prov = build_provenance(request, n=800, seed=42, stress=True)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_long_pages_have_sticky_toc(pack):
    out, _ = pack
    for name in ("capital_icaap.html", "alm.html", "executive.html"):
        text = (out / name).read_text(encoding="utf-8")
        assert '<nav class="toc">' in text, name
        assert "<h2 id=" in text


def test_toc_css_is_sticky_and_no_js(pack):
    out, _ = pack
    text = (out / "index.html").read_text(encoding="utf-8")
    assert "position: sticky" in text
    assert "<script" not in text


def test_print_media_query_present(pack):
    out, _ = pack
    text = (out / "executive.html").read_text(encoding="utf-8")
    assert "@media print" in text
    assert "size: A4" in text
    assert "print-color-adjust: exact" in text
    # 표/차트/카드 페이지 넘김 방지
    assert "break-inside: avoid" in text


def test_print_hides_toc_and_crumb(pack):
    out, _ = pack
    text = (out / "index.html").read_text(encoding="utf-8")
    assert "nav.toc { display: none; }" in text
    assert ".crumb { display: none; }" in text


def test_heatmap_uses_ink_tokens(pack):
    from tools.svg_charts import INK, INK_MUTED, heatmap

    svg = heatmap([("자본", "fail", "CET1 미달", "capital.html")], title="t")
    assert INK in svg          # 부문 라벨 (series 색 아님)
    assert INK_MUTED in svg    # detail
    # 구 hex 잔존 금지
    for old in ("#f8f9fa", "#dee2e6", "#37474f"):
        assert old not in svg


def test_kpi_strip_uses_ink_tokens():
    from tools.svg_charts import GRID, INK, INK_MUTED, kpi_card_strip

    svg = kpi_card_strip([("LCR", "1.30", "ok")])
    assert INK in svg
    assert INK_MUTED in svg
    assert GRID in svg  # 카드 테두리
    for old in ("#546e7a", "#212529"):
        assert old not in svg


def test_donut_uses_ink_tokens():
    from tools.svg_charts import INK, INK_MUTED, status_donut

    svg = status_donut({"ok": 20, "fail": 3}, title="t")
    assert INK in svg
    assert INK_MUTED in svg


def test_anchor_links_do_not_break_link_integrity(pack):
    """anchor(#) 링크는 파일 링크 무결성 검사에서 제외되어도 페이지 내 유효."""
    out, _ = pack
    text = (out / "capital_icaap.html").read_text(encoding="utf-8")
    anchors = re.findall(r'href="#([^"]+)"', text)
    ids = set(re.findall(r'<h2 id="([^"]+)"', text))
    for a in anchors:
        assert a in ids, f"TOC anchor 미해결: #{a}"


def test_all_pages_remain_self_contained(pack):
    out, files = pack
    for p in files:
        text = p.read_text(encoding="utf-8")
        assert "<script" not in text
        assert "https://" not in text
        assert "[DRAFT" in text
        assert "Reproducibility" in text
