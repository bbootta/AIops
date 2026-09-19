# 저장소 전수 코드 리뷰 (2026-08-12)

**대상**: `bbootta/AIops` 전 저장소 (633 개 코드 파일)
**리뷰 방식**: 8 개 리뷰어 서브에이전트 병렬 실행, 서브시스템별 분담
**분담**: (1) risk_lib 최상위, (2) risk_lib/regulatory, (3) risk_lib/alm+capital+credit_rating+icaap+prudential, (4) risk_lib monitoring/limits/crm/governance/stress/validation/models, (5) harness+examples+tools+cli, (6) validation-team-agent, (7) tests, (8) 저장소 전수 정책 감사

## 0. 총평 (심각도 요약)

| 범주 | 건수 | 대표 사례 |
|---|---|---|
| BLOCKER (재현·규제·거버넌스 결함) | 30+ | FSS 대사·전 파이프라인 벽시계·독립검증 서명 부재 |
| MAJOR (계산·통제·문서 결함) | 60+ | LimitBreach.severity 상충·IRRBB scenario 게이트·SFT 해어컷 미조정 |
| MINOR (정리) | 40+ | 하드코딩 상수·주석 수정·이름 정리 |
| 정책 위반 (em/en dash) | **9,076 건 / 617 파일** | 저장소 전수 |
| 벽시계 (`date.today`, `datetime.now`) | 20+ 파일 | 리포트·매니페스트 재현 파괴 |

**최대 위험**: 파이프라인 진입점(`pipeline.py:1502`)과 CLI 7/12 서브커맨드가 `asof` 없이 실행 시 벽시계로 폴백한다. AIMS 정책 §2-2 (재현가능성) 근본 위반이며, 감사원가 어떤 이슈보다 먼저 지적할 사안이다. 이 한 개 이슈가 저장소 전체 산출물의 재현성 주장을 무효화한다.

## 1. 즉시 조치 (BLOCKER)

### 1-1. 재현성 (벽시계 리크)

`asof or date.today()` 폴백을 raise 로 바꾸고, 폴백이 필요한 지점은 명시적으로 문서화해야 한다.

- `risk_lib/pipeline.py:1502` , 파이프라인 진입점 폴백. 하위 모든 원장이 벽시계 상속.
- `risk_lib/cli.py:29-61 (_cmd_run)` , 7 개 서브커맨드에 `--asof` 인자 없음.
- `risk_lib/cli.py:365-393 (_cmd_reproduce)` , 저장된 manifest 의 `asof` 를 `run_pipeline` 인자로 넘기지 않음. 재현 명령이 재현하지 못한다.
- `risk_lib/cli.py:265` , 기관 인자 있으면 `asof = a or "2025-12-31"` 하드코딩 폴백.
- `risk_lib/notifications.py:59` , `collect_alerts` 가 `datetime.now(UTC)` 를 번들에 스탬프.
- `risk_lib/deliverables.py:101` , 배포 MANIFEST 헤더에 `datetime.now(UTC)`. ZIP SHA 매 배포 다름.
- `risk_lib/adjustments.py:308` , demo_ledger 폴백. adjustment 원장 지문 -> manifest 재현성 파괴.
- `risk_lib/stress/path.py:110` , `forecast_quarter_labels(asof or date.today(), ...)`.
- `risk_lib/archive.py:129,:154` , run_date + created_at 폴백. 동일 실행이 매니페스트 다름.
- `risk_lib/report.py:43`, `risk_lib/report_chrome.py:144`, `risk_lib/board_pack.py:87,:418`, `risk_lib/work_report.py:84`, `risk_lib/ops_pages/core_overview.py:332` , 리포트 표지·페이지 푸터·이사회 팩·업무보고서·ops 페이지 asof 폴백.
- `risk_lib/case_studies/{bank7_2026q1,ib3_2026q1,ib3_report}.py` , 케이스 스터디 "산출 기준" 라인 벽시계.
- `risk_lib/market_data.py:521`, `localization.py:100,:152`, `model_inventory.py:45,:61`, `model_risk.py:36`, `datamodel/decompose.py:164` , 파이프라인·리포트 계층이 임포트하는 유틸에도 같은 패턴.

**권고**: 사전 커밋 훅으로 `tests/`, `.claude/`, `validation-team-agent/` 밖에서 `date.today()` / `datetime.now(` / `time.time()` 발생을 차단.

### 1-2. FSS 규제보고 대사 (거짓 통과·거짓 실패)

`risk_lib/regulatory/cross_form.py` 의 라인코드 등록이 실제 폼과 어긋난다. 매 제출마다 spurious FAIL 이 발생하거나, 값이 다른 두 항목이 통과된다.

- `cross_form.py:61` , `("BR-31","1110")` 총자본비율 대사 등록. `forms_ext.py:545 br_camel` 은 BR-31 을 1000/1100/1200 스텝으로 만들므로 1110 은 존재하지 않는다. "대사 대상 라인 없음" FAIL 이 매 제출마다 발생, fail-closed 게이트가 절대 열리지 않는다.
- `cross_form.py:77` , 같은 문제로 `("BR-31","1510")` LCR 대사.
- `cross_form.py:51` , `("BR-20","5000")` 위험가중자산 합계. `forms_ext.py:223` 은 여기에 `floored_rwa` (신용만) 를 넣지만, BR-01/2000 과 B2312/4000 은 `rwa["final_total"]` (신용+시장+op+CCR) 를 넣는다. 1.0 KRW tol 을 훨씬 넘어 미스매치.
- `forms.py:379-380` BR-08 , `_sum_check("순현금유출 = 총유출 − 인정유입", ..., tol=float(lcr.inflow_capped)+1.0)`. tol 이 netting 되는 양 자체. 어떤 입력이든 항등적으로 통과한다.
- `cross_form.py:38-49,:70` , "감독규정 최저적립액 합계" 는 B2506/3000, B2403/1010, B2431/1010 에도 나타나지만 등록되지 않음. "기대신용손실 합계" 는 B2506/2000 누락. "유동성커버리지비율" 은 B2916/1000, B2602-2/1000 누락.

### 1-3. 3선 독립검증의 신뢰성 결함

`risk_lib/validation/independent.py` 와 `validation-team-agent/` 는 AIMS §2-4 를 구현하지만 세 지점에서 결함이 있다.

- `validation-team-agent/tools/independent_recalc.py:140` , `RECALCULATORS` 는 6 개만 (lcr, nsfr, cet1_ratio, leverage_ratio, icaap_ratio, portfolio_default_rate). `risk_lib/validation/independent.py:44` 의 `RECALC_SCOPE` 는 21 개. **15 개 headline 이 독립 계산기 없음** (rwa_final_total, rwa_fund, rwa_securitisation, total_ratio, ecl_total, ecl_weighted_total, irrbb_worst_pct_tier1, irrbb_delta_nii_parallel, survival_days, stress_trough_cet1, reverse_critical_severity, reserve_shortfall, kr_irrbb_table6_*, lgd_backtest_*, ccf_realised_mean). 3-line-of-defense 주장이 71 % 범위에서 성립하지 않는다.
- `risk_lib/validation/independent.py:684` , `check_gate` 는 `resp.recalc_matches[k]` 를 액면가 신뢰. 재계산 증거·서명·해시 없음. all-True JSON 한 줄이면 게이트 통과. 위조에는 무방비.
- `risk_lib/validation/independent.py:176,:186` , `ValidationResponse.read` / `Finding` 이 severity 문자열을 검증하지 않음. "중대" 같은 오타면 "not 중부적합" 으로 읽혀 게이트가 적합으로 뒤집힌다. `VERDICTS`/`STATUSES` 튜플이 정의되어 있지만 어디서도 강제하지 않음.

### 1-4. 리스크 코어 결함

- `risk_lib/integrations.py:302-314` , `IsolatingDispatcher.send_with_isolation` 이 완전히 깨져 있다. WebhookRequest 를 dict 페이로드 기대하는 send() 에 넘김. `req.kind` (없음) 참조. `hashlib.sha256(req.body)` 를 str 에 호출 (bytes 필요). policy.delays() 미대기. dry-run 이외 첫 호출에 raise.
- `risk_lib/limits/limit_engine.py:41-47` vs `risk_lib/limits/limits_deep.py:55-62` , 같은 라벨 "CRITICAL" 이 정반대 의미. `LimitBreach.severity` 는 유틸 >= 1.20 (BREACH 초과). `limits_deep._severity` 는 >= 0.90 (BREACH 미만). 같은 로우가 CRO 대시보드에 정반대 의미로 CRITICAL 뜬다.
- `risk_lib/monitoring/deep.py:210-215` , 90+ 로우 `[0.02,0.02,0.03,0.05,0.88]` 은 월 12 % 로 default 를 탈출한다. cure 로직 없이. Markov projection 이 NPL persistence 를 과소평가.
- `risk_lib/op_loss.py:88` , 관측 1 개면 `std()` 가 NaN. `float(nan) or 1.0` 은 nan (nan 이 truthy). VaR/ES 가 NaN 으로 오염.

### 1-5. 테스트 결함 (최근 커밋 회귀 통제 부재)

- `tests/test_frtb_inventory.py:178-183` , `is_overdue()` 를 `today=` 없이 호출. 2030-01-01 baseline. 2030 년에 조용히 FAIL 로 뒤집힘. 시한폭탄.
- `tests/test_frtb_inventory.py:72,:81` , `np.random.normal(...)` 이 seed 없이 글로벌 RNG.
- `tests/test_frtb_inventory.py:192`, `test_monitoring_deep.py:262`, `test_stress_deep.py:336,:350` , `run_pipeline()` 에 asof 없음. `test_wall_clock_asof_is_disclosed_not_silent` 규약 위반.
- 커밋 `f7b532f` (2026-08-12, `institution_in_ledgers` 도입), `2e1d65d` (트리맵 라벨), `0d574ab` (빈 문자열 처리) 모두 회귀 테스트 부재.

## 2. MAJOR (예정 조치)

### 2-1. 규제 계산 정밀도

- `risk_lib/alm/irrbb.py:626-634` , [별표 9-1] 제21항 나는 "총 금리리스크" 를 max across scenarios 로 정의. per-scenario 로 `outlier_test_pass` 를 쓰면 non-worst 시나리오 16 % 도 outlier_duty 텍스트를 끌어옴. `is_worst` 로 게이트.
- `risk_lib/capital/crm.py:35-73` , CRE22.51 은 SFT 5 일·기타 20 일에 대해 H_10 스케일링 필요. 현재 10 일·일일 remargining 하드코딩. SFT EAD 과소.
- `risk_lib/capital/rwa_sa.py:56-57` , 연체 150 % 고정. CRE20.90 은 충당금 20 % 이상이면 100 %. 잘 충당된 default 에서 RWA 과대.
- `risk_lib/alm/nsfr.py:240-261` , compat 경로 `compute_nsfr` 가 `maturity_band_of` 를 부르지 않음. balance_sheet.py 의 사전 버킷팅에만 의존.
- `risk_lib/alm/nii.py:243` , `nii_base` 가 계약별 sign*bal*rate*H sum. 12 개월 지평에서 짧은 repricing 부채는 reset-implied rate 로 조정 필요. delta 는 맞고 base 만 틀림.
- `risk_lib/capital/bis_deep.py:243-267` , `at1_t2_recognition_limits` 가 AT1 을 CET1/3, T2 를 Tier1/3 로 cap. Basel III 에 이런 구조적 cap 없음. 이사회 팩에 "규제 exclusion" 처럼 보임.
- `risk_lib/alm/lcr.py:242-269` , L2A/L2B 사후분해가 `l2_after15 == 0` 이면 `scale40 = 0` 이 되어 L2A 절감이 사라짐. hqla_total 은 맞지만 breakdown 표시 왜곡.
- `risk_lib/frtb.py:141` , NMRF 당 flat 10 억원 addon. BCBS MAR33 은 stressed ES 요구. `frtb.py:218` `sa_capital_fallback = sa_charge * 1.30` 은 BCBS 근거 없음.
- `risk_lib/ccr.py:79` , `bank_rw = 0.50` 하드코딩. SCRA (CRE20.6) 는 A/B/C 등급 40/75/150.

### 2-2. 거버넌스

- `risk_lib/governance/rbac.py:290-317` , `decide_access` 가 `gov_sod_conflict` 를 조회하지 않음. SOD 는 사후 보고만. 최소권한 원칙이 결정 시점에서 강제되지 않음.
- `risk_lib/governance/model_lifecycle.py:175-236` , 모든 인벤토리 전이가 `evidence_ref=None`. 모든 프로덕션 모형이 `control_status='증빙미첨부'` 로 남고, 아무것도 게이팅하지 않음. 미증빙 모형의 승격을 막는 require() 없음.
- `risk_lib/crm/allocation.py:228-253` , pro-rata allocation 이 `_MAX_ROUNDS=8` 로 캡, 잔여를 조용히 반환. downstream 이 "solver stopped" 와 "no demand" 를 구분 못함.
- `risk_lib/stress/scenario.py:31-41` , `stress_pd` 가 `np.maximum(pd_base, pd_sat)` 로 one-sided. 양의 gdp_shock (comparison, sensitivity, reverse) 에서 개선분이 조용히 사라짐.
- `risk_lib/stress/ccar.py:161-227` , `evaluate_scenario` 는 `bis.required["cet1"]` 사용, `run_ccar` 리커버리 요약은 `buffers is None` 이면 하드코딩 default 로 `req_cet1` 재조립. 같은 run 안에서 "required CET1" 두 값.
- `risk_lib/validation/consistency.py:213-223` , `_check_asof_provenance` 가 벽시계 asof 에 WARN 리턴. WARN 은 게이트 통과. 비재현 headline 이 통과.
- `risk_lib/validation/consistency.py:1179-1188` , `alm_unconfirmed_param_in_use` 가 금리충격 proxy 에서도 WARN. proxy 는 ΔEVE headline 을 직접 바꿈.

### 2-3. FSS 규제 폼

- `excel.py:170-189` , `ln.line_name`, `ln.formula`, `ln.text_value` 를 검증 없이 셀에 쓴다. leading `=+-@` 이면 Excel 이 수식 해석. `'` prefix 또는 거부.
- `excel.py:283` , in-memory Workbook 로 290 개 폼 + 라인 시트. write_only 로 전환 필요.
- Citation coverage 미강제. `citations.py:22` 는 제N조 제M항 만 카운트. Basel CRE/LCR/OPE/MAR 스타일은 카운트 안 됨. 2287 개 FormLine 중 958 개 (42 %) 가 citation 없음, 771 개 (34 %) 가 source_module 없음.
- `forms.py:864` 가 임포트 후 module-level FORMS 를 in-place 변형. `build_forms` (:887) 가 같은 순서를 SECTIONS 에서 재계산. 두 순서가 drift 가능.
- `forms_fss_liquidity.py:100` 이 import 시점에 `ladder_citation()` -> `alm_time_bucket` 호출. `build_time_buckets()` 실패면 regulatory import 표면 전체 붕괴.
- `forms_fss_asset.py:107`, `forms_fss_profit.py:304`, `forms.py:485` 가 같은 `reserve_requirement(aq)` 를 세 번 호출. 세 값이 diverge 하면 제출 차단.
- `form_ids.py:174-178` , 무관 섹션이 "사. 현지화평가" 아래 잘못 묶임. 향후 마스터 정리 시 조용히 SECTIONS 에서 사라짐.

### 2-4. 독립검증 계층

- `risk_lib/validation/independent.py:167` , `passes` 는 `verdict == "적합"` 만 확인, finding severity 미확인. verdict="적합" + 중부적합 finding 이 게이트 통과. 확인 필요: `verdict == max(severity)`.
- `validation-team-agent/tools/conditional_approval.py:83` vs `risk_lib/validation/independent.py:193` , 두 `ConditionalApproval` 스키마 중복. 한쪽이 만든 레코드가 다른쪽의 `require_complete`/`grant` 를 자동으로 만족시키지 못함.
- `validation-team-agent/tools/conditional_approval.py:274,:173` , `compliance()`, `escalations()`, CLI default 가 `as_of = date.today()`. overdue 판정이 벽시계로 뒤집힘.

### 2-5. CLI / Tools / 도구

- `risk_lib/cli_docs.py:19,:38,:100` , 존재하지 않는 `pdf` 서브커맨드 문서화. 실제로는 `printable`.
- `risk_lib/cli.py:243-251 (_cmd_ui_studio)` , module-level `_app.INTERACTIVE_ROWS` 를 in-place 변형. 프로세스 전역 오염.
- `tools/gen_fss_master.py:17` , `OUT = Path("risk_lib/regulatory/fss_master.py")` 상대 경로. CWD 에 stray 트리 생성.
- `tools/gen_fss_master.py:123`, `tools/gen_requirements.py:60` , `sys.argv[1]` 미확인. IndexError.
- `risk_lib/archive.py:52-53` , `TEAM_HOME = Path("teams/risk-management")` 상대. 저장소 밖에서 실행하면 CWD 에 흩뿌림.
- `risk_lib/cli.py:437-440,:469-476,:478-480` , `notify`, `dispatch`, `api-spec` 헬프에 필요 env / 출력 레이아웃 미기재.
- `harness/team.yaml` + `harness/legal/team.yaml` , 무관한 두 팀이 같은 최상위 harness/ 폴더. 인덱스 없음.

## 3. MINOR

- `risk_lib/pipeline.py:1645-1646` , `model_cards = build_model_cards(...) if False else []`. 죽은 삼항.
- `risk_lib/pipeline.py:293-296` , `_seg_grade` 계산·쓰기 후 안 읽음. 죽은 쓰기 또는 두 번째 `pd_to_rating` 이 조용히 틀렸음.
- `risk_lib/notifications.py:158` , `bundle.asof[:10]` UTC 슬라이스. KST 자정 근처 하루 밀림.
- `risk_lib/macro_monitor.py:447-454` , `prior in (None, 0)` 가드가 NaN 을 안 잡음.
- `risk_lib/pipeline.py:1989` , `market_op_share = (rwa["market"] + rwa["op"]) / final`. all-zero synthesized institution 에서 ZeroDivisionError.
- `risk_lib/models/lgd_model.py:29-50` , 하드코딩 LGD floor. 파일 자체 주석이 저장소 규칙 위반이라고 표시.
- `risk_lib/alm/curves.py:487-489` , log(DF) flat extrapolation. 30 y 넘는 t_mid 는 조용히 discounting 없음.
- `risk_lib/alm/schedule.py:135` , maturity <= asof 시 조용히 tau=0. raise 권장.
- `risk_lib/capital/rwa_irb.py:38-40` , 주석 "3 bp" vs `references.PD_FLOOR_BPS = 5`. 오래된 주석.
- `risk_lib/capital/leverage_deep.py:174-178` , `shortfall_pct == gsib_buffer` 경계에서 off-by-one.
- `risk_lib/credit_rating/build.py:57` , `_PSI_BINS=10` / `_HOLDOUT_SHARE=0.3` 모듈 상수, ledger 없음. 파일 docstring 의 "no hidden defaults" 위반.
- `risk_lib/icaap/economic_capital.py:49-55` , `min(0.15, 0.5*hhi_sector + 0.3*hhi_country)` 인용 없이 15 % cap. Gordy 인용은 있으나 선형 형태는 Gordy 에서 나오지 않음.
- `risk_lib/prudential/liquidity.py:37` , `FX_SHARE = 0.13` 코드 내부. pru_liquidity_param 로 이동.
- `risk_lib/prudential/pca.py:63-65` , 부실금융기관 결정 (별도 법적 이벤트) 이 없다는 사실을 NULL sentinel 로 명시.
- `risk_lib/governance/change_control.py:207-270` , `evaluate_change_gate` reason 문자열 중복 가능.
- `risk_lib/governance/audit_chain.py:36-111` , "정정" 이벤트가 어떤 actor 로도 append. actor 서명 필요.
- `risk_lib/stress/climate_capital.py:35-46` , NGFS 경로 하드코딩, evidence_status 없음.
- `risk_lib/limits/limit_engine.py:83-88` , dtype mismatch 시 empty 조용히 리턴. 진단 없음.
- `risk_lib/monitoring/cure.py:59-61` , time-to-cure 를 cure_window 로 clip. 검열 (censoring) 이 사라짐.
- `risk_lib/monitoring/vintage_deep.py:40-48` , cohort 를 `rng.integers` 로 배정. 실 origination 아님.
- `risk_lib/monitoring/deep.py:262-276` , `markov_projection` 이 EAD-weighted state 를 obligor-level P 와 곱함. 단위 불일치.
- `risk_lib/integrations.py:63` , `json.dumps(payload, ensure_ascii=False)` 가 sort_keys 아님. dict-order 로 idempotency 키가 달라짐.
- `risk_lib/market_data.py:116` , `self.quotes.round(10).to_dict(...)` 는 numeric 컬럼만 가정.
- `risk_lib/frtb.py:122-126` , `rfet_test` 가 date 컬럼도 risk factor 로 취급.
- `risk_lib/notifications.py:83` , 알림 정렬 tie-break 없음. run 마다 순서 변동.
- `risk_lib/repro.py:75-82` , `_git_commit()` 이 dirty-tree 미기록.
- `risk_lib/report_chrome.py`, `risk_lib/board_pack.py`, `risk_lib/ops_pages/core_overview.py` 등 리포트 계층 자체가 asof 폴백을 갖고 있어 리포트 재현성이 코어보다 낮다. 상단 정리 시 함께 정리 필요.
- 테스트 이름: `test_extras.py:86 test_http_server_routes_smoke`, `test_frtb_inventory.py:111 test_backtest_var_smoke` , 실제 계약 테스트인데 이름이 smoke 로 위장.
- `tests/risk_agents.py` 는 test_*.py 가 아니어서 pytest 가 수집 안 함. conftest autouse 또는 test_*.py 로 이동.

## 4. 정책 위반 (일괄 조치)

### 4-1. Em/en dash 금지 (CLAUDE.md §5)

저장소 전수 grep 결과: U+2014 (em dash) 과 U+2013 (en dash) **9,076 건 / 617 파일**. 매 발생이 규칙 위반.

- 규제 폼 (`forms_fss_liquidity.py`, `forms_fss_capital.py`, `forms_fss_profit.py` 등) 안의 dash 는 최종 xlsx 로 렌더되어 감독당국 제출물에 실린다. 최우선 정리.
- `risk_lib/validation/independent.py` 자체가 64 건. 규칙을 강제하는 모듈이 규칙 위반.
- `.claude/agents/aims-compliance-auditor.md` 9 건. 감사자 페르소나 자체가 위반.
- 상위 파일: `.claude/agents/stress-test-engineer.md` (12), `.claude/agents/aims-compliance-auditor.md` (9), `.claude/commands/translate.md` (9), `.claude/agents/terminology-curator.md` (5), `.claude/agents/fluency-editor.md` (4), `.claude/agents/translator.md` (4).

**권고**: 사전 커밋 훅에 `grep -l $'\xe2\x80\x93\|\xe2\x80\x94'` 추가. 병렬로 일괄 sweep 은 sed 로 em dash 를 콤마로, en dash 를 하이픈으로 치환. 커밋 `c2ec33f` (구두점 규칙 적용: 내 산출물의 em/en dash 제거) 이 이미 부분 sweep 했으나 저장소 전체는 아직.

### 4-2. RECALC_SCOPE 커버리지

`risk_lib/validation/independent.py:44` 의 21 개 키는 모두 `_headline()` (독립.py:337-363) 이 채워주고, `report.py`/`board_pack.py`/`pillar3.py` 는 그 매핑 안에서만 metric 을 참조한다 (grep 12/17/19 hit, 모두 매핑됨). 프로덕션 headline 은 RECALC_SCOPE 에 다 있음. drift 없음.

**그러나** §1-3 에서 지적한 대로 3선 팀의 RECALCULATORS 는 6 개만 커버. 프로덕션은 21 개를 요구하지만 3선은 6 개만 다시 계산한다. **AIMS_POLICY.md §2-4 위반**.

### 4-3. AIMS §5 통제 ↔ 구현 표 대조

- A.6.2.2 OK. A.6.2.6 OK. A.6.2.7 partial (page_registry 72 페이지 vs README "66페이지").
- A.6.2.8 OK. A.7.2 OK. A.7.4 OK. A.8 OK. A.9.2 OK. A.10 OK.
- A.6.2.4 partial: README "13 체크" vs AIMS "52종", "572 골든 테스트" claim 은 실제 93 test 파일만 있으므로 재확인 필요.

### 4-4. README / ARCHITECTURE drift

- `README.md:252` "13 서브에이전트" , 실제는 10 개만 열거, 실 개수 다름.
- `README.md:325` "tests/ (1,009건)" , 실 test 파일 93 개. 카운트가 도출되지 않고 하드코딩.
- `README.md:308` `regulatory/forms.py` 만 언급 , forms_ext, form_ids, fss_master, forms_fss_card*, cross_form, provenance, citations, structure 미언급.
- `ARCHITECTURE.md:24` "266 테이블 / 2822 컬럼" , 하드코딩 숫자. datamodel/catalog.py 에서 도출해야.
- `ARCHITECTURE.md:43` 이 벽시계 금지 명시하지만 §1-1 20+ 파일이 위반.

### 4-5. 보안·기밀

`api_key|password|token|secret|bearer` grep 결과 모두 정당한 사용 (permission_guard regex, redaction test, field policy fixture, design token). 커밋된 자격증명 없음.

## 5. 권고 (root cause & 재발 방지)

### 5-1. 사전 커밋 훅 두 개

두 훅으로 §1-1 + §4-1 의 대부분을 정리 후 재발 방지:

```bash
# (1) em/en dash 차단
if git diff --cached --name-only | xargs grep -l $'\xe2\x80\x93\|\xe2\x80\x94' 2>/dev/null; then
  echo "em/en dash 발견. CLAUDE.md §5 위반." >&2; exit 1
fi

# (2) 벽시계 차단 (tests/, .claude/, validation-team-agent/ 제외)
if git diff --cached --name-only | grep -Pv '^(tests|\.claude|validation-team-agent)/' | \
   xargs grep -Pn '\bdate\.today\(\)|datetime\.now\(|time\.time\(\)' 2>/dev/null; then
  echo "벽시계 리크. AIMS §2-2 위반. asof 를 인자로 받으세요." >&2; exit 1
fi
```

### 5-2. `run_pipeline` 시그너처 강화

`asof` 를 필수 키워드 인자 (`*, asof: date`) 로 만들고, `date.today()` 폴백을 완전히 제거. CLI 는 각 서브커맨드에 `--asof YYYY-MM-DD` 를 반드시 노출. `reproduce` 는 저장된 manifest 에서 `asof` 를 회수해 명시 전달.

### 5-3. cross_form 등록 재검증

`cross_form.py` 의 라인코드 등록을 `forms_ext.br_camel`, `forms.py`, `forms_fss_*.py` 실행 후 실제 나온 line_code 셋과 대조하는 회귀 테스트를 추가. 미등록 라인이 있으면 FAIL. §1-2 재발 방지.

### 5-4. 3선 RECALCULATORS 확장

`validation-team-agent/tools/independent_recalc.py:RECALCULATORS` 를 RECALC_SCOPE 의 21 개 전량으로 확장. 미구현 항목은 명시적으로 "미구현" 상태로 등록해서 게이트가 응답대기로 남게 하고, 6 개만 True 로 통과하는 현재 상태를 차단.

응답 파일에 (a) 재계산 프로그램 해시, (b) 프로그램 실행 시 sha256(입력 지문 + 파라미터), (c) 서명자 서명 을 필수 필드로 추가. `check_gate` 는 이 세 값을 검증.

### 5-5. 리포트 재현성 스모크 테스트

같은 (seed, asof, 코드 커밋) 로 두 번 실행 시 `deliverables.py` 가 만든 zip 의 sha256 이 동일한지 확인하는 테스트를 하나 추가. §1-1 의 여러 지점이 한 테스트로 잡힌다.

## 6. 리뷰 메타

- 리뷰 도구: 8 개 병렬 서브에이전트 (general-purpose), 총 소요 약 542 초.
- 소비 토큰: 약 1.48 M 소각 (서브에이전트 합).
- 커버리지: `risk_lib/` 상위 + 8 개 서브패키지 + `harness/` + `examples/` + `tools/` + `validation-team-agent/` + `tests/` + 저장소 전수 정책 grep.
- **자체검증 (2선)**: 이번 리뷰는 코드 리뷰이며 리스크 산출이 아님. `risk-validator` 실행 대상 아님.
- **상시 독립검증 (3선)**: 코드 리뷰는 `RECALC_SCOPE` 대상이 아니므로 3선 요청 없음.
- **다음 단계**: 리뷰 결과 자체는 산출이 아니므로 AIMS 결재 게이트에 걸리지 않는다. 위 5-1 훅부터 도입 권고. §1-2 (FSS 대사) 는 폼 감독당국 제출 전까지 반드시 정리.
