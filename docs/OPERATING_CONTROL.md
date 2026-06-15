# 운영 통제

## 감사추적
모든 실행은 `request_id`, `run_id`, object/scope, version field, judgement, evidence hash를 남긴다. blocked 상태는 누락 또는 차단 사유를 `metadata.blocked_reason`에 기록한다.

## Evidence ledger
Evidence ledger는 source, lineage path, data version, code version, policy version, calculation engine version, hash, complete 여부를 기록한다. ledger가 미완성인 경우 보고서 release는 차단된다.

## Approval flow
Green은 최종 승인이 아니다. 모형 사용/변경, production 정책 반영, 감독 제출, 대외 보고, Red 결과 외부 공유는 인간 검토자와 공식 회의체 승인 대상이다.

## Change management
정책, threshold, regulation mapping, prompt, code, template 변경은 승인 전 production 반영이 차단된다. 규제 변화는 candidate validation control 제안까지만 수행하며 자동 반영하지 않는다.

## Non-Green remediation
Amber, Red, Gray 결과는 Action Notice를 생성한다. Action Notice에는 run, object, 기준시점, 이슈, 영향도, 원인 후보, 필요 조치, 담당 조직, 기한, 에스컬레이션, 첨부 증적이 포함된다.

## Production promotion control
운영 승격은 승인된 data contract, calculation logic, policy, template, deployment history가 모두 존재해야 한다. 프로토타입은 `GovernanceHarness.production_change_allowed(False)`가 차단을 표현한다.

## Red 결과 외부 공유 차단 원칙
Red는 규제위반 가능성, 보고오류 가능성, 중대 데이터 결함을 의미할 수 있으므로 인간 승인 전 `external_release_allowed=False`이며 release status가 blocked로 유지된다.
