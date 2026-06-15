from tests.conftest import sample_payload
from risk_team_agent_harness.app.agents.self_validation_agent import SelfValidationAgent
from risk_team_agent_harness.app.contracts.judgement import JudgementCode


def test_six_domains_share_same_harness_contract(hub):
    domains = [
        ("credit_model", "estimation"),
        ("rwa", "measurement"),
        ("bis_ratio", "aggregation"),
        ("ddr", "estimation"),
        ("limit", "measurement"),
        ("rapm", "hybrid"),
        ("climate_risk", "hybrid"),
        ("ai_model_validation", "estimation"),
    ]
    for domain, family in domains:
        result = hub.handle(sample_payload(domain=domain, family=family))
        assert result.run_id
        assert result.data_version
        assert result.code_version
        assert result.policy_version
        assert result.evidence_hash
        assert result.metric_results[0].approved_engine is True


def test_end_to_end_sample_run_creates_versions_evidence_and_self_validation(hub):
    result = hub.handle(sample_payload())
    assert result.overall_judgement == JudgementCode.GREEN
    assert hub.evidence.list(result.run_id)
    validation = SelfValidationAgent(hub.notices).validate(result)
    assert validation.run_id == result.run_id
    assert validation.flags == []


def test_calculation_results_are_from_approved_engine(hub):
    result = hub.handle(sample_payload())
    assert all(metric.approved_engine for metric in result.metric_results)
    assert all(metric.placeholder_calculation for metric in result.metric_results)


def test_red_result_is_not_external_releasable_without_human_approval(hub):
    result = hub.handle(sample_payload(object_family="hybrid"))
    assert result.overall_judgement == JudgementCode.RED
    assert result.external_release_allowed is False
    assert result.report_release_status == "blocked: red result requires human approval before external sharing"
