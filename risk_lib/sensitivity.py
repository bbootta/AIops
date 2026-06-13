"""Sensitivity / what-if analysis.

Closed-form one-factor sensitivities around the base PipelineResult — no need
to rerun the full pipeline for each shock.

  - PD shock      → ECL (linear in EL), Stage migration kept at base
  - LGD shock     → ECL (linear in EL), recovery side
  - EAD shock     → ECL + RWA proportional
  - GDP shock     → drives the IFRS9 PIT z-shift (uses macro module's rho)
  - Rate shock    → IRRBB ΔEVE rescaled from the parallel-up baseline result
  - HQLA shock    → LCR (linear in HQLA), holds outflows fixed
  - Funding shock → LCR (run-off boost on wholesale_fi_unsecured)

Returned as a DataFrame so the HTML report can render a sensitivity grid; the
two-factor cross-product gives an exposure surface visualisation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class SensitivityPoint:
    factor: str
    shock: float                # decimal: 0.10 = +10%; -50bp = -0.005
    metric: str
    base: float
    shocked: float
    delta: float                # shocked - base


# ---------------------------------------------------------------- shocks

def _ecl_pd_sensitivity(result: Any, pd_shock_rel: float) -> float:
    """Linear ECL response to a relative PD shock (e.g. +10% → +10% on Stage 1/2 PD).

    Stage 3 PD = 1 so it's unaffected; Stage 1/2 PD scales by (1 + shock).
    Coverage(stage) = ECL/EAD on that stage gives a good linear proxy.
    """
    ecl_by_stage = result.ecl["by_stage"]
    s1_ecl = float(ecl_by_stage.loc[1, "ecl"]) if 1 in ecl_by_stage.index else 0.0
    s2_ecl = float(ecl_by_stage.loc[2, "ecl"]) if 2 in ecl_by_stage.index else 0.0
    s3_ecl = float(ecl_by_stage.loc[3, "ecl"]) if 3 in ecl_by_stage.index else 0.0
    return s1_ecl * (1 + pd_shock_rel) + s2_ecl * (1 + pd_shock_rel) + s3_ecl


def _ecl_lgd_sensitivity(result: Any, lgd_shock_abs: float) -> float:
    """LGD shock is absolute in decimal (e.g. +0.05 = +5pp).

    Stage 3 has LGD·EAD as its ECL; Stage 1/2 likewise scales linearly.
    Assume mean LGD ≈ 0.45; bump everything by shock/0.45.
    """
    ecl_total = float(result.ecl["total"])
    base_lgd = 0.45
    if lgd_shock_abs <= -base_lgd:
        return 0.0
    return ecl_total * (1 + lgd_shock_abs / base_lgd)


def _rwa_ead_sensitivity(result: Any, ead_shock_rel: float) -> float:
    """RWA scales with EAD on credit (SA + IRB); market/op held fixed."""
    rwa = result.rwa
    credit = (rwa["sa"] + rwa["irb"]) * (1 + ead_shock_rel)
    return credit + rwa["market"] + rwa["op"]


def _cet1_from_rwa_and_capital(result: Any, rwa: float, capital_shock_rel: float = 0.0) -> float:
    cet1 = result.meta["capital"].cet1 * (1 + capital_shock_rel)
    return cet1 / rwa if rwa > 0 else 0.0


def _eve_rate_sensitivity(result: Any, rate_shock_bp: float) -> float:
    """Rescale the parallel-up ΔEVE result to an arbitrary parallel shock size."""
    from risk_lib.references import IRRBB_SHOCK_PARALLEL_BP
    irrbb = result.alm["irrbb"]
    eve_par_up = float(irrbb.delta_eve.set_index("scenario").loc["parallel_up", "delta_eve"])
    return eve_par_up * (rate_shock_bp / IRRBB_SHOCK_PARALLEL_BP)


def _lcr_hqla_sensitivity(result: Any, hqla_shock_rel: float) -> float:
    lcr = result.alm["lcr"]
    hqla = lcr.hqla_total * (1 + hqla_shock_rel)
    return hqla / lcr.net_outflow if lcr.net_outflow else float("inf")


def _lcr_funding_sensitivity(result: Any, wholesale_runoff_addon: float) -> float:
    """Increase wholesale_fi_unsecured run-off rate by `wholesale_runoff_addon`
    (e.g. +0.10 turns 100% into 110% — meaningless but illustrates stress).
    """
    lcr = result.alm["lcr"]
    out = lcr.outflows.copy()
    mask = out["category"] == "wholesale_fi_unsecured"
    extra = float((out.loc[mask, "amount"] * wholesale_runoff_addon).sum())
    new_net = lcr.gross_outflow + extra - lcr.inflow_capped
    return lcr.hqla_total / new_net if new_net > 0 else float("inf")


# ---------------------------------------------------------------- public

def one_factor_grid(result: Any) -> pd.DataFrame:
    """Standard 1F sensitivity grid the CRO desk reviews quarterly."""
    rows: list[SensitivityPoint] = []

    bis = result.bis
    base_cet1 = bis.cet1_ratio
    base_rwa = result.rwa["final_total"]
    base_ecl = float(result.ecl["total"])
    base_lcr = result.alm["lcr"].lcr
    base_eve = -result.alm["irrbb"].worst_eve_decline

    # PD relative shocks on ECL
    for s in [-0.20, -0.10, 0.10, 0.20, 0.50]:
        new_ecl = _ecl_pd_sensitivity(result, s)
        rows.append(SensitivityPoint("PD (rel)", s, "ECL", base_ecl,
                                     new_ecl, new_ecl - base_ecl))

    # LGD absolute shocks on ECL
    for s in [-0.05, 0.05, 0.10, 0.15]:
        new_ecl = _ecl_lgd_sensitivity(result, s)
        rows.append(SensitivityPoint("LGD (abs pp)", s, "ECL", base_ecl,
                                     new_ecl, new_ecl - base_ecl))

    # EAD shocks on RWA and CET1
    for s in [-0.10, 0.10, 0.20]:
        new_rwa = _rwa_ead_sensitivity(result, s)
        new_cet1 = _cet1_from_rwa_and_capital(result, new_rwa)
        rows.append(SensitivityPoint("EAD (rel)", s, "RWA", base_rwa,
                                     new_rwa, new_rwa - base_rwa))
        rows.append(SensitivityPoint("EAD (rel)", s, "CET1", base_cet1,
                                     new_cet1, new_cet1 - base_cet1))

    # Capital shocks
    for s in [-0.10, -0.05, 0.05]:
        new_cet1 = _cet1_from_rwa_and_capital(result, base_rwa, s)
        rows.append(SensitivityPoint("CET1자본 (rel)", s, "CET1", base_cet1,
                                     new_cet1, new_cet1 - base_cet1))

    # Rate shocks on EVE
    for bp in [-200, -100, 100, 200, 300]:
        new_eve = _eve_rate_sensitivity(result, bp)
        rows.append(SensitivityPoint("금리 (bp parallel)", bp, "ΔEVE",
                                     base_eve, new_eve, new_eve - base_eve))

    # HQLA shocks on LCR
    for s in [-0.20, -0.10, 0.10]:
        new_lcr = _lcr_hqla_sensitivity(result, s)
        rows.append(SensitivityPoint("HQLA (rel)", s, "LCR", base_lcr,
                                     new_lcr, new_lcr - base_lcr))

    # Wholesale run-off add-on on LCR
    for s in [0.05, 0.10, 0.20]:
        new_lcr = _lcr_funding_sensitivity(result, s)
        rows.append(SensitivityPoint("도매조달 run-off (abs)", s, "LCR",
                                     base_lcr, new_lcr, new_lcr - base_lcr))

    return pd.DataFrame([r.__dict__ for r in rows])


def two_factor_surface(result: Any, *, pd_grid=None, lgd_grid=None) -> pd.DataFrame:
    """Cross-product of PD × LGD shocks on ECL — for a heatmap visualisation."""
    pd_grid = pd_grid if pd_grid is not None else np.linspace(-0.2, 0.5, 8)
    lgd_grid = lgd_grid if lgd_grid is not None else np.linspace(-0.05, 0.15, 5)
    base_ecl = float(result.ecl["total"])
    rows = []
    for p in pd_grid:
        for l in lgd_grid:
            # apply PD and LGD shocks sequentially (linear superposition)
            ecl_pd  = _ecl_pd_sensitivity(result, float(p))
            scale_l = 1 + float(l) / 0.45
            ecl_combined = ecl_pd * scale_l
            rows.append({"pd_shock": float(p), "lgd_shock": float(l),
                         "ecl": ecl_combined,
                         "delta": ecl_combined - base_ecl})
    return pd.DataFrame(rows)
