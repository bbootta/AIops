from datetime import datetime, timezone
from risk_team_agent_harness.app.contracts.judgement import JudgementCode, RunStatus
from risk_team_agent_harness.app.contracts.request_contract import RiskRunRequest
from risk_team_agent_harness.app.contracts.result_contract import RiskRunResult
from risk_team_agent_harness.app.harness.data_lineage_harness import DataLineageHarness
from risk_team_agent_harness.app.harness.data_readiness_harness import DataReadinessHarness
from risk_team_agent_harness.app.harness.execution_harness import ExecutionHarness
from risk_team_agent_harness.app.harness.object_scope_harness import ObjectScopeHarness
from risk_team_agent_harness.app.harness.policy_harness import PolicyHarness
from risk_team_agent_harness.app.harness.reporting_harness import ReportingHarness
from risk_team_agent_harness.app.harness.remediation_harness import RemediationHarness
from risk_team_agent_harness.app.harness.governance_harness import GovernanceHarness
from risk_team_agent_harness.app.ledgers.evidence_ledger import EvidenceLedger
from risk_team_agent_harness.app.ledgers.notification_ledger import NotificationLedger


class DomainAgent:
    def __init__(self, engine, execution: ExecutionHarness, policy: PolicyHarness, evidence: EvidenceLedger, notices: NotificationLedger) -> None:
        self.engine = engine
        self.execution = execution
        self.policy = policy
        self.evidence = evidence
        self.notices = notices
        self.scope = ObjectScopeHarness()
        self.readiness = DataReadinessHarness()
        self.lineage = DataLineageHarness()
        self.reporting = ReportingHarness()
        self.remediation = RemediationHarness()
        self.governance = GovernanceHarness()

    def run(self, run_id: str, request: RiskRunRequest) -> RiskRunResult:
        issues = self.scope.validate(request) + self.readiness.check(request)
        metric_results, execution_issues = self.execution.execute(self.engine, request)
        issues.extend(execution_issues)
        judgement, findings, mapping_id = self.policy.judge(request, issues)
        engine_version = self.engine.version
        evidence = self.lineage.build_evidence(run_id, request, self.governance.code_version, engine_version)
        self.evidence.add(evidence)
        status = RunStatus.COMPLETED if judgement == JudgementCode.GREEN else RunStatus.REVIEW_REQUIRED
        result = RiskRunResult(
            run_id=run_id,
            request_id=request.request_id,
            status=status,
            object_id=request.object_id,
            object_family=request.object_family,
            risk_domain=request.risk_domain,
            overall_judgement=judgement,
            metric_results=metric_results,
            data_quality_issues=[issue for issue in issues if "data" in issue],
            policy_findings=findings,
            exceptions=[issue for issue in issues if issue.startswith("RED:")],
            action_notice_required=judgement != JudgementCode.GREEN,
            review_required=True,
            external_release_allowed=False,
            data_version=request.data_version,
            code_version=self.governance.code_version,
            policy_version=request.policy_version,
            regulation_mapping_id=mapping_id,
            calculation_engine_version=engine_version,
            evidence_hash=evidence.evidence_hash,
            evidence_complete=evidence.complete,
            completed_at=datetime.now(timezone.utc),
        )
        result.report_release_status = self.reporting.release_status(result)
        notice = self.remediation.create_if_required(request, result)
        if notice:
            self.notices.save(notice)
        return result
