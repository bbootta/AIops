"""End-to-end risk pipeline wiring every module together.

Order: data → PD models → CRM/CCF → RWA(SA+IRB) → market/op RWA →
       output floor → BIS → leverage → IFRS9 ECL → limits → concentration →
       RAPM → stress → self-verification.

Returns a structured `PipelineResult` consumed by report.py / cli.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

from risk_lib.data_gen import (
    generate_portfolio, split_train_test, generate_workout_cashflows,
)
from risk_lib.models.pd_model import fit_pd_model, gini, ks_statistic
from risk_lib.models.rating import pd_to_rating, DEFAULT_MASTER_SCALE
from risk_lib.models.discrimination import discrimination_summary
from risk_lib.models.lgd_model import fit_lgd_model, lgd_backtest
from risk_lib.models.explain import (
    coefficient_table, permutation_importance, master_scale_calibration,
    grade_migration_psi,
)
from risk_lib.capital.rwa_sa import compute_rwa_sa, standardised_rwa_total
from risk_lib.capital.rwa_irb import compute_rwa_irb
from risk_lib.capital.bis import (
    CapitalStack, compute_bis_ratios, synthesise_capital,
)
from risk_lib.capital.op_risk import BusinessIndicator, compute_op_risk_rwa
from risk_lib.capital.market_risk import compute_market_risk_rwa
from risk_lib.capital.output_floor import apply_output_floor, FULLY_LOADED_FLOOR
from risk_lib.capital.rwa_deep import compute_rwa_deep
from risk_lib.capital.bis_deep import (
    compute_bis_deep, synthesise_components_from_stack,
)
from risk_lib.capital.leverage import compute_leverage_ratio, exposure_measure
from risk_lib.capital.leverage_deep import compute_leverage_deep
from risk_lib.provisioning.ecl import compute_ecl
from risk_lib.provisioning.macro import macro_ecl, macro_ecl_path, DEFAULT_MACRO_SCENARIOS
from risk_lib.provisioning.ifrs9_deep import compute_ifrs9_deep, IFRS9DeepResult
from risk_lib.monitoring.delinquency import delinquency_summary, default_rate
from risk_lib.monitoring.recovery import cumulative_recovery_rate
from risk_lib.monitoring.deep import compute_delinquency_deep
from risk_lib.monitoring.recovery_deep import compute_recovery_deep
from risk_lib.monitoring.cure import compute_cure
from risk_lib.monitoring.vintage_deep import compute_vintage_deep
from risk_lib.limits.limit_engine import LimitDefinition, LimitEngine
from risk_lib.limits.concentration import concentration_report
from risk_lib.limits.limits_deep import compute_limits_deep, LimitsDeepResult
from risk_lib.performance.rapm import rapm_report
from risk_lib.performance.rapm_deep import compute_rapm_deep, RapmDeepResult
from risk_lib.stress.scenario import (
    run_stress, StressAxis, Scenario, BASELINE, ADVERSE, SEVERELY_ADVERSE,
)
from risk_lib.stress.reverse import reverse_stress
from risk_lib.stress.path import (
    run_stress_path, path_trough_summary, forecast_quarter_labels,
)
from risk_lib.stress.narrative import (
    DEFAULT_PATHS as MACRO_NARRATIVE_PATHS, macro_table, narrative_summary,
)
from risk_lib.stress.decomposition import (
    factor_decomposition, asset_class_sensitivity,
)
from risk_lib.stress.multi_reverse import run_multi_reverse
from risk_lib.stress.ccar import run_ccar
from risk_lib.stress.climate_capital import run_climate_capital
from risk_lib.stress.liquidity import (
    run_liquidity_stress, recovery_priority_ladder,
)
from risk_lib.stress.recovery import (
    build_recovery_plan, scenario_recovery_table,
)
from risk_lib.stress.comparison import compare_scenarios
from risk_lib.validation.consistency import run_consistency_checks
from risk_lib.validation.backtest import pd_backtest_report
from risk_lib.validation.cross_domain import run_cross_domain_checks
from risk_lib.alm.balance_sheet import generate_balance_sheet
from risk_lib.alm.irrbb import compute_irrbb
from risk_lib.alm.lcr import compute_lcr
from risk_lib.alm.nsfr import compute_nsfr
from risk_lib.icaap.economic_capital import compute_icaap
from risk_lib.appetite import build_raf
from risk_lib.climate import run_climate
from risk_lib.ccr import compute_ccr
from risk_lib.op_loss import compute_op_loss
from risk_lib.concentration_deep import (
    top_obligors, sector_country_matrix, large_exposure_test, granularity_addon,
    hierarchical_hhi, top_n_share_table, gini_coefficient, lorenz_curve,
    wrong_way_correlation, sector_systemic_correlation,
)
from risk_lib.model_risk import build_model_cards, drift_report
from risk_lib.sensitivity import one_factor_grid, two_factor_surface
from risk_lib.attribution import decompose_cet1_headroom, decompose_rwa


# Per-segment PD model feature sets available in the synthetic data.
_SEGMENT_FEATURES = {
    "corporate": ["leverage", "current_ratio", "log_assets",
                  "interest_coverage", "gdp_growth"],
    "retail_other": ["dti", "utilization", "income_log", "months_employed"],
    "residential_mortgage": ["ltv", "dti", "credit_score", "income_log"],
}

# Challenger uses half the feature set per segment to stress-test marginal lift.
_CHALLENGER_FEATURES = {
    "corporate": ["leverage", "current_ratio"],
    "retail_other": ["dti", "utilization"],
    "residential_mortgage": ["ltv", "credit_score"],
}

# LGD feature sets per segment.
_LGD_FEATURES = {
    "corporate": ["leverage", "current_ratio", "log_assets",
                  "interest_coverage"],
    "retail_other": ["dti", "utilization", "income_log"],
    "residential_mortgage": ["ltv", "dti", "credit_score"],
}

_SA_CORP_BUCKET_BY_GRADE = {g.grade: g.sa_bucket for g in DEFAULT_MASTER_SCALE}


@dataclass
class PipelineResult:
    portfolio_summary: pd.DataFrame
    pd_metrics: dict[str, dict[str, float]]
    rwa: dict[str, Any]
    bis: Any
    leverage: Any
    ecl: dict[str, Any]
    monitoring: dict[str, Any]
    limits: pd.DataFrame
    concentration: pd.DataFrame
    rapm: pd.DataFrame
    stress: pd.DataFrame
    macro_ecl: Any
    macro_ecl_path: pd.DataFrame
    reverse_stress: Any
    stress_path: pd.DataFrame
    stress_path_trough: pd.DataFrame
    backtest: dict[str, Any]
    validation: Any
    alm: dict[str, Any] = field(default_factory=dict)    # balance_sheet/irrbb/lcr/nsfr
    icaap: Any = None
    raf: Any = None
    climate: Any = None
    ccr: Any = None
    op_loss: Any = None
    concentration_deep: dict[str, Any] = field(default_factory=dict)
    model_cards: list = field(default_factory=list)
    sensitivity: dict[str, Any] = field(default_factory=dict)
    attribution: dict[str, Any] = field(default_factory=dict)
    lgd_metrics: dict[str, Any] = field(default_factory=dict)
    challenger_metrics: dict[str, Any] = field(default_factory=dict)
    explain: dict[str, Any] = field(default_factory=dict)
    calibration: dict[str, Any] = field(default_factory=dict)
    grade_migration: dict[str, Any] = field(default_factory=dict)
    rwa_deep: Any = None       # v0.7.0 CRO-grade RWA deep-dive analytics
    bis_deep: Any = None       # v0.8.0 CRO-grade BIS capital deep-dive
    leverage_deep: Any = None  # v0.8.0 leverage ratio exposure decomposition
    ifrs9_deep: Any = None     # v0.9.0 CRO-grade IFRS9 ECL deep-dive analytics
    monitoring_deep: dict[str, Any] = field(default_factory=dict)  # v0.10.0
    limits_deep: Any = None    # v0.11.0 CRO-grade limit dashboard / LEX / stress
    concentration_hier: dict[str, Any] = field(default_factory=dict)  # v0.11.0
    rapm_deep: Any = None      # v0.12.0 CRO-grade RAPM deep-dive (Du Pont/EVA/pricing/scenarios)
    stress_deep: dict[str, Any] = field(default_factory=dict)  # v0.13.0 CRO-grade stress 부문
    meta: dict[str, Any] = field(default_factory=dict)


def _fit_segment_pd(portfolio: pd.DataFrame) -> tuple[
    pd.DataFrame, dict, dict, dict, dict, dict, dict,
]:
    """Fit champion (full features) + challenger (reduced features) PD models
    per segment, fit LGD model, compute explainability/calibration/PSI.

    Returns
    -------
    out            — portfolio with overwritten pd, grade.
    metrics        — champion variability + discrimination summary per segment.
    challenger     — challenger metrics + verdict per segment.
    lgd_metrics    — LGD backtest summary + bucket calibration per segment.
    explain        — coefficient_table + permutation_importance per segment.
    calibration    — master-scale calibration table per segment.
    grade_mig      — train vs test grade-level PSI per segment.
    """
    metrics: dict[str, dict[str, float]] = {}
    challenger: dict[str, dict[str, Any]] = {}
    lgd_metrics: dict[str, dict[str, Any]] = {}
    explain: dict[str, dict[str, Any]] = {}
    calibration: dict[str, pd.DataFrame] = {}
    grade_mig: dict[str, dict[str, Any]] = {}
    out = portfolio.copy()
    for seg, feats in _SEGMENT_FEATURES.items():
        mask = out["asset_class"] == seg
        seg_df = out[mask]
        if seg_df.empty:
            continue
        train, test = split_train_test(seg_df)
        ct = float(seg_df["default_12m"].mean())
        # ---- champion
        model = fit_pd_model(train, feats, target="default_12m",
                             central_tendency=ct)
        test_pd = model.recalibrate(model.predict_pd(test))
        disc = discrimination_summary(test["default_12m"].values, test_pd)
        metrics[seg] = {
            "gini": gini(test["default_12m"].values, test_pd),
            "ks": ks_statistic(test["default_12m"].values, test_pd),
            "auc_roc": disc["auc_roc"],
            "auprc": disc["auprc"],
            "brier": disc["brier"],
            "brier_skill": disc["brier_skill"],
            "n_train": float(len(train)),
            "n_test": float(len(test)),
        }
        # ---- challenger (subset features)
        ch_feats = _CHALLENGER_FEATURES.get(seg, feats[: max(1, len(feats) // 2)])
        ch_model = fit_pd_model(train, ch_feats, target="default_12m",
                                central_tendency=ct)
        ch_pd = ch_model.recalibrate(ch_model.predict_pd(test))
        ch_disc = discrimination_summary(test["default_12m"].values, ch_pd)
        delta_gini = metrics[seg]["gini"] - (2 * ch_disc["auc_roc"] - 1)
        verdict = "CHAMPION 우월" if delta_gini > 0.01 else (
            "CHALLENGER 우월" if delta_gini < -0.01 else "통계적 동등")
        challenger[seg] = {
            "features": ch_feats,
            "gini": 2 * ch_disc["auc_roc"] - 1,
            "auc_roc": ch_disc["auc_roc"],
            "auprc": ch_disc["auprc"],
            "brier": ch_disc["brier"],
            "delta_gini": float(delta_gini),
            "verdict": verdict,
        }
        # ---- explain (champion)
        explain[seg] = {
            "coefficients": coefficient_table(model),
            "permutation": permutation_importance(model, test, n_repeats=3,
                                                  seed=42),
        }
        # ---- LGD model (fit on train, score the full segment)
        lgd_feats = [f for f in _LGD_FEATURES.get(seg, []) if f in train.columns]
        if lgd_feats and "lgd_realized" in train.columns:
            lgd_m = fit_lgd_model(train, lgd_feats, target="lgd_realized",
                                  segment=seg)
            test_lgd_pred = lgd_m.predict_lgd(test)
            bt = lgd_backtest(test["lgd_realized"].values, test_lgd_pred)
            lgd_metrics[seg] = {
                "features": lgd_feats,
                "backtest": bt,
                "model": lgd_m,
                "predicted_full": lgd_m.predict_lgd(seg_df),
            }
        # ---- write back PD + grade for segment
        seg_pd = model.recalibrate(model.predict_pd(seg_df))
        out.loc[mask, "pd"] = seg_pd
        seg_grade = pd.Series([pd_to_rating(p).grade for p in seg_pd],
                              index=seg_df.index)
        # ---- master-scale calibration on test
        test_grade = pd.Series([pd_to_rating(p).grade for p in test_pd])
        calibration[seg] = master_scale_calibration(
            test_pd, test["default_12m"].values, test_grade,
        )
        # ---- grade migration PSI: train vs test grades
        train_pd = model.recalibrate(model.predict_pd(train))
        train_grade = pd.Series([pd_to_rating(p).grade for p in train_pd])
        grade_mig[seg] = grade_migration_psi(train_grade, test_grade)
        # write back computed grade so downstream is consistent
        out.loc[seg_df.index, "_seg_grade"] = seg_grade.values

    out["grade"] = [pd_to_rating(p).grade if pd.notna(p) else None
                    for p in out["pd"]]
    if "_seg_grade" in out.columns:
        out = out.drop(columns=["_seg_grade"])
    return (out, metrics, challenger, lgd_metrics, explain,
            calibration, grade_mig)


def _standardised_rwa_all(portfolio: pd.DataFrame) -> float:
    """Full-standardised RWA across the whole book (output-floor denominator).

    Thin wrapper kept for any in-tree callers; delegates to
    :func:`risk_lib.capital.rwa_sa.standardised_rwa_total`.
    """
    return standardised_rwa_total(portfolio, _SA_CORP_BUCKET_BY_GRADE)


def _stage_split_books(portfolio: pd.DataFrame):
    sa_book = portfolio[portfolio["asset_class"].isin(["sovereign", "bank"])].copy()
    irb_book = portfolio[portfolio["asset_class"].isin(
        ["corporate", "retail_other", "residential_mortgage"])].copy()
    return sa_book, irb_book


def _stage_credit_rwa(sa_book: pd.DataFrame, irb_book: pd.DataFrame):
    sa_res = compute_rwa_sa(sa_book)
    irb_res = compute_rwa_irb(irb_book)
    rwa_sa = float(sa_res["rwa"].sum())
    rwa_irb = float(irb_res["rwa"].sum())
    return sa_res, irb_res, rwa_sa, rwa_irb


def _stage_market_op_rwa(total_ead: float):
    mkt_positions = pd.DataFrame({
        "risk_class": ["fx", "equity", "interest_rate"],
        "net_position": [total_ead * 0.02, total_ead * 0.01, total_ead * 0.05],
    })
    mkt = compute_market_risk_rwa(mkt_positions)
    bi = BusinessIndicator(ildc=total_ead * 0.02, sc=total_ead * 0.01,
                           fc=total_ead * 0.005)
    op = compute_op_risk_rwa(bi, avg_annual_losses_10y=total_ead * 0.001)
    return mkt, op, mkt_positions, bi


def _stage_capital(
    portfolio, rwa_sa, rwa_irb, mkt, op, total_ead, *, output_floor, buffers,
    ccr=None, capital=None,
):
    """자본·비율·레버리지.

    독립검증 시정 3건이 여기 반영돼 있다:
      F-001  자본을 RWA에서 역산하지 않는다.
      F-101  익스포저에도 비례시키지 않는다 — 비례시키면 이번엔 레버리지비율이
             상수가 된다(실측 변동 1.4bp). 자본은 **입력**이며, 없을 때만
             수익성 기반 합성기를 쓴다.
      F-002  거래상대방신용리스크(SA-CCR)와 CVA를 신용 RWA에 합산한다.
             CRE52·MAR50이 RWA 포함을 요구하는데 산출만 하고 빠져 있었다.
      F-004  레버리지 익스포저에 파생상품(SA-CCR EAD)을 포함한다 (LEV20.1).
    """
    ccr_rwa = float(getattr(ccr, "rwa_total", 0.0) or 0.0)
    # CVA 소요자본은 자본 기준이 아니라 이미 RWA 환산치로 산출된다(ccr 모듈).
    cva_rwa = float(getattr(ccr, "cva_charge", 0.0) or 0.0)
    ccr_total = ccr_rwa + cva_rwa

    rwa_internal_total = rwa_sa + rwa_irb + ccr_total + mkt.rwa + op.rwa
    rwa_standardised_total = (
        standardised_rwa_total(portfolio, _SA_CORP_BUCKET_BY_GRADE)
        + ccr_total + mkt.rwa + op.rwa
    )
    floor = apply_output_floor(rwa_internal_total, rwa_standardised_total,
                               output_floor)
    rwa_final = floor.rwa_final
    if capital is None:
        annual_profit = float(portfolio["revenue"].sum()
                              - portfolio["operating_cost"].sum())
        capital = synthesise_capital(annual_profit)
    bis = compute_bis_ratios(capital, rwa_final, buffers=buffers)
    em = exposure_measure(on_balance=total_ead,
                          off_balance_notional=total_ead * 0.1,
                          derivatives=float(getattr(ccr, "ead_total", 0.0) or 0.0))
    leverage = compute_leverage_ratio(capital.tier1, em)
    return (floor, rwa_final, capital, bis, leverage,
            rwa_internal_total, rwa_standardised_total, ccr_total)


def _stage_provisioning(irb_book: pd.DataFrame, quarters: list[str],
                         *, seed: int = 42):
    ecl_df = compute_ecl(irb_book)
    ecl_by_stage = ecl_df.groupby("stage").agg(
        n=("exposure_id", "size"), ead=("ead", "sum"),
        ecl=("ecl", "sum"), coverage=("coverage_ratio", "mean"),
    )
    macro = macro_ecl(irb_book, DEFAULT_MACRO_SCENARIOS)
    macro_path = macro_ecl_path(irb_book, quarters, DEFAULT_MACRO_SCENARIOS)
    deep = compute_ifrs9_deep(irb_book, seed=seed)
    return ecl_df, ecl_by_stage, macro, macro_path, deep


def _stage_monitoring(portfolio: pd.DataFrame, seed: int):
    workouts = generate_workout_cashflows(portfolio, seed=seed + 11)
    delinq_deep = compute_delinquency_deep(portfolio, seed=seed)
    recovery_deep = compute_recovery_deep(portfolio, workouts, seed=seed)
    cure = compute_cure(portfolio, seed=seed)
    vintage_deep = compute_vintage_deep(portfolio, seed=seed)
    return {
        "delinquency": delinquency_summary(portfolio, segment_col="asset_class"),
        "default_rate_ew": default_rate(portfolio, weight_col="ead"),
        "default_rate_count": default_rate(portfolio),
        "recovery_rate": cumulative_recovery_rate(workouts),
        "workouts": workouts,
        "delinquency_deep": delinq_deep,
        "recovery_deep": recovery_deep,
        "cure": cure,
        "vintage_deep": vintage_deep,
    }


def _stage_limits_concentration(portfolio: pd.DataFrame, tier1: float):
    """Headline limit + HHI report.

    Backward-compatible signature; the CRO deep-dive uses
    :func:`compute_limits_deep` which is wired in via the limits_deep field.
    """
    limits = [
        LimitDefinition("동일차주_Tier1_25pct", "obligor_id", None,
                        0.25, basis="pct_tier1"),
        LimitDefinition("섹터_총노출_3조", "sector", None,
                        3.0e12, basis="absolute"),
        LimitDefinition("국가_총노출_5조", "country", None,
                        5.0e12, basis="absolute"),
    ]
    limit_report = LimitEngine(limits, tier1_capital=tier1).report(portfolio)
    conc = concentration_report(portfolio, ["obligor_id", "sector", "country"])
    return limit_report, conc


def _stage_rapm(irb_book: pd.DataFrame, hurdle_rate: float):
    rapm_input = irb_book[["exposure_id", "asset_class", "ead", "pd", "lgd",
                           "maturity", "revenue", "operating_cost"]]
    rapm = rapm_report(rapm_input, hurdle_rate=hurdle_rate)
    by_class = rapm.merge(
        rapm_input[["exposure_id", "asset_class"]], on="exposure_id",
    ).groupby("asset_class").agg(
        n=("exposure_id", "size"),
        ec=("economic_capital", "sum"),
        el=("expected_loss", "sum"),
        revenue=("revenue", "sum"),
        raroc_mean=("raroc", "mean"),
        pass_hurdle_pct=("pass_hurdle", "mean"),
    ).reset_index()
    return by_class


def _stage_alm(portfolio: pd.DataFrame, capital, seed: int) -> dict[str, Any]:
    """ALM 부문: 합성 재무상태표 → IRRBB / LCR / NSFR."""
    bs = generate_balance_sheet(portfolio, capital.total, seed=seed)
    return {
        "balance_sheet": bs,
        "irrbb": compute_irrbb(bs.repricing, capital.tier1),
        "lcr": compute_lcr(bs),
        "nsfr": compute_nsfr(bs),
    }


def _stage_icaap(
    sa_res: pd.DataFrame, irb_res: pd.DataFrame,
    mkt, op, alm: dict[str, Any], conc: pd.DataFrame, capital,
):
    """내부자본(ICAAP): 위험유형별 경제자본과 가용자본 대비 적정성."""
    credit_ec = float((irb_res["k"] * irb_res["ead"]).sum()
                      + sa_res["rwa"].sum() * 0.08)
    hhi = conc.set_index("dimension")["hhi"]
    return compute_icaap(
        credit_ec=credit_ec,
        market_ec=mkt.rwa * 0.08,
        op_ec=op.rwa * 0.08,
        irrbb_ec=alm["irrbb"].worst_eve_decline,
        hhi_sector=float(hhi.get("sector", 0.0)),
        hhi_country=float(hhi.get("country", 0.0)),
        available_capital=capital.total,
    )


# 미인출 약정 비율 — decompose가 쓰는 규칙(약정 보유 익스포저의 잔액 10~60%)의
# 기대값을 EAD 대비로 환산한 값. 실제 약정 원장이 있으면 그 값으로 대체된다.
UNDRAWN_SHARE = 0.18


def _stress_books(portfolio, irb_book, sa_book, capital, mkt_positions,
                  bi_components, op, op_loss_result, alm, total_ead,
                  ccr_rwa: float = 0.0):
    """전 축 충격 엔진의 기준 상태. 파이프라인이 이미 만든 값만 모은다."""
    from risk_lib.stress.multi_axis import StressBooks
    lcr = alm["lcr"]
    bs = alm["balance_sheet"]
    return StressBooks(
        irb=irb_book, sa=sa_book, full=portfolio, capital=capital,
        market_positions=mkt_positions, bi=bi_components,
        # OPE25.9 ILM은 10년 평균 손실을 쓴다 — 연간 손실을 그대로 넣으면
        # 손실승수가 과대해진다.
        op_losses_10y=total_ead * 0.001,
        op_loss_annual=float(getattr(op_loss_result, "annual_total", 0.0)),
        repricing=alm["irrbb"].repricing,
        hqla=dict(bs.hqla), lcr_outflows=lcr.outflows, lcr_inflows=lcr.inflows,
        revenue=float(portfolio["revenue"].sum()),
        operating_cost=float(portfolio["operating_cost"].sum()),
        credit_securities=float(bs.hqla["level_2a"] + bs.hqla["level_2b"]),
        ccr_rwa=float(ccr_rwa),
        undrawn_share=UNDRAWN_SHARE,
        sa_bucket_by_grade=_SA_CORP_BUCKET_BY_GRADE,
    )


def _stage_stress(
    irb_book, capital, rwa_other_fixed, bis, quarters, buffers, books=None,
):
    """전 축(신용·시장·운영·유동성·수익) 동시 충격 경로.

    `run_stress`(단일 시점 신용 충격)는 부문 비교용으로 남긴다. 경로와 역스트레스는
    전 축 엔진을 쓴다 — 신용만 충격하면 자본 저점이 낙관적으로 나온다.
    """
    from risk_lib.stress.multi_axis import (
        run_multi_axis_path, solve_critical_severity,
    )
    from risk_lib.stress.reverse import ReverseStressResult

    stress = run_stress(irb_book, capital, rwa_other_fixed,
                        scenarios=[BASELINE, ADVERSE, SEVERELY_ADVERSE],
                        buffers=buffers)
    if books is None:
        reverse = reverse_stress(
            irb_book, capital, rwa_other_fixed,
            metric="cet1", target_ratio=bis.required["cet1"],
            axis=StressAxis(), buffers=buffers,
        )
        stress_path = run_stress_path(irb_book, capital, rwa_other_fixed,
                                      quarters=quarters, axis=StressAxis(),
                                      buffers=buffers)
    else:
        target = bis.required["cet1"]
        sev, resilient = solve_critical_severity(
            books, metric="cet1", target_ratio=target, buffers=buffers)
        from risk_lib.stress.multi_axis import evaluate_point
        base_pt = evaluate_point(books, 0.0, buffers=buffers)
        pt = evaluate_point(books, sev, base=base_pt.values, buffers=buffers)
        sc = StressAxis().scenario_at(sev)
        reverse = ReverseStressResult(
            metric="cet1", target_ratio=target,
            base_ratio=float(base_pt.values["cet1_ratio"]),
            critical_severity=float(sev),
            resilient=bool(resilient),
            already_breached=bool(base_pt.values["cet1_ratio"] <= target),
            converged=not resilient,
            ratio_at_break=float(pt.values["cet1_ratio"]),
            rwa_total_at_break=float(pt.values["rwa_total"]),
            ecl_at_break=float(pt.values["ecl"]),
            implied_gdp_shock=float(pt.shocks["gdp"]),
            implied_lgd_addon=float(pt.shocks["lgd_addon"]),
            scenario=sc,
        )
        stress_path, _points = run_multi_axis_path(
            books, quarters=quarters, buffers=buffers)
    stress_path_trough = path_trough_summary(stress_path)
    return stress, reverse, stress_path, stress_path_trough


def _stage_stress_deep(
    irb_book, capital, rwa_other_fixed, bis, buffers, alm, stress_df,
):
    """CRO-grade stress 부문 (v0.13.0).

    구성:
      - macro narrative 표 + 시나리오 요약
      - factor-by-factor 분해 (PD/LGD/GDP) — adverse + severe
      - 자산군 sensitivity (adverse + severe)
      - multi-target reverse stress (CET1/Tier1/LCR/NSFR)
      - 3년 CCAR 분기 경로 + 자본 보충 액션
      - NGFS 기후 → 자본 30Y horizon
      - 유동성 stress + 회복 우선순위
      - 시나리오별 recovery plan 권고
      - scenario comparison 표
    """
    narrative_table = macro_table(MACRO_NARRATIVE_PATHS)
    narrative_text = narrative_summary(MACRO_NARRATIVE_PATHS)

    fac_adv = factor_decomposition(irb_book, capital, rwa_other_fixed,
                                    ADVERSE, buffers=buffers)
    fac_sev = factor_decomposition(irb_book, capital, rwa_other_fixed,
                                    SEVERELY_ADVERSE, buffers=buffers)
    ac_adv = asset_class_sensitivity(irb_book, capital, rwa_other_fixed,
                                      ADVERSE, buffers=buffers)
    ac_sev = asset_class_sensitivity(irb_book, capital, rwa_other_fixed,
                                      SEVERELY_ADVERSE, buffers=buffers)

    multi_rev = run_multi_reverse(
        irb_book, capital, rwa_other_fixed,
        base_lcr=alm["lcr"], base_nsfr=alm["nsfr"],
        axis=StressAxis(), buffers=buffers,
    )

    ccar = run_ccar(irb_book, capital, rwa_other_fixed,
                    axis=StressAxis(), buffers=buffers)

    climate_cap = run_climate_capital(irb_book, capital, rwa_other_fixed,
                                       buffers=buffers)

    liq_stress = run_liquidity_stress(alm["lcr"], alm["nsfr"])
    # LCR breach 시 회복 우선순위 (severe 시나리오 기준)
    sev_lcr = float(liq_stress.loc[
        liq_stress["scenario"] == "combined_severe", "lcr"].iloc[0])
    if sev_lcr < 1.0:
        shortfall = (1.0 - sev_lcr) * alm["lcr"].net_outflow
    else:
        shortfall = alm["lcr"].net_outflow * 0.10   # 10% buffer 시뮬레이션
    liq_ladder = recovery_priority_ladder(shortfall, alm["lcr"])

    rec_table = scenario_recovery_table(stress_df=stress_df, buffers=buffers)

    comparison = compare_scenarios(
        stress_df, base_lcr=alm["lcr"], base_nsfr=alm["nsfr"], buffers=buffers,
    )

    return {
        "narrative_table": narrative_table,
        "narrative_summary": narrative_text,
        "factor_decomp_adverse": fac_adv,
        "factor_decomp_severe": fac_sev,
        "asset_class_sens_adverse": ac_adv,
        "asset_class_sens_severe": ac_sev,
        "multi_reverse": multi_rev,
        "ccar": ccar,
        "climate_capital": climate_cap,
        "liquidity_stress": liq_stress,
        "liquidity_recovery_ladder": liq_ladder,
        "recovery_table": rec_table,
        "comparison": comparison,
    }


def run_pipeline(
    portfolio: pd.DataFrame | None = None,
    *,
    seed: int = 42,
    hurdle_rate: float = 0.10,
    output_floor: float = FULLY_LOADED_FLOOR,
    buffers: dict[str, float] | None = None,
    years_ahead: int = 2,
    asof: "date | str | None" = None,
    capital_ledger: CapitalStack | None = None,
) -> PipelineResult:
    """`capital_ledger`를 주면 실제 자본 원장으로 산출한다. 주지 않으면
    수익성 기반 합성기를 쓰며, 그 사실이 독립검증 요청에 공시된다."""
    if buffers is None:
        buffers = {"capital_conservation": 0.025, "countercyclical": 0.0, "dsib": 0.01}
    if portfolio is None:
        portfolio = generate_portfolio(seed=seed)

    # 1. PD models per segment + grades + challenger + LGD + XAI + calibration
    (portfolio, pd_metrics, challenger_metrics, lgd_metrics, explain,
     calibration, grade_migration) = _fit_segment_pd(portfolio)

    # 2. SA / IRB split + credit RWA
    sa_book, irb_book = _stage_split_books(portfolio)
    sa_res, irb_res, rwa_sa, rwa_irb = _stage_credit_rwa(sa_book, irb_book)
    rwa_credit_internal = rwa_sa + rwa_irb    # CCR은 _stage_capital에서 합산

    # 3. Market & operational risk RWA (illustrative inputs)
    total_ead = float(portfolio["ead"].sum())
    mkt, op, mkt_positions, bi_components = _stage_market_op_rwa(total_ead)

    # 3b. 거래상대방신용리스크 — RWA 합산과 레버리지 익스포저에 모두 쓰이므로
    # 자본 단계보다 먼저 만든다 (독립검증 F-002 · F-004).
    bank_book = portfolio[portfolio["asset_class"] == "bank"]
    ccr_result = compute_ccr(bank_book, seed=seed) if not bank_book.empty else None

    # 4-6. Output floor → CapitalStack → BIS → leverage
    (floor, rwa_final, capital, bis, leverage,
     rwa_internal_total, rwa_standardised_total, rwa_ccr) = _stage_capital(
        portfolio, rwa_sa, rwa_irb, mkt, op, total_ead,
        output_floor=output_floor, buffers=buffers, ccr=ccr_result,
        capital=capital_ledger,
    )

    # 7. IFRS 9 ECL (TTC + forward-looking PIT) on the quarterly axis.
    # `asof` is overridable so a run can be pinned to a reference date for
    # bit-for-bit reproducibility independent of wall-clock time.
    if asof is None:
        asof = date.today()
    elif isinstance(asof, str):
        asof = date.fromisoformat(asof)
    quarters = forecast_quarter_labels(asof, years_ahead=years_ahead)
    ecl_df, ecl_by_stage, macro, macro_path, ifrs9_deep = _stage_provisioning(
        irb_book, quarters, seed=seed)

    # 8-11. Monitoring, limits/concentration, RAPM
    monitoring = _stage_monitoring(portfolio, seed)
    limit_report, conc = _stage_limits_concentration(portfolio, capital.tier1)
    rapm_by_class = _stage_rapm(irb_book, hurdle_rate)
    rapm_deep_result = compute_rapm_deep(irb_book, hurdle_rate=hurdle_rate)

    # 12a. ALM (IRRBB / LCR / NSFR) — 전 축 위기상황분석이 재설정 사다리와
    # LCR 구성요소를 입력으로 쓰므로 스트레스보다 먼저 만든다.
    alm = _stage_alm(portfolio, capital, seed)

    # 12b. 운영손실 — 운영 축이 손실을 충격해 ILM으로 되돌리므로 역시 선행한다.
    op_loss_result = compute_op_loss(total_ead, seed=seed,
                                     sma_capital=op.rwa * 0.08)

    # 12c. Stress + reverse stress + quarterly capital path.  Hold non-IRB RWA
    # fixed at (rwa_final - rwa_irb) so baseline stress reconciles with BIS.
    rwa_other_fixed = rwa_final - rwa_irb
    books = _stress_books(portfolio, irb_book, sa_book, capital, mkt_positions,
                          bi_components, op, op_loss_result, alm, total_ead,
                          ccr_rwa=rwa_ccr)
    stress, reverse, stress_path, stress_path_trough = _stage_stress(
        irb_book, capital, rwa_other_fixed, bis, quarters, buffers, books,
    )

    # 13. 내부자본(ICAAP)
    icaap = _stage_icaap(sa_res, irb_res, mkt, op, alm, conc, capital)

    # 12b. CRO-grade stress 부문 (v0.13.0) — ALM 의존 (LCR/NSFR base 입력)
    stress_deep = _stage_stress_deep(
        irb_book, capital, rwa_other_fixed, bis, buffers, alm, stress,
    )

    # 14. CRO add-ons: RAF + climate + CCR + Op loss + concentration deep + model cards
    climate_result = run_climate(portfolio, base_ecl=float(ecl_df["ecl"].sum()))
    conc_deep = {
        "top_by_ead": top_obligors(portfolio, n=20, by="ead"),
        "top_by_risk": top_obligors(portfolio, n=20, by="risk_score")
                        if "pd" in portfolio.columns else top_obligors(portfolio, n=20),
        "sector_country": sector_country_matrix(portfolio),
        "large_exposure": large_exposure_test(portfolio, capital.tier1),
        "granularity_addon_rate": granularity_addon(portfolio),
    }
    # v0.11.0 — limit deep-dive + hierarchical HHI + wrong-way + Gini
    limits_deep_result = compute_limits_deep(portfolio, capital.tier1, seed=seed)
    obligor_ead = portfolio.groupby("obligor_id")["ead"].sum()
    concentration_hier = {
        "hierarchical_hhi": hierarchical_hhi(portfolio),
        "top_n": top_n_share_table(portfolio),
        "gini_obligor": gini_coefficient(obligor_ead.values),
        "lorenz_obligor": lorenz_curve(obligor_ead.values),
        "wrong_way": wrong_way_correlation(portfolio, seed=seed),
        "sector_correlation": sector_systemic_correlation(portfolio),
    }
    model_cards = build_model_cards(pd_metrics, backtest["hosmer_lemeshow"]) \
        if False else []   # populate after backtest below

    # 14-15. PD backtest + consolidated self-verification
    corp = portfolio[portfolio["asset_class"] == "corporate"]
    backtest = pd_backtest_report(corp, grade_col="grade",
                                  pd_col="pd", default_col="default_12m")
    validation = run_consistency_checks(
        sa_results=sa_res, irb_results=irb_res,
        bis_result=bis, rwa_total_for_bis=rwa_final,
        leverage_result=leverage, output_floor_result=floor,
        market_rwa=mkt.rwa, op_rwa=op.rwa,
        ecl_results=ecl_df, concentration=conc, stress_results=stress,
        macro_ecl_result=macro, reverse_stress_result=reverse,
        stress_path_result=stress_path,
        macro_ecl_path_result=macro_path,
        pd_metrics=pd_metrics,
        backtest=backtest,
        limit_report=limit_report,
        alm_results=alm,
        icaap_result=icaap,
        capital_source="ledger" if capital_ledger is not None else "synthetic",
        capital_stack=capital,
        total_ead=total_ead,
    )
    # v0.14.0 — cross-domain 정합성 (PD↔RWA, RWA↔BIS, ECL↔RWA,
    # 한도↔집중, RAPM↔EC, 스트레스↔BIS).  재현성 digest는 호출자가
    # 두 차례 실행을 비교하므로 여기서는 생략 (cross-domain test가 검증).
    for _xc in run_cross_domain_checks(
        rwa={"sa": rwa_sa, "irb": rwa_irb, "ccr": rwa_ccr,
             "market": mkt.rwa, "op": op.rwa,
             "final_total": rwa_final, "output_floor": floor},
        bis_result=bis,
        irb_results=irb_res,
        pd_metrics=pd_metrics,
        ecl_results=ecl_df,
        limit_report=limit_report,
        large_exposure=conc_deep.get("large_exposure"),
        rapm_by_class=rapm_by_class,
        stress_results=stress,
    ):
        validation.add(_xc)

    summary = portfolio.groupby("asset_class").agg(
        n=("exposure_id", "size"), ead=("ead", "sum"),
        default_rate=("default_12m", "mean"),
    ).reset_index()

    # 15. CRO insight layers (depend on the assembled headline numbers)
    # PipelineResult-shaped lightweight object so build_raf can read its fields.
    class _ResultShim:
        pass
    shim = _ResultShim()
    shim.bis = bis; shim.leverage = leverage; shim.alm = alm; shim.icaap = icaap
    shim.concentration = conc; shim.pd_metrics = pd_metrics
    shim.stress = stress; shim.rwa = {"final_total": rwa_final}
    raf = build_raf(shim)
    model_cards_real = build_model_cards(pd_metrics, backtest["hosmer_lemeshow"])

    # sensitivity needs the full result shape; build a shim that has the
    # right attributes for the closed-form sensitivities.
    shim.ecl = {"total": float(ecl_df["ecl"].sum()),
                "by_stage": ecl_by_stage}
    shim.rwa = {
        "sa": rwa_sa, "irb": rwa_irb, "market": mkt.rwa, "op": op.rwa,
        "final_total": rwa_final,
    }
    shim.meta = {"capital": capital}
    sens = {
        "one_factor": one_factor_grid(shim),
        "two_factor": two_factor_surface(shim),
    }
    attr = {
        "cet1_headroom": decompose_cet1_headroom(shim),
        "rwa_components": decompose_rwa(shim),
    }

    # 16. RWA deep-dive (CRO-grade): SA/IRB/market/op decomposition,
    # LGD downturn, FIRB simulation, VaR/SVaR, BIC bucket split, floor schedule.
    lda_var = float(getattr(op_loss_result, "var_99_9", 0.0) or 0.0)
    rwa_deep = compute_rwa_deep(
        sa_results=sa_res, irb_results=irb_res,
        sa_results_pre_crm=None,
        market_positions=mkt_positions, market_sa_result=mkt,
        bi=bi_components, op_sa_result=op,
        lda_var_999=lda_var,
        rwa_internal=rwa_internal_total,
        rwa_standardised=rwa_standardised_total,
    )

    # 17. BIS capital deep-dive (CRO-grade, v0.8.0):
    # CET1/AT1/T2 item-level decomposition, buffer layering (P1→CBR→P2R→P2G),
    # country-weighted CCyB, DSIB bucket, SREP/Pillar 2, MDA component breakdown,
    # forward-looking quarterly CET1 path.
    cet1_c, at1_c, t2_c = synthesise_components_from_stack(
        cet1_total=capital.cet1,
        at1_total=capital.additional_t1,
        tier2_total=capital.tier2,
        irb_rwa=rwa_irb,
    )
    # Jurisdictional exposure split for CCyB weighting (illustrative split
    # of portfolio EAD: KR-heavy domestic bank profile).
    exposures_by_country_synth = {
        "KR": float(portfolio["ead"].sum()) * 0.80,
        "US": float(portfolio["ead"].sum()) * 0.08,
        "JP": float(portfolio["ead"].sum()) * 0.05,
        "CN": float(portfolio["ead"].sum()) * 0.05,
        "VN": float(portfolio["ead"].sum()) * 0.02,
    }
    bis_deep = compute_bis_deep(
        cet1=cet1_c, at1=at1_c, tier2=t2_c, rwa=rwa_final,
        threshold_inputs={
            "dta_temporary_diff": capital.cet1 * 0.03,
            "msr": capital.cet1 * 0.01,
            "significant_investments": capital.cet1 * 0.02,
        },
        countercyclical=buffers.get("countercyclical", 0.0),
        dsib_bucket=2,                  # 가산 1.5% — KR 시중은행 가정
        p2r=0.015, p2g=0.010,            # SREP 가정
        exposures_by_country=exposures_by_country_synth,
        mda_request={
            "dividend": capital.cet1 * 0.012,
            "buyback": capital.cet1 * 0.006,
            "variable_comp": capital.cet1 * 0.004,
            "at1_coupon": capital.additional_t1 * 0.07 / 4,
        },
        # Forward 4Q assumptions
        quarterly_earnings=capital.cet1 * 0.10 / 4,
        quarterly_dividend=capital.cet1 * 0.012,
        quarterly_buyback=capital.cet1 * 0.006,
        rwa_growth_per_q=0.01,
    )

    # 18. Leverage deep-dive — exposure measure decomposition + G-SIB buffer.
    leverage_deep = compute_leverage_deep(
        tier1=capital.tier1,
        on_balance=total_ead,
        derivatives_replacement_cost=total_ead * 0.005,
        derivatives_pfe_notional=total_ead * 0.02,
        sft_gross=total_ead * 0.03,
        sft_collateral_offset=total_ead * 0.02,
        off_balance_notional=total_ead * 0.10,
        off_balance_ccf=0.20,
        gsib_bucket=None,   # KR domestic SIFI는 일반적으로 G-SIB 미해당
    )

    return PipelineResult(
        portfolio_summary=summary,
        pd_metrics=pd_metrics,
        rwa={
            "sa": rwa_sa, "irb": rwa_irb,
            "credit_internal": rwa_credit_internal + rwa_ccr,
            "ccr": rwa_ccr,
            "market": mkt.rwa, "op": op.rwa,
            "internal_total": rwa_internal_total,
            "standardised_total": rwa_standardised_total,
            "output_floor": floor, "final_total": rwa_final,
            "market_detail": mkt, "op_detail": op,
            # 전 축 위기상황분석이 시장 포지션을 다시 충격하므로 결과에 남긴다.
            "market_positions": mkt_positions,
            # BI 구성요소(ILDC/SC/FC)는 op_detail에 총액으로만 남는다 —
            # 사업부문별 자본배분과 업무보고서 라인은 구성요소가 있어야 한다.
            "bi_detail": bi_components,
        },
        bis=bis, leverage=leverage,
        ecl={"total": float(ecl_df["ecl"].sum()), "by_stage": ecl_by_stage},
        monitoring=monitoring,
        limits=limit_report, concentration=conc,
        rapm=rapm_by_class, stress=stress,
        macro_ecl=macro, reverse_stress=reverse,
        macro_ecl_path=macro_path,
        stress_path=stress_path, stress_path_trough=stress_path_trough,
        backtest=backtest, validation=validation,
        alm=alm, icaap=icaap,
        raf=raf, climate=climate_result, ccr=ccr_result,
        op_loss=op_loss_result, concentration_deep=conc_deep,
        model_cards=model_cards_real, sensitivity=sens, attribution=attr,
        lgd_metrics=lgd_metrics,
        challenger_metrics=challenger_metrics,
        explain=explain,
        calibration=calibration,
        grade_migration=grade_migration,
        rwa_deep=rwa_deep,
        bis_deep=bis_deep,
        leverage_deep=leverage_deep,
        ifrs9_deep=ifrs9_deep,
        monitoring_deep={
            "delinquency": monitoring.get("delinquency_deep"),
            "recovery": monitoring.get("recovery_deep"),
            "cure": monitoring.get("cure"),
            "vintage": monitoring.get("vintage_deep"),
            "workouts": monitoring.get("workouts"),
        },
        limits_deep=limits_deep_result,
        concentration_hier=concentration_hier,
        rapm_deep=rapm_deep_result,
        stress_deep=stress_deep,
        meta={"seed": seed, "capital": capital, "hurdle_rate": hurdle_rate,
              "asof": asof.isoformat(), "quarters": quarters},
    )
