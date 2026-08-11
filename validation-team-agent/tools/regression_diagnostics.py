"""회귀/시계열 모형 진단 보조 함수.

다중공선성 (VIF), OLS 요약, 잔차 기초 진단, 단위근 / 정상성 검정을 제공한다.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tsa.stattools import adfuller, kpss


def calculate_vif(df: pd.DataFrame) -> pd.DataFrame:
    """수치형 변수의 VIF를 반환한다.

    상수항이 없으면 자동으로 추가된다 (VIF 계산 안정성). 결과에서는 상수항을 제외한다.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    if df.shape[1] == 0:
        raise ValueError("df must have at least one column")
    if df.isna().any().any():
        raise ValueError("VIF requires non-null values")
    if df.shape[0] <= df.shape[1]:
        raise ValueError("rows must exceed number of variables")

    X = sm.add_constant(df.astype(float), has_constant="add")
    rows = []
    for i, col in enumerate(X.columns):
        if col == "const":
            continue
        rows.append({"variable": col, "vif": float(variance_inflation_factor(X.values, i))})
    return pd.DataFrame(rows)


def regression_summary(y: Iterable, X: pd.DataFrame) -> dict:
    """OLS 적합 결과 요약.

    반환 dict 키: params, rsquared, adj_rsquared, n_obs, df_resid
    """
    y_arr = np.asarray(list(y), dtype=float)
    if not isinstance(X, pd.DataFrame):
        raise TypeError("X must be a pandas DataFrame")
    if y_arr.shape[0] != X.shape[0]:
        raise ValueError("y and X length mismatch")
    if X.isna().any().any() or np.isnan(y_arr).any():
        raise ValueError("OLS requires non-null values")

    X_const = sm.add_constant(X.astype(float), has_constant="add")
    model = sm.OLS(y_arr, X_const).fit()
    return {
        "params": model.params.to_dict(),
        "rsquared": float(model.rsquared),
        "adj_rsquared": float(model.rsquared_adj),
        "n_obs": int(model.nobs),
        "df_resid": int(model.df_resid),
    }


def check_residual_basic(model_result) -> dict:
    """statsmodels OLS 결과의 잔차에 대한 기본 진단 통계.

    반환 dict 키: mean, std, skew, kurtosis, durbin_watson
    """
    if not hasattr(model_result, "resid"):
        raise TypeError("model_result must be a fitted statsmodels result")

    resid = np.asarray(model_result.resid, dtype=float)
    if resid.size < 3:
        raise ValueError("residual length too small for diagnostics")
    s = pd.Series(resid)
    from statsmodels.stats.stattools import durbin_watson

    return {
        "mean": float(s.mean()),
        "std": float(s.std(ddof=1)),
        "skew": float(s.skew()),
        "kurtosis": float(s.kurtosis()),
        "durbin_watson": float(durbin_watson(resid)),
    }


def adf_test(series: Iterable, regression: str = "c", alpha: float = 0.05) -> dict:
    """ADF 단위근 검정. H0: 단위근 존재(비정상). reject_h0=True 이면 정상.

    regression: "c" (상수), "ct" (상수+추세), "ctt", "n"
    """
    arr = np.asarray(list(series), dtype=float)
    if arr.size < 10:
        raise ValueError("series too short for ADF (need >= 10 obs)")
    if np.isnan(arr).any():
        raise ValueError("NaN not allowed in series")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")

    stat, pval, lag, nobs, crit, _ = adfuller(arr, regression=regression, autolag="AIC")
    return {
        "test": "ADF",
        "statistic": float(stat),
        "p_value": float(pval),
        "lag": int(lag),
        "nobs": int(nobs),
        "critical_values": {k: float(v) for k, v in crit.items()},
        "alpha": alpha,
        "reject_h0": bool(pval < alpha),
        "stationary": bool(pval < alpha),
    }


def kpss_test(series: Iterable, regression: str = "c", alpha: float = 0.05) -> dict:
    """KPSS 정상성 검정. H0: 정상. reject_h0=True 이면 비정상.

    regression: "c" (level), "ct" (trend)
    """
    arr = np.asarray(list(series), dtype=float)
    if arr.size < 10:
        raise ValueError("series too short for KPSS (need >= 10 obs)")
    if np.isnan(arr).any():
        raise ValueError("NaN not allowed in series")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        stat, pval, lag, crit = kpss(arr, regression=regression, nlags="auto")
    return {
        "test": "KPSS",
        "statistic": float(stat),
        "p_value": float(pval),
        "lag": int(lag),
        "critical_values": {k: float(v) for k, v in crit.items()},
        "alpha": alpha,
        "reject_h0": bool(pval < alpha),
        "stationary": bool(pval >= alpha),
    }


def stationarity_summary(series: Iterable, alpha: float = 0.05) -> dict:
    """ADF + KPSS 결과를 결합해 일관성 라벨을 부여한다.

    label:
        - "stationary": ADF reject + KPSS not reject
        - "non_stationary": ADF not reject + KPSS reject
        - "inconclusive_likely_stationary": 둘 다 reject (분산 불안정 의심)
        - "inconclusive_likely_non_stationary": 둘 다 not reject
    """
    a = adf_test(series, alpha=alpha)
    k = kpss_test(series, alpha=alpha)
    adf_stat = a["stationary"]
    kpss_stat = k["stationary"]
    if adf_stat and kpss_stat:
        label = "stationary"
    elif (not adf_stat) and (not kpss_stat):
        label = "non_stationary"
    elif adf_stat and (not kpss_stat):
        label = "inconclusive_likely_stationary"
    else:
        label = "inconclusive_likely_non_stationary"
    return {"adf": a, "kpss": k, "label": label}
