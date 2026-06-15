from risk_team_agent_harness.app.contracts.judgement import JudgementCode
from risk_team_agent_harness.app.contracts.request_contract import RiskRunRequest
from risk_team_agent_harness.app.registries.regulation_policy_registry import RegulationPolicyRegistry
from risk_team_agent_harness.app.registries.threshold_policy_registry import ThresholdPolicyRegistry


class PolicyHarness:
    def __init__(self, policies: ThresholdPolicyRegistry, regulations: RegulationPolicyRegistry) -> None:
        self.policies = policies
        self.regulations = regulations

    def judge(self, request: RiskRunRequest, issues: list[str]) -> tuple[JudgementCode, list[str], str | None]:
        if any(issue == "data_version is missing" for issue in issues):
            mapping_id = self.policies.regulation_mapping_id(request.policy_version)
            return JudgementCode.GRAY, ["data_version is missing"], mapping_id
        judgement, findings = self.policies.judge(request.policy_version, issues)
        mapping_id = self.policies.regulation_mapping_id(request.policy_version)
        if judgement == JudgementCode.GREEN and not self.regulations.exists(mapping_id):
            return JudgementCode.GRAY, ["regulation_mapping_id is missing or not registered"], mapping_id
        return judgement, findings, mapping_id
