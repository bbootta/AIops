# Sample Input Schema

검증 요청 시 데이터를 다음과 같은 컬럼 정의로 전달한다 (실제 운영 스키마와는 무관).

## 1. 신용평가모형 검증 입력

| 컬럼 | 타입 | 단위 / 값 | 결측 처리 |
|---|---|---|---|
| `customer_id` | string | 가명 식별자 | 결측 불가 |
| `obs_date` | date | YYYY-MM-DD | 결측 불가 |
| `score` | float | 모형 점수 (높을수록 위험 가정) | 결측 불가 |
| `target` | int | 12개월 부도 여부 0/1 | 결측 불가 |
| `grade` | string | 등급 (옵션) | 허용 |
| `set` | string | 'dev' / 'oot' / 'mon' | 결측 불가 |

## 2. PD/LGD/EAD 검증 입력

| 요소 | 핵심 컬럼 |
|---|---|
| PD | `grade`, `pd_estimated`, `default_count`, `exposure_count` |
| LGD | `lgd_estimated`, `lgd_realized`, `recovery_rate` |
| EAD | `limit`, `usage_rate`, `ccf_estimated`, `ead_realized` |

## 3. IFRS 9 ECL 검증 입력

| 컬럼 | 설명 |
|---|---|
| `stage` | 1 / 2 / 3 |
| `pd`, `lgd`, `ead` | 스테이지별 사용 |
| `scenario` | base / adverse / severe |
| `weight` | 시나리오 가중치 (합 = 1) |
| `fli_*` | forward-looking 변수들 |

## 4. 거시 시나리오 모형 입력

| 컬럼 | 설명 |
|---|---|
| `period` | YYYY-Q* 또는 YYYY-MM |
| `gdp_growth`, `unemployment`, `interest_rate`, `fx_rate`, `housing_price` | 거시 변수 |
| `target_macro` | 추정 대상 (예: 시스템 PD, 손실률) |

---

## 금지 컬럼 (수신 거부)

- 주민등록번호, 계좌번호, 카드번호, 전화번호, 이메일
- 비식별화되지 않은 고객 식별정보

탐지 시 `middleware/data_safety_guard.py`가 차단 사유를 반환한다.
