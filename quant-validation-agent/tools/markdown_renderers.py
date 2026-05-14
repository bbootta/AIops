"""Consistent markdown table renderers for validation reports.

These helpers exist to keep table formatting uniform across the standard
9-section report (see docs/validation_output_spec.md). They are pure
formatters — they never mutate input and never write to disk.
"""
from __future__ import annotations

from typing import Iterable, List, Mapping, Optional

import pandas as pd


def _format_value(v, decimals: int) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        if v != v:  # NaN
            return ""
        return f"{v:.{decimals}f}"
    return str(v)


def render_dataframe_markdown(
    df: pd.DataFrame,
    columns: Optional[Iterable[str]] = None,
    aligns: Optional[Mapping[str, str]] = None,
    decimals: int = 4,
    max_rows: Optional[int] = None,
) -> str:
    """Render a DataFrame as a GitHub-flavored markdown table.

    Args:
        columns: column order; defaults to df.columns.
        aligns: per-column alignment ('left'|'right'|'center'); defaults left.
        decimals: float precision.
        max_rows: when set, render only the first `max_rows` rows and append
            a single italic note line indicating how many rows were truncated.
    """
    if df is None or df.empty:
        return "| (empty) |\n|---|\n"
    cols = list(columns) if columns is not None else list(df.columns)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing columns: {missing}")
    if max_rows is not None and max_rows < 1:
        raise ValueError("max_rows must be >= 1.")
    aligns = dict(aligns or {})
    align_marks = []
    for c in cols:
        a = aligns.get(c, "left")
        if a == "right":
            align_marks.append("---:")
        elif a == "center":
            align_marks.append(":---:")
        else:
            align_marks.append("---")
    header = "| " + " | ".join(cols) + " |\n"
    sep = "|" + "|".join(align_marks) + "|\n"
    total = int(df.shape[0])
    body = df if max_rows is None else df.head(max_rows)
    body_rows: List[str] = []
    for _, row in body.iterrows():
        cells = [_format_value(row[c], decimals) for c in cols]
        body_rows.append("| " + " | ".join(cells) + " |")
    out = header + sep + "\n".join(body_rows) + "\n"
    if max_rows is not None and total > max_rows:
        truncated = total - max_rows
        out += f"\n_... {truncated} more rows truncated (max_rows={max_rows})_\n"
    return out


def render_metrics_table(
    metrics: Mapping[str, dict],
    decimals: int = 4,
    max_rows: Optional[int] = None,
) -> str:
    """Render a {metric_name: {value, rag, ...}} dict as a markdown table."""
    if not metrics:
        return "| 지표 | 값 | 기준 | 상태 | 출처 |\n|---|---:|---:|---|---|\n| (없음) | | | | |\n"
    rows = []
    for name, info in metrics.items():
        info = info or {}
        value = info.get("value")
        rag = info.get("rag", "Gray")
        green = info.get("green_threshold")
        yellow = info.get("yellow_threshold")
        thresh = ""
        if green is not None and yellow is not None:
            thresh = f"G:{green}/Y:{yellow}"
        rows.append(
            {
                "지표": name,
                "값": _format_value(value, decimals),
                "기준": thresh,
                "상태": rag,
                "출처": info.get("source", ""),
            }
        )
    df = pd.DataFrame(rows, columns=["지표", "값", "기준", "상태", "출처"])
    return render_dataframe_markdown(
        df,
        aligns={"값": "right", "기준": "right"},
        decimals=decimals,
        max_rows=max_rows,
    )


def render_issue_table(
    issues: Iterable[Mapping],
    max_rows: Optional[int] = None,
) -> str:
    """Render a list of {issue, severity, evidence, ...} dicts."""
    issues = list(issues or [])
    if not issues:
        return "| 이슈 | 심각도 | 근거 | 원인 후보 | 추가 확인 |\n|---|---|---|---|---|\n| (없음) | | | | |\n"
    rows = []
    for it in issues:
        rows.append(
            {
                "이슈": it.get("issue", ""),
                "심각도": it.get("severity", ""),
                "근거": str(it.get("evidence", "")),
                "원인 후보": str(it.get("candidate_cause", "")),
                "추가 확인": str(it.get("next_action", "")),
            }
        )
    df = pd.DataFrame(rows, columns=["이슈", "심각도", "근거", "원인 후보", "추가 확인"])
    return render_dataframe_markdown(df, max_rows=max_rows)


def render_regression_summary(
    summary: Mapping, pvalues: Iterable[Mapping], vif: Iterable[Mapping]
) -> str:
    """Render a compact regression summary block.

    Combines basic fit stats (R², adj R², n, k), p-values, and VIF.
    """
    lines = []
    if summary:
        lines.append(
            "- n: {n}, k: {k}, R²: {r2}, adj R²: {ar2}, F p-value: {fp}".format(
                n=summary.get("n", ""),
                k=summary.get("k", ""),
                r2=_format_value(summary.get("r_squared"), 4),
                ar2=_format_value(summary.get("adj_r_squared"), 4),
                fp=_format_value(summary.get("f_pvalue"), 4),
            )
        )
    pvals = list(pvalues or [])
    if pvals:
        df = pd.DataFrame(pvals)
        lines.append("\n**p-values**\n" + render_dataframe_markdown(
            df,
            columns=[c for c in ["variable", "pvalue", "significant_at_threshold", "threshold"] if c in df.columns],
            aligns={"pvalue": "right", "threshold": "right"},
        ))
    vif_rows = list(vif or [])
    if vif_rows:
        df = pd.DataFrame(vif_rows)
        lines.append("\n**VIF**\n" + render_dataframe_markdown(
            df,
            columns=[c for c in ["variable", "vif"] if c in df.columns],
            aligns={"vif": "right"},
        ))
    return "\n".join(lines).strip() + "\n"


def render_calibration_table(
    table_df: pd.DataFrame,
    decimals: int = 4,
    max_rows: Optional[int] = None,
) -> str:
    """Render a calibration table (output of metric_calibration.build_calibration_table)."""
    expected = ["count", "mean_pred", "mean_actual", "diff"]
    missing = [c for c in expected if c not in table_df.columns]
    if missing:
        raise ValueError(f"calibration table missing columns: {missing}")
    cols = list(table_df.columns)
    aligns = {"count": "right", "mean_pred": "right", "mean_actual": "right", "diff": "right"}
    return render_dataframe_markdown(
        table_df, columns=cols, aligns=aligns, decimals=decimals, max_rows=max_rows
    )


def render_scenario_severity(
    severity: Mapping, multiplier_floors: Optional[Iterable[Mapping]] = None,
    decimals: int = 4,
    max_rows: Optional[int] = None,
) -> str:
    """Render the scenario severity / floor block for a scenario report.

    Expects the structure produced by tools.scenario_regression_pipeline:
      severity = {"pivot": [{period, base, adverse, severe}, ...],
                  "order": {n_violation_total, n_violation_base_vs_adverse,
                            n_violation_adverse_vs_severe, ...}}
      multiplier_floors = [{scenario_type, floor, n_below_floor, violation, ...}]
    """
    parts: List[str] = []
    pivot = (severity or {}).get("pivot") or []
    order = (severity or {}).get("order") or {}

    if pivot:
        df = pd.DataFrame(pivot)
        has_period = "period" in df.columns
        scenario_cols = [c for c in ("base", "adverse", "severe") if c in df.columns]
        if has_period:
            cols = ["period"] + scenario_cols
            df = df[cols]
            parts.append("**시나리오 결과 (period × scenario)**\n")
            aligns = {c: "right" for c in scenario_cols}
            parts.append(render_dataframe_markdown(df, aligns=aligns, decimals=decimals, max_rows=max_rows))
        else:
            # Single-row aggregation: pivot to a 2-column scenario | mean table.
            row = df.iloc[0]
            tall = pd.DataFrame(
                {
                    "scenario": scenario_cols,
                    "mean_pred": [float(row[c]) for c in scenario_cols],
                }
            )
            parts.append("**시나리오 결과 (집계 평균)**\n")
            parts.append(render_dataframe_markdown(tall, aligns={"mean_pred": "right"}, decimals=decimals))
    else:
        parts.append("- 시나리오 pivot 데이터 없음.")

    parts.append(
        "**서열 위반 요약**\n\n"
        + f"- 전체 행: {order.get('n', '—')}\n"
        + f"- base > adverse 위반: {order.get('n_violation_base_vs_adverse', 0)}\n"
        + f"- adverse > severe 위반: {order.get('n_violation_adverse_vs_severe', 0)}\n"
        + f"- 총 위반: {order.get('n_violation_total', 0)}\n"
    )

    floors = list(multiplier_floors or [])
    if floors:
        rows = []
        for f in floors:
            rows.append(
                {
                    "scenario": f.get("scenario_type", ""),
                    "floor": f.get("floor", ""),
                    "n": f.get("n", ""),
                    "n_below_floor": f.get("n_below_floor", ""),
                    "violation": f.get("violation", ""),
                    "min": f.get("min", ""),
                    "max": f.get("max", ""),
                }
            )
        df = pd.DataFrame(rows)
        parts.append("\n**Multiplier floor 점검**\n")
        parts.append(
            render_dataframe_markdown(
                df,
                aligns={"floor": "right", "n": "right", "n_below_floor": "right", "min": "right", "max": "right"},
                decimals=decimals,
                max_rows=max_rows,
            )
        )
    return "\n".join(parts).strip() + "\n"
