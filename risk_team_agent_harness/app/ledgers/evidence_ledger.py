from risk_team_agent_harness.app.contracts.evidence_contract import EvidenceRecord


class EvidenceLedger:
    def __init__(self) -> None:
        self._records: dict[str, list[EvidenceRecord]] = {}

    def add(self, record: EvidenceRecord) -> EvidenceRecord:
        self._records.setdefault(record.run_id, []).append(record)
        return record

    def list(self, run_id: str) -> list[EvidenceRecord]:
        return self._records.get(run_id, [])

    def complete_for(self, run_id: str) -> bool:
        records = self.list(run_id)
        return bool(records) and all(record.complete for record in records)

    def clear(self) -> None:
        self._records.clear()
