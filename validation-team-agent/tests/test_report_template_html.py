from tools.report_template import build_validation_report, render_html


def test_render_html_produces_valid_skeleton():
    md = "# 보고서\n\n> [DRAFT — 외부 제출 금지] 인간 검증자 승인 전 사용 불가\n\n## 1. 요약\n요약 본문.\n"
    html = render_html(md, title="Demo")
    assert html.startswith("<!doctype html>")
    assert "<title>Demo</title>" in html
    assert "<h1>보고서</h1>" in html
    assert "<h2>1. 요약</h2>" in html
    assert "<blockquote>" in html
    assert "DRAFT" in html


def test_render_html_preserves_inline_code_and_table():
    md = (
        "## 5. 주요 결과\n"
        "표 형식 (출처: `tools/metric_ks_auc.calculate_auc_gini`):\n"
        "\n"
        "| metric | value |\n"
        "|---|---|\n"
        "| AUC | 0.78 |\n"
    )
    html = render_html(md)
    assert "<code>tools/metric_ks_auc.calculate_auc_gini</code>" in html
    assert "<table>" in html
    assert "</table>" in html
    assert "<td>0.78</td>" in html


def test_render_html_escapes_special_chars():
    html = render_html("# <script>alert('x')</script>\n")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_render_html_full_report_round_trip():
    md = build_validation_report({"title": "T", "summary": "ok"})
    html = render_html(md)
    assert "<h1>T</h1>" in html
    assert "외부 제출 금지" in html
