"""행동모형 — 계약현금흐름을 행동조정 현금흐름으로 바꾸는 3종.

BCBS/EBA 표준방법이 인정하는 행동적 현금흐름은 **3종뿐**이다. 인터페이스를
이 3종으로 고정하는 것이 규제 대응상 정확하다 (EBA/RTS/2022/09;
BCBS d368 Annex 2).

  비만기예금(NMD)   계약: 전액 최단 버킷 → 행동: 코어를 상한 내 선형 슬로팅
  고정금리대출      계약: 상환스케줄     → 행동: SMM 적용, SIFMA 순서
  정기예금          계약: 만기 일시      → 행동: TDRR 적용

NMD가 계약/행동 두 원장을 분리해야 하는 이유를 가장 선명하게 보여준다.
계약 기준이면 전액 O/N(듀레이션 ≈ 0), 행동 기준이면 4~5년에 퍼진다 —
**ΔEVE가 자릿수로 갈린다.** 감독당국이 비교하는 것이 정확히 이 차이인데,
현행 저장소는 둘 중 어느 쪽도 산출하지 않으면서 `balance_sheet.py:89-92`
주석과 서식 각주에 "행태만기로 슬로팅되어 있다"고 **감독당국 제출문서에**
적고 있다.

**파라미터는 한 개도 이 모듈에 없다.** 전부 `params.build_*`가 만든 원장에서
온다. 원장 칸이 비어 있으면(`NULL`) 조정을 **건너뛰고** `ParamWarning`을
남긴다 — 조용히 1.0이나 0.8을 쓰지 않는다. 비어 있음이 산출물에 보이는 것이
목적이다.

공식 출처
  SMM ↔ CPR      SMM = 1 − (1 − CPR)^τ  (τ = 기간 연수; 월이면 1/12)
                 **정확식이며 선형근사 CPR/12를 쓰지 않는다** — CPR 6%에서
                 근사는 SMM을 약 3% 과대계상하고 그 오차가 만기까지 복리된다.
                 (cbonds / AnalystPrep — SMM-CPR conversion)
  PSA 100%       CPR(m) = min(0.06, 0.002·m), m = 상품연령(월)
                 (SIFMA Standard Formulas — PSA prepayment model)
  SIFMA 순서     PP_k = SMM_k·(B_{k−1} − SP_k);  B_k = B_{k−1} − SP_k − PP_k
                 순서를 바꿔 SP를 빼기 전에 SMM을 걸면 조기상환액이 과대계상된다.
  시나리오 승수   CPR_i = min(1, γ_i·CPR₀);  TDRR_i = min(1, u_i·TDRR₀)
                 (BCBS d368 Annex 2 Table 3·4)
  S-curve        RI(x) = a + b·arctan(c·(x − d))  (Richard & Roll 1989)
                 함수형만 공표 확인 · 계수 미확인 → 원장에서 받고 기본 미사용

알려진 한계 (설계 §5)
  · 국내 조기상환은 금리갭 2%p 초과에서 오히려 하락하는 **단봉형**으로 보고된다.
    단조 arctan을 이식하면 고금리갭 구간을 과대추정한다(§5.19).
  · burnout은 과거 인센티브 **경로**에 의존하므로 단일 시점 산출로 표현할 수
    없다 — 상태변수를 들고 다녀야 한다. 미구현(§5.20).
  · NMD 선형 슬로팅의 상한이 **평균만기**인지 **최종만기**인지 EBA 원문
    미확인. 여기서는 평균만기 정합(구간 [0, 2·M̄] 균등)으로 구현하고
    달성 평균만기를 함께 돌려준다 — 이산화 오차가 숨지 않게.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from risk_lib.alm.schedule import Instalment

__all__ = [
    "ParamWarning", "CashflowPoint",
    "smm_from_cpr", "seasoning_ramp", "psa_cpr", "scenario_multiplier",
    "scurve_ri", "effective_prepay_fee_rate", "apply_prepayment",
    "apply_early_redemption", "nmd_slotting",
]


@dataclass(frozen=True)
class ParamWarning:
    """원장 파라미터가 비어 있어 조정을 건너뛴 사실. 산출물에 실려 나간다."""
    model: str
    scope: str                   # 계약·범주 등 어디서 발생했는지
    param: str
    reason: str


@dataclass(frozen=True)
class CashflowPoint:
    """행동조정 후 현금흐름 1점."""
    t_years: float
    principal: float
    interest: float


# ---------------------------------------------------------------- 기본 변환

def smm_from_cpr(cpr: float, period_years: float) -> float:
    """CPR(연율) → 해당 기간의 단일월사망률 상당. SMM = 1 − (1 − CPR)^τ."""
    if not 0.0 <= cpr < 1.0:
        if cpr >= 1.0:
            return 1.0
        raise ValueError(f"CPR은 [0,1) — 받은 값 {cpr}")
    return 1.0 - (1.0 - cpr) ** period_years


def seasoning_ramp(age_months: float, *, ceiling: float, slope: float) -> float:
    """경과효과 램프 CPR(m) = min(ceiling, slope·m). 계수는 **인자로만** 온다.

    PSA는 이 함수형의 계수 한 벌(0.06 · 0.002)이며 유일한 벌이 아니다. 자체추정
    계수(`alm_behaviour_model.params_json`의 ramp_ceiling·ramp_slope)를 적용할
    자리가 필요해 함수형을 분리한다. 계수를 함수 본문에 두면 추정 결과가
    적용 경로에 닿을 수 없다.
    """
    return min(float(ceiling), float(slope) * max(float(age_months), 0.0))


# PSA 100%의 계수. SIFMA 공표 표준이며 지어낸 값은 아니지만 **미국 MBS 관행**
# 이고 국내 실증근거가 없다(§5.18). 원장이 `input_source='표준벤치마크'`로
# 표시하며, 자체추정 계수가 들어오면 이 벌은 대조군으로만 남는다.
_PSA_100_CEILING, _PSA_100_SLOPE = 0.06, 0.002


def psa_cpr(age_months: float) -> float:
    """PSA 100% 기준 CPR. 30개월에 6%로 램프업 후 평탄."""
    return seasoning_ramp(age_months, ceiling=_PSA_100_CEILING,
                          slope=_PSA_100_SLOPE)


def scenario_multiplier(mult_table: pd.DataFrame, model: str, scenario: str,
                        ) -> tuple[float, ParamWarning | None]:
    """`alm_behaviour_scenario_mult`에서 승수를 읽는다. NULL이면 1.0 + 경고.

    폴백을 1.0으로 두는 것은 "조정하지 않음"이고, 0.8/1.2 중 하나를 고르는
    것은 **모르는 값을 아는 척하는 것**이다. 둘의 차이가 이 함수의 요점이다.
    """
    hit = mult_table[(mult_table["model"] == model)
                     & (mult_table["scenario"] == scenario)]
    if hit.empty:
        return 1.0, ParamWarning(
            model, scenario, "multiplier",
            "alm_behaviour_scenario_mult에 해당 (모형, 시나리오) 행이 없다")
    val = hit["multiplier"].iloc[0]
    if pd.isna(val):
        return 1.0, ParamWarning(
            model, scenario, "multiplier",
            f"승수 미확인(evidence_status={hit['evidence_status'].iloc[0]}) — "
            "조정 없이 1.0으로 진행")
    return float(val), None


def scurve_ri(incentive: float, a: float, b: float, c: float, d: float) -> float:
    """Richard-Roll 리파이낸싱 인센티브 함수 RI(x) = a + b·arctan(c·(x − d)).

    계수는 **반드시 원장에서** 온다 — 이 함수에 기본값이 없는 이유다.
    반환값은 [0,1)로 자른다(CPR로 쓰이므로).
    """
    return min(max(a + b * math.atan(c * (incentive - d)), 0.0), 0.999999)


def effective_prepay_fee_rate(fee_rate: float, fee_term_years: float,
                              elapsed_years: float) -> float:
    """중도상환수수료의 잔존 요율 — 잔존일수/약정일수로 슬라이딩해 0으로 간다.

    국내 은행 공시 산식: 수수료 = 중도상환원금 × 요율 × 잔존일수/약정일수
    (최장 3년). 이 비용항은 결정론적이므로 조기상환 인센티브에서 차감된다.
    **다만 일시금 수수료를 금리 인센티브에서 그대로 빼는 방식(연환산 대신)에
    규제 근거는 없다** — 원장의 `deduct_prepay_fee` 스위치로 노출한다.
    """
    if fee_term_years <= 0.0:
        return 0.0
    return fee_rate * max(0.0, (fee_term_years - elapsed_years) / fee_term_years)


# ---------------------------------------------------------------- 3종 모형

def apply_prepayment(
    schedule: list[Instalment],
    *,
    annual_rate: float,
    cpr_path: list[float],
) -> list[CashflowPoint]:
    """조기상환 반영 현금흐름 — SIFMA 순서.

    계약 스케줄의 원금은 **잔존 잔액에 비례해 축소**된다(pool factor). 축소하지
    않고 원 스케줄 원금을 그대로 빼면 잔액이 음수로 내려가 만기 전에 대출이
    사라진다.

        r_k     = B_{k−1} / B°_{k−1}          (실제/무조기상환 잔액비)
        SP_k    = r_k · SP°_k
        PP_k    = SMM_k · (B_{k−1} − SP_k)     ← SP를 뺀 뒤에 건다
        B_k     = B_{k−1} − SP_k − PP_k

    최종 회차는 잔액 전액을 상환하므로 원금 합계는 조기상환 여부와 무관하게
    기초잔액과 같다 — 조기상환은 **금액이 아니라 시점**을 바꾼다. 이 항등식이
    설계의 `alm_cf_contract_ties_to_notional` 검사를 행동기준에서도 성립시킨다.
    """
    if len(cpr_path) != len(schedule):
        raise ValueError("cpr_path 길이가 스케줄 회차 수와 다르다")
    out: list[CashflowPoint] = []
    bal = schedule[0].opening_balance
    prev_t = 0.0
    for k, (ins, cpr) in enumerate(zip(schedule, cpr_path), start=1):
        tau = max(ins.t_years - prev_t, 0.0)
        interest = bal * annual_rate * tau
        if k == len(schedule):
            sp, pp = bal, 0.0
        else:
            ratio = bal / ins.opening_balance if ins.opening_balance else 0.0
            sp = ratio * ins.principal
            pp = smm_from_cpr(cpr, tau) * max(bal - sp, 0.0)
        out.append(CashflowPoint(ins.t_years, sp + pp, interest))
        bal = max(bal - sp - pp, 0.0)
        prev_t = ins.t_years
    return out


def apply_early_redemption(
    schedule: list[Instalment],
    *,
    annual_rate: float,
    tdrr: float,
    shortest_t_years: float,
) -> list[CashflowPoint]:
    """정기예금 중도해지 — TDRR 비율만큼 최단 버킷으로 앞당긴다.

    해지분은 잔여 이자를 받지 못하고 즉시 빠져나가므로, 잔존 회차의 원금·이자를
    (1 − TDRR)로 축소하고 해지 원금을 최단 시점에 놓는다. 해지 페널티(이자
    감액률)는 국내 규정을 확인하지 못해 **반영하지 않는다** — 반영하면
    없는 계수를 쓰게 된다.
    """
    if not 0.0 <= tdrr <= 1.0:
        raise ValueError(f"TDRR은 [0,1] — 받은 값 {tdrr}")
    b0 = schedule[0].opening_balance
    keep = 1.0 - tdrr
    out = [CashflowPoint(shortest_t_years, b0 * tdrr, 0.0)]
    prev_t = 0.0
    bal = b0 * keep
    for ins in schedule:
        tau = max(ins.t_years - prev_t, 0.0)
        out.append(CashflowPoint(ins.t_years, ins.principal * keep,
                                 bal * annual_rate * tau))
        bal = max(bal - ins.principal * keep, 0.0)
        prev_t = ins.t_years
    return out


def nmd_slotting(
    balance: float,
    *,
    core_ratio: float,
    core_ratio_cap: float,
    avg_maturity_years: float,
    avg_maturity_cap_years: float,
    buckets: pd.DataFrame,
    stable_ratio: float | None = None,
    scope: str = "",
) -> tuple[list[CashflowPoint], float, list[ParamWarning]]:
    """비만기예금 코어/논코어 분해와 선형 슬로팅.

    반환: (현금흐름점, 달성 평균만기, 경고)

    **원금(명목)만 슬로팅한다.** 표준방법에서 NMD는 계약 이자일정이 없는
    관리금리 상품이므로 명목 리프라이싱액을 버킷에 배분한다
    (BCBS d368 Annex 2). 이자를 얹으면 원장에 없는 이자일정을 지어내게 된다.

    상한은 **엔진이 강제한다** — 원장에 상한 초과값이 들어와도 산출은 상한을
    넘지 않는다. 금융기관 NMD는 코어 인정 불가(상한 0.00)이므로 전액 최단
    버킷으로 간다.
    """
    warns: list[ParamWarning] = []
    if stable_ratio is not None and not pd.isna(stable_ratio):
        # core ⊆ stable — 위반이면 분해 자체가 모순이다.
        if core_ratio > stable_ratio + 1e-12:
            raise ValueError(
                f"{scope}: core_ratio({core_ratio}) > stable_ratio({stable_ratio}) — "
                "코어는 안정예금의 부분집합이다")
    else:
        warns.append(ParamWarning(
            "NMD", scope, "stable_ratio",
            "안정예금 비율 미추정(NULL) — core ⊆ stable 정합성 검사 미수행"))

    core_r = min(float(core_ratio), float(core_ratio_cap))
    horizon_avg = min(float(avg_maturity_years), float(avg_maturity_cap_years))
    core = balance * core_r
    non_core = balance - core

    lo = buckets["lower_years"].to_numpy(dtype=float)
    hi = buckets["upper_years"].to_numpy(dtype=float)
    tm = buckets["t_mid_years"].to_numpy(dtype=float)
    shortest = float(tm[0])

    points = [CashflowPoint(shortest, non_core, 0.0)] if non_core > 0 else []
    if core <= 0.0 or horizon_avg <= 0.0:
        return points, 0.0, warns

    # 균등분포 [0, H]의 평균은 H/2이므로, 목표 평균만기 M̄를 맞추려면 H = 2·M̄.
    # (EBA 단순화법의 상한이 평균만기인지 최종만기인지 원문 미확인 — 모듈
    #  docstring 참조. 여기서는 평균만기 정합을 택하고 달성치를 함께 돌려준다.)
    horizon = 2.0 * horizon_avg
    overlap = (pd.Series(hi).clip(upper=horizon)
               - pd.Series(lo).clip(upper=horizon)).clip(lower=0.0).to_numpy()
    if overlap.sum() <= 0.0:
        return points, 0.0, warns
    w = overlap / overlap.sum()
    points += [CashflowPoint(float(tm[i]), float(core * w[i]), 0.0)
               for i in range(len(w)) if w[i] > 0.0]
    achieved = float((w * tm).sum())

    # 이산화가 감독상한을 넘길 수 있다. H가 버킷 경계에 떨어지지 않으면 부분적으로
    # 걸친 버킷의 질량이 그 버킷 t_mid(구간 중점이 아니다)로 밀리기 때문이다.
    # 예: 상한 4년 → H=8년이 "5-10y" 버킷 안에 떨어지고, [5,8]의 질량이 6.5년이
    # 아니라 7.5년에 놓여 달성 평균만기가 4.375년이 된다.
    # 상한 초과를 조용히 두면 감독기준 위반이 산출물에 남지 않는다. 호라이즌을
    # 줄여 맞추지도 않는다 — 그것은 규정이 아니라 버킷 격자에 맞추는 것이다.
    # 근본 해결은 표준 19버킷 적재다(설계 §2.2, §5.5).
    if achieved > avg_maturity_cap_years + 1e-9:
        warns.append(ParamWarning(
            "NMD", scope, "avg_maturity_cap_years",
            f"버킷 이산화로 달성 평균만기 {achieved:.3f}년이 감독상한 "
            f"{float(avg_maturity_cap_years):.3f}년을 초과한다 — 슬로팅 호라이즌 "
            f"{horizon:.2f}년이 버킷 경계에 떨어지지 않는다. 표준 19버킷 적재 전까지 "
            "이 초과는 사다리 격자의 산물이며 은행의 가정이 아니다"))
    return points, achieved, warns
