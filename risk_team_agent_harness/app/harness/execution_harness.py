from risk_team_agent_harness.app.contracts.request_contract import RiskRunRequest
from risk_team_agent_harness.app.contracts.result_contract import MetricResult
from risk_team_agent_harness.app.registries.calculation_logic_registry import CalculationLogicRegistry


class ExecutionHarness:
    def __init__(self, registry: CalculationLogicRegistry) -> None:
        self.registry = registry

    def execute(self, engine, request: RiskRunRequest) -> tuple[list[MetricResult], list[str]]:
        results = engine.run(request)
        issues = []
        for result in results:
            result.approved_engine = self.registry.is_approved(result.engine_id, result.engine_version)
            if not result.approved_engine:
                issues.append(f"RED: unapproved calculation engine {result.engine_id}:{result.engine_version}")
        return results, issues
