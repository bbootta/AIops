"""Scenario Library — historic + hypothetical macro/market scenarios.

Top-IB risk shops maintain a curated library of 50+ named scenarios:
  - **Historic**: 1997 Asian Crisis, 2008 GFC, 2011 EU sovereign, 2020 COVID,
    2022 Ukraine war, 2023 US regional bank failures (SVB/Signature)
  - **Hypothetical**: KR property crash, US stagflation, China hard landing,
    SK chip cycle bust, Japanification, cyber-event widespread, climate
    transition shock (NGFS Disorderly), rate spike (1980 Volcker redux)

Each scenario carries:
  - macro shocks (GDP, unemployment, FX, equity, rates, credit spreads)
  - narrative description + historical context
  - regulatory citations (Fed CCAR, EBA EU-wide ST, BoE solvency ST)
  - expected impact direction (capital / liquidity / earnings)

The library feeds risk_lib.stress runners so any scenario can be applied
with a single function call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MacroShocks:
    """Standardised macro shock vector (1-year horizon, peak values)."""
    gdp_growth: float           # absolute change (e.g. -0.05 = GDP -5%)
    unemployment: float         # absolute change (e.g. +0.03 = +3%p)
    fx_usd_krw: float           # % change (positive = KRW weaker)
    equity_kospi: float         # % change (negative = drop)
    rate_10y: float             # absolute bp change (e.g. 0.02 = +200bp)
    credit_spread_corp: float   # absolute bp change
    hpi_korea: float            # % change in housing price index
    oil_brent: float = 0.0      # % change
    co2_price: float = 0.0      # absolute change (USD/tCO2)


@dataclass(frozen=True)
class ScenarioEntry:
    name: str
    short: str
    family: str                 # historic | hypothetical | regulatory | climate
    horizon_years: float
    narrative: str
    citation: str
    shocks: MacroShocks
    severity: float             # 1=mild, 2=adverse, 3=severe (PD/LGD multiplier hint)


# ----- historic ------------------------------------------------------------

_HIST = [
    ScenarioEntry(
        name="1997 아시아 외환위기 (한국)",
        short="asia_1997",
        family="historic", horizon_years=1.0,
        narrative=("1997년 외환위기 — 단기외채 상환 불능 → IMF 구제금융, "
                   "KRW 49% 평가절하, 콜금리 30%, GDP -5.7%, 실업률 +5%p. "
                   "재벌 파산 (한보 한진 대우 등), 은행 무수익여신 폭증."),
        citation="IMF Country Report 1997/99, 한국은행 외환위기 종합백서 2000",
        shocks=MacroShocks(
            gdp_growth=-0.057, unemployment=0.050,
            fx_usd_krw=0.49, equity_kospi=-0.51,
            rate_10y=0.150, credit_spread_corp=0.600,
            hpi_korea=-0.12,
        ),
        severity=3.0,
    ),
    ScenarioEntry(
        name="2008 글로벌 금융위기",
        short="gfc_2008",
        family="historic", horizon_years=1.5,
        narrative=("Lehman 파산 → 글로벌 신용경색, 미 GDP -4.3%, 실업률 10%, "
                   "S&P -57% peak-to-trough, 회사채 spread 850bp, "
                   "한국 KOSPI -45%, KRW -38% (1500원), 부동산 -10%."),
        citation="FCIC Final Report (2011), BIS Annual Report 2009, BoK Annual Report 2009",
        shocks=MacroShocks(
            gdp_growth=-0.043, unemployment=0.060,
            fx_usd_krw=0.38, equity_kospi=-0.45,
            rate_10y=-0.025, credit_spread_corp=0.500,
            hpi_korea=-0.10,
        ),
        severity=3.0,
    ),
    ScenarioEntry(
        name="2020 COVID-19 pandemic shock",
        short="covid_2020",
        family="historic", horizon_years=1.0,
        narrative=("Pandemic — 글로벌 lockdown, 미 GDP -3.4%, 실업률 14.7% peak, "
                   "유가 -65%, 단기 유동성 발작 → Fed 대규모 양적완화. "
                   "한국 GDP -0.9% (선방), 모라토리엄 대출 22조."),
        citation="IMF WEO Apr 2020, FOMC March 2020 statement, 한국은행 2020 통화신용정책",
        shocks=MacroShocks(
            gdp_growth=-0.034, unemployment=0.020,
            fx_usd_krw=0.06, equity_kospi=-0.36,
            rate_10y=-0.020, credit_spread_corp=0.300,
            hpi_korea=0.05, oil_brent=-0.65,
        ),
        severity=2.5,
    ),
    ScenarioEntry(
        name="2022 우크라이나전·인플레 충격",
        short="ukraine_2022",
        family="historic", horizon_years=1.0,
        narrative=("러시아 우크라이나 침공 → 에너지 충격, "
                   "유럽 인플레 10%+, ECB·Fed 급격 금리 인상 425bp, "
                   "60/40 portfolio 사상 최악 수익률, KRW 1450원."),
        citation="ECB Financial Stability Review 2022/H2, Fed SEP Dec 2022",
        shocks=MacroShocks(
            gdp_growth=-0.005, unemployment=0.005,
            fx_usd_krw=0.18, equity_kospi=-0.25,
            rate_10y=0.300, credit_spread_corp=0.200,
            hpi_korea=-0.05, oil_brent=0.60,
        ),
        severity=2.0,
    ),
    ScenarioEntry(
        name="2023 미국 지역은행 위기 (SVB / Signature)",
        short="us_banks_2023",
        family="historic", horizon_years=0.5,
        narrative=("SVB / Signature / First Republic 연쇄 파산 → "
                   "예금 인출 발작, AOCI 손실 노출, 양적긴축 일시 중단. "
                   "유동성·금리 스트레스 동시 발현."),
        citation="FDIC Failure Report 2023, Fed SR 23-1, BCBS d573 (2024)",
        shocks=MacroShocks(
            gdp_growth=-0.005, unemployment=0.010,
            fx_usd_krw=0.05, equity_kospi=-0.10,
            rate_10y=-0.080, credit_spread_corp=0.150,
            hpi_korea=0.0,
        ),
        severity=1.8,
    ),
]


# ----- hypothetical --------------------------------------------------------

_HYPO = [
    ScenarioEntry(
        name="한국 부동산 급락 시나리오",
        short="kr_property_crash",
        family="hypothetical", horizon_years=1.5,
        narrative=("PF 부실 본격화 + 가계부채 디레버리징 → 부동산 -25%, "
                   "건설사 연쇄 디폴트, 가계 신용손실 폭증, "
                   "은행 모기지 LTV breach 30%."),
        citation="한국은행 금융안정보고서 가정 시나리오",
        shocks=MacroShocks(
            gdp_growth=-0.020, unemployment=0.025,
            fx_usd_krw=0.10, equity_kospi=-0.25,
            rate_10y=0.050, credit_spread_corp=0.250,
            hpi_korea=-0.25,
        ),
        severity=2.5,
    ),
    ScenarioEntry(
        name="중국 경착륙 시나리오",
        short="china_hard_landing",
        family="hypothetical", horizon_years=1.0,
        narrative=("중국 부동산 부실 globalize → GDP -2%, 수출 의존 한국 직격, "
                   "원자재 수요 급락, KRW·CNY 동반 약세."),
        citation="IMF Article IV China 2024 hypothetical adverse scenario",
        shocks=MacroShocks(
            gdp_growth=-0.030, unemployment=0.020,
            fx_usd_krw=0.12, equity_kospi=-0.30,
            rate_10y=-0.030, credit_spread_corp=0.200,
            hpi_korea=-0.10, oil_brent=-0.30,
        ),
        severity=2.5,
    ),
    ScenarioEntry(
        name="반도체 cycle bust 시나리오",
        short="chip_cycle_bust",
        family="hypothetical", horizon_years=1.0,
        narrative=("AI 수요 둔화 + 메모리 공급과잉 → SK·삼전 매출 -40%, "
                   "관련 협력사 부실, GDP -1.5%, KOSDAQ -35%."),
        citation="한국 산업연구원 반도체 시나리오 분석 2024",
        shocks=MacroShocks(
            gdp_growth=-0.015, unemployment=0.015,
            fx_usd_krw=0.05, equity_kospi=-0.20,
            rate_10y=0.0, credit_spread_corp=0.100,
            hpi_korea=0.0,
        ),
        severity=2.0,
    ),
    ScenarioEntry(
        name="Japanification — 장기 저성장 함정",
        short="japanification",
        family="hypothetical", horizon_years=3.0,
        narrative=("장기 저성장 (GDP 1% 미만) + 디플레 + 인구 감소. "
                   "은행 NIM 압박, 자산 deflation, 신용수요 둔화."),
        citation="IMF WP/16/151 'Lessons from Japan'",
        shocks=MacroShocks(
            gdp_growth=-0.010, unemployment=0.010,
            fx_usd_krw=-0.05, equity_kospi=-0.10,
            rate_10y=-0.150, credit_spread_corp=0.050,
            hpi_korea=-0.05,
        ),
        severity=1.5,
    ),
    ScenarioEntry(
        name="1980 Volcker redux — 금리 급등",
        short="volcker_redux",
        family="hypothetical", horizon_years=1.0,
        narrative=("인플레 재발 → Fed 정책금리 8%, 10y 9%, "
                   "AOCI 대규모 손실, 모기지·소비 동시 둔화."),
        citation="historical analogue: 1979-82 Fed tightening cycle",
        shocks=MacroShocks(
            gdp_growth=-0.025, unemployment=0.030,
            fx_usd_krw=0.20, equity_kospi=-0.30,
            rate_10y=0.400, credit_spread_corp=0.300,
            hpi_korea=-0.10,
        ),
        severity=3.0,
    ),
    ScenarioEntry(
        name="대형 사이버 공격 — 금융인프라 마비",
        short="cyber_pandemic",
        family="hypothetical", horizon_years=0.25,
        narrative=("CCP 청산소 / 결제망 침해 2주 마비. "
                   "거래 불능 + 평판 손실 + 운영손실 1조원+."),
        citation="BIS CPMI cyber resilience guidance 2024",
        shocks=MacroShocks(
            gdp_growth=-0.005, unemployment=0.005,
            fx_usd_krw=0.03, equity_kospi=-0.15,
            rate_10y=0.0, credit_spread_corp=0.050,
            hpi_korea=0.0,
        ),
        severity=2.0,
    ),
]


# ----- regulatory ----------------------------------------------------------

_REG = [
    ScenarioEntry(
        name="Fed CCAR 2025 severely adverse",
        short="fed_ccar_2025_sev",
        family="regulatory", horizon_years=2.25,
        narrative=("미 연준 CCAR 2025 severely adverse 시나리오. "
                   "GDP -7.5% peak-to-trough, 실업률 10%, equity -55%, "
                   "회사채 spread 575bp peak."),
        citation="Fed CCAR 2025 Scenarios (Board of Governors 2025-02)",
        shocks=MacroShocks(
            gdp_growth=-0.075, unemployment=0.060,
            fx_usd_krw=0.20, equity_kospi=-0.55,
            rate_10y=-0.150, credit_spread_corp=0.575,
            hpi_korea=-0.30,
        ),
        severity=3.0,
    ),
    ScenarioEntry(
        name="EBA EU-wide ST 2025 adverse",
        short="eba_eu_2025_adv",
        family="regulatory", horizon_years=3.0,
        narrative=("EU 전역 스트레스. GDP -6.3%, 실업률 +6.1%p, "
                   "주택가격 -16%, 회사채 spread 480bp."),
        citation="EBA EU-Wide Stress Test 2025 Methodology",
        shocks=MacroShocks(
            gdp_growth=-0.063, unemployment=0.061,
            fx_usd_krw=0.10, equity_kospi=-0.40,
            rate_10y=0.150, credit_spread_corp=0.480,
            hpi_korea=-0.16,
        ),
        severity=2.8,
    ),
    ScenarioEntry(
        name="감독원 통합 스트레스 (한국)",
        short="fss_integrated_st",
        family="regulatory", horizon_years=2.0,
        narrative=("금감원 가이드라인 severely adverse — "
                   "GDP -3.5%, 실업률 +3.5%p, KOSPI -35%, "
                   "주택 -15%, 회사채 spread +300bp."),
        citation="금감원 통합 스트레스테스트 가이드라인 2024",
        shocks=MacroShocks(
            gdp_growth=-0.035, unemployment=0.035,
            fx_usd_krw=0.15, equity_kospi=-0.35,
            rate_10y=0.080, credit_spread_corp=0.300,
            hpi_korea=-0.15,
        ),
        severity=2.5,
    ),
]


# ----- climate -------------------------------------------------------------

_CLIMATE = [
    ScenarioEntry(
        name="NGFS Phase 4 — Disorderly Transition",
        short="ngfs_disorderly",
        family="climate", horizon_years=30.0,
        narrative=("Net-zero 목표 지연 후 급격 정책 강화. CO2 가격 USD 400/t (2050), "
                   "고탄소 자산 stranded asset 위험 → 전환 RWA +25%."),
        citation="NGFS Phase 4 Scenarios for central banks and supervisors (2023-11)",
        shocks=MacroShocks(
            gdp_growth=-0.015, unemployment=0.010,
            fx_usd_krw=0.05, equity_kospi=-0.15,
            rate_10y=0.050, credit_spread_corp=0.150,
            hpi_korea=-0.05, co2_price=400.0,
        ),
        severity=2.0,
    ),
    ScenarioEntry(
        name="NGFS Phase 4 — Hot House World",
        short="ngfs_hot_house",
        family="climate", horizon_years=30.0,
        narrative=("기후 대응 실패 → +3°C 시나리오. 물리적 손실 누적, "
                   "부동산·인프라 가치 하락, 해수면 상승."),
        citation="NGFS Phase 4 Hot House World (Current Policies)",
        shocks=MacroShocks(
            gdp_growth=-0.025, unemployment=0.020,
            fx_usd_krw=0.10, equity_kospi=-0.20,
            rate_10y=0.0, credit_spread_corp=0.100,
            hpi_korea=-0.10, co2_price=30.0,
        ),
        severity=2.5,
    ),
    ScenarioEntry(
        name="NGFS Phase 4 — Net Zero 2050 (Orderly)",
        short="ngfs_orderly",
        family="climate", horizon_years=30.0,
        narrative=("질서있는 net-zero 전환. 점진적 CO2 가격 인상 + 기술 투자. "
                   "단기 GDP 영향 작으나 고탄소 산업 점진적 감소."),
        citation="NGFS Phase 4 Net Zero 2050 (Orderly)",
        shocks=MacroShocks(
            gdp_growth=-0.005, unemployment=0.003,
            fx_usd_krw=0.0, equity_kospi=-0.05,
            rate_10y=0.020, credit_spread_corp=0.030,
            hpi_korea=0.0, co2_price=130.0,
        ),
        severity=1.2,
    ),
]


# ----- library aggregation -------------------------------------------------

SCENARIO_LIBRARY: list[ScenarioEntry] = _HIST + _HYPO + _REG + _CLIMATE


def by_short(name: str) -> ScenarioEntry:
    for s in SCENARIO_LIBRARY:
        if s.short == name:
            return s
    raise KeyError(f"scenario not found: {name}")


def by_family(family: str) -> list[ScenarioEntry]:
    return [s for s in SCENARIO_LIBRARY if s.family == family]


def to_dataframe() -> "pd.DataFrame":
    import pandas as pd
    return pd.DataFrame([
        {
            "name": s.name, "short": s.short, "family": s.family,
            "horizon": s.horizon_years, "severity": s.severity,
            "narrative": s.narrative, "citation": s.citation,
            "gdp": s.shocks.gdp_growth, "unemp": s.shocks.unemployment,
            "fx": s.shocks.fx_usd_krw, "equity": s.shocks.equity_kospi,
            "rate_10y": s.shocks.rate_10y,
            "spread": s.shocks.credit_spread_corp,
            "hpi": s.shocks.hpi_korea, "oil": s.shocks.oil_brent,
            "co2": s.shocks.co2_price,
        }
        for s in SCENARIO_LIBRARY
    ])
