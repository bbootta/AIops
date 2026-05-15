"""Margin of Conservatism (MoC) aggregator.

MoC is a widely used IRB concept: predicted risk parameter estimates carry
add-ons that compensate for known uncertainty. The standard taxonomy
distinguishes:

  Category A — data and methodological deficiencies (e.g., truncated history,
               missing segments).
  Category B — estimation error (statistical uncertainty in parameter
               estimates).
  Category C — general estimation error / residual conservatism (e.g.,
               business-cycle uncertainty).

This module does NOT compute MoC values from first principles. It takes
caller-supplied component values, classifies them, sums them, and emits a
structured record suitable for inclusion in a validation report.

The caller is responsible for sourcing each component from the appropriate
analysis (e.g., bootstrap confidence intervals for Category B). Tools to
*estimate* each component live elsewhere; this module only aggregates.
"""
from __future__ import annotations

from typing import Iterable, Mapping

import pandas as pd

ALLOWED_CATEGORIES = ("A", "B", "C")


def _validate_component(rec: Mapping) -> dict:
    if "category" not in rec:
        raise ValueError("Each MoC component must have a 'category'.")
    cat = str(rec["category"]).strip().upper()
    if cat not in ALLOWED_CATEGORIES:
        raise ValueError(f"category must be one of {ALLOWED_CATEGORIES}; got {cat!r}")
    if "value" not in rec:
        raise ValueError("Each MoC component must have a 'value'.")
    value = float(rec["value"])
    if value < 0:
        raise ValueError(f"MoC value must be non-negative; got {value}")
    label = str(rec.get("label", "")).strip()
    rationale = str(rec.get("rationale", "")).strip()
    return {
        "category": cat,
        "value": value,
        "label": label,
        "rationale": rationale,
    }


def build_moc_table(components: Iterable[Mapping]) -> pd.DataFrame:
    """Validate and stack MoC components into a tidy DataFrame."""
    rows = [_validate_component(c) for c in (components or [])]
    df = pd.DataFrame(rows, columns=["category", "label", "value", "rationale"])
    if not df.empty:
        df = df.sort_values(["category", "label"]).reset_index(drop=True)
    return df


def aggregate_moc(components: Iterable[Mapping]) -> dict:
    """Aggregate MoC components and emit a structured summary.

    Returns:
        {
          'total_moc': float,
          'by_category': {'A': float, 'B': float, 'C': float},
          'components': [<validated components>],
          'n_components': int,
        }
    """
    table = build_moc_table(components)
    by_category = {c: 0.0 for c in ALLOWED_CATEGORIES}
    if not table.empty:
        for cat in ALLOWED_CATEGORIES:
            by_category[cat] = float(table.loc[table["category"] == cat, "value"].sum())
    total = float(table["value"].sum()) if not table.empty else 0.0
    return {
        "total_moc": total,
        "by_category": by_category,
        "components": table.to_dict(orient="records"),
        "n_components": int(table.shape[0]),
    }


def apply_moc(point_estimate: float, total_moc: float) -> float:
    """Apply an additive MoC add-on to a point estimate.

    Negative point estimates or negative total_moc are rejected.
    """
    if point_estimate is None:
        raise ValueError("point_estimate is required.")
    if total_moc is None or total_moc < 0:
        raise ValueError("total_moc must be a non-negative number.")
    if point_estimate < 0:
        raise ValueError("point_estimate must be non-negative.")
    return float(point_estimate) + float(total_moc)
