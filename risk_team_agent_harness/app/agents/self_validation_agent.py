from risk_team_agent_harness.app.contracts.base import ContractModel, Field
from risk_team_agent_harness.app.contracts.judgement import JudgementCode
from risk_team_agent_harness.app.contracts.result_contract import RiskRunResult
from risk_team_agent_harness.app.ledgers.notification_ledger import NotificationLedger


class SelfValidationResult(ContractModel):
    run_id: str | None
    review_required: bool
    flags: list[str] = Field(default_factory=list)


class SelfValidationAgent:
    def __init__(self, notices: NotificationLedger | None = None) -> None:
        self.notices = notices

    def validate(self, result: RiskRunResult | dict) -> SelfValidationResult:
        data = result.model_dump() if isinstance(result, RiskRunResult) else result
        flags: list[str] = []
        for field in [
            "run_id",
            "data_version",
            "code_version",
            "policy_version",
            "regulation_mapping_id",
            "evidence_hash",
        ]:
            if not data.get(field):
                flags.append(f"missing_{field}")
        judgement = data.get("overall_judgement")
        if judgement == JudgementCode.GREEN and any(flag.startswith("missing_") for flag in flags):
            flags.append("dangerous_green_with_missing_required_field")
        if judgement != JudgementCode.GREEN:
            run_id = data.get("run_id")
            if not run_id or (self.notices and self.notices.get(run_id) is None):
                flags.append("non_green_without_action_notice")
        if data.get("metric_results"):
            for metric in data["metric_results"]:
                approved = metric.get("approved_engine") if isinstance(metric, dict) else metric.approved_engine
                if not approved:
                    flags.append("metric_not_from_approved_engine")
        if not data.get("evidence_complete") and data.get("report_release_status") != "blocked: evidence ledger incomplete":
            flags.append("report_released_with_incomplete_evidence")
        if data.get("reconciliation_issues") and not data.get("review_required"):
            flags.append("cross_domain_reconciliation_issue_not_flagged")
        if judgement == JudgementCode.RED and data.get("external_release_allowed"):
            flags.append("red_result_external_release_without_human_approval")
        return SelfValidationResult(run_id=data.get("run_id"), review_required=bool(flags), flags=flags)
