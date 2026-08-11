"""인터넷전문은행 3사 (카카오뱅크 · 케이뱅크 · 토스뱅크) 케이스 스터디 분석.

2025년 3분기/말 공시자료를 토대로 각 은행의 자산·자본 구조를 합성한 후
risk_lib의 baseline + adverse + severe + reverse stress 파이프라인으로
통합 위기상황분석을 수행한다.

공시 출처 (2026-06 검색):
- 케이뱅크: BIS 15.01%, NPL 0.54%, 연체율 0.56% (3Q 2025), 총여신 18.4조
- 카카오뱅크: NPL 0.55%, 연체율 0.51%, 충당금 212% (3Q 2025), 총여신 46.9조
- 토스뱅크: BIS 16.24%, NPL 0.84%, 연체율 1.11%, 충당금 322% (FY 2025), 총여신 15.35조

각 은행 portfolio 비중은 공시 narrative + 인뱅 전반 동향을 반영해 calibrate:
- 카카오뱅크: 모기지 비중 가장 큼 + 가계신용 + 일부 기업 (개인사업자)
- 케이뱅크: 모기지 중심 + 가계신용 + 일부 기업
- 토스뱅크: 가계신용 중심 + 개인사업자 (중저신용자 비중 50%+)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class BankProfile:
    """인터넷은행 공시 기반 프로파일."""
    name: str
    short: str
    total_loans_krw: float                  # 총여신 (원)
    total_deposits_krw: float               # 총수신 (원)
    bis_capital_ratio: float                # BIS 자기자본비율 (실측)
    npl_ratio: float                        # 고정이하여신비율
    delinquency_ratio: float                # 연체율
    coverage_ratio: float                   # 충당금 적립률 (NPL 대비)
    quarterly_net_income_krw: float         # 누적 당기순이익
    mid_low_credit_share: float             # 중저신용자 신용대출 비중 (신규)
    # 자산군 구성 비중 (총여신 대비)
    mix_corporate: float                    # 기업대출
    mix_retail_unsecured: float             # 가계 신용대출
    mix_mortgage: float                     # 주담대
    # 기타
    capital_total_krw: float                # 총자본 (NPL & 추정)
    notes: str = ""


# 2025년 3분기/말 공시 + 합리적 추정값으로 정리
KAKAO = BankProfile(
    name="카카오뱅크", short="kakao",
    total_loans_krw=46.9e12,
    total_deposits_krw=68.1e12,
    bis_capital_ratio=0.205,         # 인뱅 평균 ~20% 수준 (공시 미확보 → 추정)
    npl_ratio=0.0055,
    delinquency_ratio=0.0051,
    coverage_ratio=2.12,
    quarterly_net_income_krw=3751e8,
    mid_low_credit_share=0.494,
    mix_corporate=0.08,              # 기업대출 비중 (개인사업자 포함, 상대적으로 낮음)
    mix_retail_unsecured=0.32,       # 가계 신용대출
    mix_mortgage=0.60,               # 주담대 비중 가장 큼
    capital_total_krw=6.5e12,        # 자기자본 추정 (BIS 20.5% × RWA 추정)
    notes="모기지 중심, 가계 비중 92%",
)

KBANK = BankProfile(
    name="케이뱅크", short="kbank",
    total_loans_krw=18.4e12,
    total_deposits_krw=28.4e12,
    bis_capital_ratio=0.1501,
    npl_ratio=0.0054,
    delinquency_ratio=0.0056,
    coverage_ratio=2.50,             # 인뱅 표준 추정
    quarterly_net_income_krw=1034e8,
    mid_low_credit_share=0.382,
    mix_corporate=0.10,              # 케뱅 기업 비중 일부
    mix_retail_unsecured=0.30,
    mix_mortgage=0.60,               # 케뱅 아담대 + 주담대 큰 비중
    capital_total_krw=2.0e12,        # BIS 15.0% × RWA
    notes="중저신용자 비중 작음(38.2%) → 자본 보수적",
)

TOSS = BankProfile(
    name="토스뱅크", short="toss",
    total_loans_krw=15.35e12,
    total_deposits_krw=30.07e12,
    bis_capital_ratio=0.1624,
    npl_ratio=0.0084,                # 가장 높음
    delinquency_ratio=0.0111,        # 가장 높음 (중저신용 비중 영향)
    coverage_ratio=3.22,             # 가장 보수적
    quarterly_net_income_krw=968e8,
    mid_low_credit_share=0.502,      # 가장 높음
    mix_corporate=0.15,              # 개인사업자 비중 확대
    mix_retail_unsecured=0.55,       # 신용대출 중심
    mix_mortgage=0.30,               # 모기지 상대적으로 작음
    capital_total_krw=2.5e12,        # BIS 16.24% × RWA
    notes="중저신용자 비중 50%+, 신용대출 중심, 연체율 최고",
)


BANKS = [KAKAO, KBANK, TOSS]


# ============================================================================
# 2026년 1분기 공시 — 최신 스냅샷
# ============================================================================
# 출처:
# - 카카오뱅크 1Q26: 분기 순익 1,873억(+36.3%, 분기 최대), CET1 14%+, 주담대 중심
# - 케이뱅크   1Q26: 순익 332억(+106.8%), BIS 21.47%(+6.46%p, IPO 자본 효과),
#                    CET1 +7.04%p 급등, 이자이익 1,252억, 중저신용 평균잔액 31.9%
# - 토스뱅크   1Q26: 순익 296억(+58%), 여신 15.5조(+4.4%), BIS 16.62%(+0.72%p),
#                    연체율 1.07%(-0.19%p), NPL 0.87%(-0.11%p), 충당금 320.81%
#                    고객 1,500만 돌파, 중저신용 잔액 34.75%(제1금융권 최고)

KAKAO_2026Q1 = BankProfile(
    name="카카오뱅크 (2026Q1)", short="kakao_q1_26",
    total_loans_krw=48.5e12,                 # ~46.9→48.5조 (분기 성장 추정)
    total_deposits_krw=70.0e12,
    bis_capital_ratio=0.18,                  # CET1 14%+ → BIS 18% 추정
    npl_ratio=0.0058,                        # 사업자대출 확대로 소폭 상승
    delinquency_ratio=0.0053,
    coverage_ratio=2.15,
    quarterly_net_income_krw=1873e8,
    mid_low_credit_share=0.45,               # 1Q26 추정
    mix_corporate=0.10,                      # 사업자대출 확대 반영
    mix_retail_unsecured=0.30,
    mix_mortgage=0.60,
    capital_total_krw=7.5e12,
    notes="1Q26 분기 순익 최대, 주담대 중심 조정 + 사업자대출 확대",
)

KBANK_2026Q1 = BankProfile(
    name="케이뱅크 (2026Q1)", short="kbank_q1_26",
    total_loans_krw=20.5e12,                 # 18.4→20.5조 (분기 성장)
    total_deposits_krw=30.0e12,
    bis_capital_ratio=0.2147,                # **공시: 21.47% (IPO 자본 효과)**
    npl_ratio=0.0058,                        # 기업대출 확대로 소폭 상승
    delinquency_ratio=0.0060,
    coverage_ratio=2.50,
    quarterly_net_income_krw=332e8,
    mid_low_credit_share=0.335,              # 신규 33.5%
    mix_corporate=0.13,                      # 기업대출 호조
    mix_retail_unsecured=0.27,
    mix_mortgage=0.60,
    capital_total_krw=4.4e12,                # BIS 21.47% × RWA → 약 2배 자본 확충
    notes="IPO 자본 확충으로 BIS 21.47% — 인뱅 중 최고",
)

TOSS_2026Q1 = BankProfile(
    name="토스뱅크 (2026Q1)", short="toss_q1_26",
    total_loans_krw=15.50e12,                # 공시: 15조 5,047억
    total_deposits_krw=31.5e12,
    bis_capital_ratio=0.1662,                # **공시: 16.62%**
    npl_ratio=0.0087,                        # 공시: 0.87%
    delinquency_ratio=0.0107,                # 공시: 1.07%
    coverage_ratio=3.2081,                   # 공시: 320.81%
    quarterly_net_income_krw=296e8,
    mid_low_credit_share=0.3475,             # 잔액 비중 34.75% (제1금융권 최고)
    mix_corporate=0.17,                      # 개인사업자 확대
    mix_retail_unsecured=0.55,
    mix_mortgage=0.28,
    capital_total_krw=2.6e12,
    notes="고객 1,500만 돌파, 자산건전성 개선 (NPL/연체율 모두 하락)",
)


BANKS_2026Q1 = [KAKAO_2026Q1, KBANK_2026Q1, TOSS_2026Q1]


# ============================================================================
# 4대 시중은행 — 2026년 1분기 공시 (Big 4 commercial banks, KR)
# ============================================================================
# 출처:
# - KB국민은행 1Q26: CET1 13.63%, BIS 15.75%, NPL 0.73% (커버리지 127.1%),
#                    총자산 829.7조, 1Q26 순익 1조1,010억(+7.3%)
# - 신한은행   1Q26: BIS 17.10%, 고정이하여신 0.30% (개별은행 — 그룹 CET1 13.19%),
#                    ROA 0.70%, 1Q26 총자산 추정 ~600조
# - 하나은행   1Q26: CET1 13.09%, BIS 15.21%, NIM 1.82%, ROE 10.91% (그룹),
#                    하나금융 1Q26 순익 1조2,100억(+7.3%)
# - 우리은행   1Q26: CET1 13.6% (그룹, 2025말 12.9%→+0.7%p), NPL 0.68%,
#                    연체율 0.37%, 우리금융 1Q26 순익 6,156억(-2.1%)
#
# 시중은행 공통 특성: 인뱅 대비 자산 30~50배, 자산건전성 NPL 0.3~0.7%,
# 가계·기업 균형(인뱅은 가계 90%+), 모기지·사업자대출·기업여신 분산.

# 시중은행 portfolio 비중 가정 — 한국 시중은행 평균 (FSS 통계 + 각사 IR)
_KB_MIX  = dict(corp=0.42, retail=0.18, mortgage=0.40)   # 균형형
_SH_MIX  = dict(corp=0.45, retail=0.15, mortgage=0.40)   # 기업 강세
_HN_MIX  = dict(corp=0.48, retail=0.13, mortgage=0.39)   # 기업 최강
_WR_MIX  = dict(corp=0.43, retail=0.20, mortgage=0.37)   # 가계 비중 약간 높음

KB_2026Q1 = BankProfile(
    name="KB국민은행 (2026Q1)", short="kb_q1_26",
    total_loans_krw=480e12,                     # 총자산 830조 × 여신비중 58%
    total_deposits_krw=520e12,
    bis_capital_ratio=0.1575,                   # 공시: BIS 15.75%
    npl_ratio=0.0073,                           # 공시: 0.73%
    delinquency_ratio=0.0050,                   # 시중은행 평균 추정
    coverage_ratio=1.271,                       # 공시: 127.1%
    quarterly_net_income_krw=11010e8,
    mid_low_credit_share=0.10,                  # 시중은행 인뱅 대비 낮음
    mix_corporate=_KB_MIX["corp"],
    mix_retail_unsecured=_KB_MIX["retail"],
    mix_mortgage=_KB_MIX["mortgage"],
    capital_total_krw=480e12 * 0.6 * 0.1575,    # 추정
    notes="총자산 1위, NPL 커버리지 127.1%로 보수적 적립",
)

SHINHAN_2026Q1 = BankProfile(
    name="신한은행 (2026Q1)", short="shinhan_q1_26",
    total_loans_krw=360e12,                     # 추정
    total_deposits_krw=400e12,
    bis_capital_ratio=0.1710,                   # 공시: BIS 17.10% (4사 중 최고)
    npl_ratio=0.0030,                           # 공시: 0.30% (4사 중 최저)
    delinquency_ratio=0.0035,
    coverage_ratio=1.80,                        # 추정
    quarterly_net_income_krw=12000e8,           # 신한금융 1Q26 추정
    mid_low_credit_share=0.08,
    mix_corporate=_SH_MIX["corp"],
    mix_retail_unsecured=_SH_MIX["retail"],
    mix_mortgage=_SH_MIX["mortgage"],
    capital_total_krw=360e12 * 0.6 * 0.171,
    notes="자산건전성 1위 (NPL 0.30%), 기업여신 강세",
)

HANA_2026Q1 = BankProfile(
    name="하나은행 (2026Q1)", short="hana_q1_26",
    total_loans_krw=330e12,                     # 추정
    total_deposits_krw=370e12,
    bis_capital_ratio=0.1521,                   # 공시: BIS 15.21% (4사 중 최저)
    npl_ratio=0.0050,                           # 추정
    delinquency_ratio=0.0048,                   # 기업 연체율 0.35~0.61% 평균
    coverage_ratio=1.55,
    quarterly_net_income_krw=12100e8,           # 하나금융 1Q26
    mid_low_credit_share=0.07,
    mix_corporate=_HN_MIX["corp"],
    mix_retail_unsecured=_HN_MIX["retail"],
    mix_mortgage=_HN_MIX["mortgage"],
    capital_total_krw=330e12 * 0.6 * 0.1521,
    notes="기업여신 비중 최고 48%, ROE 10.91%",
)

WOORI_2026Q1 = BankProfile(
    name="우리은행 (2026Q1)", short="woori_q1_26",
    total_loans_krw=300e12,                     # 추정
    total_deposits_krw=340e12,
    bis_capital_ratio=0.1550,                   # 추정 (그룹 CET1 13.6% + AT1/T2)
    npl_ratio=0.0068,                           # 공시: 0.68%
    delinquency_ratio=0.0037,                   # 공시: 0.37%
    coverage_ratio=1.40,
    quarterly_net_income_krw=6156e8,            # 우리금융 1Q26
    mid_low_credit_share=0.10,
    mix_corporate=_WR_MIX["corp"],
    mix_retail_unsecured=_WR_MIX["retail"],
    mix_mortgage=_WR_MIX["mortgage"],
    capital_total_krw=300e12 * 0.6 * 0.155,
    notes="토지 재평가로 CET1 +0.6%p, 13% 조기 달성",
)


BIG4_2026Q1 = [KB_2026Q1, SHINHAN_2026Q1, HANA_2026Q1, WOORI_2026Q1]
BANK7_2026Q1 = BIG4_2026Q1 + BANKS_2026Q1   # 시중 4 + 인뱅 3


# ============================================================================
# Portfolio synthesis
# ============================================================================

def synthesise_bank_portfolio(
    profile: BankProfile, *, seed: int = 42, scale: float = 1.0,
) -> pd.DataFrame:
    """공시 비중에 맞춰 차주·익스포저 portfolio을 합성한다.

    scale=1.0이면 1만건 규모로 합성. 실제 잔액과 일치하도록 EAD 정규화.
    NPL/연체율은 default_12m/dpd 분포로 재현.
    """
    # 파이썬 `hash()`는 문자열에 프로세스별 salt가 걸려 실행마다 값이 다르다
    # (PYTHONHASHSEED). seed를 그것으로 유도하면 같은 seed·같은 프로필이 실행마다
    # 다른 포트폴리오를 낸다 — 재현성 규칙이 여기서 샜다. 저장소의 다른 곳
    # (`forms_fss_asset_data.py`)이 이미 쓰는 sha256으로 바꾼다.
    _salt = int(hashlib.sha256(profile.short.encode("utf-8")).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed + _salt % 1000)
    n_total = int(10_000 * scale)
    n_corp = max(50, int(n_total * profile.mix_corporate * 0.50))     # 기업 차주 수 (최소 50)
    n_retail = int(n_total * profile.mix_retail_unsecured * 0.60)     # 신용대출
    n_mortgage = int(n_total * profile.mix_mortgage * 0.20)
    parts = []
    target_loan = profile.total_loans_krw

    def _sigmoid(x): return 1 / (1 + np.exp(-x))

    # ---- 기업대출 (개인사업자 + 일반기업)
    if n_corp:
        # 인뱅 기업대출은 소액·다건 — 평균 EAD 작게
        leverage = rng.normal(2.5, 1.0, n_corp).clip(0.3, 7)
        current = rng.normal(1.3, 0.4, n_corp).clip(0.3, 3)
        log_assets = rng.normal(10.0, 1.2, n_corp)
        icr = rng.normal(2.5, 1.5, n_corp).clip(-2, 12)
        gdp = rng.normal(0.020, 0.008, n_corp)
        # 인뱅 기업 PD는 중저신용자 비중에 따라 상승.
        # intercept는 default 표본이 항상 발생하도록 보수적(높은 부도율)으로 설정
        base_intercept = -1.6 + profile.mid_low_credit_share * 0.5
        latent = (base_intercept + 0.55 * leverage - 0.7 * current
                  - 0.18 * log_assets - 0.14 * icr - 9 * gdp
                  + rng.normal(0, 0.6, n_corp))
        pd_true = _sigmoid(latent).clip(0.0008, 0.95)
        default = (rng.random(n_corp) < pd_true * 1.0).astype(int)
        lgd_real = np.clip(rng.beta(2.5, 2.5, n_corp) + 0.05, 0.10, 0.95)
        ead = rng.lognormal(np.log(0.4), 1.0, n_corp) * 1e9
        df = pd.DataFrame({
            "exposure_id": [f"{profile.short}_CORP_{i:05d}" for i in range(n_corp)],
            "obligor_id":  [f"{profile.short}_OBL_CORP_{i:05d}" for i in range(n_corp)],
            "asset_class": "corporate", "sector": rng.choice(
                ["retail_trade", "tech", "construction", "manufacturing",
                 "real_estate", "shipping", "energy"], n_corp),
            "country": "KR",
            "ead": ead, "maturity": rng.uniform(1.0, 3.5, n_corp),
            "leverage": leverage, "current_ratio": current,
            "log_assets": log_assets, "interest_coverage": icr,
            "gdp_growth": gdp,
            "pd": pd_true, "lgd": lgd_real * 0.9 + 0.05, "ltv": np.nan,
            "default_12m": default, "lgd_realized": lgd_real,
        })
        parts.append(df)

    # ---- 가계 신용대출
    if n_retail:
        dti = rng.normal(0.40, 0.15, n_retail).clip(0.05, 1.4)
        utilization = rng.beta(2.2, 4, n_retail)
        income_log = rng.normal(10.4, 0.5, n_retail)
        months_employed = rng.normal(55, 30, n_retail).clip(0, 360)
        # 중저신용자 비중에 따른 PD shift
        ml_shift = profile.mid_low_credit_share * 0.7
        latent = (-2.2 + ml_shift + 2.8 * dti + 2.7 * utilization
                  - 0.42 * (income_log - 10) - 0.005 * months_employed
                  + rng.normal(0, 0.55, n_retail))
        pd_true = _sigmoid(latent).clip(0.0015, 0.65)
        default = (rng.random(n_retail) < pd_true).astype(int)
        lgd_real = np.clip(rng.beta(3.5, 2, n_retail), 0.25, 0.95)
        ead = rng.lognormal(np.log(25), 0.55, n_retail) * 1e6
        df = pd.DataFrame({
            "exposure_id": [f"{profile.short}_RTL_{i:05d}" for i in range(n_retail)],
            "obligor_id":  [f"{profile.short}_OBL_RTL_{i:05d}" for i in range(n_retail)],
            "asset_class": "retail_other", "sector": "household", "country": "KR",
            "ead": ead, "maturity": 1.0,
            "leverage": np.nan, "current_ratio": np.nan, "log_assets": np.nan,
            "interest_coverage": np.nan, "gdp_growth": np.nan,
            "dti": dti, "utilization": utilization, "income_log": income_log,
            "months_employed": months_employed,
            "pd": pd_true, "lgd": lgd_real * 0.9 + 0.05, "ltv": np.nan,
            "default_12m": default, "lgd_realized": lgd_real,
        })
        parts.append(df)

    # ---- 주담대
    if n_mortgage:
        ltv = rng.normal(0.62, 0.13, n_mortgage).clip(0.20, 1.0)
        dti = rng.normal(0.32, 0.10, n_mortgage).clip(0.05, 0.85)
        credit_score = rng.normal(710, 65, n_mortgage).clip(400, 850)
        income_log = rng.normal(10.7, 0.5, n_mortgage)
        latent = (-3.8 + 2.4 * ltv + 1.8 * dti
                  - 0.013 * (credit_score - 700) - 0.4 * (income_log - 10.7)
                  + rng.normal(0, 0.45, n_mortgage))
        pd_true = _sigmoid(latent).clip(0.0005, 0.30)
        default = (rng.random(n_mortgage) < pd_true).astype(int)
        ead = rng.lognormal(np.log(220), 0.5, n_mortgage) * 1e6
        lgd_real = np.clip(rng.beta(2, 7, n_mortgage), 0.05, 0.55)
        df = pd.DataFrame({
            "exposure_id": [f"{profile.short}_MTG_{i:05d}" for i in range(n_mortgage)],
            "obligor_id":  [f"{profile.short}_OBL_MTG_{i:05d}" for i in range(n_mortgage)],
            "asset_class": "residential_mortgage", "sector": "household",
            "country": "KR",
            "ead": ead, "maturity": 20.0,
            "leverage": np.nan, "current_ratio": np.nan, "log_assets": np.nan,
            "interest_coverage": np.nan, "gdp_growth": np.nan,
            "ltv": ltv, "dti": dti, "credit_score": credit_score,
            "income_log": income_log,
            "pd": pd_true, "lgd": lgd_real * 0.9 + 0.05,
            "default_12m": default, "lgd_realized": lgd_real,
        })
        parts.append(df)

    full = pd.concat(parts, ignore_index=True, sort=False)

    # 잔액을 공시 총여신과 맞추기 위한 EAD 스케일링
    cur_total = float(full["ead"].sum())
    full["ead"] = full["ead"] * (target_loan / cur_total)
    full["balance"] = full["ead"]

    # 연체/부도 — 실측 비중에 맞추기
    rng2 = np.random.default_rng(seed + 1)
    n = len(full)
    full["past_due"] = False
    full.loc[(full["default_12m"] == 1) & (rng2.random(n) < 0.7), "past_due"] = True
    full["dpd"] = 0
    dlq_mask = rng2.random(n) < profile.delinquency_ratio * 2  # half→past_due
    full.loc[dlq_mask, "dpd"] = rng2.integers(1, 89, dlq_mask.sum())
    full.loc[full["past_due"], "dpd"] = rng2.integers(90, 360, full["past_due"].sum())

    # P&L (인뱅 spread 가정)
    spread = np.where(full["asset_class"] == "corporate", 0.030,
              np.where(full["asset_class"] == "retail_other",
                       0.058 + profile.mid_low_credit_share * 0.03,
              np.where(full["asset_class"] == "residential_mortgage", 0.020, 0.012)))
    full["revenue"] = full["ead"] * spread
    full["operating_cost"] = full["ead"] * 0.004

    full["rating"] = "UNRATED"
    return full


# ============================================================================
# Bank stress test orchestration
# ============================================================================

@dataclass
class BankAnalysis:
    """은행 단위 분석 결과."""
    profile: BankProfile
    portfolio: pd.DataFrame
    result: Any                       # PipelineResult
    manifest: Any = None


# 시장·운영 산출의 구성비. 이 모듈이 다루는 은행들에 대해 근거 상태는
# '미확인'이다. 트레이딩 계정 구성과 영업지표(BI) 구성은 분기 공시에서 얻지
# 못했다. 그래도 이 자리에 적어 두는 이유는, 적지 않으면 파이프라인이 기관
# 프로파일 원장의 국내 표본 행(KR_BANK_01)을 대신 읽어 이 은행들의 시장·운영
# RWA 가 되기 때문이다. 다른 기관의 행을 빌려 쓰는 것보다 이쪽의 근거 없음을
# 드러내 두는 편이 낫다. 규모감만은 각 은행의 공시 총여신에서 온다.
_CASE_MARKET_OP_SHARES: dict[str, float] = {
    "share_fx": 0.02, "share_equity": 0.01, "share_ir": 0.05,
    "share_bi_ildc": 0.02, "share_bi_sc": 0.01, "share_bi_fc": 0.005,
    "op_loss_rate": 0.001,
}


def market_op_for(profile: BankProfile, *, scale: float = 1.0
                  ) -> dict[str, float]:
    """은행 하나의 시장·운영 산출 모수.

    기준 명목은 그 은행의 **공시 총여신**이다. 이전에는 이 인자를 넘기지
    않아 파이프라인이 국내 표본 기관의 프로파일 행(명목 10조)을 읽었고, 총여신
    46.9조·18.4조·15.35조인 세 은행이 전부 같은 시장 RWA·운영 RWA 를 받았다.
    규모가 세 배 넘게 벌어지는데 값이 같다는 것은 그 값이 이 은행들과 무관하다는
    뜻이다. 구성비는 여전히 근거가 없고 `_CASE_MARKET_OP_SHARES` 가 그 사실을
    적는다.
    """
    return {"mkt_notional_base": float(profile.total_loans_krw) * float(scale),
            **_CASE_MARKET_OP_SHARES}


def run_bank_stress(profile: BankProfile, *, seed: int = 42,
                    scale: float = 1.0) -> BankAnalysis:
    """은행 portfolio 합성 → run_pipeline → 결과 반환."""
    from risk_lib.pipeline import run_pipeline
    from risk_lib.capital.bis import CapitalStack

    portfolio = synthesise_bank_portfolio(profile, seed=seed, scale=scale)
    # 자본 구성 — 실측 BIS와 매칭하도록 buffers 조정
    result = run_pipeline(portfolio, seed=seed,
                          buffers={"capital_conservation": 0.025,
                                   "countercyclical": 0.0,
                                   "dsib": 0.0},  # 인뱅은 D-SIB 미해당
                          market_op=market_op_for(profile, scale=scale))
    return BankAnalysis(profile=profile, portfolio=portfolio, result=result)


def run_all_banks(*, seed: int = 42, scale: float = 1.0,
                  banks: list[BankProfile] | None = None) -> list[BankAnalysis]:
    """3사 모두 분석. ``banks`` 미지정 시 2025 Q3 default."""
    if banks is None:
        banks = BANKS
    return [run_bank_stress(p, seed=seed, scale=scale) for p in banks]


# ============================================================================
# Cross-bank comparison
# ============================================================================

def compare_banks(analyses: list[BankAnalysis]) -> pd.DataFrame:
    """3사 핵심 지표 비교 표."""
    rows = []
    for a in analyses:
        r = a.result; p = a.profile
        rows.append({
            "은행": p.name,
            "총여신 (조원)": p.total_loans_krw / 1e12,
            "공시 BIS": p.bis_capital_ratio,
            "산출 CET1": r.bis.cet1_ratio,
            "산출 RWA (조원)": r.rwa["final_total"] / 1e12,
            "Leverage": r.leverage.leverage_ratio,
            "LCR": r.alm["lcr"].lcr,
            "NSFR": r.alm["nsfr"].nsfr,
            "공시 NPL": p.npl_ratio,
            "산출 ECL/EAD": r.ecl["total"] / p.total_loans_krw,
            "RAF 최악": r.raf.worst() if r.raf else "",
            "ICAAP 사용률": r.icaap.utilisation,
            "ICAAP 등급": r.icaap.grade,
            "역스트레스 임계 s": r.reverse_stress.critical_severity,
            "Severe CET1": r.stress[
                r.stress["scenario"] == "severely_adverse"]["cet1_ratio"].iloc[0],
            "Severe 통과": bool(r.stress[
                r.stress["scenario"] == "severely_adverse"]["passes"].iloc[0]),
            "기후 worst transition uplift (십억)":
                max(l.uplift for l in r.climate.transition) / 1e9,
            "운영손실 99.9% VaR (십억)": r.op_loss.var_99_9 / 1e9,
        })
    return pd.DataFrame(rows)


def stress_comparison(analyses: list[BankAnalysis]) -> pd.DataFrame:
    """3사 시나리오별 CET1 / ECL / RWA 비교."""
    rows = []
    for a in analyses:
        for _, s in a.result.stress.iterrows():
            rows.append({
                "은행": a.profile.name,
                "시나리오": s["scenario"],
                "RWA (조원)": s["rwa_total"] / 1e12,
                "ECL (십억)": s["ecl"] / 1e9,
                "CET1 비율": s["cet1_ratio"],
                "CET1 잉여 (%p)": s["cet1_surplus"] * 100,
                "통과": "PASS" if s["passes"] else "FAIL",
            })
    return pd.DataFrame(rows)


def reverse_stress_comparison(analyses: list[BankAnalysis]) -> pd.DataFrame:
    rows = []
    for a in analyses:
        rev = a.result.reverse_stress
        rows.append({
            "은행": a.profile.name,
            "기준 CET1": rev.base_ratio,
            "임계 CET1": rev.target_ratio,
            "임계 심도 s": rev.critical_severity,
            "함의 GDP 충격": rev.implied_gdp_shock,
            "함의 LGD 가산 (%p)": rev.implied_lgd_addon * 100,
            "임계점 RWA (조원)": rev.rwa_total_at_break / 1e12,
            "임계점 ECL (십억)": rev.ecl_at_break / 1e9,
        })
    return pd.DataFrame(rows)
