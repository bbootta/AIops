"""상환스케줄 — 계약조건에서 원금·이자 회차를 생성한다.

**이 모듈이 왜 필요한가.** 현행 ALM은 리프라이싱 *갭*을 버킷 중점에서 할인한다.
갭에는 회차가 없으므로 상환방식(원리금균등/원금균등/만기일시/거치후분할)이
현금흐름 모양에 미치는 영향이 **원리적으로 표현되지 않는다** — 같은 잔액이면
원리금균등 대출과 만기일시 대출이 같은 값을 낸다. 실제로는 듀레이션이 배로
갈린다. 이 모듈이 그 회차를 만든다.

**잔액 경로가 1급이고 원금은 그 차분이다.** 원금을 먼저 정하고 잔액을 누적하면
반올림 오차가 만기까지 쌓여 원금 합계가 명목과 어긋난다. 반대로 잔액 경로를
정의하고 `원금_k = B_{k−1} − B_k` 로 두면 합계가 **망원급수로 정확히**
`B_0 − B_n` 이 되고, 최종 회차에 잔여 balloon을 얹으면 총원금 = 명목이 된다.
설계가 요구한 `alm_cf_contract_ties_to_notional` 검사가 이 성질에 걸려 있다.

**이자는 잔액 경로와 독립으로 관행에 따라 계산한다.** 원리금균등의 PMT는
명목 주기금리 `i = 연이율/지급횟수` 로 잡되(시장 관행), 실제 이자는
`잔액 × 연이율 × year_fraction(관행)` 이다. 따라서 ACT/365F 같은 관행에서는
회차 지급액이 PMT와 미세하게 달라진다 — 이것은 오차가 아니라 **실제 대출의
동작**이고, 관행을 원장에 둔 이유이기도 하다.

공식 출처
  원리금균등 PMT (balloon 포함):
      B_0 = PMT·a(n,i) + B_n·(1+i)^(−n),  a(n,i) = (1−(1+i)^(−n))/i
   ⇒  PMT = (B_0 − B_n·(1+i)^(−n)) · i / (1 − (1+i)^(−n))
      eCampusOntario, *Mathematics of Finance* §4.3 (Amortization / Loan balance)
  잔액 후진식 (수치안정):
      B_k = PMT·(1 − (1+i)^(−(n−k)))/i + B_n·(1+i)^(−(n−k))
      전진식 `B_k = B_0(1+i)^k − PMT((1+i)^k − 1)/i` 은 PMT 반올림이
      (1+i)^k 로 증폭되므로 **테스트 대조용으로만** 쓴다.
  이자계산 관행: ISDA 2006 Definitions §4.16 → risk_lib.alm.daycount
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from risk_lib.alm.daycount import year_fraction

__all__ = [
    "AMORT_TYPES",
    "PAY_FREQS",
    "Instalment",
    "annuity_payment",
    "payment_dates",
    "build_schedule",
    "balance_forward",
]

# `alm_product_terms.amort_type` 허용값.
#   non_maturity / revolving 은 계약상 상환일정이 없다 — 이 모듈이 아니라
#   behaviour(NMD 슬로팅)와 cashflow(최단 버킷 배치)가 처리한다.
AMORT_TYPES: tuple[str, ...] = (
    "annuity", "equal_principal", "bullet", "grace_then_annuity",
    "non_maturity", "revolving",
)
SCHEDULED_AMORT_TYPES: tuple[str, ...] = (
    "annuity", "equal_principal", "bullet", "grace_then_annuity",
)
PAY_FREQS: tuple[int, ...] = (1, 2, 4, 12)


@dataclass(frozen=True)
class Instalment:
    """상환 1회차. 금액 단위는 계약 명목과 같다(KRW)."""
    seq: int
    start: date                  # 직전 지급일 (이자 기산일)
    end: date                    # 지급일
    t_years: float               # asof 기준 경과연수 — 버킷 슬로팅 축
    opening_balance: float
    principal: float
    interest: float              # 전액(마진 포함) — 분리는 cashflow가 한다
    closing_balance: float


def _month_end(y: int, m: int) -> int:
    """해당 연·월의 말일. 다음 달 1일에서 하루 빼면 되므로 윤년 분기가 없다."""
    nxt = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1).day


def _add_months(d: date, months: int) -> date:
    """월 가산. 존재하지 않는 날짜는 해당 월의 말일로 절사한다(1/31+1M = 2/28|29)."""
    y, m0 = divmod(d.year * 12 + (d.month - 1) + months, 12)
    m = m0 + 1
    return date(y, m, min(d.day, _month_end(y, m)))


def annuity_payment(balance: float, periodic_rate: float, n: int,
                    terminal_balance: float = 0.0) -> float:
    """원리금균등 회차 지급액. r=0 분기 필수 — 나눗셈이 0/0이 된다."""
    if n <= 0:
        raise ValueError("annuity_payment: 회차 수 n은 1 이상이어야 한다")
    if periodic_rate == 0.0:
        return (balance - terminal_balance) / n
    disc = (1.0 + periodic_rate) ** (-n)
    return (balance - terminal_balance * disc) * periodic_rate / (1.0 - disc)


def balance_forward(balance: float, periodic_rate: float, pmt: float,
                    k: int) -> float:
    """전진식 잔액 — 후진식 검증 **대조용**. 산출 경로에서 쓰지 않는다.

    B_k = B_0(1+i)^k − PMT·((1+i)^k − 1)/i
    """
    if periodic_rate == 0.0:
        return balance - pmt * k
    g = (1.0 + periodic_rate) ** k
    return balance * g - pmt * (g - 1.0) / periodic_rate


def payment_dates(asof: date, maturity: date, pay_freq_per_year: int) -> list[date]:
    """asof 이후 만기까지의 지급일. **만기에서 역산**한다.

    정방향으로 만들면 마지막 회차가 만기에 떨어지지 않아 잔여 원금을 어디에
    둘지가 임의가 된다. 역산하면 최종 회차 = 만기가 보장된다.
    """
    if pay_freq_per_year not in PAY_FREQS:
        raise ValueError(f"미지원 지급주기: {pay_freq_per_year} — 허용값 {PAY_FREQS}")
    step = 12 // pay_freq_per_year
    # 만기를 **앵커로 고정**하고 k회차씩 빼서 만든다. 직전 결과에 반복해서
    # −1개월을 적용하면 말일 절사가 누적된다 (3/31 → 2/28 → 1/28): 앵커 방식은
    # 3/31 → 2/28 → 1/31 로 원래 일자를 되찾는다.
    out: list[date] = []
    k = 0
    while True:
        d = _add_months(maturity, -step * k)
        if d <= asof:
            break
        out.append(d)
        k += 1
    out.reverse()
    # 만기가 asof 이하인 계약(이미 만료)은 호출측이 걸러야 한다. 여기서 빈
    # 목록을 돌려주면 원금이 사라지므로 만기 1회차로 되돌린다.
    return out or [max(maturity, asof)]


def _closing_balances(amort_type: str, b0: float, i: float, n: int,
                      balloon_ratio: float, grace_n: int) -> list[float]:
    """회차별 **기말잔액** 경로 (길이 n, 마지막은 항상 0).

    마지막이 0인 것은 가정이 아니라 정의다 — 만기에 잔여 원금(balloon 포함)을
    전액 상환한다. balloon은 별도 회차가 아니라 최종 회차 원금에 포함된다.
    """
    bn = b0 * balloon_ratio
    if amort_type == "bullet":
        return [b0] * (n - 1) + [0.0]
    if amort_type == "equal_principal":
        sp = (b0 - bn) / n
        return [b0 - sp * k for k in range(1, n)] + [0.0]
    if amort_type == "annuity":
        pmt = annuity_payment(b0, i, n, bn)
        return [_annuity_balance(pmt, i, n - k, bn) for k in range(1, n)] + [0.0]
    if amort_type == "grace_then_annuity":
        g = min(grace_n, n - 1)          # 최소 1회차는 상환해야 거치가 의미를 갖는다
        m = n - g
        pmt = annuity_payment(b0, i, m, bn)
        head = [b0] * g
        tail = [_annuity_balance(pmt, i, m - k, bn) for k in range(1, m)] + [0.0]
        return head + tail
    raise ValueError(f"상환일정이 없는 상환방식: {amort_type!r} — "
                     f"스케줄 대상은 {SCHEDULED_AMORT_TYPES}")


def _annuity_balance(pmt: float, i: float, remaining: int, bn: float) -> float:
    """후진식 잔액: 남은 회차 remaining개의 PV + balloon PV."""
    if i == 0.0:
        return pmt * remaining + bn
    disc = (1.0 + i) ** (-remaining)
    return pmt * (1.0 - disc) / i + bn * disc


def build_schedule(
    *,
    asof: date,
    maturity: date,
    opening_balance: float,
    annual_rate: float,
    amort_type: str,
    pay_freq_per_year: int,
    day_count: str,
    grace_months: int = 0,
    balloon_ratio: float = 0.0,
) -> list[Instalment]:
    """asof 시점 잔액에서 만기까지의 잔여 상환스케줄.

    `opening_balance`는 **asof 현재 잔액**이다(원계약 최초 원금이 아니다).
    ALM은 현재 대차대조표를 앞으로 굴리는 산출이므로 과거 상환이력을 복원할
    필요가 없고, 복원하려 들면 원장에 없는 값을 지어내게 된다.

    반환 회차의 원금 합계는 `opening_balance`와 정확히 같다(망원급수).
    """
    if amort_type not in SCHEDULED_AMORT_TYPES:
        raise ValueError(f"build_schedule: {amort_type!r}은 계약 상환일정이 없다")
    if not 0.0 <= balloon_ratio < 1.0:
        raise ValueError(f"balloon_ratio는 [0,1) — 받은 값 {balloon_ratio}")

    dates = payment_dates(asof, maturity, pay_freq_per_year)
    n = len(dates)
    i = annual_rate / pay_freq_per_year
    step = 12 // pay_freq_per_year
    grace_n = max(0, grace_months) // step

    closing = _closing_balances(amort_type, opening_balance, i, n,
                                balloon_ratio, grace_n)

    out: list[Instalment] = []
    prev_date, prev_bal = asof, opening_balance
    for k, (d, cb) in enumerate(zip(dates, closing), start=1):
        tau = year_fraction(prev_date, d, day_count)
        interest = prev_bal * annual_rate * tau
        out.append(Instalment(
            seq=k, start=prev_date, end=d,
            t_years=(d - asof).days / 365.25,
            opening_balance=prev_bal,
            principal=prev_bal - cb,
            interest=interest,
            closing_balance=cb,
        ))
        prev_date, prev_bal = d, cb
    return out
