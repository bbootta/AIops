"""Tests for the CRO-grade BIS capital deep-dive (Basel III CRE40/RBC20/RBC40/SRP20)."""

import math

import pandas as pd
import pytest

from risk_lib.capital.bis_deep import (
    CET1Components, AT1Components, Tier2Components,
    cet1_decomposition_table, at1_decomposition_table, tier2_decomposition_table,
    cet1_threshold_test, at1_t2_recognition_limits,
    BufferLayering, compute_buffer_layering, country_ccyb_weighted,
    evaluate_srep, dsib_buffer_for_bucket,
    mda_component_breakdown, cet1_quarterly_path, compute_bis_deep,
    synthesise_components_from_stack,
    DSIB_BUCKETS, COUNTRY_CCYB_DEFAULT,
)
from risk_lib.capital.leverage_deep import (
    decompose_exposure_measure, gsib_leverage_buffer, leverage_mda,
    compute_leverage_deep, GSIB_RWB_BUCKETS,
)
from risk_lib.capital.leverage import MIN_LEVERAGE_RATIO


# ============================================================================
# CET1 / AT1 / Tier2 components
# ============================================================================

def test_cet1_components_net_gross_deductions():
    c = CET1Components(
        common_shares=100, share_premium=200, retained_earnings=500,
        aoci=10, minority_interest=20,
        goodwill=30, intangibles=15, dta_excess=5,
    )
    assert c.gross == pytest.approx(830)
    assert c.total_deductions == pytest.approx(50)
    assert c.net == pytest.approx(780)


def test_at1_components_net():
    a = AT1Components(perpetual_notes=60, non_cumulative_preferred=20,
                      at1_minority_interest=5, at1_deductions=10)
    assert a.net == pytest.approx(75)


def test_tier2_subdebt_amortisation_5y():
    t = Tier2Components(subordinated_debt_amortising=100,
                        subordinated_remaining_years=5.0)
    assert t.amortised_subdebt == pytest.approx(100)


def test_tier2_subdebt_amortisation_partial():
    t = Tier2Components(subordinated_debt_amortising=100,
                        subordinated_remaining_years=2.5)
    assert t.amortised_subdebt == pytest.approx(50)


def test_tier2_subdebt_amortisation_zero_when_expired():
    t = Tier2Components(subordinated_debt_amortising=100,
                        subordinated_remaining_years=0.0)
    assert t.amortised_subdebt == pytest.approx(0)


def test_tier2_general_provisions_capped_at_125bp_of_irb():
    # GP = 200, IRB RWA = 10_000 → cap = 125 → recognised = 125
    t = Tier2Components(general_provisions=200, irb_rwa_for_gp_cap=10_000)
    assert t.gp_cap == pytest.approx(125)
    assert t.recognised_general_provisions == pytest.approx(125)
    # When GP below cap, full GP is recognised
    t2 = Tier2Components(general_provisions=50, irb_rwa_for_gp_cap=10_000)
    assert t2.recognised_general_provisions == pytest.approx(50)


def test_decomposition_tables_shape():
    c = CET1Components(common_shares=100, retained_earnings=400, goodwill=20)
    df = cet1_decomposition_table(c)
    assert {"item", "amount", "sign", "ref", "cumulative"}.issubset(df.columns)
    # cumulative at last row equals net
    assert df["cumulative"].iloc[-1] == pytest.approx(c.net)

    a = AT1Components(perpetual_notes=50, non_cumulative_preferred=10)
    da = at1_decomposition_table(a)
    assert da["cumulative"].iloc[-1] == pytest.approx(a.net)

    t = Tier2Components(subordinated_debt=80, general_provisions=10,
                        irb_rwa_for_gp_cap=10_000)
    dt = tier2_decomposition_table(t)
    assert dt["cumulative"].iloc[-1] == pytest.approx(t.net)


# ============================================================================
# Threshold (15%) test for DTA / MSR / Significant investments
# ============================================================================

def test_threshold_test_below_individual_limit_no_deduction():
    # CET1 1000 → 10% limit = 100.  All items ≤ 100.
    res = cet1_threshold_test(1000.0, dta_temporary_diff=50,
                              msr=40, significant_investments=30)
    assert res["individual_limit"] == pytest.approx(100)
    for item in res["individual"]:
        assert item.deducted == 0.0
    # Combined recognised 120, combined limit 150 → no combined excess
    assert res["combined_excess_deducted"] == pytest.approx(0.0)
    assert res["total_deducted"] == pytest.approx(0.0)


def test_threshold_test_individual_excess_deducted():
    # DTA 150 > 100 → 50 deducted at individual; recognised 100
    res = cet1_threshold_test(1000.0, dta_temporary_diff=150)
    assert res["individual"][0].deducted == pytest.approx(50)
    assert res["individual"][0].recognised == pytest.approx(100)
    assert res["total_deducted"] == pytest.approx(50)


def test_threshold_test_combined_15pct():
    # Each item recognises at the individual cap of 100.  Aggregate 300 → 150
    # over the 15% combined cap.
    res = cet1_threshold_test(1000.0, dta_temporary_diff=100,
                              msr=100, significant_investments=100)
    assert res["recognised_aggregate"] == pytest.approx(300)
    assert res["combined_limit"] == pytest.approx(150)
    assert res["combined_excess_deducted"] == pytest.approx(150)
    assert res["total_deducted"] == pytest.approx(150)


# ============================================================================
# AT1 / T2 recognition limits
# ============================================================================

def test_at1_t2_recognition_caps():
    rec = at1_t2_recognition_limits(cet1=900, at1=100, tier2=200)
    # AT1 cap = 900 × 1.5/4.5 = 300; 100 < 300 → full recognition
    assert rec["at1_cap"] == pytest.approx(300)
    assert rec["at1_recognised"] == pytest.approx(100)
    assert rec["at1_excess"] == 0.0
    # T2 cap = (900 + 100) × 2/6 = 333.33
    assert rec["t2_cap"] == pytest.approx(1000 * 2 / 6)
    assert rec["t2_recognised"] == pytest.approx(200)


def test_at1_excess_when_over_cap():
    rec = at1_t2_recognition_limits(cet1=900, at1=500, tier2=10)
    # AT1 cap = 300, excess = 200
    assert rec["at1_excess"] == pytest.approx(200)


# ============================================================================
# Buffer layering
# ============================================================================

def test_buffer_layering_defaults_match_basel():
    bl = BufferLayering()
    assert bl.p1_cet1 == pytest.approx(0.045)
    assert bl.capital_conservation == pytest.approx(0.025)
    assert bl.cbr == pytest.approx(0.025)
    assert bl.mda_threshold_cet1 == pytest.approx(0.070)
    assert bl.srep_cet1 == pytest.approx(0.070)
    assert bl.ocr_cet1 == pytest.approx(0.070)


def test_buffer_layering_full_stack():
    bl = BufferLayering(countercyclical=0.005, dsib=0.015,
                        p2r=0.015, p2g=0.010)
    assert bl.cbr == pytest.approx(0.045)
    assert bl.mda_threshold_cet1 == pytest.approx(0.090)
    assert bl.srep_cet1 == pytest.approx(0.105)
    assert bl.ocr_cet1 == pytest.approx(0.115)
    df = bl.to_layers()
    # the cumulative on last row should equal ocr_cet1
    assert df["cumulative"].iloc[-1] == pytest.approx(bl.ocr_cet1)


def test_compute_buffer_layering_dsib_bucket():
    bl = compute_buffer_layering(dsib_bucket=2, p2r=0.01)
    assert bl.dsib == pytest.approx(0.015)
    assert bl.p2r == pytest.approx(0.01)


def test_dsib_buckets_known_values():
    assert dsib_buffer_for_bucket(1) == pytest.approx(0.010)
    assert dsib_buffer_for_bucket(5) == pytest.approx(0.035)
    with pytest.raises(ValueError):
        dsib_buffer_for_bucket(6)


# ============================================================================
# Country CCyB weighted
# ============================================================================

def test_country_ccyb_weighted_basic():
    exp = {"KR": 800, "US": 100, "JP": 100}
    res = country_ccyb_weighted(exp)
    # weighted = 0.8·0.010 + 0.1·0.000 + 0.1·0.000 = 0.008
    assert res["weighted_ccyb"] == pytest.approx(0.008)
    df = res["by_country"]
    assert set(df["country"]) == set(exp.keys())
    assert df["share"].sum() == pytest.approx(1.0)


def test_country_ccyb_with_overrides():
    exp = {"KR": 500, "US": 500}
    res = country_ccyb_weighted(exp, ccyb_rates={"US": 0.020})
    # weighted = 0.5·0.010 + 0.5·0.020 = 0.015
    assert res["weighted_ccyb"] == pytest.approx(0.015)


def test_country_ccyb_zero_exposure():
    res = country_ccyb_weighted({})
    assert res["weighted_ccyb"] == 0.0
    assert res["by_country"].empty


# ============================================================================
# SREP evaluation
# ============================================================================

def test_srep_all_pass_when_well_capitalised():
    bl = BufferLayering(countercyclical=0.005, dsib=0.01,
                        p2r=0.015, p2g=0.010)
    srep = evaluate_srep(cet1_ratio=0.15, layering=bl)
    assert srep.p1_pass and srep.cbr_pass and srep.srep_pass and srep.ocr_pass
    assert "OCR" in srep.overall_status()
    assert srep.surplus_to_srep > 0
    assert srep.surplus_to_ocr > 0


def test_srep_fails_p1():
    bl = BufferLayering(dsib=0.01, p2r=0.01)
    srep = evaluate_srep(cet1_ratio=0.04, layering=bl)
    assert not srep.p1_pass
    assert "P1" in srep.overall_status()


def test_srep_fails_cbr_but_passes_p1():
    bl = BufferLayering(dsib=0.01)   # CBR = 3.5%, mda_threshold = 8%
    srep = evaluate_srep(cet1_ratio=0.06, layering=bl)
    assert srep.p1_pass
    assert not srep.cbr_pass
    assert "MDA" in srep.overall_status()


def test_srep_p2g_only_failure():
    bl = BufferLayering(dsib=0.01, p2r=0.01, p2g=0.02)
    # srep_cet1 = 4.5 + 3.5 + 1 = 9%, ocr = 11%
    srep = evaluate_srep(cet1_ratio=0.10, layering=bl)
    assert srep.srep_pass and not srep.ocr_pass
    assert "P2G" in srep.overall_status()


# ============================================================================
# MDA component breakdown
# ============================================================================

def test_mda_components_distributable_full_when_pct_1():
    df = mda_component_breakdown(
        distributable_earnings=1000, distributable_pct=1.0,
        requested_dividend=200, requested_buyback=100,
        requested_variable_comp=50, requested_at1_coupon=100,
    )
    assert (df["blocked"] == 0).all()
    assert df["allowed"].sum() == pytest.approx(450)


def test_mda_components_pro_rata_with_priority():
    df = mda_component_breakdown(
        distributable_earnings=1000, distributable_pct=0.4,
        # total allowance = 400
        requested_dividend=200, requested_buyback=200,
        requested_variable_comp=200, requested_at1_coupon=200,
    )
    # AT1 first 200, then variable_comp 200; dividend + buyback blocked
    assert df.loc[df["component"] == "AT1 쿠폰", "allowed"].iloc[0] == pytest.approx(200)
    assert df.loc[df["component"] == "변동성과보수", "allowed"].iloc[0] == pytest.approx(200)
    assert df.loc[df["component"] == "배당", "allowed"].iloc[0] == 0
    assert df.loc[df["component"] == "자사주매입", "allowed"].iloc[0] == 0
    assert df["allowed"].sum() == pytest.approx(400)


def test_mda_components_zero_distributable_blocks_all():
    df = mda_component_breakdown(
        distributable_earnings=1000, distributable_pct=0.0,
        requested_dividend=100, requested_buyback=100,
        requested_variable_comp=100, requested_at1_coupon=100,
    )
    assert (df["allowed"] == 0).all()


# ============================================================================
# Quarterly CET1 path
# ============================================================================

def test_quarterly_path_shape_and_starting_value():
    df = cet1_quarterly_path(
        cet1_start=1000, rwa_start=10_000,
        quarters=4, quarterly_earnings=20,
        quarterly_dividend=10, srep_cet1=0.07,
    )
    assert len(df) == 5     # q=0..4
    assert df["cet1"].iloc[0] == 1000
    assert df["cet1_ratio"].iloc[0] == pytest.approx(0.1)


def test_quarterly_path_breach_streak_advances():
    df = cet1_quarterly_path(
        cet1_start=650, rwa_start=10_000,
        quarters=3, quarterly_earnings=0, quarterly_dividend=0,
        srep_cet1=0.07,
    )
    # CET1 ratio 6.5% < 7% → breach all 4 quarters
    assert (df["breach"]).all()
    assert df["breach_streak"].tolist() == [1, 2, 3, 4]
    assert "supervisory action" in df["supervisory_action"].iloc[-1]


def test_quarterly_path_rwa_grows():
    df = cet1_quarterly_path(
        cet1_start=1000, rwa_start=10_000, quarters=4,
        quarterly_earnings=0, rwa_growth_per_q=0.05,
    )
    # RWA grows geometrically; ratio falls
    assert df["rwa"].iloc[-1] == pytest.approx(10_000 * 1.05**4)
    assert df["cet1_ratio"].iloc[-1] < df["cet1_ratio"].iloc[0]


def test_quarterly_path_rejects_invalid():
    with pytest.raises(ValueError):
        cet1_quarterly_path(cet1_start=100, rwa_start=0, quarters=4)
    with pytest.raises(ValueError):
        cet1_quarterly_path(cet1_start=100, rwa_start=1000, quarters=0)


# ============================================================================
# Leverage deep
# ============================================================================

def test_decompose_exposure_measure_components():
    br = decompose_exposure_measure(
        on_balance=1000,
        derivatives_replacement_cost=50,
        derivatives_pfe_notional=200, derivatives_alpha=1.4,
        sft_gross=300, sft_collateral_offset=100,
        off_balance_notional=500, off_balance_ccf=0.20,
    )
    # PFE = 200 * 1.4 = 280; SFT net = 200; off = 500 * 0.20 = 100
    expected = 1000 + 50 + 280 + 200 + 100
    assert br.total_exposure == pytest.approx(expected)
    df = br.to_frame()
    assert df["share"].sum() == pytest.approx(1.0)


def test_decompose_off_balance_ccf_floor_at_10pct():
    br = decompose_exposure_measure(
        on_balance=0, off_balance_notional=1000, off_balance_ccf=0.05,
    )
    # CCF floored at 10%, so 1000 * 0.10 = 100
    assert br.total_exposure == pytest.approx(100)


def test_gsib_leverage_buffer_is_half_of_rwb():
    assert gsib_leverage_buffer(bucket=2) == pytest.approx(0.015 * 0.5)
    assert gsib_leverage_buffer(bucket=5) == pytest.approx(0.035 * 0.5)
    assert gsib_leverage_buffer(risk_weighted_rate=0.02) == pytest.approx(0.01)
    assert gsib_leverage_buffer() == 0.0
    with pytest.raises(ValueError):
        gsib_leverage_buffer(bucket=6)


def test_leverage_mda_no_breach_when_above_total_req():
    m = leverage_mda(0.05, gsib_buffer=0.01)
    assert not m.in_breach
    assert m.distributable_pct == 1.0


def test_leverage_mda_full_lock_below_minimum():
    m = leverage_mda(0.025, gsib_buffer=0.01)
    assert m.in_breach
    assert m.buffer_quartile == 1
    assert m.distributable_pct == 0.0


def test_leverage_mda_in_buffer_zone_quartiles():
    # Buffer zone is [3.0%, 4.0%] when buffer = 1%. Midpoint 3.5% should be q=2 or 3.
    m = leverage_mda(0.035, gsib_buffer=0.01)
    assert m.in_breach
    assert 1 <= m.buffer_quartile <= 4
    assert 0.0 < m.retention_ratio < 1.0


def test_compute_leverage_deep_end_to_end():
    res = compute_leverage_deep(
        tier1=100, on_balance=2000,
        derivatives_replacement_cost=50,
        derivatives_pfe_notional=200,
        off_balance_notional=500,
        gsib_bucket=1,
    )
    # EM = 2000 + 50 + 280 + 0 + 50 = 2380, LR = 100/2380 ≈ 4.20%
    assert res.leverage_ratio == pytest.approx(100 / 2380)
    assert res.gsib_buffer == pytest.approx(0.005)
    assert res.passes_minimum
    # Buffer breach? requirement = 3.5%; LR = 4.20% → no breach
    assert res.passes_with_buffer


def test_compute_leverage_deep_rejects_zero_em():
    with pytest.raises(ValueError):
        compute_leverage_deep(tier1=100, on_balance=0)


# ============================================================================
# End-to-end compute_bis_deep
# ============================================================================

def test_compute_bis_deep_full():
    cet1 = CET1Components(
        common_shares=100, share_premium=200, retained_earnings=500,
        goodwill=20, intangibles=10,
    )
    at1 = AT1Components(perpetual_notes=60, non_cumulative_preferred=20)
    t2 = Tier2Components(subordinated_debt=80, general_provisions=10,
                         irb_rwa_for_gp_cap=10_000)
    res = compute_bis_deep(
        cet1=cet1, at1=at1, tier2=t2, rwa=7000,
        threshold_inputs={"dta_temporary_diff": 50, "msr": 40,
                          "significant_investments": 30},
        # 미지정은 None 으로만 말한다. 0.0 은 "적용 CCyB 가 0" 이라는 값이며
        # 그때는 국가가중치로 갈아치우지 않는다 (아래 별도 시험).
        countercyclical=None,
        dsib_bucket=2, p2r=0.015, p2g=0.010,
        exposures_by_country={"KR": 600, "US": 200, "JP": 200},
    )
    # Layering CBR = 2.5% + weighted CCyB (0.6·0.01=0.006) + DSIB(2)=1.5% = 4.6%
    assert res.layering.dsib == pytest.approx(0.015)
    # weighted CCyB from {KR:600,US:200,JP:200} with KR=1% defaults
    assert res.layering.countercyclical == pytest.approx(0.6 * 0.010)
    assert res.layering.p2r == pytest.approx(0.015)
    # SREP eval populated
    assert res.srep.cet1_ratio == pytest.approx(cet1.net / 7000)
    # Quarterly path 5 rows
    assert len(res.quarterly_path) == 5
    # MDA components — 4 rows
    assert len(res.mda_components) == 4
    # Country CCyB DF has 3 rows
    assert len(res.country_ccyb["by_country"]) == 3


def test_supplied_zero_ccyb_is_a_value_not_a_missing_input():
    """적용 CCyB 가 0 인 기관에서 국가가중치가 그 자리를 차지하지 않는다.

    예전에는 0.0 을 미지정으로 읽어 국가가중 CCyB 로 갈아치웠다. 그러면 완충
    원장이 0 인 기관에서 이 계층의 요구비율이 `compute_bis_ratios` 의 요구비율과
    갈리고, 같은 기관에 요구비율 두 벌이 공시된다. 국가별 표는 그대로 낸다.
    """
    cet1 = CET1Components(common_shares=100, share_premium=200,
                          retained_earnings=500, goodwill=20, intangibles=10)
    at1 = AT1Components(perpetual_notes=60)
    t2 = Tier2Components(subordinated_debt=80)
    res = compute_bis_deep(
        cet1=cet1, at1=at1, tier2=t2, rwa=7000,
        countercyclical=0.0, dsib_rate=0.0,
        exposures_by_country={"KR": 600, "US": 200, "JP": 200},
    )
    assert res.layering.countercyclical == pytest.approx(0.0)
    assert res.layering.dsib == pytest.approx(0.0)
    assert len(res.country_ccyb["by_country"]) == 3


def test_compute_bis_deep_rejects_zero_rwa():
    cet1 = CET1Components(common_shares=100)
    at1 = AT1Components()
    t2 = Tier2Components()
    with pytest.raises(ValueError):
        compute_bis_deep(cet1=cet1, at1=at1, tier2=t2, rwa=0)


def test_synthesise_components_recovers_net_totals():
    c, a, t = synthesise_components_from_stack(
        cet1_total=1000.0, at1_total=150.0, tier2_total=200.0,
        irb_rwa=20_000.0,
    )
    assert c.net == pytest.approx(1000.0)
    assert a.net == pytest.approx(150.0)
    # T2: subordinated_debt + recognised GP up to 1.25% × 20000 = 250 cap
    assert t.net == pytest.approx(200.0)
