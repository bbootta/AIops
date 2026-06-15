from datetime import date, timedelta
from risk_team_agent_harness.app.agents.bis_ratio_agent import BISRatioAgent
from risk_team_agent_harness.app.agents.credit_rating_model_agent import CreditRatingModelAgent
from risk_team_agent_harness.app.agents.climate_risk_agent import ClimateRiskAgent
from risk_team_agent_harness.app.agents.ai_model_validation_agent import AIModelValidationAgent
from risk_team_agent_harness.app.agents.delinquency_default_recovery_agent import DelinquencyDefaultRecoveryAgent
from risk_team_agent_harness.app.agents.limit_management_agent import LimitManagementAgent
from risk_team_agent_harness.app.agents.rapm_agent import RAPMAgent
from risk_team_agent_harness.app.agents.rwa_agent import RWAAgent
from risk_team_agent_harness.app.contracts.action_notice import ActionNotice
from risk_team_agent_harness.app.contracts.judgement import JudgementCode, RunStatus
from risk_team_agent_harness.app.contracts.result_contract import RiskRunResult
from risk_team_agent_harness.app.engines.bis_ratio_engine import BISRatioEngine
from risk_team_agent_harness.app.engines.credit_model_engine import CreditModelEngine
from risk_team_agent_harness.app.engines.climate_risk_engine import ClimateRiskEngine
from risk_team_agent_harness.app.engines.ai_model_validation_engine import AIModelValidationEngine
from risk_team_agent_harness.app.engines.delinquency_default_recovery_engine import DelinquencyDefaultRecoveryEngine
from risk_team_agent_harness.app.engines.limit_engine import LimitEngine
from risk_team_agent_harness.app.engines.rapm_engine import RAPMEngine
from risk_team_agent_harness.app.engines.rwa_engine import RWAEngine
from risk_team_agent_harness.app.harness.execution_harness import ExecutionHarness
from risk_team_agent_harness.app.harness.identity_access_harness import IdentityAccessHarness
from risk_team_agent_harness.app.harness.policy_harness import PolicyHarness
from risk_team_agent_harness.app.harness.request_harness import RequestHarness
from risk_team_agent_harness.app.ledgers.evidence_ledger import EvidenceLedger
from risk_team_agent_harness.app.ledgers.notification_ledger import NotificationLedger
from risk_team_agent_harness.app.ledgers.run_ledger import RunLedger
from risk_team_agent_harness.app.registries.calculation_logic_registry import CalculationLogicRegistry
from risk_team_agent_harness.app.registries.regulation_policy_registry import RegulationPolicyRegistry
from risk_team_agent_harness.app.registries.threshold_policy_registry import ThresholdPolicyRegistry


class RiskManagementHubAgent:
    def __init__(self) -> None:
        self.runs = RunLedger()
        self.evidence = EvidenceLedger()
        self.notices = NotificationLedger()
        execution = ExecutionHarness(CalculationLogicRegistry())
        policy = PolicyHarness(ThresholdPolicyRegistry(), RegulationPolicyRegistry())
        self.request_harness = RequestHarness()
        self.access = IdentityAccessHarness()
        self.agents = {
            "credit_model": CreditRatingModelAgent(CreditModelEngine(), execution, policy, self.evidence, self.notices),
            "rwa": RWAAgent(RWAEngine(), execution, policy, self.evidence, self.notices),
            "bis_ratio": BISRatioAgent(BISRatioEngine(), execution, policy, self.evidence, self.notices),
            "ddr": DelinquencyDefaultRecoveryAgent(DelinquencyDefaultRecoveryEngine(), execution, policy, self.evidence, self.notices),
            "limit": LimitManagementAgent(LimitEngine(), execution, policy, self.evidence, self.notices),
            "rapm": RAPMAgent(RAPMEngine(), execution, policy, self.evidence, self.notices),
            "climate_risk": ClimateRiskAgent(ClimateRiskEngine(), execution, policy, self.evidence, self.notices),
            "ai_model_validation": AIModelValidationAgent(AIModelValidationEngine(), execution, policy, self.evidence, self.notices),
        }

    def handle(self, payload: dict) -> RiskRunResult:
        request, run_id, request_errors = self.request_harness.normalize(payload)
        if request is None:
            return self.runs.save(self._blocked(run_id, payload.get("request_id", "unknown"), payload, request_errors))
        access_errors = self.access.authorize(request)
        if access_errors:
            return self.runs.save(self._blocked(run_id, request.request_id, request.model_dump(), access_errors))
        result = self.agents[request.risk_domain].run(run_id, request)
        return self.runs.save(result)

    def _blocked(self, run_id: str, request_id: str, payload: dict, errors: list[str]) -> RiskRunResult:
        result = RiskRunResult(
            run_id=run_id,
            request_id=request_id,
            status=RunStatus.BLOCKED,
            object_id=payload.get("object_id", "unknown"),
            object_family=payload.get("object_family", "unknown"),
            risk_domain=payload.get("risk_domain", "unknown"),
            overall_judgement=JudgementCode.GRAY,
            exceptions=errors,
            action_notice_required=True,
            review_required=True,
            metadata={"blocked_reason": errors},
        )
        self.notices.save(
            ActionNotice(
                run_id=run_id,
                object_id=result.object_id,
                as_of_period=payload.get("as_of_period", "unknown"),
                key_issue="; ".join(errors),
                impact="Execution blocked; human review is required before retry, use, approval, or sharing.",
                candidate_causes=["invalid request", "insufficient authority", "missing required control input"],
                required_actions=["Correct the request or access grant", "Re-submit through the standard run endpoint"],
                owner_department="Risk Management",
                due_date=(date.today() + timedelta(days=2)).isoformat(),
                escalation_path=["Risk Team Lead", "Risk Governance Committee"],
            )
        )
        return result
