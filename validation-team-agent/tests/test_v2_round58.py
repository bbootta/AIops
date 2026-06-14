"""Round 58 — ICAAP methodology + 자본계획 시계열."""

from __future__ import annotations

import pytest


def test_icaap_methodology_sample():
    from tools.sample_generators import icaap_methodology_sample

    m = icaap_methodology_sample()
    risk_types = {x["risk_type"] for x in m}
    for required in ("신용", "시장", "운영", "IRRBB", "집중"):
        assert required in risk_types


def test_capital_plan_timeline_12_quarters():
    from tools.sample_generators import capital_plan_timeline_sample

    p = capital_plan_timeline_sample()
    assert len(p) == 12  # 3 years × 4 quarters
    quarters = {q["quarter"] for q in p}
    for y in (2026, 2027, 2028):
        for q in range(1, 5):
            assert f"{y}Q{q}" in quarters


def test_capital_plan_growth_consistent():
    from tools.sample_generators import capital_plan_timeline_sample

    p = capital_plan_timeline_sample()
    # 시간 경과에 따라 가용/필요 모두 증가
    assert p[-1]["available_capital_bn"] > p[0]["available_capital_bn"]
    assert p[-1]["required_capital_bn"] > p[0]["required_capital_bn"]


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r58")
    demo = run_demo(2_000, False, 42, out / "logs")
    request = build_request(2_000, stress=False, seed=42)
    prov = build_provenance(request, n=2_000, seed=42, stress=False)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_icaap_methodology_page_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    assert "icaap_methodology.html" in names


def test_page_lists_all_risk_types(pack):
    out, _ = pack
    text = (out / "icaap_methodology.html").read_text(encoding="utf-8")
    for rt in ("신용", "시장", "운영", "IRRBB", "집중"):
        assert rt in text


def test_page_shows_methodology_references(pack):
    out, _ = pack
    text = (out / "icaap_methodology.html").read_text(encoding="utf-8")
    for ref in ("IRBA", "MAR99", "OPE25", "SRP31"):
        assert ref in text


def test_page_shows_12_quarter_timeline(pack):
    out, _ = pack
    text = (out / "icaap_methodology.html").read_text(encoding="utf-8")
    for q in ("2026Q1", "2027Q1", "2028Q4"):
        assert q in text


def test_page_shows_buffer_trend(pack):
    out, _ = pack
    text = (out / "icaap_methodology.html").read_text(encoding="utf-8")
    assert "buffer" in text or "Buffer" in text
    assert "ALCO" in text or "MRMC" in text


def test_capital_parent_links_to_methodology(pack):
    out, _ = pack
    text = (out / "capital_icaap.html").read_text(encoding="utf-8")
    assert 'href="icaap_methodology.html"' in text


def test_index_links_to_methodology(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="icaap_methodology.html"' in idx


def test_page_self_contained(pack):
    out, _ = pack
    text = (out / "icaap_methodology.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text
    assert "[DRAFT" in text
    assert "Reproducibility" in text
