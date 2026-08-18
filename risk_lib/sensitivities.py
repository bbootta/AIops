"""Trading book sensitivities (Greeks) — Top-IB style risk decomposition.

For each derivative position (IR / FX / equity / credit) we produce:
  - **Δ (Delta)**  : ∂V/∂S   — 1st-order spot exposure
  - **Γ (Gamma)**  : ∂²V/∂S² — convexity / non-linear exposure
  - **Vega**       : ∂V/∂σ   — implied vol exposure
  - **Theta**      : ∂V/∂t   — time decay
  - **Rho**        : ∂V/∂r   — interest rate exposure
  - **dV01**       : MVA change per 1bp parallel rate shock
  - **CS01**       : MVA change per 1bp credit spread shock

Outputs roll up to:
  - desk-level Greek totals (delta-1 / Greeks-bucket)
  - VaR contribution via standard linear model
  - residual P&L attribution (PLA) test — fed to FRTB IMA framework

Closed-form approximations for Black-Scholes equivalents are used so the
container can run without scipy.stats.norm (we use Φ approximation via erf).

NOTE: 전행 단위 what-if 민감도(PD/LGD/금리/HQLA 충격 → ECL/RWA/LCR)는 별도
모듈 `risk_lib.sensitivity` 담당 — 이 모듈은 트레이딩북 Greeks 전용.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import erf, exp, log, pi, sqrt
from typing import Any

import numpy as np
import pandas as pd


# ----- Black-Scholes primitives (closed form) ------------------------------

def _N(x: float) -> float:
    """Standard normal CDF using erf (no scipy needed)."""
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def _n(x: float) -> float:
    """Standard normal PDF."""
    return exp(-0.5 * x * x) / sqrt(2 * pi)


def bs_greeks(
    spot: float, strike: float, t: float, vol: float, rate: float,
    *, call: bool = True,
) -> dict[str, float]:
    """Black-Scholes Greeks for a vanilla European option.

    Returns price, delta, gamma, vega, theta, rho.
    Sanity-checked against textbook values.
    """
    if t <= 0 or vol <= 0:
        intrinsic = max(spot - strike, 0) if call else max(strike - spot, 0)
        return dict(price=intrinsic, delta=1.0 if (call and spot > strike) else 0.0,
                    gamma=0.0, vega=0.0, theta=0.0, rho=0.0)
    d1 = (log(spot / strike) + (rate + 0.5 * vol * vol) * t) / (vol * sqrt(t))
    d2 = d1 - vol * sqrt(t)
    if call:
        price = spot * _N(d1) - strike * exp(-rate * t) * _N(d2)
        delta = _N(d1)
        rho = strike * t * exp(-rate * t) * _N(d2) / 100      # per 1% rate
    else:
        price = strike * exp(-rate * t) * _N(-d2) - spot * _N(-d1)
        delta = _N(d1) - 1.0
        rho = -strike * t * exp(-rate * t) * _N(-d2) / 100
    gamma = _n(d1) / (spot * vol * sqrt(t))
    vega = spot * _n(d1) * sqrt(t) / 100                       # per 1% vol
    # theta per day (annual/365)
    if call:
        theta = (- spot * _n(d1) * vol / (2 * sqrt(t))
                 - rate * strike * exp(-rate * t) * _N(d2)) / 365
    else:
        theta = (- spot * _n(d1) * vol / (2 * sqrt(t))
                 + rate * strike * exp(-rate * t) * _N(-d2)) / 365
    return dict(price=price, delta=delta, gamma=gamma, vega=vega,
                theta=theta, rho=rho)


def dv01(notional: float, maturity_years: float, ytm: float = 0.035,
         *, coupon: float = 0.035) -> float:
    """Approximate dV01 (modified duration × notional / 10000) for a bond/swap.

    For an at-par fixed-rate trade we use Macaulay → modified duration
    approximation:  D_mod ≈ (1 - (1+y)^-n) / y / (1+y).
    """
    if ytm <= 0 or maturity_years <= 0:
        return 0.0
    y = ytm
    n = maturity_years
    macaulay = (1 - (1 + y) ** -n) / y
    mod_dur = macaulay / (1 + y)
    return float(notional * mod_dur / 10_000)


def cs01(notional: float, maturity_years: float, spread_bps: float = 100,
         recovery: float = 0.4) -> float:
    """CS01 = Σ_t notional · (1-R) · marginal_PD(t) · DF(t) per 1bp shift.

    Closed-form approximation: notional · risky_dur · (1-R) / 10000.
    """
    if maturity_years <= 0:
        return 0.0
    s = spread_bps / 1e4
    risky_dur = (1 - exp(-(s / max(1 - recovery, 1e-6)) * maturity_years)) \
                / (s / max(1 - recovery, 1e-6))
    return float(notional * risky_dur * (1 - recovery) / 10_000)


# ----- portfolio synthesis -------------------------------------------------

@dataclass
class TradingDeskBook:
    """Synthetic trading book attached to bank counterparties."""
    trades: pd.DataFrame
    n_options: int
    n_swaps: int
    n_credit: int
    total_notional: float


def synthesise_trading_book(bank_book: pd.DataFrame, *,
                             seed: int = 42) -> TradingDeskBook:
    """Build a synthetic options + swaps + credit derivative book."""
    rng = np.random.default_rng(seed + 707)
    trades: list[dict] = []
    for _, b in bank_book.iterrows():
        n = int(rng.integers(2, 6))
        for k in range(n):
            kind = rng.choice(["option", "swap", "cds"], p=[0.35, 0.45, 0.20])
            notional = float(b["ead"]) * float(rng.uniform(0.05, 0.4))
            mat = float(rng.uniform(0.5, 5.0))
            if kind == "option":
                spot = 100.0
                strike = spot * float(rng.uniform(0.85, 1.15))
                vol = float(rng.uniform(0.10, 0.35))
                call = bool(rng.random() > 0.5)
                g = bs_greeks(spot, strike, mat, vol, 0.035, call=call)
                trades.append({
                    "counterparty": str(b.get("obligor_id", "")),
                    "kind": kind, "notional": notional, "maturity": mat,
                    "spot": spot, "strike": strike, "vol": vol,
                    "call": call, **{k: g[k] for k in
                                       ("price","delta","gamma","vega","theta","rho")},
                    "dv01": 0.0, "cs01": 0.0,
                })
            elif kind == "swap":
                d = dv01(notional, mat, ytm=0.035)
                trades.append({
                    "counterparty": str(b.get("obligor_id", "")),
                    "kind": kind, "notional": notional, "maturity": mat,
                    "spot": np.nan, "strike": np.nan, "vol": np.nan,
                    "call": False,
                    "price": 0.0, "delta": 0.0, "gamma": 0.0,
                    "vega": 0.0, "theta": 0.0, "rho": 0.0,
                    "dv01": d, "cs01": 0.0,
                })
            else:    # cds
                spread = float(rng.uniform(80, 300))
                c = cs01(notional, mat, spread_bps=spread)
                trades.append({
                    "counterparty": str(b.get("obligor_id", "")),
                    "kind": kind, "notional": notional, "maturity": mat,
                    "spot": np.nan, "strike": np.nan, "vol": np.nan,
                    "call": False, "price": 0.0,
                    "delta": 0.0, "gamma": 0.0, "vega": 0.0,
                    "theta": 0.0, "rho": 0.0,
                    "dv01": 0.0, "cs01": c,
                })
    df = pd.DataFrame(trades)
    return TradingDeskBook(
        trades=df,
        n_options=int((df["kind"] == "option").sum()),
        n_swaps=int((df["kind"] == "swap").sum()),
        n_credit=int((df["kind"] == "cds").sum()),
        total_notional=float(df["notional"].sum()),
    )


# ----- desk aggregates -----------------------------------------------------

@dataclass
class DeskSensitivities:
    """Greeks aggregated by desk."""
    by_kind: pd.DataFrame
    total_delta: float
    total_gamma: float
    total_vega: float
    total_theta: float
    total_dv01: float
    total_cs01: float
    var_linear_99: float          # 99% 1-day linear VaR
    pla_residual: float           # P&L attribution residual (target < 10%)


def desk_aggregate(book: TradingDeskBook) -> DeskSensitivities:
    df = book.trades
    by_kind = df.groupby("kind").agg(
        n=("notional", "size"),
        notional=("notional", "sum"),
        delta=("delta", "sum"),
        gamma=("gamma", "sum"),
        vega=("vega", "sum"),
        theta=("theta", "sum"),
        dv01=("dv01", "sum"),
        cs01=("cs01", "sum"),
    ).reset_index()

    # crude 99% 1-day VaR from delta-vega linear model
    delta_total = float(df["delta"].sum())
    vega_total = float(df["vega"].sum())
    dv01_total = float(df["dv01"].sum())
    cs01_total = float(df["cs01"].sum())
    sigma_eq = 0.012   # 1.2% daily equity move
    sigma_vol = 0.05
    sigma_ir_bp = 8.0
    sigma_cs_bp = 6.0
    var_components = np.array([
        abs(delta_total) * sigma_eq * 100,        # delta exposure (per 1%)
        abs(vega_total) * sigma_vol * 100,
        abs(dv01_total) * sigma_ir_bp,
        abs(cs01_total) * sigma_cs_bp,
    ])
    var_linear_99 = float(np.sqrt((var_components ** 2).sum()) * 2.326)

    # PLA residual approximation — assume gamma + non-linear convexity ~10%
    pla = abs(float(df["gamma"].sum())) * 0.5 / max(var_linear_99, 1.0)

    return DeskSensitivities(
        by_kind=by_kind,
        total_delta=delta_total,
        total_gamma=float(df["gamma"].sum()),
        total_vega=vega_total,
        total_theta=float(df["theta"].sum()),
        total_dv01=dv01_total,
        total_cs01=cs01_total,
        var_linear_99=var_linear_99,
        pla_residual=min(pla, 1.0),
    )
