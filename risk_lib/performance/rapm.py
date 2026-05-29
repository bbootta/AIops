"""Risk-Adjusted Performance Measurement (RAPM / RAROC).

RAROC = (Revenue - Operating Cost - Expected Loss + Capital Benefit) / Economic Capital

Where:
  Expected Loss EL = PD * LGD * EAD
  Economic Capital EC ≈ UL capital (use IRB K * EAD as approximation, or
                                   user-supplied EC factor).
  Capital Benefit  ≈ EC * risk_free_rate (income on the deployed capital).

Hurdle rate comparison: RAROC > cost of equity ⇒ value-creating.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from risk_lib.capital.rwa_irb import irb_capital_requirement, irb_k_vector


def economic_capital(
    pd_value: float,
    lgd: float,
    ead: float,
    asset_class: str = "corporate",
    maturity: float = 2.5,
) -> float:
    """EC ≈ IRB unexpected-loss capital."""
    k = irb_capital_requirement(pd_value, lgd, asset_class, maturity)
    return k * ead


def raroc(
    revenue: float,
    operating_cost: float,
    pd_value: float,
    lgd: float,
    ead: float,
    *,
    asset_class: str = "corporate",
    maturity: float = 2.5,
    risk_free_rate: float = 0.03,
    ec_override: float | None = None,
) -> dict[str, float]:
    """Single-exposure RAROC."""
    ec = ec_override if ec_override is not None else economic_capital(
        pd_value, lgd, ead, asset_class, maturity,
    )
    el = pd_value * lgd * ead
    cap_benefit = ec * risk_free_rate
    net = revenue - operating_cost - el + cap_benefit
    raroc_val = net / ec if ec > 0 else float("inf")
    return {
        "revenue": revenue,
        "operating_cost": operating_cost,
        "expected_loss": el,
        "capital_benefit": cap_benefit,
        "economic_capital": ec,
        "raroc": raroc_val,
    }


def rapm_report(
    portfolio: pd.DataFrame,
    *,
    hurdle_rate: float = 0.10,
    risk_free_rate: float = 0.03,
) -> pd.DataFrame:
    """Portfolio-level RAPM table.

    Required columns: exposure_id, asset_class, ead, pd, lgd, revenue,
                      operating_cost.  Optional: maturity.
    Adds: el, ec, raroc, value_added (raroc - hurdle) * ec, pass_hurdle.
    """
    required = {"exposure_id", "asset_class", "ead", "pd", "lgd",
                "revenue", "operating_cost"}
    missing = required - set(portfolio.columns)
    if missing:
        raise ValueError(f"portfolio missing columns: {missing}")

    df = portfolio
    maturity = (df["maturity"].to_numpy(dtype=float)
                if "maturity" in df.columns else np.full(len(df), 2.5))
    pd_v = df["pd"].to_numpy(dtype=float)
    lgd = df["lgd"].to_numpy(dtype=float)
    ead = df["ead"].to_numpy(dtype=float)
    revenue = df["revenue"].to_numpy(dtype=float)
    op_cost = df["operating_cost"].to_numpy(dtype=float)

    el = pd_v * lgd * ead
    ec = irb_k_vector(pd_v, lgd, df["asset_class"].to_numpy(), maturity) * ead
    cap_benefit = ec * risk_free_rate
    net = revenue - op_cost - el + cap_benefit
    with np.errstate(divide="ignore", invalid="ignore"):
        raroc_v = np.where(ec > 0, net / ec, np.inf)

    out = pd.DataFrame({
        "exposure_id": df["exposure_id"].to_numpy(),
        "revenue": revenue,
        "operating_cost": op_cost,
        "expected_loss": el,
        "capital_benefit": cap_benefit,
        "economic_capital": ec,
        "raroc": raroc_v,
    })
    out["value_added"] = (out["raroc"] - hurdle_rate) * out["economic_capital"]
    out["pass_hurdle"] = out["raroc"] >= hurdle_rate
    return out
