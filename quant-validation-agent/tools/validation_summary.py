"""Validation result summarization helpers."""
from __future__ import annotations

from typing import Iterable, List, Mapping, Optional

import pandas as pd

ALLOWED_RAG = ("Green", "Yellow", "Red", "Gray")


def build_metric_summary(result_dict: Mapping[str, object]) -> pd.DataFrame:
    """Flatten a {metric: value} dict to a DataFrame."""
    if result_dict is None:
        raise ValueError("result_dict is None.")
    rows = []
    for metric, value in result_dict.items():
        rows.append({"metric": metric, "value": value})
    return pd.DataFrame(rows)


def build_issue_table(issue_list: Iterable[Mapping[str, object]]) -> pd.DataFrame:
    """Standardize an issue list into a DataFrame with required columns."""
    issues = list(issue_list) if issue_list is not None else []
    cols = ["issue", "severity", "evidence", "candidate_cause", "next_action"]
    if not issues:
        return pd.DataFrame(columns=cols)
    rows = []
    for it in issues:
        row = {c: it.get(c, "") for c in cols}
        rows.append(row)
    return pd.DataFrame(rows, columns=cols)


_VALID_DIRECTIONS = ("higher_is_better", "lower_is_better", "abs_lower_is_better")


def assign_rag_status(
    metric_value: Optional[float],
    green_threshold: Optional[float] = None,
    yellow_threshold: Optional[float] = None,
    direction: str = "higher_is_better",
) -> str:
    """Return Green / Yellow / Red / Gray for a single metric value.

    Args:
        green_threshold: passing threshold (better than this => Green).
        yellow_threshold: caution threshold (between yellow and green => Yellow,
            worse than yellow => Red).
        direction: 'higher_is_better', 'lower_is_better', or 'abs_lower_is_better'.
            'abs_lower_is_better' compares |metric_value| against thresholds
            (e.g., PD bias where both over- and under-prediction are bad).

    Returns:
        'Green', 'Yellow', 'Red', or 'Gray' (when value or thresholds are missing).
    """
    if metric_value is None or (isinstance(metric_value, float) and pd.isna(metric_value)):
        return "Gray"
    if green_threshold is None or yellow_threshold is None:
        return "Gray"
    if direction not in _VALID_DIRECTIONS:
        raise ValueError(f"direction must be one of {_VALID_DIRECTIONS}")
    # Direction-aware sanity: green must be strictly more permissive than
    # yellow. For higher_is_better, green > yellow. For lower_is_better /
    # abs_lower_is_better, green < yellow.
    if direction == "higher_is_better" and not (green_threshold > yellow_threshold):
        raise ValueError(
            f"higher_is_better requires green_threshold > yellow_threshold; "
            f"got green={green_threshold}, yellow={yellow_threshold}."
        )
    if direction in ("lower_is_better", "abs_lower_is_better") and not (
        green_threshold < yellow_threshold
    ):
        raise ValueError(
            f"{direction} requires green_threshold < yellow_threshold; "
            f"got green={green_threshold}, yellow={yellow_threshold}."
        )
    if direction == "higher_is_better":
        if metric_value >= green_threshold:
            return "Green"
        if metric_value >= yellow_threshold:
            return "Yellow"
        return "Red"
    if direction == "lower_is_better":
        if metric_value <= green_threshold:
            return "Green"
        if metric_value <= yellow_threshold:
            return "Yellow"
        return "Red"
    # abs_lower_is_better
    if green_threshold < 0 or yellow_threshold < 0:
        raise ValueError(
            "For 'abs_lower_is_better', thresholds must be non-negative."
        )
    abs_v = abs(metric_value)
    if abs_v <= green_threshold:
        return "Green"
    if abs_v <= yellow_threshold:
        return "Yellow"
    return "Red"


def build_validation_commentary(
    metric_summary: pd.DataFrame, issue_table: pd.DataFrame
) -> str:
    """Build a non-decisive draft commentary in Korean.

    Never asserts model adequacy. Always frames as a draft.
    """
    n_metrics = int(metric_summary.shape[0]) if metric_summary is not None else 0
    n_issues = int(issue_table.shape[0]) if issue_table is not None else 0
    severities = []
    if issue_table is not None and "severity" in issue_table.columns:
        severities = list(issue_table["severity"].dropna().astype(str).tolist())
    sev_counts = {
        "Red": severities.count("Red"),
        "Yellow": severities.count("Yellow"),
        "Green": severities.count("Green"),
        "Gray": severities.count("Gray"),
    }
    lines = [
        "## 검증 의견 초안 (단정 금지)",
        f"- 적용 지표 수: {n_metrics}",
        f"- 식별된 이슈 수: {n_issues} (Red {sev_counts['Red']} / Yellow {sev_counts['Yellow']} / Gray {sev_counts['Gray']})",
        "- 본 의견은 정량 결과에 근거한 초안이며, 모형 적합/부적합을 단정하지 않는다.",
        "- 데이터 정의, 관측창, 임계값 정책에 대한 인간 검증자의 확인이 필요하다.",
    ]
    return "\n".join(lines)
