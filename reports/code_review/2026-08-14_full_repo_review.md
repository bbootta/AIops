# 저장소 전수 코드 리뷰 (2026-08-14, 43주차)

**대상**: `bbootta/AIops` 전 저장소, base `origin/main` = `00fb2c6`
**직전 리뷰**: PR #67 (2026-08-12, 42주차), 리뷰 파일 `reports/code_review/2026-08-12_full_repo_review.md`
**델타 창**: 2026-08-12 21:20 → 2026-08-14 (약 43 시간), 8 커밋, +3,428 / -264
**리뷰 방식**: 2 개 서브에이전트 병렬. (A) PR #67 tracked BLOCKER 6 건 재점검, (B) 8 커밋 델타 신규 리뷰

## 0. 총평 (한 문장)

델타 8 커밋은 **마감 워크플로 정합성** 한 축에 집중되어 실제로 그 축을 고쳤다 (DQ 통과 이력·CL-04 증빙원장·이행폐포 게이트). 그러나 PR #67 이 지적한 6 개 BLOCKER 중 5 개가 그대로 살아 있고, em/en dash 는 오히려 늘었다 (**9,076 → 9,653, +577 회 · 617 → 633 파일, +16**). 델타의 손이 좋으면서도 그 손이 42주차 BLOCKER 를 향하지 않았다.

| 층위 | 42주차 | 43주차 | 변화 |
|---|---|---|---|
| BLOCKER (§1) | 6 건 | 5 건 LIVE + 1 건 PARTIAL | -0.5 |
| MAJOR (§2) | 60+ 건 (누계) | 65+ 건 (신규 6 건 반영) | +6 신규 |
| 정책 위반 em/en dash | 9,076 / 617 파일 | **9,653 / 633 파일** | +577 / +16 (**회귀**) |
| 벽시계 파일 (`date.today`/`datetime.now`) | 20+ | 25 파일 / 32 회 | 실질 무변동 |
| 델타 신규 결함 | , | P1 ×2, P2 ×2, P3 ×2 (총 6) | 신규 |

**최대 위험**: em/en dash 정책 위반이 사흘 만에 **+577** 늘어난 사실. 리뷰가 매주 지적하는 항목이 매주 늘어난다면 리뷰가 통제 기능을 잃은 것이다. 사전 커밋 훅 (PR #67 §5-1) 이 도입되지 않은 근본 원인이 노출되었다.

## 1. 즉시 조치 (BLOCKER · Tracked 재점검)

PR #67 §1 의 6 개 BLOCKER 를 델타 이후 상태로 다시 검증한다. 자세한 실패 시나리오는 PR #67 본문 참조.

### 1-1. 재현성 (벽시계 리크) , **LIVE (19 지점 중 18 지점)**

- `risk_lib/pipeline.py:1502` 여전히 `asof = date.today()`. 델타는 :1500~:1503 에 `asof_source = "wall_clock"` 원장 태그를 추가했지만 **폴백 값 자체는 그대로**. 하류 매니페스트·zip sha256 재현성 미회복.
- **FIXED (1 지점)**: `risk_lib/cli.py` , 앵커 :29-61, :265, :365-393 세 지점 모두 clean. 서브커맨드 인자 노출과 reproduce 경로 정리는 확인.
- **여전히 LIVE (18 지점)**: `notifications.py:59`, `deliverables.py:101`, `adjustments.py:308`, `stress/path.py:110`, `archive.py:129/154`, `report.py:43`, `report_chrome.py:144`, `board_pack.py:87/418`, `work_report.py:84`, `ops_pages/core_overview.py:332`, `case_studies/bank7_2026q1.py:286`, `case_studies/ib3_report.py:228/237/280`, `case_studies/ib3_2026q1.py:198`, `market_data.py:521`, `localization.py:100/152`, `model_inventory.py:45/61`, `model_risk.py:36`. `datamodel/decompose.py` 는 앵커가 :164 → :191 로 드리프트했지만 같은 호출 (§3 신규 P1 참조).

### 1-2. FSS cross-form 대사 (거짓 통과·거짓 실패) , **LIVE (전건)**

- `risk_lib/regulatory/cross_form.py:61` 여전히 `("BR-31", "1110")`. :77 여전히 `("BR-31", "1510")`. 두 라인코드 모두 `forms_ext.py:545 br_camel` 이 만들지 않음.
- `cross_form.py:51` 위험가중자산 합계 대사 tol 그대로 default 1.0 KRW. BR-01/2000 (`final_total`) 과 BR-20/5000 (`floored_rwa`, credit-only) 미스매치 불변.
- `cross_form.py:38-49,:70` 누락 등록 (B2506/3000, B2403/1010, B2431/1010, B2506/2000, B2916/1000, B2602-2/1000) 모두 미등록.
- `risk_lib/regulatory/forms.py:380` BR-08 여전히 `tol=float(lcr.inflow_capped) + 1.0`. 항등 통과 불변.

### 1-3. 3선 독립검증 , **PARTIAL**

- **FIXED**: `risk_lib/validation/independent.py:662-708` `check_gate` 에 identity binding 이 landed. :674-677 `run_id`, :678-680 `request_id`, :684-690 재계산 키 미커버 감지 모두 강제. 델타에 명시 커밋은 없지만 이전 세션 어느 커밋에서 landed (PR #67 이후 확인).
- **LIVE**: 서명·해시 없음. 응답 파일 위조에는 여전히 무방비 (재계산 프로그램 해시·서명자 서명 필드 부재).
- **LIVE**: `validation-team-agent/tools/independent_recalc.py:140-153` `RECALCULATORS` 여전히 6 개 (lcr, nsfr, cet1_ratio, leverage_ratio, icaap_ratio, portfolio_default_rate). `RECALC_SCOPE` 21 개 대비 **15 개 headline (71 %) 이 여전히 독립 재계산 없음**.
- **LIVE**: `independent.py:39` `VERDICTS` / `STATUSES` 튜플이 정의되어 있지만 `Finding.__post_init__` 부재. `ValidationResponse.read` (:186) 가 `Finding(**f)` 로 검증 없이 삽입. severity 오타 (예: "중대") 는 여전히 게이트를 뒤집는다.

### 1-4. 리스크 코어 결함 , **LIVE (전건)**

- `risk_lib/integrations.py:302-314` `IsolatingDispatcher.send_with_isolation` 미수정. :303-304 `key` 계산 후 dedup 에 안 씀. :306-310 재시도가 sleep/backoff/jitter 없이 back-to-back.
- `risk_lib/limits/limit_engine.py:41-47` CRITICAL >= 1.20 vs `limits_deep.py:55-62` CRITICAL >= 0.90 반전 그대로. 같은 로우가 CRO 대시보드에 정반대 의미로 CRITICAL.
- `risk_lib/op_loss.py:88` `float(lognet.std() or 1.0)` , std()==nan 이면 `nan or 1.0 == nan` (nan truthy). VaR/ES NaN 오염 불변.

### 1-5. 테스트 결함 (회귀 통제 부재) , **LIVE (전건)**

- `tests/test_frtb_inventory.py:183` 여전히 `assert not e.is_overdue()` (today= 없음). 2030-01-01 시한폭탄.
- `test_frtb_inventory.py:72,:81` `np.random.normal(...)` 여전히 미시드.
- `test_frtb_inventory.py:192`, `test_monitoring_deep.py:262`, `test_stress_deep.py:336,:350` 모두 `run_pipeline(...)` 에 asof 미전달.

### 1-6. 정책 위반 (em/en dash) , **REGRESSED**

- U+2013 + U+2014 회 수: **9,076 → 9,653 (+577)**. 파일 수: **617 → 633 (+16)**.
- 43 시간의 델타 라운드에서 **하루당 약 190 회 씩 늘었다**. 이 속도면 사전 커밋 훅 없이는 계속 늘어난다.
- 델타 커밋 안에서 em dash 를 지운 흔적 (`catalog.py` MACRO_SCENARIO_LINK 한글명 en dash → 점) 이 부분적으로 있으나 저장소 신규 첨가분이 훨씬 크다.

## 2. 델타 신규 결함 (43주차 신규)

델타 8 커밋 리뷰에서 새로 발굴된 6 건. P1 은 최우선 조치.

### 2-1. P1: 벽시계 리크가 앵커만 이동한 채 살아남음

- `risk_lib/datamodel/decompose.py:191` , `decompose_from_result` 가 `result.meta` 에 `"asof"` 가 없으면 `date.today().isoformat()` 로 폴백. PR #67 §1-1 이 지적한 앵커 :164 는 델타의 +69 줄로 :191 로 밀렸다. **같은 호출**. 델타 커밋 (00fb2c6) 이 이 파일을 만졌으면서도 이 줄은 건드리지 않았다. `SNAP_rdm_exposure_<yyyy-mm-dd>` 스냅샷 ID 가 벽시계 하루로 바뀐다.

### 2-2. P1: 새 도구가 CWD-상대 경로를 사용해 리포지토리 밖에서 부러진다

- `tools/gen_flow_html.py:133` , `nav_groups()` 가 `Path("risk_lib/ui_studio/app.py").read_text(...)`. 같은 파일 :22 는 `sys.path.insert(0, str(Path(__file__).resolve().parent))` 로 `__file__` 을 쓴다. 두 접근이 일치하지 않는다.
- 재현: `cd /tmp && python /home/user/AIops/tools/gen_flow_html.py --out /tmp/x.html` , `FileNotFoundError` on nav_groups().
- 같은 결함 클래스: PR #67 §2-5 `tools/gen_fss_master.py:17` `OUT = Path("risk_lib/regulatory/fss_master.py")`.
- 새 테스트 (`tests/test_pipeline_flow.py`, `tests/test_erd.py`) 는 이 코드 경로를 밟지 않아 CI 통과.

### 2-3. P2: FK 점검이 조용히 건너뛰어 "PASS 이력" 계약을 어긴다

- `risk_lib/datamodel/spec.py:274-278` , `check_refs` 의 두 `continue` (source 컬럼 부재 :274, ref 컬럼 부재 :277) 가 `Violation` 도 `record.append` 도 부르지 않는다. `fk.ref_table` 부재 분기 (:265-272) 만 record 를 남긴다.
- 델타 00fb2c6 이 도입한 "위반 목록과 같은 코드 경로에서 나오므로 점검 목록이 실제 점검과 어긋날 수 없다" 불변을 스스로 위반. 상류 스키마 드리프트로 `rdm_exposure.obligor_id` 가 사라지면 `missing_column` 위반만 나오고, `obligor_id → rdm_obligor` FK 점검은 시도 기록조차 남지 않는다. `rdm_dq_result` 에서 "점검하지 않았다" 와 구별 불가.

### 2-4. P2: 마감 게이트 clean-run 테스트가 이행폐포 로직 없이도 통과한다

- `tests/test_sec_batch2.py:250-256` `test_a_clean_run_has_no_gate_violation` , 모든 evidence_table 이 1 행이라 모든 태스크가 `완료`. 태스크가 전부 완료면 pending predecessors 는 정의상 비어 있어 `진행가능` 이 나온다. `evaluate_gates` 를 직속 선행 로직으로 되돌려도 이 테스트는 그대로 통과.
- **한편** `tests/test_sec_batch2.py:227` `test_an_upstream_violation_reaches_the_approval_step` 은 CL-02 evidence 만 비워 CL-03/CL-08/CL-11/CL-12 가 `순서위반` 으로 잡히는지 확인해 이행폐포 로직을 실제로 검증한다. 이쪽이 정본이고, :250 은 중복이거나 아니면 다른 불변을 검증해야 한다 (예: 완료 태스크 수 == evidence_table 수).

### 2-5. P3: ERD·파이프라인 흐름 결정성 테스트가 same-process 만 본다

- `tests/test_erd.py:164` `assert build(...) == build(...)` back-to-back. `tests/test_pipeline_flow.py:162` 도 동형.
- 파이썬은 고정 PYTHONHASHSEED 아래 process 내부 dict/set iteration 순서를 보장. 따라서 set 기반 순서 (예: `_box_cols` 의 `fk_cols`) 에 결함이 있어도 이 테스트는 통과한다. 커밋 `9cc4544` 가 "항등식이던 회귀 시험 둘을 변조로 깨지는 통제로 바꾼다" 라고 못박은 실패 모드가 이 두 테스트에는 아직 반영되지 않았다.
- 권고: subprocess 로 `PYTHONHASHSEED=random` 을 재실행하거나 골든 픽스처 대조.

### 2-6. P3: `dq_result_frame(checks=None)` clean run 에서 여전히 빈 프레임

- `risk_lib/datamodel/decompose.py:153-186` , PASS 행을 만들려면 caller 가 `checks=` 를 넘겨야 한다. 현재는 `risk_lib/ui_studio/studio.py:184-186` 만 넘긴다. 다른 caller (테스트·애드혹 스크립트·미래 모듈이 `dm.validate_all(tables)` 로 부르는 경우) 는 PASS 없이 빈 프레임.
- 델타 00fb2c6 이 제거하려던 "0 위반 == 점검하지 않았다" 모호성이 API 표면에 남아 있다. 권고: `checks` 를 필수 인자로 만들거나 `validate_all` 이 항상 record 를 채워 반환하도록 시그너처 통합.

## 3. 델타 라운드 긍정 (기록)

부정 항목만 나열하면 델타의 실체가 왜곡된다. 43주차에 정말 landed 한 것을 확인 차원에서 남긴다.

- `risk_lib/close_workflow.py:135-156` `_all_predecessors` , 이행폐포 DFS with seen-set. 정확. cycle 종료 보장. CL-04 evidence 이관 (`rwa_sa_bucket → rwa_result`) 도 clean, 다른 곳의 `rwa_sa_bucket` 참조는 유효한 채로 보존.
- `risk_lib/datamodel/lineage.py` -145 줄은 전량 `ORPHAN_REGISTRY` 비움 (31 판정 → 빈 dict). `MAX_UNWIRED = 0` fail-closed 게이트는 유지. 새 미배선 원장 나오면 여전히 실패한다.
- 새 도구 (`tools/gen_{erd,pipeline_flow,flow_html,flow_diagram}.py`) 모두 `date.today()`·`time.time()`·`random.*` 부재. iteration 순서는 sorted list 또는 dict insertion order. process 내부 결정성 확보 (프로세스 간 결정성은 §2-5 지적).
- `check_gate` identity binding 이 (§1-3) landed. 3선의 nominal 신뢰가 42주차 대비 실질 개선.
- DQ 원장 PASS 세만틱: 카탈로그 note (`catalog.py:156-158`) 와 `validate(record=...)` (`spec.py:186-194`) 문서·구현이 정렬. 이건 그 자체로는 옳은 방향.

## 4. MAJOR (누계·미소화)

42주차 §2 의 60+ 건은 전량 미소화. 신규로 §2-3, §2-4, §2-6 세 건이 delta 에서 진입. 여기서는 42주차 이후 추가로 관찰된 세 건만 나열한다.

- `risk_lib/pipeline.py:1500-1503` , `asof_source` 원장 태그가 landed 했으나 `validation/consistency.py:213-223` `_check_asof_provenance` 가 여전히 WARN 리턴. WARN 이 게이트를 통과하는 한 태그 추가는 감사 기록이지 통제가 아니다. 태그를 강제로 FAIL 로 승격하거나 아예 raise 로 바꿔야 한다.
- `risk_lib/datamodel/lineage.py` 의 `ORPHAN_REGISTRY = {}` empty registry , 새 미배선 원장이 나오면 `MAX_UNWIRED = 0` 이라 실패하지만, **판정 근거 (`why` 필드) 가 사라져** 새 원장이 왜 미배선인지 후속 정리 시 판별 불가. registry 를 비우는 대신 판정을 `WIRED` 로 마이그레이션했어야 감사 흔적이 남는다.
- `tools/gen_flow_html.py:22` `sys.path.insert(0, ...)` , 같은 프로세스가 이후 `import gen_erd` `import gen_pipeline_flow` 하면 두 모듈이 `tools/` 를 sys.path 최상단에 올린 상태로 남는다. `tools/gen_flow_html` 을 라이브러리로 임포트하는 소비자에게 부작용.

## 5. PR ownership 상태 (매주 확정)

| PR | 상태 | 43주차 |
|---|---|---|
| #46 nail-simulation | draft, unowned | **16 주 확정** (last commit 2026-07-27, 무커밋 지속) |
| #38 3D shooter | draft, unowned | 6주 확정 (last commit 2026-08-02) |
| #57 HANDOVER.md | draft | 6주 (last commit 2026-08-05) |
| #67 42주차 리뷰 | draft, 이 리뷰 이후 정본 대체 | close 권고 후 이 43주차 PR 로 이관 |

- `origin/main` 은 43 시간 전 `64229b2` 에서 현재 `00fb2c6` 로 8 커밋 이동. 이 8 커밋은 `claude/stoic-ride-4wc81a` 브랜치에서 나왔으나 이 세션이 시작되기 전 landed (fast-forward). PR #67 은 별도 브랜치 (`stoic-ride-66n8l3`) 로 unmerged.
- **B9Kxm** (`claude/risk-management-agent-harness-B9Kxm`) 브랜치 head 는 `f7b532f` (2026-08-12 06:18). 델타 라운드 무커밋. 2 일간 dormant.
- **Pw9F5** (`claude/validation-team-agent-Pw9F5`) 브랜치 head 는 `75c01af` (2026-08-05 16:34). 델타 라운드 무커밋. **9 일간 dormant**. §1-3 3선 RECALCULATORS 확장이 이 브랜치 소관인데 진행 없음. warden 개입 조건 성숙.

## 6. 권고 (재발 방지)

우선순위대로 세 개.

### 6-1. 사전 커밋 훅 두 개 (재요구, 42주차 §5-1 미이행)

PR #67 이 권고했으나 **미도입**. 그 사이 em/en dash 가 +577 늘었다. 도입이 하루라도 앞당겨졌으면 이 신규분은 없었다. 다시 요구한다.

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

### 6-2. `decompose.py:191` 벽시계 즉시 raise

`decompose_from_result` 는 `result.meta["asof"]` 필수. 없으면 raise. `_all_predecessors` 처럼 계약을 코드로 강제해야 다음 리뷰에서 앵커 드리프트 (§2-1) 가 반복되지 않는다.

### 6-3. 3선 RECALCULATORS 확장 착수 지시 (Pw9F5 명시 재요구)

`validation-team-agent/tools/independent_recalc.py:RECALCULATORS` 를 `RECALC_SCOPE` 21 개 전량으로 확장. 미구현 항목은 명시적 "미구현" 상태로 등록해서 게이트가 응답대기로 남게. 6 개만 True 로 통과하는 현재 상태는 **AIMS §2-4 위반이 3 주째 이어지는 것**이다. Pw9F5 dormancy 로 진행 없음, warden 개입 조건 성숙.

## 7. 리뷰 메타 (2 서브에이전트 · 델타·tracked)

- 리뷰 도구: 2 개 병렬 서브에이전트 (general-purpose). 총 소요 약 605 초, 소비 토큰 약 211k.
- 리뷰 커버리지: (A) PR #67 §1 의 6 개 BLOCKER 재점검, (B) 델타 8 커밋 전체 (25 파일, +3,428 / -264).
- 자체검증 (2선), 상시 독립검증 (3선): 이 리뷰는 코드 리뷰이며 리스크 산출이 아님. RECALC_SCOPE 대상 아님.

---

# 부록 A: 서브시스템별 전수 리뷰 (43주차 · 8 병렬)

델타·tracked 만으로는 "전수" 라는 이름이 사실이 아니라, 42주차 (PR #67) 가 실행한 8 개 병렬 서브에이전트 sweep 을 43주차에도 다시 돌렸다. 8 개 영역, 각 영역별 리뷰어 1 명, 결함 수 상한 12 (§A-1 은 15). PR #67 이 이미 지적한 결함은 제외했다. 각 결함은 파일:줄 앵커·재현 시나리오 포함.

**총 신규 결함 99 건** (§A-1 15 + §A-2..§A-8 각 12).

## A-1. `risk_lib/` 최상위 (15 신규 결함)

리뷰 파일: `cli, pipeline, notifications, integrations, deliverables, frtb, ccr, op_loss, macro_monitor, adjustments, abbreviations, api, appetite, archive, attribution, audit_trail, board_pack, capital_simulation, cecl, climate, close_workflow, commercial, comparison, concentration_deep, data_gen, data_gen_intl, data_quality, explainability, funding, html_exec, html_report, institutions, integrations, intraday, ipv, limits_master, localization, margin, market_data, market_feed, mda, model_inventory, model_risk, ncr, op_loss, page_registry, pillar3, pillar3_disclosures, printable, product_master, rcsa, references, report, report_chrome, repro, rynta, scenario_library, sensitivities, sensitivity, systemic, timeseries, timeseries_ledger, vintage, viz, viz_advanced, work_report, xva` (~68 파일).

| # | 심각도 | 파일:줄 | 요약 |
|---|---|---|---|
| A1-1 | MAJOR | `macro_monitor.py:447-454` | YoY 필드가 모든 주기에 offset=4. 월간 지표 9/12 는 offset=12 필요. `macro_indicator.yoy` 컬럼이 전년동기대비 아님. |
| A1-2 | MAJOR | `frtb.py:121-135` | `rfet_test` 가 "date" 컬럼을 리스크 팩터로 취급. NMRF 카운트에 유령 팩터가 잡히고 :141 flat 10 억원 add-on 이 발생. |
| A1-3 | MAJOR | `capital_simulation.py:172` | `earnings = er * base_rwa` 가 초기 RWA 고정. 심각 시나리오로 RWA 가 30-50 % 커져도 이익은 동결. Q8 CET1 저점을 약 2.5pp 과소평가. |
| A1-4 | MAJOR | `attribution.py:159-163` | `dnet = (lb.net_outflow - la.net_outflow) or 1.0` 이 0 을 1.0 으로 바꾸어 뒤의 `if dnet else 0.5` fallback 이 절대 실행되지 않음. w_out = da_outflow (절대값). |
| A1-5 | MAJOR | `scenario_library.py:33-34+` | 시나리오 라이브러리 credit_spread 값이 docstring 대로 %가 아니라 ×1000 스케일. `ops_pages/market_trading.py:402` 등이 ×100 렌더하여 CCAR 575bp 가 화면에 58bp. |
| A1-6 | MAJOR | `ccr.py:67` | `maturity_factor = sqrt(min(M, 1.0))` 이 CRE52.48 의 10 영업일 numerator floor 미적용. 5 일 IR 스왑이 MF≈0 → EAD 40 % 과소. |
| A1-7 | MAJOR | `pipeline.py:1645-1646` | `if False else []` 죽은 branch. 42주차에서도 지적. 여전. `model_cards` 변수 미사용. |
| A1-8 | MINOR | `pillar3.py:112-114` | `hqla_detail.loc[0/1/2]` positional 인덱스 사용. hqla_detail 정렬·재인덱스 시 Level 1/2A/2B 스와프. |
| A1-9 | MINOR | `op_loss.py:95-96` | `above_99 = agg[agg >= q99]` 가 quantile 동일 값 ties 를 포함시켜 ES99 를 sub-tail 로 편향. Poisson 무손실 시뮬 다수인 경우 심함. |
| A1-10 | MINOR | `xva.py:129` | `im_t = im_initial * (1 - t / t.max())` 이 `t = linspace(0.25, m)` 로 시작해 첫 버킷 IM 이 초기값의 ~93 %. MVA 약 7 % 과소. |
| A1-11 | MINOR | `capital_simulation.py:214-221` | `at1_writedown_amount` 파라미터가 실제로는 conversion. 영구 write-down 을 기대한 caller 는 CET1 +1tn boost 를 받음. 이름 오도. |
| A1-12 | MINOR | `sensitivities.py:220-226` | `sqrt(Σ component²) × 2.326` SS-VaR 이 correlation=0 가정. 위기 국면 delta·cs01 실제 0.6 상관이면 20-40 % 과소. |
| A1-13 | MINOR | `frtb.py:140-141` | Docstring "10 % capital adder" vs 코드 `n_nmrf * 1e9` (10 억 원). |
| A1-14 | MINOR | `systemic.py:240-247` | `contagion_tipping_point` 이 `lo, hi = 0.0, max_frac` 초기화 후 binary search 미실행. coarse linspace 만 돔. |
| A1-15 | MINOR | `cecl.py:82` | `w_life = (ead*maturity).sum() / ead.sum()` 에 zero-guard 없음. 빈 포트폴리오나 all-zero-ead 이면 ZeroDivisionError. |

## A-2. `risk_lib/regulatory/` (12 신규 결함)

| # | 심각도 | 파일:줄 | 요약 |
|---|---|---|---|
| A2-1 | BLOCKER | `cross_form.py:55-84` | 비율 불변식이 항등적. BR-07/3000 (레버리지), BR-08/5000 (LCR), BR-09/3000 (NSFR), BR-01/3100·3300 (CET1) 모두 같은 result 에서 읽어 산술적으로 같음. 통과 카운트가 커버리지처럼 보이지만 falsifiable 하지 않음 (F-602/703 패턴). |
| A2-2 | MAJOR | `cross_form.py:59-63` | BR-31 라인코드가 positional. `br_camel` 의 `1100+i*100` 이 `pru_camel` iteration 순서에 의존. `evaluate_camel` 컴포넌트 재정렬 시 BR-31/1110 의 의미가 조용히 이동. 이름 바인딩 필요. |
| A2-3 | MAJOR | `provenance.py:276-279` | `_ledgers_for(form_id=...)` 가 BR-xx 별칭 (내부) vs FINES 코드 ("B3115") 매칭 실패. Ledger.forms 는 FINES 코드만. 향후 `forms=("B3115",)` 선언 시 BR-27 impact 조용히 누락. |
| A2-4 | MAJOR | `provenance.py:322-326` | `ledger_impact_frame` 이 MIXED 제외, `unattributed` 는 포함. MIXED 라인이 두 표에서 의미가 다름. "이 원장 확보하면 N 서식 해소" 헤드라인이 mixed 라인만큼 과소. |
| A2-5 | MAJOR | `provenance.py:102-103` | `_NEGATIONS` 가 `_MIXED` 보다 먼저 매칭. "합계는 파생하지 않았고 배분만 파생" 이 MEASURED 로 오분류. Docstring 이 경고하지만 순서가 그것을 무력화. |
| A2-6 | MAJOR | `cross_form.py:76-84` | LCR/NSFR 불변식이 B2913·B2916 등록 누락. 오늘은 A2-1 이 이를 가림 (같은 result 에서 읽어 항등). |
| A2-7 | MAJOR | `citations.py:22-23` | `n_no_clause` 가 regex 매치 카운트 (라인이 아니라). 한 줄에 clause 없는 인용이 2 개면 2 회. `coverage_sentence` 는 line 분모로 렌더. |
| A2-8 | MAJOR | `excel.py:170-195` | text-unit 라인이 시트당 두 번 기록. 메인 루프 :174 에서 col 4 로 쓰고, 트레일링 블록 :190-195 에서 `※ {text}` 형태로 col 2 재기록. BR-10/9000 · BR-14/* 모든 "비고" 라인이 중복. |
| A2-9 | MAJOR | `structure.py:31-32` | `BASELINE_PATH = parents[2] / "tests" / "form_structure_baseline.json"` 이 site-packages 설치 시 리포지토리 밖. `coverage()` 가 조용히 `n_baseline_keys=0` 리턴. |
| A2-10 | MINOR | `forms_fss_liquidity.py:100+` | `_LADDER = ladder_citation()` import-time 실행. 테스트가 `alm.params.build_time_buckets` 를 import 이후 스텁하면 wiring 소실. |
| A2-11 | MINOR | `cross_form.py:88-95` | `_value` 가 O(N·M). 9 불변식 × 30 라인이 매번 290 폼 스캔. `{(form_id, line_code): value}` 사전화로 ~10x 절감. |
| A2-12 | MINOR | `forms.py:794-811, 825-840` | `_fss_specs` 의 `BY_CODE[code]` unguarded. 13 builder 모듈 중 어느 하나의 코드 오타가 `risk_lib.regulatory` 전체 import 를 붕괴. |

## A-3. `risk_lib/{alm,capital,credit_rating,icaap,prudential}/` (12 신규 결함)

| # | 심각도 | 파일:줄 | 요약 |
|---|---|---|---|
| A3-1 | BLOCKER | `capital/rwa_sa.py:22-46` | "B" rating (B+/B/B-, CCC+/CCC/CCC-) 이 `_RW_*` 사전에 `"B": 1.00` 매핑. CRE20.6/20.24/20.44 는 BB- 미만은 150 %. `"CCC-": 1.50` 만 코딩되어 있고 B-bucket 익스포저가 100 % RW. |
| A3-2 | BLOCKER | `capital/rwa_irb.py:40-45, 74-105, 135-188` | LGD 입력 하한 (CRE32.15) 미적용. 25 % 무담보 senior corporate/bank, 50 % QRRE transactor, 30 % 기타 리테일 무담보. docstring 이 "auto-floor 없음" 을 명시. 은행 추정 LGD 가 하한 아래면 RWA 과소. |
| A3-3 | BLOCKER | `capital/rwa_deep.py:262-289` | FIRB `corporate_senior_unsecured=0.45` 하드코딩. Basel III 확정 후 corporate senior unsecured FIRB LGD 는 40 %. 코드는 벡터화 branch (:288) 에서 `residential_mortgage` 에도 FIRB LGD 를 배정 (FIRB 는 retail 미적용). |
| A3-4 | BLOCKER | `capital/op_risk.py:22, 55-67, 83` | `use_ilm=True` 디폴트로 Bucket 1 은행 (BI ≤ €1bn) OPE25.30 국가재량 (한국 FSC 통상 ILM=1) 미반영. `_BI_BUCKETS` 임계값도 EUR 원문 (1bn, 30bn) 이라 KRW BI 보고 시 소형은행 op-risk RWA inflate. |
| A3-5 | BLOCKER | `models/rating.py:12-52` | `pd_to_rating` docstring `pd_upper: exclusive` vs 모듈 주석 `pd_lower < pd <= pd_upper` (inclusive) 상충. `bisect_left(uppers, pd_value)` 는 upper inclusive. 경계 PD (예: 0.0003) 가 AA+ (기대) → AAA (실제). `multi_axis.py:143-152` 를 통해 stress-downgrade, SA bucket 배정으로 전파. |
| A3-6 | MAJOR | `capital/crm.py:35-46, 51-54, 138-141` | `_SUPERVISORY_HAIRCUTS` 에 CRE22.49 revised A/BBB 티어 (sovereign 1/3/6 %, corp bond 2/6/12 %) 누락. A/BBB 담보를 `_aaa_` 라벨로 넣으면 haircut 과소 → CRM 완화 과대. |
| A3-7 | MAJOR | `capital/rwa_sa.py:126-127, 190` | `past_due=True` 가 residential mortgage LTV 규칙을 덮어써 150 %. CRE20.91 revised 는 별도 100 % (LTV 분할). Past-due 모기지 자본 과대. |
| A3-8 | MAJOR | `alm/curves.py:444-453, 479-489` | `Curve.rate(t) = -log(DF(t))/t` 가 max_tenor 넘어서면 log(DF) flat extrapolation 으로 rate → 0. `nii.py:285` 등이 계약별 t 에서 rate() 호출. 장기 만기 계약의 Δr 축소 → ΔNII/ΔEVE 과소. |
| A3-9 | MAJOR | `alm/irrbb.py:480-506, 585-598` | `_option_risk_by_ccy` merge key `["ccy","scenario"]` 만. `kr_auto_option_risk` 가 여러 framework version 을 담고 있으면 별표9의1_2026 ΔEVE 에 d368_2016 옵션리스크가 합산. `framework_version` 필터 필요. |
| A3-10 | MAJOR | `credit_rating/scorecard.py:284-302, 499-500, 655-657` | `build_scorecard_param` 이 6 파라미터 전부 `approval_status="미승인"` 하드코딩. `fit_scorecard` 는 `.any()` 이면 미승인. 결과: 모든 obligor 의 `crm_obligor_score.param_approval == 미승인` 영구. per-parameter 트래킹 없음. |
| A3-11 | MAJOR | `icaap/economic_capital.py:49-55` | 42주차에서 15 % cap 만 지적. 추가: `0.5·hhi_sector + 0.3·hhi_country` 선형 계수 인용 없음. Gordy (2003) 인용은 있으나 선형 형태 근거 없음. 임의값이 Pillar 2 concentration RWA 전량 결정. |
| A3-12 | BLOCKER | `capital/rwa_sa.py:214-228` vs `crm.py` | `compute_rwa_sa` 가 `crm_factor` (post-computation multiplication) 를 받아 CRE22 comprehensive 기계 (`crm_adjusted_ead`, supervisory haircut, FX 미스매치, guarantee 대체) 전량 우회. Pipeline 에서 apply_crm 이 도는 포트폴리오 + `crm_factor` 존재 시 CRM 이중 적용 가능. Sign 무한. |

## A-4. `risk_lib/{monitoring,limits,crm,governance,stress,validation,models}/` (12 신규 결함)

| # | 심각도 | 파일:줄 | 요약 |
|---|---|---|---|
| A4-1 | BLOCKER | `models/rating.py:41-52` | (§A3-5 와 같은 결함, cross-check 확인) `pd_to_rating` 경계 off-by-one. `bisect_left` → `bisect_right` (또는 left-open 구간 변환). |
| A4-2 | BLOCKER | `governance/audit_chain.py:190-207` | 4-Eyes approver 가 NaN 이면 `str(NaN)=="nan"` (truthy) 로 chain 에 사인. missing approver 가 유효 항목으로 해시. `pd.isna(...)` guard 필요. |
| A4-3 | MAJOR | `monitoring/deep.py:220-239` | roll-rate prior 가 `sigma = 0.04 / (n_src + 0.05)` 로 small bucket 에서 σ≈0.67. clip(-0.05,0.05) 뒤 normalize 로 90+ 로우 (`[0.02,0.02,0.03,0.05,0.88]`) 의 규제 prior 소실. 인접 seed 가 NPL cure 확률 재현 불가. |
| A4-4 | MAJOR | `monitoring/delinquency.py:98-124` | `transition_matrix` 가 `sum(axis=1)>0` 로 absorbing DEFAULT 행 삭제. t0 에 DEFAULT 없으면 DEFAULT 열은 있지만 행 없음. `mat @ state` 형상 오류. `reindex(columns)` 만 되고 rows 미조정. |
| A4-5 | MAJOR | `monitoring/recovery.py:37-51` + `recovery_deep.py:50-64` | `rates.mean()` 가 EAD 무가중 평균. KRW 1mn default 와 1tn default 동일 가중. CRE36.83/CRE32 workout LGD 는 EAD-weighted. 같은 모듈의 `cumulative_recovery_rate` (:54-68) 는 EAD-가중이라 스칼라 vs 커브 상충. |
| A4-6 | MAJOR | `governance/model_lifecycle.py:216` | `mine["evidence_ref"].notna().all()`. `pd.notna("")` == True. `evidence_ref=""` 이면 "with evidence" 판정 → 모델 '적합'. `.astype(str).str.strip().replace("", pd.NA).notna().all()` 필요. |
| A4-7 | MAJOR | `stress/multi_axis.py:414-445` | `solve_critical_severity` 가 baseline breach 여부 미검증. `ratio_at(0) > target` 가정 없이 bisection 하면 baseline 이 이미 breach 인 경우 critical_severity ≈ 0 또는 endpoint (무의미). `RECALC_SCOPE` 대상. |
| A4-8 | MAJOR | `governance/unified_run.py:105-110` | `_fingerprint` 가 `(table, n_rows, n_cols)` 만 해시. 컬럼 rename, 값 편집, 행 재정렬 후에도 동일. `gov_unified_run.run_fingerprint` 로 저장되어 두 run 동일성 판정에 사용. `retention.py:_fingerprint:187-195` 는 content hash 를 하고 있어 대조 가능. |
| A4-9 | MAJOR | `crm/allocation.py:230-253` | `pro_rata` 가 collateral 별 greedy (알파벳순 collateral_id). 한 라운드 안에서 첫 collateral 이 pro-rata 로 채우면 두 번째는 감소된 demand 를 봄. simultaneous 아님. |
| A4-10 | MAJOR | `governance/audit_chain.py:62-66` | `json.dumps(..., default=str)` 이 NaN/Inf 를 bare `NaN`/`Infinity` (RFC 8259 위반) 로 출력. `payload_digest` 외부 감사 파서가 파싱 실패. `record_hash` 는 유지되지만 external audit 재현 불가. `allow_nan=False` 필요. |
| A4-11 | MAJOR | `crm/allocation.py:175-176` | `Hfx` 가 collateral 링크 중 하나만 FX 미스매치여도 collateral 전체에 적용. [별표 3] 65.나 는 per-pair. 자본 보수적이지만 `check_collateral_value_ties_to_terms` (`consistency.py:377-431`) 이 같은 convention 기대. 향후 per-pair 로 바꾸면 tie-out 붕괴. |
| A4-12 | MINOR | `stress/climate_capital.py:110-146` | `NGFS_CO2_PATHS` iteration dict-order 의존, no sort. `phase_version`/`vintage_date` 필드 부재. 데이터 refresh 시 phase IV → V 로 조용히 아티팩트 무효. 42주차 `evidence_status` 지적에 결정성·버전 스탬프 결함 추가. |

## A-5. `harness/`, `examples/`, `tools/`, `risk_lib/cli.py` (12 신규 결함)

| # | 심각도 | 파일:줄 | 요약 |
|---|---|---|---|
| A5-1 | BLOCKER | `risk_lib/cli.py:365-393` | `_cmd_reproduce` 가 저장된 manifest 의 `asof`, `institution_code`, `capital_ledger`, `market_op`, `structured_scale`, `pillar2`, `adjustment_ledger` 를 `run_pipeline` 에 미전달. `repro.build_manifest:163-173` 이 이 값들을 기록하는데 재현이 그것을 무시. 결정론적 코드에서도 "재현 실패" 거짓 negative. |
| A5-2 | BLOCKER | `risk_lib/cli.py:70-72, 373` | `report-set --portfolio book.csv` 가 CSV 경로를 `parameters` 에 미기록. `_cmd_reproduce:373` 이 무조건 `generate_portfolio(seed=...)` 호출. CSV 기반 run 재현 시 조용히 synthetic data 로 대체. 지문 미스매치가 코드 드리프트 vs 재현 결함을 구별 못함. |
| A5-3 | MAJOR | `risk_lib/cli.py:29-61` | `_cmd_run` 이 `build_manifest` 미호출. `run` 서브커맨드 (모듈 docstring 3-7 줄의 정본) 로 만든 리포트는 `reproduce` 불가. 사용자가 docstring 따라 쓰면 감사 시점에 발각. |
| A5-4 | MAJOR | `examples/run_end_to_end.py:175-176` | `if __name__ == "__main__": main()` 이 `main()` 리턴을 exit code 로 매핑 안 함. :160-165 의 PASS/FAIL 프린트에도 프로세스는 exit 0. CI 가 broken demo 감지 불가. `examples/run_100k.py:51,55` 는 correct pattern. |
| A5-5 | MAJOR | `examples/run_end_to_end.py:78-79, 88-91` | STEP 4 `rwa_market=1.5e12`, `rwa_op=2.0e12` 하드코딩. 이어 `CapitalStack(cet1=rwa_total*0.115, ...)` 로 CET1/T1/총자본비율이 정의상 11.5/13/15.5 %. `compute_bis_ratios` 를 실제 검증하지 않는 데모. 잘못된 교훈. |
| A5-6 | MAJOR | `examples/run_end_to_end.py:30, 41` | `generate_portfolio()`, `split_train_test(corp)` seed 무 지정. 결정성이 default (42, 7) 우연에 의존. `data_gen.py:24/207` default 변경 시 조용히 재현성 소실. |
| A5-7 | MAJOR | `tools/gen_flow_html.py:155-156` | `seed=42, asof="2026-06-30"` 하드코딩. "실측 행수" 가 한 스냅샷 pin. portfolio generator default 변경 시 doc 이 조용히 stale row counts. warning/manifest 부재. |
| A5-8 | MAJOR | `tools/gen_erd.py:317, gen_flow_diagram.py:246, gen_pipeline_flow.py:410, gen_flow_html.py:415` | 4 개 도구 `--out` default 가 `docs/erd.html` 등 CWD-상대. 리포지토리 밖 실행 시 stray `docs/` 생성 (`tools/gen_fss_master.py:17` 와 동일 결함 클래스). |
| A5-9 | MAJOR | `tools/gen_flow_diagram.py:230-238` | SVG 하드코딩 `fill="#ffffff"` 배경 + `fill="#212529"` 텍스트. 테마 스왑 없음. 다른 tools 는 CSS custom prop 사용. dark viewer 에서 unreadable. |
| A5-10 | MAJOR | `harness/de-team-runbook.md:42-44` | `deliverables/runbooks/`, `deliverables/pipelines/` 경로 참조. 실제 tree 는 `deliverables/analyses/`, `deliverables/models/` 만. 런북 따르면 non-existent dir 로 write. |
| A5-11 | MAJOR | `harness/de-team-runbook.md:1`, `handbook-map.md:18`, `harness/legal/runbook.md:21,27,28,29,35,47,56,57,58,65,78,84,85` | harness 도구 문서 자체가 em dash 대량 사용. CLAUDE.md §5 위반이 contract artifact 표면에. |
| A5-12 | MAJOR | `risk_lib/cli.py:100-120` | `_cmd_notify` 가 `--seed` 만 받고 buffer/hurdle/floor/asof 무시. Slack/이메일 페이로드가 operator 의 `report-set` 과 다른 파라미터로 파이프라인 run. `notify` 번들이 CRO deck 과 숫자 상충 가능. |

## A-6. `validation-team-agent/` (3선 독립검증, 12 신규 결함)

| # | 심각도 | 파일:줄 | 요약 |
|---|---|---|---|
| A6-1 | BLOCKER | `tools/validation_finding.py:55-60, 215-223` | `_TRANSITIONS["remediating"] = {"reverifying"}` 이 `"remediating"` 미포함. `record_reverification(result="fail")` 이후 `derive()` 가 status 를 `remediating` 로 리셋. 다음 `record_remediation` 이 `_require_transition(..., "remediating")` → False → `FindingError`. VAL-013/014 재수정 loop 표현 불가. |
| A6-2 | BLOCKER | `tools/conditional_approval.py:215` | `check_scope` 가 `usage.strip() in scope` 로 substring 매치. `scope="리테일 포트폴리오 한정"`, `usage="리"` 이면 `allowed=True`. Docstring 은 "conservative" 라고 하지만 방향 반전. VAL-016 bypass. |
| A6-3 | BLOCKER | `tools/pack_diff.py:23-52` | `_STATUS_ORDER` 에 `skipped=3 > fail=2`. `_status_transition_severity("skipped","fail")` 이 `"improved"` 리턴. KPI/heatmap 이 not-run → failing 이 개선으로 QoQ 리포트. |
| A6-4 | MAJOR | `tools/pack_verify.py:101` + `tools/report_pack.py:4368` | salt 공식 `f"vta-pack-salt-{seed}"` 이 두 파일에 하드코딩. 한 쪽 변경 시 verify 가 divergent salt 재도출. `df sha256`/`scalar_sha256` 다르게 나와 input-drift 로 오해. 헬퍼 단일화 필요. |
| A6-5 | MAJOR | `tools/pack_verify.py:189-193` | `--deep` rebuild 가 historical provenance 상속. `build_pack(demo, request, ..., provenance=prov, ...)` 로 OLD prov 전달. "rebuilt" pages 가 원본 `generated_at_utc`, `git.rev` 를 embed. 실제 provenance-generation 회귀는 이 체크로 실패 불가. |
| A6-6 | MAJOR | `tools/run_workflow_demo.py:82-135` | `_domain_inputs` 가 caller seed 무시. `capital_ratio_sample()` (seed=7), `ccr_exposure_sample()` (seed=17), `cva_counterparty_sample()` (seed=13), `concentration_exposure_sample()` (seed=23) 고정. `--seed` 는 credit df 만 변함. `provenance.build_provenance` 재현성 주장 과대. |
| A6-7 | MAJOR | `tools/sample_generators.py:62-64` | `credit_scoring_sample` obs_date 하드코딩 `"2022-01-01" periods=24`. 2026 년 실행해도 2 년 이상 stale. 같은 파일 :112 `ifrs9_weight_panel` 도 `"2024-Q1..Q4"` 하드코딩. |
| A6-8 | MAJOR | `tools/regulatory_criteria.py:56, 132` | `_cmd_verify` 가 `--catalog` override 를 받지만 `violations(data)` 는 default `root=ROOT` 사용. `data["sources"][key]["path"]` 가 프로젝트 ROOT 조인. Catalog 이동 시 조용히 "원문 없음" 또는 잘못된 파일. |
| A6-9 | MAJOR | `tools/report_export.py:38-98` | `_kpi_cards`, `_heatmap_rows`, `_risk_watch` 가 각기 `run_demo(2_000, ...)` 를 처음부터 3 회. 비용 외에도 셋 다 relative `Path("logs/export_temp")` (CWD 의존). 3 회 사이 nondeterminism 시 내부 상충 CSV. |
| A6-10 | MAJOR | `tools/policy_lint.py:52-58` | `_extract` 가 `_MARKER_PATTERN` 후 `_OP_PATTERN` 을 같은 텍스트에. `_OP_PATTERN` 이 `<!-- threshold: KS>=0.30 -->` 안도 매치. explicit marker 가 marker + free-text 2 회 카운트. `values_by_source` 지표 이중. |
| A6-11 | MAJOR | `tools/validation_memory.py:49` vs `risk_lib/validation/independent.py:39` | `SEVERITIES=("중부적합","경부적합","적합")` (여기) vs `VERDICTS=("적합","경부적합","중부적합")` (저기). 순서 반대. positional worst/best 를 쓰는 consumer 는 한 쪽이 다른 쪽에 conform 되는 순간 조용히 뒤집힘. 어느 쪽도 validator 강제 안 함. |
| A6-12 | MAJOR | `tools/validation_trigger.py:278`, `conditional_approval.py:172-175`, `validation_finding.py:297,358` | `queue()`, `compliance()`, `escalations()` 모두 `date.today()` 폴백. `overdue`, `escalate` flag 가 wall-clock. 42주차 §2-4 지적의 확장. |

## A-7. `tests/` (12 신규 결함)

| # | 심각도 | 파일:줄 | 요약 |
|---|---|---|---|
| A7-1 | MAJOR | (전체) | 미테스트 프로덕션 모듈: `governance.rbac` (395 LOC, 0 test), `governance.retention` (318), `close_workflow` (201), `rcsa` (362), `climate` (169), `margin` (366), `funding` (282), `market_feed` (286), `viz_advanced` (369), `abbreviations` (353). RBAC 특히 핵심 통제 표면인데 zero 직접 테스트. |
| A7-2 | MAJOR | 15+ 파일 | `run_pipeline()` wall-clock `asof` 리크 42주차 §1-5 스윕 부족. 신규 미해결: `test_rapm_deep.py:241`, `test_limits_deep.py:326`, `test_credit_models.py:141,215`, `test_extras.py:181,191,204`, `test_explainability.py:131,138,145,157`, `test_final_validation.py:24,225,226`, `test_timeseries.py:23` (module-scoped fixture, 5 회 unpinned), `test_xva_sensitivities.py:177`. |
| A7-3 | MAJOR | `test_erd.py:23`, `test_pipeline_flow.py:20` | `sys.path.insert(0, ".../tools")` at import time. 전체 pytest 세션 오염. `tools/*.py` 이름이 무관 모듈을 shadow. fixture 또는 repo-local conftest 로 이동. |
| A7-4 | MAJOR | (전체) | Property-based test 부재. `hypothesis` grep 0 매치 / 2,182 test. 강력한 불변식 존재 지점 예: `_backtest_zone` 경계 (`test_frtb_inventory.py:99-108`), `plat_test`/`_zone_spearman`/`_zone_ks` 단조성, `auc_roc(y,s) == (gini+1)/2`, IRRBB shock 대칭, RWA/CET1 stress 단조. |
| A7-5 | MAJOR | 8+ 위치 | Existence-only assertion. 필드가 무엇으로든 채워지면 통과: `test_rapm_deep.py:242 assert res.rapm_deep is not None`, `test_limits_deep.py:327`, `test_ecl_deep.py:264-265`, `test_rwa_deep.py:321`, `test_alm_curves.py:493`, `test_behaviour_estimation.py:201`, `test_kr_irrbb.py:1117`, `test_independent_validation.py:484-485`. 각각 shape 또는 수치 불변식 필요. |
| A7-6 | MINOR | `test_ui_screens.py:88` | `html = uiapp.render.__doc__ or ""` 후 `assert html is not None`. `or ""` fallback 이 문자열 보장. assertion never fails. |
| A7-7 | MINOR | `test_pillar3_capsim.py:212`, `test_req_wiring.py:136` | Disjunction assertion 자기충족. `sev["passes_all"] is False or sev["first_breach_q"] is not None` , severe 는 정의상 breach 로 left disjunct 항상 True, right 는 미검증. 두 positive assertion 으로 분리 필요. |
| A7-8 | MINOR | `test_citations.py:68,80,111` | 기준선 JSON 부재 시 `pytest.skip`. 오늘은 baseline 존재. 삭제 사고 시 citation 불변 조용히 통과. `pytest.fail` 또는 REGENERATE_BASELINE env gate 필요. |
| A7-9 | MINOR | `test_timeseries.py:18-27` | `_mk_ledger` module-scoped fixture 가 `run_pipeline` 5 회 (asof 없음). session-scoped fixture 재사용 가능. 아마 최슬로우 단일 유닛 (>30s wall). |
| A7-10 | MINOR | `test_explainability.py:131,138,145,157` | Session-scoped `result` fixture (`conftest.py:22-29`) 있음에도 4 회 `run_pipeline(generate_portfolio(seed=42), seed=42)` 재실행. PINNED_ASOF 와 divergent. 4 회 낭비. |
| A7-11 | MINOR | `test_behaviour_estimation.py:555-565` | `subprocess.run(..., timeout=600)` 로 `_ledger_digest` 재임포트. subprocess 오버헤드 + risk_lib 전체 재파싱. `multiprocessing.get_context("spawn")` 함수 단위 대안. |
| A7-12 | MINOR | `test_plgd.py:484`, `test_irb_estimation.py:637`, `test_discount_capm.py:511`, `test_ui_engine_parity.py:116` | `subprocess.run([sys.executable, "-c", code], ...)` 가 `cwd=REPO` 미설정. `test_behaviour_estimation.py:562` 만 설정. 향후 conftest 가 cwd 변경 시 조용히 sys.path 상 다른 risk_lib pickup. |

## A-8. 저장소 전수 정책 감사 (12 신규 결함 + 카운트 정합)

**정확 카운트 (Reviewer #8, .git 제외):**
- em/en dash: **8,325 occurrences / 570 files** (PR #67 대비 9,076 → 8,325 로 약 700 회 감소, 47 파일 감소). 부록 본문 §1-6 의 "9,653 → REGRESSED" 는 다른 grep scope (확장자 필터) 로 도출된 서브에이전트 A 의 카운트. 두 값을 병치할 때 방법 차이 인지 필요. 정책 위반은 여전히 저장소 전반, 방향은 오히려 개선.
- 테스트: 92 파일 / 2,182 함수 (README `1,009건` stale 지속).
- 카탈로그: 108 TableSpec / 942 컬럼 (ARCHITECTURE `266/2822`, README `81/594` stale).

| # | 심각도 | 파일:줄 | 요약 |
|---|---|---|---|
| A8-1 | BLOCKER | `datamodel/decompose.py:191` | 델타 커밋 `00fb2c6` 이 이 파일을 만졌음에도 `date.today().isoformat()` 폴백 재유입. 부록 §2-1 의 재확증. ARCHITECTURE.md:43 "새 벽시계 참조 금지" 를 델타 자체가 위반. |
| A8-2 | BLOCKER | (전체) | **LICENSE 파일 없음**. Header 없음. `ls LICENSE* COPYING* COPYRIGHT*` 무결과. 267 `.py` 파일 중 첫 400 바이트에 License/Copyright/SPDX 있는 파일 0 개. `pyproject.toml` 두 곳 다 `license` 필드 없음. `numpy/pandas/scipy/scikit-learn/statsmodels/pydantic/jsonschema` 등 vendored. 배포 IP 상태 미정의. |
| A8-3 | BLOCKER | `.github/workflows/` | **CI 가 `validation-team-agent/` 만 커버**. 파일 하나 `validation-team-agent-ci.yml` 의 `paths:` 가 메인 `risk_lib/` 전량 제외. 2,182 top-level test 함수 CI 미실행. 2선 (리스크관리) 프로덕션에 pytest 게이트 부재. 3선 검증기만 게이트. |
| A8-4 | MAJOR | 24 파일 | 프로덕션 벽시계 recount: 24 파일이 여전히 `date.today()`/`datetime.now()`. `deliverables.py:101`, `validation/independent.py:655`, `archive.py:129,154`, `pipeline.py:1502`, `notifications.py:59`, `repro.py:238` (`repro` 라는 이름의 모듈이 `datetime.now(timezone.utc)` 리턴). |
| A8-5 | MAJOR | 3 파일 | `ValidationRequest` 중복 정의 3 곳: `risk_lib/validation/independent.py`, `validation-team-agent/src/vta/core/models.py`, `validation-team-agent/tools/run_validation.py`. 2선/3선 경계를 넘는 contract 가 세 독립 정의. drift 시 fail-closed 게이트 조용히 붕괴. |
| A8-6 | MAJOR | 2 파일 | `CapitalAction` 중복: `risk_lib/capital_simulation.py:37` vs `risk_lib/stress/ccar.py:67`. `stress/__init__.py:26,54` 는 ccar 것, `ops_pages/capital_stress.py:794` 는 다른 것 import. 필드 다른 두 dataclass 공존. 임포트 섞이면 조용히 잘못된 dataclass. |
| A8-7 | MAJOR | 2 파일 | `ColumnSpec` 중복: `risk_lib/datamodel/spec.py:45` vs `validation-team-agent/middleware/schema_guard.py`. 3선 guard 가 canonical schema 를 fork. `datamodel/spec.py` 변경이 전파 안 됨. |
| A8-8 | MAJOR | `datamodel/catalog.py` | 모듈 레벨 `ALL_TABLES` 를 :225, :430, :582, :684, :2245, :2487, :2667 에 7 회 재바인딩. import 시 마지막만 승리. partial import (submodule 이 최종 바인딩 전에 `ALL_TABLES` 읽기, 특정 줄에 monkeypatch 테스트) 는 잘린 카탈로그. |
| A8-9 | MINOR | README.md:251 | "13 개 서브에이전트" 여전. 실제 `.claude/agents/*.md` 55 파일 (risk 10, legal 12, RP 8, translation 3, design 6, brand/UI/marketing 4, engineering 4, others 8). drift 심화. |
| A8-10 | (clean) | (전체) | Secrets 스캔 clean. `api_key|password|token|secret|bearer|AWS_|AKIA|-----BEGIN` 모든 히트가 permission_guard regex, matrix JSON, test fixture, fraud var, 한글 조사 토큰화. 커밋된 자격증명 없음. |
| A8-11 | (clean) | (전체) | BOM 없음, non-UTF-8 없음, `__pycache__/`, `.pyc`, `.egg-info`, `.pytest_cache` git 무추적. 추적 바이너리 2 개만: `design-team/.../oneline-logo-reference.png`, `docs/flow.png` (305 KB, `427c4b4` 커밋, `tools/gen_flow_diagram.py` 로 재생성 가능). |
| A8-12 | (clean) | (전체) | TODO/FIXME/XXX/HACK grep 4 히트 총합, 모두 `tests/`/`tools/` 안 문자열 리터럴 ("XXX99", "CN-XXX") , 코드 주석 아님. 프로덕션 TODO 없음. 가장 깨끗한 시그널. |

## 부록 A 총평

99 신규 결함 중:

- **BLOCKER 11 건**: A2-1 (cross_form 항등 불변식), A3-1/A3-2/A3-3/A3-4/A3-5/A3-12 (자본·rating 6 건, Basel III 확정 표준 미반영), A4-1/A4-2 (rating boundary + audit chain NaN), A5-1/A5-2 (reproduce 파라미터 누락), A6-1/A6-2/A6-3 (validation-team-agent 3 건), A8-2 (LICENSE 부재), A8-3 (CI risk_lib 미커버).
- **MAJOR 66 건**: 규제 계산 정밀도, 정합성 통제, 결정성, 서식 이중 기록 등.
- **MINOR 19 건**: 문서 상충, 카운트 오류, 죽은 코드.
- **CLEAN 3 건** (A8-10/11/12): 보안·인코딩·TODO 는 통제 유지.

**가장 놀라운 결함**: **A8-3 CI 가 risk_lib/ 을 커버하지 않는다**. 이 리뷰가 지적해 온 모든 결함이 CI 게이트를 지나 landed 될 수 있다는 뜻이다. 43주차까지 매주 코드 리뷰를 하는 이유가 여기에 있다 (사후 통제). 사전 통제 (CI) 를 세우면 리뷰의 반은 자동화된다.

**두 번째로 놀라운 것**: **A8-2 LICENSE 부재**. 금융 리스크 하네스가 오픈소스 라이브러리를 vendored 하면서 자체 라이선스를 명시하지 않으면 배포·재사용 정합성 문제. 3선 감사 시 지적 사안.

**세 번째**: **A2-1 cross_form 항등 불변식**. 통과 카운트가 커버리지처럼 보이지만 falsifiable 하지 않다. PR #67 §1-2 지적한 spurious FAIL 과 결합하면 통과·실패 모두 정보 가치 없음.

## 리뷰 메타 (부록 A)

- 리뷰 도구: 8 개 병렬 서브에이전트 (general-purpose). 총 소요 약 592 초, 소비 토큰 약 1.37 M.
- 커버리지: risk_lib top 68 파일 + regulatory 15+ 파일 + alm/capital/rating/icaap/prudential 22 파일 + monitoring/limits/etc 20+ 파일 + harness/examples/tools/cli 15+ 파일 + validation-team-agent 103 파일 + tests 92 파일 + 전 저장소 정책 grep.
- 42주차 (PR #67) 8-병렬 sweep 이 60+ MAJOR 를 지적. 43주차 sweep 이 그 위에 99 신규를 추가 (일부는 확장·재확증, 대다수는 새 지점). 저장소 결함 밀도가 감소하지 않았고 오히려 발굴 여지가 남아있음을 확인.

---
_Generated by [Claude Code](https://claude.ai/code)_
