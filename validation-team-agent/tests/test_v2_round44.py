"""Round 44 — 데이터 품질 심화 (컬럼·결측·분포·등급별 부도율)."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r44")
    demo = run_demo(3_000, False, 42, out / "logs")
    request = build_request(3_000, stress=False, seed=42)
    prov = build_provenance(request, n=3_000, seed=42, stress=False)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_data_quality_deep_page_generated(pack):
    _, files = pack
    names = {p.name for p in files}
    assert "data_quality_deep.html" in names


def test_data_quality_deep_lists_each_column(pack):
    out, _ = pack
    text = (out / "data_quality_deep.html").read_text(encoding="utf-8")
    for col in ("customer_id", "score", "target", "grade", "pd", "set",
                "score_challenger"):
        assert col in text


def test_data_quality_deep_shows_numeric_summary(pack):
    out, _ = pack
    text = (out / "data_quality_deep.html").read_text(encoding="utf-8")
    for stat in ("mean", "std", "min", "median", "max"):
        assert stat in text


def test_data_quality_deep_shows_grade_default_rate(pack):
    out, _ = pack
    text = (out / "data_quality_deep.html").read_text(encoding="utf-8")
    assert "등급별 실측 부도율" in text
    # 적어도 1개 등급 + 차트
    assert "<svg" in text


def test_data_quality_deep_shows_dev_oot_split(pack):
    out, _ = pack
    text = (out / "data_quality_deep.html").read_text(encoding="utf-8")
    assert "dev / oot" in text
    assert "dev" in text and "oot" in text


def test_data_quality_deep_shows_date_coverage(pack):
    out, _ = pack
    text = (out / "data_quality_deep.html").read_text(encoding="utf-8")
    assert "최소 일자" in text
    assert "최대 일자" in text


def test_parent_page_links_to_deep(pack):
    out, _ = pack
    text = (out / "data_quality.html").read_text(encoding="utf-8")
    assert 'href="data_quality_deep.html"' in text


def test_index_links_to_data_deep(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="data_quality_deep.html"' in idx


def test_data_deep_self_contained_and_draft(pack):
    out, _ = pack
    text = (out / "data_quality_deep.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text
    assert "[DRAFT" in text
    assert "Reproducibility" in text


def test_data_deep_links_back_to_parent(pack):
    out, _ = pack
    text = (out / "data_quality_deep.html").read_text(encoding="utf-8")
    assert 'href="data_quality.html"' in text
