from risk_team_agent_harness.app.contracts.result_contract import RiskRunResult


class RunLedger:
    def __init__(self) -> None:
        self._runs: dict[str, RiskRunResult] = {}

    def save(self, result: RiskRunResult) -> RiskRunResult:
        self._runs[result.run_id] = result
        return result

    def get(self, run_id: str) -> RiskRunResult | None:
        return self._runs.get(run_id)

    def clear(self) -> None:
        self._runs.clear()
