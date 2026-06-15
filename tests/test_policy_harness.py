from tests.conftest import sample_payload
from risk_team_agent_harness.app.contracts.judgement import JudgementCode


def test_missing_policy_version_returns_gray_not_green(hub):
    result = hub.handle(sample_payload(policy_version=None))
    assert result.overall_judgement == JudgementCode.GRAY
    assert result.overall_judgement != JudgementCode.GREEN
