from tests.conftest import sample_payload
from risk_team_agent_harness.app.agents.self_validation_agent import SelfValidationAgent
from risk_team_agent_harness.app.contracts.judgement import JudgementCode


def test_self_validation_detects_green_without_evidence(hub):
    result = hub.handle(sample_payload())
    payload = result.model_dump()
    payload["evidence_hash"] = None
    payload["overall_judgement"] = JudgementCode.GREEN
    validation = SelfValidationAgent(hub.notices).validate(payload)
    assert "missing_evidence_hash" in validation.flags
    assert "dangerous_green_with_missing_required_field" in validation.flags


def test_self_validation_detects_missing_run_id_or_versions(hub):
    result = hub.handle(sample_payload())
    payload = result.model_dump()
    payload["run_id"] = None
    payload["code_version"] = None
    validation = SelfValidationAgent(hub.notices).validate(payload)
    assert "missing_run_id" in validation.flags
    assert "missing_code_version" in validation.flags


def test_red_result_external_release_is_flagged(hub):
    result = hub.handle(sample_payload(object_family="hybrid"))
    payload = result.model_dump()
    payload["overall_judgement"] = JudgementCode.RED
    payload["external_release_allowed"] = True
    validation = SelfValidationAgent(hub.notices).validate(payload)
    assert "red_result_external_release_without_human_approval" in validation.flags
