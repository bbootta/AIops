"""위기상황분석 산출과정 추적 — 시나리오 × 분기 × 단계.

`run_multi_axis_path`는 결과만 돌려준다. 결과만으로는 "심각 시나리오 CET1
저점이 4.61%"가 **어떻게** 나왔는지 답할 수 없다. 이 모듈은 같은 엔진이 남긴
중간값을 한 행씩 펼친다 —

  거시 → 충격축(14개) → 신용파라미터 → 신용RWA → 시장 → 은행계정금리
       → 운영 → 유동성 → 손익 → 자본 → RWA합계 → 비율 → 판정

각 행은 산식·투입값·산출값·단위·규정 근거를 함께 가진다. 마지막 단계의 값은
경로 결과와 정확히 일치해야 하며, 그 사실을 테스트가 고정한다 — 추적이 결과와
갈라지면 그건 설명이 아니라 두 번째 모형이다.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from risk_lib.stress.axes import AXES
from risk_lib.stress.multi_axis import (
    CS_DURATION_YEARS, IR_DURATION_YEARS, INTEREST_SHARE_OF_REVENUE,
    LCR_INFLOW_CAP, TAX_RATE, StressPoint, run_multi_axis_path,
)

BLOCKS = ("거시", "충격축", "신용파라미터", "신용RWA", "시장", "은행계정금리",
          "운영", "유동성", "손익", "자본", "RWA합계", "비율", "판정")

_RATIOS = (("cet1", "보통주자본"), ("tier1", "기본자본"), ("total", "총자본"))


@dataclass(frozen=True)
class TraceStep:
    scenario: str
    quarter: str
    q_index: int
    seq: int
    block: str
    step: str
    formula: str
    inputs: str
    value: float
    unit: str
    citation: str


def _steps_for(pt: StressPoint) -> list[tuple]:
    """(블록, 단계, 값, 단위, 산식, 투입값, 근거) 목록."""
    v, sh, s = pt.values, pt.shocks, pt.severity
    out: list[tuple] = [
        ("거시", "충격 심도 (severity)", s, "ratio",
         "정점 도달 후 감쇠 경로", f"시나리오={pt.scenario} · 분기 {pt.q_index + 1}",
         "ST-F001 시나리오 경로"),
    ]
    # ---- 충격축: 14개 축이 같은 심도에서 동시에 발동한다
    for a in AXES:
        out.append(("충격축", f"{a.korean} ({a.risk_type})", sh[a.key], a.unit,
                    f"심도 × 단위충격({a.per_severity:g} {a.unit})",
                    f"severity={s:.4f}" + (f" · {a.note}" if a.note else ""),
                    a.citation))

    # ---- 신용 파라미터
    out += [
        ("신용파라미터", "PD (기준, EAD 가중)", v["pd_base"], "ratio",
         "Σ PDᵢ·EADᵢ ÷ Σ EADᵢ", "내부등급법 대상", "CRE36 내부추정 PD"),
        ("신용파라미터", "PD (충격 후)", v["pd_stressed"], "ratio",
         "logit(PD) + 탄력성 × ΔGDP → 로지스틱 역변환 후 max(기준, 위성)",
         f"ΔGDP={sh['gdp']:.4f}", "ST-F002 위성모형"),
        ("신용파라미터", "LGD (기준, EAD 가중)", v["lgd_base"], "ratio",
         "Σ LGDᵢ·EADᵢ ÷ Σ EADᵢ", "—", "CRE36.83"),
        ("신용파라미터", "LGD (충격 후)", v["lgd_stressed"], "ratio",
         "LGD + 경기침체가산 + 담보하락 × (1 − LGD)",
         f"가산={sh['lgd_addon']:.4f} · 담보하락={sh['collateral']:.4f}",
         "CRE36.83 · CRE22.49"),
        ("신용파라미터", "EAD (기준)", v["ead_base"], "KRW",
         "약정 인출 충격 전", "—", "CRE20.94"),
        ("신용파라미터", "EAD 증가배수", v["ead_uplift"], "ratio",
         "1 + 인출률상승 × 미인출비율",
         f"인출률상승={sh['ccf']:.4f}", "CRE20.94 CCF"),
        ("신용파라미터", "EAD (충격 후)", v["ead_stressed"], "KRW",
         "EAD × 증가배수", "—", "CRE20.94"),
        ("신용파라미터", "외부등급 하향 notch", v["rating_notches"], "count",
         "floor(심도 × 단위 notch)", "표준방법 위험가중치 구간 상승",
         "CRE20.4 ECRA"),
    ]
    # ---- 신용 RWA
    out += [
        ("신용RWA", "내부등급법 RWA", v["rwa_irb"], "KRW",
         "충격 PD·LGD·EAD로 위험가중함수 재산출", "상관계수·만기조정 동일",
         "CRE32.2"),
        ("신용RWA", "표준방법 RWA", v["rwa_sa"], "KRW",
         "등급 하향·LTV 상승·EAD 증가 반영 후 재산출",
         f"LTV 배수={1 / max(1e-9, 1 - sh['collateral']):.4f}",
         "CRE20.4 · CRE20.82"),
    ]
    # ---- 시장
    out += [
        ("시장", "금리 포지션 손익", v["pnl_ir"], "KRW",
         "−|순포지션| × Δy × 듀레이션",
         f"Δy={sh['ir_parallel']:.0f}bp · D={IR_DURATION_YEARS}y",
         "MAR21 · 듀레이션 근사"),
        ("시장", "신용스프레드 손익", v["pnl_cs"], "KRW",
         "−보유 신용물 × Δs × 스프레드듀레이션",
         f"Δs={sh['credit_spread']:.0f}bp · D={CS_DURATION_YEARS}y",
         "MAR21.8 CSR"),
        ("시장", "주식 손익", v["pnl_equity"], "KRW",
         "−|순포지션| × 주가하락률", f"하락률={sh['equity']:.2%}",
         "MAR21.71"),
        ("시장", "외환 손익", v["pnl_fx"], "KRW",
         "−|순포지션| × 환율변동률", f"변동률={sh['fx']:.2%}", "MAR21.81"),
        ("시장", "트레이딩 손익 합계", v["trading_pnl"], "KRW",
         "금리 + 스프레드 + 주식 + 외환", "—", "MAR21"),
        ("시장", "시장리스크 RWA", v["rwa_market"], "KRW",
         "위험계수에 스트레스 배수 적용 후 SSA 재산출",
         "완전 SBM 재산출은 범위 외", "MAR40"),
    ]
    # ---- 은행계정 금리
    out += [
        ("은행계정금리", "ΔEVE", v["delta_eve"], "KRW",
         "−Σ 갭ᵢ × 만기중앙값ᵢ × Δy",
         f"Δy={sh['ir_parallel']:.0f}bp · 재설정 사다리 {len(_RATIOS) and ''}",
         "SRP31.90 평행충격"),
        ("은행계정금리", "ΔNII (1년)", v["delta_nii"], "KRW",
         "Σ_{만기≤1y} 갭ᵢ × Δy", "1년 이내 재설정 갭", "SRP31.34"),
    ]
    # ---- 운영
    out += [
        ("운영", "운영손실 (연간)", v["op_loss_annual"], "KRW",
         "기준 손실 × (1 + 손실증가율)",
         f"증가율={sh['op_loss']:.1%}", "OPE25.20"),
        ("운영", "내부손실승수 (ILM)", v["op_ilm"], "ratio",
         "ln(e−1 + (LC/BIC)^0.8) — 충격 손실로 재산출",
         "10년 평균손실 기준", "OPE25.9"),
        ("운영", "운영리스크 RWA", v["rwa_op"], "KRW", "BIC × ILM × 12.5",
         "BI 불변 — 손실만 충격", "OPE25.2"),
    ]
    # ---- 유동성
    out += [
        ("유동성", "고유동성자산 (haircut 후)", v["hqla"], "KRW",
         "(L1 + 0.85×L2A + 0.50×L2B) × (1 − 추가하락)",
         f"추가하락={sh['hqla_haircut']:.2%}", "LCR30"),
        ("유동성", "총 현금유출", v["lcr_outflow"], "KRW",
         "Σ 잔액 × min(1, 이탈률 + 가산)",
         f"이탈률 가산={sh['deposit_runoff']:.2%}", "LCR40"),
        ("유동성", "순현금유출", v["lcr_net_outflow"], "KRW",
         f"총유출 − min(유입, 총유출 × {LCR_INFLOW_CAP:.0%})", "—",
         "LCR40.61"),
        ("유동성", "유동성커버리지비율", v["lcr"], "ratio",
         "HQLA ÷ 순현금유출", "—", "LCR20.1"),
        ("유동성", "LCR 기준 충족", v["lcr_passes"], "count",
         "1 = 100% 이상", "—", "은행업감독규정 제26조"),
    ]
    # ---- 손익
    out += [
        ("손익", "이자수익", v["interest_income"], "KRW",
         f"영업수익 × {INTEREST_SHARE_OF_REVENUE:.0%} × (1 − 이익축소율)",
         f"축소율={sh['nii']:.1%}", "SRP20 수익 스트레스"),
        ("손익", "수수료수익", v["fee_income"], "KRW",
         f"영업수익 × {1 - INTEREST_SHARE_OF_REVENUE:.0%} × (1 − 감소율)",
         f"감소율={sh['fee']:.1%}", "SRP20"),
        ("손익", "영업비용", -v["operating_cost"], "KRW",
         "충격 대상 아님 — 비용 절감 가정을 넣지 않는다", "보수적 가정",
         "SRP20"),
        ("손익", "충당금 전입", -v["provision"], "KRW",
         "max(0, 충격 ECL − 기준 ECL)", "잔액 전액 전입은 이중계상",
         "IFRS 9 5.5 · ST-F003"),
        ("손익", "운영손실", -v["op_loss_annual"], "KRW", "충격 후 연간 손실",
         "—", "OPE25.20"),
        ("손익", "트레이딩 손익", v["trading_pnl"], "KRW", "시장 블록 합계",
         "—", "MAR21"),
        ("손익", "법인세차감전순이익", v["pre_tax_income"], "KRW",
         "이자 + 수수료 − 비용 − 충당금 − 운영손실 + 트레이딩", "—",
         "SRP20 수익 스트레스"),
        ("손익", "법인세비용", v["tax"], "KRW",
         f"−max(0, 세전이익) × {TAX_RATE:.1%}", "손실에 환급을 잡지 않는다",
         "보수적 가정"),
        ("손익", "당기순이익", v["net_income"], "KRW", "세전이익 + 법인세비용",
         "—", "SRP20"),
        ("손익", "이익 변화 (기준 대비)", v["earnings_delta"], "KRW",
         "충격 순이익 − 기준 순이익", "자본 롤포워드의 유일한 입력",
         "ST-F004"),
    ]
    # ---- 자본
    out += [
        ("자본", "보통주자본 (기준)", v["cet1_base"], "KRW", "CRE40 가산 − 차감",
         "—", "CRE40.1~40.26"),
        ("자본", "보통주자본 (충격 후)", v["cet1"], "KRW",
         "기준 CET1 + 이익 변화",
         "충당금이 이익에 있으므로 ECL을 따로 빼지 않는다", "ST-F004"),
        ("자본", "기타기본자본", v["at1"], "KRW", "손익에 연동되지 않는다", "—",
         "CRE40.27"),
        ("자본", "보완자본", v["tier2"], "KRW", "—", "—", "CRE40.42"),
        ("자본", "자기자본 합계", v["capital_total"], "KRW",
         "CET1(충격) + AT1 + T2", "—", "CRE40"),
    ]
    # ---- RWA 합계
    out += [
        ("RWA합계", "내부모형 RWA", v["rwa_internal"], "KRW",
         "IRB + SA + 시장 + 운영 (모두 충격 후)", "—", "CRE20.1"),
        ("RWA합계", "표준방법 RWA (하한 분모)", v["rwa_standardised"], "KRW",
         "전 포트폴리오를 충격 후 표준방법으로 재산출", "등급·LTV·EAD 충격 반영",
         "RBC30.1"),
        ("RWA합계", "산출하한 증가분", v["floor_addon"], "KRW",
         "max(0, 표준방법 × 하한율 − 내부모형)", "—", "RBC20.11"),
        ("RWA합계", "하한 구속 여부", v["floor_binding"], "count",
         "1 = 구속", "—", "RBC20.11"),
        ("RWA합계", "위험가중자산 합계", v["rwa_total"], "KRW",
         "max(내부모형, 표준방법 × 하한율)", "—", "CRE20.1 · RBC20.11"),
    ]
    # ---- 비율
    for key, label in _RATIOS:
        out.append(("비율", f"{label}비율", v[f"{key}_ratio"], "ratio",
                    f"{label} ÷ 위험가중자산", "—", "은행업감독규정 제26조"))
    # ---- 판정
    for key, label in _RATIOS:
        out.append(("판정", f"{label} 요구비율", v[f"{key}_required"], "ratio",
                    "최저기준 + 완충자본", "제26조 + 제26조의2~4",
                    "은행업감독규정 제26조의2"))
        out.append(("판정", f"{label} 잉여(+)·부족(−)", v[f"{key}_surplus"],
                    "ratio", "실측 − 요구", "음수면 침범", "ST-F006"))
    out += [
        ("판정", "제약 비율", v["binding_index"], "count",
         "0=보통주 1=기본 2=총자본", "여유가 가장 얇은 비율", "ST-F006"),
        ("판정", "요구치 충족", v["passes"], "count",
         "세 비율 모두 충족 시 1", "—", "ST-F006"),
    ]
    return out


def build_trace(points: list[StressPoint]) -> pd.DataFrame:
    """엔진이 남긴 중간값을 단계별 행으로 펼친다."""
    rows: list[TraceStep] = []
    for pt in points:
        for seq, (block, step, value, unit, formula, inputs, citation) in \
                enumerate(_steps_for(pt), start=1):
            rows.append(TraceStep(
                scenario=pt.scenario, quarter=pt.quarter, q_index=pt.q_index,
                seq=seq, block=block, step=step, formula=formula,
                inputs=inputs, value=float(value), unit=unit,
                citation=citation))
    return pd.DataFrame([r.__dict__ for r in rows])


def trace_from_result(result, portfolio: pd.DataFrame) -> pd.DataFrame:
    """PipelineResult에서 추적표를 만든다 — 파이프라인과 같은 입력을 재구성한다."""
    from risk_lib.datamodel.materialize import fitted_portfolio
    from risk_lib.pipeline import _stage_split_books, _stress_books

    fitted = fitted_portfolio(portfolio)
    sa_book, irb_book = _stage_split_books(fitted)
    books = _stress_books(
        fitted, irb_book, sa_book, result.meta["capital"],
        result.rwa["market_positions"], result.rwa["bi_detail"],
        result.rwa["op_detail"], result.op_loss, result.alm,
        float(fitted["ead"].sum()))
    _path, points = run_multi_axis_path(
        books, quarters=list(result.meta.get("quarters", [])),
        buffers={"capital_conservation": 0.025, "countercyclical": 0.0,
                 "dsib": 0.01})
    return build_trace(points)
