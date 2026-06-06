from datetime import datetime, timezone
from .base import ContractModel, Field


class ActionNotice(ContractModel):
    run_id: str
    object_id: str
    as_of_period: str
    key_issue: str
    impact: str
    candidate_causes: list[str]
    required_actions: list[str]
    owner_department: str
    due_date: str
    escalation_path: list[str]
    attached_evidence: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
