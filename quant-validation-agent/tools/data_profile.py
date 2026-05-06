"""Data profiling helpers for input validation."""
from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import pandas as pd


def profile_dataframe(df: pd.DataFrame) -> dict:
    """Return a high-level profile of a DataFrame."""
    if df is None:
        raise ValueError("DataFrame is None.")
    return {
        "n_rows": int(df.shape[0]),
        "n_cols": int(df.shape[1]),
        "columns": list(df.columns),
        "dtypes": {c: str(t) for c, t in df.dtypes.items()},
        "missing_total": int(df.isna().sum().sum()),
    }


def check_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Per-column missing count and ratio."""
    n = max(len(df), 1)
    miss = df.isna().sum()
    out = pd.DataFrame(
        {
            "column": miss.index,
            "missing_count": miss.values,
            "missing_ratio": (miss.values / n).round(6),
        }
    )
    return out.reset_index(drop=True)


def check_duplicates(df: pd.DataFrame, key_cols: Optional[Iterable[str]] = None) -> dict:
    """Count duplicate rows (optionally by a key)."""
    if key_cols is None:
        dup = int(df.duplicated().sum())
        return {"key_cols": None, "duplicate_count": dup}
    keys = list(key_cols)
    missing = [c for c in keys if c not in df.columns]
    if missing:
        raise ValueError(f"key_cols not in df: {missing}")
    dup = int(df.duplicated(subset=keys).sum())
    return {"key_cols": keys, "duplicate_count": dup}


def check_date_coverage(df: pd.DataFrame, date_col: str) -> dict:
    """Return min/max/n_unique for a date-like column."""
    if date_col not in df.columns:
        raise ValueError(f"date_col '{date_col}' not in df.")
    s = pd.to_datetime(df[date_col], errors="coerce")
    valid = s.dropna()
    return {
        "date_col": date_col,
        "n_valid": int(valid.shape[0]),
        "n_invalid": int(s.isna().sum()),
        "min": str(valid.min()) if not valid.empty else None,
        "max": str(valid.max()) if not valid.empty else None,
        "n_unique": int(valid.nunique()),
    }


def check_segment_distribution(df: pd.DataFrame, segment_col: str) -> pd.DataFrame:
    """Return count and ratio per segment."""
    if segment_col not in df.columns:
        raise ValueError(f"segment_col '{segment_col}' not in df.")
    s = df[segment_col].astype("object").fillna("__NA__")
    counts = s.value_counts(dropna=False)
    n = max(int(counts.sum()), 1)
    out = pd.DataFrame(
        {
            "segment": counts.index.astype(str),
            "count": counts.values.astype(int),
            "ratio": (counts.values / n).round(6),
        }
    )
    return out.reset_index(drop=True)
