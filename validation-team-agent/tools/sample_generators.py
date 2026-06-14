"""대규모 합성 데이터 생성기 (검증 하니스 데모용).

운영 데이터를 사용하지 않는다. 모든 데이터는 결정론적 numpy 난수(seed 명시)로
생성되며 민감정보 패턴(주민/계좌/이메일)을 포함하지 않는다.

가장 일반적 용도:
    df = credit_scoring_sample(n=100_000, seed=42)
    # columns: customer_id, obs_date, score, target, grade, pd, set
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# pd by grade (a~e): 합리적 신용평가 등급 분포
_GRADES = list("ABCDE")
_PD_BY_GRADE = {"A": 0.01, "B": 0.03, "C": 0.07, "D": 0.15, "E": 0.30}
# 등급별 표본 비중 (총합 1.0)
_GRADE_MIX = {"A": 0.30, "B": 0.30, "C": 0.20, "D": 0.15, "E": 0.05}


def credit_scoring_sample(
    n: int = 100_000,
    *,
    seed: int = 42,
    dev_ratio: float = 0.625,
    psi_shift: float = 0.0,
) -> pd.DataFrame:
    """신용평가 검증용 합성 데이터.

    psi_shift > 0 이면 OOT score 분포에 우측 shift 를 가해 PSI 가 상승하도록 한다.
    target 은 등급별 PD 의 Bernoulli. score 는 (높을수록 위험) 규약.

    반환 컬럼: customer_id, obs_date, score, target, grade, pd, set
    """
    if n < 100:
        raise ValueError("n must be >= 100")
    if not 0 < dev_ratio < 1:
        raise ValueError("dev_ratio must be in (0,1)")

    rng = np.random.default_rng(seed)
    n_dev = int(n * dev_ratio)
    n_oot = n - n_dev

    grades = rng.choice(_GRADES, size=n, p=[_GRADE_MIX[g] for g in _GRADES])
    pd_est = np.array([_PD_BY_GRADE[g] for g in grades], dtype=float)
    target = (rng.uniform(size=n) < pd_est).astype(int)

    # score: 양호(target=0)는 0근방, 부실(target=1)은 +1.5 근방. 등급이 낮을수록
    # (예: E) 평균 score 가 더 높도록 grade index shift 추가.
    grade_idx = np.array([_GRADES.index(g) for g in grades], dtype=float)
    base_score = rng.normal(0.0, 1.0, size=n) + 0.2 * grade_idx
    bad_lift = rng.normal(1.5, 0.6, size=n)
    score = np.where(target == 1, base_score + bad_lift, base_score)

    set_arr = np.array(["dev"] * n_dev + ["oot"] * n_oot)
    # OOT 분포 우측 shift (PSI 시연용)
    if psi_shift > 0:
        score[n_dev:] = score[n_dev:] + psi_shift

    obs_dates = (
        pd.date_range("2022-01-01", periods=24, freq="MS").strftime("%Y-%m-%d").tolist()
    )
    obs_arr = pd.to_datetime(rng.choice(obs_dates, size=n))

    customer_ids = [f"C{(i + 1):07d}" for i in range(n)]

    # 챌린저 score — 동일 데이터에서 약간 다른 신호 (등급 가중 + 노이즈 변경)
    # 챌린저는 일반적으로 챔피언 대비 marginal 한 변별력 변화를 보인다.
    challenger_score = np.where(
        target == 1,
        base_score + bad_lift * 0.85 + 0.4 * grade_idx,
        base_score * 0.9 + 0.3 * grade_idx,
    )
    if psi_shift > 0:
        challenger_score[n_dev:] = challenger_score[n_dev:] + psi_shift * 0.7

    df = pd.DataFrame(
        {
            "customer_id": customer_ids,
            "obs_date": obs_arr,
            "score": score,
            "score_challenger": challenger_score,
            "target": target,
            "grade": grades,
            "pd": pd_est,
            "set": set_arr,
        }
    )
    return df


def macro_stationary_series(n: int = 250, *, seed: int = 11) -> list[float]:
    """정상 시계열 (white noise)."""
    rng = np.random.default_rng(seed)
    return rng.normal(0.0, 1.0, size=n).tolist()


def macro_random_walk_series(n: int = 250, *, seed: int = 11) -> list[float]:
    """단위근 시계열 (random walk)."""
    rng = np.random.default_rng(seed)
    return np.cumsum(rng.normal(0.0, 1.0, size=n)).tolist()


def ifrs9_weight_panel(*, balanced: bool = True) -> pd.DataFrame:
    """IFRS 9 시나리오 가중치 패널 (4 시점 × 3 시나리오).

    balanced=False 면 두 번째 시점의 가중치 합이 1.1 로 위반.
    """
    rows = []
    for period in ("2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4"):
        if balanced or period != "2024-Q2":
            rows.append({"period": period, "scenario": "base", "weight": 0.5})
            rows.append({"period": period, "scenario": "adverse", "weight": 0.3})
            rows.append({"period": period, "scenario": "severe", "weight": 0.2})
        else:
            rows.append({"period": period, "scenario": "base", "weight": 0.5})
            rows.append({"period": period, "scenario": "adverse", "weight": 0.4})
            rows.append({"period": period, "scenario": "severe", "weight": 0.2})
    return pd.DataFrame(rows)


def operational_bi_sample(*, large: bool = False) -> float:
    """운영리스크 Business Indicator (EUR bn)."""
    return 40.0 if large else 3.5


def cva_counterparty_sample(n: int = 25, *, seed: int = 13) -> list[dict]:
    """CVA counterparty list (BA-CVA 입력)."""
    rng = np.random.default_rng(seed)
    return [
        {"name": f"CP{i:03d}", "scva": float(rng.uniform(5.0, 50.0))}
        for i in range(n)
    ]


def ccr_exposure_sample(*, seed: int = 17) -> dict:
    """CCR (SA-CCR) RC / PFE 가정값."""
    rng = np.random.default_rng(seed)
    return {
        "ccr_rc": round(float(rng.uniform(50.0, 300.0)), 2),
        "ccr_pfe": round(float(rng.uniform(20.0, 200.0)), 2),
    }


def concentration_exposure_sample(*, breach: bool = False, seed: int = 23) -> dict:
    """신용집중리스크 익스포저 표본. breach=True 면 동일차주 한도 초과 1건 포함."""
    rng = np.random.default_rng(seed)
    tier1 = 10_000.0
    exposures = [
        {"counterparty_id": f"CP{i:03d}",
         "group_id": f"G{i % 12:02d}",
         "exposure": round(float(rng.uniform(50.0, 400.0)), 2)}
        for i in range(40)
    ]
    if breach:
        exposures.append(
            {"counterparty_id": "CP_BIG", "group_id": "G_BIG",
             "exposure": tier1 * 0.30}  # 동일차주 25% 초과
        )
    return {
        "concentration_exposures": exposures,
        "concentration_tier1": tier1,
        "concentration_equity": tier1 * 1.1,
    }


def capital_ratio_sample(*, seed: int = 7) -> dict:
    """가상의 인터넷전문은행 X 자본비율 (unverified, demo only)."""
    rng = np.random.default_rng(seed)
    cet1 = float(rng.uniform(0.10, 0.16))
    tier1 = cet1 + float(rng.uniform(0.005, 0.015))
    total = tier1 + float(rng.uniform(0.005, 0.020))
    leverage = float(rng.uniform(0.04, 0.08))
    return {
        "capital_cet1": round(cet1, 4),
        "capital_tier1": round(tier1, 4),
        "capital_total": round(total, 4),
        "capital_leverage": round(leverage, 4),
    }


def capital_stress_sample() -> dict:
    """자본 미달 시나리오 (escalation 시연용)."""
    return {
        "capital_cet1": 0.030,
        "capital_tier1": 0.040,
        "capital_total": 0.050,
        "capital_leverage": 0.020,
    }


def icaap_sample(*, stressed: bool = False) -> dict:
    """ICAAP 입력 (가용/필요내부자본). stressed=True 면 스트레스 후 미달."""
    required = {
        "credit": 4_800.0,
        "market": 1_300.0,
        "operational": 900.0,
        "irrbb": 800.0,
        "concentration": 700.0,
    }
    if stressed:
        return {
            "icaap_available_capital": 8_000.0,
            "icaap_required_by_risk": required,
            "icaap_diversification": 500.0,
            "icaap_post_stress_available": 7_000.0,  # post-stress < required
        }
    return {
        "icaap_available_capital": 11_000.0,
        "icaap_required_by_risk": required,
        "icaap_diversification": 500.0,
        "icaap_post_stress_available": 9_500.0,
    }


def alm_sample(*, stressed: bool = False) -> dict:
    """ALM 입력 (만기갭 / 조달집중 / 예대율 / NSFR). 단위: 십억원 가정."""
    if stressed:
        return {
            "alm_gaps_by_bucket": {
                "1M": -9_000.0, "3M": -5_000.0, "6M": -2_000.0,
                "1Y": 1_000.0, "3Y": 6_000.0, "over_3Y": 10_000.0,
            },
            "alm_total_assets": 100_000.0,   # 누적 -16% @6M → 한도 위반
            "alm_funding_by_provider": [12_000.0] + [800.0] * 40,
            "alm_loans": 102_000.0,
            "alm_deposits": 100_000.0,       # 예대율 102% → 위반
            "liquidity_asf": 90_000.0,
            "liquidity_rsf": 100_000.0,      # NSFR 0.90 → below_min
        }
    return {
        "alm_gaps_by_bucket": {
            "1M": -2_000.0, "3M": -1_000.0, "6M": 500.0,
            "1Y": 1_500.0, "3Y": 4_000.0, "over_3Y": 8_000.0,
        },
        "alm_total_assets": 100_000.0,
        "alm_funding_by_provider": [2_000.0] + [1_600.0] * 40,
        "alm_loans": 93_000.0,
        "alm_deposits": 100_000.0,
        "liquidity_asf": 110_000.0,
        "liquidity_rsf": 100_000.0,
    }


def irrbb_behavioral_sample() -> dict:
    """IRRBB behavioral assumption — NMD (non-maturity deposits) + prepayment.

    BCBS SRP31 §115 NMD core/non-core 분류 + prepayment rate.
    """
    return {
        "nmd_total_bn": 480_000.0,
        "nmd_core_ratio": 0.70,
        "nmd_repricing_lag_months": 18,
        "loan_prepayment_rate_annual": 0.08,
        "term_deposit_early_withdrawal_rate": 0.04,
        "duration_assets_yrs": 3.2,
        "duration_liabilities_yrs": 1.8,
        "duration_gap_yrs": 1.4,
        "framework": "BCBS SRP31 §115 (Behavioral assumptions)",
    }


def concentration_segments_sample() -> dict:
    """산업·지역·통화별 집중 분해 + top 10 exposures."""
    industry = {
        "제조업": 220_000.0,
        "도소매": 180_000.0,
        "부동산/임대": 160_000.0,
        "건설": 95_000.0,
        "금융업": 80_000.0,
        "정보통신": 70_000.0,
        "서비스": 60_000.0,
        "기타": 35_000.0,
    }
    region = {
        "수도권": 580_000.0,
        "영남권": 180_000.0,
        "충청권": 95_000.0,
        "호남권": 70_000.0,
        "강원/제주": 35_000.0,
    }
    currency = {
        "KRW": 820_000.0,
        "USD": 110_000.0,
        "JPY": 18_000.0,
        "EUR": 12_000.0,
        "CNY": 7_000.0,
    }
    top_exposures = [
        {"name": f"Group-{i:02d}",
         "industry": list(industry)[i % len(industry)],
         "exposure_bn": 280.0 - i * 18.0,
         "pct_tier1": (280.0 - i * 18.0) / 10_000.0}
        for i in range(10)
    ]
    return {
        "industry": industry,
        "region": region,
        "currency": currency,
        "top_exposures": top_exposures,
    }


def var_components_sample() -> dict:
    """VaR 분해 — General market risk vs Specific risk + SVaR + IRC.

    BCBS MAR99 (Internal Models) 의 capital charge 구성요소.
    """
    return {
        "var_99_total": 18.5,        # bn 원, 일간 99% VaR
        "var_general_market": 14.2,  # 일반 시장리스크
        "var_specific": 4.3,         # 개별 발행자 risk
        "svar_99": 27.8,             # Stressed VaR (2008-2009 calibration)
        "irc_99_9": 12.0,            # Incremental Risk Charge (credit migration)
        "multiplier": 3.0,           # 감독자 기본 multiplier (BCBS MAR99 §32.9)
        "yellow_multiplier_add": 0.4,
        "asset_classes": {
            "Interest Rate": 9.2,
            "Equity": 4.0,
            "FX": 3.1,
            "Commodity": 1.2,
            "Credit Spread": 4.8,
        },
        "framework": "BCBS MAR99 (Internal Models) + FRTB MAR50 (Sensitivity-Based)",
    }


def lcr_by_currency_sample() -> list[dict]:
    """통화별 LCR 분해 (시행세칙 외화LCR 80% + BCBS LCR 100%)."""
    return [
        {"currency": "KRW (원화)", "hqla": 130_000.0, "outflow": 100_000.0,
         "min_required": 1.00, "note": "원화 LCR ≥ 100%"},
        {"currency": "USD",       "hqla": 12_000.0,  "outflow": 14_000.0,
         "min_required": 0.80, "note": "외화 LCR 80% (감독원 행정지도)"},
        {"currency": "JPY",       "hqla": 3_500.0,   "outflow": 3_000.0,
         "min_required": 0.80, "note": "외화 LCR 80%"},
        {"currency": "EUR",       "hqla": 1_800.0,   "outflow": 2_500.0,
         "min_required": 0.80, "note": "외화 LCR 80% (미달 가능성)"},
        {"currency": "CNY",       "hqla": 900.0,     "outflow": 1_200.0,
         "min_required": 0.80, "note": "외화 LCR 80%"},
    ]


def nii_sensitivity_sample() -> list[dict]:
    """ΔNII (Net Interest Income) sensitivity — 6 표준 시나리오."""
    base_nii_annual = 3_000.0  # bn 원
    return [
        {"scenario": "parallel_up",   "delta_nii_pct": +0.08, "delta_nii_bn": +base_nii_annual*0.08},
        {"scenario": "parallel_down", "delta_nii_pct": -0.06, "delta_nii_bn": -base_nii_annual*0.06},
        {"scenario": "steepener",     "delta_nii_pct": +0.03, "delta_nii_bn": +base_nii_annual*0.03},
        {"scenario": "flattener",     "delta_nii_pct": -0.04, "delta_nii_bn": -base_nii_annual*0.04},
        {"scenario": "short_rate_up", "delta_nii_pct": +0.05, "delta_nii_bn": +base_nii_annual*0.05},
        {"scenario": "short_rate_down", "delta_nii_pct": -0.03, "delta_nii_bn": -base_nii_annual*0.03},
    ]


def intraday_liquidity_sample() -> dict:
    """일중유동성 (intraday liquidity) panel — BCBS d423 monitoring tools."""
    return {
        "daily_max_intraday_usage_bn": 4_200.0,
        "average_intraday_usage_bn": 2_100.0,
        "intraday_credit_lines_bn": 6_500.0,
        "stress_day_usage_bn": 5_800.0,
        "peak_to_average_ratio": 2.0,
        "framework": "BCBS d423 (Monitoring tools for intraday liquidity management)",
    }


def rwa_decomposition_sample() -> dict:
    """Pillar 1 RWA 분해 (Credit / Market / Operational / CVA + Output Floor).

    합성 가정값. 운영 시스템에서는 자체 RWA 산정 (IRBA / IMM / SMA / SA-CVA)
    결과로 대체.
    """
    rwa_internal = {
        "credit_irba": 120_000.0,
        "credit_sa": 25_000.0,
        "market_imm": 18_000.0,
        "operational_sma": 14_000.0,
        "cva_basa": 4_500.0,
        "ccr_sa": 6_500.0,
    }
    rwa_standardised_full = {
        "credit_sa_full": 175_000.0,
        "market_sa_full": 22_000.0,
        "operational_sa_full": 14_000.0,
        "cva_sa_full": 5_000.0,
        "ccr_sa_full": 7_000.0,
    }
    total_internal = sum(rwa_internal.values())
    total_sa_full = sum(rwa_standardised_full.values())
    output_floor_ratio = 0.725  # FRTB Output Floor 72.5% (BCBS d424)
    floor_applied = max(total_internal, output_floor_ratio * total_sa_full)
    return {
        "by_approach": rwa_internal,
        "standardised_full": rwa_standardised_full,
        "total_internal": total_internal,
        "total_standardised": total_sa_full,
        "output_floor_ratio": output_floor_ratio,
        "rwa_after_floor": floor_applied,
        "floor_binding": floor_applied > total_internal,
    }


def srep_capital_sample() -> dict:
    """SREP (Supervisory Review and Evaluation Process) capital add-on 가정.

    유럽 SSM/SREP 표준 + 국내 시행세칙 보조. 자동 점검 시연용 합성 input.
    """
    return {
        "p2r_pct": 0.020,    # Pillar 2 Requirement (binding)
        "p2g_pct": 0.010,    # Pillar 2 Guidance (non-binding)
        "stress_buffer_pct": 0.015,  # 스트레스 결과 반영 buffer
        "rationale": [
            "P2R: 시장리스크 모형 위험 + 운영리스크 추가 capital (SSM SREP 가이드).",
            "P2G: 스트레스 테스트 결과 기반 비강제 권고.",
            "stress buffer: severely adverse 시나리오 손실 흡수용 내부 buffer.",
        ],
        "framework": "SSM SREP Methodology + 시행세칙 [별표 3]",
    }


def quarterly_panel(*, n_quarters: int = 4, seed: int = 31) -> list[dict]:
    """4분기 합성 panel — 자본/유동성/내부자본/IRRBB 지표 시계열.

    실제 운영 데이터가 아니라 시계열 trend 시각화·재현성 검증용 합성 시드.
    각 분기는 결정론적으로 동일 seed 에서 재현된다.
    """
    import numpy as np

    rng = np.random.default_rng(seed)
    panel = []
    # 시작 값 — buffer 여유 상태
    cet1 = 0.135
    leverage = 0.052
    lcr = 1.40
    nsfr = 1.18
    icaap = 1.45
    delta_eve = 0.045
    psi = 0.04
    hhi = 0.028

    for q in range(n_quarters):
        period = f"Q{q+1}"
        # 점진 악화 + 작은 노이즈 (재현 가능, seed 결정론)
        cet1 = max(0.045, cet1 - 0.005 + float(rng.normal(0, 0.003)))
        leverage = max(0.020, leverage - 0.002 + float(rng.normal(0, 0.001)))
        lcr = max(0.70, lcr - 0.06 + float(rng.normal(0, 0.02)))
        nsfr = max(0.85, nsfr - 0.03 + float(rng.normal(0, 0.01)))
        icaap = max(0.85, icaap - 0.08 + float(rng.normal(0, 0.02)))
        delta_eve = min(0.30, delta_eve + 0.02 + float(rng.normal(0, 0.005)))
        psi = min(0.30, psi + 0.025 + float(rng.normal(0, 0.005)))
        hhi = min(0.20, hhi + 0.012 + float(rng.normal(0, 0.002)))
        panel.append({
            "period": period,
            "cet1": round(cet1, 4),
            "leverage": round(leverage, 4),
            "lcr": round(lcr, 3),
            "nsfr": round(nsfr, 3),
            "icaap": round(icaap, 3),
            "delta_eve": round(delta_eve, 4),
            "psi": round(psi, 4),
            "hhi": round(hhi, 4),
        })
    return panel


def market_var_pnl_panel(*, n_days: int = 250, seed: int = 41) -> list[dict]:
    """일일 P&L vs VaR backtest panel (결정론적).

    실현 P&L 이 사전 VaR 한도를 초과한 일자를 표시. 합성 데이터로 BCBS MAR99
    traffic light 와 동일 schema 의 backtest 데이터셋을 만든다.
    """
    import numpy as np

    rng = np.random.default_rng(seed)
    var_99 = -2.33  # 표준화 99% VaR (정규 가정)
    pnl_z = rng.standard_normal(n_days)
    # 일부 fat tail (stress 일자)
    stress_idx = rng.choice(n_days, size=max(1, n_days // 50), replace=False)
    pnl_z[stress_idx] -= rng.uniform(1.0, 2.5, size=len(stress_idx))
    pnl = pnl_z  # 단위 변환 없이 정규화 P&L
    panel = []
    for d in range(n_days):
        excess = bool(pnl[d] < var_99)
        panel.append({
            "day": d + 1,
            "pnl": round(float(pnl[d]), 4),
            "var_99": var_99,
            "exception": excess,
        })
    return panel


def operational_loss_scenarios(*, seed: int = 53) -> list[dict]:
    """운영리스크 시나리오 손실 표 (rogue trader / IT 장애 / 외부 사기 / 자연재해).

    BCBS OPE25 의 ILDC 사용 시 input 이 되는 시나리오 frequency/severity 가정.
    본 표는 가정값이며 운영 시스템에서는 자체 LDA 결과로 대체된다.
    """
    import numpy as np

    rng = np.random.default_rng(seed)
    types = [
        ("Rogue Trader", "Internal Fraud", 0.5, 2_000.0),
        ("IT 장애 (24h+)", "Business Disruption", 2.0, 500.0),
        ("외부 사기 (대규모)", "External Fraud", 1.5, 800.0),
        ("자연재해 (지점)", "Damage to Physical Assets", 0.2, 300.0),
        ("규제 제재", "Clients/Products & Business Practices", 0.3, 1_500.0),
        ("내부 절차 실패", "Execution, Delivery & Process Management", 5.0, 150.0),
    ]
    scenarios = []
    for name, basel_class, freq, sev_mean in types:
        # 단순 가정 — frequency × severity_mean (참고용)
        annual_expected = freq * sev_mean
        # 99% 손실 추정 (lognormal 근사)
        sigma = 0.8
        sev_99 = float(sev_mean * np.exp(2.326 * sigma))
        scenarios.append({
            "scenario": name,
            "basel_event_class": basel_class,
            "frequency_per_year": freq,
            "severity_mean_bn": sev_mean,
            "annual_expected_bn": round(annual_expected, 2),
            "severity_99_bn": round(sev_99, 2),
        })
    _ = rng  # 결정론 — 단순 가정 표
    return scenarios


def macroprudential_overlay() -> dict:
    """Macroprudential overlay 상태 — DSR/LTV/CCyB/SyRB.

    감독원 거시건전성 조치 현황 (시행세칙 + 금융위 공시) 의 자동 점검 매핑.
    본 값은 자동 점검 시연용 합성 입력이며 운영 시스템에서는 실제 정책 인용.
    """
    return {
        "ccyb_required_pct": 0.0,  # 현재 0%
        "ccyb_buffer_active": False,
        "syrb_required_pct": 0.0,  # 시스템적 위험 buffer
        "dti_household_ratio": 0.40,  # DSR 평균 (가정)
        "ltv_residential_avg": 0.55,
        "ltv_residential_warning": 0.70,
        "leverage_buffer_for_gsib": 0.0,  # 국내 D-SIB 만 적용
        "framework_versions": {
            "ccyb": "BCBS d189 §136-145 + 시행세칙 [별표 3]",
            "ltv_dsr": "주택담보대출 규제 (감독시행세칙) + 가계대출 관리방안",
            "syrb": "BCBS d189 §157 + 시행세칙",
        },
    }


def ifrs9_stage_migration_sample(*, seed: int = 71) -> dict:
    """IFRS 9 stage 1/2/3 migration matrix + ECL 분해 (합성).

    BCBS / IFRS 9: stage 1 (12m EL) / stage 2 (lifetime EL, SICR) / stage 3 (impaired).
    본 sample 은 점검 도구 시연용 결정론적 합성이며 운영 ECL 산출 대체 불가.
    """
    # 분기 시작 stage × 분기 말 stage migration matrix
    matrix = {
        "S1": {"S1": 0.945, "S2": 0.050, "S3": 0.005},
        "S2": {"S1": 0.150, "S2": 0.770, "S3": 0.080},
        "S3": {"S1": 0.010, "S2": 0.060, "S3": 0.930},
    }
    portfolio = {
        "S1": {"ead": 80_000.0, "pd_12m": 0.012, "lgd": 0.45},
        "S2": {"ead": 15_000.0, "pd_lifetime": 0.085, "lgd": 0.45},
        "S3": {"ead": 5_000.0,  "pd_lifetime": 1.000, "lgd": 0.55},
    }
    ecl = {
        "S1": portfolio["S1"]["ead"] * portfolio["S1"]["pd_12m"] * portfolio["S1"]["lgd"],
        "S2": portfolio["S2"]["ead"] * portfolio["S2"]["pd_lifetime"] * portfolio["S2"]["lgd"],
        "S3": portfolio["S3"]["ead"] * portfolio["S3"]["pd_lifetime"] * portfolio["S3"]["lgd"],
    }
    return {
        "stages": ["S1", "S2", "S3"],
        "migration_matrix": matrix,
        "portfolio": portfolio,
        "ecl_by_stage": {k: round(v, 2) for k, v in ecl.items()},
        "total_ecl": round(sum(ecl.values()), 2),
        "sicr_definition": "30일 이상 연체 OR 등급 3단계 이상 하향 OR 거시 FLI 임계 진입",
        "framework": "IFRS 9 §B5.5 (SICR) + B5.5.17 (FLI)",
    }


def stress_test_scenarios_sample() -> list[dict]:
    """스트레스 테스트 시나리오 panel (baseline / adverse / severely adverse)."""
    return [
        {
            "scenario": "baseline",
            "gdp_growth": 0.025, "unemployment": 0.030, "house_price": 0.040,
            "policy_rate": 0.035,
            "credit_loss_multiplier": 1.0,
            "cet1_post_stress": 0.130, "lcr_post_stress": 1.30,
            "icaap_post_stress": 1.40, "weight": 0.5,
        },
        {
            "scenario": "adverse",
            "gdp_growth": -0.015, "unemployment": 0.055, "house_price": -0.080,
            "policy_rate": 0.050,
            "credit_loss_multiplier": 1.8,
            "cet1_post_stress": 0.092, "lcr_post_stress": 1.05,
            "icaap_post_stress": 1.05, "weight": 0.3,
        },
        {
            "scenario": "severely_adverse",
            "gdp_growth": -0.045, "unemployment": 0.085, "house_price": -0.160,
            "policy_rate": 0.075,
            "credit_loss_multiplier": 3.2,
            "cet1_post_stress": 0.055, "lcr_post_stress": 0.85,
            "icaap_post_stress": 0.90, "weight": 0.2,
        },
    ]
