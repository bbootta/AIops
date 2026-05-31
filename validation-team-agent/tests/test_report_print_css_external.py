from pathlib import Path

from tools.report_template import _PRINT_CSS_PATH, _load_print_css, render_html


def test_print_css_file_exists():
    assert _PRINT_CSS_PATH.exists()


def test_load_print_css_returns_at_page_rule():
    css = _load_print_css()
    assert "@page" in css
    assert "@media print" in css


def test_render_html_uses_external_css(tmp_path):
    html = render_html("# T\n\n## 1. 요약\n요약.\n")
    assert "@page" in html
    # external css 내용이 그대로 임베드 되어야 한다
    assert "page-break-after" in html


def test_render_html_falls_back_when_css_missing(monkeypatch, tmp_path):
    bogus = tmp_path / "absent.css"
    monkeypatch.setattr("tools.report_template._PRINT_CSS_PATH", bogus)
    css = _load_print_css()
    assert "@page" in css  # fallback 상수가 적용
