"""Load and query the externalized threshold policy.

Reading thresholds from a structured file makes changes auditable through
change_manifest. The loader does NOT mutate values at runtime; it only reads.
"""
from __future__ import annotations

import json
import os
from typing import Optional

DEFAULT_POLICY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "harness",
    "threshold_policy.json",
)


def load_threshold_policy(path: Optional[str] = None) -> dict:
    """Load the threshold policy JSON. Raises FileNotFoundError if missing."""
    p = path or DEFAULT_POLICY_PATH
    if not os.path.exists(p):
        raise FileNotFoundError(f"Threshold policy not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        policy = json.load(f)
    if not isinstance(policy, dict):
        raise ValueError("Threshold policy must be a JSON object.")
    return policy


def get_metric_threshold(
    policy: dict,
    metric_name: str,
    segment: Optional[str] = None,
) -> dict:
    """Return {green_threshold, yellow_threshold, direction, source} for a metric.

    If `segment` is provided and the policy has a `by_segment.<segment>.metrics.<metric>`
    override, the per-segment thresholds replace the defaults; `direction` is
    always taken from the global metric definition (segments override values
    only, not the comparison direction).

    `source` indicates whether the values came from the global block or a
    segment override: 'global' or 'segment:<name>'.

    Raises:
        KeyError if the metric is not defined in the policy at all.
    """
    metrics = policy.get("metrics") or {}
    if metric_name not in metrics:
        raise KeyError(f"Metric not in policy: {metric_name}")
    cfg = metrics[metric_name]
    required = {"green_threshold", "yellow_threshold", "direction"}
    missing = required - set(cfg.keys())
    if missing:
        raise ValueError(f"Metric '{metric_name}' missing keys: {sorted(missing)}")
    out = {
        "green_threshold": cfg["green_threshold"],
        "yellow_threshold": cfg["yellow_threshold"],
        "direction": cfg["direction"],
        "source": "global",
    }
    if segment is None:
        return out
    by_segment = policy.get("by_segment") or {}
    seg_cfg = (by_segment.get(segment) or {}).get("metrics") or {}
    if metric_name in seg_cfg:
        override = seg_cfg[metric_name]
        if "green_threshold" in override:
            out["green_threshold"] = override["green_threshold"]
        if "yellow_threshold" in override:
            out["yellow_threshold"] = override["yellow_threshold"]
        out["source"] = f"segment:{segment}"
    return out


def list_segments(policy: dict) -> list:
    """Return the list of segments that have any threshold override."""
    by_segment = policy.get("by_segment") or {}
    return sorted(by_segment.keys())


def get_ead_metric_settings(policy: dict) -> dict:
    """Return the EAD-error normalizer settings, validated for consistency.

    Raises:
        ValueError if `normalizer` is not in `allowed_normalizers`.
    """
    settings = policy.get("ead_metric_settings") or {}
    normalizer = settings.get("normalizer", "mean_realized")
    allowed = settings.get(
        "allowed_normalizers",
        ["mean_realized", "mean_predicted", "total_exposure"],
    )
    if normalizer not in allowed:
        raise ValueError(
            f"ead_metric_settings.normalizer={normalizer!r} is not in "
            f"allowed_normalizers={allowed!r}"
        )
    return {"normalizer": normalizer, "allowed_normalizers": allowed}


def list_metrics_for_model(policy: dict, model_type: str) -> list:
    """List metric names whose 'model_types' includes `model_type`."""
    metrics = policy.get("metrics") or {}
    out = []
    for name, cfg in metrics.items():
        types = cfg.get("model_types") or []
        if model_type in types:
            out.append(name)
    return sorted(out)
