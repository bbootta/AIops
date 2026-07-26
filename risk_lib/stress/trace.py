"""위기상황분석 산출과정 추적 — 시나리오 × 분기 × 단계.

`run_stress_path`는 결과만 돌려준다. 결과만으로는 "심각 시나리오 CET1 저점이
8.19%"가 **어떻게** 나왔는지 답할 수 없다. 이 모듈은 같은 계산을 같은 함수로
다시 밟으면서 **모든 중간값**을 한 행씩 남긴다 —

  거시 → 위험파라미터 → 손실 → 손익 → RWA → 자본 → 비율 → 판정

각 행은 산식·투입값·산출값·단위·규정 근거를 함께 가진다. 마지막 단계의 값은
`run_stress_path`가 낸 값과 정확히 일치해야 하며, 그 사실을 테스트가 고정한다.
추적이 결과와 갈라지면 그건 추적이 아니라 두 번째 모형이다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from risk_lib.capital.bis import CapitalStack, compute_bis_ratios
from risk_lib.capital.rwa_irb import compute_rwa_irb
from risk_lib.provisioning.ecl import compute_ecl
from risk_lib.stress.path import DEFAULT_STRESS_PATHS
from risk_lib.stress.scenario import StressAxis, apply_scenario

# 단계 블록 — 화면의 드릴다운 순서이자 감독당국 설명 순서다.
BLOCKS = ("거시", "위험파라미터", "손실", "손익", "RWA", "자본", "비율", "판정")


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
    unit: str                 # KRW · ratio · count · years
    citation: str


def _w(values: np.ndarray, weights: np.ndarray) -> float:
    tot = float(weights.sum())
    return float((values * weights).sum() / tot) if tot else 0.0


def build_stress_trace(
    irb_portfolio: pd.DataFrame,
    capital: CapitalStack,
    rwa_other: float,
    *,
    quarters: list[str],
    rwa_market: float,
    rwa_op: float,
    rwa_sa: float,
    paths=None,
    axis: StressAxis | None = None,
    buffers: dict[str, float] | None = None,
    eir: float = 0.05,
) -> pd.DataFrame:
    """시나리오 × 분기별 전 단계 추적표.

    `rwa_other`는 run_stress_path에 넘긴 것과 **같은 값**이어야 한다(SA + 시장 +
    운영). 셋으로 쪼갠 인자는 화면에서 구성을 보여주기 위한 것이며, 합계가
    rwa_other와 어긋나면 즉시 예외를 던진다 — 조용히 다른 총계를 그리면
    스트레스 결과가 두 벌이 된다.
    """
    if paths is None:
        paths = DEFAULT_STRESS_PATHS
    if axis is None:
        axis = StressAxis()
    parts = rwa_sa + rwa_market + rwa_op
    if abs(parts - rwa_other) > max(1.0, abs(rwa_other) * 1e-9):
        raise ValueError(
            f"rwa_other({rwa_other:,.0f}) ≠ SA+시장+운영({parts:,.0f}) — "
            "추적표와 스트레스 결과의 RWA 총계가 갈라진다")

    base_ecl = float(compute_ecl(irb_portfolio, eir=eir)["ecl"].sum())
    ead = irb_portfolio["ead"].to_numpy(dtype=float)
    pd_base = _w(irb_portfolio["pd"].to_numpy(dtype=float), ead)
    lgd_base = _w(irb_portfolio["lgd"].to_numpy(dtype=float), ead)
    ead_total = float(ead.sum())
    base_irb_rwa = float(compute_rwa_irb(irb_portfolio)["rwa"].sum())

    n = len(quarters)
    rows: list[TraceStep] = []
    for path in paths:
        for i, (qlabel, s) in enumerate(zip(quarters, path.severities(n))):
            sc = axis.scenario_at(s)
            stressed = apply_scenario(irb_portfolio, sc)
            pd_str = _w(stressed["pd"].to_numpy(dtype=float), ead)
            lgd_str = _w(stressed["lgd"].to_numpy(dtype=float), ead)
            rwa_irb = float(compute_rwa_irb(stressed)["rwa"].sum())
            ecl = float(compute_ecl(stressed, eir=eir)["ecl"].sum())
            inc_ecl = max(ecl - base_ecl, 0.0)
            rwa_total = rwa_irb + rwa_other
            cet1 = capital.cet1 - inc_ecl
            stack = CapitalStack(cet1=cet1, additional_t1=capital.additional_t1,
                                 tier2=capital.tier2)
            bis = compute_bis_ratios(stack, rwa_total, buffers=buffers)
            surplus = bis.surplus_shortfall
            binding = min(surplus, key=surplus.get)

            seq = 0

            def add(block, step, formula, inputs, value, unit, citation):
                nonlocal seq
                seq += 1
                rows.append(TraceStep(path.name, qlabel, i, seq, block, step,
                                      formula, inputs, float(value), unit,
                                      citation))

            # ---- 1. 거시
            add("거시", "충격 심도 (severity)", "정점 도달 후 감쇠 경로",
                f"경로={path.name} · 분기 {i + 1}/{n}", s, "ratio",
                "ST-F001 시나리오 경로")
            add("거시", "GDP 성장률 충격", "ΔGDP = −severity × 단위충격",
                f"severity={s:.4f} × {axis.gdp_per_unit}", sc.gdp_shock, "ratio",
                "SRP20 거시 시나리오")
            add("거시", "LGD 가산", "ΔLGD = severity × 단위가산",
                f"severity={s:.4f} × {axis.lgd_addon_per_unit}", sc.lgd_addon,
                "ratio", "CRE36.83 경기침체 LGD")

            # ---- 2. 위험파라미터
            add("위험파라미터", "PD (기준, EAD 가중)", "Σ PDᵢ·EADᵢ ÷ Σ EADᵢ",
                f"익스포저 {len(irb_portfolio):,}건", pd_base, "ratio",
                "CRE36 내부추정 PD")
            add("위험파라미터", "PD (충격 후)",
                "logit(PD) + 탄력성 × ΔGDP → 로지스틱 역변환 후 max(기준, 위성)",
                f"탄력성={sc.pd_gdp_elasticity} · ΔGDP={sc.gdp_shock:.4f}",
                pd_str, "ratio", "ST-F002 위성모형")
            add("위험파라미터", "LGD (기준, EAD 가중)", "Σ LGDᵢ·EADᵢ ÷ Σ EADᵢ",
                "—", lgd_base, "ratio", "CRE36.83")
            add("위험파라미터", "LGD (충격 후)", "min(1, LGD + ΔLGD)",
                f"ΔLGD={sc.lgd_addon:.4f}", lgd_str, "ratio", "CRE36.83")
            add("위험파라미터", "EAD (불변)",
                "본 시나리오 축은 EAD를 충격하지 않는다",
                "한도 인출 충격을 넣으려면 CCF 축을 추가해야 한다", ead_total,
                "KRW", "CRE20.94 CCF")

            # ---- 3. 손실
            add("손실", "기대신용손실 (기준)", "Σ PD × LGD × EAD × 할인",
                f"EIR={eir:.2%}", base_ecl, "KRW", "IFRS 9 5.5")
            add("손실", "기대신용손실 (충격 후)", "충격 PD·LGD로 재산출",
                f"PD {pd_base:.4%}→{pd_str:.4%} · LGD {lgd_base:.2%}→{lgd_str:.2%}",
                ecl, "KRW", "IFRS 9 5.5 · B5.5.42")
            add("손실", "증분 ECL", "max(0, 충격 ECL − 기준 ECL)",
                f"{ecl:,.0f} − {base_ecl:,.0f}", inc_ecl, "KRW",
                "ST-F003 손익 반영")

            # ---- 4. 손익
            add("손익", "충당금 전입 (손익 차감)", "증분 ECL 전액을 당기손익에 반영",
                "세효과·이익유보는 보수적으로 인식하지 않는다", -inc_ecl, "KRW",
                "SRP20 — 보수적 손익 가정")
            add("손익", "시장·운영 손익 (본 축 불변)",
                "본 시나리오 축은 신용 파라미터만 충격한다",
                "시장·운영 충격은 별도 축(MAR·OPE)에서 다룬다", 0.0, "KRW",
                "SRP20 다축 시나리오")

            # ---- 5. RWA
            add("RWA", "신용 IRB (기준)", "CRE32 위험가중함수", "—",
                base_irb_rwa, "KRW", "CRE32.2")
            add("RWA", "신용 IRB (충격 후)", "충격 PD·LGD로 위험가중함수 재산출",
                f"상관계수·만기조정 동일", rwa_irb, "KRW", "CRE32.2")
            add("RWA", "신용 표준방법 (불변)", "SA 자산군은 등급 기반이라 불변",
                "등급 하향 시나리오를 넣으려면 등급전이 축이 필요하다", rwa_sa,
                "KRW", "CRE20")
            add("RWA", "시장리스크 (불변)", "MAR40 간편표준방법", "—", rwa_market,
                "KRW", "MAR40")
            add("RWA", "운영리스크 (불변)", "OPE25 BIC × ILM", "—", rwa_op,
                "KRW", "OPE25")
            add("RWA", "위험가중자산 합계", "IRB(충격) + SA + 시장 + 운영",
                f"{rwa_irb:,.0f} + {rwa_sa:,.0f} + {rwa_market:,.0f} + {rwa_op:,.0f}",
                rwa_total, "KRW", "CRE20.1")

            # ---- 6. 자본
            add("자본", "보통주자본 (기준)", "CRE40 가산 − 차감", "—",
                capital.cet1, "KRW", "CRE40.1~40.26")
            add("자본", "보통주자본 (충격 후)", "기준 CET1 − 증분 ECL",
                f"{capital.cet1:,.0f} − {inc_ecl:,.0f}", cet1, "KRW",
                "ST-F004 CET1 roll-forward")
            add("자본", "기타기본자본 (불변)", "AT1은 손익에 연동되지 않는다", "—",
                capital.additional_t1, "KRW", "CRE40.27")
            add("자본", "보완자본 (불변)", "Tier 2", "—", capital.tier2, "KRW",
                "CRE40.42")
            add("자본", "자기자본 합계", "CET1(충격) + AT1 + T2", "—",
                stack.total, "KRW", "CRE40")

            # ---- 7. 비율
            add("비율", "보통주자본비율", "CET1(충격) ÷ RWA(충격)",
                f"{cet1:,.0f} ÷ {rwa_total:,.0f}", bis.cet1_ratio, "ratio",
                "은행업감독규정 제26조")
            add("비율", "기본자본비율", "Tier1 ÷ RWA", "—", bis.tier1_ratio,
                "ratio", "은행업감독규정 제26조")
            add("비율", "총자본비율", "자기자본 ÷ RWA", "—", bis.total_ratio,
                "ratio", "은행업감독규정 제26조")

            # ---- 8. 판정
            for key, label in (("cet1", "보통주자본"), ("tier1", "기본자본"),
                               ("total", "총자본")):
                add("판정", f"{label} 요구비율", "최저기준 + 완충자본",
                    "제26조 + 제26조의2~4", bis.required[key], "ratio",
                    "은행업감독규정 제26조의2")
                add("판정", f"{label} 잉여(+)·부족(−)", "실측 − 요구",
                    "음수면 침범", surplus[key], "ratio", "ST-F006")
            add("판정", "제약 비율", "여유가 가장 얇은 비율",
                f"binding={binding}", float(("cet1", "tier1", "total").index(binding)),
                "count", "ST-F006 — 어느 요구치를 침범했는지 명시")
            add("판정", "요구치 충족", "세 비율 모두 충족 시 1", "—",
                1.0 if bis.passes() else 0.0, "count", "ST-F006")

    return pd.DataFrame([s.__dict__ for s in rows])


def trace_from_result(result, portfolio: pd.DataFrame) -> pd.DataFrame:
    """PipelineResult에서 추적표를 만든다 — 파이프라인과 같은 입력을 재구성한다."""
    from risk_lib.pipeline import _stage_split_books
    from risk_lib.datamodel.materialize import fitted_portfolio

    fitted = fitted_portfolio(portfolio)
    _, irb_book = _stage_split_books(fitted)
    rwa = result.rwa
    rwa_other = float(rwa["sa"]) + float(rwa["market"]) + float(rwa["op"])
    return build_stress_trace(
        irb_book, result.meta["capital"], rwa_other,
        quarters=list(result.meta.get("quarters", [])),
        rwa_sa=float(rwa["sa"]), rwa_market=float(rwa["market"]),
        rwa_op=float(rwa["op"]),
        buffers={"capital_conservation": 0.025, "countercyclical": 0.0,
                 "dsib": 0.01},
    )
