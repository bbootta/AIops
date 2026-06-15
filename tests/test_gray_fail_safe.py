from tests.conftest import sample_payload
from risk_team_agent_harness.app.contracts.judgement import JudgementCode, RunStatus


def test_missing_data_version_returns_gray_or_blocked_not_green(hub):
    result = hub.handle(sample_payload(data_version=None))
    assert result.overall_judgement == JudgementCode.GRAY
    assert result.status in {RunStatus.REVIEW_REQUIRED, RunStatus.BLOCKED}
    assert result.overall_judgement != JudgementCode.GREEN


def test_incomplete_evidence_blocks_report_release(hub):
    result = hub.handle(sample_payload(data_version=None))
    assert result.evidence_complete is False
    assert result.report_release_status == "blocked: evidence ledger incomplete"
