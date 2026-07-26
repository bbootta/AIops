"""위기상황분석 충격 축 정의 — 전 리스크 유형.

신용 파라미터만 충격하는 스트레스는 "신용 스트레스"이지 통합위기상황분석이
아니다. 금리가 오르고 스프레드가 벌어지고 예금이 빠지고 수수료가 줄어드는
동시성이 빠지면 자본 저점이 낙관적으로 나온다.

각 축은 **단위 심도(severity 1.0)당 충격 크기**로 정의된다. 시나리오 경로가
분기별 심도를 주면 모든 축이 그 심도에서 동시에 발동한다 — 축마다 다른 경로를
쓰면 어느 분기가 최악인지 말할 수 없다.

크기는 감독 스트레스 시나리오(EBA/CCAR·금감원 통합위기상황분석) 관행 수준의
**내부 관리값**이며 기관 승인 시나리오로 교체가 전제다.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

RISK_TYPES = ("신용", "시장", "운영", "유동성", "수익")


@dataclass(frozen=True)
class ShockAxis:
    key: str
    korean: str
    risk_type: str
    unit: str                 # ratio · bp · multiple · notch
    per_severity: float       # 심도 1.0당 충격 크기
    citation: str
    note: str = ""

    def at(self, severity: float) -> float:
        return float(severity) * self.per_severity


AXES: tuple[ShockAxis, ...] = (
    # ---- 신용
    ShockAxis("gdp", "GDP 성장률 충격", "신용", "ratio", -0.030,
              "SRP20 거시 시나리오",
              "위성모형을 통해 PD로 전이된다 (logit shift)"),
    ShockAxis("lgd_addon", "LGD 경기침체 가산", "신용", "ratio", 0.050,
              "CRE36.83 downturn LGD"),
    ShockAxis("collateral", "담보가치 하락", "신용", "ratio", 0.060,
              "CRE22.49 · 주택가격 충격",
              "LTV 상승(SA 주담대 위험가중치)과 LGD 상승 양쪽으로 전이"),
    ShockAxis("ccf", "미인출 약정 인출률 상승", "신용", "ratio", 0.150,
              "CRE20.94 CCF", "미인출 잔액에만 적용된다"),
    ShockAxis("migration", "외부등급 하향", "신용", "notch", 0.500,
              "CRE20.4 ECRA", "표준방법 위험가중치 구간이 올라간다"),
    # ---- 시장
    ShockAxis("ir_parallel", "금리 평행상승", "시장", "bp", 60.0,
              "MAR21 · SRP31 금리충격",
              "트레이딩북 손익과 은행계정 ΔEVE·ΔNII 양쪽에 전이"),
    ShockAxis("credit_spread", "신용스프레드 확대", "시장", "bp", 80.0,
              "MAR21.8 CSR", "보유 신용물(HQLA L2A·L2B) 평가손"),
    ShockAxis("equity", "주가 하락", "시장", "ratio", 0.120,
              "MAR21.71 주식리스크"),
    ShockAxis("fx", "환율 변동", "시장", "ratio", 0.080,
              "MAR21.81 외환리스크", "순포지션에 불리한 방향으로 적용"),
    # ---- 운영
    ShockAxis("op_loss", "운영손실 증가", "운영", "multiple", 0.350,
              "OPE25.9 내부손실승수",
              "손실 증가가 ILM을 통해 운영리스크 자본으로 되돌아온다"),
    # ---- 유동성
    ShockAxis("deposit_runoff", "예금 이탈률 가산", "유동성", "ratio", 0.050,
              "LCR40 이탈률"),
    ShockAxis("hqla_haircut", "고유동성자산 가치 하락", "유동성", "ratio", 0.040,
              "LCR30 haircut"),
    # ---- 수익
    ShockAxis("nii", "순이자이익 축소", "수익", "ratio", 0.150,
              "SRP20 수익 스트레스"),
    ShockAxis("fee", "수수료수익 감소", "수익", "ratio", 0.200,
              "SRP20 수익 스트레스"),
)

AXES_BY_KEY = {a.key: a for a in AXES}


def shocks_at(severity: float) -> dict[str, float]:
    """심도 → 축별 충격 크기. 모든 축이 같은 심도에서 동시에 발동한다."""
    return {a.key: a.at(severity) for a in AXES}


def axis_frame(severity: float = 1.0) -> pd.DataFrame:
    """축 카탈로그 — 화면·서식이 '무엇을 충격했는가'를 보여줄 때 쓴다."""
    return pd.DataFrame([{
        "key": a.key, "korean": a.korean, "risk_type": a.risk_type,
        "unit": a.unit, "per_severity": a.per_severity,
        "magnitude": a.at(severity), "citation": a.citation, "note": a.note,
    } for a in AXES])
