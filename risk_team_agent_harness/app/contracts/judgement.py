from enum import StrEnum


class JudgementCode(StrEnum):
    GREEN = "Green"
    AMBER = "Amber"
    RED = "Red"
    GRAY = "Gray"


class RunStatus(StrEnum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REVIEW_REQUIRED = "review_required"
    BLOCKED = "blocked"
    APPROVED = "approved"
    REJECTED = "rejected"
