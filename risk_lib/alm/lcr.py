"""LCR — Liquidity Coverage Ratio (Basel LCR20/30/40).

LCR = HQLA(after haircuts and the L2 40% / L2B 15% caps)
      / net cash outflows over 30 days (inflows capped at 75% of outflows)
≥ 100%.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from risk_lib.alm.balance_sheet import BalanceSheet
from risk_lib.references import (
    LCR_MIN, LCR_L2_CAP, LCR_L2B_CAP, LCR_HAIRCUT_L2A, LCR_HAIRCUT_L2B,
    LCR_INFLOW_CAP, LCR_RUNOFF, LCR_INFLOW_RATES,
)


@dataclass
class LCRResult:
    hqla_total: float
    hqla_detail: pd.DataFrame     # component, market_value, haircut, post_haircut, included
    outflows: pd.DataFrame        # category, amount, runoff, outflow
    inflows: pd.DataFrame         # category, amount, rate, inflow
    gross_outflow: float
    inflow_capped: float
    net_outflow: float
    lcr: float

    def passes(self) -> bool:
        return self.lcr >= LCR_MIN


def compute_lcr(bs: BalanceSheet, *, seed_inflow_frac: float = 0.04) -> LCRResult:
    """Compute LCR from the synthetic balance sheet.

    seed_inflow_frac: 30-day contractual inflows as a fraction of loans
    (maturing performing exposures), split retail/wholesale/FI 40/40/20.
    """
    # --- HQLA with caps (LCR30.47 adjustment formula) ---
    l1 = bs.hqla["level_1"]
    l2a = bs.hqla["level_2a"] * (1 - LCR_HAIRCUT_L2A)
    l2b = bs.hqla["level_2b"] * (1 - LCR_HAIRCUT_L2B)

    # Adjustment for the 15% L2B cap, then for the 40% total-L2 cap:
    #   adj15 = max(L2B − 15/85·(L1+L2A), L2B − 15/60·L1, 0)
    #   adj40 = max((L2A + L2B − adj15) − 2/3·L1, 0)
    #   HQLA  = L1 + L2A + L2B − adj15 − adj40
    k15 = LCR_L2B_CAP / (1 - LCR_L2B_CAP)               # 15/85
    adj15 = max(l2b - k15 * (l1 + l2a), l2b - (0.15 / 0.60) * l1, 0.0)
    l2b_after15 = l2b - adj15
    adj40 = max((l2a + l2b_after15) - LCR_L2_CAP / (1 - LCR_L2_CAP) * l1, 0.0)
    hqla_total = l1 + l2a + l2b_after15 - adj40

    # Attribute the 40% adjustment proportionally across L2A / L2B for the
    # component breakdown (the ratio itself only depends on hqla_total).
    l2_after15 = l2a + l2b_after15
    scale40 = (l2_after15 - adj40) / l2_after15 if l2_after15 > 0 else 0.0
    l2a_inc = l2a * scale40
    l2b_inc = l2b_after15 * scale40

    hqla_detail = pd.DataFrame([
        {"component": "Level 1", "market_value": bs.hqla["level_1"],
         "haircut": 0.0, "post_haircut": l1, "included": l1},
        {"component": "Level 2A", "market_value": bs.hqla["level_2a"],
         "haircut": LCR_HAIRCUT_L2A, "post_haircut": l2a, "included": l2a_inc},
        {"component": "Level 2B", "market_value": bs.hqla["level_2b"],
         "haircut": LCR_HAIRCUT_L2B, "post_haircut": l2b, "included": l2b_inc},
    ])

    # --- Outflows (LCR40 run-off) ---
    f = bs.funding
    out_rows = [
        ("retail_stable", f["retail_stable"], LCR_RUNOFF["retail_stable"]),
        ("retail_less_stable", f["retail_less_stable"],
         LCR_RUNOFF["retail_less_stable"]),
        ("corporate_operational", f["corporate_operational"],
         LCR_RUNOFF["corporate_operational"]),
        ("corporate_non_operational", f["corporate_non_operational"],
         LCR_RUNOFF["corporate_non_operational"]),
        ("wholesale_fi_unsecured", f["wholesale_fi_lt6m"],
         LCR_RUNOFF["wholesale_fi_unsecured"]),
        # committed facilities sized off the loan book (undrawn ≈ 10% of loans)
        ("committed_facilities", bs.loans * 0.10,
         LCR_RUNOFF["committed_facilities"]),
    ]
    outflows = pd.DataFrame(
        [{"category": c, "amount": a, "runoff": r, "outflow": a * r}
         for c, a, r in out_rows])
    gross_outflow = float(outflows["outflow"].sum())

    # --- Inflows (≤ 75% of outflows) ---
    base = bs.loans * seed_inflow_frac
    in_rows = [
        ("retail_inflows", base * 0.4, LCR_INFLOW_RATES["retail_inflows"]),
        ("wholesale_inflows", base * 0.4, LCR_INFLOW_RATES["wholesale_inflows"]),
        ("fi_inflows", base * 0.2, LCR_INFLOW_RATES["fi_inflows"]),
    ]
    inflows = pd.DataFrame(
        [{"category": c, "amount": a, "rate": r, "inflow": a * r}
         for c, a, r in in_rows])
    inflow_total = float(inflows["inflow"].sum())
    inflow_capped = min(inflow_total, LCR_INFLOW_CAP * gross_outflow)

    net_outflow = gross_outflow - inflow_capped
    lcr = hqla_total / net_outflow if net_outflow > 0 else float("inf")

    return LCRResult(
        hqla_total=hqla_total, hqla_detail=hqla_detail,
        outflows=outflows, inflows=inflows,
        gross_outflow=gross_outflow, inflow_capped=inflow_capped,
        net_outflow=net_outflow, lcr=lcr,
    )
