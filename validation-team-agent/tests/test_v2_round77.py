"""Round 77 — CRO digest QoQ (전분기 대비) 섹션."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def digest(tmp_path_factory):
    from tools.cro_digest import build_digest
    from tools.run_workflow_demo import run_demo

    demo = run_demo(2_000, False, 42, tmp_path_factory.mktemp("logs"))
    return build_digest(demo, stress=False, seed=42, n=2_000,
                        generated_at="2026-01-01T00:00:00Z")


def test_qoq_section_present(digest):
    assert "전분기 대비 (QoQ)" in digest["html"]
    assert "== 전분기 대비 (QoQ" in digest["text"]
    for label in ("CET1 비율", "LCR", "내부자본비율", "PSI"):
        assert label in digest["html"]


def test_qoq_marks_synthetic(digest):
    """QoQ 는 합성 panel — 실측 오인 방지 문구 강제."""
    assert "합성 분기 panel" in digest["html"]
    assert "합성 panel 예시" in digest["text"]


def test_qoq_direction_uses_metric_semantics(digest):
    """낮을수록 좋은 지표 (ΔEVE/PSI/HHI) 는 상승 시 악화로 판정."""
    text = digest["text"]
    for line in text.splitlines():
        if line.startswith("- ΔEVE/Tier1:") or line.startswith("- PSI:"):
            # 합성 panel 은 점진 악화 시계열 — 상승(▲)이면 악화여야 한다
            if "▲" in line:
                assert "악화" in line, line
            if "▼" in line:
                assert "개선" in line, line


def test_qoq_matches_report_export_source(digest):
    """digest QoQ 수치가 report_export._qoq_table (SSoT) 와 일치."""
    from tools.report_export import _qoq_table

    row = next(r for r in _qoq_table() if r["metric"] == "cet1")
    assert f"{row['current_value']:.2%}" in digest["html"]
    assert f"{row['previous_value']:.2%}" in digest["html"]


def test_digest_still_deterministic(tmp_path):
    from tools.cro_digest import build_digest
    from tools.run_workflow_demo import run_demo

    demo = run_demo(2_000, False, 42, tmp_path / "logs")
    a = build_digest(demo, stress=False, seed=42, n=2_000,
                     generated_at="2026-01-01T00:00:00Z")
    b = build_digest(demo, stress=False, seed=42, n=2_000,
                     generated_at="2026-01-01T00:00:00Z")
    assert a == b
