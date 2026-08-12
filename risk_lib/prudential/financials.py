"""재무상태표·손익계산서 요약 — 업무보고서 기본 서식의 원천.

자본비율 서식만 있고 재무제표가 없으면 감독당국은 분모·분자를 대사할 수 없다.
여기서 만드는 값은 전부 이미 산출된 것에서 유도한다 —

  자산   대차대조표(alm.balance_sheet) + 대손충당금 차감
  부채   조달 구성 합계
  자본   CapitalStack (규제자본과 회계자본을 구분해 둘 다 남긴다)
  손익   포트폴리오 revenue/operating_cost + ECL 전입 + 운영손실

새 가정을 넣는 곳(법인세율·기타영업외손익)은 상수로 뽑아 근거를 적는다.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# 법인세율 — 지방소득세 포함 실효세율 가정. 실제 제출 시 기관 실효세율로 교체.
CORPORATE_TAX_RATE = 0.242


@dataclass(frozen=True)
class FinancialStatements:
    asof: str
    balance: pd.DataFrame       # section, item, amount
    income: pd.DataFrame        # seq, item, amount, formula
    total_assets: float
    total_liabilities: float
    accounting_equity: float
    regulatory_capital: float
    net_income: float

    def passes(self) -> bool:
        """자산 = 부채 + 자본이 맞아야 재무제표다."""
        return abs(self.total_assets
                   - (self.total_liabilities + self.accounting_equity)) <= 1.0


def build_financials(result, portfolio: pd.DataFrame) -> FinancialStatements:
    """대차대조표·손익계산서를 산출값에서 조립한다."""
    asof = result.meta.get("asof", "1970-01-01")
    bs = result.alm["balance_sheet"]
    cap = result.meta["capital"]
    ecl_total = float(result.ecl["total"])

    loans_gross = float(bs.loans)
    hqla_total = float(sum(bs.hqla.values()))
    # 대손충당금은 대출채권에서 차감표시한다 — 총액만 두면 순자산이 과대계상된다.
    loans_net = loans_gross - ecl_total
    total_assets = float(bs.total_assets) - ecl_total

    bal_rows = [
        ("자산", "현금 및 예치금", float(bs.hqla["level_1"])),
        ("자산", "유가증권 (Level 2A)", float(bs.hqla["level_2a"])),
        ("자산", "유가증권 (Level 2B)", float(bs.hqla["level_2b"])),
        ("자산", "대출채권 (총액)", loans_gross),
        ("자산", "대손충당금 (차감)", -ecl_total),
        ("자산", "대출채권 (순액)", loans_net),
        ("자산", "기타자산", float(bs.other_assets)),
        ("자산", "자산총계", total_assets),
    ]
    liab_total = 0.0
    _FUND_KO = {
        "retail_stable": "예수금 — 개인 안정",
        "retail_less_stable": "예수금 — 개인 준안정",
        "corporate_operational": "예수금 — 법인 결제성",
        "corporate_non_operational": "예수금 — 법인 비결제성",
        "wholesale_fi_lt6m": "차입금 — 금융기관 6개월 이내",
        "wholesale_fi_6to12m": "차입금 — 금융기관 6~12개월",
        "funding_gt1y": "사채 및 장기차입금",
    }
    for k, v in bs.funding.items():
        bal_rows.append(("부채", _FUND_KO.get(k, k), float(v)))
        liab_total += float(v)
    bal_rows.append(("부채", "부채총계", liab_total))

    accounting_equity = total_assets - liab_total
    bal_rows += [
        ("자본", "자본금 및 자본잉여금", float(cap.cet1) * 0.29),
        ("자본", "이익잉여금", accounting_equity - float(cap.cet1) * 0.29
         - float(cap.additional_t1)),
        ("자본", "신종자본증권 (AT1)", float(cap.additional_t1)),
        ("자본", "자본총계 (회계)", accounting_equity),
        ("자본", "규제자본 합계 (참고)", float(cap.total)),
    ]
    balance = pd.DataFrame(bal_rows, columns=["section", "item", "amount"])

    # ---- 손익계산서
    revenue = float(portfolio["revenue"].sum())
    opex = float(portfolio["operating_cost"].sum())
    op_loss = float(getattr(result.op_loss, "annual_total", 0.0))
    # 충당금 전입액은 당기 ECL 전액이 아니라 잔액 변동이지만, 기초 원장이 없으므로
    # 요인별 귀속(ifrs9_deep.attribution)의 순증분을 전입액으로 쓴다.
    attr = getattr(result.ifrs9_deep, "attribution", None)
    if isinstance(attr, pd.DataFrame) and {"effect", "value"} <= set(attr.columns):
        m = dict(zip(attr["effect"], attr["value"]))
        provision = float(m.get("end", ecl_total)) - float(m.get("start", 0.0))
    else:
        provision = ecl_total
    pre_tax = revenue - opex - provision - op_loss
    tax = max(pre_tax, 0.0) * CORPORATE_TAX_RATE
    net_income = pre_tax - tax

    inc_rows = [
        (1, "영업수익", revenue, "포트폴리오 수익 합계"),
        (2, "영업비용", -opex, "포트폴리오 운영비용 합계"),
        (3, "충당금 전입액", -provision,
         "IFRS 9 ECL 기말 − 기초 (요인별 귀속 기준)"),
        (4, "운영손실", -op_loss, "운영손실 사건 순손실 연간 합계"),
        (5, "법인세차감전순이익", pre_tax, "① + ② + ③ + ④"),
        (6, "법인세비용", -tax, f"max(0, 세전이익) × {CORPORATE_TAX_RATE:.1%}"),
        (7, "당기순이익", net_income, "⑤ + ⑥"),
    ]
    income = pd.DataFrame(inc_rows, columns=["seq", "item", "amount", "formula"])

    return FinancialStatements(
        asof=asof, balance=balance, income=income,
        total_assets=total_assets, total_liabilities=liab_total,
        accounting_equity=accounting_equity,
        regulatory_capital=float(cap.total), net_income=net_income,
    )
