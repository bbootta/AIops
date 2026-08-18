"""XVA — Valuation adjustments suite (CVA, DVA, FVA, ColVA, MVA).

Global Top IB derivative pricing decomposes the trade value into:
  V = V_risk_free + CVA_adj + DVA_adj + FVA_adj + ColVA_adj + MVA_adj

Each adjustment captures a different counterparty/funding cost:

  - **CVA** (Credit Valuation Adjustment): expected loss from counterparty
                                            default. CVA = LGD_cpty · ∫ EPE(t) · dPD_cpty(t) · DF(t)
  - **DVA** (Debit Valuation Adjustment):   expected gain from own default.
                                            DVA = LGD_own · ∫ ENE(t) · dPD_own(t) · DF(t)
  - **FVA** (Funding Valuation Adjustment): funding cost of uncollateralised
                                            future exposure. Σ EPE(t) · FundingSpread · DF(t)
  - **ColVA** (Collateral Valuation Adj.):  cost of posting collateral on
                                            collateralised trades (OIS-CSA spread).
  - **MVA** (Margin Valuation Adjustment):  funding cost of initial margin
                                            (IM) posted to clearinghouse / SIMM IM.

This module produces:
  - per-counterparty XVA decomposition table
  - portfolio-level XVA P&L: CVA - DVA + FVA + ColVA + MVA
  - sensitivity of XVA to CDS spread, recovery, EPE/ENE
  - XVA hedge effectiveness ratio (residual after CDS hedge applied)

References: Gregory (2020) "The XVA Challenge", BCBS d325 (BA-CVA),
            CRR2 Art. 381–386, ISDA SIMM v2.6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


# ----- per-trade XVA inputs ------------------------------------------------

@dataclass
class XVAInputs:
    """Inputs for one trade's XVA decomposition."""
    notional: float
    maturity_years: float
    epe_curve: np.ndarray             # Expected Positive Exposure (NPV-weighted)
    ene_curve: np.ndarray             # Expected Negative Exposure
    time_grid: np.ndarray             # year fractions matching curves
    cpty_cds_bps: float               # 5y CDS spread of counterparty
    own_cds_bps: float                # 5y CDS spread of own bank
    funding_spread_bps: float = 50    # own funding spread
    csa_spread_bps: float = 10        # CSA collateral spread vs OIS
    im_initial_krw: float = 0         # initial margin posted (KRW)
    lgd_cpty: float = 0.60
    lgd_own: float = 0.60
    discount_rate: float = 0.035


@dataclass
class XVAResult:
    """Per-counterparty XVA breakdown."""
    counterparty: str
    cva: float
    dva: float
    fva: float
    colva: float
    mva: float
    net_xva: float                    # CVA - DVA + FVA + ColVA + MVA
    cds_hedge_pct: float = 0.0        # 0=naked, 1=fully hedged
    residual_after_hedge: float = 0.0


# ----- core XVA formulas ---------------------------------------------------

def _df(t: np.ndarray, r: float) -> np.ndarray:
    return np.exp(-r * t)


def _hazard_curve(cds_bps: float, lgd: float, t: np.ndarray) -> np.ndarray:
    """Standard CDS → hazard rate λ = s / (1 - R).  Survival S(t) = e^(-λt)."""
    s = cds_bps / 1e4 / max(lgd, 1e-6)
    return 1 - np.exp(-s * t)         # cumulative PD curve


def cva(epe: np.ndarray, t: np.ndarray, cds_bps: float, lgd: float,
        r: float = 0.035) -> float:
    """CVA = LGD · Σ EPE_i · (PD_i+1 - PD_i) · DF_i."""
    pd = _hazard_curve(cds_bps, lgd, t)
    df = _df(t, r)
    dpd = np.diff(pd, prepend=0)
    return float(lgd * (epe * dpd * df).sum())


def dva(ene: np.ndarray, t: np.ndarray, own_cds_bps: float, own_lgd: float,
        r: float = 0.035) -> float:
    """DVA mirrors CVA on the negative exposure side."""
    return cva(ene, t, own_cds_bps, own_lgd, r)


def fva(epe: np.ndarray, t: np.ndarray, funding_spread_bps: float,
        r: float = 0.035) -> float:
    """FVA = Σ EPE_i · (FundingSpread · Δt) · DF_i (uncollateralised funding)."""
    s = funding_spread_bps / 1e4
    df = _df(t, r)
    dt = np.diff(t, prepend=0)
    return float((epe * s * dt * df).sum())


def colva(epe: np.ndarray, ene: np.ndarray, t: np.ndarray,
          csa_spread_bps: float, r: float = 0.035) -> float:
    """ColVA — funding cost of collateral posted (net EPE side)."""
    s = csa_spread_bps / 1e4
    df = _df(t, r)
    dt = np.diff(t, prepend=0)
    net = np.maximum(epe - ene, 0)
    return float((net * s * dt * df).sum())


def mva(im_initial: float, t: np.ndarray, funding_spread_bps: float,
        r: float = 0.035) -> float:
    """MVA — funding cost of initial margin posted to clearinghouse.

    Assumes IM amortises linearly to zero over the trade life.
    """
    if im_initial <= 0 or len(t) == 0:
        return 0.0
    s = funding_spread_bps / 1e4
    df = _df(t, r)
    dt = np.diff(t, prepend=0)
    im_t = im_initial * (1 - t / t.max())
    return float((im_t * s * dt * df).sum())


def compute_xva(inputs: XVAInputs, *, counterparty: str = "") -> XVAResult:
    t = inputs.time_grid
    c = cva(inputs.epe_curve, t, inputs.cpty_cds_bps, inputs.lgd_cpty,
            inputs.discount_rate)
    d = dva(inputs.ene_curve, t, inputs.own_cds_bps, inputs.lgd_own,
            inputs.discount_rate)
    f = fva(inputs.epe_curve, t, inputs.funding_spread_bps,
            inputs.discount_rate)
    col = colva(inputs.epe_curve, inputs.ene_curve, t,
                inputs.csa_spread_bps, inputs.discount_rate)
    m = mva(inputs.im_initial_krw, t, inputs.funding_spread_bps,
            inputs.discount_rate)
    net = c - d + f + col + m
    return XVAResult(
        counterparty=counterparty, cva=c, dva=d, fva=f, colva=col, mva=m,
        net_xva=net,
    )


# ----- portfolio-level synthesis ------------------------------------------

def synthesise_xva_portfolio(
    bank_book: pd.DataFrame, *, seed: int = 42,
) -> list[XVAInputs]:
    """Build XVA inputs for each bank counterparty in the credit book.

    EPE/ENE curves are stylised: bell-shaped over the trade life, peaking
    around 60% of maturity (industry standard for cross-currency IRS).
    """
    rng = np.random.default_rng(seed + 1013)
    out: list[XVAInputs] = []
    for _, b in bank_book.iterrows():
        m = max(float(b.get("maturity", 3.0)), 0.5)
        n_pts = max(int(m * 4), 4)
        t = np.linspace(0.25, m, n_pts)
        notional = float(b["ead"])
        peak = 0.05 * notional
        epe = peak * np.exp(-((t - 0.6 * m) ** 2) / (0.4 * m ** 2))
        ene = 0.4 * epe                                # ENE smaller than EPE
        cpty_cds = float(rng.uniform(60, 250))         # 60–250 bps
        own_cds = 80.0                                  # KR bank ~80 bps
        funding = 50.0
        im = notional * 0.02 if rng.random() < 0.3 else 0.0   # 30% cleared
        out.append(XVAInputs(
            notional=notional, maturity_years=m,
            epe_curve=epe, ene_curve=ene, time_grid=t,
            cpty_cds_bps=cpty_cds, own_cds_bps=own_cds,
            funding_spread_bps=funding, csa_spread_bps=10,
            im_initial_krw=im,
        ))
    return out


@dataclass
class XVAPortfolio:
    by_cpty: pd.DataFrame             # per counterparty XVA components
    totals: dict[str, float]          # portfolio sums per XVA component
    net_xva_pl: float                 # CVA - DVA + FVA + ColVA + MVA
    cds_sensitivity_per_10bps: float  # ΔCVA per +10bps CDS shock
    epe_sensitivity_per_pct: float    # ΔCVA per +1% EPE shock
    hedge_residual_after_50pct: float


def compute_xva_portfolio(bank_book: pd.DataFrame, *,
                          seed: int = 42) -> XVAPortfolio:
    inputs = synthesise_xva_portfolio(bank_book, seed=seed)
    results = []
    for inp, (_, row) in zip(inputs, bank_book.iterrows()):
        r = compute_xva(inp, counterparty=str(row.get("obligor_id", "")))
        results.append({
            "counterparty": r.counterparty,
            "cva": r.cva, "dva": r.dva, "fva": r.fva,
            "colva": r.colva, "mva": r.mva, "net_xva": r.net_xva,
            "notional": inp.notional, "maturity": inp.maturity_years,
            "cpty_cds_bps": inp.cpty_cds_bps,
        })
    df = pd.DataFrame(results)
    totals = {k: float(df[k].sum()) for k in
              ("cva", "dva", "fva", "colva", "mva", "net_xva")}

    # sensitivity: CDS +10 bps
    bumped = [
        cva(inp.epe_curve, inp.time_grid, inp.cpty_cds_bps + 10,
            inp.lgd_cpty, inp.discount_rate)
        for inp in inputs
    ]
    cds_sens = float(np.sum(bumped) - totals["cva"])

    # sensitivity: EPE +1%
    bumped_epe = [
        cva(inp.epe_curve * 1.01, inp.time_grid, inp.cpty_cds_bps,
            inp.lgd_cpty, inp.discount_rate)
        for inp in inputs
    ]
    epe_sens = float(np.sum(bumped_epe) - totals["cva"])

    # 50% CDS hedge — residual
    residual = totals["cva"] * 0.5
    return XVAPortfolio(
        by_cpty=df, totals=totals, net_xva_pl=totals["net_xva"],
        cds_sensitivity_per_10bps=cds_sens,
        epe_sensitivity_per_pct=epe_sens,
        hedge_residual_after_50pct=residual,
    )
