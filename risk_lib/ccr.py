"""Counterparty Credit Risk (CCR) — simplified SA-CCR + CVA.

Basel III CRE52 (SA-CCR) and CRE50.6 (CVA capital charge, simplified BA-CVA).

This is an MVP sized for portfolios that don't carry explicit derivative
data: it synthesises a small derivatives book attached to the bank
counterparties already present in the credit portfolio so the CRO has
visible CCR / CVA numbers in the report.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from risk_lib.references import (
    BA_CVA_KAPPA, CCR_BANK_RW_FLAT, SACCR_SF_CREDIT_IG_PROXY,
)


# SA-CCR 감독계수 (CRE52.72). ir·fx·equity(단일명)·commodity 는 규정표 그대로다.
# credit_ig 만 규정표에 없는 대표값이다. 단일명 IG 는 등급별 0.38~0.54%, 지수 IG 는
# 0.38% 인데 상대방 등급을 쓰지 않아 구간 안의 값 하나를 놓았다 (references 참조).
SF = {
    "ir": 0.005,        # interest rate
    "fx": 0.040,        # FX
    "credit_ig": SACCR_SF_CREDIT_IG_PROXY,
    "equity": 0.32,
    "commodity": 0.18,
}


@dataclass
class SACCRResult:
    by_counterparty: pd.DataFrame   # counterparty, asset_class, ead, rwa, k
    ead_total: float
    rwa_total: float
    cva_charge: float
    n_counterparties: int


def synthesise_derivatives(bank_book: pd.DataFrame, *, seed: int = 42) -> pd.DataFrame:
    """Attach a small derivatives book to each bank counterparty."""
    rng = np.random.default_rng(seed + 909)
    rows = []
    asset_classes = ["ir", "fx", "credit_ig", "equity"]
    for _, b in bank_book.iterrows():
        n_trades = int(rng.integers(1, 5))
        for k in range(n_trades):
            ac = rng.choice(asset_classes, p=[0.55, 0.25, 0.12, 0.08])
            notional = float(b["ead"]) * rng.uniform(0.05, 0.3)
            maturity = rng.uniform(0.5, 5.0)
            mtm = notional * rng.normal(0.005, 0.02)
            rows.append({"counterparty": b["obligor_id"],
                         "asset_class": ac,
                         "notional": notional,
                         "mtm": mtm,
                         "maturity": maturity,
                         "collateral": notional * rng.uniform(0, 0.5)})
    return pd.DataFrame(rows)


def saccr_ead(trades: pd.DataFrame) -> pd.DataFrame:
    """Compute SA-CCR EAD = α · (RC + PFE), α = 1.4 (CRE52.4).

    Per counterparty: RC = max(V - C, 0); PFE = aggregated add-on by asset
    class with the supervisory factor × maturity factor.
    """
    df = trades.copy()
    df["maturity_factor"] = np.sqrt(np.minimum(df["maturity"], 1.0))
    df["add_on"] = df.apply(
        lambda r: SF[r["asset_class"]] * r["notional"] * r["maturity_factor"],
        axis=1)
    grouped = df.groupby("counterparty").agg(
        v=("mtm", "sum"), c=("collateral", "sum"),
        pfe=("add_on", "sum")).reset_index()
    grouped["rc"] = (grouped["v"] - grouped["c"]).clip(lower=0)
    grouped["ead"] = 1.4 * (grouped["rc"] + grouped["pfe"])
    return grouped


def saccr_rwa(ead: pd.DataFrame, bank_rw: float = CCR_BANK_RW_FLAT) -> pd.DataFrame:
    """RWA = EAD × 상대방 위험가중치.

    CRE20.18 은 등급별(20/30/50/100/150%)이다. 이 하네스는 상대방 등급을 쓰지
    않고 BBB 구간 50% 하나를 전 상대방에 놓는다 (내부 가정, references 참조).
    """
    out = ead.copy()
    out["rw"] = bank_rw
    out["rwa"] = out["ead"] * bank_rw
    out["k"] = out["rwa"] * 0.08
    return out


# CVA 소요자기자본을 위험가중자산으로 환산하는 배수. 최저자기자본비율 8%의
# 역수이며, Basel은 소요자본 기준으로 산출되는 항목(CVA·시장·운영)을 RWA에
# 합산할 때 이 배수를 쓴다 (MAR50.2 · RBC20.6).
CVA_RWA_MULTIPLIER = 12.5


def cva_capital_charge(ead: pd.DataFrame, *, kappa: float = BA_CVA_KAPPA) -> float:
    """Simplified BA-CVA: K_BA = κ · √(Σ (S_i · EAD_i)²) — supervisory weights
    folded into κ for an MVP; ~5% of total EAD typical.

    반환값은 **소요자기자본(K)**이지 위험가중자산이 아니다. RWA로 합산하려면
    `cva_rwa()`를 쓴다 — 파이프라인이 K를 그대로 RWA에 더하면 CVA가 12.5배
    과소계상된다.
    """
    return float(kappa * np.sqrt((ead["ead"] ** 2).sum()))


def cva_rwa(charge: float) -> float:
    """CVA 소요자기자본 → 위험가중자산 (MAR50.2 · RBC20.6)."""
    return float(charge) * CVA_RWA_MULTIPLIER


def compute_ccr(bank_book: pd.DataFrame, *, seed: int = 42) -> SACCRResult:
    trades = synthesise_derivatives(bank_book, seed=seed)
    if trades.empty:
        return SACCRResult(pd.DataFrame(), 0.0, 0.0, 0.0, 0)
    ead = saccr_ead(trades)
    rwa = saccr_rwa(ead)
    cva = cva_capital_charge(ead)
    return SACCRResult(
        by_counterparty=rwa,
        ead_total=float(rwa["ead"].sum()),
        rwa_total=float(rwa["rwa"].sum()),
        cva_charge=cva,
        n_counterparties=int(rwa.shape[0]),
    )
