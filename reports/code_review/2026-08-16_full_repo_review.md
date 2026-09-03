# 저장소 전수 코드 리뷰 (2026-08-16, 44주차)

**대상**: `bbootta/AIops` 전 저장소, base `origin/main` = `153d7d6`
**직전 리뷰**: `reports/code_review/2026-08-14_full_repo_review.md` (43주차, PR 미상 · commit `153d7d6`)
**델타 창**: 2026-08-14 21:34 → 2026-08-16 (약 43 시간), **0 커밋 (코드 델타 없음)**
**리뷰 방식**: 6 개 서브에이전트 병렬. (5) tracked BLOCKER 재확인, (1·2·3·4·6) 서브시스템 신규 결함.

## 0. 총평 (한 문장)

44주차 리뷰 창에는 **코드가 한 줄도 바뀌지 않았다**. 그런데도 6-병렬 sweep 이 이전 리뷰가 다루지 않은 표면에서 **BLOCKER 8, MAJOR 35, MINOR/MEDIUM 9 (합 52)** 를 새로 발굴했다. 42주차·43주차의 tracked BLOCKER 21 건 중 **20 건이 여전히 LIVE, 1 건이 PARTIAL, 0 건이 FIXED**. 조직이 리뷰 결과를 소비하지 않는다.

| 층위 | 42주차 (PR #67) | 43주차 | 44주차 | 변화 |
|---|---|---|---|---|
| 코드 델타 (커밋) | , | 8 커밋 | **0 커밋** | 활동 정지 |
| Tracked BLOCKER LIVE | 6 → | 21 (신규 15 반영) | **20 LIVE + 1 PARTIAL** | -0 |
| 신규 결함 | 60+ | 99 | **52** | 잔여 발굴 여지 확인 |
| 신규 BLOCKER | , | 11 | **8** | , |
| 3선 RECALCULATORS 커버 | 6/21 (29 %) | 6/21 (29 %) | **4/21 (19 %)** | **재계산 (43주차 6 → 44주차 4)** |
| em/en dash 파일 | 617 | 633 | **633** | 변화 없음 (변경 없음) |

**최대 위험 (44주차 신규)**: 세 곳에서 "**항등식 검증**" 이 발견되었다.
- `risk_lib/data_quality.reconcile()` 이 CET1 비율·LCR·NSFR 을 각각 **자기 자신의 정의**와 대조 (§B-2). 세 건 모두 산술적으로 항등이라 절대 실패할 수 없다.
- `risk_lib/datamodel/materialize_detail.py` 의 `rdm_reconciliation` 세 항목이 같은 컬럼에서 양쪽을 뽑아 대사 (§B-2). 같은 결함 클래스.
- 3선 `_auto_verdict(kind="golden")` 이 커버되지 않는 17/21 타깃에 대해 `None` 을 반환해 `VERDICT_UNANSWERED` 로 조용히 처리 (§B-6).

세 결함이 43주차 §A2-1 (cross_form 항등 불변식) 과 결합하면, **저장소의 세 대사 층 (data-quality · rdm reconciliation · cross-form · 3선 golden verdict) 이 모두 항등식** 이 된다. 통과 카운트가 커버리지처럼 보이지만 모두 falsifiable 하지 않다.

## 1. Tracked BLOCKER 재확인 (§A, Reviewer #5)

21 개 tracked BLOCKER (PR #67 §1-1..§1-6 6 건 + 43주차 부록 A 15 건) 을 델타 이후 상태로 다시 검증.

**요약: LIVE 20, PARTIAL 1, FIXED 0, ANCHOR-DRIFTED 0.**

| ID | 심각도 | 파일:줄 | 상태 |
|---|---|---|---|
| §1-1 | BLOCKER | `risk_lib/pipeline.py:1502` + 18 지점 | LIVE (`asof = date.today()` 폴백 그대로) |
| §1-2 | BLOCKER | `risk_lib/regulatory/cross_form.py:61,77,51` + `forms.py:380` | LIVE (BR-31 라인코드 미변경, LCR 항등 tol 그대로) |
| §1-3 | BLOCKER | 3선 독립검증 | **PARTIAL** (`check_gate` identity binding landed, 그러나 서명·해시 없음, RECALCULATORS 6→4 로 오히려 후퇴) |
| §1-4 | BLOCKER | `integrations.py:302-314`, `limits/limit_engine.py:41-47` vs `limits_deep.py:55-62`, `op_loss.py:88` | LIVE (전건) |
| §1-5 | BLOCKER | `tests/test_frtb_inventory.py:183 외` | LIVE (전건) |
| §1-6 | BLOCKER | em/en dash 정책 | LIVE (633 파일 / 9,119 회, 델타 없음 = 변화 없음) |
| A2-1 | BLOCKER | `cross_form.py:55-84` | LIVE (5 개 비율 불변식 항등 통과) |
| A3-1 | BLOCKER | `capital/rwa_sa.py:22-46` | LIVE (B+/B/B- 여전히 100 %) |
| A3-2 | BLOCKER | `capital/rwa_irb.py:40-45` | LIVE (LGD 하한 미적용, 주석에도 명시) |
| A3-3 | BLOCKER | `capital/rwa_deep.py:262-289` | LIVE (FIRB LGD 0.45, residential mortgage 잘못 배정) |
| A3-4 | BLOCKER | `capital/op_risk.py:22, 55-67, 83` | LIVE (`_BI_BUCKETS` EUR 원문, `use_ilm=True` 디폴트) |
| A3-5 = A4-1 | BLOCKER | `models/rating.py:41-52` | LIVE (`bisect_left` 경계 off-by-one) |
| A3-12 | BLOCKER | `capital/rwa_sa.py:214-228` | LIVE (`crm_factor` post-mul 로 CRM 엔진 우회) |
| A4-2 | BLOCKER | `governance/audit_chain.py:190-207` | LIVE (`str(NaN) == "nan"` 서명자 통과) |
| A5-1 | BLOCKER | `risk_lib/cli.py:365-393` | LIVE (`_cmd_reproduce` 7 파라미터 재전달 안 함) |
| A5-2 | BLOCKER | `risk_lib/cli.py:70-72, 373` | LIVE (CSV 포트폴리오 파라미터 미기록) |
| A6-1 | BLOCKER | `validation-team-agent/tools/validation_finding.py:55-60` | LIVE (재수정 loop 표현 불가) |
| A6-2 | BLOCKER | `validation-team-agent/tools/conditional_approval.py:215` | LIVE (`in` substring bypass) |
| A6-3 | BLOCKER | `validation-team-agent/tools/pack_diff.py:23-52` | LIVE (skipped=3 > fail=2 로 개선 라벨) |
| A8-2 | BLOCKER | LICENSE 부재 | LIVE (`ls LICENSE* COPYING* COPYRIGHT*` 무결과) |
| A8-3 | BLOCKER | `.github/workflows/` risk_lib CI 커버 | LIVE (validation-team-agent-ci.yml 만 존재) |

**"손이 근처에 있었으나 아무것도 하지 않았다"**: 0 커밋 → 이번 라운드에는 어떤 앵커도 손대지 않았다. 직전 라운드의 사례 (delta 커밋 `00fb2c6` 가 `decompose.py` 를 만졌으면서도 :191 `date.today()` 폴백을 재유입, 43주차 §2-1/§A8-1) 는 그대로 잔존.

## 2. Reviewer #5 우선순위 재정렬 (LIVE 21 → top-5 land-first)

Reviewer #5 가 독립적으로 뽑은 착수 순서. 이론적 심각도가 아니라 **의존성 순서**를 반영한다.

1. **A8-3 CI risk_lib/ 미커버**, 다른 20 개 BLOCKER 가 이 게이트를 세우기 전에는 새로 landing 되어도 감지되지 않는다. 나머지의 발판.
2. **§1-2 / A2-1 cross_form 항등 통과**, 대사 통제가 위약 (placebo) 이라 §1-4/A3 산술 오류를 가리고 있다. False coverage 는 no coverage 보다 나쁘다.
3. **§1-4 limit_engine ↔ limits_deep CRITICAL 반전**, 같은 포트폴리오 로우가 CRO 대시보드에서 정반대 의미로 CRITICAL. 잘못된 방향 조치의 즉각적 운영 리스크.
4. **A3-1 / A3-3 / A3-5 자본·rating 표준 오적용**, B-bucket RW=100 %, rating boundary off-by-one 이 자본 요구를 직접 과소평가. 감독당국이 먼저 보는 Basel III 정의 정합성.
5. **A6-2 conditional_approval substring bypass**, 1 글자 `usage` 문자열이 3선 게이트의 scope 강제를 우회한다. 다른 결함을 잡아야 할 통제 안에서의 거버넌스 실패.

## 3. 리뷰 메타

- 리뷰 도구: 6 개 병렬 서브에이전트 (general-purpose). Reviewer #5 재확인 + Reviewer #1·#2·#3·#4·#6 신규 발굴.
- 커버리지: (5) tracked 21, (1) `ui_studio/` 9 파일 + `ops_pages/` 12 파일 (~19.6 kLOC), (2) `datamodel/` 12 파일 + DQ/repro/archive/close_workflow (~10 kLOC), (3) `alm/` 15 파일 (~9.3 kLOC, kr_irrbb 2,164 LOC 포함), (4) `.claude/workflows/*.js` 6 개 + `.claude/agents/*.md` 55 개 + `.github/workflows/` + `harness/` + `pyproject.toml`, (6) `validation-team-agent/` 103 파일 재딥.
- 자체검증 (2선), 상시 독립검증 (3선): 이 리뷰는 코드 리뷰이며 리스크 산출이 아님. RECALC_SCOPE 대상 아님.

---

# 부록 B: 서브시스템별 44주차 신규 결함 (6-병렬)

**총 신규 결함 52 건** (§B-1 10 · §B-2 10 · §B-3 12 · §B-4 10 · §B-6 10). §B-5 는 tracked 재확인 (본문 §1) 이므로 신규 카운트에 미반영.

## B-1. `risk_lib/ui_studio/` + `risk_lib/ops_pages/` (10 신규 결함)

| # | 심각도 | 파일:줄 | 요약 |
|---|---|---|---|
| B1-1 | MAJOR | `ops_pages/governance.py:498-503` | `page_data_quality` 대사표가 `_won(c) if abs(c) > 1 else f"{c:.6g}"` 로 포맷. LCR (1.42) · NSFR (1.10) 은 두 셀 모두 `_won(1.x)` → "1원", CRO 대사 라인이 "1원 / 1원 / 0원". |
| B1-2 | MAJOR | `ops_pages/nonfinancial.py:246-250` | `page_sensitivity` 도 동형. `metric="LCR"` (base 1.35 → shocked 1.42) 이 `_won(...)` → "1원" 으로 렌더. 1-factor 민감도 그리드 전 행 손실. |
| B1-3 | MAJOR | `ops_pages/credit.py:1010-1015` | `page_cecl_ifrs9` IFRS9→CECL 브리지가 `attribution_waterfall([...], [bridge.gap*0.85, bridge.gap*0.15])` 로 하드코딩 85/15. `compute_cecl`/`reconcile_ifrs9_cecl` 결과 무시. **CRO 데크 워터폴 귀속이 계산이 아니라 임의값**. |
| B1-4 | MAJOR | `ops_pages/governance.py:164-215` | `page_explainability` 가 CET1 변동 내러티브 **전체를 조작**. `prev_cet1 = base_cet1 - 0.003` (30bp 임의), `driver_decomposition(..., {"신용 RWA 증감": 0.0015, ...})` 리터럴, `narrate_capital_change(rwa_change_pct=0.02, capital_change_pct=0.025)` 하드코딩. 파이프라인과 무관하지만 실 분석과 구별 불가. |
| B1-5 | MAJOR | `ops_pages/core_credit.py:658-673` | `_page_limits` 가 `top_lim = limits.head(15)` 를 "한도 사용률 상위 15" 라벨로 렌더. `LimitEngine.report()` 는 삽입 순서 · groupby 순서 (미정렬). 15 개 초과 시 실제 최고 BREACH 가 알파벳 순 앞 WARN 에 밀려 조용히 탈락. |
| B1-6 | MAJOR | `ops_pages/market_trading.py:601-603` | `page_intraday` 라인 차트가 `reference_value=normal.ticks["var"].iloc[0] * 2 / 1e9, reference_label="VaR 한도"`. **승인된 한도가 아니라 개장 tick VaR × 2**. 이후 모든 intraday 브리치·정상 판정이 조작된 임계값 대비. |
| B1-7 | MAJOR | `ui_studio/app.py:566-569` | `_kpis` 의 "고정이하여신비율" = `aq[classification ∈ ("고정","회수의문","추정손실")].balance.sum() / aq.balance.sum()`. 한글 리터럴 튜플 하드코딩, fallback 없음. 상류 스키마가 영문 (`substandard/doubtful/loss`) 이나 "요주의" 추가로 드리프트하면 NPL=0.00 % 로 조용히 뒤집힘. |
| B1-8 | MAJOR | `ops_pages/market_trading.py:755-761` | `page_liquidity_stress` "Base LCR" KPI 가 `ls.loc[0, 'lcr']` (positional). 인접 "Combined severe LCR" KPI 는 `ls['scenario'] == 'combined_severe'` 명시 필터. `run_liquidity_stress` 에 `scenarios=` 오버라이드 시 삽입 순서가 다르면 stressed 시나리오 값이 "Base LCR" 로 표시. |
| B1-9 | MINOR | `ops_pages/capital_stress.py:37-42` | `page_capital_stack` CET1 워터폴 마지막 바 = `cet1.net - cet1_df["amount"].sum() + cet1.net` (= 2·net - Σamounts). 항등은 아이템 합이 net 일 때만; 반올림·누락 아이템 드리프트가 잔차로 표시되지 않고 최종 바에 두 배로 얹힘. |
| B1-10 | MINOR | `ops_pages/capital_stress.py:815-823` | `page_capital_simulation` fan_chart 가 `series.get("baseline", series[list(series)[0]])` 폴백. 시나리오 키 부재 시 첫 시나리오를 조용히 대체, fan 차트 median/envelope 이 같은 시계열 세 벌로 조립되어도 화면에 표시 없음. |

**서브시스템 총평**: 프레젠테이션 층은 표면적으로 넓지만 (~19.6 kLOC / 21 파일) 대부분 이미 계산된 `PipelineResult` 필드에 대한 템플레이팅이므로 대부분 상류 수치만큼만 안전하다. 반복되는 결함 클래스는 (a) 임계값 휴리스틱 `abs(x) > 1` 로 단위 포맷을 선택하는 `_won`/`_pct` (B1-1/2), (b) 안정성이 명목적일 뿐인 DataFrame 에 대한 positional `.loc[0/1/2]` (B1-8), (c) `sort_values` 없이 "상위 N" 라벨을 붙인 `.head(N)` (B1-5), 그리고 가장 우려되는 (d) `page_explainability`·`page_cecl_ifrs9`·`page_intraday` 가 **조작된 귀속·기준선·참조선**을 실 수치와 같은 크롬으로 표시 (B1-3/4/6) 하는 문제. `ui_studio/` 자체는 방어적으로 작성됨 (Studio 조립이 조용한 폴백 거부, `nl_query`/`layout` 이 field policy 로 게이트, `req_trace` 가 미매핑 요건을 숨기지 않음). 리스크는 `ops_pages/` 파일에 있다.

## B-2. `risk_lib/datamodel/` + DQ / repro / archive / close_workflow (10 신규 결함)

| # | 심각도 | 파일:줄 | 요약 |
|---|---|---|---|
| B2-1 | **BLOCKER** | `risk_lib/data_quality.py:143-151, 165-173, 175-184` | `reconcile()` 이 `capital.cet1/bis.rwa` 를 `bis.cet1_ratio` 와, `lcr.hqla_total/lcr.net_outflow` 를 `lcr.lcr` 와, `nsfr.asf_total/nsfr.rsf_total` 를 `nsfr.nsfr` 와 대조. 그러나 `capital/bis.py:89`, `alm/lcr.py:449`, `alm/nsfr.py:235` 은 각 우변을 **좌변 비율로 정의**. CRO 헤드라인 세 대사가 항등적으로 항상 PASS. 조작된 `hqla_total` 도 통과. |
| B2-2 | **BLOCKER** | `risk_lib/datamodel/catalog.py:1829-1917` | `rdm_fund_master`/`rdm_fund_holding`/`rdm_fund_mandate`/`rwa_fund_result`/`rdm_derivative_*`/`rdm_netting_set` 스펙이 `asof` 를 `"string"` 으로 선언. `spec.py:171-175` date-format 체크 우회, `ddl()` 은 `VARCHAR(64)` DATE 대신 방출, `rdm_snapshot.asof` (date) 와의 조인이 사전식. `"2026/6/30"` 이나 `"asof"` 도 검증 통과 후 `rwa_fund_result` → RWA 총계. |
| B2-3 | MAJOR | `risk_lib/repro.py:75-82` | `_git_commit` 이 `git rev-parse HEAD` 만 하고 `git status --porcelain` 을 안 봄. `archive.py:_git_revision:86-88` 은 그 패턴이 있음을 증명. 미커밋 로컬 편집 상태에서 실행하면 `code.git_commit=<clean-SHA>` 를 `RunManifest` 에 기록, `diff_manifests` 가 코드 델타 없다고 리턴. **재현 증명 실패: 두 소스 트리가 해시 매치**. |
| B2-4 | MAJOR | `risk_lib/archive.py:81-90` | `_git_revision` 이 `cwd=` 없이 subprocess 호출. `repro.py:_git_commit:78` 은 `cwd=Path(__file__).parent` 를 씀. `/tmp` 나 다른 git 저장소에서 `archive()` 를 부르면 잘못된 (또는 `(unknown)`) revision 을 `VersionInfo.git_revision` 에 기록. `scan()` 이 `이력.csv` 로 오귀속 재생. 지문 체크는 request 파일의 `headline_digest` 를 그대로 복사하기 때문에 살아남음. |
| B2-5 | MAJOR | `risk_lib/datamodel/materialize_detail.py:186-207` | `rdm_reconciliation` 세 행이 대수적 항등. `ead_rwa` (:187) 는 `rwa_result` 부재 시 `ead_src` 로 폴백 (0 gap → PASS), `bal_aq` (:189) 는 `p["balance"]` 의 partition (합 항상 매치), `len(base["rdm_obligor"])` = `p["obligor_id"].nunique()` (`decompose.py:49` 이 `drop_duplicates("obligor_id")` 로 생성). **"집계 대사" 증빙이 허구**. |
| B2-6 | MAJOR | `risk_lib/datamodel/materialize_detail.py:157-163` | `rdm_source_contract` 이 `expected_rows=int(len(df)), actual_rows=int(len(df)), expected_sum=total, actual_sum=total` 을 같은 `df`/`total` 에서 단일 dict 로 기록, `status="PASS"` 하드코딩. **`decompose.py:156-158` 이 없애려던 "PASS vs 미점검" 모호성이 재출현**. 잘린 소스 프레임도 PASS. |
| B2-7 | MAJOR | `risk_lib/ui_studio/studio.py:186-215` | `rdm_dq_result` 를 :187-189 에서 materialize (forms/UIX/gov/aig 이전). 이후 추가되는 `opr_close_task`, `opr_close_gate`, `gov_audit_chain`, `gov_rbac`, `gov_retention`, `gov_unified_run`, `aig_agent_trace`, form frames 은 절대 `validate_all()` 을 거치지 않음. `opr_close_gate` PK 중복이나 `gov_audit_chain` `not_null` 위반이 DQ 원장에 나타나지 않으면서 CL-02 은 완료로 표시. |
| B2-8 | MAJOR | `risk_lib/datamodel/catalog.py:1855-1917` | `RDM_FUND_HOLDING.fund_id`, `RDM_FUND_MANDATE.fund_id`, `RWA_FUND_RESULT.fund_id`, `RDM_DERIVATIVE_UNDERLYING.trade_id`, `RDM_DERIVATIVE_MASTER.netting_set_id` 가 모두 부모 참조 컬럼인데 `foreign_keys=` 미선언. `check_refs` 가 `fund_id` 가 `rdm_fund_master` 에 없는 `rwa_fund_result` 행을 감지 못함. LTA 집계가 조용히 1250 % 폴백. |
| B2-9 | MAJOR | `risk_lib/datamodel/catalog.py:2345-2363` | `MACRO_SCENARIO_LINK` PK `("scenario","indicator_id")` 로 `latest`/`scenario_value` 를 `macro_indicator` 에서 복사하지만 `foreign_keys=(FK(("indicator_id",), "macro_indicator", ("indicator_id",)),)` 미선언. 지표 삭제·재키잉 시 `latest` 가 존재하지 않는 계열을 가리키고 `check_refs` 는 침묵. **시나리오 provenance 가 source-of-truth 에 바인딩 안 됨**. |
| B2-10 | MAJOR | `risk_lib/datamodel/catalog.py:52-85, 185-218` | `EXPOSURE.account_code`/`product_code` 가 `nullable=False` 이며 "rdm_account_master 참조" 노트가 있지만 `foreign_keys=` 에 `obligor_id` 만 등록. `code_scope.EXPOSURE_CODES:69-75` 드리프트 (예: 새 asset_class 가 `ACCOUNTS` 에 없는 account 로 매핑) 시 `decompose.py:80-87` 이 고아 `account_code` 를 채우고 FK 체크 미발동. **계정 레벨 집계 조용히 이중 계산**. |

**서브시스템 총평**: 데이터모델 스파인에는 방어 심층 설계가 있음 (`spec.py:187-190` 의 PASS-record 시맨틱, `lineage.py:692-746` 의 ORPHAN_REGISTRY fail-closed, `__post_init__` 로 fail-fast 하는 PK/FK 프리미티브). 그러나 `catalog.py:1829-2363` 의 fund/derivative/macro 서브트리는 이 통제 없이 병합, `data_quality.py` 와 `materialize_detail.py` 는 양쪽을 같은 식에서 뽑는 대사 안티패턴을 드러냄. `close_workflow._all_predecessors` 는 올바름 (transitive closure with seen-set); 그러나 studio 조립 순서가 그것을 무력화, CL-02 은 CL-08 이 게이트해야 할 바로 그 테이블들이 채워지기 전에 완료 판정. `repro.py` 와 `archive.py` 는 `_git_*` 시맨틱이 갈림 (한 쪽은 dirty-tree 감지, 다른 쪽은 `cwd=`), 같은 run 의 manifest 와 archive VersionInfo 가 어떤 코드가 산출했는지 서로 다르게 말함. 108-테이블 `catalog.py` 를 도메인별 모듈로 추출 · TableSpec 단위 테스트가 시급.

## B-3. `risk_lib/alm/` (12 신규 결함)

| # | 심각도 | 파일:줄 | 요약 |
|---|---|---|---|
| B3-1 | **BLOCKER** | `alm/lcr.py:352-354` | `lcr_balances_from_ledgers` 가 `product_code` 가 `funding_category_of` 에 없는 부채 계약을 조용히 drop (`if cat is None: continue`). 30-day outflow 가 사라지면서 **LCR 비율이 경고 · 원장 로우 없이 팽창**. |
| B3-2 | MAJOR | `alm/kr_irrbb.py:1863-1870` | `anchor = reset if not NaN else mat` 가 `rate_type` 무관하게 `next_reset_date` 선택. 채워진 (stale · 시스템 디폴트) `next_reset_date` 를 가진 고정금리 5년 대출이 만기 대신 리셋 버킷으로 슬로팅, `kr_irrbb_gap` 의 장기 포지션 과소. |
| B3-3 | MAJOR | `alm/nii.py:279-284` | 시나리오 루프 안에서 한 leg 의 `shocked[(ccy, sc)]` 누락이 `missing = True; break` 발동, 외곽 `continue` 가 **시나리오 전체를 drop**. 단일 미매핑 외화 leg 이 KRW-지배 ΔNII 를 0 으로 만들고 (ccy, sc) 경고 한 번만 방출. |
| B3-4 | MAJOR | `alm/liquidity.py:348-357` | `used = p[p["category"].astype(str).isin(bal)]`, `bal` 에는 있지만 시나리오의 `stress_param` 에 없는 balance category 는 조용히 drop. NA-rate category 만 경고 발동, 미매핑 `wholesale_fi_lt6m` 라인이 사라지고 net outflow 과소 합산. |
| B3-5 | MAJOR | `alm/behaviour.py:190,225-227` | `apply_prepayment`/`apply_early_redemption` 이자 = `bal * annual_rate * tau` where `tau = ins.t_years - prev_t` (365.25 기준). `schedule.py:210` 은 `year_fraction(prev_date, d, day_count)`. `30/360, ACT/360, ACT/ACT_ISDA` 에서 같은 계약이 contract CF vs behavioural CF 다른 이자, **cross-basis 대사 붕괴**. |
| B3-6 | MAJOR | `alm/contracts.py:190` | `next_reset_date = asof + (u_reset * 0.25 + 1/365.25) 년` 은 항상 ≤91 일. `LN_RETAIL`, `LN_MTG_FLT` product_terms 는 `reset_freq_months=6`. `liquidity._reset_window` 는 6개월 사이클, `cashflow.py` 는 ≤91일 슬로팅, 같은 합성 계약에서 두 경로가 불일치. |
| B3-7 | MAJOR | `alm/kr_irrbb.py:1878-1892` | `core_amt = notional * ratio` 가 집계 `core_ratio = core_amount / latest_month_avg_balance` 를 계약별로 적용. 시점 Σ 계약 notional ≠ latest_month_avg_balance 이 일반적, Σ(core_amt) ≠ 실 `core_amount`. 8 버킷 1/8 선형 분산이 과소·과대 배분. |
| B3-8 | MAJOR | `alm/irrbb.py:702` | `source = {sc: shk.shock_source for (_ccy, sc), shk in shocked.items()}`, 같은 `sc` 키 중복이 조용히 덮어씀. 두 통화가 같은 시나리오에 다른 `shock_source` 문자열을 담으면 (prox 제거 후 잔재 버그) 마지막 iterated 값만 `alm_irrbb_result.shock_source` 에 살아남음. |
| B3-9 | MAJOR | `alm/irrbb.py:585-597, 534` | `_aggregate_across_currencies` :534 에서 `opt = per_ccy["auto_option_risk"].fillna(0.0)`. `kr_auto_option_risk` 의 `(ccy, scenario)` 누락이 0 으로 채워짐, :593 warn 은 `gap[:5]` 로 truncate. 옵션 원장 로우 없는 통화가 "옵션 손실 없음" 으로 처리, `delta_eve` 가 less-negative 로 편향. |
| B3-10 | MAJOR | `alm/nii.py:243-244` | `nii_base += sign * bal * rate * H` 가 floating 계약도 12개월 지평 전체에 coupon rate 사용, 기준 시나리오 reset 재투자 leg 미추가. :286 `delta` 는 `dr * remaining` 만 더함. pre-reset leg 의 `bal*rate` 가 base 커브의 post-reset rate 와 다르면 **`nii_base` 절대값 오표기** (Δ 는 여전히 정확). |
| B3-11 | MINOR | `alm/irrbb.py:620-621` | `np.where(g["delta_nii"].notna(), MARGIN_EVE_AND_NII, MARGIN_EVE_ONLY)` 가 같은 `basis` 안에서 두 라벨 (parallel 시나리오는 하나, rotation 은 다른 하나). 프레임워크 레벨 라벨이 시나리오별 라벨이 되어 `margin_treatment` 조인이 brittle. |
| B3-12 | MINOR | `alm/curves.py:451-453` | `Curve.rate(0)` 이 `self.zero_rates[0]` (최단 tenor 노드, 예 3M/6M) 리턴. `nii.py:285` 의 NMD/administered leg 가 `rate(0.0)` 을 β·Δr 로 호출, non-zero tenor 로 캘리브레이션된 rate 를 받음. 문서상 "extrapolation 아님" 이지만 short-end shock 의 소량 mis-scale. |

**서브시스템 총평**: ALM 서브시스템은 규제 코드치고 이례적으로 잘 구조화됨 (파라미터가 원장에 있음, 엔진이 프레임 위 순수함수, CBCS d368/d578/[별표 9-1]/EBA GL 2022-14 인용 인라인 앵커). 검증한 올바른 설계 불변식: LCR `apply_hqla_caps` (BCBS d238 Annex 1, k15/k40 공식 `lcr.py:260-269`), 30/360 daycount D1/D2 순서 (`daycount.py:38-46`), ACT/ACT_ISDA 연말 분할 (`daycount.py:56-66`), 통화 loss-only 집계와 `auto_option_risk` 부호 (`irrbb.py:534-542`), Bachelier put/call 대칭 (`kr_irrbb.py:993-1018`), post-shock floor (`curves.py:621-623`). 주된 시스템 갭은 **엔진 경계의 silent-drop 패턴** (findings 1, 3, 4, 8, 9): 저장소 설계 원칙이 "빈 것 ≠ 0" 인데 몇몇 콜사이트가 여전히 `continue`/`fillna(0)`/dict-collide 로 empty 를 `ParamWarning` 으로 표면화하지 않음. kr_irrbb 별표9의1_2026 vs d368/d578 분리는 깔끔 (`framework_version` 이 전파). 테스트 디렉터리 (43주차 §A7-5) 는 이들 경로를 여전히 existence-only assertion 으로 exercise 하므로 위 silent-drop 결함이 데이터 드리프트에도 CI 실패 가능성 낮음.

## B-4. 메타 · 하네스 · 워크플로 · CI (10 신규 결함)

| # | 심각도 | 파일:줄 | 요약 |
|---|---|---|---|
| B4-1 | **BLOCKER** | `.claude/workflows/legal-kb-update.js:63,74` | `legal-statute-researcher` / `legal-case-researcher` 에게 "Edit 로 수정" 을 지시하고 `UPDATE_SCHEMA` 에 `changes_applied` 를 요구. 그러나 두 agent 의 frontmatter (`.claude/agents/*.md:4`) 는 `Read, Grep, Glob, WebSearch, WebFetch` 만 허용. **KB 업데이트가 조용히 no-op 하거나 agent 가 `changes_applied` 값을 환각**. 콜러는 "갱신 완료" 로 표시. |
| B4-2 | MAJOR | `.claude/workflows/contract-review.js:117-131` | `legal-red-team` verdict 가 `{PASS, PASS_WITH_FIXES, FAIL}` 로 캡처되지만 게이트로 사용 안 됨. `FAIL` 조차 `legal-writer` (:123) 를 통과, 보고서가 `reports/legal/` 에 기록. skill 은 "반대검증 게이트" 로 마케팅되지만 구현은 없음. |
| B4-3 | MAJOR | `.claude/workflows/legal-consult.js:121-129` | red-team FAIL 시 one-shot revision. 재작성도 실패하면 여전히 `legal-writer` (:131) 를 재체크 없이 호출. `legal-team` SKILL 은 "PASS 까지 반복" 이지만 구현은 단일 재작성으로 상한. |
| B4-4 | MAJOR | `.claude/agents/{rp-*, analytics-engineer, data-*-engineer, dimensional-*-modeler, fact-data-modeler, pipeline-ops-engineer, spark-engineer, streaming-engineer}.md` (17 파일) | `tools:` frontmatter 없음, 부모 툴셋 (Bash, Write, Edit, WebFetch, Agent) 상속. `rp-lead-professor` ("판정"), `rp-peer-review-team` ("심사보고서 작성") 등 명시 범위와 무관한 툴 과부여. |
| B4-5 | MAJOR | `.claude/settings.json:2-12` | 3rd-party 플러그인 `codex@openai-codex` 를 `openai/codex-plugin-cc` 에서 version/tag/SHA pin 없이 활성화. 매 세션마다 upstream HEAD 를 pull. 동반 `permissions` 블록 없음. **공급망 리스크**. |
| B4-6 | MAJOR | `.gitignore:1-27` | `.env`, `*.env*`, `secrets/`, `.claude/settings.local.json` 항목 없음. 마지막은 Claude Code 의 per-user 허용 목록 · 때때로 API 키 포함, 실수로 staging 시 직접 커밋. |
| B4-7 | MAJOR | `pyproject.toml:6-11` | 모든 런타임 deps 가 lower bound 만 (`numpy>=1.24`, `pandas>=2.0`, ...), upper pin 없음, lockfile 없음, top-level CI 없음 (유일한 CI 는 `validation-team-agent/**` scope). Fresh `pip install .` 이 오늘 numpy 2.x 로 해결되고 조용히 부러질 수 있음. |
| B4-8 | MAJOR | `.claude/workflows/risk-premium-lab.js:186-196` | `positive = reviews.filter(r => r.verdict === 'ACCEPT' \|\| 'MINOR_REVISION').length; if (positive >= 2) accepted = true`. 3 개 peer-review 중 하나가 schema 실패로 drop 되면 나머지 2 개 ACCEPT/MINOR 로도 통과 트리거. **누락된 리뷰어의 암묵적 veto 가 조용히 consent 로 카운트** (축소된 분모의 majority). |
| B4-9 | MEDIUM | `.claude/workflows/risk-premium-lab.js:22-24` | `const maxValidationRounds = (args && args.max_validation_rounds) \|\| 2`. 명시 `0` (검증 스킵 fast trial) 이 `2` 로 강제 재변환. `??` 여야 함. |
| B4-10 | MEDIUM | `.github/workflows/validation-team-agent-ci.yml:4-6,47` | `on: push: branches: ["**"]` + `fetch-depth: 0` + 2-버전 Python matrix 로 모든 브랜치의 모든 푸시에서 full CI 실행 (throwaway/experimental 포함). `push` 를 main/release 로 좁히고 나머지는 `pull_request` 에 의존해야. |

**서브시스템 총평**: 워크플로 스크립트는 내부적으로 정합 (`agentType` 문자열이 실존 agent 파일 해결, await 누락 없음), 두 skill (`independent-validation`, `legal-team`) 은 잘 작성된 산문. **시스템적 약점은 층 사이**: 워크플로가 red-team 을 "게이트" 로 가정하지만 실제로는 `risk-orchestrator.md` 만 이를 강제, 4 개 legal 워크플로와 `risk-premium-lab.js` 는 verdict 를 advisory 메타데이터로 취급 (B4-2, B4-3, B4-8). 툴 권한 스토리는 양방향 모두 비일관: 17 개 agent 가 누락으로 전부 부여 (B4-4), 두 agent 가 실행 불가능한 명시 `Edit` 지시 (B4-1). 저장소 어디에도 write 시 훅이 없고 `.claude/hooks/` 도 없음, 가이드라인 강제 (dash, wall-clock, secret-in-diff) 가 하네스 층에서 기계적으로 저지되지 않음, 부모 리뷰의 `+577` dash 회귀와 일관. 설정 위생 얇음: `settings.json` 13 줄에 unpinned 3rd-party 플러그인 · permission 블록 없음 (B4-5), `.gitignore` 표준 Claude/secret 패턴 누락 (B4-6), `pyproject.toml` upper pin 없음 · top-level CI 없음 (B4-7). 유일한 CI 는 `validation-team-agent/` 에 대해 철저하지만 over-trigger (B4-10).

## B-5. Tracked BLOCKER 재확인 (Reviewer #5)

본문 §1 참조. 21 건 중 LIVE 20, PARTIAL 1, FIXED 0, ANCHOR-DRIFTED 0.

## B-6. `validation-team-agent/` 3선 (10 신규 결함)

| # | 심각도 | 파일:줄 | 요약 |
|---|---|---|---|
| B6-1 | **BLOCKER** | `validation-team-agent/tools/independent_recalc.py:140-153` | `RECALCULATORS` 가 6 개 정의; `risk_lib.validation.independent.RECALC_SCOPE` 21 키와 교집합은 **4 개** (lcr, nsfr, cet1_ratio, leverage_ratio). 17/21 (81 %) 헤드라인 (rwa_final_total, ecl_total, ecl_weighted_total, irrbb_worst_pct_tier1, kr_irrbb_table6_*, lgd_backtest_*, ccf_realised_mean, etc.) 이 독립 재계산 없음. **43주차 기준선 (6/21) 에서 오히려 감소**. |
| B6-2 | **BLOCKER** | `validation-team-agent/tools/validation_finding.py:269` | `close_finding` 가드 `if enforce_sod and not sod["passed"] and sod["violations"]` 가 `violations == []` 시 short-circuit. `check_sod` 결과 `NOT_EVALUATED` (모든 actor 미기록) 는 `passed=False` + 빈 violations, finding 이 `sod_status="NOT_EVALUATED"` 로 조용히 종료. **sod_guard docstring 이 절대 pass 로 취급 금지라 명시한 케이스**. |
| B6-3 | **BLOCKER** | `validation-team-agent/tools/adversarial_review.py:129-132` | `_auto_verdict(kind="golden")` 이 `RECALCULATORS` 에 없는 타깃에 대해 `None` 리턴. B6-1 과 결합 시 골든 회귀 챌린지가 21 개 RECALC_SCOPE 타깃 중 17 개에 대해 `VERDICT_UNANSWERED` 로 변환. **적대적 프로토콜이 헤드라인 대다수에서 최강 자동 체크를 조용히 drop**. |
| B6-4 | **BLOCKER** | `validation-team-agent/docs/independent_validation/RUN-*.response.json` (전건) | 응답 envelope 이 HMAC/signature/publisher key 없는 plain JSON. `validated_by` 필드가 free text, 파일을 실제 3선 agent 에 바인딩하는 것 없음, risk_lib 측 `check_gate` 는 `run_id`/`request_id`/`recalc_matches` 키만 체크. `docs/independent_validation/` FS 접근 있는 writer 는 request 파일에서 도출 가능한 값으로 "적합" 응답 작성 가능. |
| B6-5 | MAJOR | `validation-team-agent/tools/independent_recalc.py:196-233` | `recalculate()` 가 caller 공급 `inputs_operational` 을 accept, 검증 중인 run 에 대한 pinning 없음, 정본 위치에서 같은 `asof`/`seed` 읽기 없음, 지문 비교 없음. **잘못 공급된 vintage 로 recalc 이 주장 값과 "일치", 파이프라인이 드리프트 감지 못함**. |
| B6-6 | MAJOR | `validation-team-agent/middleware/schema_guard.py:49` | `pd.to_datetime(series.dropna().head(20), errors="raise")` 로 date-dtype 검증에 20 행만 샘플. 21+ 행의 malformed date 는 valid `date` 로 통과, 하류 date-coverage 체크가 오염 문자열을 조용히 해석. **스키마 fail-open**. |
| B6-7 | MAJOR | `validation-team-agent/tools/pack_archive.py:31-33, 100-101, 121-122` | `_default_label()` 이 `%Y%m%dT%H%M%SZ` (초 정밀도) 리턴. 같은 초 안의 두 concurrent `add()` 가 `FileExistsError` 로 하나 손실, entries-sort tiebreak 도 `stored_at_utc` (초 정밀도) 라 `_prune` FIFO 비결정론. `keep=N` 아래 잘못된 pack 삭제 가능. |
| B6-8 | MAJOR | `validation-team-agent/tools/validation_finding.py:148-152` | `_next_id` 가 그 날의 기존 `opened` 이벤트 카운트로 ID 도출. 두 concurrent `open_finding` 이 동일 `VF-YYYYMMDD-NNNN` 생성, `derive()` :103 이 두 번째 `opened` 시 `state[fid] = {...}` 무조건 재초기화, **첫 finding 의 전체 이력을 조용히 덮어씀**. |
| B6-9 | MINOR | `.github/workflows/validation-team-agent-ci.yml:79` | mypy 가 `src/vta/core/` 와 `src/vta/policies/` 만 실행. `tools/` (independent_recalc, adversarial_review, pack_verify, validation_finding, pack_archive) 와 `middleware/` 제외. **실제 게이트/재계산 코드의 type-drift 가 CI 실패 안 함**. |
| B6-10 | MINOR | `validation-team-agent/middleware/permission_guard.py:73-79` | Malformed `harness/permission_matrix.json` (`OSError | ValueError | KeyError`) 에 loader 가 조용히 `_FALLBACK_PATTERNS` 리턴. JSON typo 로 tightened matrix 가 로그·경고·exit code 없이 약한 디폴트로 회귀. **"패턴 추가하는" operator 가 실수로 전부 제거 가능**. |

**서브시스템 총평**: validation-team-agent 는 잘 문서화되고 subagent 분류법 (orchestrator + 6 스페셜리스트) 이 깔끔. 그러나 **독립성 계약이 대부분 열망적**: `RECALCULATORS` 가 RECALC_SCOPE 21 키 중 4 개만 커버, 부족분이 증가 (2선은 헤드라인 추가, 3선의 계산기 표는 안 움직임), `check_gate` 가 사실상 "3선 agent 가 `true` 라고 말했다" 를 강제하지 실제로 "코드가 재계산하고 매치했다" 는 아님. 응답 envelope 이 validating team 에 대한 암호학적 결속 없음, 전체 fail-closed 게이트가 파일시스템 write 신뢰에 의존. Fail-closed 정책이 세 seam 에서 무너짐: `close_finding` 의 NOT_EVALUATED SoD 허용 (B6-2), `_auto_verdict` 의 uncovered target 에 대한 None 리턴 (B6-3), `permission_guard` 의 parse error 시 약한 디폴트 폴백 (B6-10). 결정론/동시성 위생 얼룩덜룩 (`pack_archive` 초 정밀도 FIFO, `_next_id` 경쟁, `runner_result.py:121` / `run_audit.py:141` 의 temp-dir 누수), CI mypy 범위가 가장 결과-무거운 모듈을 정확히 제외. 구조적 강점 (Pydantic v2 dataclass, append-only Finding 원장, adversarial-protocol JSON, memory 원장의 상호 무결성 체크) 은 실제이며 43주차 대비 재료 상 개선이나, recalc-coverage 회귀 (단일 최대 헤드라인 결함) 를 상쇄 못함.

## 부록 B 총평

52 신규 결함 중:

- **BLOCKER 8 건**: B2-1 (data_quality 항등 대사), B2-2 (fund/derivative asof=string), B3-1 (LCR 부채 silent-drop), B4-1 (legal-kb-update 에이전트 Edit 권한 없음), B6-1 (RECALCULATORS 4/21 회귀), B6-2 (close_finding NOT_EVALUATED bypass), B6-3 (_auto_verdict None 리턴), B6-4 (response envelope 서명 없음).
- **MAJOR 35 건**: 프레젠테이션 층의 조작된 참조선/기준선 (B1-3/4/6), fund/derivative FK 누락 (B2-8/9/10), materialize_detail 항등 대사 (B2-5/6), studio 조립 순서 (B2-7), ALM 엔진 경계 silent-drop (B3-1..9), harness 툴 권한 (B4-4), 공급망 pin 없음 (B4-5/7), red-team 게이트 미강제 (B4-2/3/8), 3선 recalc pinning 없음 (B6-5), 스키마 fail-open (B6-6), pack_archive 경쟁 조건 (B6-7/8).
- **MINOR/MEDIUM 9 건**: 문서·라벨 드리프트, CI 트리거 과광범, unit heuristic 폴백.

**가장 놀라운 결함**: **B6-1 3선 RECALCULATORS 4/21 회귀**. 43주차가 6/21 (29 %) 로 지적했는데 44주차 정밀 검증에서 실제 교집합은 4/21 (19 %) 로 확인. 3주째 progress 없음, warden 개입 조건 성숙. Reviewer #5 top-5 land-first list 에는 이 결함이 없지만, `check_gate` 의 fail-closed 계약이 사실상 `true` 문자열 신뢰로 강등된다는 뜻이라 §1-3 PARTIAL 판정을 사실상 LIVE 에 가깝게 만듦.

**두 번째로 놀라운 것**: **B2-1 + B2-5 + B2-6 + B6-3 + 43주차 §A2-1** = 저장소의 **네 대사 층 (DQ 원장 · rdm reconciliation · cross-form · 3선 golden verdict) 이 모두 falsifiable 하지 않음**. 통과 카운트가 커버리지처럼 보이지만 어느 것도 실 산술 오류를 잡지 못함.

**세 번째**: **B4-1 legal-kb-update BLOCKER**. 워크플로가 agent 에게 도구가 없는 작업을 지시. 대변인의 산문은 "갱신 완료" 로 도착. 이 결함 클래스 (워크플로↔에이전트 계약 미검증) 가 다른 워크플로 스크립트에도 있을 가능성 높음.

## 리뷰 메타 (부록 B)

- 리뷰 도구: 6 개 병렬 서브에이전트 (general-purpose). Reviewer #1 (~354 s, 315k tok), #2 (~454 s, 185k tok), #3 (~856 s, 308k tok), #4 (~310 s, 123k tok), #5 (~151 s, 77k tok), #6 (~326 s, 190k tok). 합 약 1.20 M 토큰, wall 최대 856 s.
- 커버리지: (1) `ui_studio/` 9 + `ops_pages/` 12 = 21 파일 · ~19.6 kLOC, (2) `datamodel/` 12 + DQ/repro/archive/close_workflow = ~10 kLOC, (3) `alm/` 15 파일 · ~9.3 kLOC (kr_irrbb 2,164 LOC 포함), (4) `.claude/workflows/` 6 개 · `.claude/agents/` 55 개 · `.github/workflows/` · `harness/` · `pyproject.toml` · `.gitignore`, (5) tracked 21 BLOCKER 재확인, (6) `validation-team-agent/` 103 파일 재딥.
- 42주차 (PR #67) 60+, 43주차 99, 44주차 52 신규. **누계 210+ MAJOR-이상 결함, 순 감소 없음**. 코드 델타 없이도 리뷰가 계속 새 결함을 발굴 = 저장소 결함 밀도 여전히 감소하지 않음.

---
_Generated by [Claude Code](https://claude.ai/code)_
