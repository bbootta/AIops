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
from risk_lib.capital.rwa_sa import compute_rwa_sa, standardised_rwa_total
from risk_lib.capital.rwa_irb import compute_rwa_irb
from risk_lib.capital.bis import CapitalStack, compute_bis_ratios
from risk_lib.capital.op_risk import BusinessIndicator, compute_op_risk_rwa
from risk_lib.capital.market_risk import compute_market_risk_rwa
from risk_lib.capital.output_floor import apply_output_floor, FULLY_LOADED_FLOOR
from risk_lib.capital.leverage import compute_leverage_ratio, exposure_measure
from risk_lib.provisioning.ecl import compute_ecl
from risk_lib.provisioning.macro import macro_ecl, macro_ecl_path, DEFAULT_MACRO_SCENARIOS
from risk_lib.monitoring.delinquency import delinquency_summary, default_rate
from risk_lib.monitoring.recovery import cumulative_recovery_rate
from risk_lib.limits.limit_engine import LimitDefinition, LimitEngine
from risk_lib.limits.concentration import concentration_report
from risk_lib.performance.rapm import rapm_report
from risk_lib.stress.scenario import (
    run_stress, StressAxis, BASELINE, ADVERSE, SEVERELY_ADVERSE,
)
from risk_lib.stress.reverse import reverse_stress
from risk_lib.stress.path import (
    run_stress_path, path_trough_summary, forecast_quarter_labels,
)
from risk_lib.validation.consistency import run_consistency_checks
from risk_lib.validation.backtest import pd_backtest_report
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
    meta: dict[str, Any] = field(default_factory=dict)


def _fit_segment_pd(portfolio: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Fit a PD model per credit segment, overwrite pd, attach grade."""
    metrics: dict[str, dict[str, float]] = {}
    out = portfolio.copy()
    for seg, feats in _SEGMENT_FEATURES.items():
        mask = out["asset_class"] == seg
        seg_df = out[mask]
        if seg_df.empty:
            continue
        train, test = split_train_test(seg_df)
        model = fit_pd_model(train, feats, target="default_12m",
                             central_tendency=float(seg_df["default_12m"].mean()))
        test_pd = model.recalibrate(model.predict_pd(test))
        metrics[seg] = {
            "gini": gini(test["default_12m"].values, test_pd),
            "ks": ks_statistic(test["default_12m"].values, test_pd),
            "n_train": float(len(train)),
            "n_test": float(len(test)),
        }
        seg_pd = model.recalibrate(model.predict_pd(seg_df))
        out.loc[mask, "pd"] = seg_pd
    out["grade"] = [pd_to_rating(p).grade if pd.notna(p) else None
                    for p in out["pd"]]
    return out, metrics


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
    return mkt, op


def _stage_capital(
    portfolio, rwa_sa, rwa_irb, mkt, op, total_ead, *, output_floor, buffers,
):
    rwa_internal_total = rwa_sa + rwa_irb + mkt.rwa + op.rwa
    rwa_standardised_total = (
        standardised_rwa_total(portfolio, _SA_CORP_BUCKET_BY_GRADE)
        + mkt.rwa + op.rwa
    )
    floor = apply_output_floor(rwa_internal_total, rwa_standardised_total,
                               output_floor)
    rwa_final = floor.rwa_final
    capital = CapitalStack(
        cet1=rwa_final * 0.115,
        additional_t1=rwa_final * 0.015,
        tier2=rwa_final * 0.025,
    )
    bis = compute_bis_ratios(capital, rwa_final, buffers=buffers)
    em = exposure_measure(on_balance=total_ead, off_balance_notional=total_ead * 0.1)
    leverage = compute_leverage_ratio(capital.tier1, em)
    return (floor, rwa_final, capital, bis, leverage,
            rwa_internal_total, rwa_standardised_total)


def _stage_provisioning(irb_book: pd.DataFrame, quarters: list[str]):
    ecl_df = compute_ecl(irb_book)
    ecl_by_stage = ecl_df.groupby("stage").agg(
        n=("exposure_id", "size"), ead=("ead", "sum"),
        ecl=("ecl", "sum"), coverage=("coverage_ratio", "mean"),
    )
    macro = macro_ecl(irb_book, DEFAULT_MACRO_SCENARIOS)
    macro_path = macro_ecl_path(irb_book, quarters, DEFAULT_MACRO_SCENARIOS)
    return ecl_df, ecl_by_stage, macro, macro_path


def _stage_monitoring(portfolio: pd.DataFrame, seed: int):
    workouts = generate_workout_cashflows(portfolio, seed=seed + 11)
    return {
        "delinquency": delinquency_summary(portfolio, segment_col="asset_class"),
        "default_rate_ew": default_rate(portfolio, weight_col="ead"),
        "default_rate_count": default_rate(portfolio),
        "recovery_rate": cumulative_recovery_rate(workouts),
    }


def _stage_limits_concentration(portfolio: pd.DataFrame, tier1: float):
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


def _stage_stress(
    irb_book, capital, rwa_other_fixed, bis, quarters, buffers,
):
    stress = run_stress(irb_book, capital, rwa_other_fixed,
                        scenarios=[BASELINE, ADVERSE, SEVERELY_ADVERSE],
                        buffers=buffers)
    reverse = reverse_stress(
        irb_book, capital, rwa_other_fixed,
        metric="cet1", target_ratio=bis.required["cet1"],
        axis=StressAxis(), buffers=buffers,
    )
    stress_path = run_stress_path(irb_book, capital, rwa_other_fixed,
                                  quarters=quarters, axis=StressAxis(),
                                  buffers=buffers)
    stress_path_trough = path_trough_summary(stress_path)
    return stress, reverse, stress_path, stress_path_trough


def run_pipeline(
    portfolio: pd.DataFrame | None = None,
    *,
    seed: int = 42,
    hurdle_rate: float = 0.10,
    output_floor: float = FULLY_LOADED_FLOOR,
    buffers: dict[str, float] | None = None,
    years_ahead: int = 2,
) -> PipelineResult:
    if buffers is None:
        buffers = {"capital_conservation": 0.025, "countercyclical": 0.0, "dsib": 0.01}
    if portfolio is None:
        portfolio = generate_portfolio(seed=seed)

    # 1. PD models per segment + grades
    portfolio, pd_metrics = _fit_segment_pd(portfolio)

    # 2. SA / IRB split + credit RWA
    sa_book, irb_book = _stage_split_books(portfolio)
    sa_res, irb_res, rwa_sa, rwa_irb = _stage_credit_rwa(sa_book, irb_book)
    rwa_credit_internal = rwa_sa + rwa_irb

    # 3. Market & operational risk RWA (illustrative inputs)
    total_ead = float(portfolio["ead"].sum())
    mkt, op = _stage_market_op_rwa(total_ead)

    # 4-6. Output floor → CapitalStack → BIS → leverage
    (floor, rwa_final, capital, bis, leverage,
     rwa_internal_total, rwa_standardised_total) = _stage_capital(
        portfolio, rwa_sa, rwa_irb, mkt, op, total_ead,
        output_floor=output_floor, buffers=buffers,
    )

    # 7. IFRS 9 ECL (TTC + forward-looking PIT) on the quarterly axis
    asof = date.today()
    quarters = forecast_quarter_labels(asof, years_ahead=years_ahead)
    ecl_df, ecl_by_stage, macro, macro_path = _stage_provisioning(irb_book, quarters)

    # 8-11. Monitoring, limits/concentration, RAPM
    monitoring = _stage_monitoring(portfolio, seed)
    limit_report, conc = _stage_limits_concentration(portfolio, capital.tier1)
    rapm_by_class = _stage_rapm(irb_book, hurdle_rate)

    # 12. Stress + reverse stress + quarterly capital path.  Hold non-IRB RWA
    # fixed at (rwa_final - rwa_irb) so baseline stress reconciles with BIS.
    rwa_other_fixed = rwa_final - rwa_irb
    stress, reverse, stress_path, stress_path_trough = _stage_stress(
        irb_book, capital, rwa_other_fixed, bis, quarters, buffers,
    )

    # 13. ALM (IRRBB / LCR / NSFR) + 내부자본(ICAAP)
    alm = _stage_alm(portfolio, capital, seed)
    icaap = _stage_icaap(sa_res, irb_res, mkt, op, alm, conc, capital)

    # 14. CRO add-ons: RAF + climate + CCR + Op loss + concentration deep + model cards
    bank_book = portfolio[portfolio["asset_class"] == "bank"]
    ccr_result = compute_ccr(bank_book, seed=seed) if not bank_book.empty else None
    op_loss_result = compute_op_loss(total_ead, seed=seed,
                                     sma_capital=op.rwa * 0.08)
    climate_result = run_climate(portfolio, base_ecl=float(ecl_df["ecl"].sum()))
    conc_deep = {
        "top_by_ead": top_obligors(portfolio, n=20, by="ead"),
        "top_by_risk": top_obligors(portfolio, n=20, by="risk_score")
                        if "pd" in portfolio.columns else top_obligors(portfolio, n=20),
        "sector_country": sector_country_matrix(portfolio),
        "large_exposure": large_exposure_test(portfolio, capital.tier1),
        "granularity_addon_rate": granularity_addon(portfolio),
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
    )

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

    return PipelineResult(
        portfolio_summary=summary,
        pd_metrics=pd_metrics,
        rwa={
            "sa": rwa_sa, "irb": rwa_irb, "credit_internal": rwa_credit_internal,
            "market": mkt.rwa, "op": op.rwa,
            "internal_total": rwa_internal_total,
            "standardised_total": rwa_standardised_total,
            "output_floor": floor, "final_total": rwa_final,
            "market_detail": mkt, "op_detail": op,
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
        meta={"seed": seed, "capital": capital, "hurdle_rate": hurdle_rate,
              "asof": asof.isoformat(), "quarters": quarters},
    )
