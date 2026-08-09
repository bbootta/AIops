"""Single source of truth for regulatory constants and citations.

Every Basel III / IFRS 9 / 금감원 threshold the harness uses is defined here
with its source paragraph attached, so a) thresholds drift in one place when a
standard changes, b) every quantitative validation check can cite its source
in the결재 report, c) auditors can trace each number back to a paragraph.

Sections cited:
  Basel III Consolidated Framework (BCBS, https://www.bis.org/basel_framework/)
    CRE10  – Calculation of RWA, overview
    CRE20  – Standardised approach for credit RWA (ECRA variant)
    CRE22  – Credit risk mitigation (CRM) — supervisory haircuts
    CRE31  – IRB risk weight functions (Vasicek/Gordy ASRF)
    CRE32  – PD / LGD / EAD parameters and floors
    LEV10  – Leverage ratio (3% Tier1 / EM)
    MAR20  – Market risk — simplified standardised approach
    OPE25  – Operational risk — Standardised Measurement Approach (SMA)
    RBC20  – Capital buffers (CCB 2.5%, CCyB, D-SIB)
    RBC30  – Output floor (72.5% fully phased in)

  IFRS 9 Financial Instruments (IASB)
    5.5.3   – 12-month ECL (Stage 1)
    5.5.5   – Lifetime ECL (Stage 2)
    5.5.7   – Significant Increase in Credit Risk (SICR)
    5.5.17  – Probability-weighted, forward-looking
    B5.5.42 – Multiple economic scenarios

  금융감독원 (FSS / KR)
    은행업감독업무시행세칙 (감독세칙)
      § 자본적정성 — CET1/T1/Total 최저비율 + 자본보전버퍼 2.5%
      § 신용공여한도 — 동일차주 25%, 동일인 20% of Tier1 (은행법 §35)
      § 대손충당금 적립기준 — IFRS9 정합
      § 스트레스테스트 가이드라인 — baseline/adverse/severe
      § 신용평가모형 — 변별력(Gini) 및 안정성(PSI) 기준

  Academic
    Vasicek O. (2002) "The Distribution of Loan Portfolio Value"
    Gordy M. (2003) "A Risk-Factor Model Foundation for Ratings-Based Capital"
    Hosmer D., Lemeshow S. (1980) — GOF test used here for PD calibration
    BCBS WP14 (2005) — Studies on the Validation of IRB Systems
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Citation:
    """A (regulatory) source paragraph attached to a constant or check."""
    standard: str   # e.g. "Basel III"
    section: str    # e.g. "CRE31.5"
    note: str = ""

    def __str__(self) -> str:
        base = f"{self.standard} {self.section}"
        return f"{base} — {self.note}" if self.note else base


# ============================================================================
# Capital adequacy — Pillar 1 minima and buffers
# ============================================================================

BIS_MIN_CET1 = 0.045        # Basel III CRE10.4 / 감독세칙 자본적정성
BIS_MIN_TIER1 = 0.060
BIS_MIN_TOTAL = 0.080

CAPITAL_CONSERVATION_BUFFER = 0.025      # RBC20.1
COUNTERCYCLICAL_BUFFER_RANGE = (0.0, 0.025)  # RBC20 (national)
DSIB_BUFFER_RANGE = (0.0, 0.02)          # RBC40 / 금감원 시스템적중요은행 가산

LEVERAGE_MIN_RATIO = 0.03                # LEV10.6
GSIB_LEVERAGE_ADDON = 0.005              # LEV40 (50% of buffer)

OUTPUT_FLOOR_FULLY_LOADED = 0.725        # RBC30.1 (2028 phased-in)
OUTPUT_FLOOR_PHASE_IN = {                # RBC30.5 transition schedule
    2023: 0.500, 2024: 0.550, 2025: 0.600,
    2026: 0.650, 2027: 0.700, 2028: 0.725,
}

CITE_BIS_MIN = Citation("Basel III", "CRE10.4 / 감독세칙",
                        "CET1 4.5% + Tier1 6.0% + Total 8.0%")
CITE_CCB = Citation("Basel III", "RBC20.1", "자본보전버퍼 2.5% (상시)")
CITE_LEVERAGE = Citation("Basel III", "LEV10.6", "Leverage ratio ≥ 3.0%")
CITE_OUTPUT_FLOOR = Citation("Basel III", "RBC30.1",
                              "Output floor 72.5% (2028 fully phased in)")


# ============================================================================
# Credit RWA — IRB / SA
# ============================================================================

PD_FLOOR_BPS = 5                         # BCBS d424 (2017) Basel III finalisation:
                                         # PD 하한 5bp (AIRB corporate/bank 및 대부분 retail).
                                         # 직전 CRE32.5 3bp 기준을 대체.
LGD_FLOOR_UNSECURED_CORP = 0.25          # CRE32 FIRB unsecured senior
LGD_FLOOR_MORTGAGE = 0.05                # CRE32 residential mortgage
MATURITY_FLOOR_YEARS = 1.0               # CRE31.6
MATURITY_CAP_YEARS = 5.0                 # CRE31.6
CONFIDENCE_LEVEL = 0.999                 # CRE31.4 (G(0.999))

DEFAULT_DPD_THRESHOLD = 90               # CRE36.69 + IFRS 9 5.5.5 + 감독세칙
SICR_DPD_THRESHOLD = 30                  # IFRS 9 5.5.11 rebuttable presumption

CITE_PD_FLOOR = Citation("Basel III", "CRE32.5 / BCBS d424",
                          "PD 하한 5bp (2017년 최종안에서 3bp→5bp 상향)")
CITE_MATURITY = Citation("Basel III", "CRE31.6", "M floored at 1y, capped at 5y")
CITE_DEFAULT_90DPD = Citation("Basel III / IFRS 9", "CRE36.69 / 5.5.5",
                              "90일 이상 연체 시 부도/Stage 3")
CITE_SICR = Citation("IFRS 9", "5.5.11",
                     "SICR rebuttable presumption: 30 DPD")
CITE_IRB_FORMULA = Citation("Basel III", "CRE31.5",
                            "Vasicek ASRF risk-weight function")


# ============================================================================
# IFRS 9 — ECL
# ============================================================================

IFRS9_SICR_PD_MULTIPLE = 2.0             # 5.5.7 (entity-specific; 2x is common KR practice)
IFRS9_FORECAST_HORIZON_YEARS = 3         # 5.5.17 reasonable-and-supportable
IFRS9_REVERSION_DECAY = 0.5              # post-horizon revert to TTC

CITE_IFRS9_STAGE1 = Citation("IFRS 9", "5.5.3", "Stage 1 → 12-month ECL")
CITE_IFRS9_STAGE2 = Citation("IFRS 9", "5.5.5", "Stage 2 (SICR) → lifetime ECL")
CITE_IFRS9_FORWARD = Citation("IFRS 9", "B5.5.42",
                               "Probability-weighted multiple scenarios")
CITE_VASICEK = Citation("Vasicek (2002)", "—",
                        "One-factor Gaussian model for PIT PD transform")


# ============================================================================
# 금감원 — 신용공여한도 (large exposure)
# ============================================================================

SINGLE_OBLIGOR_LIMIT_PCT_TIER1 = 0.25    # 은행법 §35 / 감독세칙
SINGLE_PERSON_LIMIT_PCT_TIER1 = 0.20

CITE_OBLIGOR_LIMIT = Citation("은행법", "§35",
                              "동일차주 신용공여 한도 Tier1의 25%")


# ============================================================================
# PD model validation — 변별력 / 안정성 / 캘리브레이션
# ============================================================================

# Discrimination thresholds.  Supervisory practice (BCBS WP14, ECB SREP, 금감원
# 신용평가모형 검증 가이드) treats Gini in tiers rather than a single cliff:
#   < 0.20  : poor — model has essentially no usable signal → FAIL
#   0.20–0.40: acceptable but weak; requires monitoring & improvement → WARN
#   ≥ 0.40  : good → PASS
GINI_MIN_ACCEPTABLE = 0.20
GINI_MIN_GOOD = 0.40

# Population Stability Index thresholds (industry standard).
PSI_STABLE = 0.10                        # < 0.10 stable
PSI_MINOR_SHIFT = 0.25                   # 0.10–0.25 minor, > 0.25 major shift

# Hosmer-Lemeshow calibration acceptance (95% confidence).
HL_P_VALUE_MIN = 0.05

CITE_GINI = Citation("BCBS WP14 / 감독세칙", "—",
                     "PD 모형 변별력 Gini ≥ 0.40 양호")
CITE_PSI = Citation("Industry standard", "—",
                    "PSI < 0.10 안정, 0.10–0.25 경미, > 0.25 중대 이동")
CITE_HL = Citation("Hosmer-Lemeshow (1980)", "—",
                   "PD 캘리브레이션 χ² 검정, p ≥ 0.05 양호")


# ============================================================================
# Concentration risk
# ============================================================================

HHI_HIGH = 0.18                          # DOJ/FTC analog; supervisory practice
HHI_VERY_HIGH = 0.25

CITE_HHI = Citation("US DOJ/FTC Horizontal Merger Guidelines", "—",
                    "HHI > 0.18 highly concentrated; supervisory practice "
                    "for portfolio diversification reviews")


# ============================================================================
# RAPM
# ============================================================================

RAPM_HURDLE_RATE = 0.10                  # cost of equity benchmark


# ============================================================================
# ALM — IRRBB (interest rate risk in the banking book)
# ============================================================================

# 금리충격 폭(bp)은 **이 파일에 없다.** 통화별 값은 BCBS d368 Annex 2 Table 1의
# 규제표이고, 그 표를 적재하는 곳은 원장 빌더 `alm.curves.build_rate_shock_param`
# 한 군데다. 여기 상수를 두면 원장을 채워도 감응도·화면이 옛 상수로 계속 나눠
# 두 벌이 어긋난다. 아래 이름은 그 원장을 읽어 주는 계승 접근자다.
#
# 정정 이력: 이전 판은 200/300/150을 "USD reference calibration을 보수적
# 기본값으로 쓴다"고 적었다. 사실과 반대다 — 원문 KRW는 300/400/200이고 USD는
# 모든 축에서 그보다 작으므로 USD 대용은 보수가 아니라 과소산출이었다.
IRRBB_SHOCK_LEDGER_CCY = "KRW"           # 계승 이름이 가리키는 통화
IRRBB_SHOCK_LEDGER_FRAMEWORK = "d368_2016"

_IRRBB_SHOCK_ATTRS = {
    "IRRBB_SHOCK_PARALLEL_BP": "parallel",
    "IRRBB_SHOCK_SHORT_BP": "short",
    "IRRBB_SHOCK_LONG_BP": "long",
}


def irrbb_shock_bp(shock_type: str, *,
                   ccy: str = IRRBB_SHOCK_LEDGER_CCY,
                   framework_version: str = IRRBB_SHOCK_LEDGER_FRAMEWORK) -> int:
    """`alm_rate_shock_param` 원장의 충격폭(bp).

    원장에 값이 없으면 예외를 낸다. 기본값으로 대신 채우면 근거 없는 절대수준이
    조용히 산출에 들어간다.
    """
    from risk_lib.alm.curves import build_rate_shock_param
    import pandas as pd

    sp = build_rate_shock_param()
    hit = sp[(sp["framework_version"] == framework_version)
             & (sp["ccy"] == ccy) & (sp["shock_type"] == shock_type)]
    if hit.empty or pd.isna(hit.iloc[0]["shock_bp"]):
        raise LookupError(
            f"alm_rate_shock_param에 {framework_version}/{ccy}/{shock_type}의 "
            "충격폭이 없다 — 원장을 채우기 전까지 이 수치는 산출에 쓸 수 없다")
    return int(hit.iloc[0]["shock_bp"])


def irrbb_decay_x(framework_version: str = IRRBB_SHOCK_LEDGER_FRAMEWORK) -> float:
    """S_short(t) = e^{−t/x}의 x. `alm_scenario_def.decay_x`에서 읽는다."""
    from risk_lib.alm.curves import build_scenario_def

    xs = {float(v) for v in build_scenario_def()["decay_x"]}
    if len(xs) != 1:
        raise ValueError(f"alm_scenario_def의 decay_x가 여럿이다 {sorted(xs)}")
    return xs.pop()


def __getattr__(name: str):
    """계승 이름(IRRBB_SHOCK_*_BP · IRRBB_SHOCK_DECAY_X)을 원장으로 잇는다.

    `sensitivity.py`가 ΔEVE를 임의 충격폭으로 환산할 때 이 이름으로 나눈다.
    상수로 남겨 두면 원장의 충격폭이 바뀌어도 환산 분모가 따라가지 않아 감응도
    화면이 산출과 어긋난다. 지연 import라 references를 부르는 쪽이 ALM 모듈
    적재 비용을 항상 물지는 않는다.
    """
    if name in _IRRBB_SHOCK_ATTRS:
        return irrbb_shock_bp(_IRRBB_SHOCK_ATTRS[name])
    if name == "IRRBB_SHOCK_DECAY_X":
        return irrbb_decay_x()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Supervisory outlier test: max ΔEVE decline ≤ 15% of Tier 1 capital.
# BCBS d368 (2016.4) §88 원문확인 — 분모는 기본자본(Tier 1)이고 총자기자본이
# 아니다. 국내 「은행업감독업무시행세칙」 [별표 9의1] 제27항은 **자기자본의
# 20%**를 쓰고 지표도 ΔEVE가 아니라 금리 VaR이므로 별개 기준이다.
IRRBB_OUTLIER_EVE_PCT_TIER1 = 0.15
IRRBB_EARLY_WARNING_PCT_TIER1 = 0.12     # internal early-warning level

CITE_IRRBB = Citation("BCBS d368 (2016.4)", "Annex 2",
                      "6대 표준 금리충격 시나리오, ΔEVE/ΔNII. 통화별 충격폭은 "
                      "Table 1 (KRW 300/400/200)")
CITE_IRRBB_OUTLIER = Citation("BCBS d368 (2016.4)", "§88",
                              "outlier test: 최대 ΔEVE 대 기본자본(Tier 1)의 15%")


# ============================================================================
# ALM — LCR (Liquidity Coverage Ratio)
# ============================================================================

LCR_MIN = 1.00                           # LCR20.1 — 100% 상시
LCR_L2_CAP = 0.40                        # LCR30 — Level 2 ≤ 40% of HQLA
LCR_L2B_CAP = 0.15                       # LCR30 — Level 2B ≤ 15% of HQLA
LCR_HAIRCUT_L2A = 0.15                   # LCR30
LCR_HAIRCUT_L2B = 0.50                   # LCR30 (보수적 단일 적용)
LCR_INFLOW_CAP = 0.75                    # LCR40 — inflows ≤ 75% of outflows

# Run-off rates (LCR40).
LCR_RUNOFF = {
    "retail_stable": 0.05,
    "retail_less_stable": 0.10,
    "corporate_operational": 0.25,
    "corporate_non_operational": 0.40,
    "wholesale_fi_unsecured": 1.00,
    "secured_funding_l1": 0.00,
    "secured_funding_other": 0.25,
    "committed_facilities": 0.10,
}
LCR_INFLOW_RATES = {
    "retail_inflows": 0.50,
    "wholesale_inflows": 0.50,
    "fi_inflows": 1.00,
}

CITE_LCR = Citation("Basel III", "LCR20.1 / LCR30 / LCR40",
                    "LCR = HQLA / 30일 순현금유출 ≥ 100%")


# ============================================================================
# ALM — NSFR (Net Stable Funding Ratio)
# ============================================================================

NSFR_MIN = 1.00                          # NSF20.1 — 100% 상시

NSFR_ASF_FACTORS = {                     # NSF30 — available stable funding
    "capital": 1.00,
    "retail_stable": 0.95,
    "retail_less_stable": 0.90,
    "corporate_lt1y": 0.50,
    "wholesale_fi_lt6m": 0.00,
    "wholesale_fi_6to12m": 0.50,
    "funding_gt1y": 1.00,
}
NSFR_RSF_FACTORS = {                     # NSF30 — required stable funding
    "cash": 0.00,
    "hqla_l1": 0.05,
    "hqla_l2a": 0.15,
    "hqla_l2b": 0.50,
    "loans_fi_lt6m": 0.15,
    "loans_lt1y": 0.50,
    "mortgages_ge1y": 0.65,
    "other_loans_ge1y": 0.85,
    "npl": 1.00,
    "other_assets": 1.00,
}

CITE_NSFR = Citation("Basel III", "NSF20.1 / NSF30",
                     "NSFR = 가용안정자금조달 / 필요안정자금조달 ≥ 100%")


# ============================================================================
# ICAAP — 내부자본 적정성 (Pillar 2)
# ============================================================================

ICAAP_CONFIDENCE = 0.999                 # 경제자본 신뢰수준 (IRB와 정합)
ICAAP_GREEN_UTILISATION = 0.80           # 내부자본 사용률 80% 이하 양호
ICAAP_AMBER_UTILISATION = 1.00           # 80~100% 주의, 초과 시 부적정

# Inter-risk correlation matrix (credit, market, operational, irrbb).
# Conservative supervisory-style assumptions (industry ICAAP practice).
ICAAP_RISK_TYPES = ["credit", "market", "operational", "irrbb"]
ICAAP_CORRELATION = [
    [1.00, 0.50, 0.30, 0.40],
    [0.50, 1.00, 0.20, 0.50],
    [0.30, 0.20, 1.00, 0.20],
    [0.40, 0.50, 0.20, 1.00],
]

CITE_ICAAP = Citation("Basel III / 감독세칙", "SRP20 (Pillar 2) / ICAAP",
                      "내부자본 ≥ 위험유형별 경제자본 통합액")
CITE_EC_AGG = Citation("Industry ICAAP practice", "—",
                       "분산-공분산 방식 위험 통합 (inter-risk correlation)")
CITE_CONC_ADDON = Citation("Gordy (2003) / SRP20", "—",
                           "집중리스크 Pillar 2 add-on (granularity adjustment 단순화)")


# ============================================================================
# 순자본비율 (NCR) — 금융투자업자 건전성 (한국)
# ============================================================================
# 2016년 개편된 신 NCR 체계:
#   순자본비율 = (영업용순자본 − 총위험액) / 필요유지자기자본 × 100%
# 舊 NCR(영업용순자본/총위험액)과 분모·의미가 다르므로 혼용 금지.

NCR_MIN = 1.00                           # 100% — 적기시정조치 발동 기준선
NCR_PROMPT_ACTION = {                    # 제3-26조(권고)·제3-27조(요구)·제3-28조(명령)
    "경영개선권고": 1.00,                #   100% 미만
    "경영개선요구": 0.50,                #    50% 미만
    "경영개선명령": 0.00,                #     0% 미만
}
NCR_EARLY_WARNING = 1.50                 # 내부 조기경보 (감독 기준 아님 — 관리목적)

# 영업용순자본 차감항목 — 즉시 현금화가 곤란한 자산 (금융투자업규정 제3-11조 계열).
NCR_DEDUCTION_ITEMS = (
    "고정자산", "특수관계인채권", "임차보증금", "선급금·선급비용",
    "이연법인세자산", "무형자산",
)
# 가산항목 — 후순위성 자금 등 (제3-14조 계열).
NCR_ADDITION_ITEMS = ("후순위차입금", "대손충당금", "자산평가이익")

# 총위험액 구성 (제3-21조 계열): 시장·신용·운영위험액.
NCR_RISK_COMPONENTS = ("시장위험액", "신용위험액", "운영위험액")

CITE_NCR = Citation(
    "금융투자업규정", "제3-6조",
    "순자본비율 = (영업용순자본 − 총위험액) / 필요유지자기자본; "
    "필요유지자기자본 = 인가업무 단위별 최저자기자본의 100분의 70")
CITE_NCR_PROMPT_ACTION = Citation(
    "금융투자업규정", "제3-26조 · 제3-27조 · 제3-28조",
    "적기시정조치 — 순자본비율 100% 미만 경영개선권고(제3-26조), "
    "50% 미만 경영개선요구(제3-27조), 0% 미만 경영개선명령(제3-28조)")
CITE_NCR_DEDUCTION = Citation(
    "금융투자업규정", "제3-11조",
    "영업용순자본 차감항목 — 즉시 현금화 곤란 자산")
CITE_NCR_RISK = Citation(
    "금융투자업규정", "제3-21조",
    "총위험액 = 시장위험액 + 신용위험액 + 운영위험액")


# ============================================================================
# Convenience: a flat listing of all citations for the report's "출처" section.
# ============================================================================

ALL_CITATIONS: list[tuple[str, Citation]] = [
    ("§4 BIS 자본적정성",       CITE_BIS_MIN),
    ("§4 BIS 자본적정성",       CITE_CCB),
    ("§5 레버리지비율",         CITE_LEVERAGE),
    ("§3 RWA · output floor",   CITE_OUTPUT_FLOOR),
    ("§3 RWA · IRB",            CITE_IRB_FORMULA),
    ("§3 RWA · IRB",            CITE_PD_FLOOR),
    ("§3 RWA · IRB",            CITE_MATURITY),
    ("§6/§7 ECL · 부도정의",    CITE_DEFAULT_90DPD),
    ("§6 ECL · SICR",           CITE_SICR),
    ("§6 ECL · Stage 1",        CITE_IFRS9_STAGE1),
    ("§6 ECL · Stage 2",        CITE_IFRS9_STAGE2),
    ("§6-1 PIT 거시연계",       CITE_IFRS9_FORWARD),
    ("§6-1 PIT 거시연계",       CITE_VASICEK),
    ("§8 한도관리",             CITE_OBLIGOR_LIMIT),
    ("§9 집중리스크",           CITE_HHI),
    ("§2/§12 PD 모형 검증",     CITE_GINI),
    ("§2/§12 PD 모형 검증",     CITE_PSI),
    ("§12 PD 캘리브레이션",     CITE_HL),
    ("§13 내부자본 (ICAAP)",    CITE_ICAAP),
    ("§13 내부자본 (ICAAP)",    CITE_EC_AGG),
    ("§13 내부자본 (ICAAP)",    CITE_CONC_ADDON),
    ("§14 ALM · IRRBB",         CITE_IRRBB),
    ("§14 ALM · IRRBB",         CITE_IRRBB_OUTLIER),
    ("§14 ALM · LCR",           CITE_LCR),
    ("§14 ALM · NSFR",          CITE_NSFR),
    ("§16 순자본비율 (NCR)",     CITE_NCR),
    ("§16 순자본비율 (NCR)",     CITE_NCR_PROMPT_ACTION),
    ("§16 순자본비율 (NCR)",     CITE_NCR_DEDUCTION),
    ("§16 순자본비율 (NCR)",     CITE_NCR_RISK),
]
