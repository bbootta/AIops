"""LGD 모형 — workout LGD + beta(logit) 회귀 + 백테스트.

* :func:`workout_lgd` — 회수 cashflow → 실현 LGD (discounted).
* :class:`LGDModel` — logit-변환 LGD에 대한 ridge 회귀.  Beta regression의
  GLM 근사로, ``E[LGD] ≈ sigmoid(Xβ)`` 형태.  Floor 적용 후 [floor, 1]로
  클리핑한다.
* :func:`fit_lgd_model` — train DataFrame으로 회귀를 적합.
* :func:`lgd_backtest` — 예측 LGD vs 실현 LGD 검증.  MAE, RMSE, R², Brier,
  bias.  Basel CRE36 (LGD 모형 정합성) 및 BCBS WP 14 (LGD 검증) 준거.

수식
----
* LGD_realised = 1 - PV(recoveries - costs) / EAD_at_default
* y_logit = log(y/(1-y)) — y는 [eps, 1-eps]로 winsorise.
* Beta regression 근사: ridge α=1로 stabilise.
* R² = 1 - SSE/SST; SST는 (y - y_bar)^2의 합.
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
    alpha: float = 1.0,
) -> LGDModel:
    """Fit ridge regression on logit-transformed LGD (beta-regression approx).

    Notes
    -----
    Pure beta regression requires GLM with logit link and beta variance;
    we substitute a closed-form ridge on logit(y) to keep the harness
    dependency-light.  Empirically this matches beta regression closely
    when LGD is bounded away from 0/1 (which we ensure by clipping).
    """
    X = train[features].values
    y_raw = train[target].astype(float).values
    y_clip = np.clip(y_raw, 1e-3, 1 - 1e-3)
    y_logit = np.log(y_clip / (1 - y_clip))

    scaler = StandardScaler().fit(X)
    reg = Ridge(alpha=alpha, random_state=42).fit(scaler.transform(X), y_logit)
    return LGDModel(features=list(features), scaler=scaler, reg=reg, floor=floor)


def lgd_backtest(
    realised: np.ndarray,
    predicted: np.ndarray,
) -> dict[str, float]:
    """LGD 모형 사후 검증.

    반환 metric
    -----------
    * mae   — mean absolute error
    * rmse  — root mean squared error
    * r2    — coefficient of determination (1 - SSE/SST)
    * brier — Brier 점수(MSE).  LGD 회귀에서도 forecast error의 표준 지표.
    * bias  — mean(predicted - realised); 양수면 보수적 과대예측.
    * n     — 표본 수.
    """
    y = np.asarray(realised, dtype=float)
    p = np.asarray(predicted, dtype=float)
    n = len(y)
    if n == 0:
        return {"mae": float("nan"), "rmse": float("nan"), "r2": float("nan"),
                "brier": float("nan"), "bias": float("nan"), "n": 0}
    err = p - y
    mae = float(np.mean(np.abs(err)))
    mse = float(np.mean(err ** 2))
    rmse = float(np.sqrt(mse))
    sst = float(np.sum((y - y.mean()) ** 2))
    r2 = float(1.0 - n * mse / sst) if sst > 0 else float("nan")
    return {"mae": mae, "rmse": rmse, "r2": r2, "brier": mse,
            "bias": float(err.mean()), "n": int(n),
            "mean_realised": float(y.mean()),
            "mean_predicted": float(p.mean())}


def lgd_bucket_calibration(
    realised: np.ndarray,
    predicted: np.ndarray,
    n_bins: int = 10,
) -> pd.DataFrame:
    """LGD를 분위로 자른 후 bucket별 (mean_pred, mean_realised)."""
    y = np.asarray(realised, dtype=float)
    p = np.asarray(predicted, dtype=float)
    if len(y) == 0:
        return pd.DataFrame(columns=["bucket", "n", "mean_pred",
                                     "mean_realised", "bias"])
    order = np.argsort(p)
    p_s, y_s = p[order], y[order]
    edges = np.linspace(0, len(p_s), n_bins + 1, dtype=int)
    rows = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        if hi <= lo:
            continue
        rows.append({"bucket": i + 1, "n": int(hi - lo),
                     "mean_pred": float(p_s[lo:hi].mean()),
                     "mean_realised": float(y_s[lo:hi].mean()),
                     "bias": float(p_s[lo:hi].mean() - y_s[lo:hi].mean())})
    return pd.DataFrame(rows)
