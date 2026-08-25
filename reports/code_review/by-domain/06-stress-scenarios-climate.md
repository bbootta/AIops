# 06. 스트레스·시나리오·기후 코드 리뷰

**리뷰 범위:** `risk_lib/stress/`, `risk_lib/climate.py`, `risk_lib/scenario_library.py`, `risk_lib/macro_monitor.py`, `risk_lib/market_feed.py`, `risk_lib/systemic.py`.

## HIGH

### 1. `risk_lib/stress/ccar.py:224–226` — 버퍼 기본값 불일치
- `recovery_summary`가 `req_cet1`를 하드코딩 `{"capital_conservation": 0.025, "countercyclical": 0.0, "dsib": 0.01}`로 재산출. `compute_bis_ratios`(`bis.py:31`)의 기본은 `dsib: 0.0`.
- 실패 시나리오: `run_ccar` `buffers=None`이면 `paths_df.cbr_breach`는 ~7.0% CET1 기준, `recovery_summary.recovery_quarter`는 ≥8.0% 기준. 같은 결과에서 CET1 7.5%가 "no breach"이면서 "not recovered".

### 2. `risk_lib/stress/ccar.py:163` — `cum_ecl_uplift`가 실제 누적이 아님
- `max(cum_ecl_uplift, ev["incremental_ecl"])`. 코멘트는 "누적". 
- 실패 시나리오: q4 100bn / q5 80bn / q6 60bn hump path에서 action 브랜치가 100bn에 고착(정답 240bn). 액션 브랜치와 메인 브랜치의 손실 구조가 달라짐.

### 3. `risk_lib/climate.py:109, 141` — 포트폴리오 PD·LGD 무시
- `transition_leg`가 LGD=0.45 하드코딩, `physical_leg`가 PD=0.02 하드코딩. 무담보 소매(LGD ~60%)와 담보 mortgage(LGD ~20%)가 동일 기후 uplift. `climate_capital._apply_climate_shock`(실제 포트폴리오 값 사용)와 두 개의 서로 다른 "climate ECL" 산출.

### 4. `risk_lib/scenario_library.py:33–34` — docstring vs 실제 값 단위 상충
- Docstring: `rate_10y: absolute bp change (e.g. 0.02 = +200bp)`. 실제 Volcker `rate_10y=0.400`이면 4000bp, 1997 `credit_spread_corp=0.600`이면 6000bp. 실제 400bp/600bp를 의도했다면 단위는 "decimal percentage points"이지 docstring이 잘못.

## MEDIUM

### 5. `risk_lib/stress/multi_axis.py:250–253` — P&L 부호 관례 미문서화
- `-abs(position) * shock`이라 방향/부호 무관 항상 음의 P&L. 단기 duration 은행이 rate rise에서 손실 표기.

### 6. `risk_lib/stress/reverse.py:81–84` / `multi_axis.py:434` — bisection 이미 breach 상태 방어 없음
- `solve_critical_severity`가 `already_breached` 체크 없이 bisect. base_ratio ≤ target이면 hi→0 붕괴, `s≈0`·`resilient=False` 반환.

### 7. `risk_lib/stress/multi_axis.py:154` — `_downgrade` 미매칭 등급 CCC로 처리
- `idx.get(str(r), last)`, last=CCC. "AA-", "BBB+", "D", "Baa2" 등 모든 정밀 등급이 CCC로 사전 격하.

### 8. `risk_lib/macro_monitor.py:530–535` — `alerts` z-score reference 창 확대 편향
- `v[:-1]` (전체 이력 −1). rolling window 아님. `n_periods` 증가에 따라 같은 관측이 다른 z를 냄.

### 9. `.loc[df[col].idxmin()]` empty 방어 없음
- `stress/management_action.py:168, 182`, `path.py:147`, `climate_capital.py:142`. 빈 capital_path/scenario/horizon에서 ValueError.

### 10. `risk_lib/market_feed.py:263` — staleness_days 침묵 0
- `staleness_days = None if pd.isna(f["last_sync"]) else 0.0`. `last_sync` 존재하면 실제 age와 무관하게 0.0. Docstring 경고("0으로 적으면 방금 받은 것으로 읽힌다")를 코드가 정확히 위반.

## LOW
- `risk_lib/stress/scenario.py:40` — `stress_pd`가 `np.maximum(pd_base, pd_sat)`라 우호적 GDP(gdp_shock > 0)에서도 PD 하락 못 함. 비대칭·미문서화.
- `risk_lib/systemic.py:240–247` — `contagion_tipping_point`에 미사용 `lo, hi` 선언, 40포인트 조밀 스캔.
- CLAUDE.md §5 위반 — 전 파일 대부분에 em/en dash. 저장소 광역.

## 클린
`stress/__init__.py`, `stress/axes.py`, `stress/comparison.py`, `stress/decomposition.py`, `stress/liquidity.py`, `stress/narrative.py`, `stress/recovery.py`, `stress/trace.py` (장dash 제외).
