# Operating Model

검증팀 에이전트 하니스의 표준 운영 절차.

---

## 1. 요청 접수

검증 요청은 다음 항목을 포함하여 접수한다 (`examples/sample_validation_request.md` 참조).

- 검증 대상 모형 (이름, 군, 버전)
- 검증 목적 (신규 승인, 정기 검증, 변경 검증, 모니터링 검토 등)
- 검증 범위 (방법론, 데이터, 운영, 문서화)
- 입력 데이터 위치 및 컬럼 정의
- 표본 기간 (개발 / 운영 / 모니터링)
- 목표변수 정의
- 성공 기준 (예: AUROC ≥ X, PSI ≤ Y, 보고서 모든 섹션 작성 완료)

요청이 모호하면 오케스트레이터는 **임의 해석 없이 사용자에게 질의**한다.

---

## 2. 입력 점검

`subagents/data_quality_reviewer.md`가 다음을 점검한다.

- 컬럼 정의 / 타입 / 결측 / 이상치 / 중복
- 표본 기간 누락
- 개발/운영 데이터 구분
- 누수 가능성 (target leakage)
- 표본 수 적정성 (`middleware/sample_size_guard.py`)
- 민감정보 포함 여부 (`middleware/data_safety_guard.py`)

점검 실패 시 분석 단계로 진입하지 않는다.

---

## 3. 분석 실행

`tools/`의 함수를 통해 정량 지표를 산출한다. 모든 실행은
`middleware/run_logger.py`로 기록된다.

분석 함수는 결정론적이어야 한다 (난수 사용 시 seed 명시).

---

## 4. 보고서 작성

`subagents/report_writer.md`가 결과를 검증보고서 초안 / 점검표 / 검증의견서
초안 형태로 변환한다. 모든 문안은 다음을 포함한다.

- 근거
- 한계
- 추가 확인 사항

---

## 5. 인간 검토

인간 검증자는 다음을 검토한다.

- 검증 의견의 적정성
- 한계와 추가 확인사항의 충분성
- 문서화 형식 준수 여부
- 외부 제출 적합성

**모형 승인 / 부적합 / 외부 제출 / 감독기관 대응** 결정은 인간만 수행한다.

---

## 6. 변경 이력 관리

모든 코드/정책/문서 변경은 `harness/change_manifest.json`에 기록된다.

- change_id, timestamp, component
- change_type, evidence, root_cause, targeted_fix
- expected_benefit, expected_regression_risk
- validation_method, rollback_rule, status
- human_approval_required (대부분 true)

검증되지 않은 변경은 `validated`로 표기하지 않는다.

---

## 7. 사이클 다이어그램

```
[요청 접수] -> [입력 점검] -> [분석 실행] -> [자기검증]
     ^                                            |
     |                                            v
[변경 이력 기록] <- [인간 검토] <- [보고서 작성]
```
