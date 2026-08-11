"""Round 69 — 보고서 디자인 시스템 (CSS 토큰 / 타이포그래피 / 컴포넌트 polish)."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r69")
    demo = run_demo(800, True, 42, out / "logs")
    request = build_request(800, stress=True, seed=42)
    prov = build_provenance(request, n=800, seed=42, stress=True)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


# ---------- CSS 토큰 / 디자인 시스템 ----------

def test_index_uses_design_tokens(pack):
    out, _ = pack
    text = (out / "index.html").read_text(encoding="utf-8")
    # CSS variables 가 :root 에 선언됨
    assert ":root" in text
    for token in ("--c-primary", "--c-surface", "--c-border", "--c-text",
                  "--c-success", "--c-warning", "--c-danger",
                  "--radius-md", "--shadow-sm"):
        assert token in text


def test_korean_font_stack_present(pack):
    out, _ = pack
    text = (out / "index.html").read_text(encoding="utf-8")
    # 한국어 시스템 폰트 stack
    assert "Pretendard" in text
    assert "Apple SD Gothic Neo" in text or "Malgun Gothic" in text


def test_no_external_fonts_or_scripts(pack):
    """디자인 강화 후에도 self-contained 유지 — 외부 폰트/CDN/스크립트 금지."""
    out, files = pack
    for p in files:
        text = p.read_text(encoding="utf-8")
        assert "fonts.googleapis.com" not in text
        assert "fonts.gstatic.com" not in text
        assert "cdn." not in text.lower()
        assert "<script" not in text
        # http://www.w3.org (SVG namespace) 만 허용
        assert text.replace("http://www.w3.org", "").count("http://") == 0
        assert "https://" not in text


def test_draft_banner_uses_modern_markup(pack):
    """DRAFT 배너가 단순 텍스트에서 markup polish (외부 제출 금지 strong)."""
    out, _ = pack
    text = (out / "executive.html").read_text(encoding="utf-8")
    assert "[DRAFT — 외부 제출 금지]" in text
    # 강조용 span / weight
    assert "letter-spacing" in text  # CSS 토큰이 banner 영역에서 사용


def test_table_has_box_shadow_and_rounded(pack):
    out, _ = pack
    text = (out / "index.html").read_text(encoding="utf-8")
    # 테이블이 그림자/라운드 (CSS 의 box-shadow)
    assert "box-shadow" in text
    assert "border-radius" in text


def test_card_grid_is_responsive(pack):
    out, _ = pack
    text = (out / "index.html").read_text(encoding="utf-8")
    # auto-fill 또는 minmax 그리드
    assert "grid-template-columns" in text
    assert "minmax(280px" in text


def test_card_hover_effect_present(pack):
    out, _ = pack
    text = (out / "index.html").read_text(encoding="utf-8")
    # hover 시 그림자/transform 효과
    assert ".card:hover" in text


def test_exec_summary_hero_uses_gradient(pack):
    """exec_summary 의 hero status 박스가 단색이 아닌 gradient polish."""
    out, _ = pack
    text = (out / "exec_summary.html").read_text(encoding="utf-8")
    assert "linear-gradient" in text


def test_executive_escalation_box_polished(pack):
    """stress case 의 escalation 박스가 polish 처리됨."""
    out, _ = pack
    text = (out / "executive.html").read_text(encoding="utf-8")
    # 새 박스 디자인: gradient + box-shadow + border-radius
    assert "Escalation" in text
    # 적어도 한 곳에서 linear-gradient 사용 (R69 hero or escalation box)
    assert text.count("linear-gradient") >= 1


def test_provenance_card_uses_subtle_palette(pack):
    out, _ = pack
    text = (out / "index.html").read_text(encoding="utf-8")
    assert "details.prov" in text
    # summary 의 chevron 트리거 (▸ / ▾)
    assert "summary::before" in text


def test_badges_pill_shape(pack):
    out, _ = pack
    text = (out / "executive.html").read_text(encoding="utf-8")
    # pill 형태 = border-radius 999px
    assert "border-radius: 999px" in text or "999px" in text


def test_typography_scale_visible(pack):
    out, _ = pack
    text = (out / "index.html").read_text(encoding="utf-8")
    for tag in ("h1 {", "h2 {", "h3 {", "h4 {"):
        assert tag in text
    # heading 에 letter-spacing 적용
    assert "letter-spacing:" in text


# ---------- 회귀 안전망 (디자인 변경이 의미 깨뜨리지 않음) ----------

def test_draft_watermark_still_required(pack):
    """디자인 강화 후에도 워터마크 텍스트 인식 가능."""
    out, files = pack
    for p in files:
        text = p.read_text(encoding="utf-8")
        assert "[DRAFT" in text
        assert "외부 제출 금지" in text


def test_provenance_card_still_present_on_all_pages(pack):
    out, files = pack
    for p in files:
        text = p.read_text(encoding="utf-8")
        assert "Reproducibility" in text


def test_svg_palette_remains_accessible(pack):
    """차트 색상이 디자인 변경 후에도 status 매칭 유지."""
    from tools.svg_charts import PALETTE

    # 6 키 모두 hex 색상
    for key in ("ok", "warning", "fail", "skipped", "simulated", "neutral"):
        assert key in PALETTE
        assert PALETTE[key].startswith("#")
        assert len(PALETTE[key]) == 7
