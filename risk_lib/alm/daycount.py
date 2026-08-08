"""이자계산 관행(day count convention) — 이자금액을 직접 바꾸는 계약조건.

같은 명목·같은 금리라도 30/360과 ACT/365F는 이자금액이 다르다. 현행 ALM이
갭을 버킷 중점에서 할인하는 근사였을 때는 이 차이가 보이지 않았지만, 현금흐름을
계약대로 생성하는 순간 **이자금액의 1차 결정요인**이 된다. 따라서 관행은
`alm_product_terms.day_count` 컬럼에서 오고, 이 모듈은 그 문자열을 연분수로
바꾸는 일만 한다 — 기본값을 함수 시그니처에 숨기지 않는다.

출처: ISDA 2006 Definitions §4.16 (Day Count Fraction).
  (a) ACT/ACT (ISDA)  — 윤년·평년 구간을 나눠 각각 366·365로 나눈 뒤 합산
  (d) ACT/365 (Fixed) — 실제일수 / 365
  (e) ACT/360         — 실제일수 / 360
  (f) 30/360 (Bond basis) — D1←min(D1,30); D1이 30이 된 뒤 D2도 31이면 D2←30

30/360의 보정 순서가 핵심이다. D1 보정을 하지 않은 채 D2만 자르면 월말 계약의
이자가 하루씩 어긋나고, 그 오차는 만기까지 누적된다.
"""

from __future__ import annotations

from datetime import date

__all__ = ["DAY_COUNTS", "year_fraction"]

# `alm_product_terms.day_count` 의 허용값. 스펙(allowed)과 이 튜플이 같은 소스를
# 봐야 원장에 있는데 엔진이 모르는 관행이 생기지 않는다.
DAY_COUNTS: tuple[str, ...] = ("30/360", "ACT/365F", "ACT/360", "ACT/ACT_ISDA")


def _is_leap(y: int) -> bool:
    return (y % 4 == 0 and y % 100 != 0) or y % 400 == 0


def _thirty_360(d1: date, d2: date) -> float:
    """30/360 Bond basis — ISDA 2006 §4.16(f)."""
    dd1, dd2 = d1.day, d2.day
    # 1) 시작일이 31일이면 30일로 본다.
    if dd1 == 31:
        dd1 = 30
    # 2) 시작일이 (보정 후) 30일이고 종료일이 31일이면 종료일도 30일로 본다.
    #    조건에 dd1==30을 넣지 않으면 2월말→3월31일 같은 구간이 틀린다.
    if dd2 == 31 and dd1 == 30:
        dd2 = 30
    return (360 * (d2.year - d1.year)
            + 30 * (d2.month - d1.month)
            + (dd2 - dd1)) / 360.0


def _act_act_isda(d1: date, d2: date) -> float:
    """ACT/ACT (ISDA) — ISDA 2006 §4.16(b).

    구간을 연도 경계로 쪼개 윤년 부분은 /366, 평년 부분은 /365로 나눈 뒤 합산한다.
    구간 전체를 한 분모로 나누면 윤년을 걸치는 계약의 이자가 틀린다.
    """
    if d2 <= d1:
        return 0.0
    total = 0.0
    y = d1.year
    cur = d1
    while y < d2.year:
        nxt = date(y + 1, 1, 1)
        total += (nxt - cur).days / (366.0 if _is_leap(y) else 365.0)
        cur = nxt
        y += 1
    total += (d2 - cur).days / (366.0 if _is_leap(y) else 365.0)
    return total


def year_fraction(d1: date, d2: date, convention: str) -> float:
    """[d1, d2) 구간의 연분수. 이자 = 잔액 × 연이율 × year_fraction.

    d2 <= d1 이면 0.0 — 음수 연분수는 이자를 음수로 만들어 조용히 대차를 깬다.
    """
    if convention not in DAY_COUNTS:
        raise ValueError(
            f"미지원 이자계산 관행: {convention!r} — 허용값 {DAY_COUNTS}. "
            "원장(alm_product_terms.day_count)에 없는 값이 들어왔다면 "
            "스펙의 allowed와 DAY_COUNTS 중 한쪽만 고쳐진 것이다.")
    if d2 <= d1:
        return 0.0
    if convention == "30/360":
        return _thirty_360(d1, d2)
    if convention == "ACT/365F":
        return (d2 - d1).days / 365.0
    if convention == "ACT/360":
        return (d2 - d1).days / 360.0
    return _act_act_isda(d1, d2)
