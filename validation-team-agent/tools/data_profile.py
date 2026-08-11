"""Data profiling utilities for validation-team-agent.

운영 DB나 외부 네트워크에 접근하지 않는다. 입력은 항상 pandas DataFrame이며,
호출자가 결측·이상치 처리 정책을 명시적으로 결정한다.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def _ensure_columns(df: pd.DataFrame, cols: Iterable[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"required columns missing: {missing}")


def profile_dataframe(df: pd.DataFrame) -> dict:
    """기초 프로파일을 반환한다.

    반환 dict 키:
        n_rows, n_cols, dtypes, missing_ratio, numeric_summary
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    n_rows, n_cols = df.shape
    dtypes = {c: str(t) for c, t in df.dtypes.items()}
    missing_ratio = (df.isna().sum() / max(n_rows, 1)).to_dict()

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols:
        numeric_summary = df[numeric_cols].describe().to_dict()
    else:
        numeric_summary = {}

    return {
        "n_rows": n_rows,
        "n_cols": n_cols,
        "dtypes": dtypes,
        "missing_ratio": missing_ratio,
        "numeric_summary": numeric_summary,
    }


def check_missing(df: pd.DataFrame) -> pd.DataFrame:
    """컬럼별 결측 건수와 비율을 반환한다."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    n = max(len(df), 1)
    miss = df.isna().sum()
    out = pd.DataFrame(
        {
            "column": miss.index,
            "missing_count": miss.values,
            "missing_ratio": (miss.values / n),
        }
    )
    return out.reset_index(drop=True)


def check_duplicates(df: pd.DataFrame, key_cols: Iterable[str]) -> dict:
    """key_cols 기준 중복 행 수와 일부 샘플을 반환한다.

    반환 dict 키:
        duplicate_count, duplicate_keys (최대 10개 키 샘플)
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    key_cols = list(key_cols)
    if not key_cols:
        raise ValueError("key_cols must not be empty")
    _ensure_columns(df, key_cols)

    dup_mask = df.duplicated(subset=key_cols, keep=False)
    dup_count = int(dup_mask.sum())
    sample_keys = (
        df.loc[dup_mask, key_cols].drop_duplicates().head(10).to_dict(orient="records")
    )
    return {"duplicate_count": dup_count, "duplicate_keys": sample_keys}


def check_date_coverage(df: pd.DataFrame, date_col: str) -> dict:
    """일자 컬럼의 최소·최대·고유 일수·결측·기간 누락(월 단위)을 반환한다."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    _ensure_columns(df, [date_col])

    s = pd.to_datetime(df[date_col], errors="coerce")
    valid = s.dropna()
    if valid.empty:
        return {
            "min_date": None,
            "max_date": None,
            "unique_days": 0,
            "missing_count": int(s.isna().sum()),
            "missing_months": [],
        }

    min_d, max_d = valid.min(), valid.max()
    months_present = set(valid.dt.to_period("M").astype(str).unique())
    expected_months = set(
        pd.period_range(start=min_d, end=max_d, freq="M").astype(str)
    )
    missing_months = sorted(expected_months - months_present)
    return {
        "min_date": str(min_d.date()),
        "max_date": str(max_d.date()),
        "unique_days": int(valid.dt.normalize().nunique()),
        "missing_count": int(s.isna().sum()),
        "missing_months": missing_months,
    }
