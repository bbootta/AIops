from tests.conftest import sample_payload
from risk_team_agent_harness.app.contracts.judgement import RunStatus


def test_unauthorized_user_is_blocked(hub):
    result = hub.handle(sample_payload(user_role="front_office"))
    assert result.status == RunStatus.BLOCKED
    assert "insufficient_authority" in result.exceptions
