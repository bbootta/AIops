"""Round 78 — 차트 접근성: 모든 SVG 에 role="img" + aria-label."""

from __future__ import annotations

import re

ARIA_RE = re.compile(r'<svg [^>]*role="img"[^>]*aria-label="[^"]+"')


def test_all_chart_builders_emit_aria():
    from tools.svg_charts import (
        gauge,
        hbar,
        heatmap,
        kpi_card_strip,
        status_donut,
        trend_line,
    )

    svgs = [
        hbar([("a", 1.0)], title="변별력"),
        gauge(1.2, minimum=1.0, label="LCR"),
        status_donut({"ok": 3, "fail": 1}, title="상태"),
        heatmap([("부문", "ok", "detail", None)], title="부문 현황"),
        kpi_card_strip([("CET1", "13%", "ok")]),
        trend_line([("Q1", 1.0), ("Q2", 2.0)], title="추이"),
    ]
    for svg in svgs:
        assert ARIA_RE.search(svg), svg[:120]


def test_aria_label_includes_title():
    from tools.svg_charts import hbar

    svg = hbar([("a", 1.0)], title="등급별 KS")
    assert 'aria-label="가로 막대 차트: 등급별 KS"' in svg


def test_aria_label_escapes_quotes():
    from tools.svg_charts import hbar

    svg = hbar([("a", 1.0)], title='x"y<z>')
    m = ARIA_RE.search(svg)
    assert m and '"y' not in m.group(0).split('aria-label=')[1][:30].replace(
        "&quot;", "")
    assert "&quot;" in svg and "&lt;z&gt;" in svg


def test_built_pack_pages_have_no_unlabeled_svg(tmp_path):
    """빌드된 팩의 모든 콘텐츠 SVG 가 aria-label 을 가진다."""
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    demo = run_demo(2_000, False, 42, tmp_path / "logs")
    request = build_request(2_000, stress=False, seed=42)
    written = build_pack(demo, request, tmp_path / "pack")
    unlabeled = []
    for p in written:
        html = p.read_text(encoding="utf-8")
        for m in re.finditer(r"<svg [^>]*>", html):
            tag = m.group(0)
            if 'role="img"' not in tag or "aria-label=" not in tag:
                unlabeled.append((p.name, tag[:90]))
    assert not unlabeled, unlabeled[:5]
