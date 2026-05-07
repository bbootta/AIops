"""DataFrame 스키마 강제 점검.

run_validation / run_macro_validation 같은 thin runner가 외부 CSV를
받기 전에 컬럼 존재 여부, dtype, 허용 값 범위를 사전 점검한다.

본 모듈은 데이터를 변환하지 않는다. 위반 사항만 반환한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    dtype: str = "any"  # "numeric", "binary", "string", "date", "any"
    allow_null: bool = False
    min_value: float | None = None
    max_value: float | None = None
    allowed_values: tuple | None = None


@dataclass(frozen=True)
class Schema:
    required: tuple[ColumnSpec, ...] = field(default=())
    optional: tuple[ColumnSpec, ...] = field(default=())


def _dtype_check(series: pd.Series, dtype: str) -> bool:
    if dtype == "any":
        return True
    if dtype == "numeric":
        return pd.api.types.is_numeric_dtype(series)
    if dtype == "binary":
        if not pd.api.types.is_numeric_dtype(series):
            return False
        unique = set(pd.unique(series.dropna()).tolist())
        return unique.issubset({0, 1, True, False})
    if dtype == "string":
        return pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series)
    if dtype == "date":
        if pd.api.types.is_datetime64_any_dtype(series):
            return True
        try:
            pd.to_datetime(series.dropna().head(20), errors="raise")
            return True
        except Exception:
            return False
    raise ValueError(f"unknown dtype: {dtype!r}")


def check_schema(df: pd.DataFrame, schema: Schema) -> dict:
    """스키마를 점검하고 위반 목록을 반환한다.

    반환 dict 키: passed, violations(list of dict), checked_columns(list of str)
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    violations: list[dict] = []
    checked: list[str] = []

    def _check_one(spec: ColumnSpec, required: bool) -> None:
        if spec.name not in df.columns:
            if required:
                violations.append({"type": "missing", "column": spec.name})
            return
        checked.append(spec.name)
        col = df[spec.name]
        if not _dtype_check(col, spec.dtype):
            violations.append({"type": "dtype", "column": spec.name, "expected": spec.dtype})
        if not spec.allow_null and col.isna().any():
            violations.append(
                {"type": "null", "column": spec.name, "n_null": int(col.isna().sum())}
            )
        if spec.dtype == "numeric" and (spec.min_value is not None or spec.max_value is not None):
            arr = pd.to_numeric(col, errors="coerce")
            if spec.min_value is not None and (arr < spec.min_value).any():
                violations.append(
                    {
                        "type": "min_value",
                        "column": spec.name,
                        "threshold": spec.min_value,
                        "n_violation": int((arr < spec.min_value).sum()),
                    }
                )
            if spec.max_value is not None and (arr > spec.max_value).any():
                violations.append(
                    {
                        "type": "max_value",
                        "column": spec.name,
                        "threshold": spec.max_value,
                        "n_violation": int((arr > spec.max_value).sum()),
                    }
                )
        if spec.allowed_values is not None:
            disallowed = set(pd.unique(col.dropna()).tolist()) - set(spec.allowed_values)
            if disallowed:
                violations.append(
                    {
                        "type": "allowed_values",
                        "column": spec.name,
                        "disallowed": sorted(map(str, disallowed)),
                    }
                )

    for spec in schema.required:
        _check_one(spec, required=True)
    for spec in schema.optional:
        _check_one(spec, required=False)

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "checked_columns": checked,
    }


def credit_scoring_schema(
    *,
    score_col: str,
    target_col: str,
    set_col: str | None = None,
    grade_col: str | None = None,
    pd_col: str | None = None,
    date_col: str | None = None,
) -> Schema:
    """run_validation 호환 스키마 헬퍼."""
    required: list[ColumnSpec] = [
        ColumnSpec(score_col, dtype="numeric"),
        ColumnSpec(target_col, dtype="binary"),
    ]
    optional: list[ColumnSpec] = []
    if set_col:
        optional.append(ColumnSpec(set_col, dtype="string"))
    if grade_col:
        optional.append(ColumnSpec(grade_col, dtype="any"))
    if pd_col:
        optional.append(ColumnSpec(pd_col, dtype="numeric", min_value=0.0, max_value=1.0))
    if date_col:
        optional.append(ColumnSpec(date_col, dtype="date", allow_null=True))
    return Schema(required=tuple(required), optional=tuple(optional))


def macro_schema(
    *,
    target_col: str,
    feature_cols: Iterable[str],
    period_col: str | None = None,
) -> Schema:
    """run_macro_validation 호환 스키마 헬퍼."""
    required = [ColumnSpec(target_col, dtype="numeric")]
    required.extend(ColumnSpec(c, dtype="numeric") for c in feature_cols)
    optional: list[ColumnSpec] = []
    if period_col:
        optional.append(ColumnSpec(period_col, dtype="any", allow_null=True))
    return Schema(required=tuple(required), optional=tuple(optional))
