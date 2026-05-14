"""Leakage guard.

Detects post-event / outcome columns mistakenly used as features.
Heuristic — name-based — that flags columns whose names suggest they are
realized outcomes after the prediction reference time.
"""
from __future__ import annotations

import re
from typing import Iterable, List

LEAKAGE_PATTERNS = [
    r"\btarget\b",
    r"\blabel\b",
    r"\bdefault(_|$)",
    r"\bbad(_|$)",
    r"\bnpl\b",
    r"\boutcome\b",
    r"\brealized\b",
    r"\brecovered?\b",
    r"\brecovery\b",
    r"\bcollection\b",
    r"\bpost_event\b",
    r"\bafter_default\b",
    r"\bwriteoff\b",
    r"\bcharge_off\b",
    r"\bobserved_loss\b",
    r"\bactual_lgd\b",
    r"\brealized_lgd\b",
    r"\brealized_ead\b",
]


def _name_match(name: str) -> List[str]:
    matches = []
    for p in LEAKAGE_PATTERNS:
        if re.search(p, name, flags=re.IGNORECASE):
            matches.append(p)
    return matches


def detect_leakage_candidates(feature_columns: Iterable[str]) -> list:
    """Return [{column, matched_patterns}] for any name that matches."""
    out = []
    for col in feature_columns:
        if col is None:
            continue
        matches = _name_match(str(col))
        if matches:
            out.append({"column": col, "matched_patterns": matches})
    return out


def assert_no_leakage_candidates(feature_columns: Iterable[str]) -> None:
    """Raise PermissionError if leakage candidates are found among features."""
    cands = detect_leakage_candidates(feature_columns)
    if cands:
        cols = ", ".join(c["column"] for c in cands)
        raise PermissionError(f"Possible leakage columns in features: {cols}")


def detect_leakage_candidates_df(df, feature_columns: Iterable[str]) -> list:
    """DataFrame-aware leakage detection.

    Combines name-based heuristics with dtype heuristics:
      - datetime-like columns whose names suggest realized timestamps
        (default_date, recovery_date, closed_at, etc.) are flagged.
      - integer/boolean columns whose names suggest realized flags
        (default_flag, npl_flag, recovered) are flagged.

    Each match records the matched_patterns and the reason ('name', 'dtype').
    """
    import pandas as pd  # local import — keeps the name-only API import-free

    out = []
    for col in feature_columns:
        if col is None or col not in df.columns:
            continue
        name = str(col)
        matches = _name_match(name)
        reasons = ["name"] if matches else []
        dtype = df[name].dtype
        if pd.api.types.is_datetime64_any_dtype(dtype):
            if re.search(r"(_date|_at|_time)$", name, flags=re.IGNORECASE):
                reasons.append("dtype:datetime")
        # Bool/int dtype is suspicious only when the name suggests a flag.
        # This keeps legitimate boolean features like 'is_premium' clean.
        if (pd.api.types.is_bool_dtype(dtype) or pd.api.types.is_integer_dtype(dtype)) \
                and re.search(r"(_flag$|_observed$|_realized$)", name, flags=re.IGNORECASE):
            reasons.append("dtype:flag")
        if reasons:
            out.append({
                "column": col,
                "matched_patterns": matches,
                "reasons": reasons,
                "dtype": str(dtype),
            })
    return out
