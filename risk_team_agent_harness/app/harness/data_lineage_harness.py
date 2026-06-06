import hashlib
from risk_team_agent_harness.app.contracts.evidence_contract import EvidenceRecord
from risk_team_agent_harness.app.contracts.request_contract import RiskRunRequest


class DataLineageHarness:
    def build_evidence(self, run_id: str, request: RiskRunRequest, code_version: str, engine_version: str | None) -> EvidenceRecord:
        seed = f"{run_id}|{request.request_id}|{request.object_id}|{request.data_version}|{request.policy_version}|{code_version}"
        return EvidenceRecord(
            run_id=run_id,
            evidence_hash=hashlib.sha256(seed.encode()).hexdigest(),
            source="prototype_lineage",
            data_version=request.data_version,
            code_version=code_version,
            policy_version=request.policy_version,
            calculation_engine_version=engine_version,
            lineage_path=["source_data", "intermediate_result", "metric_result"],
            complete=bool(request.data_version),
        )
