"""Basic OLS regression diagnostics for scenario / PD multiplier models."""
from __future__ import annotations

from typing import Dict, Mapping

import numpy as np
import pandas as pd


def _to_xy(y, X):
    y_arr = np.asarray(y, dtype=float).reshape(-1)
    X_df = pd.DataFrame(X).copy()
    if y_arr.shape[0] != X_df.shape[0]:
        raise ValueError("y and X length mismatch.")
    if X_df.empty:
        raise ValueError("X is empty.")
    if X_df.isna().any().any() or np.isnan(y_arr).any():
        raise ValueError("Inputs contain NaN.")
    return y_arr, X_df


def calculate_vif(X: pd.DataFrame) -> pd.DataFrame:
    """VIF for each column. Uses statsmodels if available, falls back to OLS-by-hand."""
    Xdf = pd.DataFrame(X).copy()
    if Xdf.shape[1] < 2:
        raise ValueError("VIF requires at least 2 columns.")
    if Xdf.isna().any().any():
        raise ValueError("X contains NaN.")
    cols = list(Xdf.columns)
    rows = []
    try:
        from statsmodels.stats.outliers_influence import variance_inflation_factor
        import statsmodels.api as sm

        Xc = sm.add_constant(Xdf, has_constant="add")
        for i, c in enumerate(cols):
            vif = float(variance_inflation_factor(Xc.values, i + 1))
            rows.append({"variable": c, "vif": vif})
    except Exception:
        for c in cols:
            others = [x for x in cols if x != c]
            X_others = Xdf[others].values
            y_target = Xdf[c].values
            X_des = np.column_stack([np.ones(X_others.shape[0]), X_others])
            beta, *_ = np.linalg.lstsq(X_des, y_target, rcond=None)
            yhat = X_des @ beta
            ss_res = float(np.sum((y_target - yhat) ** 2))
            ss_tot = float(np.sum((y_target - y_target.mean()) ** 2))
            r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
            vif = 1.0 / (1.0 - r2) if r2 < 1 else float("inf")
            rows.append({"variable": c, "vif": float(vif)})
    return pd.DataFrame(rows)


def fit_ols(y, X):
    """Fit an OLS model. Returns a statsmodels result.

    Prefers statsmodels; if unavailable, raises ImportError.
    """
    y_arr, X_df = _to_xy(y, X)
    import statsmodels.api as sm

    Xc = sm.add_constant(X_df, has_constant="add")
    return sm.OLS(y_arr, Xc).fit()


def extract_regression_summary(model_result) -> dict:
    """Extract R2, adj R2, n, k, params, pvalues from statsmodels result."""
    return {
        "n": int(model_result.nobs),
        "k": int(len(model_result.params) - 1),
        "r_squared": float(model_result.rsquared),
        "adj_r_squared": float(model_result.rsquared_adj),
        "params": {k: float(v) for k, v in model_result.params.items()},
        "pvalues": {k: float(v) for k, v in model_result.pvalues.items()},
        "f_pvalue": float(getattr(model_result, "f_pvalue", float("nan"))),
    }


def check_pvalues(model_result, threshold: float = 0.05) -> pd.DataFrame:
    """Per-variable p-value vs threshold."""
    rows = []
    for var, p in model_result.pvalues.items():
        rows.append(
            {
                "variable": var,
                "pvalue": float(p),
                "significant_at_threshold": bool(p < threshold),
                "threshold": threshold,
            }
        )
    return pd.DataFrame(rows)


def check_coefficient_signs(
    model_result, expected_signs: Mapping[str, str]
) -> pd.DataFrame:
    """Compare coefficient signs against expected ('+', '-', or 'any')."""
    rows = []
    for var, exp in expected_signs.items():
        if var not in model_result.params:
            rows.append(
                {"variable": var, "coef": None, "expected": exp, "match": None}
            )
            continue
        coef = float(model_result.params[var])
        if exp == "+":
            match = coef > 0
        elif exp == "-":
            match = coef < 0
        elif exp == "any":
            match = True
        else:
            raise ValueError(f"expected_signs must be '+', '-', or 'any'; got {exp}")
        rows.append(
            {"variable": var, "coef": coef, "expected": exp, "match": bool(match)}
        )
    return pd.DataFrame(rows)


def check_condition_index(X) -> dict:
    """Condition index from singular values of standardized X."""
    Xdf = pd.DataFrame(X).copy()
    if Xdf.empty or Xdf.shape[1] < 1:
        raise ValueError("X is empty.")
    if Xdf.isna().any().any():
        raise ValueError("X contains NaN.")
    Xs = (Xdf - Xdf.mean()) / Xdf.std(ddof=0).replace(0, np.nan)
    Xs = Xs.dropna(axis=1, how="any")
    if Xs.shape[1] == 0:
        raise ValueError("All columns have zero variance.")
    sv = np.linalg.svd(Xs.values, compute_uv=False)
    sv = sv[sv > 0]
    if sv.size == 0:
        raise ValueError("No positive singular values.")
    cond_indices = sv.max() / sv
    return {
        "max_condition_index": float(cond_indices.max()),
        "all_condition_indices": [float(x) for x in cond_indices.tolist()],
    }


def check_residual_basic(model_result) -> dict:
    """Basic residual statistics: mean, std, min, max, and a normality cue."""
    res = np.asarray(model_result.resid, dtype=float)
    out = {
        "n": int(res.shape[0]),
        "mean": float(res.mean()),
        "std": float(res.std(ddof=1)) if res.shape[0] > 1 else float("nan"),
        "min": float(res.min()),
        "max": float(res.max()),
    }
    try:
        from scipy.stats import jarque_bera

        jb_stat, jb_p = jarque_bera(res)
        out["jarque_bera_stat"] = float(jb_stat)
        out["jarque_bera_pvalue"] = float(jb_p)
    except Exception:
        out["jarque_bera_stat"] = None
        out["jarque_bera_pvalue"] = None
    return out
