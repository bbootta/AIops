# data_requirement.md

본 문서는 모형 유형별 입력 데이터 요건을 정리한다.
필수 컬럼 누락 시 검증을 진행하지 않고 누락 항목을 보고한다.

---

## 1. 신용평가모형 / 스코어링

### 필수
- `customer_id`, `score`, `target` (0/1), `obs_date`, `dataset` (`dev`/`prod` 등)

### 선택
- `grade`, `segment`, `exposure`

### 권장 품질
- 결측 < 1% (필수 컬럼)
- 중복 ID 없음 (snapshot 단위)
- score 방향성 명시
- target 정의 일관

---

## 2. PD

### 필수
- `customer_id`, `pd` (0~1), `default_flag` (0/1), `obs_date`, `grade` 또는 `bucket`

### 선택
- `segment`, `exposure`, `time_to_default_days`

### 권장 품질
- PD 0~1 범위
- 부도 정의 일관 (90DPD 등)
- 관측창 일관 (12M 등)
- LDP 시 다년 누적 표본 권장

---

## 3. LGD

### 필수
- `customer_id`, `predicted_lgd`, `realized_lgd`, `default_date`, `recovery_completed_flag`

### 선택
- `collateral_type`, `segment`, `recovery_period_days`, `discount_rate`

### 권장 품질
- LGD 정의(현금회수율 vs 손실률) 명시
- 미완료 회수 처리 정책 명시
- 음수/100% 초과 LGD 정책 명시
- 할인율 일관

---

## 4. EAD/CCF

### 필수
- `customer_id`, `predicted_ead`, `realized_ead`, `limit`, `drawn_amount`, `default_date`

### 선택
- `product_type`, `ccf_predicted`, `ccf_realized`, `off_balance_flag`

### 권장 품질
- 부도시점 EAD 산정 기준 명시
- 약정한도 변경 이력 반영 여부 명시
- off-balance exposure 정의 명시

---

## 5. 거시경제 회귀 / PD multiplier

### 시계열 입력 (회귀 적합)
- `period`, 종속변수 1개, 설명변수 n개

### 시나리오 입력
- `scenario` ∈ {base, adverse, severe}
- `period`, 동일 설명변수, 산출 결과 컬럼

### 권장 품질
- 정상성 변환 명시
- 표본 수 ≥ 변수 수 × 10 권장
- 시차 변수의 사전 기대 부호 정의
