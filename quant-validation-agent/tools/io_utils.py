"""I/O helpers for reading and writing local validation data.

Only operates on local files. Never connects to operational systems.
"""
from __future__ import annotations

import os
from typing import Iterable

import pandas as pd


def read_csv_safely(
    path: str,
    scan_pii: bool = False,
    pii_max_rows: int = 1000,
    **kwargs,
) -> pd.DataFrame:
    """Read a CSV file with strict checks.

    Args:
        scan_pii: when True, scan up to `pii_max_rows` rows of object columns
            for PII patterns (RRN, phone, email, card, account). Any match
            raises PermissionError, refusing to return the dataframe.
        pii_max_rows: maximum rows to scan when `scan_pii=True`.

    Raises:
        FileNotFoundError: if the path does not exist.
        ValueError: if the file is empty.
        PermissionError: if `scan_pii` is True and PII is detected.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV not found: {path}")
    df = pd.read_csv(path, **kwargs)
    if df.shape[0] == 0:
        raise ValueError(f"CSV is empty: {path}")
    if scan_pii:
        # Local import to avoid pulling middleware into all io_utils consumers.
        from middleware.data_safety_guard import detect_pii_in_dataframe

        hits = detect_pii_in_dataframe(df, max_rows=pii_max_rows)
        if hits:
            types = sorted({h["type"] for h in hits})
            raise PermissionError(
                f"PII detected in {path}: types={types}, hits={len(hits)}; refusing to return data."
            )
    return df


def write_dataframe_safely(df: pd.DataFrame, path: str, index: bool = False) -> str:
    """Write a DataFrame to CSV, creating parent directories if needed.

    Emits a warning (via the standard `warnings` module) when the destination
    path does not end with `.csv`; callers can promote the warning to an
    error in their own configuration.
    """
    import warnings as _warnings

    if df is None:
        raise ValueError("DataFrame is None.")
    if not path.lower().endswith(".csv"):
        _warnings.warn(
            f"write_dataframe_safely target does not end with .csv: {path!r}",
            stacklevel=2,
        )
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    df.to_csv(path, index=index)
    return path


def ensure_columns(df: pd.DataFrame, required_columns: Iterable[str]) -> None:
    """Raise ValueError if any required column is missing."""
    required = list(required_columns)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Required columns missing: {missing}")


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase and strip whitespace; replace spaces and dashes with underscores."""
    new_cols = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("-", "_", regex=False)
    )
    out = df.copy()
    out.columns = new_cols
    return out
