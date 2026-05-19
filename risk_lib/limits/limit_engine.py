"""Exposure limit framework.

Supports concentration limits along arbitrary dimensions (single name, sector,
country, product, internal rating) expressed either as absolute amounts or as
percentage of Tier 1 capital (regulatory standard for 동일인 신용공여 한도).

Korean reference: 「은행법」 제35조 동일차주 신용공여 한도 (Tier1의 25%),
                  동일인 한도 (Tier1의 20%) — defaults below mirror these.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd


LimitBasis = Literal["absolute", "pct_tier1"]


@dataclass(frozen=True)
class LimitDefinition:
    name: str
    dimension: str           # column in portfolio to group by, e.g. "obligor_id"
    value: object            # specific bucket; None = applies per bucket
    threshold: float         # amount or pct (0..1)
    basis: LimitBasis = "absolute"


@dataclass
class LimitBreach:
    limit: LimitDefinition
    bucket: object
    exposure: float
    threshold_amount: float
    utilisation: float       # exposure / threshold_amount

    @property
    def severity(self) -> str:
        if self.utilisation >= 1.20:
            return "CRITICAL"
        if self.utilisation >= 1.00:
            return "BREACH"
        if self.utilisation >= 0.90:
            return "WARN"
        return "OK"


class LimitEngine:
    """Evaluate a set of LimitDefinitions against a portfolio."""

    def __init__(self, limits: list[LimitDefinition], tier1_capital: float | None = None):
        self.limits = limits
        self.tier1_capital = tier1_capital

    def _threshold_amount(self, lim: LimitDefinition) -> float:
        if lim.basis == "absolute":
            return lim.threshold
        if lim.basis == "pct_tier1":
            if self.tier1_capital is None or self.tier1_capital <= 0:
                raise ValueError("tier1_capital required for pct_tier1 limits")
            return lim.threshold * self.tier1_capital
        raise ValueError(f"unknown basis: {lim.basis}")

    def evaluate(self, portfolio: pd.DataFrame, *, exposure_col: str = "ead") -> list[LimitBreach]:
        """Return all breaches including warnings (utilisation >= 0.90).

        For limits with value=None, the limit is applied to *each* bucket of
        the dimension (e.g. per obligor, per sector).
        """
        breaches: list[LimitBreach] = []
        for lim in self.limits:
            if lim.dimension not in portfolio.columns:
                raise ValueError(f"dimension {lim.dimension!r} not in portfolio")
            threshold_amt = self._threshold_amount(lim)

            if lim.value is not None:
                df = portfolio[portfolio[lim.dimension] == lim.value]
                exp = float(df[exposure_col].sum())
                util = exp / threshold_amt if threshold_amt > 0 else float("inf")
                if util >= 0.90:
                    breaches.append(LimitBreach(lim, lim.value, exp, threshold_amt, util))
            else:
                grp = portfolio.groupby(lim.dimension)[exposure_col].sum()
                for bucket, exp in grp.items():
                    util = exp / threshold_amt if threshold_amt > 0 else float("inf")
                    if util >= 0.90:
                        breaches.append(LimitBreach(lim, bucket, float(exp), threshold_amt, util))
        return breaches

    def report(self, portfolio: pd.DataFrame, *, exposure_col: str = "ead") -> pd.DataFrame:
        rows = []
        for b in self.evaluate(portfolio, exposure_col=exposure_col):
            rows.append({
                "limit": b.limit.name,
                "dimension": b.limit.dimension,
                "bucket": b.bucket,
                "exposure": b.exposure,
                "threshold": b.threshold_amount,
                "utilisation": b.utilisation,
                "severity": b.severity,
            })
        cols = ["limit", "dimension", "bucket", "exposure",
                "threshold", "utilisation", "severity"]
        return pd.DataFrame(rows, columns=cols)
