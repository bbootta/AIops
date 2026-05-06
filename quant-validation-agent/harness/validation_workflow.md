# validation_workflow.md

본 문서는 양적검증의 표준 작업 절차를 정의한다.

---

## 1. 단계

```
[요청 재구성] → [데이터 계약 확인] → [분석 계획] → [실행]
       ↓
   [자기검증] → [결과 보고] → [change_manifest 기록] → [로그 저장]
```

---

## 2. 단계별 산출물

### 2.1 요청 재구성
산출물: 검증 목적, 모형 유형, 검증 구분, 입력 데이터, 필요 지표, 제약, 성공 기준.

### 2.2 데이터 계약 확인
산출물:
- 필수 컬럼 점검 결과
- 결측/중복 점검
- 표본 수, 부도건수 점검
- target/score/PD/LGD/EAD 정의 확인
- 개발/운영 구분 확인

### 2.3 분석 계획
산출물:
- 적용 지표 목록
- 표본 필터, 결측/이상치 처리 방침
- 산출 표 정의
- 테스트 방법

### 2.4 실행
산출물:
- 함수 단위 Python 코드 (`tools/`)
- pytest 테스트 (`tests/`)
- 결과 산출 (`reports/`)
- 실행 로그 (`logs/`)

### 2.5 자기검증
산출물:
- 방향성 점검
- 수치 범위 점검
- 분모 0 점검
- 표본 부족 점검
- 시나리오 서열 점검
- 결과 해석의 단정 여부 점검

### 2.6 결과 보고
산출물: `docs/validation_output_spec.md` 형식의 표준 검증 리포트.

### 2.7 change_manifest 기록
산출물: `harness/change_manifest.json`에 변경 1건 추가.

### 2.8 로그 저장
산출물: `logs/`에 JSON 또는 markdown 형태의 실행 로그.

---

## 3. 모형 유형별 분기

| 유형 | 호출 스킬 |
|---|---|
| 스코어링 | `skills/credit_score_validation.md` |
| PD | `skills/pd_model_validation.md` |
| LGD | `skills/lgd_model_validation.md` |
| EAD/CCF | `skills/ead_model_validation.md` |
| PD multiplier / 회귀 | `skills/pd_multiplier_validation.md` |
| 운영 모니터링 | `skills/monitoring_validation.md` |
| 챌린저 비교 | `skills/challenger_model_validation.md` |
| 표 생성 전용 | `skills/validation_table_generation.md` |

---

## 4. 실패 / 미완성 처리

- 데이터 부족 → RAG **Gray**, 결과에 명시.
- 함수 실패 → 원인을 데이터/코드/방법론/권한/출력으로 분류 후 `harness_debugger`에 위임.
- 임계 미정의 → 임의로 기준 부여 금지. 정책 확인 요청 항목으로 보고.
