"""Scenario order checks for base / adverse / severe."""
from __future__ import annotations

import numpy as np
import pandas as pd

ALLOWED_DIRECTIONS = ("higher_is_worse", "lower_is_worse")


def check_scenario_order(
    base, adverse, severe, direction: str = "higher_is_worse"
) -> dict:
    """Check that severity ordering holds for each row.

    Args:
        base, adverse, severe: array-like of equal length.
        direction: 'higher_is_worse' (default) or 'lower_is_worse'.

    Returns:
        dict with violation counts and detailed positions.
    """
    if direction not in ALLOWED_DIRECTIONS:
        raise ValueError(f"direction must be one of {ALLOWED_DIRECTIONS}")
    b = np.asarray(list(base), dtype=float)
    a = np.asarray(list(adverse), dtype=float)
    s = np.asarray(list(severe), dtype=float)
    if not (b.shape[0] == a.shape[0] == s.shape[0]):
        raise ValueError("base, adverse, severe must have equal length.")
    if b.size == 0:
        raise ValueError("Inputs are empty.")
    if np.isnan(b).any() or np.isnan(a).any() or np.isnan(s).any():
        raise ValueError("Inputs contain NaN.")
    if direction == "higher_is_worse":
        viol_ba = b > a
        viol_as = a > s
    else:
        viol_ba = b < a
        viol_as = a < s
    n = int(b.shape[0])
    return {
        "n": n,
        "direction": direction,
        "n_violation_base_vs_adverse": int(viol_ba.sum()),
        "n_violation_adverse_vs_severe": int(viol_as.sum()),
        "n_violation_total": int((viol_ba | viol_as).sum()),
        "violation_positions": [int(i) for i in np.where(viol_ba | viol_as)[0]],
    }


def check_pd_multiplier_floor(values, scenario_type: str, floor: float = 1.0) -> dict:
    """Check whether PD multipliers respect a floor.

    For 'base' scenarios, multiplier is typically expected to be >= floor (default 1.0).
    For other scenarios (adverse/severe) it should also be >= floor by usual policy.
    """
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        raise ValueError("values are empty.")
    if np.isnan(arr).any():
        raise ValueError("values contain NaN.")
    n_below = int((arr < floor).sum())
    return {
        "scenario_type": scenario_type,
        "floor": float(floor),
        "n": int(arr.shape[0]),
        "n_below_floor": n_below,
        "min": float(arr.min()),
        "max": float(arr.max()),
        "violation": n_below > 0,
    }


def summarize_scenario_violations(
    df: pd.DataFrame, base_col: str, adverse_col: str, severe_col: str
) -> pd.DataFrame:
    """Per-row table flagging severity violations."""
    for c in (base_col, adverse_col, severe_col):
        if c not in df.columns:
            raise ValueError(f"Column missing: {c}")
    out = df[[base_col, adverse_col, severe_col]].copy()
    out["viol_base_vs_adverse"] = out[base_col] > out[adverse_col]
    out["viol_adverse_vs_severe"] = out[adverse_col] > out[severe_col]
    out["any_violation"] = out["viol_base_vs_adverse"] | out["viol_adverse_vs_severe"]
    return out.reset_index(drop=True)
