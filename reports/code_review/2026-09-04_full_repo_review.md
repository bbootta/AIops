# 저장소 전수 코드 리뷰 (2026-09-04, 47주차 · near-zero-delta)

**대상**: `bbootta/AIops` 전 저장소, base `origin/main` = `8ce5a34` 상당 (44 커밋 앞섬)
**직전 리뷰**: PR #84 (2026-09-03, 46주차)
**델타 창**: 2026-09-03 (PR #84 head `c750e93`) → 2026-09-04, **커밋 1건**
   - `e9d40cb 구 UI: 알림 상자 가운데 해설·이동 안내 13건을 지운다` (`ui_studio/app.py` -40 / +3)
**리뷰 방식**: 단일 세션 상세 스캔 (Agent 병렬·verify pass 없음). 스코프는 리스크 코어 (validation/consistency, validation/independent, capital, ncr, close_workflow, deliverables, ui_studio/studio, validation-team-agent/vta). UI-Next JS·registry·i18n 대량 델타는 PR #84 델타 리뷰에서 다뤘고 오늘 델타는 이 축을 건드리지 않으므로 이번 회차는 코어에 집중.

## 0. 총평 (한 문장)

델타가 사실상 없다 (구 UI 문구 정리 1건, -40/+3). 그러나 코어 재스캔에서 **`_not_run` 을 루프 안에서 호출하는 세 지점 (`consistency.py:513`, `:1071`+`:1088`, `:1640`) 이 val_check 기본키 (asof, check_name) 를 깨는 시스템성 패턴**이 드러났고, **`_check_ncr` (`consistency.py:1557`) 이 `is_identity=True` 없이 tautology 를 통제로 집계**하는 결함까지 합쳐 오늘 신규 결함 8건 (HIGH 5·MED 2·LOW 1) 을 기록한다. 46주차 PR #84 이 tracked BLOCKER 14건과 문서 층 회귀 (dash +478, 벽시계 +3) 을 이미 다뤘으므로, 이번 회차는 **이 8건이 PR #84 tracked 리스트 밖에 있는 델타 신규 후보** 라는 것이 유일한 새 정보다.

| 층위 | PR #84 (46주차) | 47주차 오늘 | 변화 |
|---|---|---|---|
| 델타 커밋 | 17 | **1** | -16 |
| 델타 삽입/삭제 | 대량 UI-Next | +3 / -40 | near-zero |
| PR #84 tracked BLOCKER 14 (LIVE 12·PART 1·FIXED 1) | 이번 스캔 미대상 | **무점검** | 유지 |
| 신규 결함 (본 회차 리뷰) | HIGH 0·MED 2·LOW 4·MIN 3 | **HIGH 5·MED 2·LOW 1** | 등급 상향 |
| 3선 `Pw9F5` dormant | 29일 | **30일** (누적) | +1 |
| em/en dash 회수 | 9,767 | 스캔 안함 (델타 무관) | ~ |
| 사전 커밋 훅 | 미배치 | 미배치 | **6주 연속** |

**최대 위험**: `_not_run` 을 루프 안에서 호출해 val_check 기본키 (asof, check_name) 를 조용히 깨는 패턴이 세 지점에서 동일하게 나타난다는 사실 자체다. 하나가 아니고 셋이면 이 라이브러리 규약 (`_not_run` 은 함수당 최대 1회) 이 명문화·강제되지 않았다는 뜻이고, 앞으로도 새 검사가 같은 방식으로 추가된다.

---

## 1. 즉시 조치 (HIGH · 델타 신규 후보)

**주의**: 이 5건은 오늘 스캔에서 재발굴한 항목이며, PR #78~#84 tracked BLOCKER 리스트 안에 이미 있는지 이번 회차에서는 확인하지 않았다. 다음 회차에서 tracked 재점검 시 중복 제거해야 한다.

### 1-1. HIGH · `_check_delta_eve_recalc` 가 val_check PK 를 두 지점에서 깬다

**파일**: `risk_lib/validation/consistency.py:1071`, `:1088`

`for (basis, sc, ccy), g in bp.groupby(...)` 안에서 `shk is None` 이면 `_not_run(report, "delta_eve_recalc", ...)` 를 부르고 `continue`. `_not_run` (`:70~:79`) 은 `ConsistencyCheck("delta_eve_recalc_not_run", "WARN", ...)` 을 만든다. 같은 이름이 여러 번 나온다.

**실패 시나리오**: `shocked` 에 `(USD, adverse)`, `(EUR, adverse)` 두 조합의 충격곡선이 빠지면 `_not_run(..., "delta_eve_recalc", "shk is None")` 이 두 번 실행되어 val_check 에 `delta_eve_recalc_not_run` 행이 2개 쌓인다. `datamodel/catalog.py:651` 이 `val_check` 를 `primary_key=("asof", "check_name")` 로 잡고 있고, `datamodel/spec.py:247` 이 `pk_unique` 위반을 `schema_validation.csv` 로 낸다. 3선이 자체검증 원장을 읽지 못하는 상태가 된다.

같은 함수의 :1088 (`got is None`) 도 동일 패턴이다.

**시정**: 루프 밖에서 발생한 리스트를 모아 하나의 `ConsistencyCheck("delta_eve_recalc_not_run", "WARN", f"…{n}개 스킵")` 로 접거나, 이름을 `delta_eve_recalc_not_run_{ccy}_{sc}` 로 분할한다. 후자는 이름 폭발 위험이 있으므로 전자를 권한다.

### 1-2. HIGH · `_check_market_op_rwa` 가 val_check PK 를 깬다 + 어느 쪽이 스킵됐는지 못 본다

**파일**: `risk_lib/validation/consistency.py:513`

```python
for label, val, zero_status in [("market_rwa_nonneg", market_rwa, "WARN"),
                                ("op_rwa_nonneg", op_rwa, "FAIL")]:
    if val is None:
        _not_run(report, "market_op_rwa", "val is None")
        continue
```

`market_rwa=None, op_rwa=None` 인 부분 실행/독립 재계산에서 `market_op_rwa_not_run` 이 두 번 append 된다. 게다가 이름이 공유돼 있어 어느 축이 스킵됐는지 원장에서 알 수 없다.

**시정**: `_not_run(report, f"{label}", "val is None")` (기존 label 을 그대로 씀). 이러면 이름이 자연히 갈라진다 (`market_rwa_nonneg_not_run` / `op_rwa_nonneg_not_run`).

### 1-3. HIGH · `_check_doc_figures` 가 val_check PK 를 깬다

**파일**: `risk_lib/validation/consistency.py:1640`

```python
for doc in doc_paths:
    if not Path(doc).exists():
        _not_run(report, "doc_figures", "not Path(doc).exists()")
        continue
```

`doc_paths` 에 세 개가 있고 두 개가 disk 에 없으면 `doc_figures_not_run` 이 두 번 쌓인다.

부수 결함: `studio.py:242` 이 이 이름 하나만 dedup 대상으로 잡는다 (`| {"doc_figures_not_run"}`) — 위 시정을 하면 studio 의 dedup 도 함께 손봐야 한다.

**시정**: 위 1-2 와 같은 원리, 또는 리스트로 접기.

### 1-4. HIGH · `_check_stress_trough_requirement` 가 tiers 가 비면 조용히 PASS 를 낸다 (fail-open)

**파일**: `risk_lib/validation/consistency.py:1365~:1381`

```python
tiers = [(k, col) for k, col in tiers
         if col in path_df.columns and k in req_all]
breached = []
for sc, g in path_df.groupby("scenario", sort=False):
    for k, col in tiers:
        …
seen = "·".join(k for k, _ in tiers) or "없음"
if not breached:
    report.add(ConsistencyCheck(
        "stress_trough_meets_requirement", "PASS",
        f"전 시나리오 저점 >= 요구치 (비교 계층 {seen})"))
    return
```

**실패 시나리오**: `path_df` 가 `cet1_ratio`·`tier1_ratio`·`total_ratio` 를 하나도 안 들고 있는 부분 스트레스 경로 (예: 초기 프로토타입, `rwa_total` 만 있는 레거시 경로) 이거나 `bis_result.required` 가 비면 `tiers=[]`. 내부 for 루프가 아예 안 돌아 `breached=[]`. 검사가 `stress_trough_meets_requirement · PASS · "전 시나리오 저점 >= 요구치 (비교 계층 없음)"` 를 낸다. **결재선에는 "위기 요구치를 통과했다" 로 읽힌다**. 코드는 통과 판단을 아무것도 하지 않았다.

**시정**: `if not tiers: _not_run(report, "stress_trough_requirement", "tiers empty (path_df에 tier 컬럼 없음 또는 required 비어있음)"); return` 를 for 루프 앞에 넣는다.

### 1-5. HIGH · `_check_ncr` 의 identity 검사가 tautology 인데 `is_identity=False` 로 통제 건수에 잡힌다

**파일**: `risk_lib/validation/consistency.py:1548~:1561`

```python
expected = ((noc.net_operating_capital - risk.total)
            / ncr_result.required_capital)
grade = prompt_action_grade(ncr_result.ncr)
problems = []
if abs(ncr_result.ncr - expected) > 1e-9 * max(1.0, abs(expected)):
    problems.append(...)
if str(ncr_result.action) != str(grade):
    problems.append(...)
report.add(ConsistencyCheck(
    "ncr_identity", "FAIL" if problems else "PASS",
    ..., metric=float(ncr_result.ncr)))
```

`compute_ncr` (`ncr.py:213~:219`) 이 `surplus = noc.net_operating_capital - risk.total; ncr = surplus / req; action = prompt_action_grade(ncr)` 로 만들었다. 이 검사의 `expected` 와 `grade` 는 그 산식·그 호출 그대로다. **`abs(ncr - expected)` 는 언제나 0**, **`str(action) != str(grade)` 도 언제나 False** (같은 함수를 같은 값으로 부른다). 검사는 구성상 반드시 PASS.

그런데 `ConsistencyCheck.is_identity` 는 기본값 `False` (`consistency.py:31`). 이 검사는 `is_identity=True` 로 표시되어 있지 않다. `ValidationReport.controls_summary` (`:59~:62`) 가 `is_identity` 를 걸러내지만 이 항목은 걸러지지 않고 통제 PASS 로 계산된다. **결재선에 "통제 63건 PASS" 라는 숫자가 뜨면 그 중 한 건은 자기 자신을 자기 산식으로 다시 계산한 항목이다**. 규제 관점에서는 독립 재계산 아님.

**시정 (택 1)**:
- (a) 이 검사를 삭제한다. 값이 없다.
- (b) 이름 그대로 유지하고 `is_identity=True` 로 표시한다. 통제 건수에서 빠져 사실을 반영한다.
- (c) 재계산 산식을 다른 경로로 뽑는다 (예: `licenses` 를 다시 파싱해 `required_capital` 을 두 번째 구현으로 재산출). 이게 진짜 독립 대사다.

부수 관측: `market_op_rwa`·`delta_eve_recalc`·`doc_figures` 계열 시정과 함께 val_check 원장이 통제 건수를 정확히 반영하도록 한 회차에 묶어 처리하는 것이 자연스럽다.

---

## 2. MEDIUM · 델타 신규 후보

### 2-1. MED · `build_deliverables` 가 2선/규제 hold 를 3선 pending 으로 상승 표시

**파일**: `risk_lib/deliverables.py:222~:227`

```python
if require_gate:
    studio.iv_gate.require()          # 3선 게이트가 승인이면 통과
    if hold:                          # 그런데 val_check FAIL / blocks_approval 이 있으면
        raise IndependentValidationPending(...)
```

`hold = approval_hold_reasons(tables, studio.iv_gate)` (`ui_studio/governance.py`) 는 3선 게이트 이외에도 2선 FAIL, `blocks_approval=True` WARN (예: bis buffer shortfall) 을 포함한다. 3선이 `적합` 인 경우에도 `hold` 가 남아있으면 `IndependentValidationPending("결재 차단 사유가 남아 있다: 자체검증 FAIL 1건")` 을 던진다. 예외 클래스 이름을 보는 사람 (로그, 운영 알람) 은 "3선 응답이 안 왔다" 로 읽지만 실제는 2선/규제.

**시정**: `ApprovalHoldError` 같은 상위 게이트 예외를 하나 두고, `IndependentValidationPending` 는 그것을 상속한 3선 전용 하위 예외로 둔다. `require()` 는 `IndependentValidationPending` 을, hold-남음 분기는 `ApprovalHoldError(hold)` 를 던진다.

### 2-2. MED · `build_request` 가 `blocks_approval` 을 identity-포함 프레임에서 센다 (silent drift 위험)

**파일**: `risk_lib/validation/independent.py:606~:613`

```python
ctrl = (checks[~checks["is_identity"].astype(bool)]
        if "is_identity" in checks.columns else checks)
summary = {k: int(v) for k, v in ctrl["status"].value_counts().items()}
if "blocks_approval" in checks.columns:
    n_block = int(checks["blocks_approval"].astype(bool).sum())   # <-- ctrl 아님
    if n_block:
        summary["규제미달"] = n_block
```

지금은 identity 검사가 `blocks_approval=True` 로 설정되지 않아 결과가 우연히 일치한다. 앞으로 identity 검사가 하나라도 `blocks_approval=True` 를 갖게 되면 이 요청서의 `규제미달 n건` 이 `ValidationReport.controls_summary()` 가 세는 값과 갈라진다. 3선이 보는 요청서와 사내가 보는 요약이 다르면 회귀가 소리 없이 통과한다.

**시정**: `n_block = int(ctrl["blocks_approval"].astype(bool).sum())`.

---

## 3. LOW

### 3-1. LOW · `compute_ncr_from_result(result, seed=99)` 가 seed 를 조용히 무시

**파일**: `risk_lib/ncr.py:285~:295`

캐시된 `result.ncr` 을 그대로 돌려주므로 캐시가 있으면 `seed` 는 무의미. docstring 이 캐시 우선을 명시하지만 파라미터가 남아있어 "다른 seed 로 다시 뽑는다" 가 안 된다는 사실이 시그니처만 보고는 안 보인다. 디버깅/테스트에서 잘못된 답을 소리 없이 받는다.

**시정 (택 1)**: seed 인자를 제거, 또는 `cached is None` 인 경로에서만 쓴다는 것을 시그니처에서 분리 (예: `compute_ncr_from_result` 는 seed 없이, 캐시 무시가 필요하면 `synthesise_securities_firm(result, seed=…)` 를 직접 부른다).

---

## 4. 각하 (스캔에서 후보로 나왔으나 리뷰가 각하)

- **`ivr_response.py:1462`** — 파일이 193줄. 라인 참조 자체가 허위. 스캔이 만들어냈다. (참고: `validation-team-agent/tools/ivr_response.py` 는 실재하지만 짧다.)
- **`independent.py:176`** — `DEFAULT_DIR` 을 인계 대상 경로로 하드코딩하는 것은 브랜치간 인계 계약상 의도로 보인다 (docstring `<directory>/outbox/…` 는 로컬 아웃박스, 대상은 3선 브랜치의 고정 경로). 각하.
- **`studio.py:242`** — `check_doc_figures` 가 문서별로 다른 이름을 낸다는 규약을 지키면 동작한다. 규약이 깨질 때만 문제. 지금은 관측 가능한 실패 없음. 각하 (§1-3 시정 시 이 지점도 함께 점검).

---

## 5. 재요구 권고 (46주차 PR #84 §6 미이행 항목)

이번 회차가 tracked BLOCKER 재점검을 하지 않았으므로 PR #84 §6 을 그대로 이어받는다.

1. **사전 커밋 훅 두 개 (em/en dash 차단, 벽시계 차단) 배치**. **6주 연속 미이행**. 매주 되돌아온다는 것이 회귀 데이터로 확정됐다.
2. **`risk_lib/datamodel/decompose.py:191` 즉시 raise**. 5주 연속 미이행.
3. **`_not_run` 을 루프 안에서 부르면 CI 가 실패하도록 하는 lint 규칙 (신규 요구)**. 위 §1-1, §1-2, §1-3 이 같은 패턴이다. 라이브러리 규약이 강제 없이 문서에만 있으면 다음 검사에서도 재발한다.
4. **§1-5 `ncr_identity` 를 `is_identity=True` 로 표시하거나 진짜 독립 대사로 재구현 (신규 요구)**.

---

## 6. 리뷰 메타

- 단일 세션 상세 스캔, 약 55k 토큰. Agent 서브에이전트 병렬·verify pass 없음.
- 스코프: `risk_lib/validation/{consistency,independent}.py`, `risk_lib/{ncr,deliverables}.py`, `risk_lib/ui_studio/studio.py`, `validation-team-agent/tools/ivr_response.py`, `validation-team-agent/tools/independent_recalc.py`.
- 델타가 near-zero (1 커밋 -40/+3) 라 UI-Next 대량 델타 (registry·i18n·JS) 는 이 회차에서 재리뷰 안함. PR #84 델타 리뷰가 유효.
- 자체검증 (2선), 상시 독립검증 (3선): 이 리뷰는 코드 리뷰이며 리스크 산출 아님. `RECALC_SCOPE` 대상 아님.
- 스캔 도구가 §4의 `ivr_response.py:1462` 처럼 존재하지 않는 라인을 만들어냈으므로, 다음 회차부터 verify pass (원문 대조) 를 리뷰 파이프라인에 넣을 것을 권장한다.
