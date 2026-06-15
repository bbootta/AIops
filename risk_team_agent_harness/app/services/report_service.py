from risk_team_agent_harness.app.contracts.result_contract import RiskRunResult
from risk_team_agent_harness.app.harness.reporting_harness import ReportingHarness


class ReportService:
    def __init__(self, reporting: ReportingHarness) -> None:
        self.reporting = reporting

    def draft_metadata(self, result: RiskRunResult) -> dict[str, object]:
        return {
            "run_id": result.run_id,
            "request_id": result.request_id,
            "object_id": result.object_id,
            "data_version": result.data_version,
            "code_version": result.code_version,
            "policy_version": result.policy_version,
            "calculation_engine_version": result.calculation_engine_version,
            "generated_at": result.completed_at,
            "reviewer_required": True,
            "release_status": self.reporting.release_status(result),
        }
