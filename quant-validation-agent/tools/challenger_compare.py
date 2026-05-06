"""Champion vs challenger model comparison helpers.

These helpers focus on like-for-like comparisons. They first verify the same
sample assumption, then compute metric deltas. They do NOT recommend a winner —
that is the human validator's decision.
"""
from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import pandas as pd

from .metric_calibration import calculate_brier_score
from .metric_ks_auc_ar import (
    calculate_accuracy_ratio,
    calculate_auc,
    calculate_ks,
)


def check_same_sample(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    key_col: str,
) -> dict:
    """Verify that two DataFrames cover the same sample (by `key_col`)."""
    for d, name in ((df_a, "df_a"), (df_b, "df_b")):
        if key_col not in d.columns:
            raise ValueError(f"key_col '{key_col}' missing in {name}.")
    keys_a = set(df_a[key_col].dropna().tolist())
    keys_b = set(df_b[key_col].dropna().tolist())
    only_a = sorted(keys_a - keys_b, key=str)
    only_b = sorted(keys_b - keys_a, key=str)
    return {
        "n_a": len(keys_a),
        "n_b": len(keys_b),
        "n_intersection": len(keys_a & keys_b),
        "n_only_a": len(only_a),
        "n_only_b": len(only_b),
        "same_sample": (len(only_a) == 0 and len(only_b) == 0 and len(keys_a) == len(keys_b)),
        "only_a_examples": only_a[:10],
        "only_b_examples": only_b[:10],
    }


def compare_discrimination(
    y_true: Iterable,
    score_champion: Iterable,
    score_challenger: Iterable,
    higher_is_worse: bool = True,
) -> pd.DataFrame:
    """Side-by-side KS / AUROC / AR for champion vs challenger.

    Both score arrays must align element-wise with `y_true`.
    """
    y = list(y_true)
    sc = list(score_champion)
    sl = list(score_challenger)
    if not (len(y) == len(sc) == len(sl)):
        raise ValueError("y_true, score_champion, score_challenger must have same length.")
    rows = []
    for name, s in (("champion", sc), ("challenger", sl)):
        rows.append(
            {
                "model": name,
                "ks": calculate_ks(y, s, higher_is_worse=higher_is_worse),
                "auroc": calculate_auc(y, s, higher_is_worse=higher_is_worse),
                "ar": calculate_accuracy_ratio(y, s, higher_is_worse=higher_is_worse),
            }
        )
    df = pd.DataFrame(rows).set_index("model")
    diff = df.loc["challenger"] - df.loc["champion"]
    df.loc["delta_challenger_minus_champion"] = diff
    return df.reset_index()


def compare_calibration(
    y_true: Iterable,
    pd_champion: Iterable,
    pd_challenger: Iterable,
) -> pd.DataFrame:
    """Side-by-side Brier score and bias for two PD models on the same sample."""
    y_arr = np.asarray(list(y_true), dtype=float)
    pc = np.asarray(list(pd_champion), dtype=float)
    pl = np.asarray(list(pd_challenger), dtype=float)
    if not (y_arr.shape[0] == pc.shape[0] == pl.shape[0]):
        raise ValueError("Inputs must have same length.")
    obs = float(np.mean(y_arr))
    rows = []
    for name, p in (("champion", pc), ("challenger", pl)):
        brier = calculate_brier_score(y_arr.tolist(), p.tolist())
        rows.append(
            {
                "model": name,
                "brier": brier,
                "mean_predicted_pd": float(np.mean(p)),
                "observed_default_rate": obs,
                "abs_bias": float(np.mean(p) - obs),
            }
        )
    df = pd.DataFrame(rows).set_index("model")
    diff = df.loc["challenger"] - df.loc["champion"]
    df.loc["delta_challenger_minus_champion"] = diff
    return df.reset_index()
