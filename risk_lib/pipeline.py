"""End-to-end risk pipeline wiring every module together.

Order: data → PD models → CRM/CCF → RWA(SA+IRB) → market/op RWA →
       output floor → BIS → leverage → IFRS9 ECL → limits → concentration →
       RAPM → stress → self-verification.

Returns a structured `PipelineResult` consumed by report.py / cli.py.
"""

from __future__ import annotations

import warnings as warnings_mod
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping, Sequence

import numpy as np
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
from risk_lib.alm.lcr import compute_lcr
from risk_lib.alm.nsfr import compute_nsfr
from risk_lib.icaap.economic_capital import compute_icaap
from risk_lib.appetite import build_raf
from risk_lib.climate import run_climate
from risk_lib.ccr import compute_ccr, cva_rwa as _cva_rwa
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
    # ALM 원장(계수·계약·현금흐름·곡선·IRRBB·유동성) — 실체화가 이 프레임을
    # 그대로 받는다. 화면이 산출 객체에서 다시 만들면 원장과 화면이 갈라진다.
    alm_tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    # 신규 요건 원장(거시 마스터·한도 정의·별표 9의1 국내 고유·LGD/CCF 실측검증·
    # 내부등급법 추정·신용평가·CRM 배분·거액익스포져·행동모형·통제 원장).
    # `alm_tables`와 같은 규약이다. 산출은 여기서 한 번만 돌고, 화면·검증은
    # 그 프레임을 받는다. 화면이 같은 빌더를 다시 부르면 두 벌이 된다.
    ledger_tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    # 원장 산출이 근거 부족으로 건너뛴 항목. 집계만 보고 "이상 없음"이라
    # 읽지 않도록 결과에 남긴다.
    ledger_warnings: list[str] = field(default_factory=list)
    # RDM 분해 결과. 파이프라인이 한 번 돌리고 실체화 엔진이 그대로 받는다.
    rdm_base: dict[str, pd.DataFrame] = field(default_factory=dict)
    icaap: Any = None
    # 한도 소진율 전량(위반 아닌 버킷 포함) — 화면용. 위반 보고서와 별개다.
    limits_full: pd.DataFrame | None = None
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
    # 구조화 원장(집합투자증권·유동화) — 자본비율 분모에 들어간 바로 그 원장이다.
    # 화면이 따로 만들면 분모와 화면이 다른 실행을 설명하게 된다.
    structured: Any = None
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


# 외부등급 → 장기 부도율(합성, S&P 장기 코호트 수준) — SA북 IFRS 9 충당금용.
# 내부 PD 모형은 IRB 세그먼트만 적합하므로 SA북은 외부등급 기반이 정본이다.
_SA_RATING_PD = {"AAA-AA": 0.0003, "A": 0.0008, "BBB": 0.0026,
                 "BB": 0.0110, "B": 0.0450, "CCC": 0.1800, "UNRATED": 0.0110}
_SA_SUPERVISORY_LGD = 0.45          # CRE32 — 선순위 무담보 감독 LGD


def _fill_sa_parameters(portfolio: pd.DataFrame) -> pd.DataFrame:
    """SA북(sovereign·bank)의 PD·LGD 를 세운다 — ECL 전 필수 선행.

    이전에는 SA북 PD·LGD 가 NaN 인 채로 남았고, 전 포트폴리오 ECL 합이
    NaN 을 조용히 무시했다 — SA북 충당금이 0도 아니고 '없음'이었다.
    조용한 NaN 은 조용한 절단과 같은 결함이다.
    """
    out = portfolio.copy()
    mask = out["pd"].isna()
    out.loc[mask, "pd"] = out.loc[mask, "rating"].map(_SA_RATING_PD)
    out.loc[out["lgd"].isna(), "lgd"] = _SA_SUPERVISORY_LGD
    assert not out["pd"].isna().any(), "PD가 비어 있는 익스포저가 남았다"
    return out


# 접근법별 자산군 — 이 목록에 없는 자산군은 어느 북에도 들어가지 않는다.
# 합성 데이터에서는 생길 수 없지만 실데이터에서는 생기며, 그때 그 익스포저는
# RWA에서 **소리 없이 사라진다**. 목록을 한 곳에 두고 완전성 대사가 이것을 본다.
SA_ASSET_CLASSES = ("sovereign", "bank")
IRB_ASSET_CLASSES = ("corporate", "retail_other", "residential_mortgage")


def unbooked_exposures(portfolio: pd.DataFrame) -> pd.DataFrame:
    """SA·IRB 어느 북에도 들어가지 않는 익스포저 — 조용한 유실의 실물."""
    known = set(SA_ASSET_CLASSES) | set(IRB_ASSET_CLASSES)
    return portfolio[~portfolio["asset_class"].isin(known)]


def _stage_split_books(portfolio: pd.DataFrame):
    sa_book = portfolio[portfolio["asset_class"].isin(SA_ASSET_CLASSES)].copy()
    irb_book = portfolio[portfolio["asset_class"].isin(IRB_ASSET_CLASSES)].copy()
    return sa_book, irb_book


def _stage_credit_rwa(sa_book: pd.DataFrame, irb_book: pd.DataFrame):
    sa_res = compute_rwa_sa(sa_book)
    irb_res = compute_rwa_irb(irb_book)
    rwa_sa = float(sa_res["rwa"].sum())
    rwa_irb = float(irb_res["rwa"].sum())
    return sa_res, irb_res, rwa_sa, rwa_irb


def _stage_market_op_rwa(seed: int, params: "Mapping[str, float]"):
    """시장·운영 RWA — 신용 포트폴리오와 **독립**이다(전용 시드 스트림).

    이전에는 트레이딩 명목과 영업지표(BI)를 신용 EAD 합에 비례시켰다.
    그러면 신용 익스포저가 움직일 때마다 시장·운영 RWA가 따라 움직인다 —
    실제 원천은 서로 다르다(트레이딩 북·손익 지표). 도메인 병렬 산출의
    전제가 이 독립성이므로, 규모감만 같은 합성 명목을 독립 시드로 만든다.

    명목 규모와 위험군·BI 구성비는 `params` 로 받는다. 기관마다 트레이딩
    비중이 다른데 본문에 수를 두면 어느 기관을 돌려도 같은 시장 RWA가 나온다.
    값의 출처는 `data_gen_intl.INST_PROFILE` 한 곳뿐이다.
    """
    rng = np.random.default_rng(seed + 7100)
    # 총자산 규모감(합성) — 신용 EAD가 아니라 독립 기준이다.
    notional = float(params["mkt_notional_base"]) * float(rng.uniform(0.95, 1.05))
    mkt_positions = pd.DataFrame({
        "risk_class": ["fx", "equity", "interest_rate"],
        "net_position": [notional * float(params["share_fx"]),
                         notional * float(params["share_equity"]),
                         notional * float(params["share_ir"])],
    })
    mkt = compute_market_risk_rwa(mkt_positions)
    bi = BusinessIndicator(ildc=notional * float(params["share_bi_ildc"]),
                           sc=notional * float(params["share_bi_sc"]),
                           fc=notional * float(params["share_bi_fc"]))
    op = compute_op_risk_rwa(
        bi, avg_annual_losses_10y=notional * float(params["op_loss_rate"]))
    return mkt, op, mkt_positions, bi, notional


@dataclass
class StructuredRWA:
    """집합투자증권(CRE60)·유동화(CRE40) 위험가중자산 — 신용 RWA의 일부다.

    두 원장은 은행계정 익스포저(`rdm_exposure`)와 **모집단이 겹치지 않는다**.
    포트폴리오의 자산군은 sovereign·bank·corporate·retail_other·
    residential_mortgage 다섯이며 펀드 수익증권도 유동화 트렌치도 여기 없다.
    그러므로 합산은 이중계상이 아니라 **누락의 시정**이다.

    산출만 하고 분모에 넣지 않으면 자본비율이 실제보다 좋게 나온다 — 4.13조가
    빠진 분모는 CET1을 약 3.5%p 부풀린다. 원장에 값이 있는데 비율에 반영되지
    않는 것은 "보수적"이 아니라 틀린 것이다.

    표준방법 총계(output floor 비교용)에는 SEC-IRBA를 쓰지 않는다 — 내부모형
    기반 접근법이므로 floor의 비교 대상이 될 수 없다 (CRE40 · RBC20.11).
    집합투자증권은 LTA·MBA 모두 기초자산에 **표준방법 위험가중치**를 적용하므로
    (CRE60.5·60.7) 내부·표준 총계가 같다.
    """
    fund_rwa: float                 # 채택 방법 (LTA/MBA/fallback) — 내부·표준 동일
    sec_rwa_internal: float         # 채택 계층 (IRBA→ERBA→SA)
    sec_rwa_standardised: float     # IRBA 제외 계층 (ERBA→SA)
    exposure: float                 # 레버리지 익스포저용 장부 익스포저
    tables: dict[str, pd.DataFrame]

    @property
    def rwa_internal(self) -> float:
        return self.fund_rwa + self.sec_rwa_internal

    @property
    def rwa_standardised(self) -> float:
        return self.fund_rwa + self.sec_rwa_standardised


def _stage_structured(asof: "date", seed: int,
                      scale: "Mapping[str, float]") -> StructuredRWA:
    """집합투자증권·유동화 원장을 세우고 RWA를 뽑는다.

    신용·시장운영·CCR 어느 갈래의 산출물도 쓰지 않으므로 네 번째 병렬 갈래다.
    원장 생성은 (asof, seed) 로 결정론적이다.

    `scale` 은 기관 프로파일 원장의 금액 배수(`fund_scale`·`sec_scale`)다.
    이전에는 (asof, seed) 만 받았으므로 기관이 바뀌어도 규모가 같은 구조화
    블록이 붙었고, 그 블록이 최종 RWA 의 19~31% 였다. 시드가 다르니 값은
    달랐지만 규모감은 국내 표본 그대로였다. 배수를 본문에 두지 않고 원장에서
    받는 이유는 다른 모수와 같다.
    """
    from risk_lib.datamodel.funds import build_funds
    from risk_lib.datamodel.securitisation import build_securitisation

    asof_s = asof.isoformat()
    tables = build_funds(asof=asof_s, seed=seed,
                         scale=float(scale["fund_scale"]))
    tables.update(build_securitisation(asof=asof_s, seed=seed,
                                       scale=float(scale["sec_scale"])))

    fund = tables["rwa_fund_result"]
    sec = tables["rwa_sec_result"]
    # ERBA 가 없는 트렌치는 SEC-SA 로 내려간다. `erba_available` 를 보지 않고
    # rwa_erba 를 그냥 더하면 미산출분(0)이 조용히 섞여 표준 총계가 작아진다.
    sec_std = sec["rwa_erba"].where(sec["erba_available"], sec["rwa_sa"])
    return StructuredRWA(
        fund_rwa=float(fund["adopted_rwa"].sum()),
        sec_rwa_internal=float(sec["adopted_rwa"].sum()),
        sec_rwa_standardised=float(sec_std.sum()),
        exposure=float(fund["investment"].sum() + sec["holding_amount"].sum()),
        tables=tables,
    )


def _stage_capital(
    portfolio, rwa_sa, rwa_irb, mkt, op, total_ead, *, output_floor, buffers,
    ccr=None, capital=None, irb_el: float = 0.0,
    eligible_provisions: float = 0.0, structured: "StructuredRWA | None" = None,
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

    구조화 익스포저(집합투자증권 CRE60 · 유동화 CRE40)도 여기서 합산한다.
    원장은 있는데 분모에 들어가지 않아 자본비율이 부풀려져 있었다 —
    RWA 는 BIS 분모에, 장부 익스포저는 레버리지 익스포저에 함께 넣는다.
    한쪽만 넣으면 두 비율이 서로 다른 은행을 설명하게 된다.
    """
    ccr_rwa = float(getattr(ccr, "rwa_total", 0.0) or 0.0)
    # CVA는 **소요자기자본(K_BA)** 으로 산출되므로 RWA에 합산하려면 12.5배
    # 환산해야 한다 (MAR50.2 · RBC20.6). 이전 주석은 "이미 RWA 환산치"라고
    # 적었으나 ccr 모듈의 반환 기준과 반대였고, 그 결과 CVA가 12.5배 과소
    # 계상되고 있었다 — 서식 저작 중 적대적 검토에서 드러났다. 근거 없는
    # 주석 한 줄이 산출을 조용히 틀리게 하는 전형이다.
    cva_rwa_amount = _cva_rwa(float(getattr(ccr, "cva_charge", 0.0) or 0.0))
    ccr_total = ccr_rwa + cva_rwa_amount

    str_internal = structured.rwa_internal if structured else 0.0
    str_standardised = structured.rwa_standardised if structured else 0.0
    rwa_internal_total = (rwa_sa + rwa_irb + ccr_total + mkt.rwa + op.rwa
                          + str_internal)
    rwa_standardised_total = (
        standardised_rwa_total(portfolio, _SA_CORP_BUCKET_BY_GRADE)
        + ccr_total + mkt.rwa + op.rwa + str_standardised
    )
    floor = apply_output_floor(rwa_internal_total, rwa_standardised_total,
                               output_floor)
    rwa_final = floor.rwa_final
    if capital is None:
        annual_profit = float(portfolio["revenue"].sum()
                              - portfolio["operating_cost"].sum())
        capital = synthesise_capital(annual_profit)

    # IRB 기대손실 > 적격충당금이면 그 차액을 보통주자본에서 차감한다
    # (CRE35.3 · CRE40.11). 초과충당금은 IRB 신용 RWA의 0.6% 한도로 보완자본에
    # 산입한다 (CRE40.30). **표시용 분해가 아니라 실제 자본에 반영해야** 비율이
    # 움직인다 — 이전 시정은 분해 계층에만 닿아 비율이 그대로였다 (지적 F-802).
    from risk_lib.capital.bis_deep import expected_loss_vs_provisions
    el_vs_prov = expected_loss_vs_provisions(irb_el, eligible_provisions, rwa_irb)
    # 차감(CRE40.11)만 적용한다. 초과충당금의 보완자본 산입(CRE40.30)은 **임의
    # 규정**("may")이라 산입하지 않는 편이 보수적이고, 산입하면 총자본비율이
    # 올라간다 — 결함 시정의 부수효과로 비율을 좋게 만들지 않는다. 산입 여지는
    # `el_vs_prov["surplus_recognised"]`로 산출·공시만 한다.
    if el_vs_prov["shortfall"]:
        capital = CapitalStack(
            cet1=capital.cet1 - el_vs_prov["shortfall"],
            additional_t1=capital.additional_t1,
            tier2=capital.tier2,
        )
    bis = compute_bis_ratios(capital, rwa_final, buffers=buffers)
    em = exposure_measure(
        on_balance=total_ead + (structured.exposure if structured else 0.0),
        off_balance_notional=total_ead * 0.1,
        derivatives=float(getattr(ccr, "ead_total", 0.0) or 0.0))
    leverage = compute_leverage_ratio(capital.tier1, em)
    return (floor, rwa_final, capital, bis, leverage,
            rwa_internal_total, rwa_standardised_total, ccr_total, el_vs_prov)


def _stage_provisioning(book: pd.DataFrame, quarters: list[str],
                         *, seed: int = 42):
    """IFRS 9 ECL — **전 포트폴리오** 대상이다.

    이전에는 IRB북만 계산했다. 그러면 SA북의 손상 익스포저에 충당금이 없어
    SA 규제 익스포저(개별충당금 차감 후 — CRE20)를 세울 수 없다. 충당금은
    회계(IFRS 9) 산출이라 접근법(SA/IRB) 구분 없이 전 여신에 선다.
    """
    ecl_df = compute_ecl(book)
    ecl_by_stage = ecl_df.groupby("stage").agg(
        n=("exposure_id", "size"), ead=("ead", "sum"),
        ecl=("ecl", "sum"), coverage=("coverage_ratio", "mean"),
    )
    macro = macro_ecl(book, DEFAULT_MACRO_SCENARIOS)
    macro_path = macro_ecl_path(book, quarters, DEFAULT_MACRO_SCENARIOS)
    deep = compute_ifrs9_deep(book, seed=seed)
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


def _stage_limits_concentration(portfolio: pd.DataFrame, tier1: float,
                                limit_ledger: pd.DataFrame | None = None):
    """Headline limit + HHI report.

    Backward-compatible signature; the CRO deep-dive uses
    :func:`compute_limits_deep` which is wired in via the limits_deep field.

    한도 5종의 정의는 여기 리스트 리터럴로 박혀 있었다. 박혀 있으면 화면에
    승인기구·승인일·근거를 실을 자리가 없다. 이제 `lim_limit_definition`
    원장에서 읽으며, 임계가 비었거나 단위를 해석할 수 없는 행은 싣지 않고
    `limit_definitions`가 경고를 남긴다. 원장을 비우면 한도 산출도 비어야
    한다는 것이 이 배선의 계약이다.
    """
    from risk_lib.limits_master import limit_definitions
    limits = limit_definitions(limit_ledger)
    engine = LimitEngine(limits, tier1_capital=tier1)
    limit_report = engine.report(portfolio)
    # 화면은 소진율 분포를 봐야 하므로 위반이 아닌 버킷까지 함께 낸다. 검증·서식이
    # 쓰는 위반 보고서(limit_report)와는 별개 프레임이다 — 둘을 섞으면 "위반 N건"이
    # 갑자기 전 버킷 수가 된다.
    limit_full = engine.report(portfolio, min_utilisation=0.0)
    # 차주 단위는 버킷이 2,980개라 화면에서 분포를 가린다 — 위반분은 위반
    # 보고서에 이미 있으므로 전량 프레임에서는 뺀다.
    limit_full = limit_full[limit_full["dimension"] != "obligor_id"].copy()
    limit_full = limit_full.sort_values("utilisation", ascending=False)
    conc = concentration_report(portfolio, ["obligor_id", "sector", "country"])
    return limit_report, limit_full, conc


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


# ---------------------------------------------------------------- ALM 배선
#
# 산출 선택지를 파이프라인 상수로 올려 둔다. 엔진 함수 기본값에 숨기면 어떤
# 계정·어떤 기준·어떤 시계로 산출했는지가 산출물 어디에도 남지 않는다 —
# 현행 `compute_irrbb(base_rate=0.03)`이 정확히 그 상태였고, 파이프라인이
# 인자를 넘기지 않아 평면 3% 곡선이 조용히 쓰였다.

# IRRBB 계정. 계정명을 문자열로 다시 적지 않고 충격 원장이 헤드라인으로
# 선언한 계정을 그대로 받는다. 원장이 계정을 옮기면 파이프라인이 따라간다.
#
# 직전에는 여기 'd368_2016'이 박혀 있었다. 그 계정의 KRW 충격은 300/400/200이고
# 충격후 하한도 없다. 둘 다 2019.11.29·2026.1.29 개정으로 대체된 값이므로
# 헤드라인 ΔEVE가 폐지된 기준으로 산출되고 있었다. 현행 [별표 9-1] 개정
# 2026.1.29는 KRW 225/350/225이고 제12항 다가 충격후 금리 하한을 0으로 둔다.
# 계정 전환으로 ΔEVE 수치가 바뀐다 — 바뀌는 것이 맞는 방향이다.
from risk_lib.alm.curves import (                                # noqa: E402
    HEADLINE_FRAMEWORK_VERSION as ALM_FRAMEWORK_VERSION,
)
ALM_CCY = "KRW"

# 헤드라인 산출기준. 표준체계의 비만기예금 슬로팅(BCBS d368 Annex 2)이
# 행동가정이고 서식 각주도 "행태만기로 슬로팅"이라 적고 있으므로 행동조정을
# 헤드라인으로 둔다. 계약기준은 같은 원장에 나란히 남아 감독당국이 요구하는
# 두 기준 비교가 성립한다.
ALM_HEADLINE_BASIS = "행동조정"

# ΔNII 시계 12개월(BCBS d368 §132). 국내 세칙의 시계·재투자 가정은 미대조다.
ALM_NII_HORIZON_YEARS = 1.0

# 생존기간 산출 시계. **규정값이 아니다** — BCBS d144 Principle 10은 "LCR
# 30일보다 긴 시계"만 요구하고 목표 생존기간은 이사회 승인 대상이다
# (Principle 11). 승인 원장이 아직 없으므로 여기 적고 원장의 horizon_days
# 컬럼으로 내보낸다. 숨기면 이 수치가 승인 없이 산출에 들어간 사실이 안 보인다.
ALM_SURVIVAL_HORIZON_DAYS = 90


def _alm_risk_factor(asof: str, seed: int) -> pd.DataFrame:
    """`mkt_risk_factor`의 금리커브 행. 실체화 엔진과 **같은 스냅샷**에서 만든다.

    ALM이 커브를 따로 정의하면 시장리스크와 ALM이 서로 다른 곡선으로 할인하게
    된다. `demo_market_data(asof, seed)`는 결정론적이므로 여기서 만든 호가와
    `materialize_detail`이 원장에 적재하는 호가가 같은 값이다.
    """
    from risk_lib.market_data import demo_market_data
    snaps, _curve, _vol = demo_market_data(asof=asof, seed=seed)
    snap = next(s for s in snaps if s.data_type == "ir_curve")
    return pd.DataFrame([{
        "asof": asof, "risk_class": "interest_rate", "curve": snap.name,
        "tenor": float(r["tenor"]), "value": float(r["quote"]),
    } for _, r in snap.quotes.iterrows()])


def _stage_alm(portfolio: pd.DataFrame, capital, seed: int, *,
               asof: str) -> dict[str, Any]:
    """ALM 부문: 계수원장 → 계약원장 → 현금흐름 → 곡선/충격 → IRRBB · 유동성.

    반환 dict의 `tables`가 실체화 대상 원장 23장이다. 지표 객체
    (`irrbb`·`lcr`·`nsfr`)는 기존 소비처가 읽는 이름 그대로 유지한다.
    """
    from risk_lib.alm import curves as alm_curves
    from risk_lib.alm import irrbb as alm_irrbb
    from risk_lib.alm import liquidity as alm_liq
    from risk_lib.alm import nii as alm_nii
    from risk_lib.alm.cashflow import build_cashflows
    from risk_lib.alm.contracts import build_contract_ledger
    from risk_lib.alm.lcr import build_lcr_factor, lcr_balances_from_balance_sheet
    from risk_lib.alm.nsfr import build_nsfr_factor
    from risk_lib.alm.params import build_param_ledgers

    bs = generate_balance_sheet(portfolio, capital.total, seed=seed, asof=asof)
    params = build_param_ledgers(asof)
    curve_led = alm_curves.build_curve_ledgers()

    # 기저곡선이 계약 금리의 기준이다. 평면 3%를 여기 적으면 시장커브를
    # 연결한 의미가 없어지므로 1년 제로금리를 그대로 쓴다.
    base = alm_curves.base_curve(_alm_risk_factor(asof, seed), asof=asof)
    curves = {ALM_CCY: base}
    base_rate = float(base.rate(1.0))

    contracts = build_contract_ledger(
        portfolio, asof=asof, funding=bs.funding, hqla=bs.hqla,
        equity=bs.equity, base_rate=base_rate, seed=seed)
    cf = build_cashflows(
        contracts, asof=asof, product_terms=params["alm_product_terms"],
        buckets=params["alm_time_bucket"],
        behaviour_param=params["alm_behaviour_param"],
        scenario_mult=params["alm_behaviour_scenario_mult"],
        nmd_param=params["alm_nmd_param"],
        scurve_param=params["alm_prepay_scurve_param"])

    # ΔEVE와 ΔNII가 같은 충격곡선을 쓰게 한 자리에서 만든다.
    shocked, curve_warns = alm_irrbb.build_shocked_curves(
        curves, scenarios=alm_irrbb.SCENARIOS,
        shock_param=curve_led["alm_rate_shock_param"],
        scenario_def=curve_led["alm_scenario_def"],
        floor=curve_led["alm_post_shock_floor"],
        framework_version=ALM_FRAMEWORK_VERSION, allow_proxy=True)
    nii = alm_nii.compute_delta_nii(
        contracts, params["alm_product_terms"], asof=asof,
        horizon_years=ALM_NII_HORIZON_YEARS, curves=curves, shocked=shocked,
        scenario_def=curve_led["alm_scenario_def"],
        nmd_param=params["alm_nmd_param"])
    irrbb = alm_irrbb.compute_irrbb_from_cashflows(
        cf.bucket, asof=asof, tier1=capital.tier1, curves=curves,
        shock_param=curve_led["alm_rate_shock_param"],
        scenario_def=curve_led["alm_scenario_def"],
        floor=curve_led["alm_post_shock_floor"],
        framework_version=ALM_FRAMEWORK_VERSION,
        headline_basis=ALM_HEADLINE_BASIS, allow_proxy=True,
        delta_nii=nii.delta_nii)
    # 계승 소비처(업무보고서 B2510~B2512 금리 재구성, ALM 화면)가 읽는 기준금리.
    # 계승 경로에서는 평면 곡선 수준이었고, 여기서는 계약원장을 세운 1년 제로
    # 금리다 — 어느 쪽이든 "그 산출이 출발점으로 삼은 금리"라는 뜻은 같다.
    irrbb.base_rate = base_rate

    lcr_factor = build_lcr_factor()
    nsfr_factor = build_nsfr_factor()
    lcr = compute_lcr(bs, factor=lcr_factor, asof=asof)
    nsfr = compute_nsfr(bs, factor=nsfr_factor, asof=asof)

    # 반대매매가능자산 = 헤어컷·상한 후 HQLA. LCR 분자와 같은 값을 쓴다 —
    # 유동성 화면 두 곳이 다른 HQLA를 그리면 어느 쪽이 정본인지 알 수 없다.
    cbc = float(lcr.hqla_total)
    ladder = alm_liq.build_maturity_ladder(cf.bucket,
                                           counterbalancing_capacity=cbc)
    stress_param = alm_liq.build_liquidity_stress_param(
        lcr_factor, horizon_days=ALM_SURVIVAL_HORIZON_DAYS)
    outflow_balance = (lcr_balances_from_balance_sheet(bs, seed_inflow_frac=0.04)
                       .query("section == '유출'")[["category", "balance"]])
    survival = alm_liq.build_survival_path(
        outflow_balance, stress_param, asof=asof,
        counterbalancing_capacity=cbc)

    warnings = (list(bs.ladder_warnings) + list(cf.warnings)
                + list(curve_warns) + list(nii.warnings)
                + list(irrbb.warnings) + list(survival.warnings))

    tables: dict[str, pd.DataFrame] = dict(params)
    tables.update(curve_led)
    tables.update({
        "alm_contract": contracts,
        "alm_cashflow_contract": cf.contract,
        "alm_cashflow_behavioural": cf.behavioural,
        "alm_cashflow_bucket": cf.bucket,
        "alm_irrbb_bucket_pv": irrbb.bucket_pv,
        "alm_irrbb_result": irrbb.result,
        "alm_nii_result": nii.result,
        "alm_lcr_factor": lcr_factor,
        "alm_lcr_flow": lcr.flow,
        "alm_nsfr_factor": nsfr_factor,
        "alm_nsfr_item": nsfr.item,
        "alm_maturity_ladder": ladder,
        "alm_liquidity_stress_param": stress_param,
        "alm_survival_path": survival.path,
    })
    return {
        "balance_sheet": bs,
        "irrbb": irrbb,
        "lcr": lcr,
        "nsfr": nsfr,
        "cashflow": cf,
        "nii": nii,
        "survival": survival,
        "base_curve": base,
        "warnings": warnings,
        "tables": tables,
    }


# ---------------------------------------------------------------- 신규 원장 스테이지

def _kr_nmd_deposits(contracts: pd.DataFrame, product_terms: pd.DataFrame,
                     *, asof: str) -> pd.DataFrame:
    """계약원장의 비만기성예금 행을 [별표 9-1] 제8항 가의 판정 입력으로 옮긴다.

    예치인 구분을 새로 만들지 않는다. 계약원장이 이미 들고 있는
    `counterparty_type`을 별표의 어휘로 옮기기만 한다. 옮길 수 없는 값은
    비워 두며, 그러면 판정 엔진이 잔여규칙(도매)을 적용하고 그 사실을
    `rule_applied`에 남긴다.

    `is_retail_managed`·`funding_total_amount`는 계약원장에 없다. 중소기업
    소매 유사 간주(15억원 미만)를 판정할 입력이 없다는 뜻이므로 NULL로 두고
    엔진이 경고를 내게 한다. 임의로 채우면 도매예금이 소매로 올라간다.
    """
    nmd = product_terms[product_terms["behaviour_class"] == "nmd"]
    src = contracts[contracts["product_code"].isin(set(nmd["product_code"]))]
    # 계약원장 어휘 → 별표 어휘. 금융기관 예치금은 상품코드로만 구분되므로
    # 상품코드를 먼저 본다(계약원장의 counterparty_type이 도매로 뭉쳐 있다).
    rows = []
    for r in src.itertuples():
        code = str(r.product_code)
        ctype = str(getattr(r, "counterparty_type", "") or "")
        if code.endswith("_FI"):
            dtype, regular, free = "금융기관", None, None
        elif ctype.startswith("retail"):
            dtype = "개인"
            regular = ctype.endswith("transactional") and "non" not in ctype
            free = None
        elif ctype.startswith("wholesale"):
            dtype, regular, free = "법인", None, None
        else:
            dtype, regular, free = "법인", None, None
        rows.append({
            "asof": asof, "account_id": str(r.contract_id), "ccy": str(r.ccy),
            "balance": float(r.notional), "depositor_type": dtype,
            "is_retail_managed": None, "funding_total_amount": None,
            "has_regular_transaction": regular, "is_interest_free": free,
        })
    return pd.DataFrame(rows, columns=[
        "asof", "account_id", "ccy", "balance", "depositor_type",
        "is_retail_managed", "funding_total_amount", "has_regular_transaction",
        "is_interest_free"])


def _kr_behavioural_contracts(contracts: pd.DataFrame,
                              product_terms: pd.DataFrame,
                              portfolio: pd.DataFrame, *, asof: str
                              ) -> pd.DataFrame:
    """계약원장에서 제9·10항 판정 대상(조기상환·중도해지)을 뽑는다.

    행동옵션 구분과 금리유형은 상품원장이 이미 들고 있다. 고객 구분은
    익스포저의 자산군에서 온다. 예수금 행은 익스포저가 없으므로 상품코드가
    소매·기업 중 어느 쪽인지를 그대로 쓴다.

    `is_retail_managed`(소매여신 관리 여부)와 중도해지의 법적 해지권·위약금
    여부는 이 저장소의 어느 원장에도 없다. NULL로 두면 판정 엔진이 그 계약을
    건너뛰고 경고를 남긴다. 채워 넣으면 근거 없는 판정이 원장에 들어간다.
    """
    terms = product_terms.set_index("product_code")
    cls_by_code = terms["behaviour_class"].to_dict()
    rate_by_code = terms["rate_type"].to_dict()
    wanted = {"prepayment", "early_redemption"}
    src = contracts[contracts["product_code"].map(cls_by_code).isin(wanted)]
    ac = portfolio.set_index("exposure_id")["asset_class"].to_dict()
    # 자산군 → 별표의 고객 구분. 소매·주담대는 개인, 기업·국가는 법인,
    # 은행은 금융기관이다. 중소기업 구분은 자산군에 없으므로 여기서 만들지
    # 않는다. 만들면 15억·10억 기준이 근거 없이 발동한다.
    _CUSTOMER = {"retail_other": "개인", "residential_mortgage": "개인",
                 "corporate": "법인", "sovereign": "법인", "bank": "금융기관"}
    rows = []
    for r in src.itertuples():
        code = str(r.product_code)
        exp = getattr(r, "exposure_id", None)
        if exp is not None and not pd.isna(exp) and str(exp) in ac:
            ctype = _CUSTOMER.get(str(ac[str(exp)]), "법인")
        else:
            ctype = "개인" if code.endswith("_RT") else "법인"
        fee = getattr(r, "prepay_fee_rate", None)
        rows.append({
            "asof": asof, "contract_id": str(r.contract_id),
            "behaviour_class": str(cls_by_code[code]),
            "ccy": str(r.ccy), "notional": float(r.notional),
            "customer_type": ctype, "rate_type": rate_by_code.get(code),
            "is_retail_managed": None, "exposure_amount": None,
            "prepay_fee_charged": (None if fee is None or pd.isna(fee)
                                   else bool(float(fee) > 0.0)),
            "has_legal_termination_right": None, "substantial_penalty": None,
        })
    return pd.DataFrame(rows, columns=[
        "asof", "contract_id", "behaviour_class", "ccy", "notional",
        "customer_type", "rate_type", "is_retail_managed", "exposure_amount",
        "prepay_fee_charged", "has_legal_termination_right",
        "substantial_penalty"])


#: 잠정 준용 할인율의 승인자 자리. 승인기구 의결이 아니라는 것을 값 자체가
#: 말하게 둔다. 거액익스포져 설정 원장의 '(미승인)'과 같은 표기 방식이다.
PROVISIONAL_RATE_APPROVER = "(미승인·업계참고 잠정준용)"

#: 준용 행의 무위험이자율·베타 출처 칸. 우리가 산출한 값이 아니라는 사실을
#: 칸 자체가 말한다. 참고치의 원문 근거는 같은 행의 참고치 근거 칸에 있다.
_PROVISIONAL_SOURCE_NOTE = (
    "산출하지 않았다. 타행이 공시한 자기자본비용을 통째로 준용한 값이라 "
    "우리 쪽 무위험이자율·베타가 들어가지 않았다. 근거는 참고치 근거 칸에 있다")


def _provisional_discount_rates(asof: str) -> tuple[pd.DataFrame, list[str]]:
    """'전체' 회수유형 할인율을 참고치로 잠정 준용한 원장을 만든다.

    [별표 3] 184.(1)은 할인율의 산식·수준을 주지 않는다. CAPM 추정은
    무위험이자율과 베타까지는 관측으로 내지만 시장수익률은 내지 못한다
    (지표 마스터의 주가 계열에 표류항이 없어 실현 위험프리미엄이 음수다).
    그 결과 '전체' 회수유형 할인율이 비고, LGD·BEEL 곡선·PLGD가 전부
    산출불가로 멈춘다.

    여기서 쓰는 값은 지어낸 수가 아니라 할인율 원장이 이미 들고 있는 참고치
    (`reference_value`, 타행 실측)다. 파이프라인은 그 값을 옮겨 적을 뿐이고
    승인자 자리에는 :data:`PROVISIONAL_RATE_APPROVER`가 들어가 의결이 없다는
    사실을 원장·화면·결재 문서가 함께 읽는다. 참고치가 비어 있으면 아무것도
    채우지 않고 사유만 남긴다.

    무위험회수 회수유형은 관측 평균(국고채 만기수익률)으로 채워지므로 준용
    대상이 아니다. `discount_capm.apply_capm_discount_rates`가 채운다.
    """
    from risk_lib.models.estimation import (
        build_crm_lgd_discount_rate, approve_discount_rate,
    )
    rates = build_crm_lgd_discount_rate(asof)
    warns: list[str] = []
    scope = "전체"
    target = rates[(rates["asof"] == asof) & (rates["recovery_scope"] == scope)]
    applied = 0
    for _, row in target.iterrows():
        ref = row["reference_value"]
        seg = str(row["segment"])
        if pd.isna(ref):
            warns.append(
                f"회수 할인율({seg}/{scope})에 참고치가 없어 잠정 준용도 하지 "
                "못했다. 이 세그먼트 LGD는 산출불가로 남는다")
            continue
        rates = approve_discount_rate(
            rates, asof=asof, segment=seg, recovery_scope=scope,
            rate=float(ref), basis="자기자본비용",
            approved_by=PROVISIONAL_RATE_APPROVER, approval_date=asof,
            # 준용 값은 타행이 공시한 자기자본비용을 통째로 가져온 것이라
            # 우리 쪽 무위험이자율·베타가 들어가지 않았다. 두 칸에 원장의
            # 참고치 근거를 그대로 옮기면 우리가 낸 값처럼 읽히므로, 산출을
            # 하지 않았다는 사실을 적는다. 근거 원문은 참고치 근거 칸에 있다.
            rf_source=_PROVISIONAL_SOURCE_NOTE,
            beta_source=_PROVISIONAL_SOURCE_NOTE,
            evidence_status="2차자료")
        applied += 1
    if applied:
        warns.append(
            f"'{scope}' 회수유형 할인율 {applied}건을 원장 참고치(타행 실측)로 "
            f"잠정 준용했다. 승인자 '{PROVISIONAL_RATE_APPROVER}' · 승인일은 "
            "기준일 자리표시자다. crm_estimation_param의 capm_market_return이 "
            "승인되면 CAPM 추정치로 갈아탄다")
    return rates, warns


def _stage_ledgers(portfolio: pd.DataFrame, base: dict[str, pd.DataFrame],
                   alm: dict[str, Any], capital, bis, stress_path: pd.DataFrame,
                   ecl_df: pd.DataFrame, rwa: dict[str, float],
                   op_loss, limit_report: pd.DataFrame,
                   *, asof: str, seed: int) -> dict[str, Any]:
    """신규 원장 스테이지. 순서는 뒤 단계가 앞 단계의 산출을 쓰는 순서다.

    거시지표 마스터 → 한도 정의 → [별표 9-1] 국내 금리리스크 → LGD·CCF
    실측검증 → 나머지 신규 요건.

    이 스테이지가 만드는 프레임은 `PipelineResult.ledger_tables`로 나가고
    실체화 엔진이 그대로 싣는다. 화면이 같은 빌더를 다시 부르면 두 벌이 된다.

    근거가 없어 산출하지 못한 항목은 `warnings`에 문장으로 남긴다. 조용히
    건너뛰면 화면에서 "없음"과 "확인 안 함"이 같아진다.
    """
    tables: dict[str, pd.DataFrame] = {}
    warns: list[str] = []

    def _note(w) -> str:
        return getattr(w, "reason", None) or str(w)

    # ---- 1. 거시지표 마스터 (지표 정의 · 시나리오 충격 배수)
    from risk_lib.macro_monitor import (
        build_macro_master_ledgers, unapproved_indicators,
        unapproved_scenario_shocks,
    )
    macro_led = build_macro_master_ledgers()
    tables.update(macro_led)
    n_ind = len(unapproved_indicators(macro_led["rdm_macro_indicator_master"]))
    n_shk = len(unapproved_scenario_shocks(macro_led["st_macro_scenario_shock"]))
    if n_ind:
        warns.append(f"거시지표 마스터 {n_ind}행이 승인 전이다(출처 대조 미실시)")
    if n_shk:
        warns.append(f"시나리오 충격 배수 {n_shk}행이 내부가정이며 승인 전이다")

    # ---- 2. 한도 정의 — `_stage_limits_concentration`이 읽은 바로 그 원장
    from risk_lib.limits_master import build_limit_definitions, unapproved_limits
    limit_ledger = build_limit_definitions()
    tables["lim_limit_definition"] = limit_ledger
    n_lim = len(unapproved_limits(limit_ledger))
    if n_lim:
        warns.append(f"내부한도 {n_lim}행이 승인일 미기재다")

    # ---- 3. [별표 9-1] 국내 고유 요건 + 제22항 공시서식
    from risk_lib.alm import kr_irrbb as kr
    criteria = kr.build_kr_retail_criteria()
    tables["kr_retail_criteria"] = criteria
    tables["kr_auto_option_param"] = kr.build_kr_auto_option_param()
    deposits = _kr_nmd_deposits(alm["tables"]["alm_contract"],
                                alm["tables"]["alm_product_terms"], asof=asof)
    nmd_cat, w = kr.classify_kr_nmd_category(deposits, criteria, asof=asof)
    tables["kr_nmd_category"] = nmd_cat
    warns += [_note(x) for x in w]
    scope, w = kr.build_kr_retail_behavioural_scope(
        _kr_behavioural_contracts(alm["tables"]["alm_contract"],
                                  alm["tables"]["alm_product_terms"],
                                  portfolio, asof=asof),
        criteria, asof=asof)
    tables["kr_retail_behavioural_scope"] = scope
    warns += [_note(x) for x in w]
    gov_kr, w = kr.build_kr_irrbb_governance(asof=asof)
    tables["kr_irrbb_governance"] = gov_kr
    warns += [_note(x) for x in w]

    from risk_lib.regulatory.forms_irrbb_disclosure import (
        build_table6, build_table7_qualitative, build_table7_quantitative,
    )
    # <표6>은 산출기준 하나의 표를 받는다. 결과 원장의 낟알은
    # (기준일, 산출기준, 시나리오)이므로 헤드라인 계정·헤드라인 기준으로 좁힌다.
    irrbb_res = alm["tables"]["alm_irrbb_result"]
    headline = irrbb_res[
        (irrbb_res["framework_version"] == ALM_FRAMEWORK_VERSION)
        & (irrbb_res["basis"] == ALM_HEADLINE_BASIS)]
    t6, w = build_table6(headline, None, asof=asof,
                         tier1_current=float(capital.tier1),
                         framework_version=ALM_FRAMEWORK_VERSION)
    tables["disc_irrbb_table6"] = t6
    warns += [_note(x) for x in w]
    t7a, w = build_table7_qualitative(asof=asof)
    tables["disc_irrbb_table7_qualitative"] = t7a
    warns += [_note(x) for x in w]
    t7b, w = build_table7_quantitative(asof=asof)
    tables["disc_irrbb_table7_quantitative"] = t7b
    warns += [_note(x) for x in w]

    # ---- 4. LGD·CCF 실측검증 (관측중단 건수를 원장이 들고 나온다)
    from risk_lib.models.lgd_ead_backtest import build_lgd_ead_backtest_ledgers
    with warnings_mod.catch_warnings():
        warnings_mod.simplefilter("ignore")
        tables.update(build_lgd_ead_backtest_ledgers(
            portfolio, base["rdm_exposure"], asof=asof,
            collateral=base["rdm_collateral"], seed=seed))

    # ---- 5. 신규 요건 산출
    # 5a. 내부등급법 PD·LGD·CCF 추정 (다년 관측이력은 모듈이 합성한다)
    from risk_lib.models.estimation import build_irb_estimation_ledgers
    rates, rate_warns = _provisional_discount_rates(asof)
    warns += [_note(x) for x in rate_warns]
    with warnings_mod.catch_warnings():
        warnings_mod.simplefilter("ignore")
        tables.update(build_irb_estimation_ledgers(
            asof=asof, seed=seed, current_portfolio=portfolio, rates=rates))

    # 5b·5c(신용평가시스템·CRM 배분)는 `crm_model`·`rwa_result`를 입력으로 쓴다.
    # 그 둘은 실체화 단계에서 서므로 이 스테이지가 아니라
    # `materialize_ledgers`에서 만든다. 여기서 다시 세우면 같은 산출이 두 벌이 된다.

    # 5d. 거액익스포져 — 감독규정 제26조·별표 3-12
    from risk_lib.limits import large_exposure as lex
    # 설정 원장의 승인 3칸은 NULL을 받지 않는 스펙이다. 이 저장소에는 거액
    # 익스포져 설정을 의결한 기록이 없으므로 승인자 자리에 '(미승인)'을 적고
    # 승인일에는 산출 기준일을 넣는다. 승인일은 자리표시자이며 그 사실을
    # 경고로 남긴다. 실제 의결일을 지어내지 않는다.
    lex_setting = lex.build_lex_setting(
        asof, bank_is_gsib=False, lookthrough_small_to_structure=False,
        input_by="리스크데이터관리자(배선 적재)", approved_by="(미승인)",
        approved_at=asof)
    warns.append("거액익스포져 설정 원장에 의결 기록이 없다. 승인자 '(미승인)' · "
                 "승인일은 기준일 자리표시자다")
    lex_in = lex.build_lex_inputs(portfolio, asof=asof,
                                  tier1=float(capital.tier1), seed=seed)
    lex_res = lex.compute_large_exposure(
        lex_in, lex_setting, asof=asof, tier1=float(capital.tier1),
        own_funds=float(capital.total))
    tables.update({
        "lex_setting": lex_res.setting,
        "lex_exposure_measure": lex_res.exposure_measure,
        "lex_lookthrough": lex_res.lookthrough,
        "lex_substitution": lex_res.substitution,
        "lex_connected_group": lex_res.connected_group,
        "lex_exemption": lex_res.exemption,
        "lex_position": lex_res.position,
        "lex_aggregate": lex_res.aggregate,
    })
    warns += [_note(x) for x in lex_res.warnings]

    # 5e. 고객행동모형 관측이력·추정
    from risk_lib.alm import behaviour_estimation as be
    from risk_lib.alm import behaviour_history as bh
    base_rate = float(alm["irrbb"].base_rate)
    history = bh.build_behaviour_history(asof, seed=seed, base_rate=base_rate)
    tables.update(history)
    shock_row = alm["tables"]["alm_rate_shock_param"]
    hit = shock_row[(shock_row["framework_version"] == ALM_FRAMEWORK_VERSION)
                    & (shock_row["ccy"] == ALM_CCY)
                    & (shock_row["shock_type"] == "parallel")]
    est = be.run_estimation(history, asof=asof)
    if hit.empty or pd.isna(hit["shock_bp"].iloc[0]):
        warns.append("행동모형 전가율 산출에 쓸 평행충격이 원장에 없다. 추정 원장을 만들지 않는다")
    else:
        tables.update(be.build_estimation_ledgers(
            est, history, alm["tables"]["alm_nmd_param"],
            alm["tables"]["alm_time_bucket"],
            shock_bp=float(hit["shock_bp"].iloc[0])))

    # 5f. ICAAP 리스크 인벤토리 — 중요성 3축은 실제 산출에서 온다
    from risk_lib.icaap.risk_inventory import build_risk_inventory
    tables.update(build_risk_inventory(
        _inventory_observations(rwa, ecl_df, op_loss, limit_report),
        _inventory_capital(rwa), asof=asof))

    # 5g. 조달·증거금·상품·RCSA·시장데이터·PMA·경영조치
    from risk_lib import funding, margin, market_feed, product_master, rcsa
    from risk_lib.ccr import synthesise_derivatives
    from risk_lib.provisioning.pma import build_pma_and_recon
    from risk_lib.stress.management_action import build_management_actions

    fund_t, fund_w = funding.build_funding(asof=asof, base_rate=base_rate,
                                           seed=seed)
    tables.update(fund_t)
    warns += list(fund_w)
    # 증거금 원장은 파생거래에서 나온다. 은행 익스포저가 없는 포트폴리오에서는
    # 거래가 0건이고, 그때 원장을 억지로 세우면 거래상대방 없는 CSA가 생긴다.
    # 원장을 만들지 않고 그 사실을 경고로 남긴다.
    bank_book = portfolio[portfolio["asset_class"] == "bank"]
    deriv = (synthesise_derivatives(bank_book, seed=seed) if len(bank_book)
             else pd.DataFrame())
    if len(deriv):
        mgn_t, mgn_w = margin.build_margin(deriv, asof=asof, seed=seed)
        tables.update(mgn_t)
        warns += list(mgn_w)
    else:
        warns.append("파생거래가 0건이라 증거금·담보 원장을 만들지 않는다")
    prd_t, prd_w = product_master.build_product_master(asof=asof)
    tables.update(prd_t)
    warns += [f"평가불가 상품: {x}" for x in prd_w]
    tables.update(rcsa.build_rcsa(asof=asof))
    feed_t, feed_w = market_feed.build_market_feed(asof=asof)
    tables.update(feed_t)
    warns += list(feed_w)

    seg_ecl = (ecl_df.assign(segment=portfolio["asset_class"].to_numpy())
               .groupby("segment", as_index=False)["ecl"].sum())
    pma_t, pma_w = build_pma_and_recon(seg_ecl, asof=asof)
    tables.update(pma_t)
    warns += list(pma_w)

    act_t, act_w = build_management_actions(
        stress_path, {k: float(v) for k, v in bis.required.items()})
    tables.update(act_t)
    warns += list(act_w)

    # 5h. 변경·연계 통제
    from risk_lib.governance.change_control import build_change_control
    from risk_lib.governance.model_lifecycle import build_model_lifecycle
    from risk_lib.integration import connector, engine_adapter, inbound, resilience
    # 변경요청 접수 경로가 이 저장소에 배선돼 있지 않다. 정책표만 싣고
    # 요청·영향·통제 원장은 비운다. 표본을 만들어 채우면 실시하지 않은 통제가
    # 실시한 것으로 보인다.
    tables.update(build_change_control([], [], []))
    warns.append("변경통제 요청 원장이 비어 있다. 변경요청 접수 경로가 배선되지 않았다")
    life_t, life_w = build_model_lifecycle(asof=asof)
    tables.update(life_t)
    warns += list(life_w)
    tables.update(connector.build_connector_control())
    tables.update(engine_adapter.build_engine_adapter())
    # 커넥터가 전건 미연결이므로 수신분이 없다. 전 피드가 '미수신'으로 남는다.
    inb = inbound.build_inbound({}, asof=asof)
    tables.update(inb)
    tables.update(resilience.build_resilience(
        _delivery_events(inb["int_inbound_contract"],
                         inb["int_inbound_delivery"])))
    n_recv = int((inb["int_inbound_delivery"]["status"] != "미수신").sum())
    if not n_recv:
        warns.append("외부 수신 계약 전건이 미수신이다. 커넥터가 전건 미연결이다")

    return {"tables": tables, "warnings": warns, "limit_ledger": limit_ledger}


def _delivery_events(contracts: pd.DataFrame, deliveries: pd.DataFrame
                     ) -> list[dict]:
    """수신 판정 원장을 복원력 엔진이 읽는 시도 사건으로 옮긴다.

    연계 유형은 계약의 데이터 형식에서 온다. 파일 형식(CSV)은 '파일',
    REST는 'API', 나머지는 계약 표기를 그대로 쓴다. 정책 원장에 없는 유형이면
    엔진이 재시도하지 않고 즉시 격리한다 — 근거 없는 재시도를 막는 쪽이 맞다.
    """
    _KIND = {"CSV": "파일", "REST API": "API"}
    fmt = contracts.set_index("feed_id")["data_format"].to_dict()
    out = []
    for r in deliveries.itertuples():
        raw = str(fmt.get(str(r.feed_id), ""))
        out.append({
            "feed_id": str(r.feed_id), "asof": str(r.asof),
            "batch_seq": int(r.batch_seq),
            "channel_kind": _KIND.get(raw, raw),
            # 미수신분에는 내용이 없다. 체크섬 자리가 비면 멱등키가 피드·기준일·
            # 회차만으로 서고, 그것이 '아직 아무것도 오지 않았다'의 지문이다.
            "content_fingerprint": str(r.checksum or ""),
            "ok": str(r.status) == "정상",
            "reason": str(r.detail),
        })
    return out


def _inventory_observations(rwa: dict[str, float], ecl_df: pd.DataFrame,
                            op_loss, limit_report: pd.DataFrame) -> list[dict]:
    """중요성 3축(노출·손실·KRI 초과)을 실제 산출에서 만든다.

    노출은 RWA 구성비, 손실은 신용 ECL과 운영손실 합계 대비 비중, KRI 초과는
    한도 위반 건수 비중이다. 관측이 없는 리스크 유형은 행을 만들지 않으며,
    중요성 판정은 그 유형을 '미판정'으로 남긴다.
    """
    total_rwa = float(rwa.get("final_total", 0.0)) or 1.0
    credit = float(rwa.get("sa", 0.0)) + float(rwa.get("irb", 0.0)) \
        + float(rwa.get("ccr", 0.0)) + float(rwa.get("structured_total", 0.0))
    ecl_total = float(ecl_df["ecl"].sum())
    op_net = float(getattr(op_loss, "total_net_loss", 0.0) or 0.0)
    loss_total = ecl_total + op_net or 1.0
    n_breach = int(len(limit_report)) or 1
    return [
        {"risk_id": "R-CRD", "exposure_share": credit / total_rwa,
         "loss_share": ecl_total / loss_total, "kri_breach_share": 1.0},
        {"risk_id": "R-MKT",
         "exposure_share": float(rwa.get("market", 0.0)) / total_rwa,
         "loss_share": 0.0, "kri_breach_share": 0.0},
        {"risk_id": "R-OPR",
         "exposure_share": float(rwa.get("op", 0.0)) / total_rwa,
         "loss_share": op_net / loss_total, "kri_breach_share": 0.0},
    ]


def _inventory_capital(rwa: dict[str, float]) -> dict[str, float]:
    """유형별 내부자본 = RWA × 8%. Pillar 1이 자본을 요구하는 유형만 넣는다."""
    credit = float(rwa.get("sa", 0.0)) + float(rwa.get("irb", 0.0)) \
        + float(rwa.get("ccr", 0.0)) + float(rwa.get("structured_total", 0.0))
    return {"R-CRD": credit * 0.08,
            "R-MKT": float(rwa.get("market", 0.0)) * 0.08,
            "R-OPR": float(rwa.get("op", 0.0)) * 0.08}


def _stage_icaap(
    sa_res: pd.DataFrame, irb_res: pd.DataFrame,
    mkt, op, alm: dict[str, Any], conc: pd.DataFrame, capital,
    structured: "StructuredRWA | None" = None,
    ccr_rwa: float = 0.0,
):
    """내부자본(ICAAP): 위험유형별 경제자본과 가용자본 대비 적정성.

    구조화(집합투자증권·유동화)와 거래상대방신용리스크(SA-CCR + CVA)도 신용
    경제자본에 넣는다. 1선 자본(Pillar 1)이 자본을 요구하는 익스포저를 내부자본이
    덮지 않으면, ICAAP가 규제 최저보다 **적은** 자본을 적정하다고 말하게 된다.
    시장·운영과 같은 RWA×8% 환산이다.

    CCR은 `rwa_internal_total`에 이미 들어가 있으면서 경제자본에서만 빠져 있었다 —
    구조화 4.13조와 같은 유형이 한 단계 아래에 남아 있던 것이다. 분모에 넣은
    항목이 내부자본에서 빠지지 않게 `xd_ec_covers_rwa_components`가 고정한다.
    """
    parts = {"irb": float((irb_res["k"] * irb_res["ead"]).sum()),
             "sa": float(sa_res["rwa"].sum()) * 0.08,
             "ccr": float(ccr_rwa) * 0.08}
    if structured is not None:
        parts["structured_total"] = float(structured.rwa_internal) * 0.08
    credit_ec = float(sum(parts.values()))
    hhi = conc.set_index("dimension")["hhi"]
    return compute_icaap(
        credit_ec=credit_ec,
        credit_ec_components=tuple(sorted(parts)),
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
                  bi_components, op, op_loss_result, alm, op_notional,
                  ccr_rwa: float = 0.0, structured=None):
    """전 축 충격 엔진의 기준 상태. 파이프라인이 이미 만든 값만 모은다."""
    from risk_lib.stress.multi_axis import StressBooks
    lcr = alm["lcr"]
    bs = alm["balance_sheet"]
    return StressBooks(
        irb=irb_book, sa=sa_book, full=portfolio, capital=capital,
        market_positions=mkt_positions, bi=bi_components,
        # OPE25.9 ILM은 10년 평균 손실을 쓴다 — 연간 손실을 그대로 넣으면
        # 손실승수가 과대해진다. 기준은 운영 도메인의 독립 명목이다 — 신용
        # EAD 비례가 여기 한 곳 남아 있으면 base 재현이 1.2bp 어긋난다
        # (도메인 독립화 때 실제로 이 자리가 누락됐고 검사가 잡았다).
        op_losses_10y=op_notional * 0.001,
        op_loss_annual=float(getattr(op_loss_result, "annual_total", 0.0)),
        # 잔액 기준 재설정 갭 사다리. `irrbb.repricing`은 현금흐름을 접은 PV
        # 뷰라 축이 다르다 — 갭 근사(gap × t_mid × Δr)에 넣으면 원금과 이자를
        # 함께 듀레이션 가중하게 된다.
        repricing=bs.repricing,
        hqla=dict(bs.hqla), lcr_outflows=lcr.outflows, lcr_inflows=lcr.inflows,
        revenue=float(portfolio["revenue"].sum()),
        operating_cost=float(portfolio["operating_cost"].sum()),
        credit_securities=float(bs.hqla["level_2a"] + bs.hqla["level_2b"]),
        ccr_rwa=float(ccr_rwa),
        structured_rwa=float(structured.rwa_internal) if structured else 0.0,
        structured_rwa_standardised=(float(structured.rwa_standardised)
                                     if structured else 0.0),
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
    market_op: Mapping[str, float] | None = None,
    institution_code: str | None = None,
    institution_type: str | None = None,
    base_seed: int | None = None,
    structured_scale: "Mapping[str, float] | None" = None,
    pillar2: "Mapping[str, float | None] | None" = None,
    capital_basis: str | None = None,
) -> PipelineResult:
    """`capital_ledger`를 주면 그 자본으로 산출하고, 주지 않으면 수익성 기반
    합성기를 쓴다. 어느 쪽이든 그 사실이 독립검증 요청에 공시된다.

    원장을 준다고 해서 실측 자본이 되지는 않는다. 이 저장소가 가진 유일한
    원장 경로(`data_gen_intl.capital_ledger_for`)는 `cet1_to_ead` 등 총익스포저
    비율에 총익스포저를 곱한 값이라 자본이 익스포저를 그대로 따라간다. 이
    함수는 넘어온 `CapitalStack` 의 출처를 확인하지 않으므로, 호출부가
    `capital_basis` 로 산출근거를 함께 넘겨야 자체검증이 그 사실을 적을 수
    있다 (넘기지 않으면 `capital_source` 가 WARN 이다).

    `market_op`·`buffers`·`structured_scale`·`pillar2` 를 주지 않으면 기관
    프로파일 원장의 국내 표본 행을 읽는다. 엔진 기본값으로 두면 그 수가 소스에
    남는다. 기관 산출을 돌리는 호출자는 반드시 자기 기관의 행을 넘겨야 하며,
    넘기지 않으면 국내 표본의 모수로 자기 기관을 설명하게 된다.

    `institution_code` 는 산출에 쓰이지 않고 meta 에만 남는다. 결과 한 벌이
    어느 기관 것인지 결과 자신이 말하게 하기 위한 것이다.

    `base_seed` 는 **기관 오프셋을 더하기 전** 시드다. 공유 참조 원장(거시지표
    관측치처럼 기관과 무관하게 한 값인 표)은 이 시드로 만들어야 한다. 기관
    시드로 만들면 같은 시점 같은 지표가 기관마다 다른 값을 갖고, 기관코드가
    없는 그 표들은 합쳤을 때 기본키가 충돌한다. 주지 않으면 `seed` 와 같다.
    """
    from risk_lib import data_gen_intl as _intl
    if buffers is None:
        buffers = _intl.buffers_for(_intl.BASE_INSTITUTION)
    if market_op is None:
        market_op = _intl.market_op_params(_intl.BASE_INSTITUTION)
    if structured_scale is None:
        structured_scale = _intl.structured_scale_for(_intl.BASE_INSTITUTION)
    if pillar2 is None:
        pillar2 = _intl.pillar2_for(_intl.BASE_INSTITUTION)
    if base_seed is None:
        base_seed = seed
    if portfolio is None:
        portfolio = generate_portfolio(seed=seed)

    # 1. PD models per segment + grades + challenger + LGD + XAI + calibration
    (portfolio, pd_metrics, challenger_metrics, lgd_metrics, explain,
     calibration, grade_migration) = _fit_segment_pd(portfolio)

    # `asof`를 안 주면 벽시계를 쓴다. 그러면 같은 seed·같은 데이터라도 실행 날짜가
    # 다르면 헤드라인 지문이 달라진다 — ARCHITECTURE의 "seed+asof 같으면 산출 같다"가
    # 진입점에서 깨진다. 기본값을 없애면 기존 호출부가 전부 깨지므로, **출처를
    # 기록**하고 자체검증이 그것을 드러내게 한다. 조용한 것이 문제였다.
    asof_source = "explicit"
    if asof is None:
        asof = date.today()
        asof_source = "wall_clock"
    elif isinstance(asof, str):
        asof = date.fromisoformat(asof)
    quarters = forecast_quarter_labels(asof, years_ahead=years_ahead)
    total_ead = float(portfolio["ead"].sum())

    # 2~3. 도메인 병렬 산출 — 신용(ECL→EAD→RWA) · 시장·운영 · CCR 세 갈래는
    # 서로의 산출물을 쓰지 않는다(공유하는 것은 원천 원장뿐). 그래서 갈래
    # 간 순서가 없고, 나란히 돈다. 갈래 **안**의 순서는 규정이 정한다:
    #
    #   ECL이 신용 EAD보다 먼저다 — SA 규제 익스포저는 개별충당금(손상)
    #   차감 후이므로(CRE20), 충당금 없이 신용 EAD가 서지 않는다. IRB는
    #   EAD를 차감하지 않는다 — EL-적격충당금 비교(CRE35.3·40.11)가 자본
    #   에서 처리하므로 EAD 차감까지 하면 이중계상이다.
    #   (이전에는 신용 RWA가 ECL보다 먼저였다 — 충당금 차감 전 EAD였다.)
    def _branch_credit():
        book = _fill_sa_parameters(portfolio)
        ecl_df, ecl_by_stage, macro, macro_path, ifrs9_deep = \
            _stage_provisioning(book, quarters, seed=seed)
        sa_book, irb_book = _stage_split_books(book)
        # SA 익스포저 = 장부가 − 개별충당금(손상 Stage 3). CRE20.
        stage3 = ecl_df[ecl_df["stage"] == 3].set_index("exposure_id")["ecl"]
        sa_book["ead"] = (sa_book["ead"]
                          - sa_book["exposure_id"].map(stage3).fillna(0.0)
                          ).clip(lower=0.0)
        sa_res, irb_res, rwa_sa, rwa_irb = _stage_credit_rwa(sa_book, irb_book)
        return (book, ecl_df, ecl_by_stage, macro, macro_path, ifrs9_deep,
                sa_book, irb_book, sa_res, irb_res, rwa_sa, rwa_irb)

    def _branch_market_op():
        return _stage_market_op_rwa(seed, market_op)

    def _branch_ccr():
        bank_book = portfolio[portfolio["asset_class"] == "bank"]
        return compute_ccr(bank_book, seed=seed) if not bank_book.empty else None

    # 구조화(집합투자증권·유동화) — 은행계정 익스포저와 모집단이 겹치지 않고
    # 어느 갈래의 산출물도 쓰지 않으므로 네 번째 독립 갈래다.
    def _branch_structured():
        return _stage_structured(asof, seed, structured_scale)

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as _ex:
        _f_credit = _ex.submit(_branch_credit)
        _f_mkt = _ex.submit(_branch_market_op)
        _f_ccr = _ex.submit(_branch_ccr)
        _f_structured = _ex.submit(_branch_structured)
        (portfolio, ecl_df, ecl_by_stage, macro, macro_path, ifrs9_deep,
         sa_book, irb_book, sa_res, irb_res, rwa_sa, rwa_irb) = _f_credit.result()
        # 이후 전 단계(모니터링·집중도·원장 실체화)는 파이프라인이 **실제로
        # 쓴** 포트폴리오(SA 파라미터 충전본)를 본다 — 원본을 남기면 원장이
        # 실사용과 다른 실행을 설명하게 된다 (F-501 유형).
        mkt, op, mkt_positions, bi_components, op_notional = _f_mkt.result()
        ccr_result = _f_ccr.result()
        structured = _f_structured.result()
    rwa_credit_internal = rwa_sa + rwa_irb    # CCR·구조화는 _stage_capital에서 합산

    # 5-7. Output floor → CapitalStack → BIS → leverage
    (floor, rwa_final, capital, bis, leverage,
     rwa_internal_total, rwa_standardised_total, rwa_ccr, el_vs_prov) = _stage_capital(
        portfolio, rwa_sa, rwa_irb, mkt, op, total_ead,
        output_floor=output_floor, buffers=buffers, ccr=ccr_result,
        capital=capital_ledger,
        irb_el=float(irb_res["el"].sum()) if "el" in irb_res.columns else 0.0,
        eligible_provisions=float(ecl_df["ecl"].sum()),
        structured=structured,
    )

    # 8-11. Monitoring, limits/concentration, RAPM
    # 한도 정의는 원장에서 읽는다. 원장 자체는 신규 원장 스테이지가 다시 싣지만
    # 한도 산출이 그보다 앞서므로 여기서 한 번 세워 두 곳이 같은 프레임을 본다.
    from risk_lib.limits_master import build_limit_definitions as _build_limits
    limit_ledger = _build_limits()
    monitoring = _stage_monitoring(portfolio, seed)
    limit_report, limit_full, conc = _stage_limits_concentration(
        portfolio, capital.tier1, limit_ledger)
    rapm_by_class = _stage_rapm(irb_book, hurdle_rate)
    rapm_deep_result = compute_rapm_deep(irb_book, hurdle_rate=hurdle_rate)

    # 12a. ALM (IRRBB / LCR / NSFR) — 전 축 위기상황분석이 재설정 사다리와
    # LCR 구성요소를 입력으로 쓰므로 스트레스보다 먼저 만든다.
    alm = _stage_alm(portfolio, capital, seed, asof=asof.isoformat())

    # 12b. 운영손실 — 운영 축이 손실을 충격해 ILM으로 되돌리므로 역시 선행한다.
    # 운영손실은 운영 도메인의 기준(독립 명목)을 쓴다 — 신용 EAD가 아니다.
    op_loss_result = compute_op_loss(op_notional, seed=seed,
                                     sma_capital=op.rwa * 0.08)

    # 12c. Stress + reverse stress + quarterly capital path.  Hold non-IRB RWA
    # fixed at (rwa_final - rwa_irb) so baseline stress reconciles with BIS.
    rwa_other_fixed = rwa_final - rwa_irb
    books = _stress_books(portfolio, irb_book, sa_book, capital, mkt_positions,
                          bi_components, op, op_loss_result, alm, op_notional,
                          ccr_rwa=rwa_ccr, structured=structured)
    stress, reverse, stress_path, stress_path_trough = _stage_stress(
        irb_book, capital, rwa_other_fixed, bis, quarters, buffers, books,
    )

    # 12d. 신규 원장 스테이지 — RDM 분해를 여기서 한 번만 돌리고 그 결과를
    # 실체화 엔진에 넘긴다. 실체화가 다시 분해하면 두 벌이 되고, 두 벌이
    # 갈라지면 원장 FK가 어느 쪽을 가리키는지 알 수 없게 된다.
    from risk_lib.datamodel.decompose import decompose as _decompose
    rdm_base = _decompose(portfolio, asof=asof.isoformat(), seed=seed)
    ledgers = _stage_ledgers(
        portfolio, rdm_base, alm, capital, bis, stress_path, ecl_df,
        {"sa": rwa_sa, "irb": rwa_irb, "ccr": rwa_ccr, "market": mkt.rwa,
         "op": op.rwa, "structured_total": structured.rwa_internal,
         "final_total": rwa_final},
        op_loss_result, limit_report,
        asof=asof.isoformat(), seed=seed)

    # 13. 내부자본(ICAAP)
    icaap = _stage_icaap(sa_res, irb_res, mkt, op, alm, conc, capital,
                         structured, ccr_rwa=rwa_ccr)

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
    limits_deep_result = compute_limits_deep(
        portfolio, capital.tier1, asof=asof.isoformat(), seed=seed)
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
        portfolio=portfolio,
        meta={"asof": asof.isoformat(), "asof_source": asof_source,
              "pillar2": dict(pillar2),
              "institution_code": institution_code,
              "institution_type": institution_type},
        sa_results=sa_res, irb_results=irb_res,
        bis_result=bis, rwa_total_for_bis=rwa_final,
        leverage_result=leverage, output_floor_result=floor,
        market_rwa=mkt.rwa, market_positions=mkt_positions,
        op_rwa=op.rwa,
        # 구성요소 재합산 대사가 부분(WARN)에 머무르지 않게 CCR·구조화를 넘긴다.
        # 넘기지 않으면 `rwa_components_reconcile`이 SA·IRB만 보고 두 항을
        # 뺀 채 합계를 맞추므로, 그 두 항의 변조를 잡지 못한다.
        ccr_rwa=rwa_ccr,
        structured_rwa=float(structured.rwa_internal) if structured else 0.0,
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
        capital_basis=capital_basis,
        capital_stack=capital,
        total_ead=total_ead,
        ledger_tables=ledgers["tables"],
    )
    # v0.14.0 — cross-domain 정합성 (PD↔RWA, RWA↔BIS, ECL↔RWA,
    # 한도↔집중, RAPM↔EC, 스트레스↔BIS).  재현성 digest는 호출자가
    # 두 차례 실행을 비교하므로 여기서는 생략 (cross-domain test가 검증).
    for _xc in run_cross_domain_checks(
        rwa={"sa": rwa_sa, "irb": rwa_irb, "ccr": rwa_ccr,
             "market": mkt.rwa, "op": op.rwa,
             "structured_total": structured.rwa_internal,
             "final_total": rwa_final, "output_floor": floor},
        bis_result=bis,
        icaap_result=icaap,
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
    # 구성요소는 최종 RWA 항등식(sa+irb+ccr+market+op+structured+floor add-on)
    # 전부를 넘긴다. 네 항만 넘기면 `decompose_rwa`가 나머지를 미배분으로
    # 드러낸다. 예전에는 그 잔차가 "Output floor 가산"으로 표시되어 CCR과
    # 구조화가 산출하한 안에 숨었다.
    shim.rwa = {
        "sa": rwa_sa, "irb": rwa_irb, "ccr": rwa_ccr,
        "market": mkt.rwa, "op": op.rwa,
        "structured_total": (float(structured.rwa_internal)
                             if structured else 0.0),
        "output_floor": floor,
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
    # `capital`은 이미 EL 차감·초과충당금 산입이 반영된 값이다(_stage_capital).
    # 분해에 차감액을 함께 넘겨 명세에 그 줄이 보이게 하되, 총계는 입력과
    # 같아야 한다 — 분해는 표시용이지 자본을 다시 줄이는 자리가 아니다.
    cet1_c, at1_c, t2_c = synthesise_components_from_stack(
        cet1_total=capital.cet1,
        at1_total=capital.additional_t1,
        tier2_total=capital.tier2,
        irb_rwa=rwa_irb,
        el_shortfall=el_vs_prov["shortfall"],
    )
    # 국가별 익스포저는 포트폴리오가 실제로 들고 있는 것을 센다. 이전에는
    # KR 80%/US 8%/JP 5%/CN 5%/VN 2% 로 고정한 배분을 넘겼고, 그 배분은 어느
    # 기관의 원장과도 대조되지 않았다. 국가가중 CCyB 는 이 배분 위에서 나온다.
    exposures_by_country = (
        {str(k): float(v) for k, v in
         portfolio.groupby("country")["ead"].sum().items()}
        if "country" in portfolio.columns else None)
    # 완충·Pillar 2 는 전부 원장에서 온다. 이전에는 DSIB 등급 2(가산 1.5%)와
    # P2R 1.5%·P2G 1.0% 를 여기에 박아 넘겼다. 그러면 같은 기관에 대해
    # `compute_bis_ratios` 가 쓰는 요구비율과 이 계층의 요구비율이 갈리고,
    # 화면(33. 버퍼 layering)과 자본비율 화면이 서로 다른 요구치를 공시한다.
    # DSIB 는 등급이 아니라 원장의 가산율을 그대로 넘긴다. 등급표를 한 번 더
    # 거치면 원장 값과 어긋날 수 있다.
    _p2r = pillar2.get("p2r")
    _p2g = pillar2.get("p2g")
    bis_deep = compute_bis_deep(
        cet1=cet1_c, at1=at1_c, tier2=t2_c, rwa=rwa_final,
        threshold_inputs={
            "dta_temporary_diff": capital.cet1 * 0.03,
            "msr": capital.cet1 * 0.01,
            "significant_investments": capital.cet1 * 0.02,
        },
        countercyclical=float(buffers.get("countercyclical", 0.0)),
        dsib_rate=float(buffers.get("dsib", 0.0)),
        p2r=0.0 if _p2r is None else float(_p2r),
        p2g=0.0 if _p2g is None else float(_p2g),
        exposures_by_country=exposures_by_country,
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
            # 구조화 — 집합투자증권(CRE60)·유동화(CRE40). 신용 RWA의 일부이며
            # 분모에 들어간다. 표준 총계는 SEC-IRBA를 뺀 계층이다.
            "fund": structured.fund_rwa,
            "securitisation": structured.sec_rwa_internal,
            "securitisation_standardised": structured.sec_rwa_standardised,
            "structured_total": structured.rwa_internal,
            "internal_total": rwa_internal_total,
            "standardised_total": rwa_standardised_total,
            "output_floor": floor, "final_total": rwa_final,
            "market_detail": mkt, "op_detail": op,
            # 전 축 위기상황분석이 시장 포지션을 다시 충격하므로 결과에 남긴다.
            "market_positions": mkt_positions,
        "op_notional": op_notional,
            # BI 구성요소(ILDC/SC/FC)는 op_detail에 총액으로만 남는다 —
            # 사업부문별 자본배분과 업무보고서 라인은 구성요소가 있어야 한다.
            "bi_detail": bi_components,
        },
        bis=bis, leverage=leverage,
        ecl={"total": float(ecl_df["ecl"].sum()), "by_stage": ecl_by_stage},
        monitoring=monitoring,
        limits=limit_report, limits_full=limit_full, concentration=conc,
        rapm=rapm_by_class, stress=stress,
        macro_ecl=macro, reverse_stress=reverse,
        macro_ecl_path=macro_path,
        stress_path=stress_path, stress_path_trough=stress_path_trough,
        backtest=backtest, validation=validation,
        alm=alm, alm_tables=alm["tables"],
        ledger_tables=ledgers["tables"], ledger_warnings=ledgers["warnings"],
        rdm_base=rdm_base, icaap=icaap,
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
        structured=structured,
        meta={"seed": seed, "capital": capital, "hurdle_rate": hurdle_rate,
              "asof": asof.isoformat(), "asof_source": asof_source,
              "quarters": quarters,
              # 어느 기관의 산출인가. 없으면 결과 한 벌만 보고는 알 수 없고,
              # 기관을 섞은 표를 만들었을 때 그것을 잡아낼 근거도 없다.
              "institution_code": institution_code,
              # 업권. 이 파이프라인은 은행 기준 한 벌만 산출하므로, 업권이
              # 다르면 그 결과가 그 기관의 건전성 지표가 아니라는 사실을
              # 결과 자신이 들고 있어야 한다.
              "institution_type": institution_type,
              # 공유 참조 원장(거시지표 관측치)을 만들 때 쓰는 시드. 기관
              # 오프셋을 더하기 전 값이며, 실체화 단계가 이것을 봐야 같은
              # 시점 같은 지표가 기관과 무관하게 한 값으로 나온다.
              "base_seed": int(base_seed),
              "market_op": dict(market_op),
              "structured_scale": dict(structured_scale),
              "pillar2": dict(pillar2),
              "capital_basis": capital_basis,
              # 추적표가 같은 입력으로 다시 세워질 수 있게 실제 쓴 완충자본을
              # 남긴다. 없으면 `trace_from_result`가 값을 지어내야 하고, 실제로
              # 지어내고 있었다 — 화면과 보고서가 같은 은행에 다른 요구비율을
              # 보였다.
              "buffers": dict(buffers)},
    )


# ---------------------------------------------------------------- 다기관 실행부
#
# 기관 축(INST-001)을 세우고 권역별 가상 기관을 등록했지만, 태그를 붙인 것만으로는
# 축이 산다는 증거가 되지 않는다. 기관마다 파이프라인을 실제로 돌려 RWA·자본비율·
# ECL 이 각각 다른 값으로 나오고, 각자의 자체검증을 통과해야 축이 선 것이다.
#
# 합산하지 않는다. 규제자본은 기관 단위 지표이고, 통화가 다르고 환산 근거도 없다.
# 여기서 만드는 표는 전부 **기관 1행**이며 합계 행이 없다.


@dataclass
class InstitutionRun:
    """기관 한 곳의 산출 한 벌."""
    institution_code: str
    result: PipelineResult
    elapsed_sec: float
    portfolio: pd.DataFrame

    @property
    def validation_summary(self) -> dict[str, int]:
        return self.result.validation.summary()

    def passes(self) -> bool:
        return self.result.validation.passes()


@dataclass
class MultiInstitutionResult:
    """기관별 산출 묶음. 합계는 없다."""
    runs: dict[str, InstitutionRun]
    headline: pd.DataFrame
    validation: pd.DataFrame
    timing: pd.DataFrame
    ledgers: dict[str, pd.DataFrame]
    asof: str
    seed: int

    def failing(self) -> list[str]:
        return [c for c, r in self.runs.items() if not r.passes()]


def _headline_row(code: str, run: InstitutionRun,
                  master: pd.DataFrame, profile: pd.DataFrame) -> dict:
    r = run.result
    m = master[master["institution_code"] == code].iloc[0]
    p = profile[profile["institution_code"] == code].iloc[0]
    rwa = r.rwa
    final = float(rwa["final_total"])
    alm = r.alm or {}
    lcr = getattr(alm.get("lcr"), "lcr", float("nan"))
    nsfr = getattr(alm.get("nsfr"), "nsfr", float("nan"))
    # 업권별 건전성 체계. 산출은 은행 기준 한 벌뿐이라 증권 기관의 자본·유동성
    # 비율은 참고치다. 표에 그 사실이 없으면 헤드라인만 보고 은행 비율을 그
    # 기관의 건전성 지표로 읽게 된다.
    from risk_lib import institutions as _inst
    itype = str(m["institution_type"])
    regime = _inst.prudential_regime(itype)
    applies = _inst.regime_applies(itype)
    return {
        "institution_code": code,
        "name": (m["name_ko"] if bool(m["is_domestic"]) else m["name_en"]),
        "region": m["region"],
        "institution_type": itype,
        "regulatory_regime": m["regulatory_regime"],
        "prudential_regime": regime,
        "ratio_applicable": bool(applies),
        "ratio_basis": ("적용" if applies
                        else f"참고치 ({_inst.IMPLEMENTED_REGIME} 기준 산출, "
                             f"적용 체계는 {regime})"),
        "currency": m["currency"],
        "archetype": p["archetype"],
        "n_exposures": int(len(run.portfolio)),
        "total_ead": float(run.portfolio["ead"].sum()),
        "rwa_credit": float(rwa["sa"]) + float(rwa["irb"]) + float(rwa["ccr"]),
        "rwa_market": float(rwa["market"]),
        "rwa_op": float(rwa["op"]),
        "rwa_structured": float(rwa["structured_total"]),
        "rwa_final": final,
        "market_op_share": (float(rwa["market"]) + float(rwa["op"])) / final,
        "cet1_ratio": float(r.bis.cet1_ratio),
        "tier1_ratio": float(r.bis.tier1_ratio),
        "total_ratio": float(r.bis.total_ratio),
        "leverage_ratio": float(r.leverage.leverage_ratio),
        "ecl_total": float(r.ecl["total"]),
        "lcr": float(lcr),
        "nsfr": float(nsfr),
        "data_origin": p["data_origin"],
        "evidence_status": p["evidence_status"],
    }


def run_multi_institution(
    codes: "Sequence[str] | None" = None,
    *,
    seed: int = 42,
    asof: str = "2025-12-31",
    ledgers: "dict[str, pd.DataFrame] | None" = None,
) -> MultiInstitutionResult:
    """등록된 기관 전부(또는 `codes`)에 대해 파이프라인을 돌린다.

    기관마다 쓰는 것:
      포트폴리오   `data_gen_intl.generate_institution_portfolio`
      난수 스트림  `institutions.institution_seed` (seed + 원장의 오프셋)
      완충자본·요구수익률·산출하한·시장운영 모수  `inst_profile`

    돌리는 순서는 기관 원장의 등록 순서이며 기관 간 상태를 공유하지 않는다.
    같은 (asof, seed) 로 몇 번을 돌려도 같은 값이 나온다. `asof` 에 기본값을
    둔 것은 벽시계를 타지 않기 위해서다. 보고기준일은 호출자가 정한다.
    """
    import time
    from risk_lib import data_gen_intl as intl
    from risk_lib import institutions as _inst

    led = intl.build_all() if ledgers is None else ledgers
    master = led[_inst.AXIS_MASTER]
    profile = led[intl.INST_PROFILE.name]
    all_codes = intl.institution_codes(master)
    todo = tuple(all_codes) if codes is None else tuple(codes)
    unknown = [c for c in todo if c not in all_codes]
    if unknown:
        raise ValueError(f"기관 원장에 없는 기관코드: {unknown}")

    runs: dict[str, InstitutionRun] = {}
    head: list[dict] = []
    val: list[dict] = []
    for code in todo:
        prow = intl.profile_row(code, profile)
        port = intl.generate_institution_portfolio(
            code, seed=seed, master=master, profile=profile,
            mix=led[intl.INST_PORTFOLIO_MIX.name],
            country_mix=led[intl.INST_COUNTRY_MIX.name],
            lexicon=led[intl.INTL_LABEL_LEXICON.name])
        t0 = time.perf_counter()
        res = run_pipeline(
            port.drop(columns=[_inst.INSTITUTION_COLUMN]),
            seed=_inst.institution_seed(seed, code, master),
            hurdle_rate=float(prow["hurdle_rate"]),
            output_floor=float(prow["output_floor"]),
            buffers=intl.buffers_for(code, profile),
            asof=asof,
            market_op=intl.market_op_params(code, profile),
            structured_scale=intl.structured_scale_for(code, profile),
            pillar2=intl.pillar2_for(code, profile),
            capital_ledger=intl.capital_ledger_for(
                code, float(port["ead"].sum()), profile),
            capital_basis=intl.CAPITAL_BASIS,
            institution_code=code,
            institution_type=str(
                master.loc[master["institution_code"] == code,
                           "institution_type"].iloc[0]),
            # 공유 참조 원장은 기관 오프셋을 더하기 전 시드로 만든다.
            base_seed=seed,
        )
        elapsed = time.perf_counter() - t0
        run = InstitutionRun(code, res, elapsed, port)
        runs[code] = run
        head.append(_headline_row(code, run, master, profile))
        s = run.validation_summary
        val.append({
            "institution_code": code,
            "PASS": int(s.get("PASS", 0)),
            "WARN": int(s.get("WARN", 0)),
            "FAIL": int(s.get("FAIL", 0)),
            "n_checks": int(len(res.validation.checks)),
            "passes": bool(run.passes()),
        })

    timing = pd.DataFrame([{"institution_code": c, "elapsed_sec": r.elapsed_sec}
                           for c, r in runs.items()])
    return MultiInstitutionResult(
        runs=runs,
        headline=pd.DataFrame(head),
        validation=pd.DataFrame(val),
        timing=timing,
        ledgers=led,
        asof=asof,
        seed=seed,
    )


def institution_ledgers(run: InstitutionRun) -> dict[str, pd.DataFrame]:
    """산출 원장에 기관코드를 채운 사본. 공유 참조 원장은 손대지 않는다."""
    from risk_lib import institutions as _inst
    tables: dict[str, pd.DataFrame] = {}
    tables.update(run.result.rdm_base)
    tables.update(run.result.alm_tables)
    tables.update(run.result.ledger_tables)
    if run.result.structured is not None:
        tables.update(run.result.structured.tables)
    return _inst.stamp_all(tables, run.institution_code)
