from risk_team_agent_harness.app.contracts.result_contract import MetricResult
from risk_team_agent_harness.app.contracts.request_contract import RiskRunRequest


class DeterministicStubEngine:
    engine_id = "base_engine"
    version = "0.1.0"

    def run(self, request: RiskRunRequest) -> list[MetricResult]:
        return [
            MetricResult(
                metric_name=metric,
                value="placeholder_result",
                engine_id=self.engine_id,
                engine_version=self.version,
                approved_engine=True,
                placeholder_calculation=True,
            )
            for metric in request.requested_metrics
        ]
