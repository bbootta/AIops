from risk_team_agent_harness.app.contracts.action_notice import ActionNotice
from risk_team_agent_harness.app.ledgers.notification_ledger import NotificationLedger


class ActionNoticeService:
    def __init__(self, ledger: NotificationLedger) -> None:
        self.ledger = ledger

    def save(self, notice: ActionNotice | None) -> ActionNotice | None:
        return self.ledger.save(notice) if notice else None
