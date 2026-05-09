"""End-to-end pipeline for scenario / PD multiplier regression validation.

Combines:
- OLS fitting (statsmodels)
- Regression diagnostics (R², p-values, VIF, condition index, residual basics)
- Time-series diagnostics (Durbin-Watson, Breusch-Godfrey, ARCH)
- Scenario prediction
- Severity ordering check (base ≤ adverse ≤ severe)
- Multiplier floor check

This module is a thin orchestrator over tools/regression_diagnostics.py
and tools/scenario_order_check.py. It does NOT compute RAG on its own —
RAG should be assigned by the caller using threshold_policy.
"""
from __future__ import annotations

from typing import Iterable, Mapping, Optional

import numpy as np
import pandas as pd

from . import regression_diagnostics as rd
from . import scenario_order_check as soc


def fit_scenario_regression(
    hist_df: pd.DataFrame,
    target_col: str,
    feature_cols: Iterable[str],
    expected_signs: Optional[Mapping[str, str]] = None,
    pvalue_threshold: float = 0.05,
    autocorr_lags: int = 1,
) -> dict:
    """Fit OLS on historical data and return a structured diagnostic bundle."""
    feats = list(feature_cols)
    if not feats:
        raise ValueError("feature_cols must not be empty.")
    for c in [target_col, *feats]:
        if c not in hist_df.columns:
            raise ValueError(f"Column missing in hist_df: {c}")
    work = hist_df.dropna(subset=[target_col, *feats])
    if work.empty:
        raise ValueError("Historical data has no non-null rows.")
    y = work[target_col].astype(float).values
    X = work[feats].astype(float)
    n = int(work.shape[0])
    k = len(feats)
    fit = rd.fit_ols(y, X)
    summary = rd.extract_regression_summary(fit)
    pvals = rd.check_pvalues(fit, threshold=pvalue_threshold)
    signs_df = rd.check_coefficient_signs(fit, expected_signs) if expected_signs else None
    vif = rd.calculate_vif(X) if k >= 2 else pd.DataFrame(columns=["variable", "vif"])
    cond = rd.check_condition_index(X)
    resid = rd.check_residual_basic(fit)
    dw = rd.calculate_durbin_watson(fit)
    try:
        bg = rd.calculate_breusch_godfrey(fit, lags=autocorr_lags)
    except Exception as e:
        bg = {"error": str(e)}
    try:
        arch = rd.calculate_arch_test(fit, lags=autocorr_lags)
    except Exception as e:
        arch = {"error": str(e)}
    return {
        "n": n,
        "k": k,
        "n_to_k_ratio": float(n / k) if k > 0 else float("inf"),
        "summary": summary,
        "pvalues": pvals.to_dict(orient="records"),
        "coefficient_signs": signs_df.to_dict(orient="records") if signs_df is not None else None,
        "vif": vif.to_dict(orient="records"),
        "condition_index": cond,
        "residual_basic": resid,
        "durbin_watson": dw,
        "breusch_godfrey": bg,
        "arch_test": arch,
        "model": fit,
        "feature_cols": feats,
        "target_col": target_col,
    }


def predict_scenarios(
    fit_bundle: dict,
    scenario_df: pd.DataFrame,
    scenario_col: str,
    period_col: Optional[str] = None,
) -> pd.DataFrame:
    """Predict the target for each scenario row using the fitted model."""
    if scenario_col not in scenario_df.columns:
        raise ValueError(f"scenario_col missing: {scenario_col}")
    feats = list(fit_bundle["feature_cols"])
    for c in feats:
        if c not in scenario_df.columns:
            raise ValueError(f"Feature column missing in scenario_df: {c}")
    work = scenario_df.copy()
    import statsmodels.api as sm

    Xc = sm.add_constant(work[feats].astype(float), has_constant="add")
    work["pred"] = fit_bundle["model"].predict(Xc)
    keep = [scenario_col] + ([period_col] if period_col and period_col in work.columns else []) + feats + ["pred"]
    return work[keep].reset_index(drop=True)


def check_scenario_severity(
    pred_df: pd.DataFrame,
    scenario_col: str,
    pred_col: str = "pred",
    period_col: Optional[str] = None,
    direction: str = "higher_is_worse",
) -> dict:
    """Pivot scenarios to base/adverse/severe and run scenario_order_check."""
    required_scenarios = {"base", "adverse", "severe"}
    present = set(pred_df[scenario_col].astype(str).unique())
    missing = required_scenarios - present
    if missing:
        raise ValueError(
            f"Scenario data missing required scenarios: {sorted(missing)}"
        )
    if period_col and period_col in pred_df.columns:
        pivot = pred_df.pivot_table(index=period_col, columns=scenario_col, values=pred_col, aggfunc="mean")
    else:
        # Aggregate to a single row per scenario
        pivot = pred_df.groupby(scenario_col)[pred_col].mean().to_frame().T
    pivot = pivot[["base", "adverse", "severe"]].dropna(how="any")
    if pivot.empty:
        raise ValueError("After alignment, no rows with all three scenarios available.")
    order = soc.check_scenario_order(
        pivot["base"].values,
        pivot["adverse"].values,
        pivot["severe"].values,
        direction=direction,
    )
    return {
        "pivot": pivot.reset_index().to_dict(orient="records"),
        "order": order,
    }


def check_multiplier_floors(
    pred_df: pd.DataFrame,
    scenario_col: str,
    pred_col: str,
    floor_by_scenario: Mapping[str, float],
) -> list:
    """Apply per-scenario floor checks; returns one record per scenario."""
    if scenario_col not in pred_df.columns or pred_col not in pred_df.columns:
        raise ValueError("scenario_col or pred_col missing.")
    out = []
    for scenario, group in pred_df.groupby(scenario_col):
        floor = floor_by_scenario.get(str(scenario))
        if floor is None:
            continue
        out.append(
            soc.check_pd_multiplier_floor(group[pred_col].values, scenario_type=str(scenario), floor=float(floor))
        )
    return out


def run_pipeline(
    hist_df: pd.DataFrame,
    target_col: str,
    feature_cols: Iterable[str],
    scenario_df: pd.DataFrame,
    scenario_col: str,
    period_col: Optional[str] = None,
    pred_col_in_scenario: Optional[str] = None,
    expected_signs: Optional[Mapping[str, str]] = None,
    multiplier_floor_by_scenario: Optional[Mapping[str, float]] = None,
    severity_direction: str = "higher_is_worse",
    pvalue_threshold: float = 0.05,
    autocorr_lags: int = 1,
) -> dict:
    """Run the full scenario regression validation pipeline.

    If `pred_col_in_scenario` is given (e.g., a pre-supplied PD multiplier),
    the pipeline uses those values for severity / floor checks instead of
    re-predicting. Otherwise it predicts using the fitted OLS model.
    """
    fit_bundle = fit_scenario_regression(
        hist_df,
        target_col,
        feature_cols,
        expected_signs=expected_signs,
        pvalue_threshold=pvalue_threshold,
        autocorr_lags=autocorr_lags,
    )
    if pred_col_in_scenario is not None:
        if pred_col_in_scenario not in scenario_df.columns:
            raise ValueError(f"pred_col_in_scenario missing: {pred_col_in_scenario}")
        pred_df = scenario_df.rename(columns={pred_col_in_scenario: "pred"}).copy()
        pred_col_eff = "pred"
    else:
        pred_df = predict_scenarios(fit_bundle, scenario_df, scenario_col, period_col=period_col)
        pred_col_eff = "pred"
    severity = check_scenario_severity(
        pred_df, scenario_col, pred_col=pred_col_eff, period_col=period_col, direction=severity_direction
    )
    floors = (
        check_multiplier_floors(pred_df, scenario_col, pred_col_eff, multiplier_floor_by_scenario)
        if multiplier_floor_by_scenario
        else []
    )
    # Drop the non-serializable model object from the returned bundle.
    serializable_fit = {k: v for k, v in fit_bundle.items() if k != "model"}
    return {
        "fit": serializable_fit,
        "predictions": pred_df.to_dict(orient="records"),
        "severity": severity,
        "multiplier_floors": floors,
    }
