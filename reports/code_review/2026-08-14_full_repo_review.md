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

## 7. 리뷰 메타

- 리뷰 도구: 2 개 병렬 서브에이전트 (general-purpose). 총 소요 약 605 초, 소비 토큰 약 211k. `code-review` skill 은 델타 파일 수 (25) 가 skill 의 커버리지 기대치를 넘어 대신 서브에이전트 병렬 실행 방식 채택.
- 리뷰 커버리지: (A) PR #67 §1 의 6 개 BLOCKER 재점검, (B) 델타 8 커밋 전체 (25 파일, +3,428 / -264). §1-2 FSS 대사 6 개 앵커, §1-4 리스크 코어 4 개 앵커, §1-5 테스트 5 개 앵커 각각 grep 재검증.
- 자체검증 (2선), 상시 독립검증 (3선): 이 리뷰는 코드 리뷰이며 리스크 산출이 아님. RECALC_SCOPE 대상 아님.
- **다음 단계**: §6-1 훅 도입 (사흘 미이행), §6-2 decompose 벽시계 raise, §6-3 Pw9F5 warden 개입. §1-2 FSS 대사는 폼 감독당국 제출 전까지 반드시 정리 (3 주째 미이행).

---
_Generated by [Claude Code](https://claude.ai/code)_
