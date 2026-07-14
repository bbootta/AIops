"""Round 76 — 보고서 팩 다크모드 (prefers-color-scheme) + 인쇄 라이트 강제."""

from __future__ import annotations

import re

from tools.report_pack import _CSS, _page


def _contrast(fg: str, bg: str) -> float:
    def lum(hexc: str) -> float:
        r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))

        def f(c: float) -> float:
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

    la, lb = lum(fg), lum(bg)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _dark_block() -> str:
    m = re.search(
        r"@media \(prefers-color-scheme: dark\) \{(.*?)\n\}", _CSS, re.DOTALL)
    assert m, "다크모드 블록 누락"
    return m.group(1)


def _print_block() -> str:
    m = re.search(r"@media print \{(.*)", _CSS, re.DOTALL)
    assert m, "인쇄 블록 누락"
    return m.group(1)


def _token(block: str, name: str) -> str:
    m = re.search(rf"{re.escape(name)}:\s*(#[0-9a-fA-F]{{6}})", block)
    assert m, f"{name} 토큰 누락"
    return m.group(1)


def test_dark_mode_overrides_core_tokens():
    dark = _dark_block()
    for token in ("--c-bg", "--c-surface", "--c-text", "--c-text-muted",
                  "--c-border", "--c-code-bg", "--chart-plate"):
        assert token in dark, token


def test_dark_tokens_meet_wcag_contrast():
    """다크 텍스트 토큰 WCAG AA (본문 4.5:1) — 계산 검증, 눈대중 금지."""
    dark = _dark_block()
    bg = _token(dark, "--c-bg")
    surface = _token(dark, "--c-surface")
    assert _contrast(_token(dark, "--c-text"), bg) >= 4.5
    assert _contrast(_token(dark, "--c-text"), surface) >= 4.5
    assert _contrast(_token(dark, "--c-text-muted"), surface) >= 4.5
    assert _contrast(_token(dark, "--c-primary-2"), bg) >= 4.5


def test_chart_plate_light_in_dark_mode():
    """차트 SVG 는 고정 잉크색 — 다크에선 라이트 플레이트 위에 표시."""
    dark = _dark_block()
    assert _token(dark, "--chart-plate").lower() == "#ffffff"
    assert re.search(r"svg \{[^}]*background: var\(--chart-plate\)", _CSS,
                     re.DOTALL)


def test_print_forces_light_tokens():
    """인쇄는 다크모드 브라우저에서도 항상 라이트 (CRO 결재 출력)."""
    pr = _print_block()
    assert _token(pr, "--c-bg").lower() == "#ffffff"
    assert _token(pr, "--c-text").lower() == "#0f172a"
    assert "color: #0f172a" in pr
    # 인쇄 블록이 다크 블록보다 뒤 (같은 specificity 에서 인쇄가 이긴다)
    assert _CSS.index("@media print") > _CSS.index(
        "@media (prefers-color-scheme: dark)")


def test_no_hardcoded_banner_gradient():
    assert "var(--c-banner-bg), #fff)" not in _CSS


def test_rendered_page_contains_dark_block():
    html = _page("t", "<p>x</p>")
    assert "@media (prefers-color-scheme: dark)" in html
    assert "<script" not in html.lower()
