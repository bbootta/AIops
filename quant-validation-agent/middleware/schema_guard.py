"""Schema guard for required columns / dtypes / parseable dates."""
from __future__ import annotations

from typing import Iterable, Mapping

import pandas as pd


def check_required_columns(df: pd.DataFrame, required: Iterable[str]) -> dict:
    """Return missing required columns."""
    required = list(required)
    missing = [c for c in required if c not in df.columns]
    return {"required": required, "missing": missing, "pass": len(missing) == 0}


def check_dtypes(df: pd.DataFrame, expected: Mapping[str, str]) -> pd.DataFrame:
    """Compare expected dtypes (numpy/pandas type strings, e.g., 'int64', 'float64')."""
    rows = []
    for col, exp in expected.items():
        if col not in df.columns:
            rows.append({"column": col, "expected": exp, "actual": None, "pass": False})
            continue
        actual = str(df[col].dtype)
        rows.append(
            {
                "column": col,
                "expected": exp,
                "actual": actual,
                "pass": actual == exp,
            }
        )
    return pd.DataFrame(rows)


def check_date_parseable(df: pd.DataFrame, date_cols: Iterable[str]) -> pd.DataFrame:
    """Ensure each date column can be parsed; report failure counts."""
    rows = []
    for col in date_cols:
        if col not in df.columns:
            rows.append({"column": col, "n": 0, "n_failed": None, "pass": False})
            continue
        n = int(df[col].shape[0])
        parsed = pd.to_datetime(df[col], errors="coerce")
        failed = int(parsed.isna().sum())
        rows.append({"column": col, "n": n, "n_failed": failed, "pass": failed == 0})
    return pd.DataFrame(rows)
