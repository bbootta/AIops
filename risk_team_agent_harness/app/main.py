from importlib.util import find_spec

if find_spec("fastapi") is not None:
    from fastapi import FastAPI, HTTPException
else:
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class FastAPI:
        def __init__(self, *args, **kwargs):
            self.routes = []

        def get(self, path):
            def decorator(func):
                self.routes.append(("GET", path, func))
                return func
            return decorator

        def post(self, path):
            def decorator(func):
                self.routes.append(("POST", path, func))
                return func
            return decorator

from risk_team_agent_harness.app.agents.risk_management_hub_agent import RiskManagementHubAgent
from risk_team_agent_harness.app.agents.self_validation_agent import SelfValidationAgent

app = FastAPI(title="Risk Management Team Agent Harness", version="0.1.0")
hub = RiskManagementHubAgent()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/runs")
def create_run(payload: dict):
    result = hub.handle(payload)
    return {
        "run_id": result.run_id,
        "status": result.status,
        "object_id": result.object_id,
        "requested_domain": result.risk_domain,
        "initial_validation_status": result.status,
        "overall_judgement": result.overall_judgement,
    }


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    result = hub.runs.get(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="run not found")
    return result


@app.get("/runs/{run_id}/evidence")
def get_evidence(run_id: str):
    return hub.evidence.list(run_id)


@app.get("/runs/{run_id}/action-notice")
def get_action_notice(run_id: str):
    notice = hub.notices.get(run_id)
    if not notice:
        raise HTTPException(status_code=404, detail="action notice not found")
    return notice


@app.post("/runs/{run_id}/self-validate")
def self_validate(run_id: str):
    result = hub.runs.get(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="run not found")
    return SelfValidationAgent(hub.notices).validate(result)
