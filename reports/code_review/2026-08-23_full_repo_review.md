# 저장소 전수 코드 리뷰 (2026-08-23, 44주차)

**대상**: `bbootta/AIops` 전 저장소, base `origin/main` = `60bda57`
**직전 리뷰**: 2026-08-14 (43주차), `reports/code_review/2026-08-14_full_repo_review.md`, 앵커 `00fb2c6`
**델타 창**: 2026-08-14 → 2026-08-23 (9일), 30 커밋, +20,686 / -129 (파일 195개 · 대다수 세일즈/법무 문서), 코드 델타는 2 커밋에 집중 (`eaf8907` 시장 포지션 원장 · `3912f66` PD 순환성 검증), 신규 `.py` 4개 1,157 LOC
**리뷰 방식**: 4개 서브에이전트 병렬. (A) 43주차 tracked BLOCKER 6건 재검증, (B) `market_portfolio` 원장 신규 심층, (C) `pd_cyclicality` 3선 도구 신규 심층, (D) 저장소 전역 정책 지표 재측정

## 0. 총평 (한 문장)

델타 9일간의 **코드 손은 두 신규 파일에 집중되어 각각의 자체 테스트는 통과**하지만 (원장 일원화 4장 · PD 순환성 6개 프로브), **43주차 BLOCKER 6건 중 5건이 그대로 살아 있고**, 두 신규 모두 각기 P1 결함을 안고 landed 되었다, 시장 원장의 "일원화 대사" 는 알고리즘 항등이라 절대 실패하지 못하고, PD 순환성 도구는 verdict 어휘가 3선 게이트 스키마에 안 맞아 어떤 결과가 나와도 게이트를 통과시킬 수 있다. em/en dash 는 43주차의 +577 회 회귀가 −558 회로 되돌아왔지만 (9,653 → 9,095) 여전히 4자릿수 위반 규모이며 사전 커밋 훅 부재는 그대로다.

| 층위 | 42주차 | 43주차 | 44주차 | 변화 |
|---|---|---|---|---|
| BLOCKER (§1) | 6건 | 5건 LIVE + 1건 PARTIAL | **5건 LIVE + 1건 PARTIAL** | **무변동** |
| 델타 신규 결함 | . | P1 ×2, P2 ×2, P3 ×2 (6건) | **P1 ×3, P2 ×5, P3 ×5 (13건)** | **+7 신규** |
| em/en dash | 9,076 회 / 617 파일 | 9,653 / 633 (**+577 / +16**) | **9,095 / 629 (−558 / −4)** | 부분 회귀 정지, 여전히 정책 위반 |
| 벽시계 파일 (risk_lib) | 20+ | 25 파일 / 32 회 | **24 파일 / 30 회** | 실질 무변동 |
| 테스트 `run_pipeline(asof=)` 미전달 | . | 4 지점 (§1-5) | **20 지점** (재측정 결과 표면 확장) | +16 노출 |

**최대 위험**: 43주차가 §1-3에서 지적한 3선 독립검증의 근본 결함 (재계산기 6/21, `Finding.__post_init__` 부재, 서명·해시 무방비)이 44주차에도 무변동이면서, 그 게이트를 통과해야 할 신규 도구 (`pd_cyclicality`)가 게이트 스키마에 안 맞는 verdict 어휘로 landed 했다. 3선을 강화하지 못한 채 3선에 넣어야 할 도구를 늘리고 있는 셈이다.

## 1. 즉시 조치 (BLOCKER · Tracked 재점검)

43주차 §1 의 6개 BLOCKER를 44주차 HEAD (`60bda57`)에서 재검증. 상세 실패 시나리오는 43주차 본문 참조.

### 1-1. 재현성 (벽시계 리크), LIVE

- `risk_lib/pipeline.py:1502` 여전히 `asof = date.today()` (원장 태그 `wall_clock` 은 :1500·:1503 그대로, 폴백 값 자체 미개선).
- 43주차 리스트업 18개 앵커 전량 LIVE (변동 없음): `notifications.py:59`, `deliverables.py:101`, `adjustments.py:308`, `stress/path.py:110`, `archive.py:129/154`, `report.py:43`, `report_chrome.py:144`, `board_pack.py:87/418`, `work_report.py:84`, `ops_pages/core_overview.py:332`, `case_studies/bank7_2026q1.py:286`, `case_studies/ib3_report.py:228/237/280`, `case_studies/ib3_2026q1.py:198`, `market_data.py:521`, `localization.py:100/152`, `model_inventory.py:45/61`, `model_risk.py:36`.
- `risk_lib/datamodel/decompose.py:191` (43주차 §2-1 P1) 여전히 `date.today().isoformat()` 폴백. `SNAP_rdm_exposure_<yyyy-mm-dd>` 스냅샷 ID 벽시계 표류 불변.
- `risk_lib/cli.py` 여전히 clean.

### 1-2. FSS cross-form 대사, LIVE (전건)

- `risk_lib/regulatory/cross_form.py:61` `("BR-31", "1110")`. BR-31 builder는 `br_camel` (`forms_ext.py:545`)이고 라인코드는 `base = 1000 + i*100` CAMEL 등급/지표값, 총자본비율과 산술적으로 같지 않음. 대사 자체가 세만틱을 위반.
- `cross_form.py:77` `("BR-31", "1510")` 동일 (LCR과 CAMEL 5번 지표값 대사).
- `cross_form.py:51` `("BR-01", "2000") ↔ ("BR-20", "5000")` tol default 1.0 KRW 유지. `forms.py:54` BR-01/2000 = `rwa["final_total"]` (전위험 총액) vs `forms_ext.py:223` BR-20/5000 = `floored_rwa` (신용 하한 후만), 항상 시장+운영+CCR RWA 만큼 차이가 나 항상 거짓 FAIL.
- 누락 등록 6건 전량 미등록: B2506/3000, B2506/2000, B2403/1010, B2431/1010, B2916/1000, B2602-2/1000.
- `risk_lib/regulatory/forms.py:380` BR-08 `tol=float(lcr.inflow_capped) + 1.0`, 순현금유출 대사가 tol 안에 인정유입 자기값을 포함해 항등적 통과.

### 1-3. 3선 독립검증, PARTIAL

- `risk_lib/validation/independent.py:662-708` `check_gate` identity binding **유지 (FIXED)**: run_id (:674-677), request_id (:678-680), `RECALC_SCOPE` 미커버 감지 (:684-690) 모두 fail-closed.
- `ValidationResponse`/`Finding` 어디에도 `signature`/`hash` 필드 **없음 LIVE**. `ValidationResponse.read`(:186-189)는 서명 검증 없이 JSON을 그대로 파싱, 응답 파일 위조 무방비.
- `validation-team-agent/tools/independent_recalc.py:140-153` `RECALCULATORS`는 여전히 **6개** (lcr, nsfr, cet1_ratio, leverage_ratio, icaap_ratio, portfolio_default_rate). `RECALC_SCOPE`는 **21개**. **15/21 = 71.4% headline이 여전히 독립 재계산기 없음 LIVE**. check_gate identity binding은 `missing` 태그로 잡지만 재계산기 자체는 미구현이므로 결재 시점에 항상 미커버 감지 → 조건부/응답대기 폴백.
- `independent.py:39` `VERDICTS`/`STATUSES` tuple은 정의되어 있으나 **`Finding.__post_init__` 부재 LIVE** (`grep __post_init__` 결과 0). `Finding(**f)` 로 severity 오타 검증 없이 삽입, 응답 JSON `"severity":"중대"` 오타가 게이트를 뒤집는다.

### 1-4. 리스크 코어 결함, LIVE (전건)

- `risk_lib/integrations.py:302-314` `send_with_isolation` 미수정. `key = idempotency_key(...)` (:303-304) 계산 후 dedup에 안 씀 (`dead_letters`에만 사용). 재시도 (:306-310) `sleep`/backoff/jitter 없이 back-to-back.
- `risk_lib/limits/limit_engine.py:41` `>= 1.20 → "CRITICAL"` vs `limits/limits_deep.py:55-62` `>= 0.90 → "CRITICAL"`, `>= 1.00 → "BREACH"`, 같은 로우가 두 엔진에서 정반대 의미로 CRITICAL.
- `risk_lib/op_loss.py:88` `float(lognet.std() or 1.0)`. `std()` = `np.float64(nan)`, `nan or 1.0` = nan (nan truthy). 관측 1건 이벤트타입에서 sigma=nan → VaR/ES 전체 오염.

### 1-5. 테스트 결함, LIVE (전건 · 표면 확장)

- `tests/test_frtb_inventory.py:183` `assert not e.is_overdue()` (`today=` 없음, `next_due="2030-01-01"`), 2030-01-01 시한폭탄.
- `test_frtb_inventory.py:72,:81` `np.random.normal(...)` 미시드 (파일 다른 곳에서 시딩되지만 이 두 콜은 시드 컨텍스트 밖).
- `run_pipeline(...)` 에 `asof=` 미전달 **20 지점 LIVE**, Agent D 재측정으로 43주차 4 지점보다 표면이 훨씬 넓음이 확인됨:
  - `tests/test_credit_models.py:141,:215`
  - `tests/test_explainability.py:131,:138,:145,:157`
  - `tests/test_extras.py:181,:191,:204`
  - `tests/test_final_validation.py:24,:225,:226`
  - `tests/test_frtb_inventory.py:192`
  - `tests/test_limits_deep.py:326`
  - `tests/test_monitoring_deep.py:262`
  - `tests/test_rapm_deep.py:241`
  - `tests/test_stress_deep.py:336,:350`
  - `tests/test_timeseries.py:23`
  - `tests/test_xva_sensitivities.py:177`

### 1-6. em/en dash 정책 위반, LIVE (부분 개선 · 여전히 4자릿수)

- 저장소 전체: **9,095회 / 629 파일** (자기 리뷰 파일·규정 원문 제외 스코프). 43주차 대비 **−558 회 / −4 파일**.
- 스코프 미제한 (`.git/` 제외만): **9,664 회 / 635 파일** (Agent D 재측정).
- `.py` 전용: **4,924 회 / 381 파일** (또는 4,930 · 381, 파일 유니온 정의에 따라 ±).
- 사전 커밋 훅 미도입 상태에서 자연 감소가 일어남, 통제가 재현적으로 걸린 건 아니고 우연한 개선. LIVE.

## 2. 델타 신규 결함 (44주차 신규)

델타 2 코드 커밋 리뷰에서 새로 발굴된 13건. 심각도 P0 없음, P1 3건이 최우선.

### 2-1. P1: 시장 포지션 원장 "일원화 대사" 가 알고리즘 항등이라 절대 실패 못함

- `risk_lib/validation/consistency.py:482-508` `_check_market_portfolio_split` 는 `market_positions` (엔진 입력)를 받아 `mp.split_positions` + `mp.capital_frame` 을 **다시 실행**해서 `market_rwa` 와 대사한다.
- `market_portfolio.py:63-79` 는 로딩 테이블 가중치가 양수·합=1.0 임을 import-time 에 강제한다. 즉 재계산 결과는 항상 원본과 일치할 수밖에 없고, 이 체크는 **알고리즘 항등** 이다.
- 대사가 실제로 봐야 하는 것은 **materialized `mkt_position` 원장** 이다. 미래에 스트레스북 오버레이 (`pipeline.py:1287`) 가 같은 원장 키를 재사용하거나 asof 표류가 생기면, 원장은 엔진과 어긋난 채 이 체크는 여전히 PASS `"{len(split)}행 분해 · 합 보존"` 을 낸다.
- 라벨은 "일원화 대사" 인데 실제는 "분해 알고리즘 자기 일치", 43주차 §1-2 FSS 대사 결함과 동형 패턴이 신규 코드에서 반복됐다.
- **수정 방향**: `base["mkt_portfolio_capital"]` (또는 `tables["mkt_portfolio_capital"]`) 을 읽어 `rwa` 합계를 대조. `market_positions` 재실행 금지.

### 2-2. P1: `capital_frame` 이 `DEFAULT_RISK_WEIGHTS` 를 하드코딩해 per-row override 를 무시

- `risk_lib/market_portfolio.py:209-227` `capital_frame` 은 `DEFAULT_RISK_WEIGHTS[cls]` 를 직접 읽는다.
- `risk_lib/capital/market_risk.py:61-65` `compute_market_risk_rwa` 는 `risk_weight` 컬럼을 지원 (`sub["risk_weight"].fillna(DEFAULT_RISK_WEIGHTS[rc])`).
- `split_positions` (`market_portfolio.py:190-206`) 는 `risk_weight` 컬럼을 아예 드롭.
- 결과: 스트레스 시나리오·IPV 오버레이·향후 어떤 caller 든 per-row `risk_weight` 를 넘기기 시작하면 `mkt_portfolio_capital` 합계가 `market_rwa` 와 벌어진다. §2-1 대사가 항등이라 이 divergence 는 잡히지 않고 `rwa_market_component` · 포트폴리오 상세 · VaR 할당 모두 틀린 숫자로 흐른다.
- 현재는 `pipeline.py:374-379` 가 `risk_weight` 를 세팅하지 않아 dormant. 모듈 docstring `market_portfolio.py:212-215` 의 "산식은 `compute_market_risk_rwa` 와 같다" 주장은 override 존재 시 거짓.
- **수정 방향**: 컬럼을 forward 하거나 존재 시 raise.

### 2-3. P1: `pd_cyclicality` verdict 어휘가 3선 게이트 스키마와 호환 안 됨

- `validation-team-agent/tools/pd_cyclicality.py:348` 은 `{"verdict": "정합" | "불일치", "findings": list[str]}` 를 리턴.
- `risk_lib/validation/independent.py:39,149` 는 `verdict ∈ {"적합","경부적합","중부적합"}` 를 요구하고 `Finding.severity` 도 같은 3값 집합.
- `independent_recalc.to_finding()` (`validation_finding.py:52`) 은 `severity="high"` 로 다른 축을 쓰는데, 두 축의 매핑 규칙이 어디에도 없다.
- 결과: 검증자가 `"불일치"` verdict 를 `ValidationResponse` 로 옮길 때 severity 배정 규칙이 없어, `"경부적합"` 을 임의로 골라 conditional 경로에 태우면 재실질적 TTC/PIT 불일치도 `check_gate` 가 `"조건부"` 로 통과시킨다.
- 매핑 assertion 하는 테스트는 없다. `test_pd_cyclicality.py` 는 도구 내부 로직만 검증.
- 43주차 §1-3 이 지적한 "Finding.__post_init__ 부재로 severity 오타가 게이트를 뒤집는다" 결함과 같은 뿌리, 그 결함이 안 고쳐진 상태에서 그 결함을 우회할 도구를 3선에 넣고 있다.
- **수정 방향**: `pd_cyclicality` 가 처음부터 `Finding` schema 로 리턴하거나, `independent_recalc.to_finding` 스타일 어댑터를 이 도구용으로 명시.

### 2-4. P2: `mix_level_decomposition` 이 첫·마지막 기간만 비교, 사이클 중간 배제

- `validation-team-agent/tools/pd_cyclicality.py:140-149` 은 `periods[keys[0]]` 와 `periods[keys[-1]]` 만 읽는다.
- 6년 패널의 매크로 경로가 시작과 끝이 근접하면 (예: 데모 시나리오 `[1.8, 2.4, -1.2, -2.6, 0.9, 2.1]`, z₀=1.8, z₅=2.1) endpoint 비교는 다운턴 전체를 감춘다.
- 재현: PIT PD 가 2022~2023 급변했다가 2025 에 2020 수준으로 복귀 → `total_delta ≈ 0`, `mix_effect_share` 수치 불안정 or NaN 스킵 → TTC verdict `"정합"`.
- **수정 방향**: 연속 기간 pair 전체 iteration 또는 사이클 극단 두 해 비교.

### 2-5. P2: `pd_cyclicality` 매크로 상관 유의성 컷 (`abs(r)>0.5` AND `p<0.05`)이 n=5 에서 도달 불가

- `pd_cyclicality.py:308-312`. n=5 (허용 최소 관측)에서 p<0.05 는 |r|>0.878 요구, n=3 에서는 |r|>0.997.
- 결과: 중간 강도 (r=0.7, n=5, p≈0.19) PIT 이 TTC 라벨링을 통과. CV 컷 (`0.02` iid vs `exp(-0.35z)`) 이 데모 강신호는 잡지만, CV≤0.25 의 완만한 PIT 은 두 필터 모두 통과한다.
- **수정 방향**: 관측 수 하한을 유의성 최소 요구 수준으로 올리거나 (예: n≥8), Bayes factor 또는 부트스트랩 CI 로 판정.

### 2-6. P2: `grade_pd_stability` 가 매크로를 참조하지 않아 "불안정" 과 "순환적" 을 혼동

- `pd_cyclicality.py:107-119` 는 `std/mean` 만 계산. TTC 인데 등급 표본이 얇아 sampling variance 로 CV≥0.30 이 되면 "TTC 아님" 으로 잡힌다, Type-I 오류.
- **수정 방향**: 매크로 부분상관 (partial-correlation-against-macro) 프로브. finding 문구도 "unstable" 과 "cyclical" 을 분리.

### 2-7. P2: `POSITION` PK 강제 안 되고 duplicate 위험

- `risk_lib/market_portfolio.py:190-206`, `:209-227`. `POSITION.primary_key = ("asof","portfolio_id","risk_class")`.
- `split_positions` 는 pre-aggregate 없이 rows iterate → `class_positions` 가 같은 risk_class 로 여러 row 를 가지면 (`compute_market_risk_rwa` 는 이를 허용) `mkt_position`, `mkt_portfolio_capital` PK 중복.
- `spec.validate` 의 `pk_unique` 가 잡을 순 있으나 downstream `build_component_tables:271` 가 다시 groupby+sum 하므로 `rwa_market_component` 는 정상, 원장만 중복 → 상세 화면·감사 리포트 왜곡.
- **수정 방향**: `class_positions.groupby("risk_class", as_index=False)["net_position"].sum()` 선행 or 진입 시 1-row-per-class assert.

### 2-8. P2: `_check_loading_table` 이 `SSA_SCALING` 전 클래스 커버를 검증 안 함

- `market_portfolio.py:69-79` 는 `classes = {c for *_,w,_l in _PORTFOLIOS for c in w}` 로만 iterate, `SSA_SCALING` 이 정의하는 `commodity`, `credit_spread` 등의 커버리지는 확인하지 않는다.
- 결과: 이들 클래스 포지션 row 가 `mkt_position` / `mkt_portfolio_capital` 에서 조용히 사라진다.
- **수정 방향**: `set(SSA_SCALING) == classes` assert 또는 예상 클래스 subset 을 명시적으로 문서화하고 벗어난 클래스는 raise.

### 2-9. P2: `mkt_trade.portfolio_id` 매핑 exhaustive 검증 안 됨

- `catalog.py:+540-+543` + `materialize.py:+405-+412` + `market_portfolio.py:59-60`. `KIND_TO_PORTFOLIO = {"swap":..., "option":..., "cds":...}`, 현재 `synthesise_trading_book`(`sensitivities.py:132`) 이 만드는 3종만 커버.
- `test_every_trade_kind_is_assigned_a_portfolio` (테스트 파일 :59-68) 은 `inspect.getsource` 로 `"option" in src and "swap" in src and "cds" in src` substring 매치, 네 번째 kind (`"future"`) 추가되어도 기존 세 substring 은 그대로라 이 테스트는 통과 (blind spot).
- **수정 방향**: 공유 상수 (kind universe) 를 만들고 generator + 매핑 + 테스트가 모두 이를 import; set-equality 검증.

### 2-10. P3: `_check_market_portfolio_split` 이 `asof="0000-00-00"` fabricate

- `consistency.py:496`. 현재는 persist 안 되지만 이 프레임이 언젠가 downstream 에 흘러가면 오염.

### 2-11. P3: `mix_effect_share` 오프셋 효과를 가산으로 취급

- `pd_cyclicality.py:152-153`. `abs(mix)/(abs(mix)+abs(level))`, mix=+0.001, level=-0.0005 면 share=0.667 로 TTC 통과지만 `total_delta` 자체가 미미해 해석이 취약.

### 2-12. P3: `gen_regulatory_criteria.py:377-381` 규정 앵커 mismatch

- 새 PIT criterion 이 감독규정 제29조를 인용하지만 제29조는 대손충당금 소요액 규정, PIT 성 판정의 규제 앵커가 아님. 정본 앵커는 IFRS 9 5.5.17.
- 도구 자체 문서 (`pd_design_thresholds.json:3`) 는 "IFRS 9, 기준 스택 밖" 을 caveat 로 남겼지만 상위 criterion 에서 잘못된 조문을 인용.

### 2-13. P3: PD 순환성 임계값 boundary 재현성 테스트 부재

- cv=0.25, r=0.5, mix_share=0.6, tracking_corr=0.5 정확한 boundary 에서 부동소수점 표류로 verdict 반전 가능. 픽스처 추가로 저비용 방지 가능.

### 2-14. P3: `test_a_broken_loading_table_dies_at_import` 이름이 실제 검증과 어긋남

- `tests/test_market_portfolio.py:44-56`. 이름은 "dies at import" 인데 body 는 import 후 `_PORTFOLIOS` 를 swap 하고 `_check_loading_table()` 을 직접 호출. 향후 guard 가 module scope 에서 빠지면 테스트는 통과하되 invariant 는 사라진다.

### 2-15. P3: `WARN` 이 fail-open 이라는 자기 부인

- `consistency.py:490-493` 는 `market_positions is None or market_rwa is None: WARN` 이지만 docstring 은 "fail-open 금지" 를 주장. WARN 은 3선 게이트를 막지 않으므로 문서와 행동이 어긋남.

## 3. 정책 지표 (Agent D 재측정)

| 지표 | 현재 (2026-08-23) | Baseline 2026-08-14 | Δ |
|---|---:|---:|---:|
| em (U+2014) 회수 | 9,154 | . | . |
| en (U+2013) 회수 | 510 | . | . |
| em+en 합계 (scope: `.git/` 제외만) | 9,664 | 9,653 | +11 |
| em+en 합계 (self-ref 제외) | **9,095** | 9,653 | **-558** |
| em+en 파일 유니온 | 635 | 633 | +2 |
| `.py` em+en 회수 | 4,930 | . | . |
| `.py` 파일 (em or en) | 381 | . | . |
| 벽시계 리크 파일 (risk_lib) | 24 | 25 | -1 |
| 벽시계 리크 콜사이트 (risk_lib) | 30 | 32 | -2 |
| 벽시계 리크 파일 (전체 union) | **39** | . | (신규 측정) |
| 벽시계 리크 콜사이트 (전체 union) | **50** | . | (신규 측정) |
| `run_pipeline(..)` asof 미전달 (tests) | **20 지점** | 4 지점 (§1-5 커버분) | +16 노출 |
| `np.random` 미시드 파일 (tests) | 0 | . | 파일 스코프 판정으로는 clean |
| 신규 `.py` 파일 (`00fb2c6..60bda57`) | 4 (1,157 LOC) | . | . |
| HEAD 정합 | `HEAD == origin/main == 60bda57` | . | . |

**요약**: em/en dash 회귀는 정지, 벽시계 리크는 실질 무변동, `run_pipeline` 미전달 노출 표면은 예상보다 훨씬 넓다 (4 → 20). 신규 코드는 2 커밋에 집중.

## 4. 델타 라운드 긍정 (기록)

- **`market_portfolio.py`**: import-time weight guard (`:63-82`) 가 `1e-9` 로 fail-closed, 음수 weight 브랜치 명시 테스트, `test_component_position_comes_from_the_ledger_not_a_back_solve` (테스트 :154-165) 가 신규 position 이 이전 `capital/0.08` 값과 >1% 벌어짐을 명시 assert, 43주차 §5 "회귀 통제" 원칙과 정합. lineage 시나리오 (`test_unification_is_visible_in_lineage`, 테스트 :184-193) 로 원장이 실제 lineage 그래프에 등장함을 직접 검증. `materialize_detail.py:783-789` 의 `{**base, **out}` 정합은 최소 변경으로 필요 원장 순서를 통과시키는 좋은 손.
- **`pd_cyclicality.py`**: `pit_tracking` docstring (`:186-193`) 이 이전 판이 portfolio-average 만 봐 mislabeled PIT 을 못 잡았던 실패를 기록하고 재설계 사유를 문서화, CLAUDE.md §2 "통제 실패 가능성 검증" 원칙 정합. mirror 부정 통제 (`test_pit_data_claimed_as_ttc_is_detected`, `test_flat_prediction_claimed_as_pit_is_detected`) 존재 및 fixed seed 사용. `test_thresholds_are_declared_not_hardcoded` 가 SSoT 계약을 잠금. `pd_design_thresholds.json` 이 규제 앵커 값 (5년 관측, 세칙 별표 3) 과 내부 판단 임계값을 분리 표기.

## 5. 권고 (다음 주 최우선 5)

우선순위는 (블로킹 재발위험 × 수정 비용) 기준. 43주차 §6 권고 5건 중 이행분이 없어 그대로 재상신하며 신규 2건을 앞에 붙인다.

1. **[NEW · P1] `_check_market_portfolio_split` 을 materialized 원장 대사로 재구현.** `consistency.py:482-508` 을 `base["mkt_portfolio_capital"]` 합계 대비로 바꾸고 재실행 로직 삭제. 2 시간 이내.
2. **[NEW · P1] `pd_cyclicality` verdict → `Finding` 스키마 어댑터.** 3선 게이트에 들어가려면 `verdict ∈ {"적합","경부적합","중부적합"}`, severity 어휘 통합. 매핑 규칙을 코드로 강제하고 assertion 테스트 추가. 3 시간 이내.
3. **[43주차 §1-6 재상신] em/en dash 사전 커밋 훅 도입.** 9,000+ 위반이 정책 vs 관행 사이 격차의 크기를 정의한다. `.git/hooks/pre-commit` 또는 `.pre-commit-config.yaml` 에 U+2013/U+2014 grep → non-zero exit. 30 분.
4. **[43주차 §1-3 재상신] 3선 재계산기 확장 (6 → 최소 10).** 현재 `passes`/`conditional` 판정이 사실상 15 개 headline 에 대해 미커버 감지로 전락. `RECALC_SCOPE` 21 개 중 최소 신용/시장/운영 RWA 재계산기 우선. 1 주 스프린트.
5. **[43주차 §1-1 재상신] `pipeline.py:1502` 벽시계 폴백 제거.** `asof` 를 필수 인자로 승격하고 caller 를 전수 갱신. 재현성의 뿌리 결함이므로 다른 어떤 리팩토링보다 선행. 반나절.

---

## 부록 A. 리뷰 방식·재현

- HEAD 기준: `git rev-parse HEAD` = `60bda5701267ae2457fb95b317790311372c6bd4`, `origin/main` 과 동일 (Agent D §F).
- 델타 창: `git log --oneline 00fb2c6..60bda57` (30 커밋), `git diff --stat 00fb2c6..60bda57 -- '*.py'` (17 파일, +1,348/-23).
- 코드 스코프 델타 커밋: `eaf8907` (10 파일, +644/-20), `3912f66` (5 파일, +698/-2), `60bda57` (2 파일, +6/-1), merge 3개.
- 서브에이전트 4 개 병렬:
  - Agent A: 43주차 §1 6개 BLOCKER 재검증 (36 tool calls, 250 s)
  - Agent B: `market_portfolio` 델타 심층 (19 tool calls, 210 s)
  - Agent C: `pd_cyclicality` 델타 심층 (16 tool calls, 179 s)
  - Agent D: 저장소 전역 정책 지표 재측정 (18 tool calls, 128 s)

## 부록 B. 3선 게이트 상태 (44주차 자기 확인)

이 리뷰 자체는 자체 리스크 산출물이 아니므로 3선 독립검증 요청 대상이 아니지만, CLAUDE.md §6 형식을 따라 기록:

```
자체검증 (2선)      해당없음 (리뷰 산출물, 리스크 수치 미생성)
상시 독립검증 (3선)  해당없음 (동)
```

리뷰가 지적한 §2-3 (PD 순환성 verdict 스키마) 는 3선 게이트 자체의 접근 통제 결함이므로, 이 결함이 landed 한 상태에서 향후 어떤 리스크 산출물이든 `check_gate(..).require()` 결과가 형식적으로 pass 하더라도 실질 게이트 통과 여부는 재의심 대상이다.
