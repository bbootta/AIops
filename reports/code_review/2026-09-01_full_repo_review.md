# 저장소 전수 코드 리뷰 (2026-09-01, 44주차)

**대상**: `bbootta/AIops` 전 저장소, base `origin/main` = `60bda57`, 리뷰 브랜치 `claude/stoic-ride-u3mmwj` HEAD = `454a95e`
**직전 리뷰**: 2026-08-14 (43주차), `reports/code_review/2026-08-14_full_repo_review.md`
**델타 창**: 2026-08-14 (`00fb2c6`) → 2026-09-01 (`454a95e`), 43 커밋, +51,528 / -129, 200 파일
**리뷰 방식**: 3 개 서브에이전트 병렬. (A) 43주차 tracked BLOCKER 59 건 재점검, (B) 델타 신규 Python 코드 리뷰, (C) 저장소 전수 정책 감사 (em/en dash, 벽시계, 미시드 RNG, 훅 배치)

## 0. 총평 (한 문장)

델타 43 커밋 중 실질 Python 코드는 두 신규 파일 (`market_portfolio.py` 296 줄, `pd_cyclicality.py` 492 줄) 과 몇 개 datamodel/validation 파일 소폭 편집에 집중되었으며 신설 모듈의 수치·집합 계약은 대체로 옳게 작성되어 신규 BLOCKER 는 발생하지 않았으나, **43주차 tracked 항목 59 건 중 57 건 (96.6 %) 이 그대로 LIVE** 이고 em/en dash 는 다시 **+134 회 증가 (9,653 → 9,787)** 하여 리뷰 자체가 통제 기능을 하지 못하고 있다.

| 층위 | 43주차 | 44주차 | 변화 |
|---|---|---|---|
| Tracked BLOCKER (§1) | 6 건 + §A 서브시스템 12+ 건 | 57 LIVE / 1 PARTIAL / 1 FIXED | 실질 무변동 |
| 벽시계 리크 파일·회수 | 25 파일 / 32 회 | 37 파일 / 50 회 | **+12 파일 / +18 회 (회귀)** |
| em/en dash 총합 | 9,653 회 / 633 파일 | 9,787 회 / 639 파일 | **+134 회 / +6 파일 (회귀)** |
| 델타 신규 결함 | P1 ×2, P2 ×2, P3 ×2 | MAJOR ×10, MINOR ×10 | 신규 20 |
| 미테스트 프로덕션 모듈 | 10+ | (변동 미검증) | ~10 지속 |
| 사전 커밋 훅 | 미배치 | 미배치 | 무변동 |
| 3선 RECALCULATORS 커버리지 | 6/21 (29 %) | 6/21 (29 %) | 무변동 |
| `check_gate` identity binding | FIXED | FIXED (유지) | , |

**최대 위험 두 개**:

1. 사전 커밋 훅이 42주차·43주차 두 차례 권고에도 여전히 미배치라 em/en dash 는 43 시간에 +577 (43주차) 이었고 이번 18 일에 +134 로 (일당 ~7 회로) 완만해졌으나 **여전히 증가**. 리뷰가 매번 지적하는 항목이 매번 늘어난다면 리뷰가 통제가 아니라 회계다.
2. `datamodel/decompose.py:191` 벽시계 폴백은 43주차에 명시 지적되었고 43주차 권고 §6-2 가 "즉시 raise" 를 요구했으나 이번 델타에서 `datamodel/*` 를 광범위하게 만졌으면서도 이 한 줄은 그대로. **의도적 부작위**로 해석.

## 1. 즉시 조치 (BLOCKER · Tracked 재점검)

43주차 §1 의 6 대 BLOCKER 카테고리를 델타 이후로 다시 검증한 결과. 59 건 중 57 건 LIVE.

### 1-1. 재현성 (벽시계 리크), **LIVE (24 지점 LIVE / 25 지점)**

- `risk_lib/pipeline.py:1502` 여전히 `asof = date.today()`. `asof_source="wall_clock"` 태그는 :1500 에 있으나 폴백 값은 그대로. 하류 매니페스트·zip sha256 재현성 미회복.
- `risk_lib/datamodel/decompose.py:191` 여전히 `date.today().isoformat()` 폴백 (43주차 §2-1 P1, 44주차 델타로도 이 파일을 재편집했음에도 살아남음). 앵커 :164 → :191 로 드리프트.
- LIVE 24 지점 전량: `notifications.py:59`, `deliverables.py:101`, `adjustments.py:308`, `stress/path.py:110`, `archive.py:129 / :154`, `report.py:43`, `report_chrome.py:144`, `board_pack.py:87 / :418`, `work_report.py:84`, `ops_pages/core_overview.py:332`, `case_studies/bank7_2026q1.py:286`, `case_studies/ib3_report.py:228 / :237 / :280`, `case_studies/ib3_2026q1.py:198`, `market_data.py:521`, `localization.py:100 / :152`, `model_inventory.py:45 / :61`, `model_risk.py:36`.
- **신규 표출 12 파일** (43주차 이후 새로 진입): `risk_lib/validation/independent.py:655` (`datetime.now`), `risk_lib/repro.py:238` (`datetime.now`), 그리고 `validation-team-agent/tools/*` 10 개 파일 (`audit_retention.py:53`, `conditional_approval.py:173 / :274`, `cro_digest.py:261`, `escalation_report.py:27`, `feedback_retention.py:67`, `manifest.py:94 / :147`, `pack_archive.py:28 / :33`, `provenance.py:199`, `report_export.py:196`, `validation_finding.py:297 / :358`, `validation_scope.py:122`, `validation_trigger.py:188 / :278`) 및 `middleware/run_logger.py:30`. 3선 코드 표면 전반이 as_of override 를 받도록 시그너처만 정비하고 default 는 여전히 `date.today()`/`datetime.now()` 로 폴백.

### 1-2. FSS cross-form 대사 (거짓 통과·거짓 실패), **LIVE (전건)**

- `risk_lib/regulatory/cross_form.py:38-49` 누락 등록 (B2506/3000, B2403/1010, B2431/1010, B2506/2000, B2916/1000, B2602-2/1000) 전량 미등록.
- `cross_form.py:51` 위험가중자산 합계 대사 `tolerance` default 1.0 KRW (`Invariant` dataclass field :32). BR-01/2000 (`final_total`) 과 BR-20/5000 (`floored_rwa`, credit-only) 미스매치 불변.
- `cross_form.py:61` 여전히 `("BR-31", "1110")` 포지셔널. :77 여전히 `("BR-31", "1510")`. 두 라인코드 모두 `forms_ext.py:545 br_camel` 이 만들지 않음.
- `cross_form.py:70` 기대신용손실 합계 여전히 `B2403/1020`·`B2431/1020` 참조 (요구는 `1010`).
- `risk_lib/regulatory/forms.py:380` BR-08 여전히 `tol=float(lcr.inflow_capped) + 1.0`. 항등 통과 불변.

### 1-3. 3선 독립검증, **PARTIAL (43주차 대비 무진전)**

- **FIXED (유지)**: `risk_lib/validation/independent.py:662-708` `check_gate` identity binding (:674 run_id, :678 request_id, :684-690 미커버 recalc-key 감지) 유지.
- **LIVE**: 서명·해시 없음. 응답 파일 위조에 여전히 무방비.
- **LIVE**: `validation-team-agent/tools/independent_recalc.py:140-153` `RECALCULATORS` 여전히 6 개 (lcr, nsfr, cet1_ratio, leverage_ratio, icaap_ratio, portfolio_default_rate). `RECALC_SCOPE` 21 개 대비 15 개 headline (71 %) 이 여전히 독립 재계산 없음. **3 주 연속 무진전**. Pw9F5 브랜치 dormancy (14 일+) 심화.
- **LIVE**: `risk_lib/validation/independent.py:39` `VERDICTS` / `STATUSES` 튜플만 있고 `Finding` dataclass (:147) `__post_init__` 없음. :186 `ValidationResponse.read` `Finding(**f)` 여전히 검증 없이 삽입. severity 오타 (예: "중대") 는 여전히 게이트를 뒤집는다.

### 1-4. 리스크 코어 결함, **LIVE (전건)**

- `risk_lib/integrations.py:302-314` `IsolatingDispatcher.send_with_isolation` 미수정. :303-304 `key` 계산 후 dedup 에 안 씀. :306-310 재시도가 sleep/backoff/jitter 없이 back-to-back.
- `risk_lib/limits/limit_engine.py:41-47` (CRITICAL ≥ 1.20, WARN ≥ 0.90) vs `limits_deep.py:55-62` (CRITICAL ≥ 0.90, WARN ≥ 0.75) 반전 그대로. 같은 로우가 CRO 대시보드에 정반대 의미로 CRITICAL.
- `risk_lib/op_loss.py:88` `float(lognet.std() or 1.0)` 여전. `std()==nan` 이면 `nan or 1.0 == nan` (nan truthy). VaR/ES NaN 오염 불변.

### 1-5. 테스트 결함 (회귀 통제 부재), **LIVE (전건)**

- `tests/test_frtb_inventory.py:183` 여전히 `assert not e.is_overdue()` (`next_due="2030-01-01"`, today= 없음). 2030-01-01 시한폭탄.
- `test_frtb_inventory.py:72, :81` `np.random.normal(...)` 여전히 미시드.
- `test_frtb_inventory.py:192`, `test_monitoring_deep.py:262`, `test_stress_deep.py:336 / :350` 모두 `run_pipeline(...)` 에 asof 미전달.

### 1-6. 정책 위반 (em/en dash), **REGRESSED (또)**

- U+2014 (em) + U+2013 (en) 회 수: **9,653 → 9,787 (+134)**. 파일 수: **633 → 639 (+6)**.
- 18 일간 +134 회, **일당 약 7.4 회 증가**. 43주차 (일당 190) 대비 속도는 느려졌으나 여전히 단조 증가.
- 신규 델타 파일에서도 em dash 8 지점 추가 (§2-2 참조).
- 사전 커밋 훅 (43주차 §6-1 재요구) 여전히 미배치. `.git/hooks/pre-commit` 파일 부재 (`.sample` 만 존재), `.pre-commit-config.yaml` 부재, `.claude/settings.json` 에 `hooks` 키 부재.
- Top 오염원 (파일당 em dash) 는 43주차 대비 순위 무변동: `tests/form_structure_baseline.json` (503), `validation-team-agent/harness/reference/basel_framework_sourcebook_20260809.md` (446), `validation-team-agent/tools/report_pack.py` (270), `docs/independent_validation/RUN-20260630-42.remediation.md` (249).

### 1-7. 43주차 §A 서브시스템 BLOCKER (샘플 재점검), **LIVE (전건)**

12 개 샘플 전량 그대로.

- `risk_lib/capital/rwa_sa.py:22-46`: `_RW_SOVEREIGN["B"]=1.00`, `_RW_BANK_ECRA["B"]=1.00`, `_RW_CORPORATE["B"]=1.00` 그대로. B 등급 익스포저 150 % 미적용.
- `risk_lib/capital/rwa_irb.py:40-45`: 코멘트가 "the harness does not auto-floor LGD" 를 명시. 하한 미적용 불변.
- `risk_lib/capital/rwa_deep.py:262-289`: `FIRB_LGD` dict 및 :287 `np.where(...)` 하드코딩 45 % 그대로. Basel III 확정 40 % 미반영.
- `risk_lib/capital/op_risk.py:22, :55-67`: `use_ilm: bool = True` 디폴트, `_BI_BUCKETS` EUR (1bn / 30bn) 그대로.
- `risk_lib/models/rating.py:12-52`: :49 `bisect.bisect_left(uppers, pd_value)` 그대로. 경계 PD off-by-one.
- `risk_lib/governance/audit_chain.py:190-207`: :198 `actor = str(r[use_actor]) if use_actor else actor_default` 로 컬럼명만 확인, 행값 NaN 은 `str(NaN)=="nan"` (truthy) 로 chain 사인.
- `risk_lib/governance/audit_chain.py:62-66`: `json.dumps(..., default=str)` `allow_nan` 미지정. NaN/Inf 가 bare `NaN`/`Infinity` (RFC 8259 위반).
- `risk_lib/monitoring/delinquency.py:98-124`: :120 컬럼만 reindex, :122 행은 관측된 t0 등급만 유지. 결과 프레임 shape 이 (len(grades) × len(grades)) 아님.
- `validation-team-agent/tools/validation_finding.py:55-60, :215-223`: `_TRANSITIONS` 그대로 (open→remediating→reverifying→{closed, remediating}). `remediating→remediating` 미포함. VAL-013/014 재수정 loop 미표현.
- `validation-team-agent/tools/conditional_approval.py:215`: `if usage.strip() in scope:` 서브스트링 매치. `usage="리"`, `scope="리테일 포트폴리오 한정"` 이면 `allowed=True`.
- `validation-team-agent/tools/pack_diff.py:23-52`: `_STATUS_ORDER` 에 `skipped=3 > fail=2`. `_status_transition_severity("fail", "skipped")` 가 "degraded" (방향은 맞음). 그러나 `ok→skipped` 는 skipped 를 fail 보다 나쁘게 랭킹.

**총 재점검**: 59 건 중 **57 LIVE / 1 PARTIAL / 1 FIXED**. 43주차 대비 실질 개선 0.

## 2. 델타 신규 결함 (44주차 신규)

델타에서 새로 발굴한 20 건. MAJOR 10 · MINOR 10. BLOCKER 는 신규 없음 (구조적 계약이 대체로 옳게 작성됨).

### 2-1. MAJOR (10 건)

| # | 파일:줄 | 요약 | 재현 시나리오 |
|---|---|---|---|
| M1 | `risk_lib/market_portfolio.py:242` | `allocate_var_es` 가 `total <= 0` 이면 모든 포트폴리오 share 0 으로 조용히 zeroing. 모듈 docstring (:25-27) "측정치별 합 = 전사 값" 계약 위반. | 트레이딩북 무포지션 (mkt_position 전량 0) + `mkt_var_es` 에 nonzero 전사값 존재 → 배분 테이블 전량 0 · alloc_share=0, 헤드라인 VaR 조용히 소실. |
| M2 | `risk_lib/datamodel/materialize.py:409-411` | `nullable=False` 컬럼을 `assert trade["portfolio_id"].notna().all()` 로만 방어. `python -O` 에서 assert 제거되어 NaN portfolio_id 유입 가능. | `synthesise_trading_book` 이 향후 `kind` 를 `{swap, option, cds}` 밖 값으로 emit 시 assert 무력화, `mkt_trade` FK 위반이 NaN 형태로 통과. |
| M3 | `risk_lib/validation/consistency.py:493-496` | Docstring "fail-open 금지" (:490) vs 실제 **WARN** 리턴. `ValidationReport.passes()` (:42) 는 WARN 을 non-blocking 취급. 게이트가 kwarg 하나 안 넘겨서 조용히 우회됨. | `run_consistency_checks(..., market_positions=<omit>)` 호출 시 게이트 WARN → PASS. 계약이 코드로 강제 안 됨. |
| M4 | `risk_lib/market_portfolio.py:70-77` | `_check_loading_table` 이 `_PORTFOLIOS` 에 있는 class 만 검증. `SSA_SCALING` 에 있는 `commodity`, `credit_spread` 는 커버 안 됨. `split_positions` 가 이 class 로우를 조용히 드롭. | `mkt_positions` 에 `commodity` 로우 유입 → `mkt_position` 원장 소실, `rwa_market_component.position` = NaN, 리포트에서 "미측정" 로 표시되나 원인 불명. |
| M5 | `risk_lib/market_portfolio.py:219-220` + `risk_lib/validation/consistency.py:500` | `capital_frame` (그리고 `_check_market_portfolio_split`) 이 `DEFAULT_RISK_WEIGHTS[cls]` 만 사용. `capital/market_risk.py:61-64` `compute_market_risk_rwa` 가 지원하는 per-position `risk_weight` override 무시. | `mkt_positions.risk_weight` 컬럼 사용 시 대사 FAIL 스퓨리어스 발생, FAIL 메시지가 원인을 "portfolio split defect" 로 오귀속. |
| M6 | `validation-team-agent/tools/pd_cyclicality.py:362` | `synthetic_panel` 이 `cycle = np.array([...])[:years]` 로 8 원소 리터럴 슬라이스. `years > 8` 이면 `float(cycle[i])` `IndexError`. | `python -m tools.pd_cyclicality demo --years 10` → `IndexError: index 8 is out of bounds`. CLI 인자 가드 부재. |
| M7 | `validation-team-agent/tools/gen_regulatory_criteria.py:546` | 신규 `CRITERIA_PD` (6 로우) 를 중간 삽입해 이후 모든 `BIS-NNN` id 가 조용히 재넘버링. | 이전 regenerate 산출물의 `BIS-047` 참조가 다른 criterion 을 가리키게 됨. id-stability 테스트 부재. |
| M8 | `risk_lib/datamodel/materialize_detail.py:786-790` | 순서 의존 실행: `mkt_var_alloc` 이 `mkt_portfolio_capital` (from `mkt_portfolio_detail`) 을 읽지만 `DETAIL_MATERIALIZERS` dict.values() 순서에만 의존. 인라인 코멘트 (:771) 만 경고. | `DETAIL_MATERIALIZERS` 를 알파벳순 정렬 시 `mkt_var_alloc` 이 `mkt_portfolio_detail` 보다 먼저 실행, empty capital 로 배분 결과 empty, `_check_market_portfolio_split` 는 여전히 PASS. |
| M9 | `risk_lib/validation/consistency.py:498` | 대사에서 `asof = "0000-00-00"` 하드코딩 placeholder. 향후 이 함수에 `validate(...)` 를 추가하면 파싱 실패. | 편집자가 `validate(split, mp.POSITION)` 를 넣으면 매 실행 raise. 지뢰 코드. |
| M10 | `risk_lib/market_portfolio.py:270-271` + `tests/test_market_portfolio.py:172-174` | `build_component_tables` 가 원장 부재 시에도 engine capital 을 그대로 기록, `position=NaN, capital=X, rwa=X*12.5` 로우 생성. Docstring "지어내지 않고 NaN 을 남긴다" 위반. | Legacy `result` (`market_positions` 없음) 실행 → `rwa_market_component` 에 phantom capital 로우, downstream 합산이 조용히 정상값처럼 통과. `test_component_position_comes_from_the_ledger_not_a_back_solve` 는 legacy path 미커버. |

### 2-2. MINOR (10 건)

| # | 파일:줄 | 요약 |
|---|---|---|
| m1 | `risk_lib/market_portfolio.py:1, :38`, `tests/test_market_portfolio.py:140`, `risk_lib/validation/consistency.py:488`, `risk_lib/datamodel/materialize.py:384, :410`, `risk_lib/datamodel/materialize_detail.py:771, :787`, `validation-team-agent/harness/policies/pd_lgd_ead.md:1` | 신규/변경 라인에 em dash 8 지점 신규 추가. CLAUDE.md §5 위반. |
| m2 | `risk_lib/market_portfolio.py:69-70` | `_check_loading_table` 이 set-comprehension iteration. 동시 다중 결함 시 `ValueError` 메시지에 나오는 class 명 순서가 프로세스 간 nondeterministic. |
| m3 | `risk_lib/validation/consistency.py:507, :509` | `metric` 필드 의미가 두 브랜치에서 다름 (FAIL 은 diff `got-want`, PASS 는 level `got`). 시계열 대시보드에서 스케일 뒤섞임. |
| m4 | `risk_lib/market_portfolio.py:216-227` | `capital_frame` 이 `iterrows()` + per-row dict 조회 (O(N) Python 루프). 미지 `risk_class` 시 bare `KeyError` 로 컨텍스트 없이 raise. |
| m5 | `tests/test_market_portfolio.py:44-56` | `test_a_broken_loading_table_dies_at_import` 가 모듈 레벨 `mp._PORTFOLIOS` mutate. try/finally 로 복원하나 `KeyboardInterrupt` 개입 시 후속 테스트가 파손된 상태를 봄. |
| m6 | `validation-team-agent/tools/pd_cyclicality.py:246-257` | `wmean` 이 분자에서 NaN 을 dropna 하나 분모 `tw` 는 total. 편향된 가중평균 (현재 dead-path, 향후 편집자 트랩). |
| m7 | `validation-team-agent/tools/pd_cyclicality.py:107-119` | `grade_pd_stability` CV = `std / mean`. mean 이 tiny (near-zero PD) 이면 CV 폭증, TTC 트리거 spuriously. Absolute-threshold 필요. |
| m8 | `validation-team-agent/tools/pd_cyclicality.py:152-153` | `mix_effect_share = abs(mix) / (abs(mix) + abs(level))` interaction 항 제외. sum ≠ 1. 임계값 판정 오도. |
| m9 | `validation-team-agent/tools/gen_regulatory_criteria.py:552-555` | `BASEL_MAP_BY_CRITERION` 이 exact criterion string 을 key. 오타 수정 시 mapping 조용히 소실 후 `BASEL_MAP` (src, cite) 폴백. |
| m10 | `risk_lib/validation/consistency.py:509-510` | PASS 메시지 `"{len(split)}행 분해 · 합 보존"` 이 0 행에서 `"0행 분해 · 합 보존"` (0=0 trivially true). "not-checked" 케이스와 구별 불가. |

## 3. 델타 라운드 긍정 (기록)

부정만 나열하면 델타의 실체가 왜곡된다. 44주차에 실제로 landed 한 것.

- **`risk_lib/market_portfolio.py`**: 시장 포지션 원장 단일화. 신설 296 줄. weight 합 = 1.0 · 전부 양수 강제 (`_check_loading_table`), split 이 클래스별 sum-preserving, `mkt_position → rwa_market_component` 라인애지 traceable. 구조적 계약 잘 설계됨 (앞서 M1·M3·M4·M5·M10 은 계약 표면의 fail-open / silent-drop 경계 이슈이며 계산 자체는 대체로 옳음).
- **`tests/test_market_portfolio.py`**: 신설 212 줄. 헤드라인 보존, 음수 부호 처리, 부재 vs 지어냄 구별, 라인애지 가시성까지 커버. 42주차·43주차 지적한 "existence-only assert" 회피, 실질 불변식 검증.
- **`validation-team-agent/tools/pd_cyclicality.py`**: 신설 492 줄. TTC/PIT 분리 통계 검증, negative-control 테스트 (`test_pd_cyclicality.py:*`), threshold 를 `harness/pd_design_thresholds.json` 로 외부화 (하드코딩 회피). 3선 관측능 확장의 정당한 방향.
- **`validation-team-agent/harness/policies/pd_lgd_ead.md`**: 신설 41 줄. PD 설계 구분 (TTC/PIT) 판단 정책 문서화. 3선 심사 기준 명문화.
- **`risk_lib/datamodel/materialize_detail.py`**: `mkt_portfolio_detail`, `mkt_var_alloc`, `mkt_portfolio_capital` 등 상세 원장 5 종 신규. 포트폴리오 유형 상세 화면 뒷단 원장 완비 (M8 순서 의존 지적은 있으나 데이터 자체는 옳음).
- **`docs/risk_team_architecture.html` (15k 줄), `docs/validation_team_architecture.html` (15k 줄)**: Archify 로 팀에이전트 아키텍처 다이어그램 산출. 팀 구조 가시성 확보 (렌더링 결과물이라 코드 리뷰 대상 아님).

## 4. MAJOR (누계·미소화)

42주차 §2 의 60+ 건, 43주차 §2·§A 의 99+ 건이 전량 미소화된 상태를 유지. 여기서는 44주차 델타에서 추가로 관찰된 것만 나열 (§2-1 MAJOR 10 건이 이에 해당).

43주차 §4 에서 지적된 "WARN 은 게이트를 통과한다" 회귀 통제 부재 문제는 §2-1 M3 (`_check_market_portfolio_split` WARN) 에서 신규 발현. 같은 계약 실패 모드가 신설 게이트에서도 반복 = 코드 리뷰가 통제로 작동 안 함의 방증.

## 5. PR ownership 상태 (매주 확정)

`git log --since="2026-08-14"` 43 커밋을 브랜치별로 재구성 (git-only, PR 상태는 gh 인터페이스 미확인, 추후 갱신 예정):

- **`claude/stoic-ride-u3mmwj`** (현재 리뷰 브랜치): 44주차 리뷰 자체가 대체 정본이 됨. head `454a95e`.
- **`claude/validation-team-agent-Pw9F5`**: 델타에 `pd_cyclicality.py` 신설 커밋 (`3912f66`) 이 origin/main 에 들어와 있음. 43주차 dormancy (9 일) 이 풀렸으나 §1-3 지적한 `RECALCULATORS` 확장 6→21 은 여전히 미착수. 별도 확인 필요.
- **`origin/main`**: 43주차 `00fb2c6` 에서 44주차 `60bda57` 로 12 커밋 이동 (fast-forward 흔적). 대부분 sales 캠페인 문서·아웃리치 자산 (T3 노트, ICP, 리서치 배치). Python 코드는 §2 델타 파일 8 종에만 국한.
- **B9Kxm** (`claude/risk-management-agent-harness-B9Kxm`): 델타 43 커밋에 무커밋. **26 일간 dormant**. Warden 개입 조건 성숙 (43주차 기준 이미 14 일).
- PR #46 (nail-simulation), #38 (3D shooter), #57 (HANDOVER.md): 43주차 dormancy 지속 관측치. 별도 확인 없이 dormant 판정 유지.

## 6. 권고 (재발 방지)

우선순위대로 세 개. 43주차 §6 재요구를 그대로 유지 (하나도 이행되지 않음).

### 6-1. 사전 커밋 훅 두 개 (**43주차 §6-1 재요구, 3주 연속 미이행**)

18 일간 em/en dash +134 회, 벽시계 +18 회. 훅이 도입되지 않는 한 매주 리뷰가 매주 늘어난다.

```bash
# (1) em/en dash 차단
if git diff --cached --name-only | xargs grep -l $'\xe2\x80\x93\|\xe2\x80\x94' 2>/dev/null; then
  echo "em/en dash 발견. CLAUDE.md §5 위반." >&2; exit 1
fi

# (2) 벽시계 차단 (tests/, .claude/, validation-team-agent/ 제외 여부는 팀 정책)
if git diff --cached --name-only | grep -Pv '^(tests|\.claude)/' | \
   xargs grep -Pn '\bdate\.today\(\)|datetime\.now\(|time\.time\(\)' 2>/dev/null; then
  echo "벽시계 리크. AIMS §2-2 위반. asof 를 인자로 받으세요." >&2; exit 1
fi
```

배치 위치는 `.git/hooks/pre-commit` (exec bit) 또는 `.pre-commit-config.yaml` + `pre-commit install`. 43주차 리뷰 이후로 `.git/hooks/pre-commit` 는 여전히 부재, `.pre-commit-config.yaml` 부재, `.claude/settings.json` 에 `hooks` 키 부재로 재확인 완료.

### 6-2. `decompose.py:191` 즉시 raise (**43주차 §6-2 재요구, 2주 연속 미이행**)

`decompose_from_result` 는 `result.meta["asof"]` 필수. 없으면 raise. 43주차에도 명시 지적. 44주차 델타에서 datamodel/* 를 광범위하게 만졌으면서도 이 한 줄은 그대로. `_all_predecessors` 처럼 계약을 코드로 강제해야 매주 반복되는 앵커 드리프트가 종결된다.

### 6-3. 3선 `RECALCULATORS` 확장 착수 (**43주차 §6-3 재요구, 3주 연속 미이행**)

`validation-team-agent/tools/independent_recalc.py:RECALCULATORS` 를 `RECALC_SCOPE` 21 개 전량으로 확장. 미구현 항목은 명시적 "미구현" 상태로 등록해서 게이트가 응답대기로 남게. 6 개만 True 로 통과하는 현재 상태는 **AIMS §2-4 위반이 4 주째 이어지는 것**. Pw9F5 브랜치가 이번 델타에 `pd_cyclicality.py` 로 활성화되었으므로 착수 여건은 성숙.

## 7. 리뷰 메타 (3 서브에이전트 · 병렬)

- 리뷰 도구: 3 개 병렬 서브에이전트 (general-purpose). 총 소요 약 900 초, 소비 토큰 약 312k.
- 리뷰 커버리지:
  - (A) 43주차 §1 tracked BLOCKER 47 건 + §A 서브시스템 샘플 12 건 = 59 건 재점검.
  - (B) 델타 신규 Python 4 파일 + 변경 Python 10 파일 리뷰 (신규 결함 20 건).
  - (C) 저장소 전수 정책 감사 (em/en dash, 벽시계, 미시드 RNG, 훅 배치).
- 자체검증 (2선), 상시 독립검증 (3선): 이 리뷰는 코드 리뷰이며 리스크 산출 아님. `RECALC_SCOPE` 대상 아님.
- 파일: `reports/code_review/2026-09-01_full_repo_review.md` (본 파일).

---

_Generated by [Claude Code](https://claude.ai/code)_
