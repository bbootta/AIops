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

    def evaluate(self, portfolio: pd.DataFrame, *, exposure_col: str = "ead",
                 min_utilisation: float = 0.90) -> list[LimitBreach]:
        """Return breaches at or above `min_utilisation` (기본 0.90 = 경보 이상).

        For limits with value=None, the limit is applied to *each* bucket of
        the dimension (e.g. per obligor, per sector).

        `min_utilisation=0.0`을 주면 위반이 아닌 버킷까지 전부 돌려준다 —
        한도관리 화면은 소진율 **분포**를 보여야 하므로 그 경로가 필요하다.
        위반 보고서(`report()` 기본값)의 계약은 바뀌지 않는다.
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
                if util >= min_utilisation:
                    breaches.append(LimitBreach(lim, lim.value, exp, threshold_amt, util))
            else:
                grp = portfolio.groupby(lim.dimension)[exposure_col].sum()
                for bucket, exp in grp.items():
                    util = exp / threshold_amt if threshold_amt > 0 else float("inf")
                    if util >= min_utilisation:
                        breaches.append(LimitBreach(lim, bucket, float(exp), threshold_amt, util))
        return breaches

    def report(self, portfolio: pd.DataFrame, *, exposure_col: str = "ead",
               min_utilisation: float = 0.90) -> pd.DataFrame:
        rows = []
        for b in self.evaluate(portfolio, exposure_col=exposure_col,
                               min_utilisation=min_utilisation):
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
