# 09. 거버넌스·검증·감사 코드 리뷰

**리뷰 범위:** `risk_lib/governance/`, `risk_lib/validation/`, `risk_lib/audit_trail.py`, `risk_lib/repro.py`, `risk_lib/archive.py`, `risk_lib/rcsa.py`, `risk_lib/op_loss.py`, `risk_lib/close_workflow.py`, `risk_lib/appetite.py`.

## HIGH

### 1. `risk_lib/governance/rbac.py:290~338`, RBAC 결정이 실경계에서 미호출
- `decide_access`, `build_access_decisions`가 결정 원장은 만들지만 실제 API/CLI 경계에서 호출되지 않음. 테스트 외 grep 무결과. `cli.py`, `deliverables.py`, `studio.py`, 파이프라인 어디에도 없음.
- 실패 시나리오: 쉘 접근자가 `python -m risk_lib.cli validation-request`를 실행하면 역할 무관하게 산출·아카이브 진행. RBAC 원장은 R-OPS 거부 "해야 했음"을 기록하지만 액션은 그대로. IV 게이트만 `require()`, 역할 체크는 등가물 부재.

### 2. `risk_lib/governance/audit_chain.py:118, 150`, `verify_chain`·`chain_head` 미호출
- 문서상 tamper-evidence + 봉인 메커니즘("manifest에 실어 원장 전체를 한 값으로 봉인")이지만 테스트 외 호출 부재. `RunManifest`(`repro.py:115~142`)에 chain_head 필드 없음. 아카이브 로드 시 `verify_chain` 실행 안 함.
- 실패 시나리오: 아카이브된 `gov_audit_chain.csv` 임의 편집 → 다음 산출 팩에 그대로 로드 → 검증 미실행이라 아무도 못 봄.

## MEDIUM

### 3. `risk_lib/governance/audit_chain.py:118~147`, verify가 payload_digest 자체만 재계산
- `verify_chain`이 저장된 `payload_digest`로 `record_hash`를 재계산할 뿐, **현재 원본 원장 행**을 재해시하지 않음. source-vs-chain 대조 없음.
- 실패 시나리오: 마감 후 `aig_adjustment` 금액을 조용히 변경, `gov_audit_chain`은 그대로 → `verify_chain`이 [] 반환.

### 4. `risk_lib/governance/model_lifecycle.py:186~199` vs `:218~219`, `승인없이운영` 제어 도달 불가
- `build_transitions`가 `_INVENTORY_STAGE`가 운영/폐기인 모든 모델에 대해 무조건 `내부검증→승인` 전이를 등록. `approved = ...` 항상 True.
- 실패 시나리오: 실제 승인 회의록 없는 PROD 모델이 최악 `증빙미첨부`로만 표기됨. 의도된 "운영 중 승인 부재" 에스컬레이션은 canonical 경로에서 절대 발동 안 함.

### 5. `risk_lib/validation/cross_domain.py:305~323, 349~350`, 입력 부재 시 fail-open
- `_check_reproducibility`가 digest 중 하나라도 falsy면 `[]` 반환. `_check_ec_covers_rwa`가 `rwa is None or icaap_result is None`이면 `[]` 반환. `consistency.py`처럼 WARN sentinel 없음.
- 실패 시나리오: 파이프라인 변경으로 `icaap_result` 전달 일시 중단 → F-002 방지용 EC 커버 체크가 조용히 사라짐, "0 FAIL" 리포트.

### 6. `risk_lib/governance/change_control.py:207~270`, `required_steps` 빈 튜플 자동 통과
- `evaluate_change_gate`가 빈 `required_steps`를 `배포가능`("필수 0단계 전건 완료")으로 처리. `CHANGE_POLICY`에 `required=False`인 (change_class, risk_tier) 신설 시 무통제 배포.

## LOW
- `risk_lib/ui_studio/studio.py:246`, `check_gate(iv_request)`에 dir 미전달, 상대경로 `DEFAULT_DIR="docs/independent_validation"` 사용. `cli.py:294`는 `args.dir` 사용. 다른 CWD에서 실행 시 아카이브가 항상 `응답대기`(fail-closed지만 CLI exit과 불일치).
- `risk_lib/op_loss.py:82~93`, `aggregate_lda`의 이중 루프가 파이썬 레벨. 기본 n_sim=50k, 유형 7 × 이벤트 ~350/y → ~17M `rng.normal`. 정확성 OK, 산출 시간 이슈.
- CLAUDE.md §5 위반, `independent.py` 64, `consistency.py` 47, `doc_figures.py` 27, `cross_domain.py` 16, 그리고 `governance/` 전 파일.

## 클린
`backtest.py`, `pricing_control.py`, `retention.py`(NULL `min_retention_years`에 fail-closed 올바름), `unified_run.py`, `close_workflow.py`, `appetite.py`, `rcsa.py`, `audit_trail.py`, `repro.py`, `archive.py`.
