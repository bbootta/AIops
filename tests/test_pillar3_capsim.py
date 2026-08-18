"""Tests for Pillar 3 disclosure templates + multi-period capital simulation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib.pillar3_disclosures import (
    km1, ov1, cr1, cr2, cr3, cr4, cr5,
    mr1, mr2, liq1, liq2, lr1, lr2,
)
from risk_lib.capital_simulation import (
    simulate_capital_path, projection_summary, CapitalAction,
    _mda_quartile, _mda_retention,
)

# `result` / `portfolio` fixtures: session-scoped shared — see conftest.py.


# ----- Pillar 3 — each template returns rows -------------------------------

def test_km1_shape(result):
    df = km1(result)
    assert len(df) == 17
    assert set(df.columns) == {"행", "지표", "값", "단위"}


def test_km1_critical_values(result):
    df = km1(result).set_index("지표")
    assert "보통주자본(CET1)" in df.index
    assert "CET1 비율" in df.index
    assert "LCR" in df.index
    assert "NSFR" in df.index


def test_ov1_total_equals_pipeline_rwa(result):
    df = ov1(result)
    # Last row should be 최종 RWA
    assert "최종" in df.iloc[-1]["부문"]
    final = float(df.iloc[-1]["RWA"])
    assert final == pytest.approx(result.rwa["final_total"], rel=1e-9)


def test_ov1_capital_requirement_is_8pct_of_rwa(result):
    df = ov1(result)
    for _, row in df.iterrows():
        if isinstance(row["RWA"], (int, float)) and row["RWA"] > 0:
            assert row["최저 자본요구 (8%)"] == pytest.approx(row["RWA"] * 0.08, rel=1e-9)


def test_cr1_sum_balances(result, portfolio):
    df = cr1(result, portfolio)
    # Last row is the total; performing + non-performing should equal it
    total_row = df[df["행"] == "5"].iloc[0]
    perf_row = df[df["행"] == "1"].iloc[0]
    npe_row  = df[df["행"] == "3"].iloc[0]
    assert total_row["총 익스포저"] == pytest.approx(
        perf_row["총 익스포저"] + npe_row["총 익스포저"], rel=1e-9)


def test_cr2_movement_balances(result, portfolio):
    """CR2: 기초 + inflow - cure - writeoff + other = 기말."""
    df = cr2(result, portfolio).set_index("행")
    opening = float(df.loc["1", "금액"])
    closing = float(df.loc["6", "금액"])
    movements = float(df.loc[["2","3","4","5"], "금액"].sum())
    assert opening + movements == pytest.approx(closing, rel=1e-6)


def test_cr3_total_matches_portfolio_ead(result, portfolio):
    df = cr3(result, portfolio)
    total_row = df[df["행"] == "7"].iloc[0]
    assert total_row["EAD"] == pytest.approx(float(portfolio["ead"].sum()), rel=1e-9)


def test_cr4_post_crm_less_than_pre(result, portfolio):
    df = cr4(result, portfolio)
    for _, row in df.iterrows():
        assert row["EAD (post-CRM)"] < row["EAD (pre-CRM)"]


def test_cr5_shares_sum_to_total(result, portfolio):
    df = cr5(result, portfolio)
    rw_cols = ["0%", "20%", "50%", "75%", "100%", "150%", "기타"]
    for _, row in df.iterrows():
        bucket_sum = sum(float(row[c]) for c in rw_cols)
        assert bucket_sum == pytest.approx(float(row["총 EAD"]), rel=1e-6)


def test_mr1_total_equals_rwa(result):
    df = mr1(result)
    components = df[df["행"].isin(["1","2","3","4","5"])]["값"].astype(float).sum()
    total_row = df[df["행"] == "6"]["값"].iloc[0]
    assert components == pytest.approx(float(total_row), rel=1e-6)


def test_mr2_terminates_at_current_rwa(result):
    df = mr2(result)
    end = df[df["행"] == "7"]["금액"].iloc[0]
    assert float(end) == pytest.approx(result.rwa["market"], rel=1e-9)


def test_liq1_includes_all_hqla_levels(result):
    df = liq1(result)
    items = set(df["항목"])
    assert any("Level 1" in i for i in items)
    assert any("Level 2A" in i for i in items)
    assert any("Level 2B" in i for i in items)
    assert any("LCR" in i for i in items)


def test_liq2_has_asf_and_rsf(result):
    df = liq2(result)
    sections = set(df["섹션"])
    assert "ASF" in sections and "RSF" in sections


def test_lr1_total_matches_exposure_measure(result):
    df = lr1(result)
    total = df[df["행"] == "7"]["금액"].iloc[0]
    assert float(total) == pytest.approx(result.leverage.exposure_measure, rel=1e-9)


def test_lr2_leverage_matches_pipeline(result):
    df = lr2(result).set_index("항목")
    # Row "레버리지 비율" must equal pipeline leverage_ratio
    val = float(df.loc["<b>레버리지 비율</b>", "값"])
    assert val == pytest.approx(result.leverage.leverage_ratio, rel=1e-9)


# ----- MDA constraint helpers ---------------------------------------------

def test_mda_quartile_above_buffer():
    """CET1 above 4.5% + 2.5% CBR → quartile 0."""
    assert _mda_quartile(0.115) == 0


def test_mda_quartile_progression():
    """Walking from top of CBR down should hit quartile 1 → 2 → 3 → 4."""
    cbr_top = 0.045 + 0.025
    # Quartile 1: just below the top
    assert _mda_quartile(cbr_top - 0.003) == 1
    # Quartile 2
    assert _mda_quartile(cbr_top - 0.010) == 2
    # Quartile 3
    assert _mda_quartile(cbr_top - 0.016) == 3
    # Quartile 4: below P1 minimum
    assert _mda_quartile(0.040) == 4


def test_mda_retention_increases():
    """Deeper quartile → more retention."""
    assert _mda_retention(0) == 0.0
    assert _mda_retention(1) == 0.40
    assert _mda_retention(4) == 1.00


# ----- Capital simulation -------------------------------------------------

def test_capital_simulation_smoke(result):
    cap = result.meta["capital"]
    proj = simulate_capital_path(
        base_cet1=cap.cet1, base_tier1=cap.tier1, base_total=cap.total,
        base_rwa=result.bis.rwa, n_quarters=8,
    )
    assert len(proj) == 24      # 3 scenarios × 8 quarters
    assert set(proj["scenario"]) == {"baseline", "adverse", "severe"}


def test_severe_strictly_worse_than_baseline(result):
    cap = result.meta["capital"]
    proj = simulate_capital_path(
        base_cet1=cap.cet1, base_tier1=cap.tier1, base_total=cap.total,
        base_rwa=result.bis.rwa, n_quarters=8,
    )
    final = proj[proj["quarter"] == 8]
    b = float(final[final["scenario"] == "baseline"]["cet1_ratio"].iloc[0])
    s = float(final[final["scenario"] == "severe"]["cet1_ratio"].iloc[0])
    assert s < b


def test_at1_issuance_lifts_tier1(result):
    cap = result.meta["capital"]
    proj_no = simulate_capital_path(
        base_cet1=cap.cet1, base_tier1=cap.tier1, base_total=cap.total,
        base_rwa=result.bis.rwa, n_quarters=8,
    )
    proj_yes = simulate_capital_path(
        base_cet1=cap.cet1, base_tier1=cap.tier1, base_total=cap.total,
        base_rwa=result.bis.rwa, n_quarters=8,
        planned_actions=[CapitalAction(quarter=2, action="at1_issue", amount=2e12)],
    )
    # Compare baseline scenario at Q8
    tier1_no = float(proj_no[(proj_no["scenario"] == "baseline") & (proj_no["quarter"] == 8)]["tier1"].iloc[0])
    tier1_yes = float(proj_yes[(proj_yes["scenario"] == "baseline") & (proj_yes["quarter"] == 8)]["tier1"].iloc[0])
    assert tier1_yes > tier1_no


def test_projection_summary_finds_breach(result):
    cap = result.meta["capital"]
    proj = simulate_capital_path(
        base_cet1=cap.cet1 * 0.6,       # crank down for guaranteed breach
        base_tier1=cap.tier1 * 0.6,
        base_total=cap.total * 0.6,
        base_rwa=result.bis.rwa,
        n_quarters=8,
    )
    summ = projection_summary(proj)
    # Severe scenario must report a first breach quarter
    sev = summ[summ["scenario"] == "severe"].iloc[0]
    assert sev["passes_all"] is False or sev["first_breach_q"] is not None


# ----- Page registration --------------------------------------------------

def test_pillar3_capsim_pages_in_report(tmp_path, result, portfolio):
    from risk_lib.html_report import build_full_report_package
    written = build_full_report_package(result, tmp_path, portfolio=portfolio)
    assert "ops/59_pillar3_full.html" in written
    assert "ops/60_capital_simulation.html" in written
    import os
    assert os.path.getsize(written["ops/59_pillar3_full.html"]) > 5000
    assert os.path.getsize(written["ops/60_capital_simulation.html"]) > 5000
