# API 명세

- `POST /runs`: 표준 리스크관리 실행 요청 접수. `run_id`, status, object, domain, initial validation status 반환.
- `GET /runs/{run_id}`: 실행 상태, 판정, 주요 결과, version, evidence 상태 반환.
- `GET /runs/{run_id}/evidence`: evidence ledger entries 반환.
- `GET /runs/{run_id}/action-notice`: Amber/Red/Gray Action Notice 반환.
- `POST /runs/{run_id}/self-validate`: SelfValidationAgent 정합성 점검 결과 반환.
- `GET /health`: 시스템 상태 반환.
