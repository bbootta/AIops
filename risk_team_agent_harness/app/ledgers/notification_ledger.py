from risk_team_agent_harness.app.contracts.action_notice import ActionNotice


class NotificationLedger:
    def __init__(self) -> None:
        self._notices: dict[str, ActionNotice] = {}

    def save(self, notice: ActionNotice) -> ActionNotice:
        self._notices[notice.run_id] = notice
        return notice

    def get(self, run_id: str) -> ActionNotice | None:
        return self._notices.get(run_id)

    def clear(self) -> None:
        self._notices.clear()
