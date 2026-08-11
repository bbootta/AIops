"""vta.core.models — Pydantic v2 데이터 계약 (Phase 2, Q3=a).

워크플로우 요청 envelope 을 타입 검증한다. 엔진(`WorkflowEngine.run`)은
v1 호환을 위해 여전히 Mapping 을 받으므로, 검증된 요청은
``ValidationRequest(...).to_request()`` 로 dict 변환해 전달한다.

운영 데이터 금지 원칙은 모델 차원에서 강제하지 않는다 — 데이터 안전성은
``middleware.data_safety_guard`` 와 2.safety step 이 담당한다.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ValidationRequest(BaseModel):
    """워크플로우 요청 envelope.

    공통 필드는 명시 선언으로 타입 검증하고, 부문별 입력 (capital_*, irrbb_* 등)
    은 ``extra="allow"`` 로 그대로 통과시킨다. df 는 pandas DataFrame 또는 None.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    title: str = "Validation Request"
    df: Any = None
    score_col: str | None = None
    target_col: str | None = None
    set_col: str | None = None
    grade_col: str | None = None
    pd_col: str | None = None
    date_col: str | None = None
    key_cols: list[str] = Field(default_factory=list)
    feature_names: list[str] = Field(default_factory=list)

    @field_validator("df")
    @classmethod
    def _df_is_dataframe_or_none(cls, v: Any) -> Any:
        if v is None:
            return v
        import pandas as pd

        if not isinstance(v, pd.DataFrame):
            raise ValueError(f"df must be a pandas DataFrame or None, got {type(v).__name__}")
        return v

    def to_request(self) -> dict[str, Any]:
        """엔진에 전달할 dict. df 등 임의 객체는 참조 그대로 유지."""
        out: dict[str, Any] = {}
        for name in type(self).model_fields:
            out[name] = getattr(self, name)
        if self.model_extra:
            out.update(self.model_extra)
        return out


__all__ = ["ValidationRequest"]
