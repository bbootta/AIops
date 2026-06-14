"""Round 49 — 신용평가 고도화 (세그먼트별 변별력 + ROC + 분포 + vintage)."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r49")
    demo = run_demo(5_000, False, 42, out / "logs")
    request = build_request(5_000, stress=False, seed=42)
    prov = build_provenance(request, n=5_000, seed=42, stress=False)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_credit_segments_page_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    assert "credit_segments.html" in names


def test_credit_vintage_page_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    assert "credit_vintage.html" in names


def test_credit_segments_has_grade_ks_table(pack):
    out, _ = pack
    text = (out / "credit_segments.html").read_text(encoding="utf-8")
    assert "등급별 변별력" in text
    assert "KS" in text and "AUROC" in text
    # 등급 A~E 모두 등장
    for g in "ABCDE":
        assert f"<td>{g}</td>" in text


def test_credit_segments_has_dev_oot_comparison(pack):
    out, _ = pack
    text = (out / "credit_segments.html").read_text(encoding="utf-8")
    assert "dev / oot" in text
    assert "Gini" in text
    assert "AUROC" in text


def test_credit_segments_has_roc_and_histogram(pack):
    out, _ = pack
    text = (out / "credit_segments.html").read_text(encoding="utf-8")
    assert "ROC" in text
    assert "TPR" in text and "FPR" in text
    assert "good" in text and "bad" in text


def test_credit_vintage_has_quarterly_cohorts(pack):
    out, _ = pack
    text = (out / "credit_vintage.html").read_text(encoding="utf-8")
    # 2022/2023 분기 등장
    assert "2022Q" in text or "2022-Q" in text
    assert "2023Q" in text or "2023-Q" in text
    assert "vintage" in text or "Vintage" in text


def test_credit_vintage_has_grade_pivot(pack):
    out, _ = pack
    text = (out / "credit_vintage.html").read_text(encoding="utf-8")
    assert "등급 × 분기" in text or "등급" in text


def test_credit_main_page_links_to_new_deep(pack):
    out, _ = pack
    text = (out / "credit.html").read_text(encoding="utf-8")
    assert 'href="credit_segments.html"' in text
    assert 'href="credit_vintage.html"' in text


def test_index_links_to_new_credit_deep(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="credit_segments.html"' in idx
    assert 'href="credit_vintage.html"' in idx


def test_new_pages_self_contained_and_provenance(pack):
    out, _ = pack
    for name in ("credit_segments.html", "credit_vintage.html"):
        text = (out / name).read_text(encoding="utf-8")
        assert "https://" not in text
        assert "<script" not in text
        assert "[DRAFT" in text
        assert "Reproducibility" in text
