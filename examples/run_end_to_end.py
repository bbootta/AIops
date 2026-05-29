"""End-to-end demo: PD model → RWA(SA+IRB) → BIS → limits → RAPM → validation."""

from __future__ import annotations

import pandas as pd

from risk_lib.data_gen import (
    generate_portfolio, split_train_test, generate_workout_cashflows,
)
from risk_lib.models.pd_model import fit_pd_model, gini, ks_statistic
from risk_lib.models.rating import pd_to_rating
from risk_lib.capital.rwa_sa import compute_rwa_sa
from risk_lib.capital.rwa_irb import compute_rwa_irb
from risk_lib.capital.bis import CapitalStack, compute_bis_ratios
from risk_lib.monitoring.delinquency import delinquency_summary, default_rate
from risk_lib.monitoring.recovery import cumulative_recovery_rate, recovery_curve
from risk_lib.limits.limit_engine import LimitDefinition, LimitEngine
from risk_lib.performance.rapm import rapm_report
from risk_lib.validation.consistency import run_consistency_checks
from risk_lib.validation.backtest import pd_backtest_report


pd.set_option("display.float_format", lambda v: f"{v:,.4f}")


def main() -> None:
    print("=" * 70)
    print("STEP 1. 합성 포트폴리오 생성")
    print("=" * 70)
    portfolio = generate_portfolio()
    print(portfolio.groupby("asset_class").agg(
        n=("exposure_id", "size"),
        ead_total=("ead", "sum"),
        default_rate=("default_12m", "mean"),
    ))

    print("\n" + "=" * 70)
    print("STEP 2. 신용평가모형(PD) 학습 - corporate 세그먼트 예시")
    print("=" * 70)
    corp = portfolio[portfolio["asset_class"] == "corporate"].copy()
    train, test = split_train_test(corp)
    features = ["leverage", "current_ratio", "log_assets",
                "interest_coverage", "gdp_growth"]
    pd_model = fit_pd_model(
        train, features, target="default_12m",
        central_tendency=float(train["default_12m"].mean()),
    )
    test_pd = pd_model.predict_pd(test)
    test_pd = pd_model.recalibrate(test_pd)
    print(f"  Test Gini : {gini(test['default_12m'].values, test_pd):.3f}")
    print(f"  Test KS   : {ks_statistic(test['default_12m'].values, test_pd):.3f}")

    # Map predicted PDs back to internal grade for corp portfolio
    corp_pd = pd_model.recalibrate(pd_model.predict_pd(corp))
    corp["pd"] = corp_pd
    corp["grade"] = [pd_to_rating(p).grade for p in corp_pd]

    print("\n" + "=" * 70)
    print("STEP 3. RWA 산출 - 표준방법(SA) 및 내부등급법(IRB)")
    print("=" * 70)
    sa_assets = portfolio[portfolio["asset_class"].isin(["sovereign", "bank"])].copy()
    sa_res = compute_rwa_sa(sa_assets)
    print(f"  SA RWA total      : {sa_res['rwa'].sum():>20,.0f}")

    irb_assets = pd.concat([
        corp[["exposure_id", "asset_class", "ead", "pd", "lgd", "maturity",
              "obligor_id", "sector", "country"]],
        portfolio[portfolio["asset_class"].isin(
            ["retail_other", "residential_mortgage"]
        )][["exposure_id", "asset_class", "ead", "pd", "lgd", "maturity",
            "obligor_id", "sector", "country"]],
    ], ignore_index=True)
    irb_res = compute_rwa_irb(irb_assets)
    print(f"  IRB RWA total     : {irb_res['rwa'].sum():>20,.0f}")
    print(f"  IRB Expected Loss : {irb_res['el'].sum():>20,.0f}")

    rwa_credit = sa_res["rwa"].sum() + irb_res["rwa"].sum()
    rwa_market = 1.5e12   # placeholder (시장리스크)
    rwa_op = 2.0e12       # placeholder (운영리스크)
    rwa_total = rwa_credit + rwa_market + rwa_op
    print(f"  Credit RWA        : {rwa_credit:>20,.0f}")
    print(f"  + Market+Op RWA   : {rwa_market + rwa_op:>20,.0f}")
    print(f"  = Total RWA       : {rwa_total:>20,.0f}")

    print("\n" + "=" * 70)
    print("STEP 4. BIS비율 산출")
    print("=" * 70)
    capital = CapitalStack(
        cet1=rwa_total * 0.115,
        additional_t1=rwa_total * 0.015,
        tier2=rwa_total * 0.025,
    )
    bis = compute_bis_ratios(
        capital, rwa_total,
        buffers={"capital_conservation": 0.025, "countercyclical": 0.0, "dsib": 0.01},
    )
    print(f"  CET1 ratio  : {bis.cet1_ratio:>7.2%}  (요구 {bis.required['cet1']:>6.2%})")
    print(f"  Tier1 ratio : {bis.tier1_ratio:>7.2%}  (요구 {bis.required['tier1']:>6.2%})")
    print(f"  Total ratio : {bis.total_ratio:>7.2%}  (요구 {bis.required['total']:>6.2%})")
    print(f"  자본적정성 : {'PASS' if bis.passes() else 'FAIL'}")

    print("\n" + "=" * 70)
    print("STEP 5. 연체율 / 부도율 / 회수율")
    print("=" * 70)
    delq = delinquency_summary(portfolio, segment_col="asset_class")
    print(delq.to_string(index=False))
    print(f"\n  연간 부도율 (exposure-weighted) : "
          f"{default_rate(portfolio, weight_col='ead'):.4%}")
    workouts = generate_workout_cashflows(portfolio)
    print(f"  포트폴리오 누적회수율           : "
          f"{cumulative_recovery_rate(workouts):.4%}")

    print("\n" + "=" * 70)
    print("STEP 6. 한도관리")
    print("=" * 70)
    limits = [
        LimitDefinition("동일차주_Tier1_25pct", "obligor_id", None,
                        0.25, basis="pct_tier1"),
        LimitDefinition("동일인_Tier1_20pct", "obligor_id", None,
                        0.20, basis="pct_tier1"),
        LimitDefinition("섹터_총노출_3조", "sector", None,
                        3.0e12, basis="absolute"),
        LimitDefinition("국가_총노출_5조", "country", None,
                        5.0e12, basis="absolute"),
    ]
    engine = LimitEngine(limits, tier1_capital=capital.tier1)
    breaches = engine.report(portfolio)
    if breaches.empty:
        print("  모든 한도 정상")
    else:
        print(breaches.head(20).to_string(index=False))

    print("\n" + "=" * 70)
    print("STEP 7. RAPM (RAROC)")
    print("=" * 70)
    rapm_input = pd.concat([
        corp[["exposure_id", "asset_class", "ead", "pd", "lgd",
              "maturity", "revenue", "operating_cost"]],
        portfolio[portfolio["asset_class"].isin(
            ["retail_other", "residential_mortgage"]
        )][["exposure_id", "asset_class", "ead", "pd", "lgd",
            "maturity", "revenue", "operating_cost"]],
    ], ignore_index=True)
    rapm = rapm_report(rapm_input, hurdle_rate=0.10)
    by_class = rapm.merge(
        rapm_input[["exposure_id", "asset_class"]], on="exposure_id",
    ).groupby("asset_class").agg(
        n=("exposure_id", "size"),
        ec=("economic_capital", "sum"),
        el=("expected_loss", "sum"),
        revenue=("revenue", "sum"),
        raroc_weighted=("raroc", "mean"),
        pass_hurdle_pct=("pass_hurdle", "mean"),
    )
    print(by_class)

    print("\n" + "=" * 70)
    print("STEP 8. 자체검증 (정합성 + PD 백테스트)")
    print("=" * 70)
    report = run_consistency_checks(
        sa_results=sa_res, irb_results=irb_res,
        bis_result=bis, rwa_total_for_bis=rwa_total,
    )
    print(f"  Consistency summary: {report.summary()}")
    print(f"  Overall pass       : {report.passes()}")

    bt = pd_backtest_report(corp, grade_col="grade",
                            pd_col="pd", default_col="default_12m")
    print(f"  HL test: chi2={bt['hosmer_lemeshow']['chi_square']:.2f}, "
          f"p={bt['hosmer_lemeshow']['p_value']:.3f}")
    print("  Per-grade backtest (top 8):")
    print(bt["per_grade"].head(8).to_string(index=False))


if __name__ == "__main__":
    main()
