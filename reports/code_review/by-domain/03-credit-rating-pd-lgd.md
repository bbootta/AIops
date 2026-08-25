# 03. 신용등급·PD/LGD 모형 코드 리뷰

**리뷰 범위:** `risk_lib/credit_rating/`, `risk_lib/models/` (하위 `estimation/` 포함), `risk_lib/model_inventory.py`, `risk_lib/model_risk.py`, `risk_lib/explainability.py`, `risk_lib/attribution.py`.

## BLOCKER

### 1. `risk_lib/models/rating.py:49`, `pd_to_rating` 경계 매핑 오류
- `pd_upper`가 **exclusive**임을 docstring(라인 12~13)이 명시하는데 `bisect_left`를 쓰고 있다. 정확히 경계값과 일치하는 PD가 아래 등급으로 매핑된다.
- 실패 시나리오: `pd_to_rating(0.05)` → BB+ (midpoint 0.04) 반환, 정답은 BB (midpoint 0.067). `pd_to_rating(0.0003)` → AAA 반환, 정답은 AA+.
- 영향: 16개 모든 경계(0.0003 ~ 0.55)에서 발생. 원장 midpoint 재보정과 하류 계산 전부 오염.
- 수정: `bisect_right`로 교체.

## HIGH

### 2. `risk_lib/models/pd_model.py:98~103`, `gini()` 동점 미처리
- `np.arange(1, n+1)`로 순위 부여, 동점 처리 없음. `discrimination.auc_roc()`는 평균 순위를 쓰므로 두 지표가 불일치.
- 실패 시나리오: WoE 스코어카드처럼 버킷화된 점수가 많은 경우 동점이 흔해서 `gini`와 `2*auc_roc - 1`이 벌어짐.

### 3. `risk_lib/models/pd_model.py:112~113`, `ks_statistic` 분모 클램프
- `max(y_sorted.sum(), 1)` 사용. 전 부도 또는 전 정상 세그먼트에서 조용히 0 반환.
- 실패 시나리오: all-good 서브포트폴리오 백테스트가 "KS=0, 정상"로 표기됨.

### 4. `risk_lib/models/pd_model.py:117~128`, `psi()` 중복 경계
- `np.quantile`로 경계 산출 → 0이 많은 변수(utilization, dti, categorical 유사)에서 중복 경계, 폭 0 bin이 생겨 PSI가 0에 근접.
- 실패 시나리오: 실제 드리프트가 있어도 PSI ≈ 0으로 감지 실패.

### 5. `risk_lib/models/estimation/pd_est.py:214~216, 234`, NaN 침묵 전파
- `np.nanmean` 결과가 NaN이면 `max(nan, floor)` = NaN이 되어 MoC/floor/`final_applied` 전 구간을 오염. `check_pd_floor`가 NaN을 드롭하므로 실패가 노출되지 않음.

## MEDIUM

### 6. `risk_lib/models/lgd_model.py:29~50`, `LGD_FLOORS_BY_SEGMENT` 수치 오류
- 저자 주석이 이미 FSS 2018-04-12 워크숍과 불일치를 지적. 소매 기타 30%, 소매 리볼빙 50%, 무담보 mortgage 5%가 잘못됨.
- 실패 시나리오: `retail_other`가 10%에서 클립 → LGD 최대 20 ppt 과소평가.

### 7. `risk_lib/models/lgd_model.py:60~86`, `workout_lgd(discount_rate=0.05)` 기본값 근거 부재
- 저자 주석에 근거 없음이 명시. 실제 재조달 금리가 다르면 회수 PV 왜곡 → LGD 과소평가.

### 8. `risk_lib/models/pd_model.py:41~54`, `recalibrate` 범위 포화
- 로짓 이동을 `[-10, 10]`으로 bisect. 현재 평균 0.5, 목표 5e-6 같은 큰 격차에서는 -12가 필요한데 -10에서 포화 → TTC 앵커 침묵 미달.

### 9. `risk_lib/models/lgd_ead_backtest.py:699~702`, 재할당 후 참조 위험
- `done = done[np.isfinite(diff)]`가 재할당되지만 `diff`는 필터 이전 시리즈. 인덱스가 리셋되는 리팩터가 들어오면 조용히 깨짐.

## LOW

### 10. `risk_lib/models/discrimination.py:63~65`, precision 분모 클램프 + `(0, 1)` 프리펜드
- 표준 sklearn 동작이나, 최상위 랭크가 양성이 아니면 AUPRC 과대. 감사관에게 주의.

### 11. `risk_lib/models/estimation/plgd.py:407~409`, `_monotonicity` 판정 임계 부재
- rho > 0이면 크기·유의성 무관하게 "단조증가" 라벨. `check_beel_monotonicity`가 이를 그대로 수용.

### 12. `risk_lib/model_inventory.py:44~47, 62`, `date.today()` 기본값
- `days_overdue`/`is_overdue`/`build_standard_inventory`가 실행시각 의존 → 재현성 규약 위반.

### 13. `risk_lib/model_risk.py:96~124`, 파이프라인과 디커플된 하드코딩
- 피처 리스트와 PENDING 임계(`gini<0.20`) 하드코딩. 파라미터 변경 시 버전 bump 미연동. `challenger_comparison` 판정이 Gini delta만 사용, KS·calibration 무시.

## CLAUDE.md §5 위반 (장dash 사용)
콤마·콜론·하이픈으로 교체 필요.
- `risk_lib/models/lgd_model.py`, 9건 (1, 3, 4, 7, 8, 14, 39, 124, 148~153)
- `risk_lib/models/explain.py`, 8건 (1, 10, 11, 13, 14, 15, 30, 86)
- `risk_lib/models/discrimination.py`, 1건 (9, en dash)
- `risk_lib/models/estimation/history.py`, 1건 (1)
- `risk_lib/explainability.py`, 4건 (1, 19, 301, 309)
- `risk_lib/model_inventory.py`, 7건
- `risk_lib/model_risk.py`, 4건

## 클린 판정
`credit_rating/{build,override,requirements,sample,scorecard}.py`, `models/estimation/{ccf_est,moc,common,validation,checks}.py`(LOW 제외), `attribution.py`, `explainability.py`, `rating.py`(BLOCKER 이외).
