from risk_team_agent_harness.app.contracts.judgement import JudgementCode
from risk_team_agent_harness.app.contracts.judgement import RunStatus


def test_incomplete_request_is_blocked(hub):
    result = hub.handle({"request_id": "bad"})
    assert result.status == RunStatus.BLOCKED
    assert result.overall_judgement == JudgementCode.GRAY
    assert result.metadata["blocked_reason"]
