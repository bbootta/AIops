from risk_team_agent_harness.app.contracts.result_contract import RiskRunResult


class ReportingHarness:
    def release_status(self, result: RiskRunResult) -> str:
        if not result.evidence_complete:
            return "blocked: evidence ledger incomplete"
        if result.overall_judgement == "Red" and not result.external_release_allowed:
            return "blocked: red result requires human approval before external sharing"
        return "draft_ready_for_human_review"
