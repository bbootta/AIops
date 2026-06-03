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

PD_FLOOR_BPS = 3                         # CRE32.5: PD floor 3bp (0.03%)
LGD_FLOOR_UNSECURED_CORP = 0.25          # CRE32 FIRB unsecured senior
LGD_FLOOR_MORTGAGE = 0.05                # CRE32 residential mortgage
MATURITY_FLOOR_YEARS = 1.0               # CRE31.6
MATURITY_CAP_YEARS = 5.0                 # CRE31.6
CONFIDENCE_LEVEL = 0.999                 # CRE31.4 (G(0.999))

DEFAULT_DPD_THRESHOLD = 90               # CRE36.69 + IFRS 9 5.5.5 + 감독세칙
SICR_DPD_THRESHOLD = 30                  # IFRS 9 5.5.11 rebuttable presumption

CITE_PD_FLOOR = Citation("Basel III", "CRE32.5", "PD 하한 3bp")
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
]
