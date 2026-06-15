from datetime import datetime, timezone
from typing import Any
from .base import ContractModel, Field
from .judgement import JudgementCode, RunStatus


class MetricResult(ContractModel):
    metric_name: str
    value: float | int | str | None = None
    unit: str | None = None
    engine_id: str
    engine_version: str
    approved_engine: bool
    placeholder_calculation: bool = True
    notes: str = "Stub result from approved deterministic engine; not produced by agent logic."


class RiskRunResult(ContractModel):
    run_id: str
    request_id: str
    status: RunStatus
    object_id: str
    object_family: str
    risk_domain: str
    overall_judgement: JudgementCode
    metric_results: list[MetricResult] = Field(default_factory=list)
    data_quality_issues: list[str] = Field(default_factory=list)
    reconciliation_issues: list[str] = Field(default_factory=list)
    policy_findings: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    action_notice_required: bool = False
    review_required: bool = True
    external_release_allowed: bool = False
    data_version: str | None = None
    code_version: str | None = None
    policy_version: str | None = None
    regulation_mapping_id: str | None = None
    calculation_engine_version: str | None = None
    evidence_hash: str | None = None
    evidence_complete: bool = False
    report_release_status: str = "blocked"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
