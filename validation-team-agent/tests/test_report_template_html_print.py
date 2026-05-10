from tools.report_template import render_html


def test_print_css_included_by_default():
    html = render_html("# T\n\n## 1. 요약\n요약.\n")
    assert "@page" in html
    assert "@media print" in html


def test_print_css_can_be_disabled():
    html = render_html("# T\n\n## 1. 요약\n요약.\n", print_friendly=False)
    assert "@page" not in html
    assert "@media print" not in html


def test_h2_page_break_class_added_when_requested():
    html = render_html(
        "# T\n\n## 1. 요약\n요약.\n\n## 2. 검증 목적\n목적.\n",
        page_break_before_h2=True,
    )
    assert '<h2 class="pb">1. 요약</h2>' in html
    assert '<h2 class="pb">2. 검증 목적</h2>' in html


def test_h2_no_pb_class_by_default():
    html = render_html("# T\n\n## 1. 요약\n요약.\n")
    assert '<h2 class="pb">' not in html
    assert '<h2>1. 요약</h2>' in html
