# 리스크관리 팀에이전트 하네스

## 목적
은행 리스크관리 조직이 신용평가모형, RWA, BIS 비율, 연체/부도/회수, 한도관리, RAPM, 기후리스크, AI 모형검증 업무를 통제 가능하고 감사추적 가능한 방식으로 실행하도록 지원하는 플랫폼 독립형 Agent Harness 프로토타입입니다.

## 적용 범위
- 요청 정규화, 권한 확인, 객체/범위 확인
- 승인된 결정론적 stub 계산엔진 호출
- policy/threshold/regulation mapping registry 대사
- evidence ledger 및 run ledger 기록
- Green/Amber/Red/Gray 판정과 Action Notice 생성
- SelfValidationAgent를 통한 정합성 점검

## 비범위
- 최종 승인 자동화
- 감독당국 제출 또는 대외 보고 자동화
- 실제 Basel/FSS 임계치, 해석, 산식 하드코딩
- 실제 고객 데이터, 운영 credential, 비공개 endpoint 포함

## 아키텍처 개요
`RiskManagementHubAgent`가 `/runs` 요청을 받아 Request Harness와 Identity & Access Harness를 통과시킨 뒤 도메인 Agent로 라우팅합니다. 도메인 Agent는 Execution Harness를 통해 승인된 deterministic stub engine만 호출하고, Policy Harness가 registry 기반 판정을 수행합니다. Evidence Ledger가 불완전하면 Reporting Harness는 release를 차단합니다.

## 로컬 실행 방법
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
uvicorn risk_team_agent_harness.app.main:app --reload
pytest
```

## Sample requests
8개 샘플 요청은 `risk_team_agent_harness/app/config/sample_requests.example.yaml`에 있습니다.
1. 신용평가모형 모니터링
2. RWA 산출 검증
3. BIS 비율 검증
4. 연체율 / 부도율 / 회수율 모니터링
5. 한도 사용률 모니터링
6. RAPM 분석

## Green / Amber / Red / Gray 정의
- Green: 등록된 기준상 중대 예외가 식별되지 않음. 최종 승인 아님.
- Amber: 주의, 보완, 추가 검토 필요.
- Red: 중대한 계산 불일치, 규제위반 가능성, 보고오류 가능성, 중대 데이터 결함. 인간 승인 전 외부 공유 금지.
- Gray: 데이터 부족, 정책 미정의, 표본 부족, 권한 불충분, regulation mapping 누락, 계산 실패, evidence 누락 등 판단유보.

## Fail-safe rules
- 권한 불충분 또는 필수 요청 필드 누락: `blocked`
- `policy_version` 누락: Green 금지, Gray
- `data_version` 누락: Green 금지, Gray 또는 blocked
- regulation mapping 누락: Gray
- evidence ledger 미완성: 보고서 release blocked
- Amber/Red/Gray: Action Notice 필수
- Red: 인간 승인 전 external release blocked

## Human-in-the-loop 지점
모형 사용/변경, production policy 반영, threshold 변경, regulatory mapping 반영, Red 결과 외부 공유, 감독당국 제출, 대외 보고는 인간 검토자와 공식 조직 승인 없이는 수행되지 않습니다.

## 한계 및 주의사항
현재 계산엔진은 승인된 deterministic stub입니다. 수치는 `placeholder_result`로 표시되며 실제 금융 계산이 아닙니다. 운영화 시 실제 승인 산식, 데이터 계약, 접근통제, 변경관리, 독립 검증 및 배포 승인 체계를 연결해야 합니다.

## 샘플 자체검증 보고서 생성

8개 리스크관리 부문 샘플 요청을 한 번에 실행하고 자체검증 Excel, 실무자용 Markdown/HTML, 경영진용 Markdown/HTML 보고서를 생성하려면 다음을 실행합니다.

```bash
python scripts/generate_sample_validation_reports.py
```

생성 위치는 `reports/sample_validation/`입니다. 보고서는 prototype 샘플 검증 산출물이며 실제 금융 수치, 최종 승인, 감독 제출 또는 대외 보고 근거가 아닙니다.

## 샘플 테스트 10라운드 실행

8개 리스크관리 부문 샘플 요청을 10라운드 반복 실행하고 CSV, Markdown, HTML 결과를 생성하려면 다음을 실행합니다.

```bash
python scripts/run_sample_test_rounds.py
```

생성 위치는 `reports/sample_validation/ten_round_sample_test.*`입니다. Green 결과는 등록된 샘플 기준상 중대 예외가 식별되지 않았다는 의미이며 최종 승인 또는 외부 보고 가능 상태를 의미하지 않습니다.


## 기후리스크 및 AI 모형검증 규제/권고 매핑 원칙

- 기후리스크는 Basel 기후리스크 관리 원칙 및 글로벌 권고(예: NGFS, TCFD/ISSB)를 **configurable registry** 항목으로 관리합니다.
- AI 모형검증은 글로벌 AI 리스크관리 권고(예: NIST AI RMF, OECD AI Principles)를 **configurable registry** 항목으로 관리합니다.
- 실제 임계치/해석은 코드 하드코딩이 아니라 승인된 정책·레지스트리 변경 절차를 통해서만 반영합니다.
