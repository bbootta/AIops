"""Diff two validate / validate-pd-calibration JSON outputs.

This is purely descriptive: returns the per-metric delta along with the
RAG transition (e.g., Green -> Yellow). The caller decides whether a
transition is acceptable.
"""
from __future__ import annotations

from typing import Mapping


def _numeric(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def diff_metric_blocks(base: Mapping, current: Mapping) -> list:
    """Return a list of {metric, base_value, current_value, delta,
    base_rag, current_rag, transition} for every metric appearing in
    either input."""
    base_metrics = (base or {}).get("metrics") or {}
    cur_metrics = (current or {}).get("metrics") or {}
    keys = sorted(set(base_metrics.keys()) | set(cur_metrics.keys()))
    rows = []
    for k in keys:
        b = base_metrics.get(k) or {}
        c = cur_metrics.get(k) or {}
        bv = _numeric(b.get("value"))
        cv = _numeric(c.get("value"))
        delta = None if (bv is None or cv is None) else (cv - bv)
        b_rag = b.get("rag", "Gray")
        c_rag = c.get("rag", "Gray")
        rows.append({
            "metric": k,
            "base_value": bv,
            "current_value": cv,
            "delta": delta,
            "base_rag": b_rag,
            "current_rag": c_rag,
            "transition": f"{b_rag} -> {c_rag}",
        })
    return rows


def diff_overall_rag(base: Mapping, current: Mapping) -> dict:
    """Compare the top-level overall_rag fields."""
    return {
        "base": (base or {}).get("overall_rag", "Gray"),
        "current": (current or {}).get("overall_rag", "Gray"),
        "regressed": _rag_rank((current or {}).get("overall_rag", "Gray"))
        > _rag_rank((base or {}).get("overall_rag", "Gray")),
    }


def _rag_rank(label) -> int:
    return {"Gray": 0, "Green": 1, "Yellow": 2, "Red": 3}.get(label, 0)
