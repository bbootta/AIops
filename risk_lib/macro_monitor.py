"""거시·금융지표 모니터링 — 통합위기상황분석 시나리오의 입력 원장.

## 왜 필요한가

시나리오 심도(`gdp_path`·`severity`)는 지금까지 코드 상수였다. 그 숫자가 어느
통계에서 나왔는지 원장이 없으면 감독당국·검증팀의 "왜 그 심도인가"에 답할 수
없다. 시나리오는 근거 없는 숫자 묶음이 되고, 재현은 되지만 정당화는 안 된다.

## 값은 아직 합성이다 — 그렇게 말한다

외부 통계 API를 붙이지 않았다. 그러므로 이 모듈이 만드는 관측치는 **전건
`basis="파생"`** 이고, 실측이라고 말하지 않는다. 대신 출처 기관과 통계표·계열
코드를 원장 컬럼으로 박는다:

- 한국은행 ECOS 통계표코드 (예: `200Y001` 국민계정, `722Y001` 시장금리)
- 통계청 KOSIS 표ID (예: `DT_1DA7001S` 소비자물가)

코드가 원장에 있으므로 실 피드가 생기면 **이 모듈만 갈아끼우면** 되고, 어느
계열을 어디에 꽂아야 하는지 다시 조사할 필요가 없다. 값이 실측으로 바뀌는
순간 `basis`가 `실측`이 되고 화면·서식이 그것을 그대로 표시한다.

생성은 `(asof, seed)` 고정이다 — 같은 기준일·시드면 같은 계열이 나온다.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class IndicatorSpec:
    """지표 하나의 정의. `code`는 실제 공표 계열을 가리킨다."""
    indicator_id: str
    name: str
    category: str
    source: str
    code: str
    unit: str
    freq: str
    level: float          # 최근 수준 (합성 기준점)
    vol: float            # 분기 변동성
    drives: str           # 이 지표가 스트레스 축 중 무엇을 움직이는가


# 통합위기상황분석이 쓰는 축을 덮는 최소 집합. 축마다 최소 1개 지표가 있어야
# 시나리오 가정이 관측치에 걸린다.
INDICATORS: tuple[IndicatorSpec, ...] = (
    IndicatorSpec("GDP_YOY", "실질 GDP 성장률", "성장", "한국은행", "200Y001",
                  "%", "분기", 2.0, 1.1, "PD 시스템요인 (z)"),
    IndicatorSpec("CPI_YOY", "소비자물가 상승률", "물가", "통계청", "DT_1DA7001S",
                  "%", "월", 2.3, 0.7, "정책금리 경로"),
    IndicatorSpec("BASE_RATE", "한국은행 기준금리", "금리", "한국은행", "722Y001",
                  "%", "월", 3.0, 0.4, "IRRBB 금리충격"),
    IndicatorSpec("KTB3Y", "국고채 3년 금리", "금리", "한국은행", "817Y002",
                  "%", "월", 3.2, 0.5, "IRRBB · 시장 VaR"),
    IndicatorSpec("USDKRW", "원/달러 환율", "환율", "한국은행", "731Y001",
                  "원", "월", 1340.0, 55.0, "외화 익스포저 · 시장 VaR"),
    IndicatorSpec("UNEMP", "실업률", "고용", "통계청", "DT_1DA7104S",
                  "%", "월", 3.0, 0.4, "리테일 PD"),
    IndicatorSpec("HH_DEBT_GDP", "가계부채/GDP", "가계부채", "한국은행", "151Y005",
                  "%", "분기", 92.0, 2.0, "리테일 LGD · 담보"),
    IndicatorSpec("HOUSE_PRICE", "주택매매가격지수", "부동산", "한국은행", "901Y062",
                  "지수", "월", 100.0, 3.5, "주담대 LGD (담보가치)"),
    IndicatorSpec("KOSPI", "KOSPI", "금융시장", "한국은행", "802Y001",
                  "지수", "월", 2600.0, 190.0, "시장 VaR · 지분증권"),
    IndicatorSpec("CDS_5Y", "국가 CDS 프리미엄 5년", "대외", "한국은행", "902Y001",
                  "bp", "월", 35.0, 9.0, "조달 스프레드 · 유동성"),
    IndicatorSpec("BANK_NPL", "국내은행 고정이하여신비율", "가계부채",
                  "금융감독원", "FSS-NPL", "%", "분기", 0.45, 0.09,
                  "부도율 벤치마크"),
    IndicatorSpec("TERM_SPREAD", "장단기 금리차 (10y−3y)", "금리", "한국은행",
                  "817Y002", "%p", "월", 0.35, 0.22, "경기 선행 · z 보정"),
)

# 시나리오별 지표 충격 — 축마다 방향과 배수를 명시한다. 배수는 표준편차 단위라
# 지표의 실제 변동성에 비례해 충격이 커진다(수준이 다른 지표를 같은 %로 때리면
# 환율과 실업률이 같은 충격을 받는 셈이 된다).
SCENARIO_SHOCK: dict[str, dict[str, float]] = {
    "baseline":         {},
    "adverse":          {"GDP_YOY": -1.6, "UNEMP": +1.4, "HOUSE_PRICE": -1.5,
                         "KOSPI": -1.5, "CDS_5Y": +1.4, "BANK_NPL": +1.5,
                         "USDKRW": +1.2, "TERM_SPREAD": -1.2},
    "severely_adverse": {"GDP_YOY": -3.2, "UNEMP": +2.8, "HOUSE_PRICE": -3.0,
                         "KOSPI": -3.0, "CDS_5Y": +3.2, "BANK_NPL": +3.4,
                         "USDKRW": +2.6, "TERM_SPREAD": -2.4},
}


def _rng(seed: int, key: str) -> np.random.Generator:
    """지표별 전용 스트림 — 지표를 추가해도 기존 계열이 흔들리지 않는다."""
    off = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) % 100_000
    return np.random.default_rng(seed + off)


def _periods(asof: date, n: int, freq: str) -> list[str]:
    if freq == "분기":
        out, y, q = [], asof.year, (asof.month - 1) // 3 + 1
        for _ in range(n):
            out.append(f"{y}Q{q}")
            q -= 1
            if q == 0:
                q, y = 4, y - 1
        return list(reversed(out))
    out, y, m = [], asof.year, asof.month
    for _ in range(n):
        out.append(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(out))


def observations(asof: date | str, *, seed: int = 42,
                 n_periods: int = 12) -> pd.DataFrame:
    """지표별 관측 계열. `basis`는 전건 '파생'이다 — 외부 피드가 없다."""
    if isinstance(asof, str):
        asof = date.fromisoformat(asof)
    rows = []
    for sp in INDICATORS:
        g = _rng(seed, sp.indicator_id)
        # 평균회귀 경로 — 난수 걷기로 두면 마지막 값이 수준에서 멀어져
        # "최근 관측치"라는 이름이 무의미해진다.
        vals, v = [], sp.level
        for _ in range(n_periods):
            v = v + 0.45 * (sp.level - v) + g.normal(0, sp.vol * 0.5)
            vals.append(v)
        pers = _periods(asof, n_periods, sp.freq)
        for i, (p, v) in enumerate(zip(pers, vals)):
            prior = vals[i - 4] if i >= 4 else None
            rows.append({
                "indicator_id": sp.indicator_id, "name": sp.name,
                "category": sp.category, "source": sp.source,
                "source_code": sp.code, "period": p, "freq": sp.freq,
                "value": round(float(v), 4), "unit": sp.unit,
                "yoy": (None if prior in (None, 0) else
                        round(float(v / prior - 1), 6)),
                "basis": "파생",
            })
    return pd.DataFrame(rows)


def scenario_links(obs: pd.DataFrame) -> pd.DataFrame:
    """시나리오 가정이 어느 지표의 어떤 값에서 나왔는지 남긴다."""
    latest = (obs.sort_values("period").groupby("indicator_id").tail(1)
              .set_index("indicator_id"))
    by_id = {s.indicator_id: s for s in INDICATORS}
    rows = []
    for scen, shocks in SCENARIO_SHOCK.items():
        for sp in INDICATORS:
            if sp.indicator_id not in latest.index:
                continue
            base = float(latest.loc[sp.indicator_id, "value"])
            k = shocks.get(sp.indicator_id, 0.0)
            val = base + k * by_id[sp.indicator_id].vol
            rows.append({
                "scenario": scen, "indicator_id": sp.indicator_id,
                "name": sp.name, "latest": round(base, 4),
                "scenario_value": round(float(val), 4),
                "shock": round(float(val - base), 4), "drives": sp.drives,
            })
    return pd.DataFrame(rows)


def alerts(obs: pd.DataFrame, *, z_threshold: float = 1.5) -> list[dict]:
    """최근 관측이 자기 계열의 평소 범위를 벗어난 지표.

    임계는 계열 자신의 표준편차로 잡는다 — 지표마다 수준·단위가 달라 절대값
    임계를 두면 환율만 계속 걸린다.
    """
    out = []
    for iid, g in obs.groupby("indicator_id"):
        g = g.sort_values("period")
        v = g["value"].to_numpy()
        if len(v) < 4:
            continue
        mu, sd = float(v[:-1].mean()), float(v[:-1].std(ddof=1))
        if sd <= 0:
            continue
        z = (float(v[-1]) - mu) / sd
        if abs(z) >= z_threshold:
            r = g.iloc[-1]
            out.append({
                "indicator_id": iid, "name": str(r["name"]),
                "category": str(r["category"]), "period": str(r["period"]),
                "value": float(r["value"]), "unit": str(r["unit"]),
                "z": round(z, 2), "drives": by_id_drives(iid),
            })
    return sorted(out, key=lambda x: -abs(x["z"]))


def by_id_drives(indicator_id: str) -> str:
    for s in INDICATORS:
        if s.indicator_id == indicator_id:
            return s.drives
    return ""
