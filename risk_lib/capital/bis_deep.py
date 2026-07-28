"""CRO-grade BIS capital deep-dive (Basel III CRE40, RBC10, RBC20, RBC40, SRP20).

Adds beyond the headline BIS pipeline:

  * CET1 / AT1 / Tier2 item-level decomposition (감독세칙 자본적정성, CRE40).
    - CET1: 보통주자본금, 자본잉여금, 이익잉여금, AOCI, 자기주식차감,
      영업권차감, 무형자산차감, DTA 한도초과차감.
    - AT1:  영구신종자본증권, 비누적적 우선주.
    - Tier2: 후순위채(잔존만기 ≥ 5y), 일반대손충당금(IRB 한도 1.25%).
  * Recognition limits (15% threshold for DTA/MSR/Significant investments per CRE40.10)
    and AT1/T2 인정한도 cap test.
  * Buffer layering (P1 → CBR → P2R → P2G → OCR) per RBC20/RBC40/SRP20.
    Country-level CCyB weighted by jurisdictional exposure (KR/US/JP/CN/VN).
    DSIB bucket 1~5 (1.0% / 1.5% / 2.0% / 2.5% / 3.5%).
  * SREP / Pillar 2 — P2R supervisory add-on, P2G stress-test guidance.
  * MDA component breakdown — AT1 쿠폰 / 자기주식매입 / 변동성과보수
    각 항목별 잔여 분배 한도, 4분위 적용.
  * CET1 분기별 시뮬레이션 — 미래 4분기 자본 경로(배당·자사주·신주).

Pure, deterministic. Returns dataclasses / DataFrames suitable for HTML tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from risk_lib.references import (
    BIS_MIN_CET1, BIS_MIN_TIER1, BIS_MIN_TOTAL,
    CAPITAL_CONSERVATION_BUFFER,
)


# ============================================================================
# 1. Capital stack item-level decomposition (CRE40 / 감독세칙 §2-1)
# ============================================================================


@dataclass
class CET1Components:
    """CET1 보통주자본 항목별 분해 (CRE40.1~CRE40.45 / 감독세칙 §2-1-1).

    Positive items are additions; deduction fields are POSITIVE numbers that
    will be subtracted from gross CET1.  All amounts in KRW (or unit-aligned).
    """
    common_shares: float = 0.0          # 보통주자본금
    share_premium: float = 0.0          # 자본잉여금 (주식발행초과금)
    retained_earnings: float = 0.0      # 이익잉여금
    aoci: float = 0.0                   # 기타포괄손익누계 (signed)
    minority_interest: float = 0.0      # 비지배지분 (인정분)

    treasury_shares: float = 0.0        # 자기주식차감 (CRE40.20)
    goodwill: float = 0.0               # 영업권차감 (CRE40.5)
    intangibles: float = 0.0            # 무형자산차감 (CRE40.6)
    dta_excess: float = 0.0             # DTA 한도초과차감 (CRE40.10)
    cashflow_hedge_reserve: float = 0.0 # 현금흐름위험회피 적립금 차감
    expected_loss_shortfall: float = 0.0  # IRB EL > 충당금 차감 (CRE40.11)
    own_credit_gains: float = 0.0       # 자기신용위험 평가이익 차감
    other_deductions: float = 0.0       # 기타 규제 차감

    @property
    def gross(self) -> float:
        """차감 전 CET1 합산."""
        return (self.common_shares + self.share_premium
                + self.retained_earnings + self.aoci
                + self.minority_interest)

    @property
    def total_deductions(self) -> float:
        return (self.treasury_shares + self.goodwill + self.intangibles
                + self.dta_excess + self.cashflow_hedge_reserve
                + self.expected_loss_shortfall + self.own_credit_gains
                + self.other_deductions)

    @property
    def net(self) -> float:
        """차감 후 CET1 (감독목적 보통주자본)."""
        return self.gross - self.total_deductions


@dataclass
class AT1Components:
    """AT1 기타기본자본 항목별 분해 (CRE40.27 / 감독세칙 §2-1-2)."""
    perpetual_notes: float = 0.0        # 영구신종자본증권
    non_cumulative_preferred: float = 0.0  # 비누적적 우선주
    at1_minority_interest: float = 0.0  # AT1 비지배지분
    at1_deductions: float = 0.0         # 자기 AT1 보유 등 차감

    @property
    def net(self) -> float:
        return (self.perpetual_notes + self.non_cumulative_preferred
                + self.at1_minority_interest - self.at1_deductions)


@dataclass
class Tier2Components:
    """Tier2 보완자본 항목별 분해 (CRE40.42 / 감독세칙 §2-1-3)."""
    subordinated_debt: float = 0.0      # 후순위채 (잔존만기 ≥ 5y) — 전액 인정
    subordinated_debt_amortising: float = 0.0  # 잔존만기 < 5y — 20%/y 상각
    subordinated_remaining_years: float = 5.0  # 가장 보수적 잔존만기
    general_provisions: float = 0.0     # 일반대손충당금
    irb_rwa_for_gp_cap: float = 0.0     # IRB RWA — 1.25% 한도 적용 기준
    t2_minority_interest: float = 0.0
    t2_deductions: float = 0.0

    @property
    def amortised_subdebt(self) -> float:
        """잔존만기 5년 미만 후순위채는 매년 20%씩 인정금액 차감 (CRE40.42)."""
        m = max(0.0, min(5.0, self.subordinated_remaining_years))
        return self.subordinated_debt_amortising * (m / 5.0)

    @property
    def recognised_general_provisions(self) -> float:
        """IRB RWA의 1.25% 한도 내에서만 인정 (CRE40.45 / 감독세칙)."""
        cap = max(0.0, self.irb_rwa_for_gp_cap) * 0.0125
        return min(self.general_provisions, cap)

    @property
    def gp_cap(self) -> float:
        return max(0.0, self.irb_rwa_for_gp_cap) * 0.0125

    @property
    def net(self) -> float:
        return (self.subordinated_debt + self.amortised_subdebt
                + self.recognised_general_provisions
                + self.t2_minority_interest - self.t2_deductions)


def cet1_decomposition_table(c: CET1Components) -> pd.DataFrame:
    """CET1 항목별 표 — 양의 적립 + 차감(괄호 처리)."""
    rows = [
        ("보통주자본금",       c.common_shares,        "+", "CRE40.1"),
        ("자본잉여금",         c.share_premium,        "+", "CRE40.1"),
        ("이익잉여금",         c.retained_earnings,    "+", "CRE40.2"),
        ("기타포괄손익누계",   c.aoci,                 "+", "CRE40.3"),
        ("비지배지분 인정분",  c.minority_interest,    "+", "CRE40.4"),
        ("자기주식 차감",      -c.treasury_shares,     "-", "CRE40.20"),
        ("영업권 차감",        -c.goodwill,            "-", "CRE40.5"),
        ("무형자산 차감",      -c.intangibles,         "-", "CRE40.6"),
        ("DTA 한도초과 차감",  -c.dta_excess,          "-", "CRE40.10"),
        ("현금흐름위험회피 차감", -c.cashflow_hedge_reserve, "-", "CRE40.8"),
        ("EL > 충당금 부족분 차감", -c.expected_loss_shortfall, "-", "CRE40.11"),
        ("자기신용 평가이익 차감", -c.own_credit_gains, "-", "CRE40.7"),
        ("기타 규제 차감",     -c.other_deductions,    "-", "CRE40"),
    ]
    df = pd.DataFrame(rows, columns=["item", "amount", "sign", "ref"])
    df["cumulative"] = df["amount"].cumsum()
    return df


def at1_decomposition_table(a: AT1Components) -> pd.DataFrame:
    rows = [
        ("영구신종자본증권",      a.perpetual_notes,            "+", "CRE40.27"),
        ("비누적적 우선주",       a.non_cumulative_preferred,   "+", "CRE40.27"),
        ("AT1 비지배지분 인정분", a.at1_minority_interest,      "+", "CRE40.30"),
        ("자기 AT1 보유 차감",    -a.at1_deductions,            "-", "CRE40.34"),
    ]
    df = pd.DataFrame(rows, columns=["item", "amount", "sign", "ref"])
    df["cumulative"] = df["amount"].cumsum()
    return df


def tier2_decomposition_table(t: Tier2Components) -> pd.DataFrame:
    rows = [
        ("후순위채(잔존 ≥5y)",     t.subordinated_debt,             "+", "CRE40.42"),
        (f"후순위채 상각분 (잔존 {t.subordinated_remaining_years:.1f}y)",
         t.amortised_subdebt,                                       "+", "CRE40.42"),
        (f"일반대손충당금 (한도 {t.gp_cap:,.0f})",
         t.recognised_general_provisions,                            "+", "CRE40.45"),
        ("T2 비지배지분 인정분",   t.t2_minority_interest,           "+", "CRE40.42"),
        ("자기 T2 보유 차감",      -t.t2_deductions,                 "-", "CRE40.46"),
    ]
    df = pd.DataFrame(rows, columns=["item", "amount", "sign", "ref"])
    df["cumulative"] = df["amount"].cumsum()
    return df


# ============================================================================
# 2. Recognition limits — 15% threshold (CRE40.10) + AT1/T2 인정한도
# ============================================================================


@dataclass
class ThresholdResult:
    item: str           # "DTA" / "MSR" / "Significant Investments"
    amount: float       # 인식 전 잔액
    threshold: float    # 인정 한도 (CET1 × 0.10 또는 합산 0.15)
    recognised: float   # 한도 이하 인정 (CET1 위험가중 250% 처리)
    deducted: float     # 한도 초과 차감 (CET1에서 직접 차감)


def cet1_threshold_test(
    cet1_pre_threshold: float,
    *,
    dta_temporary_diff: float = 0.0,    # 일시적 차이 DTA
    msr: float = 0.0,                   # 모기지 서비싱권
    significant_investments: float = 0.0,  # 금융기관 중요 투자
    individual_limit_pct: float = 0.10,  # 각 항목 한도 10%
    combined_limit_pct: float = 0.15,    # 3항목 합산 한도 15%
) -> dict[str, Any]:
    """CRE40.10 — DTA/MSR/금융기관 중요투자 각 10% + 합산 15% threshold test.

    한도 이하: CET1에서 차감 안 함 (RW 250%).
    한도 초과: CET1에서 직접 차감.

    Returns dict with 'individual' (3개 ThresholdResult), 'combined', 'total_deducted'.
    """
    ind_limit = max(0.0, cet1_pre_threshold * individual_limit_pct)
    items = [
        ("일시적 차이 DTA", dta_temporary_diff),
        ("MSR (Mortgage Servicing Rights)", msr),
        ("금융기관 중요 투자", significant_investments),
    ]
    individual: list[ThresholdResult] = []
    total_recognised = 0.0
    total_deducted_ind = 0.0
    for name, amount in items:
        rec = min(amount, ind_limit)
        ded = max(0.0, amount - ind_limit)
        individual.append(ThresholdResult(
            item=name, amount=amount, threshold=ind_limit,
            recognised=rec, deducted=ded,
        ))
        total_recognised += rec
        total_deducted_ind += ded
    # Combined 15% threshold applies to the recognised aggregate.
    combined_limit = max(0.0, cet1_pre_threshold * combined_limit_pct)
    combined_excess = max(0.0, total_recognised - combined_limit)
    total_deducted = total_deducted_ind + combined_excess

    return {
        "individual": individual,
        "individual_limit": ind_limit,
        "combined_limit": combined_limit,
        "recognised_aggregate": total_recognised,
        "combined_excess_deducted": combined_excess,
        "total_deducted": total_deducted,
    }


def at1_t2_recognition_limits(
    cet1: float, at1: float, tier2: float,
) -> dict[str, float]:
    """AT1·T2 인정한도 테스트 (감독세칙 §2-1-2/3).

    AT1 인정한도: Tier1 비율이 6% (RWA 대비)에 도달하기까지 인정.
    Tier2 인정한도: Total 비율이 8% (RWA 대비)에 도달하기까지 인정.
    여기서는 CET1 대비 cap 형태 ('상대적 인정한도') 만 노출.
    """
    # Common practice (CRE40): AT1 ≤ 1.5%·RWA portion of Tier1, Tier2 ≤ 2%·RWA.
    # Here we expose simple proportional caps relative to CET1 anchor.
    at1_cap_ratio = 1.5 / 4.5   # AT1 인정 = CET1의 1/3 까지 = Tier1 6% 도달
    t2_cap_ratio = 2.0 / 6.0    # T2 인정 = Tier1의 1/3 까지 = Total 8% 도달
    at1_cap = cet1 * at1_cap_ratio
    tier1_for_t2 = cet1 + min(at1, at1_cap)
    t2_cap = tier1_for_t2 * t2_cap_ratio

    return {
        "at1_cap": at1_cap,
        "at1_recognised": min(at1, at1_cap),
        "at1_excess": max(0.0, at1 - at1_cap),
        "t2_cap": t2_cap,
        "t2_recognised": min(tier2, t2_cap),
        "t2_excess": max(0.0, tier2 - t2_cap),
    }


# ============================================================================
# 3. Buffer layering — P1 / CBR / P2R / P2G → OCR (RBC20, RBC40, SRP20)
# ============================================================================


# DSIB bucket → buffer rate (KR 금감원 시스템적중요은행 가산자본률).
# 1등급 1.0%, 2등급 1.5%, 3등급 2.0%, 4등급 2.5%, 5등급 3.5%.
DSIB_BUCKETS = {
    1: 0.010,
    2: 0.015,
    3: 0.020,
    4: 0.025,
    5: 0.035,
}


# 국가별 CCyB율 — 예시 (실제 운영 시 BIS CCyB 등록부 최신값 사용).
COUNTRY_CCYB_DEFAULT = {
    "KR": 0.010,    # 한국: 2024년 1% 발동
    "US": 0.000,
    "JP": 0.000,
    "CN": 0.0125,   # 중국: 1.25% 가정
    "VN": 0.000,
}


def dsib_buffer_for_bucket(bucket: int) -> float:
    """DSIB 등급(1~5)에 따른 가산자본률 (감독세칙 RBC40)."""
    if bucket not in DSIB_BUCKETS:
        raise ValueError(f"DSIB 등급은 1~5만 허용 (입력={bucket})")
    return DSIB_BUCKETS[bucket]


def country_ccyb_weighted(
    exposures_by_country: dict[str, float],
    *, ccyb_rates: dict[str, float] | None = None,
) -> dict[str, Any]:
    """국가별 익스포저 가중 CCyB 산출 (RBC20 jurisdictional reciprocity).

    가중 CCyB = Σ (익스포저 share_i × CCyB_i).
    """
    rates = dict(COUNTRY_CCYB_DEFAULT)
    if ccyb_rates:
        rates.update(ccyb_rates)
    total = sum(max(0.0, v) for v in exposures_by_country.values())
    if total <= 0:
        return {"weighted_ccyb": 0.0, "by_country": pd.DataFrame(
            columns=["country", "exposure", "share", "ccyb", "weighted"])}
    rows = []
    weighted = 0.0
    for c, exp in exposures_by_country.items():
        exp = max(0.0, exp)
        share = exp / total
        rate = rates.get(c, 0.0)
        contrib = share * rate
        weighted += contrib
        rows.append({"country": c, "exposure": exp, "share": share,
                     "ccyb": rate, "weighted": contrib})
    df = pd.DataFrame(rows).sort_values("exposure", ascending=False) \
                            .reset_index(drop=True)
    return {"weighted_ccyb": weighted, "by_country": df}


@dataclass
class BufferLayering:
    """규제자본 요구의 layering — Pillar 1 + CBR + P2R + P2G → OCR.

    All numbers are ratios (CET1 % of RWA).  Tier1 / Total layers are derived
    by adding fixed +1.5% / +3.5% above CET1 base (CRE10.4).
    """
    p1_cet1: float = BIS_MIN_CET1
    capital_conservation: float = CAPITAL_CONSERVATION_BUFFER
    countercyclical: float = 0.0
    dsib: float = 0.0
    p2r: float = 0.0
    p2g: float = 0.0

    @property
    def cbr(self) -> float:
        return self.capital_conservation + self.countercyclical + self.dsib

    @property
    def ocr_cet1(self) -> float:
        """Overall Capital Requirement (CET1)."""
        return self.p1_cet1 + self.cbr + self.p2r + self.p2g

    @property
    def srep_cet1(self) -> float:
        """SREP-bound (P1 + CBR + P2R) — binding regulatory minimum."""
        return self.p1_cet1 + self.cbr + self.p2r

    @property
    def mda_threshold_cet1(self) -> float:
        """MDA 가산 trigger — P1 + CBR (CBR 침범 시 MDA 발동)."""
        return self.p1_cet1 + self.cbr

    def to_layers(self) -> pd.DataFrame:
        """Waterfall-friendly per-layer breakdown for the layering chart."""
        layers = [
            ("Pillar 1 최저",     self.p1_cet1,           "CRE10.4"),
            ("+ 자본보전버퍼 (CCB)", self.capital_conservation, "RBC20.1"),
            ("+ 경기대응버퍼 (CCyB)", self.countercyclical, "RBC20"),
            ("+ D-SIB 가산",      self.dsib,              "RBC40"),
            ("+ P2R (감독요구)",  self.p2r,               "SRP20"),
            ("+ P2G (감독가이드)", self.p2g,              "SRP20 / Stress"),
        ]
        rows = []
        cum = 0.0
        for label, val, ref in layers:
            cum += val
            rows.append({"layer": label, "increment": val,
                         "cumulative": cum, "ref": ref})
        return pd.DataFrame(rows)


def compute_buffer_layering(
    *,
    countercyclical: float = 0.0,
    dsib_bucket: int | None = None,
    dsib_rate: float | None = None,
    p2r: float = 0.0,
    p2g: float = 0.0,
) -> BufferLayering:
    """Build a BufferLayering — DSIB bucket → rate lookup, P2R/P2G supplied."""
    if dsib_rate is not None:
        dsib = dsib_rate
    elif dsib_bucket is not None:
        dsib = dsib_buffer_for_bucket(dsib_bucket)
    else:
        dsib = 0.0
    return BufferLayering(
        capital_conservation=CAPITAL_CONSERVATION_BUFFER,
        countercyclical=max(0.0, countercyclical),
        dsib=dsib, p2r=max(0.0, p2r), p2g=max(0.0, p2g),
    )


# ============================================================================
# 4. SREP / Pillar 2 — P2R + P2G 합산 OCR (SRP20)
# ============================================================================


@dataclass
class SREPResult:
    """SREP / Pillar 2 자본 요구 요약 (SRP20).

    Buckets the CET1 ratio against the four layers; the binding gap is to
    SREP (P1+CBR+P2R) — P2G violation triggers supervisory dialogue but not
    automatic restrictions.
    """
    cet1_ratio: float
    layering: BufferLayering
    surplus_to_srep: float       # actual − (P1 + CBR + P2R)
    surplus_to_ocr: float        # actual − OCR (incl. P2G)
    p1_pass: bool
    cbr_pass: bool
    srep_pass: bool
    ocr_pass: bool

    def overall_status(self) -> str:
        if not self.p1_pass:
            return "P1 미달 — supervisory action"
        if not self.cbr_pass:
            return "CBR 침범 — MDA 발동"
        if not self.srep_pass:
            return "SREP 미달 — 감독요구 미충족"
        if not self.ocr_pass:
            return "P2G 미충족 — 감독 대화 필요"
        return "OCR 충족"


def evaluate_srep(
    cet1_ratio: float, layering: BufferLayering,
) -> SREPResult:
    """Evaluate CET1 against the four layered thresholds."""
    p1_pass = cet1_ratio >= layering.p1_cet1 - 1e-12
    cbr_pass = cet1_ratio >= layering.mda_threshold_cet1 - 1e-12
    srep_pass = cet1_ratio >= layering.srep_cet1 - 1e-12
    ocr_pass = cet1_ratio >= layering.ocr_cet1 - 1e-12
    return SREPResult(
        cet1_ratio=cet1_ratio, layering=layering,
        surplus_to_srep=cet1_ratio - layering.srep_cet1,
        surplus_to_ocr=cet1_ratio - layering.ocr_cet1,
        p1_pass=p1_pass, cbr_pass=cbr_pass,
        srep_pass=srep_pass, ocr_pass=ocr_pass,
    )


# ============================================================================
# 5. MDA component breakdown (AT1 쿠폰 / 자사주 / 변동성과보수)
# ============================================================================


@dataclass
class MDAComponentLimit:
    """MDA 침범 시 항목별 잔여 분배 한도.

    Total distributable amount (TDA) = 분기 분배가능이익 × distributable_pct.
    위에서 각 항목이 인출하는 금액의 한도.
    """
    component: str          # "배당", "자사주매입", "변동성과보수", "AT1 쿠폰"
    base_allowance: float   # 분기 신청 금액
    allowed: float          # MDA 적용 후 허용
    blocked: float          # 차단 금액

    @property
    def blocked_pct(self) -> float:
        return self.blocked / self.base_allowance if self.base_allowance > 0 else 0.0


def mda_component_breakdown(
    distributable_earnings: float,
    distributable_pct: float,
    *,
    requested_dividend: float,
    requested_buyback: float,
    requested_variable_comp: float,
    requested_at1_coupon: float,
) -> pd.DataFrame:
    """MDA 잔여 한도를 4개 항목에 우선순위(AT1 쿠폰 → 변동성과 → 배당 → 자사주) 배분.

    Basel III RBC30.7: AT1 쿠폰이 가장 먼저 제한된다 (자본보전 우선순위).
    실제 운영 시는 더 정교한 발동 logic이 필요하지만 본 모듈은 보수적
    pro-rata 후 우선순위 sweep을 제공한다.
    """
    total_allowance = max(0.0, distributable_earnings) * max(0.0, min(1.0, distributable_pct))
    items = [
        ("AT1 쿠폰",          requested_at1_coupon),
        ("변동성과보수",      requested_variable_comp),
        ("배당",              requested_dividend),
        ("자사주매입",        requested_buyback),
    ]
    remaining = total_allowance
    rows = []
    for name, req in items:
        req = max(0.0, req)
        allowed = min(req, remaining)
        blocked = req - allowed
        remaining = max(0.0, remaining - allowed)
        rows.append({
            "component": name, "requested": req,
            "allowed": allowed, "blocked": blocked,
            "blocked_pct": (blocked / req) if req > 0 else 0.0,
        })
    df = pd.DataFrame(rows)
    df["total_allowance"] = total_allowance
    df["remaining_after_sweep"] = remaining
    return df


# ============================================================================
# 6. Quarterly CET1 path simulation (forward-looking)
# ============================================================================


def cet1_quarterly_path(
    cet1_start: float,
    rwa_start: float,
    *,
    quarters: int = 4,
    quarterly_earnings: float | None = None,
    quarterly_dividend: float = 0.0,
    quarterly_buyback: float = 0.0,
    quarterly_new_issuance: float = 0.0,
    rwa_growth_per_q: float = 0.0,
    srep_cet1: float | None = None,
    ocr_cet1: float | None = None,
) -> pd.DataFrame:
    """미래 N분기 CET1 ratio 경로를 시뮬레이션.

    Each quarter:
      CET1_{t+1} = CET1_t + earnings - dividend - buyback + new_issuance
      RWA_{t+1}  = RWA_t × (1 + rwa_growth)

    Marks supervisory_action when CET1 ratio < SREP (consecutive quarters
    flagged).  Pure, deterministic.
    """
    if rwa_start <= 0:
        raise ValueError("rwa_start must be positive")
    if quarters <= 0:
        raise ValueError("quarters must be positive")
    if quarterly_earnings is None:
        # default: 10% RoE on CET1 / 4 (단순 가정)
        quarterly_earnings = cet1_start * 0.10 / 4
    rows = []
    cet1 = cet1_start
    rwa = rwa_start
    breach_streak = 0
    for q in range(quarters + 1):
        ratio = cet1 / rwa if rwa > 0 else 0.0
        in_breach = (srep_cet1 is not None) and (ratio < srep_cet1 - 1e-12)
        breach_streak = breach_streak + 1 if in_breach else 0
        if breach_streak == 0:
            action = "정상"
        elif breach_streak == 1:
            action = "감독 보고 (1분기 침범)"
        elif breach_streak == 2:
            action = "자본보전계획 제출 (2분기 연속)"
        elif breach_streak >= 3:
            action = "supervisory action — 분배제한·자본확충 명령"
        rows.append({
            "quarter": q, "cet1": cet1, "rwa": rwa,
            "cet1_ratio": ratio,
            "srep_threshold": srep_cet1 if srep_cet1 is not None else None,
            "ocr_threshold": ocr_cet1 if ocr_cet1 is not None else None,
            "breach": in_breach, "breach_streak": breach_streak,
            "supervisory_action": action,
        })
        if q == quarters:
            break
        cet1 = (cet1 + quarterly_earnings - quarterly_dividend
                - quarterly_buyback + quarterly_new_issuance)
        rwa = rwa * (1.0 + rwa_growth_per_q)
    return pd.DataFrame(rows)


# ============================================================================
# 7. Aggregated container
# ============================================================================


@dataclass
class BISDeepResult:
    """One-shot container consumed by the report pages."""
    cet1: CET1Components
    at1: AT1Components
    tier2: Tier2Components
    cet1_table: pd.DataFrame
    at1_table: pd.DataFrame
    tier2_table: pd.DataFrame
    threshold_test: dict[str, Any]
    recognition: dict[str, float]
    layering: BufferLayering
    layering_table: pd.DataFrame
    country_ccyb: dict[str, Any]
    srep: SREPResult
    mda_components: pd.DataFrame
    quarterly_path: pd.DataFrame


def compute_bis_deep(
    *,
    cet1: CET1Components,
    at1: AT1Components,
    tier2: Tier2Components,
    rwa: float,
    threshold_inputs: dict[str, float] | None = None,
    countercyclical: float = 0.0,
    dsib_bucket: int | None = None,
    p2r: float = 0.0,
    p2g: float = 0.0,
    exposures_by_country: dict[str, float] | None = None,
    ccyb_rates: dict[str, float] | None = None,
    mda_request: dict[str, float] | None = None,
    quarterly_earnings: float | None = None,
    quarterly_dividend: float = 0.0,
    quarterly_buyback: float = 0.0,
    quarterly_new_issuance: float = 0.0,
    rwa_growth_per_q: float = 0.0,
) -> BISDeepResult:
    """Run every BIS deep-dive analytic in a single call.  Deterministic."""
    if rwa <= 0:
        raise ValueError("rwa must be positive")

    # 1. Threshold test (DTA/MSR/Significant Investments)
    th_inp = dict(threshold_inputs or {})
    th_res = cet1_threshold_test(
        cet1.gross - cet1.total_deductions,
        dta_temporary_diff=th_inp.get("dta_temporary_diff", 0.0),
        msr=th_inp.get("msr", 0.0),
        significant_investments=th_inp.get("significant_investments", 0.0),
    )

    # 2. AT1/T2 인정한도
    rec = at1_t2_recognition_limits(cet1.net, at1.net, tier2.net)

    # 3. Buffer layering — CCyB from exposures if supplied
    if exposures_by_country:
        ccyb_info = country_ccyb_weighted(exposures_by_country,
                                          ccyb_rates=ccyb_rates)
        ccyb_eff = ccyb_info["weighted_ccyb"] if countercyclical == 0.0 else countercyclical
    else:
        ccyb_info = {"weighted_ccyb": 0.0,
                     "by_country": pd.DataFrame(
                         columns=["country", "exposure", "share",
                                  "ccyb", "weighted"])}
        ccyb_eff = countercyclical
    layering = compute_buffer_layering(
        countercyclical=ccyb_eff, dsib_bucket=dsib_bucket,
        p2r=p2r, p2g=p2g,
    )

    # 4. SREP evaluation
    cet1_ratio = cet1.net / rwa
    srep = evaluate_srep(cet1_ratio, layering)

    # 5. MDA component breakdown — use distributable_pct from the buffer position
    from risk_lib.mda import compute_mda
    buffers = {"capital_conservation": layering.capital_conservation,
               "countercyclical": layering.countercyclical,
               "dsib": layering.dsib}
    m = compute_mda(cet1_ratio, cet1.net, rwa, buffers=buffers)
    mreq = mda_request or {}
    mda_df = mda_component_breakdown(
        # rough distributable earnings = 10% of CET1 / 4 if not supplied
        distributable_earnings=mreq.get("distributable_earnings",
                                        cet1.net * 0.10 / 4),
        distributable_pct=m.distributable_pct,
        requested_dividend=mreq.get("dividend", cet1.net * 0.01),
        requested_buyback=mreq.get("buyback", cet1.net * 0.005),
        requested_variable_comp=mreq.get("variable_comp", cet1.net * 0.003),
        requested_at1_coupon=mreq.get("at1_coupon", at1.net * 0.07 / 4),
    )

    # 6. Quarterly CET1 path
    qpath = cet1_quarterly_path(
        cet1_start=cet1.net, rwa_start=rwa, quarters=4,
        quarterly_earnings=quarterly_earnings,
        quarterly_dividend=quarterly_dividend,
        quarterly_buyback=quarterly_buyback,
        quarterly_new_issuance=quarterly_new_issuance,
        rwa_growth_per_q=rwa_growth_per_q,
        srep_cet1=layering.srep_cet1, ocr_cet1=layering.ocr_cet1,
    )

    return BISDeepResult(
        cet1=cet1, at1=at1, tier2=tier2,
        cet1_table=cet1_decomposition_table(cet1),
        at1_table=at1_decomposition_table(at1),
        tier2_table=tier2_decomposition_table(tier2),
        threshold_test=th_res, recognition=rec,
        layering=layering, layering_table=layering.to_layers(),
        country_ccyb=ccyb_info, srep=srep,
        mda_components=mda_df, quarterly_path=qpath,
    )


# ============================================================================
# 8. Helper — synthesise components from a plain CapitalStack
# ============================================================================


# IRB 초과충당금의 보완자본 산입 한도 — IRB 신용 RWA의 0.6% (CRE40.30).
IRB_PROVISION_SURPLUS_CAP = 0.006


def expected_loss_vs_provisions(irb_el: float, eligible_provisions: float,
                                irb_credit_rwa: float = 0.0) -> dict[str, float]:
    """IRB 기대손실과 적격충당금 비교 — CRE35.3 · CRE40.11 · CRE40.30.

    IRB를 쓰면 규제상 기대손실(EL)과 회계상 충당금을 **합계 수준**에서 대비해야
    한다. EL이 크면 그 차액을 보통주자본에서 **차감**하고(CRE40.11), 충당금이
    크면 초과분을 IRB 신용 RWA의 0.6% 한도 안에서 보완자본에 **산입**한다
    (CRE40.30).

    이 비교가 구현되지 않아 `CET1Components.expected_loss_shortfall`이 항상
    0이었다 — 현 포트폴리오는 충당금이 EL보다 커서 차감 대상이 0이라 산출값이
    틀리지는 않았으나, 자본 원장이나 포트폴리오가 바뀌면 조용히 틀린다.
    "지금 0이다"와 "통제가 있다"는 다르다 (독립검증 지적 F-704).

    대손준비금(F-601)과 같은 **합계 기준** 비교다. 익스포저별로 max(0, ·)를
    걸면 초과충당 익스포저가 상계되지 못해 차감이 과대해진다.
    """
    net = float(irb_el) - float(eligible_provisions)
    shortfall = max(0.0, net)                     # CET1에서 차감
    surplus = max(0.0, -net)                      # 보완자본 산입 후보
    cap = float(irb_credit_rwa) * IRB_PROVISION_SURPLUS_CAP
    return {
        "irb_el": float(irb_el),
        "eligible_provisions": float(eligible_provisions),
        "net": net,
        "shortfall": shortfall,
        "surplus": surplus,
        "surplus_cap": cap,
        "surplus_recognised": min(surplus, cap),
    }


def synthesise_components_from_stack(
    cet1_total: float, at1_total: float, tier2_total: float,
    irb_rwa: float = 0.0, el_shortfall: float = 0.0,
) -> tuple[CET1Components, AT1Components, Tier2Components]:
    """When only aggregate CET1/AT1/T2 are available, split into plausible
    item-level mix for visualisation.  Pure proportional allocation — sums
    back to the input net values exactly.
    """
    # CET1 mix (industry-typical KR commercial bank).
    # Gross composition (% of gross): common 7 + premium 20 + retained 65 + AOCI 5 + minority 3 = 100.
    # Deductions (% of gross):        goodwill 3 + intangibles 1.5 + DTA 1.5 + other 1 = 7.
    # ⇒ net = gross × (1 − 0.07).  Pick gross so net == cet1_total.
    d_ratio = 0.07
    gross_target = cet1_total / (1.0 - d_ratio) if cet1_total > 0 else 0.0
    cet1 = CET1Components(
        common_shares=gross_target * 0.07,
        share_premium=gross_target * 0.20,
        retained_earnings=gross_target * 0.65,
        aoci=gross_target * 0.05,
        minority_interest=gross_target * 0.03,
        goodwill=gross_target * 0.03,
        intangibles=gross_target * 0.015,
        dta_excess=gross_target * 0.015,
        other_deductions=gross_target * 0.01,
        expected_loss_shortfall=float(el_shortfall),
    )
    # AT1 mix — perpetual notes dominant
    at1 = AT1Components(
        perpetual_notes=at1_total * 0.80,
        non_cumulative_preferred=at1_total * 0.20,
    )
    # Tier2 mix — subordinated debt + general provisions (1.25% of IRB RWA cap)
    gp_cap = max(0.0, irb_rwa) * 0.0125
    gp_used = min(gp_cap, tier2_total * 0.25)
    tier2 = Tier2Components(
        subordinated_debt=tier2_total - gp_used,
        general_provisions=gp_used,
        irb_rwa_for_gp_cap=irb_rwa,
        subordinated_remaining_years=5.0,
    )
    return cet1, at1, tier2
