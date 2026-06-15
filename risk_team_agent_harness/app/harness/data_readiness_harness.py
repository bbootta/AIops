from risk_team_agent_harness.app.contracts.request_contract import RiskRunRequest


class DataReadinessHarness:
    def check(self, request: RiskRunRequest) -> list[str]:
        issues = []
        if not request.data_version:
            issues.append("data_version is missing")
        return issues
