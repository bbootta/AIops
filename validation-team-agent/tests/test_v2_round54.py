"""Round 54 — IRRBB behavioral assumption + duration gap."""

from __future__ import annotations

import pytest


def test_irrbb_behavioral_sample_complete():
    from tools.sample_generators import irrbb_behavioral_sample

    b = irrbb_behavioral_sample()
    for k in ("nmd_total_bn", "nmd_core_ratio", "loan_prepayment_rate_annual",
              "duration_assets_yrs", "duration_liabilities_yrs",
              "duration_gap_yrs", "framework"):
        assert k in b
    # duration gap = asset - liab
    assert abs((b["duration_assets_yrs"] - b["duration_liabilities_yrs"])
               - b["duration_gap_yrs"]) < 0.01
    assert "SRP31" in b["framework"]


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r54")
    demo = run_demo(2_000, False, 42, out / "logs")
    request = build_request(2_000, stress=False, seed=42)
    prov = build_provenance(request, n=2_000, seed=42, stress=False)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_irrbb_behavioral_page_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    assert "irrbb_behavioral.html" in names


def test_page_shows_nmd_classification(pack):
    out, _ = pack
    text = (out / "irrbb_behavioral.html").read_text(encoding="utf-8")
    assert "NMD" in text
    assert "Core" in text and "Non-core" in text


def test_page_shows_prepayment_and_withdrawal(pack):
    out, _ = pack
    text = (out / "irrbb_behavioral.html").read_text(encoding="utf-8")
    assert "prepayment" in text.lower() or "Prepayment" in text
    assert "early withdrawal" in text.lower() or "early_withdrawal" in text.lower() or "Early" in text


def test_page_shows_duration_gap(pack):
    out, _ = pack
    text = (out / "irrbb_behavioral.html").read_text(encoding="utf-8")
    assert "Duration" in text or "duration" in text
    assert "gap" in text or "Gap" in text


def test_page_attributes_srp31(pack):
    out, _ = pack
    text = (out / "irrbb_behavioral.html").read_text(encoding="utf-8")
    assert "SRP31" in text


def test_alm_parent_links_to_behavioral(pack):
    out, _ = pack
    text = (out / "alm.html").read_text(encoding="utf-8")
    assert 'href="irrbb_behavioral.html"' in text


def test_index_links_to_behavioral(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="irrbb_behavioral.html"' in idx


def test_page_self_contained(pack):
    out, _ = pack
    text = (out / "irrbb_behavioral.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text
    assert "[DRAFT" in text
    assert "Reproducibility" in text
