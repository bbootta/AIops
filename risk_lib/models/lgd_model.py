"""LGD modeling.

Two paths:
  - workout_lgd(): present-value workout LGD from recovery cashflows.
  - LGDModel: simple beta-regression style point estimator over collateral &
    seniority features.  Returns LGD clipped to [floor, 1].
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


def workout_lgd(
    ead_at_default: float,
    recoveries: list[tuple[float, float]],  # (years_since_default, amount)
    workout_costs: float = 0.0,
    discount_rate: float = 0.05,
) -> float:
    """Compute realised LGD from observed workout cashflows.

    LGD = 1 - PV(recoveries - costs) / EAD_at_default
    """
    if ead_at_default <= 0:
        raise ValueError("ead_at_default must be > 0")
    pv = -workout_costs  # initial cost at t=0
    for t, amt in recoveries:
        pv += amt / ((1 + discount_rate) ** max(t, 0.0))
    lgd = 1.0 - pv / ead_at_default
    return float(np.clip(lgd, 0.0, 1.0))


@dataclass
class LGDModel:
    features: list[str]
    scaler: StandardScaler
    reg: Ridge
    floor: float = 0.05

    def predict_lgd(self, X: pd.DataFrame) -> np.ndarray:
        Xs = self.scaler.transform(X[self.features].values)
        raw = self.reg.predict(Xs)
        # logistic squash to [0,1], then floor
        lgd = 1.0 / (1.0 + np.exp(-raw))
        return np.clip(lgd, self.floor, 1.0)


def fit_lgd_model(
    train: pd.DataFrame,
    features: list[str],
    target: str = "lgd_realized",
    floor: float = 0.05,
) -> LGDModel:
    """Fit ridge regression on logit-transformed LGD."""
    X = train[features].values
    y_raw = train[target].astype(float).values
    y_clip = np.clip(y_raw, 1e-3, 1 - 1e-3)
    y_logit = np.log(y_clip / (1 - y_clip))

    scaler = StandardScaler().fit(X)
    reg = Ridge(alpha=1.0).fit(scaler.transform(X), y_logit)
    return LGDModel(features=list(features), scaler=scaler, reg=reg, floor=floor)
