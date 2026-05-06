# data_contract.md

본 문서는 입력 데이터에 대한 **계약(contract)** 을 정의한다.
계약을 충족하지 못하면 검증을 진행하지 않고 누락 항목을 보고한다.

운영계 데이터 직접 접속은 금지되며, 모든 입력은 검증용 추출 / 익명화 / 샘플 데이터로 한정한다.

---

## 1. 공통 요건

| 항목 | 요구사항 |
|---|---|
| 인코딩 | UTF-8 |
| 결측 표기 | 빈 칸, NA, NaN 중 하나로 통일 |
| 날짜 컬럼 | ISO 8601 (YYYY-MM-DD) |
| 식별자 | 익명 ID (주민/계좌/카드/전화/이메일 금지) |
| 컬럼명 | 영문 소문자 + underscore 권장 |

---

## 2. 신용평가모형 / 스코어링 모형

### 필수 컬럼
- `customer_id` (익명 ID)
- `score` (실수, 방향성 명시)
- `target` (0/1; 1=불량/부도)
- `obs_date` 또는 `snapshot_date`
- `dataset` (`train` / `test` / `oot` / `dev` / `prod`)

### 선택 컬럼
- `grade` (등급)
- `segment` (세그먼트)
- `exposure` (잔액)

### 점검 항목
- `score` 방향성: 높을수록 양호 vs 불량
- `target` 정의 일관성
- 개발/운영 표본 분리
- 기준시점, 관측기간

---

## 3. PD 모형

### 필수 컬럼
- `customer_id`
- `pd` (예측 PD; 0~1 실수)
- `default_flag` (0/1, 관측창 내 부도 여부)
- `obs_date`
- `grade` 또는 `bucket`

### 선택 컬럼
- `segment`
- `exposure`
- `time_to_default_days`

### 점검 항목
- PD 범위 (0~1)
- 부도 정의 일관성
- 관측창 일관성
- 장기평균 PD 대비 단기 관측값 혼동 여부
- LDP(low default portfolio) 여부

---

## 4. LGD 모형

### 필수 컬럼
- `customer_id`
- `predicted_lgd` (0~1 실수)
- `realized_lgd` (실수; 음수/100% 초과 처리 정책 명시)
- `default_date`
- `recovery_completed_flag` (회수 종결 여부)

### 선택 컬럼
- `collateral_type`
- `segment`
- `recovery_period_days`
- `discount_rate`

### 점검 항목
- LGD 범위 (음수/초과 처리 정책)
- 미완료 회수 처리 방식
- 할인율 적용 일관성
- downturn 식별 가능성

---

## 5. EAD/CCF 모형

### 필수 컬럼
- `customer_id`
- `predicted_ead` (실수)
- `realized_ead` (실수)
- `limit` (한도)
- `drawn_amount` (사용금액)
- `default_date`

### 선택 컬럼
- `product_type`
- `ccf_predicted`
- `ccf_realized`
- `off_balance_flag`

### 점검 항목
- 미사용한도 정의
- 부도시점 EAD 산정 기준
- off-balance exposure 처리
- 음수/과도한 CCF

---

## 6. 거시경제 시나리오 회귀모형 / PD multiplier

### 시계열 입력 (회귀 적합용)
- `period` (분기/연도)
- 종속변수: `pd_target` 또는 `pd_multiplier`
- 설명변수: `gdp_growth`, `unemployment`, `bond_spread`, … (n개)

### 시나리오 입력
- `scenario` (`base` / `adverse` / `severe`)
- `period`
- 동일 설명변수 컬럼
- 산출 결과 `pd_pred` 또는 `pd_multiplier`

### 점검 항목
- 정상성 변환 여부
- 표본 수 / 변수 수
- 시차 변수 사용
- 시나리오 서열: `base ≤ adverse ≤ severe`
- multiplier floor 적용 정책

---

## 7. 모니터링

### 필수 컬럼
- `obs_date`
- `grade` 또는 `bucket`
- `count`
- `default_count`
- 분포 비교 대상의 `dataset` 식별자

---

## 8. 계약 위반 처리

- 필수 컬럼 누락 → `schema_guard` 차단, 검증 진행 불가.
- 표본/부도건수 부족 → `sample_size_guard` 경고, 결과는 RAG **Gray** 또는 **Yellow**.
- 사후정보 의심 컬럼이 설명변수에 포함 → `leakage_guard` 경고.
- 개인정보 패턴 탐지 → `data_safety_guard` 즉시 중단 권고.
