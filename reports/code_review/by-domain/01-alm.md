# 01. ALM 도메인 코드 리뷰

**리뷰 범위:** `risk_lib/alm/*.py` (14 파일).

## HIGH

### 1. `risk_lib/alm/contracts.py:189~190`, 재설정 창 하드코딩
- 모든 변동금리 계약에 0.25년 재설정 창을 하드코딩. `params._PRODUCTS`의 `LN_RETAIL`, `LN_MTG_FLT`는 `reset_freq_months=6`인데 `next_reset_date`가 `(1/365.25, 0.25 + 1/365.25]` 년에서 표본.
- 실패 시나리오: 6개월 변동 소매·mortgage 대출의 재설정 일자가 0~3개월에 압축 → repricing ladder 슬롯이 과소 편향, 재산정 소요시간을 mortgage EAD의 약 절반, retail_other EAD의 100%에서 저평가.

### 2. `risk_lib/alm/nsfr.py:170~174` + `balance_sheet.py:172~174`, 은행 대출 RSF 오매핑
- 잔존만기 ≥1y 금융기관 대출이 `other_loans_ge1y`(85% RSF)로 매핑. BCBS d295 NSF30.14는 100% RSF 요구.
- 실패 시나리오: 2y 만기 은행간 대출 1T KRW 포트폴리오가 RSF 850B(정답 1T) → NSFR 과대.

## MEDIUM

### 3. `risk_lib/alm/cashflow.py:206` vs `liquidity.py:402`, 버킷 경계 관례 불일치
- `_Buckets.assign`은 `searchsorted(side="right")`(즉 `[lower, upper)`, t=1/12 → 버킷 1), `_slot`은 `side="left"`(즉 `(lower, upper]`, t=1/12 → 버킷 0). 3개월 정확 경계 계약이 `build_maturity_ladder` vs `build_repricing_ladder`에서 다른 버킷.

### 4. `risk_lib/alm/behaviour.py:189, 225`, 이자 계산 day_count 불일치
- `apply_prepayment`/`apply_early_redemption`가 `tau = ins.t_years - prev_t`(365.25 기반) 사용. `build_schedule`은 상품 `day_count` 기반 `year_fraction(...)` 사용. 30/360, ACT/360 상품에서 CPR=0/TDRR=0에서도 행동 CF 이자 ≠ 계약 CF 이자 → `adjustment_cf`가 day-count 불일치를 "behaviour"에 귀속.

### 5. `risk_lib/alm/nii.py:277~288`, 통화 하나 결측 시 시나리오 전체 드롭
- 한 `(ccy, scenario)` 쌍 결측 시 `break`. 소액 외화 shock 파라미터가 NULL이면 KRW 포함 시나리오 전체가 ΔNII 없음. `irrbb.py`의 `_aggregate_across_currencies`는 통화별 독립 처리.

### 6. `risk_lib/alm/contracts.py:137`, `_years_to_date` 침묵 clamp
- `years`를 `1/365.25`까지 상향. 만기 완료 대출(mat_years=0)이나 당일 재설정이 미래 1일로 재작성됨.

### 7. `risk_lib/alm/schedule.py:135`, 만기 초과 계약 방어적 fallback
- `payment_dates(...)` `[max(maturity, asof)]` 반환. asof에 원금 전액, 이자 0. Raise 대신 침묵.

### 8. `risk_lib/alm/behaviour_estimation.py:952~953, 1268~1270`, obs_seq=1에서 KeyError
- `d.set_index("obs_seq").loc[use["obs_seq"] - 1, "deposit_rate"]`가 obs_seq=1이 포함되면 KeyError. 합성 생성기가 policy_rate_change_bp=None(obs_seq=1)로 해 준 덕에 오늘만 안 터짐. 실제 피드가 첫 관측 rate change nonzero면 crash.

## LOW
- 전 ALM 14 파일에 em/en dash 338건 (curves.py 43, irrbb.py 41, lcr.py 35, cashflow.py 30, liquidity.py 28, behaviour.py 24, nii.py 22).
- `kr_irrbb.py:1787`, `day_count: str = "ACT/365F"` 기본값이 module의 "함수 기본값에 계수가 하나도 없는 것이 이 시그니처의 요점"과 상충. USD/EUR 계약이 침묵으로 ACT/365F 적용.
- `lcr.py:501`, `compute_lcr` wrapper가 balance-sheet 경로 전용 하드코딩. ledger-based factor가 L2B 세분화하면 KeyError.

## 클린
`daycount.py`, `__init__.py`, `params.py`(규정 데이터 충실 전사), `kr_irrbb.py` Bachelier pricing, `curves.py` scenario/shock 구축 ([별표 9-1] §12/BCBS d578 일치), `behaviour_history.py`.
