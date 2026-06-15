from risk_team_agent_harness.app.contracts.request_contract import RiskRunRequest


class IdentityAccessHarness:
    allowed_roles = {"risk_analyst", "risk_manager", "model_validator", "auditor", "admin"}

    def authorize(self, request: RiskRunRequest) -> list[str]:
        if request.user_role not in self.allowed_roles:
            return ["insufficient_authority"]
        return []
