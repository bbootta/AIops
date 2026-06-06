from uuid import uuid4
from risk_team_agent_harness.app.contracts.base import ValidationError
from risk_team_agent_harness.app.contracts.request_contract import RiskRunRequest


class RequestHarness:
    def normalize(self, payload: dict) -> tuple[RiskRunRequest | None, str, list[str]]:
        run_id = f"run-{uuid4().hex}"
        try:
            return RiskRunRequest.model_validate(payload), run_id, []
        except ValidationError as exc:
            return None, run_id, [f"invalid_request: {err['loc']} {err['msg']}" for err in exc.errors()]
