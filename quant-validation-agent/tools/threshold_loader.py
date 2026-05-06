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


def get_metric_threshold(policy: dict, metric_name: str) -> dict:
    """Return {green_threshold, yellow_threshold, direction} for a metric.

    Raises:
        KeyError if the metric is not defined in the policy.
    """
    metrics = policy.get("metrics") or {}
    if metric_name not in metrics:
        raise KeyError(f"Metric not in policy: {metric_name}")
    cfg = metrics[metric_name]
    required = {"green_threshold", "yellow_threshold", "direction"}
    missing = required - set(cfg.keys())
    if missing:
        raise ValueError(f"Metric '{metric_name}' missing keys: {sorted(missing)}")
    return {
        "green_threshold": cfg["green_threshold"],
        "yellow_threshold": cfg["yellow_threshold"],
        "direction": cfg["direction"],
    }


def list_metrics_for_model(policy: dict, model_type: str) -> list:
    """List metric names whose 'model_types' includes `model_type`."""
    metrics = policy.get("metrics") or {}
    out = []
    for name, cfg in metrics.items():
        types = cfg.get("model_types") or []
        if model_type in types:
            out.append(name)
    return sorted(out)
