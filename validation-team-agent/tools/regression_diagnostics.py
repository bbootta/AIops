"""회귀/시계열 모형 진단 보조 함수.

다중공선성 (VIF), OLS 요약, 잔차 기초 진단을 제공한다.
시계열 정상성 검정 등 무거운 분석은 호출자가 별도 라이브러리로 수행한다.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor


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
