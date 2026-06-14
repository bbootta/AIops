"""Round 37 — ICAAP/ALM 부문 + 계층형 HTML 보고서 팩."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


# ---------- ICAAP ----------

def test_icaap_ok_case():
    from vta.domains.icaap import check_internal_capital

    out = check_internal_capital(
        11_000.0,
        {"credit": 4_800, "market": 1_300, "operational": 900,
         "irrbb": 800, "concentration": 700},
        diversification_benefit=500.0,
        post_stress_available=9_500.0,
    )
    assert out["passed"] is True
    assert out["level"] == "ok"
    assert out["ratio"] == pytest.approx(11_000 / 8_000)
    assert out["post_stress_level"] == "ok"
    assert out["findings"] == []
    assert out["missing_risk_types"] == []


def test_icaap_below_min_fails():
    from vta.domains.icaap import check_internal_capital

    out = check_internal_capital(
        7_000.0, {"credit": 5_000, "market": 2_000, "operational": 1_000,
                  "irrbb": 500, "concentration": 500})
    assert out["passed"] is False
    assert out["level"] == "below_min"


def test_icaap_post_stress_breach_fails():
    from vta.domains.icaap import check_internal_capital

    out = check_internal_capital(
        10_000.0,
        {"credit": 4_000, "market": 1_500, "operational": 1_000,
         "irrbb": 800, "concentration": 700},
        post_stress_available=7_000.0,  # 7000/8000 < 1.0
    )
    assert out["passed"] is False
    assert out["post_stress_level"] == "below_min"


def test_icaap_missing_risk_type_flagged():
    from vta.domains.icaap import check_internal_capital

    out = check_internal_capital(10_000.0, {"credit": 5_000, "market": 2_000})
    assert "operational" in out["missing_risk_types"]
    assert any("누락" in f for f in out["findings"])


def test_icaap_single_risk_concentration_warning():
    from vta.domains.icaap import check_internal_capital

    out = check_internal_capital(
        20_000.0, {"credit": 7_000, "market": 1_000, "operational": 1_000,
                   "irrbb": 500, "concentration": 500})
    assert any("단일 리스크(credit)" in f for f in out["findings"])


def test_icaap_excess_diversification_warning():
    from vta.domains.icaap import check_internal_capital

    out = check_internal_capital(
        10_000.0, {"credit": 4_000, "market": 2_000, "operational": 1_500,
                   "irrbb": 1_500, "concentration": 1_000},
        diversification_benefit=4_000.0)  # 40% > 30%
    assert any("분산효과" in f for f in out["findings"])


def test_icaap_invalid_inputs_raise():
    from vta.domains.icaap import check_internal_capital

    with pytest.raises(ValueError):
        check_internal_capital(-1.0, {"credit": 100})
    with pytest.raises(ValueError):
        check_internal_capital(100.0, {})
    with pytest.raises(ValueError):
        check_internal_capital(100.0, {"credit": 50}, diversification_benefit=60)


# ---------- ALM ----------

def test_alm_maturity_gap_ok():
    from vta.domains.alm import check_maturity_gap

    out = check_maturity_gap(
        {"1M": -2_000, "3M": -1_000, "6M": 500, "1Y": 1_500,
         "3Y": 4_000, "over_3Y": 8_000},
        100_000.0)
    assert out["passed"] is True
    assert out["level"] == "ok"
    assert out["worst_bucket"] == "3M"
    assert out["worst_ratio"] == pytest.approx(-0.03)


def test_alm_maturity_gap_breach():
    from vta.domains.alm import check_maturity_gap

    out = check_maturity_gap(
        {"1M": -9_000, "3M": -5_000, "6M": -2_000}, 100_000.0)
    assert out["passed"] is False
    assert out["level"] == "below_min"
    assert out["worst_ratio"] == pytest.approx(-0.16)


def test_alm_funding_concentration():
    from vta.domains.alm import check_funding_concentration

    ok = check_funding_concentration([2_000.0] + [1_600.0] * 40)
    assert ok["passed"] is True
    warn = check_funding_concentration([12_000.0] + [800.0] * 40)
    assert warn["level"] == "warning"
    assert warn["top1_share"] > 0.10


def test_alm_loan_to_deposit():
    from vta.domains.alm import check_loan_to_deposit

    assert check_loan_to_deposit(93_000, 100_000)["level"] == "ok"
    assert check_loan_to_deposit(98_000, 100_000)["level"] == "warning"
    breach = check_loan_to_deposit(102_000, 100_000)
    assert breach["passed"] is False


def test_alm_invalid_inputs_raise():
    from vta.domains.alm import (
        check_funding_concentration,
        check_loan_to_deposit,
        check_maturity_gap,
    )

    with pytest.raises(ValueError):
        check_maturity_gap({"1M": 0.0}, 0.0)
    with pytest.raises(ValueError):
        check_maturity_gap({"unknown_bucket": 1.0}, 100.0)
    with pytest.raises(ValueError):
        check_funding_concentration([])
    with pytest.raises(ValueError):
        check_loan_to_deposit(100.0, 0.0)


# ---------- workflow 통합 ----------

def test_demo_normal_runs_icaap_alm(tmp_path):
    from tools.run_workflow_demo import run_demo

    demo = run_demo(500, False, 42, tmp_path)
    assert demo["results"]["3.icaap"]["status"] == "ok"
    assert demo["results"]["3.alm"]["status"] == "ok"
    # NSFR 이 demo 입력으로 실제 평가된다 (R37 이전에는 입력 부재로 미평가)
    assert "nsfr" in demo["results"]["3.liquidity"]["outputs"]


def test_demo_stress_icaap_alm_fail_and_escalate(tmp_path):
    from tools.run_workflow_demo import run_demo

    demo = run_demo(500, True, 42, tmp_path)
    assert demo["results"]["3.icaap"]["status"] == "fail"
    assert demo["results"]["3.alm"]["status"] == "fail"
    assert demo["results"]["3.liquidity"]["status"] == "fail"  # NSFR 0.90
    trig = demo["results"]["9.escalate"]["outputs"]["triggered_by"]
    assert "3.icaap" in trig and "3.alm" in trig


# ---------- 보고서 팩 ----------

@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("pack")
    demo = run_demo(800, True, 42, out / "logs")
    request = build_request(800, stress=True, seed=42)
    files = build_pack(demo, request, out)
    return out, files


EXPECTED_PAGES = {
    "executive.html", "index.html", "explainability.html", "trends.html",
    "credit.html", "credit_calibration.html", "challenger.html",
    "credit_segments.html", "credit_vintage.html",
    "capital_icaap.html", "capital_buffer_deep.html", "capital_rwa_deep.html",
    "icaap_deep.html", "icaap_methodology.html",
    "alm.html", "alm_gap.html", "alm_irrbb.html", "alm_currency_deep.html",
    "irrbb_behavioral.html",
    "market_ops.html", "operational_deep.html", "operational_bi_deep.html",
    "ccr_deep.html",
    "market_backtest_deep.html", "market_components_deep.html",
    "op_scenario_deep.html", "cva_deep.html", "ccr_netting_deep.html",
    "macro_overlay.html",
    "concentration.html", "concentration_segments.html",
    "data_quality.html", "data_quality_deep.html",
    "ifrs9_deep.html", "ifrs9_fli_deep.html",
    "stress_test.html", "change_audit.html",
    "esg_climate.html", "cyber_risk.html", "fx_dependency.html",
}


def test_pack_generates_all_pages(pack):
    out, files = pack
    assert {p.name for p in files} == EXPECTED_PAGES


def test_pack_every_page_has_draft_watermark_and_svg(pack):
    out, files = pack
    for p in files:
        text = p.read_text(encoding="utf-8")
        assert "[DRAFT" in text, f"{p.name}: 워터마크 누락"
        assert "외부 제출 금지" in text
    # 시각화: 요약/부문 페이지에 inline SVG 존재
    for name in ("index.html", "credit.html", "capital_icaap.html", "alm.html"):
        assert "<svg" in (out / name).read_text(encoding="utf-8"), name


def test_pack_is_self_contained(pack):
    """외부 JS/CSS/이미지 참조 없음 (내부망 열람 가능)."""
    out, files = pack
    for p in files:
        text = p.read_text(encoding="utf-8")
        assert "http://" not in text.replace("http://www.w3.org", "")
        assert "https://" not in text
        assert "<script" not in text


def test_pack_index_links_resolve(pack):
    import re

    out, files = pack
    names = {p.name for p in files}
    for p in files:
        for href in re.findall(r'href="([^"]+)"', p.read_text(encoding="utf-8")):
            assert href in names, f"{p.name} → 깨진 링크: {href}"


def test_pack_stress_index_shows_escalation(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert "Escalation 발생" in idx
    assert "3.icaap" in idx


def test_pack_cli(tmp_path):
    from tools.report_pack import main

    rc = main(["--n", "500", "--out", str(tmp_path / "pack"),
               "--log-dir", str(tmp_path / "logs")])
    assert rc == 0
    assert (tmp_path / "pack" / "index.html").exists()
