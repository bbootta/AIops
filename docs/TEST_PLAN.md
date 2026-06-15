# 테스트 계획

## Gold set
정상 sample policy/data/regulation mapping을 가진 6개 도메인 요청이 Green 또는 명확한 판정을 만들고 run/version/evidence를 생성하는지 검증한다.

## Replay set
동일 계약을 통해 도메인별 요청이 재실행 가능하고 deterministic stub engine 결과가 승인 엔진에서 생성된 것으로 표시되는지 검증한다.

## Negative set
불완전 요청, 권한 없는 사용자, policy_version 누락, data_version 누락, evidence 미완성, 위험한 Green, Red 외부공유 가능 상태를 검증한다.

## Regulation-change set
규제 변화는 production registry 자동 반영이 아니라 candidate validation control 제안으로만 처리한다.

## Acceptance criteria
- pytest 전체 통과
- 6개 도메인 sample request 존재
- 모든 정상 run은 run_id, data_version, code_version, policy_version, evidence_hash 보유
- blocked run은 차단 사유 기록
- 실제 Basel/FSS 임계치 하드코딩 금지
- 비Green Action Notice 생성
- evidence ledger 미완성 시 report release blocked
- SelfValidationAgent가 누락 및 위험 상태 탐지
