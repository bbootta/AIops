from risk_team_agent_harness.app.contracts.request_contract import RiskRunRequest


class ObjectScopeHarness:
    expected = {
        "credit_model": "estimation",
        "rwa": "measurement",
        "bis_ratio": "aggregation",
        "ddr": "estimation",
        "limit": "measurement",
        "rapm": "hybrid",
        "climate_risk": "hybrid",
        "ai_model_validation": "estimation",
    }

    def validate(self, request: RiskRunRequest) -> list[str]:
        expected_family = self.expected.get(request.risk_domain)
        if expected_family and request.object_family != expected_family:
            return [f"RED: object_family should be {expected_family} for {request.risk_domain}"]
        return []
