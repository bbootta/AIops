"""거시 narrative — 시나리오별 거시변수 표 + 스토리텔링.

CCAR / DFAST / 금감원 스트레스테스트 운영기준이 요구하는 시나리오 설계서의
핵심은 "거시 변수의 path"와 "narrative"다.  이 모듈은 BASELINE / ADVERSE /
SEVERELY_ADVERSE 세 시나리오에 대해

  - GDP 성장률
  - 실업률
  - 주택가격지수(HPI)
  - 정책금리
  - 회사채 spread (BBB)
  - KOSPI
  - 원/달러 환율

를 1Y / 2Y / 3Y 시점별 가정값으로 제시한다.

각 시나리오의 narrative는 BCBS 2018 "Stress testing principles" §5의 "scenario
storytelling" 요건 (단순 충격치 외에 거시 환경 묘사)을 충족한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class MacroPath:
    """3개년 거시변수 경로 — 각 변수의 t=1Y/2Y/3Y 시점 값."""
    scenario: str
    narrative: str
    gdp_growth: list[float]        # YoY 성장률 (%)
    unemployment: list[float]      # 실업률 (%)
    hpi_change: list[float]        # HPI YoY (%)
    policy_rate: list[float]       # 정책금리 (%)
    bbb_spread: list[float]        # BBB 회사채 spread (bp)
    kospi_change: list[float]      # KOSPI YoY (%)
    fx_krw_usd: list[float]        # USD/KRW 변화율 (%)
    peak_year: int                 # 최대 충격 시점 (1, 2, or 3)

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame({
            "지표": ["GDP 성장률(%)", "실업률(%)", "HPI YoY(%)",
                    "정책금리(%)", "BBB spread(bp)", "KOSPI YoY(%)",
                    "USD/KRW 변화율(%)"],
            "1Y": [self.gdp_growth[0], self.unemployment[0], self.hpi_change[0],
                   self.policy_rate[0], self.bbb_spread[0], self.kospi_change[0],
                   self.fx_krw_usd[0]],
            "2Y": [self.gdp_growth[1], self.unemployment[1], self.hpi_change[1],
                   self.policy_rate[1], self.bbb_spread[1], self.kospi_change[1],
                   self.fx_krw_usd[1]],
            "3Y": [self.gdp_growth[2], self.unemployment[2], self.hpi_change[2],
                   self.policy_rate[2], self.bbb_spread[2], self.kospi_change[2],
                   self.fx_krw_usd[2]],
        })

    def peak_shock(self) -> dict[str, float]:
        """가장 심각한 시점의 단일 충격치를 PD/LGD 변환에 사용."""
        i = self.peak_year - 1
        return {
            "gdp_growth": self.gdp_growth[i],
            "unemployment": self.unemployment[i],
            "hpi_change": self.hpi_change[i],
            "bbb_spread": self.bbb_spread[i],
            "kospi_change": self.kospi_change[i],
        }


# ---------------------------------------------------------------- 기본 narrative

BASELINE_PATH = MacroPath(
    scenario="baseline",
    narrative="중립적 거시 — 잠재성장률 부근, 점진적 금리 정상화. "
              "한국은행 중기 전망 (2026~2028) 기준선과 정합.",
    gdp_growth=[2.0, 2.1, 2.2],
    unemployment=[3.0, 3.0, 2.9],
    hpi_change=[1.0, 1.5, 2.0],
    policy_rate=[3.00, 2.75, 2.50],
    bbb_spread=[120, 115, 110],
    kospi_change=[5.0, 5.5, 6.0],
    fx_krw_usd=[0.0, -0.5, -1.0],
    peak_year=1,
)

ADVERSE_PATH = MacroPath(
    scenario="adverse",
    narrative="중대 시나리오 — 글로벌 수요 둔화 + 부동산 PF 부실 재현. "
              "GDP 1Y −1.5%, 실업률 5%대 진입, HPI 두 자릿수 조정. "
              "BCBS 'plausible severe' 수준.",
    gdp_growth=[-1.5, 0.5, 1.8],
    unemployment=[4.5, 5.5, 4.8],
    hpi_change=[-10.0, -5.0, 1.0],
    policy_rate=[2.00, 1.50, 1.75],
    bbb_spread=[280, 220, 160],
    kospi_change=[-20.0, -5.0, 8.0],
    fx_krw_usd=[8.0, 4.0, -2.0],
    peak_year=1,
)

SEVERELY_ADVERSE_PATH = MacroPath(
    scenario="severely_adverse",
    narrative="극단 시나리오 — 글로벌 금융위기(2008/09) 재현 + 코로나 재발. "
              "GDP 누적 −6%, 실업률 6%대, KOSPI 반토막, "
              "USD/KRW 15% 절하. FED CCAR 'severely adverse' 강도와 정합.",
    gdp_growth=[-3.5, -2.5, 1.0],
    unemployment=[5.0, 6.5, 6.2],
    hpi_change=[-18.0, -12.0, -2.0],
    policy_rate=[1.00, 0.50, 0.75],
    bbb_spread=[450, 380, 240],
    kospi_change=[-40.0, -10.0, 12.0],
    fx_krw_usd=[15.0, 8.0, -3.0],
    peak_year=1,
)


DEFAULT_PATHS: list[MacroPath] = [BASELINE_PATH, ADVERSE_PATH, SEVERELY_ADVERSE_PATH]


def macro_table(paths: list[MacroPath] | None = None) -> pd.DataFrame:
    """시나리오 × 연도 × 지표 long-form 테이블 — 보고서 출력용."""
    paths = paths or DEFAULT_PATHS
    rows = []
    for p in paths:
        for i, year in enumerate(["1Y", "2Y", "3Y"]):
            rows.append({
                "scenario": p.scenario,
                "year": year,
                "gdp_growth": p.gdp_growth[i],
                "unemployment": p.unemployment[i],
                "hpi_change": p.hpi_change[i],
                "policy_rate": p.policy_rate[i],
                "bbb_spread": p.bbb_spread[i],
                "kospi_change": p.kospi_change[i],
                "fx_krw_usd": p.fx_krw_usd[i],
            })
    return pd.DataFrame(rows)


def narrative_summary(paths: list[MacroPath] | None = None) -> pd.DataFrame:
    """시나리오별 narrative 요약 (name, story, peak GDP, peak unemployment)."""
    paths = paths or DEFAULT_PATHS
    rows = []
    for p in paths:
        peak = p.peak_shock()
        rows.append({
            "scenario": p.scenario,
            "narrative": p.narrative,
            "peak_year": p.peak_year,
            "peak_gdp": peak["gdp_growth"],
            "peak_unemployment": peak["unemployment"],
            "peak_hpi": peak["hpi_change"],
            "peak_bbb_spread": peak["bbb_spread"],
        })
    return pd.DataFrame(rows)
