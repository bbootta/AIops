"""Round 70 — 차트 시각화 polish (dataviz mark specs 적용).

dataviz 스킬 원칙 검증:
- 텍스트는 series 색이 아닌 ink 토큰 (INK/INK_MUTED/INK_SUBTLE)
- trend_line 값 라벨은 selective (첫/끝/임계 위반) — never a number on
  every point (anti-pattern)
- recessive grid/축 (GRID/AXIS 토큰)
- 마커 ≥ 8px 직경 + 2px surface ring
- rounded data-ends (rx=4)
- skipped 색은 contrast ≥ 3:1 확보 (#64748b)
"""

from __future__ import annotations

import pytest


# ---------- 토큰 ----------

def test_ink_and_grid_tokens_defined():
    from tools.svg_charts import AXIS, GRID, INK, INK_MUTED, INK_SUBTLE

    for token in (INK, INK_MUTED, INK_SUBTLE, GRID, AXIS):
        assert token.startswith("#") and len(token) == 7


def test_skipped_color_has_sufficient_contrast():
    """#94a3b8 (2.5:1) → #64748b (≥3:1) — dataviz validator 결과 반영."""
    from tools.svg_charts import PALETTE

    assert PALETTE["skipped"] == "#64748b"


# ---------- hbar ----------

def test_hbar_labels_use_ink_tokens():
    from tools.svg_charts import INK, INK_MUTED, hbar

    svg = hbar([("A", 1.0), ("B", 2.0)], title="t")
    assert INK_MUTED in svg  # 카테고리 라벨
    assert INK in svg        # 값 라벨 + 제목


def test_hbar_has_recessive_grid():
    from tools.svg_charts import GRID, hbar

    svg = hbar([("A", 1.0)], title="t")
    assert GRID in svg


def test_hbar_rounded_ends_rx4():
    from tools.svg_charts import hbar

    svg = hbar([("A", 1.0)])
    assert 'rx="4"' in svg


def test_hbar_vline_uses_palette_fail():
    from tools.svg_charts import PALETTE, hbar

    svg = hbar([("A", 1.0)], vline=0.5, vline_label="min")
    assert PALETTE["fail"] in svg


# ---------- trend_line ----------

def test_trend_line_selective_value_labels():
    """8 point 시계열 — 값 라벨은 첫/끝/위반 점만 (dataviz anti-pattern 방지)."""
    from tools.svg_charts import trend_line

    series = [(f"P{i}", 1.2) for i in range(8)]  # 위반 없음
    svg = trend_line(series, minimum=1.0, fmt="{:.2f}")
    # 값 텍스트 '1.20' 은 첫/끝 2회만 등장해야 (모든 점 아님)
    assert svg.count(">1.20</text>") == 2


def test_trend_line_labels_breach_points():
    from tools.svg_charts import trend_line

    series = [("P0", 1.2), ("P1", 0.8), ("P2", 1.3)]  # P1 위반
    svg = trend_line(series, minimum=1.0, fmt="{:.2f}")
    # 첫(1.20)/위반(0.80)/끝(1.30) 3개 라벨
    assert ">1.20</text>" in svg
    assert ">0.80</text>" in svg
    assert ">1.30</text>" in svg


def test_trend_line_x_labels_thinned_for_many_points():
    from tools.svg_charts import trend_line

    series = [(f"D{i}", 1.0 + i * 0.01) for i in range(50)]
    svg = trend_line(series)
    # x 라벨은 처음/중간/끝 3개만
    x_labels = sum(1 for i in range(50) if f">D{i}</text>" in svg)
    assert x_labels == 3


def test_trend_line_has_y_axis_gridlines():
    from tools.svg_charts import GRID, trend_line

    svg = trend_line([("A", 1.0), ("B", 2.0)])
    assert GRID in svg
    # y 눈금 3 단계 (0/50/100%)
    assert svg.count(GRID) >= 3


def test_trend_line_markers_have_surface_ring():
    """마커는 white ring (r=5) 위 컬러 dot (r=4) — 2px surface ring spec."""
    from tools.svg_charts import trend_line

    svg = trend_line([("A", 1.0)])
    assert 'r="5" fill="white"' in svg
    assert 'r="4"' in svg


# ---------- gauge ----------

def test_gauge_track_uses_grid_token():
    from tools.svg_charts import GRID, gauge

    svg = gauge(1.2, minimum=1.0, label="LCR")
    assert GRID in svg
    assert 'rx="4"' in svg


def test_gauge_threshold_colors_from_palette():
    from tools.svg_charts import PALETTE, gauge

    svg = gauge(1.2, minimum=1.0, warning=1.1, label="LCR")
    assert PALETTE["fail"] in svg     # min 마커
    assert PALETTE["warning"] in svg  # warn 마커


# ---------- 통합 (팩 렌더) ----------

@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r70")
    demo = run_demo(800, True, 42, out / "logs")
    request = build_request(800, stress=True, seed=42)
    prov = build_provenance(request, n=800, seed=42, stress=True)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_trends_page_charts_use_new_tokens(pack):
    out, _ = pack
    text = (out / "trends.html").read_text(encoding="utf-8")
    from tools.svg_charts import GRID, INK

    assert GRID in text
    assert INK in text


def test_all_pages_remain_self_contained(pack):
    out, files = pack
    for p in files:
        text = p.read_text(encoding="utf-8")
        assert "<script" not in text
        assert "https://" not in text
        assert text.replace("http://www.w3.org", "").count("http://") == 0


def test_old_saturated_hexes_removed_from_charts():
    """구 팔레트 hex 가 차트 모듈에 잔존하지 않음."""
    from pathlib import Path

    src = Path("tools/svg_charts.py").read_text(encoding="utf-8")
    for old in ("#f9a825", "#c62828", "#9e9e9e", "#eceff1", "#90a4ae"):
        assert old not in src, f"구 hex 잔존: {old}"
