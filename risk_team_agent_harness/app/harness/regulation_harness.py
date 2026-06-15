from risk_team_agent_harness.app.registries.regulation_policy_registry import RegulationPolicyRegistry


class RegulationHarness:
    def __init__(self, registry: RegulationPolicyRegistry) -> None:
        self.registry = registry

    def propose_candidate_controls(self, change_summary: str) -> list[dict[str, str]]:
        return self.registry.candidate_validation_controls(change_summary)
