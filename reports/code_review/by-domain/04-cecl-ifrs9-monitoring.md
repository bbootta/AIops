# 04. CECL·IFRS9·모니터링 코드 리뷰

**리뷰 범위:** `risk_lib/cecl.py`, `risk_lib/provisioning/`, `risk_lib/monitoring/`, `risk_lib/vintage.py`, `risk_lib/adjustments.py` (총 2,940 LOC).

## BLOCKER

### 1. `risk_lib/provisioning/ecl.py:155–177` — SICR 트리거 4개 무시
- `classify_stage_vector`가 `dpd>=30 | watchlist | pd_current>=k*pd_orig`만 체크. `ifrs9_deep._trigger_matrix`(88–131)가 계산·귀속하는 `forbearance`, `notch_drop`, `abs_pd`를 무시.
- 실패 시나리오: 채무재조정(forbearance) 차주가 dpd=0, pd 변화 없으면 Stage 1(12M ECL)에 머무름. IFRS9 5.5.7는 Stage 2 요구. Under-provision (lifetime − 12M ECL). SICR 분해 페이지의 forbearance 기여도가 0%로 오표기.

### 2. `risk_lib/monitoring/vintage_deep.py:117–121` — vintage_drift 신·구 역전
- `vintage.py:48` docstring은 cohort index 0 = 최신, n-1 = 최오래. `vintage_drift`는 `sort_index()` 후 `iloc[-recent_n:]`로 **가장 오래된** cohort를 "recent"로 선택.
- 실패 시나리오: 최신 3개 cohort가 진짜 악화되면 `improvement`로 보고, 반대도 마찬가지. RED/GREEN 판정이 역전.

## HIGH

### 3. `risk_lib/provisioning/ecl.py:56–62, 175–177` — Stage 3 UTP 트리거 부재
- DPD ≥ 90 승격만 있음. IFRS9 5.5.11, BCBS CRE36.68/72의 unlikely-to-pay(파산·감액·부실재조정) 없음. `deep.py:17` docstring은 "DPD ≥ 90 OR default_12m == 1 (UTP 포함)" 이라 하나 staging 코드는 `default_12m`을 안 읽음.

### 4. `risk_lib/monitoring/delinquency.py:28–32`, `deep.py:42–49` — 음수/NaN DPD 침묵 오분류
- `_bucket`에서 dpd=-1이 모든 range 통과 → `"180+"` 반환. `_bucketise`는 dpd=-1 → `"90+"`(NPL), NaN → `"Current"`.
- 실패 시나리오: 상류 `due_date − asof` 부호 뒤집힘 한 번에 전 장부가 NPL로 오분류 → `npl_ratio` 부풀림.

### 5. CLAUDE.md §5 위반 — 장dash 광범위
- `cecl.py:11, 111, 121, 125`; `vintage.py:10, 92`; `adjustments.py`(~30건); `provisioning/ecl.py:1`; `provisioning/ifrs9_deep.py:9, 57, 60, 370, 585–589, 620`; `provisioning/macro.py:1, 19, 196, 307`; `monitoring/cure.py:7, 24`; `monitoring/deep.py:7–11, 18, 209`; `monitoring/recovery_deep.py:5–8, 80, 81, 158`; `monitoring/vintage_deep.py:67, 99`; `adjustments.py:265`(en dash).

## MEDIUM

### 6. `risk_lib/provisioning/ecl.py:216, 218` / `macro.py:186–187, 203–204` — 12M·Stage3 ECL 할인 누락
- 오직 lifetime ECL만 EIR 할인. IFRS9 B5.5.44는 전 stage에서 EIR 할인 요구. 3년 워크아웃·EIR 5% Stage 3 익스포저 ECL ~14% 과대.

### 7. `risk_lib/provisioning/pma.py:133–147` — 중요성 게이트 부재
- `control_violations`가 SoD·증빙·유효기간만 체크. 세그먼트 ECL의 40% PMA 하나가 상급 승인 요건 없이 통과. `adjustments.py:101–105`의 `MATERIALITY_ABS=100억, MATERIALITY_REL=1%`와 상충. 3%×3건 분할 우회도 무방비.

### 8. `risk_lib/provisioning/macro.py:233–234` — 클립 안 된 PD 전달
- `classify_stage_vector`에 `df["pd"]`가 NaN 허용 상태로 넘어감. `pd_arr`는 지역 clip 되지만 분류기에는 미전달. NaN PD·pd_orig=0.02는 pd-doubling 트리거 못 발동.

### 9. `risk_lib/monitoring/recovery.py:44–50`, `recovery_deep.py:53–63` — 회수율 가중 오류
- 부도건별 단순 평균, 분모가 관측 시점 부도가 아닌 총 부도. $1B 5% + $1k 100% → 52.5%. `n_defaults_observed`가 검열된 부도를 오라벨.

### 10. `risk_lib/monitoring/cure.py:31–71` — Basel 관찰기간 없음
- Docstring은 CRE36.81 준수 표방. 실제로는 단발 Bernoulli. `deep.roll_rate_matrix`도 90+에서 12%/월 이탈 허용(`base["90+"]`).

### 11. Division-by-zero on empty book
- `cecl.py:82`(`w_life`), `cecl.py:115`(`ead_total`), `macro.py:265`, `macro.py:167`(`n_vec.max()`) — 빈 포트폴리오에서 raise.

## LOW
- `risk_lib/monitoring/delinquency.py:112–114` — `transition_matrix`가 inner merge로 스냅샷 사이 이탈 차주를 드롭(검열 vs 부도 편향).
- `risk_lib/adjustments.py:155–156` — `cumulative_violations`가 `items[0].base_value`를 공통 기준으로 사용. 같은 figure_id에 base가 다른 조정이 쌓이면 잘못됨.

## 클린
`risk_lib/monitoring/__init__.py`, `risk_lib/provisioning/__init__.py`, `risk_lib/vintage.py` 전이 로직(장dash 제외), `risk_lib/monitoring/recovery_deep.lgd_distribution`.
