import pytest
from risk_team_agent_harness.app.agents.risk_management_hub_agent import RiskManagementHubAgent


def sample_payload(domain="rwa", family="measurement", **overrides):
    payload = {
        "request_id": f"req-{domain}",
        "request_type": "standard_run",
        "risk_domain": domain,
        "object_id": f"obj-{domain}",
        "object_family": family,
        "as_of_period": "2026Q1",
        "entity_scope": "BANK_SAMPLE",
        "portfolio_scope": "PORTFOLIO_SAMPLE",
        "segment_scope": "SEGMENT_SAMPLE",
        "requested_metrics": ["sample_metric"],
        "output_formats": ["json"],
        "initiated_by": "tester",
        "user_role": "risk_analyst",
        "policy_version": "policy-sample-v1",
        "data_version": "data-sample-v1",
        "urgency": "normal",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def hub():
    return RiskManagementHubAgent()
