# Risk Control Framework

검증팀 에이전트 운영 과정에서 발생 가능한 리스크와 통제 장치.

---

## 1. 데이터 리스크

| 리스크 | 통제 |
|---|---|
| 민감정보 유입 | `middleware/data_safety_guard.py`로 패턴 탐지 후 출력/저장 차단 |
| 표본 부족 | `middleware/sample_size_guard.py`로 표본 수·부도 건수·등급별 표본 점검 |
| 결측·이상치 | `tools/data_profile.py`에서 명시적 보고 |
| 기간 누락 | `tools/data_profile.check_date_coverage`로 점검 |
| 누수 | `middleware/leakage_guard.py`로 target/outcome 변수 사용 점검 |

---

## 2. 방법론 리스크

| 리스크 | 통제 |
|---|---|
| 다중공선성 | `tools/regression_diagnostics.calculate_vif` |
| 비정상 시계열 | `tools/regression_diagnostics`의 잔차 진단 |
| 시나리오 서열 위반 | `tools/scenario_order_check` |
| 챌린저 모형 부재 | `skills/challenger_model_review.md`에 점검 항목 명시 |

---

## 3. 코드 리스크

| 리스크 | 통제 |
|---|---|
| 결정론성 부족 | seed 명시 / pure function 원칙 |
| 테스트 누락 | `tests/`의 pytest 강제 |
| 부작용 | tools 함수는 파일 시스템·네트워크에 부작용 없도록 작성 |

---

## 4. 운영 리스크

| 리스크 | 통제 |
|---|---|
| 운영계 직접 변경 | `middleware/permission_guard.py`로 위험 명령어 탐지 |
| 외부 전송 | permission_guard에서 차단 |
| 무단 배포 / 푸시 | CLAUDE.md 권한 제한 / 사용자 승인 필수 |

---

## 5. 내부통제 리스크

| 리스크 | 통제 |
|---|---|
| 권한 분리 위반 | `harness/permission_policy.md`에 권한 매트릭스 명시 |
| 변경 이력 부재 | `harness/change_manifest.json` 강제 기록 |
| 검증 기준 임의 완화 | `harness/validation_policy.md`에 기준 고정 |

---

## 6. 문서화 리스크

| 리스크 | 통제 |
|---|---|
| 필수 섹션 누락 | `middleware/output_completeness_guard.py` |
| 한계 누락 | output_completeness_guard에서 점검 |
| 근거 부재 | 모든 보고서 문안에 근거·한계·추가 확인사항 의무 |

---

## 7. 감사 대응 리스크

| 리스크 | 통제 |
|---|---|
| 재현 불가 | 입력·코드·로그·산출물을 한 세트로 보존 |
| 감사추적 단절 | `middleware/run_logger.py`로 실행 메타데이터 일관 기록 |
| 변경 사유 부재 | change_manifest의 evidence / root_cause 필드 강제 |
