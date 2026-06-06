class ApprovalLedger:
    def __init__(self) -> None:
        self._approved_for_external_release: set[str] = set()

    def approve_external_release(self, run_id: str) -> None:
        self._approved_for_external_release.add(run_id)

    def is_external_release_approved(self, run_id: str) -> bool:
        return run_id in self._approved_for_external_release
