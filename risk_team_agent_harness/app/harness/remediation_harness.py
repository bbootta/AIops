from datetime import date, timedelta
from risk_team_agent_harness.app.contracts.action_notice import ActionNotice
from risk_team_agent_harness.app.contracts.judgement import JudgementCode
from risk_team_agent_harness.app.contracts.request_contract import RiskRunRequest
from risk_team_agent_harness.app.contracts.result_contract import RiskRunResult


class RemediationHarness:
    def create_if_required(self, request: RiskRunRequest, result: RiskRunResult) -> ActionNotice | None:
        if result.overall_judgement == JudgementCode.GREEN:
            return None
        return ActionNotice(
            run_id=result.run_id,
            object_id=result.object_id,
            as_of_period=request.as_of_period,
            key_issue="; ".join(result.policy_findings or result.data_quality_issues or result.exceptions),
            impact="Human review required before use, approval, or external sharing.",
            candidate_causes=["missing policy/data/evidence", "registered control exception", "calculation or reconciliation issue"],
            required_actions=["Review evidence ledger", "Resolve issue or document override rationale", "Obtain formal human approval"],
            owner_department="Risk Management",
            due_date=(date.today() + timedelta(days=5)).isoformat(),
            escalation_path=["Risk Team Lead", "Risk Governance Committee"],
            attached_evidence=[result.evidence_hash] if result.evidence_hash else [],
        )
