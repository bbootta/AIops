from typing import Literal
from .base import ContractModel, Field


RiskDomain = Literal["credit_model", "rwa", "bis_ratio", "ddr", "limit", "rapm", "climate_risk", "ai_model_validation"]
ObjectFamily = Literal["estimation", "measurement", "aggregation", "hybrid"]


class RiskRunRequest(ContractModel):
    request_id: str = Field(min_length=1)
    request_type: str = Field(min_length=1)
    risk_domain: RiskDomain
    object_id: str = Field(min_length=1)
    object_family: ObjectFamily
    as_of_period: str = Field(min_length=1)
    entity_scope: str = Field(min_length=1)
    portfolio_scope: str = Field(min_length=1)
    segment_scope: str = Field(min_length=1)
    requested_metrics: list[str] = Field(min_length=1)
    output_formats: list[str] = Field(default_factory=lambda: ["json"])
    initiated_by: str = Field(min_length=1)
    user_role: str = Field(min_length=1)
    policy_version: str | None = None
    data_version: str | None = None
    urgency: str = "normal"
