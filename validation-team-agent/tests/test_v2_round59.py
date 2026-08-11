"""Round 59-61 (combined) — ESG/Climate + Cyber + FX dependency."""

from __future__ import annotations

import pytest


# ---------- samples ----------

def test_esg_climate_sample_complete():
    from tools.sample_generators import esg_climate_sample

    e = esg_climate_sample()
    for k in ("scope1_emissions_tco2e_thousand",
              "scope2_emissions_tco2e_thousand",
              "financed_emissions_mtco2e",
              "carbon_intensity_by_sector",
              "transition_risk_exposure_bn",
              "physical_risk_exposure_bn",
              "ngfs_scenarios", "framework"):
        assert k in e
    assert len(e["ngfs_scenarios"]) == 3
    assert "BCBS d530" in e["framework"]


def test_cyber_risk_sample_complete():
    from tools.sample_generators import cyber_risk_sample

    c = cyber_risk_sample()
    assert len(c["incident_history_5y"]) == 5
    assert len(c["scenarios"]) >= 5
    # NIST CSF 5 function
    for f in ("Identify", "Protect", "Detect", "Respond", "Recover"):
        keys = " ".join(c["control_maturity"])
        assert f in keys
    assert "BCBS d533" in c["framework"]


def test_fx_dependency_sample_complete():
    from tools.sample_generators import fx_dependency_sample

    f = fx_dependency_sample()
    for k in ("fx_assets_by_currency", "fx_liabilities_by_currency",
              "usd_funding_dependency_pct", "fx_var_99_1d_bn",
              "fx_stress_won_dollar_shock"):
        assert k in f
    # 양쪽 통화 set 일치
    assert set(f["fx_assets_by_currency"]) == set(f["fx_liabilities_by_currency"])


# ---------- pack ----------

@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r59_61")
    demo = run_demo(2_000, False, 42, out / "logs")
    request = build_request(2_000, stress=False, seed=42)
    prov = build_provenance(request, n=2_000, seed=42, stress=False)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_three_new_pages_generated(pack):
    _, files = pack
    names = {p.name for p in files}
    for p in ("esg_climate.html", "cyber_risk.html", "fx_dependency.html"):
        assert p in names


def test_esg_page_shows_ngfs_and_pcaf(pack):
    out, _ = pack
    text = (out / "esg_climate.html").read_text(encoding="utf-8")
    for label in ("Scope 1", "Scope 2", "Scope 3", "NGFS", "financed",
                  "전환", "물리적"):
        assert label in text
    for scen in ("Orderly", "Disorderly", "Hot House"):
        assert scen in text


def test_esg_page_shows_sector_intensity(pack):
    out, _ = pack
    text = (out / "esg_climate.html").read_text(encoding="utf-8")
    for sector in ("에너지", "운송", "건설", "제조업"):
        assert sector in text


def test_cyber_page_shows_nist_csf(pack):
    out, _ = pack
    text = (out / "cyber_risk.html").read_text(encoding="utf-8")
    for f in ("Identify", "Protect", "Detect", "Respond", "Recover"):
        assert f in text
    assert "RTO" in text and "RPO" in text


def test_cyber_page_lists_scenarios(pack):
    out, _ = pack
    text = (out / "cyber_risk.html").read_text(encoding="utf-8")
    for s in ("Ransomware", "DDoS", "Insider", "Third-party", "Cloud"):
        assert s in text


def test_cyber_page_shows_5y_history(pack):
    out, _ = pack
    text = (out / "cyber_risk.html").read_text(encoding="utf-8")
    for year in range(2021, 2026):
        assert str(year) in text


def test_fx_page_shows_currencies(pack):
    out, _ = pack
    text = (out / "fx_dependency.html").read_text(encoding="utf-8")
    for c in ("KRW", "USD", "JPY", "EUR", "CNY"):
        assert c in text
    assert "NOP" in text or "Net Open Position" in text


def test_fx_page_shows_usd_funding_and_stress(pack):
    out, _ = pack
    text = (out / "fx_dependency.html").read_text(encoding="utf-8")
    assert "USD" in text
    assert "외환스왑" in text or "swap" in text.lower()
    assert "NDF" in text
    assert "원화 급락" in text or "won 급락" in text


def test_index_links_to_all_three(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    for href in ("esg_climate.html", "cyber_risk.html", "fx_dependency.html"):
        assert f'href="{href}"' in idx


def test_executive_links_to_all_three(pack):
    out, _ = pack
    exe = (out / "executive.html").read_text(encoding="utf-8")
    for href in ("esg_climate.html", "cyber_risk.html", "fx_dependency.html"):
        assert f'href="{href}"' in exe


def test_new_pages_self_contained_and_provenance(pack):
    out, _ = pack
    for name in ("esg_climate.html", "cyber_risk.html", "fx_dependency.html"):
        text = (out / name).read_text(encoding="utf-8")
        assert "https://" not in text
        assert "<script" not in text
        assert "[DRAFT" in text
        assert "Reproducibility" in text
