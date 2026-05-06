"""I/O helpers for reading and writing local validation data.

Only operates on local files. Never connects to operational systems.
"""
from __future__ import annotations

import os
from typing import Iterable

import pandas as pd


def read_csv_safely(path: str, **kwargs) -> pd.DataFrame:
    """Read a CSV file with strict checks.

    Raises:
        FileNotFoundError: if the path does not exist.
        ValueError: if the file is empty.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV not found: {path}")
    df = pd.read_csv(path, **kwargs)
    if df.shape[0] == 0:
        raise ValueError(f"CSV is empty: {path}")
    return df


def write_dataframe_safely(df: pd.DataFrame, path: str, index: bool = False) -> str:
    """Write a DataFrame to CSV, creating parent directories if needed."""
    if df is None:
        raise ValueError("DataFrame is None.")
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
