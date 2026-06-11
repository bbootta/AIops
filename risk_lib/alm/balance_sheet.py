"""Synthetic bank balance sheet derived from the loan book.

The loan portfolio (EAD) anchors the asset side; HQLA holdings, other assets,
funding mix and repricing profiles are generated deterministically (seeded)
with proportions typical of a KR commercial bank, so the ALM modules
(IRRBB / LCR / NSFR) have consistent inputs that tie back to the credit book.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


# Repricing ladder used for IRRBB (bucket label, midpoint in years, upper bound).
REPRICING_BUCKETS = [
    ("0-1m",   1 / 24,  1 / 12),
    ("1-3m",   2 / 12,  3 / 12),
    ("3-6m",   4.5 / 12, 6 / 12),
    ("6-12m",  9 / 12,  1.0),
    ("1-2y",   1.5,     2.0),
    ("2-3y",   2.5,     3.0),
    ("3-5y",   4.0,     5.0),
    ("5-10y",  7.5,     10.0),
    ("10y+",   12.5,    20.0),
]


@dataclass
class BalanceSheet:
    """All amounts in KRW (same unit as portfolio EAD)."""
    total_assets: float
    loans: float                      # = portfolio EAD total
    hqla: dict[str, float]            # level_1 / level_2a / level_2b (market value)
    other_assets: float
    funding: dict[str, float]         # category → amount
    equity: float
    repricing: pd.DataFrame           # bucket, t_mid, assets, liabilities, gap
    asset_split: dict[str, float] = field(default_factory=dict)  # NSFR asset buckets

    def funding_total(self) -> float:
        return sum(self.funding.values())


def generate_balance_sheet(
    portfolio: pd.DataFrame,
    capital_total: float,
    *,
    seed: int = 42,
) -> BalanceSheet:
    """Build a balance sheet around the loan book.

    Loans are taken as-is from the portfolio; the rest of the balance sheet is
    proportioned to total assets with mild seeded jitter (±5%) so different
    seeds yield slightly different but always-coherent sheets.
    """
    rng = np.random.default_rng(seed + 101)
    loans = float(portfolio["ead"].sum())

    def jitter(x: float) -> float:
        return x * float(rng.uniform(0.95, 1.05))

    # Asset side: loans ~72% of total assets.
    total_assets = loans / jitter(0.72)
    hqla = {
        "level_1": total_assets * jitter(0.13),
        "level_2a": total_assets * jitter(0.04),
        "level_2b": total_assets * jitter(0.02),
    }
    other_assets = total_assets - loans - sum(hqla.values())

    # Funding side: liabilities = assets - equity.
    equity = capital_total
    liabilities = total_assets - equity
    w = {
        "retail_stable": jitter(0.28),
        "retail_less_stable": jitter(0.17),
        "corporate_operational": jitter(0.12),
        "corporate_non_operational": jitter(0.13),
        "wholesale_fi_lt6m": jitter(0.07),
        "wholesale_fi_6to12m": jitter(0.05),
        "funding_gt1y": jitter(0.18),
    }
    scale = liabilities / sum(w.values())
    funding = {k: v * scale for k, v in w.items()}

    # Repricing profile: assets reprice slower (fixed-rate mortgages, term
    # corporate loans).  Liabilities include non-maturity core deposits slotted
    # at behavioral maturities (IRRBB NMD treatment) — hence material weight in
    # the 1y+ buckets rather than pure contractual overnight repricing.
    asset_w = np.array([0.06, 0.08, 0.09, 0.12, 0.14, 0.13, 0.16, 0.14, 0.08])
    liab_w = np.array([0.10, 0.10, 0.10, 0.12, 0.13, 0.11, 0.14, 0.13, 0.07])
    asset_w = asset_w * rng.uniform(0.9, 1.1, len(asset_w))
    liab_w = liab_w * rng.uniform(0.9, 1.1, len(liab_w))
    asset_w /= asset_w.sum()
    liab_w /= liab_w.sum()

    rate_sensitive_assets = loans + sum(hqla.values())
    rate_sensitive_liabs = liabilities * 0.93   # ~7% non-rate-sensitive

    rep = pd.DataFrame({
        "bucket": [b[0] for b in REPRICING_BUCKETS],
        "t_mid": [b[1] for b in REPRICING_BUCKETS],
        "assets": asset_w * rate_sensitive_assets,
        "liabilities": liab_w * rate_sensitive_liabs,
    })
    rep["gap"] = rep["assets"] - rep["liabilities"]

    # NSFR asset decomposition tied to the actual portfolio composition.
    ac = portfolio.groupby("asset_class")["ead"].sum()
    mortgages = float(ac.get("residential_mortgage", 0.0))
    fi_loans = float(ac.get("bank", 0.0))
    npl = float(portfolio.loc[portfolio["dpd"] >= 90, "ead"].sum()) \
        if "dpd" in portfolio.columns else 0.0
    lt1y = float(portfolio.loc[portfolio["maturity"] < 1.0, "ead"].sum()) \
        if "maturity" in portfolio.columns else loans * 0.2
    other_ge1y = max(loans - mortgages - fi_loans - npl - lt1y, 0.0)
    asset_split = {
        "hqla_l1": hqla["level_1"],
        "hqla_l2a": hqla["level_2a"],
        "hqla_l2b": hqla["level_2b"],
        "loans_fi_lt6m": fi_loans * 0.4,
        "loans_lt1y": lt1y,
        "mortgages_ge1y": mortgages,
        "other_loans_ge1y": other_ge1y + fi_loans * 0.6,
        "npl": npl,
        "other_assets": other_assets,
    }

    return BalanceSheet(
        total_assets=total_assets,
        loans=loans,
        hqla=hqla,
        other_assets=other_assets,
        funding=funding,
        equity=equity,
        repricing=rep,
        asset_split=asset_split,
    )
