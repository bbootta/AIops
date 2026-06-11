"""NSFR — Net Stable Funding Ratio (Basel NSF20/30).

NSFR = ASF (available stable funding, liability side × ASF factors)
       / RSF (required stable funding, asset side × RSF factors)
≥ 100%.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from risk_lib.alm.balance_sheet import BalanceSheet
from risk_lib.references import NSFR_MIN, NSFR_ASF_FACTORS, NSFR_RSF_FACTORS


@dataclass
class NSFRResult:
    asf: pd.DataFrame           # category, amount, factor, weighted
    rsf: pd.DataFrame
    asf_total: float
    rsf_total: float
    nsfr: float

    def passes(self) -> bool:
        return self.nsfr >= NSFR_MIN


def compute_nsfr(bs: BalanceSheet) -> NSFRResult:
    f = bs.funding
    asf_rows = [
        ("capital", bs.equity, NSFR_ASF_FACTORS["capital"]),
        ("retail_stable", f["retail_stable"], NSFR_ASF_FACTORS["retail_stable"]),
        ("retail_less_stable", f["retail_less_stable"],
         NSFR_ASF_FACTORS["retail_less_stable"]),
        ("corporate_lt1y",
         f["corporate_operational"] + f["corporate_non_operational"],
         NSFR_ASF_FACTORS["corporate_lt1y"]),
        ("wholesale_fi_lt6m", f["wholesale_fi_lt6m"],
         NSFR_ASF_FACTORS["wholesale_fi_lt6m"]),
        ("wholesale_fi_6to12m", f["wholesale_fi_6to12m"],
         NSFR_ASF_FACTORS["wholesale_fi_6to12m"]),
        ("funding_gt1y", f["funding_gt1y"], NSFR_ASF_FACTORS["funding_gt1y"]),
    ]
    asf = pd.DataFrame(
        [{"category": c, "amount": a, "factor": x, "weighted": a * x}
         for c, a, x in asf_rows])

    rsf_rows = [(k, v, NSFR_RSF_FACTORS[k]) for k, v in bs.asset_split.items()]
    rsf = pd.DataFrame(
        [{"category": c, "amount": a, "factor": x, "weighted": a * x}
         for c, a, x in rsf_rows])

    asf_total = float(asf["weighted"].sum())
    rsf_total = float(rsf["weighted"].sum())
    nsfr = asf_total / rsf_total if rsf_total > 0 else float("inf")

    return NSFRResult(asf=asf, rsf=rsf, asf_total=asf_total,
                      rsf_total=rsf_total, nsfr=nsfr)
