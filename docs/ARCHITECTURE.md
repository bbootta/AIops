# 아키텍처

## Agent 책임분리
- `RiskManagementHubAgent`: 진입점, 요청 검증, 권한 확인, 도메인 라우팅. 직접 계산 또는 승인하지 않는다.
- `CreditRatingModelAgent`: PD/LGD/EAD/Scorecard/Rating Model 모니터링 workflow.
- `RWAAgent`: 익스포져 분류, CRM, 위험가중치, RWA 재수행 workflow.
- `BISRatioAgent`: 자본/RWA 집계, BIS ratio, reconciliation workflow.
- `DelinquencyDefaultRecoveryAgent`: 연체율, 부도율, 회수율 모니터링 workflow.
- `LimitManagementAgent`: 한도 사용률, 초과, 임계치 근접, 에스컬레이션 workflow.
- `RAPMAgent`: 위험조정성과, 자본비용, 포트폴리오 수익성 workflow.
- `SelfValidationAgent`: 결과를 override하지 않고 누락, 위험한 Green, evidence 미비, Red 외부공유 위험을 flag한다.

## Harness architecture
Request, Identity & Access, Object & Scope, Data Readiness, Data Lineage, Execution, Policy, Regulation, Reporting, Remediation, Evaluation, Governance Harness로 분리했다. 각 Harness는 업무 통제를 명시적으로 담당한다.

## Registry 및 ledger design
Registry는 validation object, metric library, calculation logic, policy/threshold, regulation mapping을 보관한다. Ledger는 run, evidence, approval, notification 기록을 보관한다. 프로토타입은 in-memory 저장소를 사용한다.

## Deterministic engine separation
Agent는 금융 수치나 규제비율을 직접 만들지 않는다. 모든 metric result는 `approved_engine=True`인 deterministic stub engine에서 생성되며 `placeholder_calculation=True`로 표시된다.

## SelfValidationAgent 역할
필수 필드, run/version/evidence 존재, 비Green Action Notice, 승인 엔진 여부, evidence 미완성 report release, Red external release 상태를 독립적으로 점검한다.

## 계산엔진과 LLM 계층 분리 원칙
LLM/Agent 계층은 orchestration, 입력 검증, Tool 호출, 증적 정리, 설명 생성, 보고서 초안만 담당한다. 산식, 규제비율, 최종 판정, 제출 승인은 결정론적 엔진과 인간 검토자가 담당한다.
