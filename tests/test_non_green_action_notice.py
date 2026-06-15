from tests.conftest import sample_payload
from risk_team_agent_harness.app.contracts.judgement import JudgementCode


def test_non_green_creates_action_notice(hub):
    result = hub.handle(sample_payload(policy_version=None))
    assert result.overall_judgement != JudgementCode.GREEN
    assert result.action_notice_required is True
    notice = hub.notices.get(result.run_id)
    assert notice is not None
    assert notice.run_id == result.run_id


def test_blocked_request_creates_action_notice(hub):
    result = hub.handle({"request_id": "bad"})
    notice = hub.notices.get(result.run_id)
    assert result.action_notice_required is True
    assert notice is not None
    assert notice.run_id == result.run_id
