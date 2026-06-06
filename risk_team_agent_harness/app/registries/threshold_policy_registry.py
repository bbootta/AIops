from risk_team_agent_harness.app.contracts.judgement import JudgementCode


class ThresholdPolicyRegistry:
    def __init__(self) -> None:
        self._versions = {"policy-sample-v1": {"regulation_mapping_id": "basel-fss-sample-map-v1"}}

    def exists(self, policy_version: str | None) -> bool:
        return bool(policy_version and policy_version in self._versions)

    def regulation_mapping_id(self, policy_version: str | None) -> str | None:
        if not self.exists(policy_version):
            return None
        return self._versions[policy_version]["regulation_mapping_id"]

    def judge(self, policy_version: str | None, issues: list[str]) -> tuple[JudgementCode, list[str]]:
        if not self.exists(policy_version):
            return JudgementCode.GRAY, ["policy_version is missing or not registered"]
        if any(issue.startswith("RED:") for issue in issues):
            return JudgementCode.RED, issues
        if issues:
            return JudgementCode.AMBER, issues
        return JudgementCode.GREEN, ["No material exception identified under registered sample policy; not final approval"]
