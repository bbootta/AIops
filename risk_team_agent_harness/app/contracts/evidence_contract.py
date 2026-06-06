from datetime import datetime, timezone
from .base import ContractModel, Field


class EvidenceRecord(ContractModel):
    run_id: str
    evidence_hash: str
    source: str
    data_version: str | None
    code_version: str
    policy_version: str | None
    calculation_engine_version: str | None = None
    lineage_path: list[str] = Field(default_factory=list)
    complete: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
