"""Sanity checks: harness/threshold_policy.md must reflect the JSON values
for the metrics most often quoted in reports. These checks read the JSON
and look for the corresponding numeric strings in the markdown table.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY_JSON = os.path.join(ROOT, "harness", "threshold_policy.json")
POLICY_MD = os.path.join(ROOT, "harness", "threshold_policy.md")


def _load_md():
    with open(POLICY_MD, "r", encoding="utf-8") as f:
        return f.read()


def _load_json():
    import json
    with open(POLICY_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


# Metrics whose markdown rows must mention the JSON-defined thresholds.
# These are the values consumers most often cite in validation reports.
_TRACKED = [
    ("ks", "KS"),
    ("auroc", "AUROC"),
    ("ar", "AR (Gini)"),
    ("psi", "PSI"),
    ("brier", "Brier"),
    ("vif", "VIF"),
]


def _pretty(value):
    """Convert numeric thresholds to the textual forms used in the markdown."""
    if isinstance(value, float) and value.is_integer():
        return [str(int(value)), f"{value:.1f}", f"{value:.2f}"]
    if isinstance(value, float):
        return [f"{value:.2f}", f"{value:.1f}", str(value)]
    return [str(value)]


def test_markdown_quotes_json_thresholds_for_tracked_metrics():
    md = _load_md()
    policy = _load_json()
    metrics = policy.get("metrics", {})
    missing = []
    for key, label in _TRACKED:
        cfg = metrics.get(key)
        if not cfg:
            continue
        # Find the table row whose first cell starts with the label
        # (the markdown allows clarifiers like "PSI (전체)").
        row_pat = re.compile(
            r"\|\s*" + re.escape(label) + r"[^|]*\|.*",
            re.MULTILINE,
        )
        rows = row_pat.findall(md)
        if not rows:
            missing.append(f"{label}: row not found in markdown")
            continue
        row = rows[0]
        for tval in (cfg.get("green_threshold"), cfg.get("yellow_threshold")):
            if tval is None:
                continue
            if not any(form in row for form in _pretty(tval)):
                missing.append(
                    f"{label}: value {tval} not present in row '{row.strip()}'"
                )
    assert not missing, "JSON ↔ markdown mismatch: " + "; ".join(missing)


def test_segment_overlay_segments_listed_in_markdown():
    """If by_segment is defined, each segment name should appear in the md
    so reviewers know overrides exist."""
    md = _load_md()
    policy = _load_json()
    by_segment = policy.get("by_segment") or {}
    missing = [seg for seg in by_segment.keys() if seg not in md]
    assert not missing, f"segments missing from markdown: {missing}"
