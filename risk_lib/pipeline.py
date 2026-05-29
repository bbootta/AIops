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
from risk_lib.capital.rwa_sa import compute_rwa_sa, sa_risk_weight
from risk_lib.capital.rwa_irb import compute_rwa_irb
from risk_lib.capital.bis import CapitalStack, compute_bis_ratios
from risk_lib.capital.op_risk import BusinessIndicator, compute_op_risk_rwa
from risk_lib.capital.market_risk import compute_market_risk_rwa
from risk_lib.capital.output_floor import apply_output_floor, FULLY_LOADED_FLOOR
from risk_lib.capital.leverage import compute_leverage_ratio, exposure_measure
from risk_lib.provisioning.ecl import compute_ecl
from risk_lib.provisioning.macro import macro_ecl, DEFAULT_MACRO_SCENARIOS
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


# Per-segment PD model feature sets available in the synthetic data.
_SEGMENT_FEATURES = {
    "corporate": ["leverage", "current_ratio", "log_assets",
                  "interest_coverage", "gdp_growth"],
    "retail_other": ["dti", "utilization", "income_log", "months_employed"],
    "residential_mortgage": ["ltv", "dti"],
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
    reverse_stress: Any
    stress_path: pd.DataFrame
    stress_path_trough: pd.DataFrame
    backtest: dict[str, Any]
    validation: Any
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
    """Full-standardised RWA across the whole book (output-floor denominator)."""
    df = portfolio.copy()

    def _rw(row) -> float:
        ac = row["asset_class"]
        if ac in ("sovereign", "bank"):
            return sa_risk_weight(ac, row.get("rating", "UNRATED"))
        if ac == "corporate":
            bucket = _SA_CORP_BUCKET_BY_GRADE.get(row.get("grade"), "UNRATED")
            return sa_risk_weight("corporate", bucket)
        if ac == "retail_other":
            return sa_risk_weight("retail_regulatory")
        if ac == "residential_mortgage":
            return sa_risk_weight("residential_mortgage", ltv=row.get("ltv", 0.8))
        return 1.0

    return float((df["ead"] * df.apply(_rw, axis=1)).sum())


def run_pipeline(
    portfolio: pd.DataFrame | None = None,
    *,
    seed: int = 42,
    hurdle_rate: float = 0.10,
    output_floor: float = FULLY_LOADED_FLOOR,
    buffers: dict[str, float] | None = None,
) -> PipelineResult:
    if buffers is None:
        buffers = {"capital_conservation": 0.025, "countercyclical": 0.0, "dsib": 0.01}
    if portfolio is None:
        portfolio = generate_portfolio(seed=seed)

    # 1. PD models per segment + grades
    portfolio, pd_metrics = _fit_segment_pd(portfolio)

    # 2. Split SA vs IRB books
    sa_book = portfolio[portfolio["asset_class"].isin(["sovereign", "bank"])].copy()
    irb_book = portfolio[portfolio["asset_class"].isin(
        ["corporate", "retail_other", "residential_mortgage"])].copy()

    sa_res = compute_rwa_sa(sa_book)
    irb_res = compute_rwa_irb(irb_book)

    rwa_sa = float(sa_res["rwa"].sum())
    rwa_irb = float(irb_res["rwa"].sum())
    rwa_credit_internal = rwa_sa + rwa_irb

    # 3. Market & operational risk RWA (illustrative inputs)
    total_ead = float(portfolio["ead"].sum())
    mkt_positions = pd.DataFrame({
        "risk_class": ["fx", "equity", "interest_rate"],
        "net_position": [total_ead * 0.02, total_ead * 0.01, total_ead * 0.05],
    })
    mkt = compute_market_risk_rwa(mkt_positions)
    bi = BusinessIndicator(ildc=total_ead * 0.02, sc=total_ead * 0.01,
                           fc=total_ead * 0.005)
    op = compute_op_risk_rwa(bi, avg_annual_losses_10y=total_ead * 0.001)

    rwa_internal_total = rwa_credit_internal + mkt.rwa + op.rwa

    # 4. Output floor (full-standardised credit RWA + market + op)
    rwa_sa_credit_all = _standardised_rwa_all(portfolio)
    rwa_standardised_total = rwa_sa_credit_all + mkt.rwa + op.rwa
    floor = apply_output_floor(rwa_internal_total, rwa_standardised_total, output_floor)
    rwa_final = floor.rwa_final

    # 5. Capital & BIS
    capital = CapitalStack(
        cet1=rwa_final * 0.115,
        additional_t1=rwa_final * 0.015,
        tier2=rwa_final * 0.025,
    )
    bis = compute_bis_ratios(capital, rwa_final, buffers=buffers)

    # 6. Leverage ratio
    em = exposure_measure(on_balance=total_ead, off_balance_notional=total_ead * 0.1)
    leverage = compute_leverage_ratio(capital.tier1, em)

    # 7. IFRS 9 ECL — TTC (point estimate) + forward-looking PIT (probability-weighted)
    ecl_df = compute_ecl(irb_book)
    ecl_by_stage = ecl_df.groupby("stage").agg(
        n=("exposure_id", "size"), ead=("ead", "sum"),
        ecl=("ecl", "sum"), coverage=("coverage_ratio", "mean"),
    )
    macro = macro_ecl(irb_book, DEFAULT_MACRO_SCENARIOS)

    # 8. Monitoring
    delq = delinquency_summary(portfolio, segment_col="asset_class")
    workouts = generate_workout_cashflows(portfolio, seed=seed + 11)
    monitoring = {
        "delinquency": delq,
        "default_rate_ew": default_rate(portfolio, weight_col="ead"),
        "default_rate_count": default_rate(portfolio),
        "recovery_rate": cumulative_recovery_rate(workouts),
    }

    # 9. Limits
    limits = [
        LimitDefinition("동일차주_Tier1_25pct", "obligor_id", None, 0.25, basis="pct_tier1"),
        LimitDefinition("섹터_총노출_3조", "sector", None, 3.0e12, basis="absolute"),
        LimitDefinition("국가_총노출_5조", "country", None, 5.0e12, basis="absolute"),
    ]
    engine = LimitEngine(limits, tier1_capital=capital.tier1)
    limit_report = engine.report(portfolio)

    # 10. Concentration
    conc = concentration_report(portfolio, ["obligor_id", "sector", "country"])

    # 11. RAPM
    rapm_input = irb_book[["exposure_id", "asset_class", "ead", "pd", "lgd",
                           "maturity", "revenue", "operating_cost"]]
    rapm = rapm_report(rapm_input, hurdle_rate=hurdle_rate)
    rapm_by_class = rapm.merge(
        rapm_input[["exposure_id", "asset_class"]], on="exposure_id",
    ).groupby("asset_class").agg(
        n=("exposure_id", "size"),
        ec=("economic_capital", "sum"),
        el=("expected_loss", "sum"),
        revenue=("revenue", "sum"),
        raroc_mean=("raroc", "mean"),
        pass_hurdle_pct=("pass_hurdle", "mean"),
    ).reset_index()

    # 12. Stress (forward) + reverse stress (solve for the breaking severity)
    # Hold everything except IRB RWA fixed: SA credit + market + op + any output-
    # floor add-on.  Using rwa_final - rwa_irb keeps the baseline stress RWA equal
    # to the reported (post-floor) rwa_final, so stress ratios reconcile with BIS.
    rwa_other_fixed = rwa_final - rwa_irb
    stress = run_stress(irb_book, capital, rwa_other_fixed,
                        scenarios=[BASELINE, ADVERSE, SEVERELY_ADVERSE],
                        buffers=buffers)
    # break point = buffer-inclusive CET1 requirement (MDA/buffer-breach trigger)
    reverse = reverse_stress(
        irb_book, capital, rwa_other_fixed,
        metric="cet1", target_ratio=bis.required["cet1"],
        axis=StressAxis(), buffers=buffers,
    )
    # quarterly projection through end of asof.year + 2 (e.g. 2026Q3..2028Q4)
    asof = date.today()
    quarters = forecast_quarter_labels(asof, years_ahead=2)
    stress_path = run_stress_path(irb_book, capital, rwa_other_fixed,
                                  quarters=quarters, axis=StressAxis(),
                                  buffers=buffers)
    stress_path_trough = path_trough_summary(stress_path)

    # 13. Self-verification
    validation = run_consistency_checks(
        sa_results=sa_res, irb_results=irb_res,
        bis_result=bis, rwa_total_for_bis=rwa_final,
        leverage_result=leverage, output_floor_result=floor,
        market_rwa=mkt.rwa, op_rwa=op.rwa,
        ecl_results=ecl_df, concentration=conc, stress_results=stress,
        macro_ecl_result=macro, reverse_stress_result=reverse,
        stress_path_result=stress_path,
    )

    corp = portfolio[portfolio["asset_class"] == "corporate"]
    backtest = pd_backtest_report(corp, grade_col="grade",
                                  pd_col="pd", default_col="default_12m")

    summary = portfolio.groupby("asset_class").agg(
        n=("exposure_id", "size"), ead=("ead", "sum"),
        default_rate=("default_12m", "mean"),
    ).reset_index()

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
        stress_path=stress_path, stress_path_trough=stress_path_trough,
        backtest=backtest, validation=validation,
        meta={"seed": seed, "capital": capital, "hurdle_rate": hurdle_rate,
              "asof": asof.isoformat(), "quarters": quarters},
    )
