"""v0.14.0 — final validation (cross-domain + attestation) tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from risk_lib import generate_portfolio, run_pipeline
from risk_lib.validation import (
    ConsistencyCheck,
    run_cross_domain_checks,
    domain_status,
    DOMAINS,
)


# ---- shared pipeline fixture (re-used across tests for speed) --------------

@pytest.fixture(scope="module")
def pipeline_result():
    return run_pipeline(generate_portfolio(seed=42), seed=42)


# ---- cross_domain unit tests ---------------------------------------------

def test_cross_domain_pd_in_master_scale_pass():
    irb = pd.DataFrame({"pd": [0.001, 0.05, 0.5], "asset_class": ["corporate"]*3})
    out = run_cross_domain_checks(irb_results=irb)
    pd_check = [c for c in out if c.name == "xd_pd_in_master_scale"][0]
    assert pd_check.status == "PASS"


def test_cross_domain_pd_in_master_scale_fail():
    irb = pd.DataFrame({"pd": [-0.1, 0.05, 1.2], "asset_class": ["corporate"]*3})
    out = run_cross_domain_checks(irb_results=irb)
    pd_check = [c for c in out if c.name == "xd_pd_in_master_scale"][0]
    assert pd_check.status == "FAIL"


def test_cross_domain_rwa_components_sum_pass():
    rwa = {
        "sa": 100.0, "irb": 200.0, "market": 50.0, "op": 50.0,
        "final_total": 400.0,
        "output_floor": SimpleNamespace(add_on=0.0, is_binding=False,
                                         rwa_internal=400.0, rwa_final=400.0),
    }
    bis = SimpleNamespace(rwa=400.0, cet1_ratio=0.115)
    out = run_cross_domain_checks(rwa=rwa, bis_result=bis)
    sums = [c for c in out if c.name == "xd_rwa_components_sum"][0]
    assert sums.status == "PASS"
    eq = [c for c in out if c.name == "xd_rwa_equals_bis_input"][0]
    assert eq.status == "PASS"


def test_cross_domain_rwa_components_sum_fail():
    # missing add-on but final_total inflated → mismatch
    rwa = {
        "sa": 100.0, "irb": 200.0, "market": 50.0, "op": 50.0,
        "final_total": 500.0,
        "output_floor": SimpleNamespace(add_on=0.0, is_binding=False,
                                         rwa_internal=400.0, rwa_final=500.0),
    }
    bis = SimpleNamespace(rwa=500.0, cet1_ratio=0.115)
    out = run_cross_domain_checks(rwa=rwa, bis_result=bis)
    sums = [c for c in out if c.name == "xd_rwa_components_sum"][0]
    assert sums.status == "FAIL"


def test_cross_domain_rwa_equals_bis_input_fail():
    rwa = {
        "sa": 100.0, "irb": 200.0, "market": 50.0, "op": 50.0,
        "final_total": 400.0,
        "output_floor": SimpleNamespace(add_on=0.0, is_binding=False,
                                         rwa_internal=400.0, rwa_final=400.0),
    }
    bis = SimpleNamespace(rwa=420.0, cet1_ratio=0.115)
    out = run_cross_domain_checks(rwa=rwa, bis_result=bis)
    eq = [c for c in out if c.name == "xd_rwa_equals_bis_input"][0]
    assert eq.status == "FAIL"


def test_cross_domain_ecl_el_direction():
    irb = pd.DataFrame({"el": [100.0, 200.0]})
    ecl = pd.DataFrame({"ecl": [110.0, 200.0], "stage": [1, 1]})
    out = run_cross_domain_checks(irb_results=irb, ecl_results=ecl)
    c = [c for c in out if c.name == "xd_ecl_el_direction"][0]
    assert c.status == "PASS"


def test_cross_domain_ecl_el_direction_warn_on_huge_gap():
    irb = pd.DataFrame({"el": [100.0]})
    ecl = pd.DataFrame({"ecl": [10000.0], "stage": [1]})
    out = run_cross_domain_checks(irb_results=irb, ecl_results=ecl)
    c = [c for c in out if c.name == "xd_ecl_el_direction"][0]
    assert c.status == "WARN"


def test_cross_domain_stress_baseline_matches():
    stress = pd.DataFrame({
        "scenario": ["baseline", "adverse", "severely_adverse"],
        "cet1_ratio": [0.115, 0.10, 0.08],
        "rwa_total": [400.0, 500.0, 600.0],
    })
    bis = SimpleNamespace(rwa=400.0, cet1_ratio=0.115)
    out = run_cross_domain_checks(stress_results=stress, bis_result=bis)
    base = [c for c in out if c.name == "xd_stress_baseline_matches_bis"][0]
    assert base.status == "PASS"
    mono = [c for c in out if c.name == "xd_stress_cet1_severity_monotone"][0]
    assert mono.status == "PASS"


def test_cross_domain_stress_severity_monotone_fail():
    stress = pd.DataFrame({
        "scenario": ["baseline", "adverse", "severely_adverse"],
        "cet1_ratio": [0.115, 0.13, 0.08],   # adverse > baseline = wrong
        "rwa_total": [400.0, 500.0, 600.0],
    })
    bis = SimpleNamespace(rwa=400.0, cet1_ratio=0.115)
    out = run_cross_domain_checks(stress_results=stress, bis_result=bis)
    mono = [c for c in out if c.name == "xd_stress_cet1_severity_monotone"][0]
    assert mono.status == "FAIL"


def test_cross_domain_reproducibility_pass():
    out = run_cross_domain_checks(first_digest="abc123", second_digest="abc123")
    c = [c for c in out if c.name == "xd_reproducibility_digest"][0]
    assert c.status == "PASS"


def test_cross_domain_reproducibility_fail():
    out = run_cross_domain_checks(first_digest="abc123", second_digest="def456")
    c = [c for c in out if c.name == "xd_reproducibility_digest"][0]
    assert c.status == "FAIL"


def test_cross_domain_rapm_ec_reconciles():
    irb = pd.DataFrame({"k": [0.08, 0.10], "ead": [1000.0, 2000.0]})
    rapm = pd.DataFrame({"asset_class": ["a", "b"], "ec": [80.0, 200.0]})
    out = run_cross_domain_checks(irb_results=irb, rapm_by_class=rapm)
    c = [c for c in out if c.name == "xd_rapm_ec_reconciles_irb_k"][0]
    assert c.status == "PASS"


def test_cross_domain_limits_concentration_alignment():
    limit_report = pd.DataFrame({
        "limit": ["동일차주_Tier1_25pct", "섹터_총노출_3조"],
        "severity": ["BREACH", "OK"],
    })
    lex = pd.DataFrame({"severity": ["BREACH"]})
    out = run_cross_domain_checks(limit_report=limit_report, large_exposure=lex)
    c = [c for c in out if c.name == "xd_obligor_lex_count"][0]
    assert c.status == "PASS"


def test_cross_domain_limits_concentration_mismatch():
    limit_report = pd.DataFrame({
        "limit": ["동일차주_Tier1_25pct"],
        "severity": ["BREACH"],
    })
    lex = pd.DataFrame({"severity": ["OK", "OK"]})
    out = run_cross_domain_checks(limit_report=limit_report, large_exposure=lex)
    c = [c for c in out if c.name == "xd_obligor_lex_count"][0]
    assert c.status == "FAIL"


# ---- domain_status aggregation -------------------------------------------

def test_domain_status_keys_match_DOMAINS():
    checks = [ConsistencyCheck("pd_in_[0,1]", "PASS", "ok")]
    out = domain_status(checks)
    assert set(out.keys()) == {k for k, _ in DOMAINS}


def test_domain_status_fail_dominates():
    checks = [
        ConsistencyCheck("xd_rwa_components_sum", "FAIL", "bad"),
        # SA·IRB EAD 체크는 이름이 분리돼 있다 — 같은 이름으로 두 번 등록하면
        # 이름 조회 시 한쪽이 가려지므로 label을 붙였다.
        ConsistencyCheck("ead_nonneg_sa", "PASS", "ok"),
    ]
    out = domain_status(checks)
    assert out["rwa"]["status"] == "FAIL"
    assert out["rwa"]["n_fail"] == 1
    assert out["rwa"]["n_pass"] == 1


def test_domain_status_warn_when_no_fail():
    checks = [ConsistencyCheck("concentration_hhi", "WARN", "high")]
    out = domain_status(checks)
    assert out["limits"]["status"] == "WARN"


# ---- pipeline integration -----------------------------------------------

def test_pipeline_includes_cross_domain_checks(pipeline_result):
    v = pipeline_result.validation
    names = {c.name for c in v.checks}
    expected = {
        "xd_pd_in_master_scale", "xd_rwa_components_sum",
        "xd_rwa_equals_bis_input", "xd_ecl_el_direction",
        "xd_obligor_lex_count", "xd_rapm_ec_reconciles_irb_k",
        "xd_stress_baseline_matches_bis",
        "xd_stress_cet1_severity_monotone",
    }
    assert expected.issubset(names)


def test_pipeline_passes_overall(pipeline_result):
    """All real-data cross-domain checks should pass on the canonical seed."""
    v = pipeline_result.validation
    assert v.passes(), [
        (c.name, c.status, c.detail) for c in v.checks if c.status == "FAIL"
    ]


def test_pipeline_reproducibility_bit_for_bit():
    """Identical seed → identical headline_digest (bit-level determinism)."""
    from risk_lib.repro import build_manifest
    from datetime import datetime, timezone
    pf1 = generate_portfolio(seed=42)
    pf2 = generate_portfolio(seed=42)
    r1 = run_pipeline(pf1, seed=42)
    r2 = run_pipeline(pf2, seed=42)
    now = datetime.now(timezone.utc)
    m1 = build_manifest(portfolio=pf1, parameters={"seed": 42}, result=r1,
                        start_utc=now, end_utc=now)
    m2 = build_manifest(portfolio=pf2, parameters={"seed": 42}, result=r2,
                        start_utc=now, end_utc=now)
    assert m1.headline_digest == m2.headline_digest


# ---- attestation page rendering -----------------------------------------

def test_attestation_page_rendered(pipeline_result, tmp_path: Path):
    from risk_lib.html_report import build_report_set
    out = tmp_path / "ops"
    paths = build_report_set(pipeline_result, out)
    assert "52_final_attestation.html" in paths
    content = Path(paths["52_final_attestation.html"]).read_text(encoding="utf-8")
    assert "최종 결재 attestation" in content
    assert "BCBS 239" in content
    # 8 domain labels should appear
    for _, label in DOMAINS:
        assert label in content, f"missing domain label: {label}"
    # Verdict line
    assert ("결재 가능" in content) or ("결재 불가" in content)
    # Signature placeholders
    assert "CRO" in content
    assert "산출 책임자" in content


def test_validation_page_includes_matrix(pipeline_result, tmp_path: Path):
    from risk_lib.html_report import build_report_set
    out = tmp_path / "ops"
    paths = build_report_set(pipeline_result, out)
    content = Path(paths["12_validation.html"]).read_text(encoding="utf-8")
    assert "8 부문 정합성 매트릭스" in content
    assert "Cross-domain 정합성" in content
