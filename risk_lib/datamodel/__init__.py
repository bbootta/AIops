"""정규 리스크 데이터모델 — 스펙·카탈로그·분해·검증 (RYNTA PRD-RDM)."""
from risk_lib.datamodel.spec import (
    ColumnSpec, TableSpec, ForeignKey, Violation, SchemaError,
    validate, check_refs, ddl, summary_frame,
)
from risk_lib.datamodel import catalog
from risk_lib.datamodel.decompose import (
    decompose, decompose_from_result, validate_all, dq_result_frame,
)

__all__ = [
    "ColumnSpec", "TableSpec", "ForeignKey", "Violation", "SchemaError",
    "validate", "check_refs", "ddl", "summary_frame", "catalog",
    "decompose", "decompose_from_result", "validate_all", "dq_result_frame",
]
