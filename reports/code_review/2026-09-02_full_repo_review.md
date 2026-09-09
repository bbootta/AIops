# 저장소 전수 코드 리뷰 (2026-09-02, 45주차)

**대상**: `bbootta/AIops` 전 저장소, base `origin/main` = `60bda57`, 리뷰 브랜치 `claude/stoic-ride-flvnxv` HEAD = `9814480`
**직전 리뷰**: 2026-09-01 (44주차), `reports/code_review/2026-09-01_full_repo_review.md` (PR #82)
**델타 창**: 2026-09-01 (`454a95e`) → 2026-09-02 (`9814480`), 7 커밋 (+ merge 제외), +48,131 / -287, 134 파일
**리뷰 방식**: 4 개 서브에이전트 병렬. (A) 44주차 tracked BLOCKER 14 건 재점검, (B) 델타 3e69926·a69e374·e75d564·UI-Next 3 커밋 각각 별 서브에이전트, (C) 저장소 전수 정책 감사 (em/en dash, 벽시계, 사전 커밋 훅 배치)

## 0. 총평 (한 문장)

44주차에 지적된 재발 방지 권고 3 건 중 두 개 (사전 커밋 훅, `decompose.py:191` 즉시 raise) 는 여전히 미이행이나, **세 번째 (3선 `RECALCULATORS` 확장) 은 실질 착수** (`6→10`, 커버리지 29% → 48%) 했고 별개로 델타 커밋 3e69926 이 **44주차 §1-7 tracked 항목 중 `_RW_CORPORATE["B"]` 를 150% 로 정정**하여 44주차 리뷰가 처음으로 통제로 작동한 흔적을 남겼다. 다만 델타 커밋 a69e374 (결재 경로 fail-closed) 는 광범위한 재작업임에도 `_check_ncr` institution_type 미상 시 fail-open, `dispatch_request` 스테일 요청 파일 재기록 부재, `deliverables.require_gate=True` 가 조건부 결재 자체를 원천 차단, `close_workflow._evidence_done` 이 `ConditionalApproval` 없이도 "조건부" 를 완료 처리 등 **신규 게이트 표면에 fail-open 6 지점, 계약 모순 2 지점** 을 새로 열었다.

| 층위 | 44주차 | 45주차 | 변화 |
|---|---|---|---|
| Tracked BLOCKER (§1, 14 샘플) | 12 LIVE / 1 PARTIAL / 1 FIXED | 12 LIVE / 1 PARTIAL / 1 FIXED (신규 1 FIXED 반영) | 실질 -1 LIVE, +1 FIXED |
| 벽시계 리크 파일·회수 (production) | 37 파일 / 50 회 | 38 파일 / 49 회 | +1 파일 / -1 회 (미개선) |
| em/en dash 총합 | 9,787 회 / 639 파일 | 9,289 회 / 638 파일 | **-498 회 / -1 파일 (개선)** |
| 델타 신규 결함 | MAJOR ×10, MINOR ×10 | HIGH ×5, MEDIUM ×6, LOW ×2, MINOR ×2 | 신규 15 |
| 3선 RECALCULATORS 커버리지 | 6/21 (29%) | 10/21 (48%) | **+4 (5주 만에 첫 착수)** |
| 사전 커밋 훅 | 미배치 | 미배치 | 무변동 (4주 연속) |

**최대 성과 (기록)**:

1. 5 주 연속 미이행이던 `RECALCULATORS` 확장이 착수됨 (`rwa_final_total`, `total_ratio`, `ecl_total`, `reserve_shortfall` 4 종 추가). 다만 아래 §2-3 HIGH 3 건은 새 코드 표면에서 발생.
2. `_RW_CORPORATE["B"]=1.50` 정정. CRE20.34 정합.

**최대 위험 두 개 (변동 없음)**:

1. 사전 커밋 훅 4주차 무이행. 이번 회차 em/en dash 는 개선 (-498) 되었으나 이는 델타 커밋 aec94b8 이 테스트 파일 다수를 손봐서 부수적으로 소거된 결과이지 자동화의 힘이 아니다. 다음 커밋에서 다시 증가할 가능성 상존.
2. `datamodel/decompose.py:191` 즉시 raise 재요구 2주 연속 미이행.

## 1. 즉시 조치 (Tracked BLOCKER 재점검, 14 샘플)

44주차 §1 및 §1-7 항목에서 델타 커밋이 직접 만지거나 관련성 높은 14 건 샘플 재검증.

| # | 항목 | 상태 | 근거 |
|---|---|---|---|
| 1 | `risk_lib/pipeline.py:1505` 벽시계 폴백 | **LIVE** | `asof = date.today()` 그대로 (앵커 :1502→:1505 드리프트만 발생) |
| 2 | `risk_lib/datamodel/decompose.py:191` 벽시계 폴백 | **LIVE** | `date.today().isoformat()` 그대로. 44주차 §6-2 명시 재요구 미이행 |
| 3 | `risk_lib/capital/rwa_sa.py` B 등급 RW | **FIXED (정확)** | :48 `_RW_CORPORATE["B"]=1.50`. CRE20.34 정합. Sovereign / Bank B 는 1.00 유지 (기준상 B- 미만만 150% 이므로 44주차 지적이 오히려 부정확했음, :39-42 코멘트로 명시). 3e69926 의 정정은 정확 |
| 4 | `risk_lib/capital/rwa_deep.py:268-274` FIRB_LGD 0.45 | **LIVE** | :291-293 `np.where(...)` 하드코딩 0.45 그대로. Basel III 확정 0.40 미반영 |
| 5 | `risk_lib/capital/rwa_irb.py:40-41` LGD 하한 코멘트 | **LIVE** | "the harness does not auto-floor LGD" 그대로. 하한 미적용 불변 |
| 6 | `risk_lib/models/rating.py:49` bisect off-by-one | **LIVE** | `bisect.bisect_left(uppers, pd_value)` 그대로. 경계 처리 없음 |
| 7 | `risk_lib/integrations.py:302-314` IsolatingDispatcher | **LIVE** | :303-304 `key` 계산 후 dedup 미사용. 재시도가 sleep/backoff/jitter 없이 back-to-back |
| 8 | `limits/limit_engine.py:41-47` vs `limits/limits_deep.py:56-62` 방향 반전 | **LIVE** | (CRITICAL ≥ 1.20, BREACH ≥ 1.00, WARN ≥ 0.90) vs (BREACH ≥ 1.00, CRITICAL ≥ 0.90, WARN ≥ 0.75). 동일 로우 정반대 의미 |
| 9 | `risk_lib/op_loss.py:88` NaN 오염 | **LIVE** | `float(lognet.std() or 1.0)` 그대로. NaN truthy → `nan or 1.0 == nan`, VaR/ES 오염 |
| 10 | `risk_lib/regulatory/cross_form.py:38-49, 51, 61, 70` | **LIVE** | 누락 등록 6 종 (B2506/3000, B2403/1010 등) 전량 미등록. tolerance default 1.0 KRW 유지. BR-31 포지셔널 line code (1110/1510) 유지. ECL 합계 참조 오류 (`1020` vs `1010`) 유지 |
| 11 | `risk_lib/validation/independent.py:215-222` `Finding` severity `__post_init__` | **LIVE** | `@dataclass(frozen=True)` 에 `__post_init__` 없음. :257 `Finding(**f)` 여전히 검증 없이 삽입. severity 오타는 여전히 게이트 뒤집는다. e75d564 는 이 파일 미터치 (a69e374 가 다른 부분을 터치했으나 `Finding` dataclass 는 손대지 않음) |
| 12 | `validation-team-agent/tools/independent_recalc.py:RECALCULATORS` | **PARTIAL (실질 진전)** | :230-253 이제 10 개 (`lcr, nsfr, cet1_ratio, leverage_ratio, icaap_ratio, portfolio_default_rate, rwa_final_total, total_ratio, ecl_total, reserve_shortfall`). RECALC_SCOPE 21 중 48%. 미커버 11 개: `rwa_fund, rwa_securitisation, ecl_weighted_total, irrbb_*, survival_days, stress_trough_cet1, reverse_critical_severity, kr_irrbb_table6_*, lgd_backtest_*, ccf_realised_mean` |
| 13 | 사전 커밋 훅 (em-dash, 벽시계) | **LIVE** | `.git/hooks/pre-commit` 부재, `.pre-commit-config.yaml` 부재, `.claude/settings.json` 에 `hooks` 키 부재. 4주 연속 |
| 14 | `consistency.py:_check_market_portfolio_split` WARN 우회 | **LIVE (의도 유지)** | :537-540 `market_positions is None or market_rwa is None` 시 여전히 WARN. `ValidationReport.passes()` (:45-46) 는 FAIL 만 차단. a69e374 가 `blocks_approval` 플래그 (:35) 를 도입했으나 이 WARN 에는 세팅되지 않음. 44주차 §2-1 M3 로 지적한 fail-open 경로 존치 |

**총 재점검**: 14 건 중 **1 FIXED (신규) / 1 PARTIAL (신규 진전) / 12 LIVE**. 44주차 대비 실질 개선 2 건. 44주차 §1 전체 (57 LIVE / 1 PARTIAL / 1 FIXED) 로 확장 추정 시 **약 55 LIVE / 2 PARTIAL / 2 FIXED**.

## 2. 델타 신규 결함 (45주차 신규)

델타 3e69926, a69e374, e75d564 및 UI-Next 3 커밋을 4 개 서브에이전트로 병렬 심사. 신규 15 건 발굴.

### 2-1. 델타 3e69926 (검수 5단계: RW 정정 · 상수 파라미터화)

| # | 파일:줄 | 등급 | 요약 | 재현 시나리오 |
|---|---|---|---|---|
| D1 | `risk_lib/capital/rwa_sa.py:15,48` | HIGH | 등급 버킷 조립이 BB- 를 "BB" 로 묶어 100% 를 부여. CRE20.34 는 BB- 미만을 150% 로 요구. 3e69926 의 corporate B 정정은 정확하나, 인접 BB- 미커버 | 차주 등급 "BB-" → `rating="BB"` (버킷) → RW 100%. Basel 대비 50pp 과소 가중 |
| D2 | `risk_lib/ccr.py:85-92` | MINOR | `saccr_rwa` docstring 이 "상대방 등급 미사용, BBB 50% 고정" 을 명시하나 `bank_rw` kwarg override 열려 있어 계약 불일치 | 호출자가 `bank_rw=0.20` 전달 시 실행됨. "규정값 아님" 코멘트와 모순 |

3e69926 자체는 대부분 하드코딩 상수를 `references.INTERNAL_ASSUMPTION` 로 옮긴 리팩터링. `test_formula_corrections.py` (신설 92 줄) 이 정정 지점을 잠금. Fail-open 회귀 없음.

### 2-2. 델타 a69e374 (검수 1~4단계: 결재 경로 fail-closed)

| # | 파일:줄 | 등급 | 요약 | 재현 시나리오 |
|---|---|---|---|---|
| D3 | `risk_lib/validation/consistency.py:_check_ncr` | HIGH | `meta["institution_type"]` 미상 시 NCR < 100% 여도 `blocks_approval=False` WARN. 코멘트가 fail-open 을 자인 ("어느 쪽인지 모르면 참고치") | 증권사 스코프 파이프라인 caller 가 `meta["institution_type"]` 미설정 → NCR=80% → WARN "참고치", 결재 승인 |
| D4 | `risk_lib/validation/consistency.py:_check_ncr` | MEDIUM | `try: regime = _inst.prudential_regime(...) except ValueError: regime = None` 좁은 except. `KeyError`/`TypeError` 발생 시 전체 `run_consistency_checks` abort | 미등록 institution_type 조회 시 `KeyError` → 전체 val_check 리포트 소실 |
| D5 | `risk_lib/validation/independent.py:dispatch_request` | HIGH | `if not src.exists(): src = request.write(d)` 로 스테일 요청 파일 재기록 안 함. 같은 run_id 안에서 재실행 시 outbox 사본과 dispatch.json 이 불일치 | 재실행으로 request_id/digest 변경 → 디스크에 예전 `.request.json` 잔존 → 3선이 예전 내용을 받고 dispatch.json 은 새 request_id 를 기록 |
| D6 | `risk_lib/close_workflow.py:_evidence_done` | HIGH | `_GATE_APPROVED = ("적합", "조건부")` 로 CL-10 완료 판정. Gate.approved 는 "적합" 만 True, "조건부" 는 `ConditionalApproval` 필요. CL-10 "완료" 는 실제 상태를 오도 | 3선 경부적합 → status="조건부", `ConditionalApproval` 미기록 → CL-10 완료 표시. CL-11 이 별도로 차단하므로 결재 leak 은 없으나 원장 표시 오도 |
| D7 | `risk_lib/deliverables.py:222-227` | HIGH | `studio.iv_gate.require()` 가 `conditional` 인자 없이 호출되어 정상 조건부 결재도 원천 차단. `cli deliverables --require-gate` 로 조건부 결재 패키지 생성 불가 | 결재 책임자가 정상 ConditionalApproval 기록 → CLI 는 여전히 `IndependentValidationPending` raise |
| D8 | `risk_lib/validation/consistency.py:_check_pillar2_evidence` | MEDIUM | p2r/p2g 부재 시 무조건 `blocks_approval=True`. `data_gen_intl.pillar2_for` 가 미구성 institution 에 `{"p2r": None, "p2g": None}` 반환 → 그런 institution 은 결재 원천 차단 | P2R/P2G 미구성 profile 로 합성 실행 → "approval possible with WARN" 에서 "approval blocked" 로 조용히 격상 |
| D9 | `risk_lib/validation/independent.py:build_request` | MEDIUM | `summary` 는 `ctrl = checks[~is_identity]` 사용, 그러나 `n_block = int(checks["blocks_approval"].astype(bool).sum())` 은 unfiltered `checks` 사용. 의미 불일치 | 향후 `is_identity=True` + `blocks_approval=True` 조합 (구성 실수) 발생 시 "규제미달" 카운트 부풀림, per-status 총계에는 미출현 |
| D10 | `risk_lib/validation/consistency.py:_check_large_exposure_sources` | MEDIUM | `any_breach = n_ledger > 0 or bool(n_engine)` 가 `n_engine=None` (미실행) 을 `n_engine=0` (깨끗) 과 동일 취급 | 한도 엔진 미실행 (구성 실수) + ledger 우연히 clean → `blocks_approval=False`, 결재 승인 |

**성과 (기록)**: `_not_run` WARN 패턴 (:70-79), `blocks_approval` 컬럼 (:35), `ConsistencyCheck.is_identity` (:36), CL-11 approval_hold_reasons 조립, `dispatch_request` 아웃박스 사본과 dispatch.json 페어링은 구조적으로 옳게 설계. 신설 테스트 (`test_approval_blockers.py`, `test_approval_gate_path.py`, `test_close_gate.py`) 이 happy/blocked 브랜치를 커버.

### 2-3. 델타 e75d564 (적합성검증 팀에이전트 자기 점검)

| # | 파일:줄 | 등급 | 요약 |
|---|---|---|---|
| D11 | `tools/gen_regulatory_criteria.py:558` | HIGH | `rule_id = f"KR-{idx:03d}"`/`f"BIS-{idx:03d}"` 를 단일 enumerate 카운터로 부여. CRITERIA 에 새 로우 삽입 시 이후 모든 KR-NNN/BIS-NNN 재넘버링. 44주차 §2-1 M7 재발. 커밋 메시지가 "KR-020·KR-043 자동" 을 인용하는데 그 id 는 다음 삽입 때까지만 유효 |
| D12 | `tools/independent_recalc.py:recalc_rwa_final_total:140~165` | HIGH | `floor_factor` + `standardised_rwa_total` 둘 다 미제공 시 성분 합만 반환. 내부모형 사용 은행 (floor bind 필요) 의 clained value = 내부 합 이면 조용히 통과. `test_rwa_total_without_floor_inputs_is_the_plain_sum` 이 이 동작을 잠금 |
| D13 | `tools/ivr_response.py:98~101` + `harness/ivr_response.schema.json:29~33` | HIGH | recalc mismatch 는 "same target 의 중부적합 finding" 이 설명하면 통과하나 schema 가 `recomputed`/`reported` 를 optional 로 두어 내용 없는 `{"finding_id": "F-x", "severity": "중부적합", "target": "cet1_ratio", "detail": "TBD"}` 로 mismatch 무력화 가능 |
| D14 | `src/vta/handlers/registry.py:872~876` | MEDIUM | `alm_handler` 가 `alm_won_ltd` 파싱 실패 시 early return `{}`. 위에서 성공한 `maturity_gap`/`funding_concentration`/`loan_to_deposit` 결과 손실. 전체 스텝이 "skipped" 로 오보고 |
| D15 | `tools/independent_recalc.py:recalc_ecl_total, recalc_total_ratio` | MEDIUM | 두 recalc 는 caller 가 이미 스테이징한 값의 합/비율만 확인. 스테이지 분류 오류 (스테이지-3 ECL 오산) 는 양측이 같은 버킷을 받아 조용히 통과. registry 에 `aggregation_only` 로 명시 필요 |
| D16 | `harness/ivr_response.schema.json:22` | LOW | finding severity enum 에 "적합" 포함. `derive_verdict` 가 "적합" severity finding 만 있으면 verdict "적합" 도출. "적합 finding" 은 의미 노이즈. `["경부적합","중부적합"]` 로 제한 필요 |
| D17 | `harness/ivr_response.schema.json` `finding_id` | LOW | `minLength:1` 만 요구. 안정 인용 스타일 id (`IVR-...-F001`) 강제 필요 |

### 2-4. 델타 UI-Next (ecdedd5 + 0cb0312 + 9814480)

신설 `risk_lib/ui_studio/next/` 패키지 (11 화면 · i18n · registry · payload_ext · render), 신설 테스트 `test_ui_next.py` (1035 줄) · `test_ui_next_browser.py` (768 줄).

**심사 결과**: 게이트 전파 (fail-closed), 벽시계 (0 지점), i18n 경계 (import-time 강제), XSS 표면 (`textContent`/`createTextNode` 만 사용), 수치 리터럴 규율 (`test_payload_ext_carries_no_regulatory_literal` 이 `{"0.0","1.0"}` 외 float 리터럴 금지) 모두 옳게 설계·잠금. 테스트가 존재-only assertion 이 아니라 실제 불변식 (`test_self_tally_partitions_val_check_exactly_once`, `test_pending_gate_is_reported_as_pending`, `test_a_foreign_response_is_procedural_not_substantive`, `test_build_ext_never_reads_the_response_itself`) 을 검증.

| # | 파일:줄 | 등급 | 요약 |
|---|---|---|---|
| D18 | `risk_lib/ui_studio/next/render.py:66` | MINOR | 정적 파일 부재 시 warn + `""` 반환. `screens/*.js` 우발적 삭제 시 스크립트 없는 페이지가 조용히 렌더. raise 로 전환 |

## 3. 델타 라운드 긍정 (기록)

부정만 나열하면 실체가 왜곡된다. 45주차에 실제로 landed 한 것.

- **`risk_lib/capital/rwa_sa.py:_RW_CORPORATE["B"]=1.50`** (3e69926): 44주차 §1-7 로 지적한 tracked 항목 첫 정정. CRE20.34 정합. `test_formula_corrections.py` 로 잠금.
- **`validation-team-agent/tools/independent_recalc.py:RECALCULATORS` 6→10** (e75d564): 5주차 무이행이던 §6-3 착수. 신설 4 개는 자체 구현 (grep 확인, `src/vta/domains` 나 `tools/risk_checks` 미import).
- **`risk_lib/ui_studio/next/`** (ecdedd5·0cb0312·9814480): 새 UI 셸이 game 아닌 gatehouse. `_x_gate` 가 `Studio.iv_gate` 만 읽고 `overall.tone` 을 fail-closed 로 조립. 응답 파일 자체는 셸이 열지 않음 (`test_build_ext_never_reads_the_response_itself` 로 강제).
- **`risk_lib/validation/consistency.py`** 재작업 (a69e374): `_not_run` WARN 패턴 · `blocks_approval` 컬럼 · `is_identity` 태깅. 44주차 §1-2 로 지적한 "WARN 이 게이트를 통과한다" 문제의 구조적 처방. 다만 §2-2 D3/D6/D7/D8/D10 은 이 처방의 표면에서 발현.
- **`validation-team-agent/tools/ivr_response.py`** 신설 (e75d564): 3선이 손으로 쓰던 응답 JSON 을 하니스가 조립 · 검증 · 서명 없이 outbox 로 보내는 자동화. 응답 오탈자로 인한 게이트 뒤집기 위험 감소 (다만 §2-3 D13 로 새 우회 표면).
- **`risk_lib/governance/run_issue.py`** 신설 (a69e374): approval_hold_reasons 원장 구조화.
- **`.claude/agents/alm-analyst.md`** 신설, 13 개 에이전트 정의를 실코드 정합으로 재정렬 (d3550d6).

## 4. MAJOR (누계·미소화)

42주차 §2 의 60+ 건, 43주차 §2·§A 의 99+ 건, 44주차 §2 의 20 건 전량 미소화 상태 유지. 45주차 델타에서 추가로 관찰된 것은 §2 신규 15 건이 이에 해당.

44주차 §2-1 M3 로 지적한 "WARN 은 게이트를 통과한다" 문제는 a69e374 가 `blocks_approval` 컬럼과 `_not_run` 패턴을 도입해 구조적으로 처방했으나, 새 게이트 표면에서 §2-2 D3/D6/D7/D8/D10 로 재발. 처방의 실행 표면이 여전히 fail-open 로 기울어 있음.

## 5. PR ownership 상태 (매주 확정)

- **`claude/stoic-ride-flvnxv`** (현재 리뷰 브랜치): 45주차 리뷰가 여기로 실림. head `9814480`.
- **`claude/stoic-ride-u3mmwj`** (44주차 리뷰): PR #82, `454a95e` 기준, 병합 없이 draft 유지. base branch 는 45주차 델타 (`60bda57` → `9814480`) 로 이동했으나 PR #82 자체는 갱신 없음.
- **`claude/validation-team-agent-Pw9F5`** (3선): e75d564 실린 브랜치. 45주차에서 `RECALCULATORS` +4 착수로 dormancy 해제 · 실질 진전.
- **`claude/risk-management-agent-harness-B9Kxm`**: 델타 7 커밋에 무커밋. **27일간 dormant** (44주차 26일에서 +1). Warden 개입 조건 성숙 (44주차 이미 14일 초과).
- **PR #46, #38, #57**: 44주차 대비 무변동, dormancy 유지.
- **44주차 이전 PR #49~PR #82 (전 34 개 review PR)**: 병합 없이 모두 draft 상태. 이번 45주차 PR 신설로 총 35 개.

## 6. 권고 (재발 방지)

우선순위대로 세 개. 이번 회차에 §6-3 만 실질 착수했으므로 §6-1·§6-2 는 5주차·3주차 재요구.

### 6-1. 사전 커밋 훅 두 개 (**44주차 §6-1 재요구, 4주 연속 미이행**)

이번 회차는 부수적으로 em/en dash -498 회. 훅이 없으면 다음 커밋에서 다시 오를 것.

```bash
# (1) em/en dash 차단
if git diff --cached --name-only | xargs grep -l $'\xe2\x80\x93\|\xe2\x80\x94' 2>/dev/null; then
  echo "em/en dash 발견. CLAUDE.md §5 위반." >&2; exit 1
fi

# (2) 벽시계 차단 (production paths)
if git diff --cached --name-only | grep -Pv '^(tests|\.claude)/' | \
   xargs grep -Pn '\bdate\.today\(\)|datetime\.now\(|time\.time\(\)' 2>/dev/null; then
  echo "벽시계 리크. AIMS §2-2 위반. asof 를 인자로 받으세요." >&2; exit 1
fi
```

배치 위치: `.git/hooks/pre-commit` (exec bit) 또는 `.pre-commit-config.yaml` + `pre-commit install`. 45주차 리뷰 시점에도 `.git/hooks/pre-commit` 부재, `.pre-commit-config.yaml` 부재, `.claude/settings.json` 에 `hooks` 키 부재.

### 6-2. `decompose.py:191` 즉시 raise (**44주차 §6-2 재요구, 3주 연속 미이행**)

`decompose_from_result` 는 `result.meta["asof"]` 필수. 없으면 raise. 44주차·43주차 명시 지적. 45주차 델타는 datamodel/* 은 만졌으나 이 한 줄은 그대로. 44주차 §2 M2 (materialize.py `assert notna` production assert) 도 같은 계열.

### 6-3. 신규 fail-closed 게이트 표면 5 지점 즉시 봉합 (**45주차 신규**)

a69e374 가 구조적 처방 (`blocks_approval` 컬럼 · `_not_run` 패턴 · `is_identity` 태깅) 을 도입한 자리에서 §2-2 D3, D6, D7, D8, D10 이 fail-open 로 새 표면. 처방을 세운 커밋 스스로 계약을 어긴 경우이므로 후속 커밋에서 다음 5 지점을 fail-closed 로 봉합:

1. **D3**: `_check_ncr` institution_type 미상 시 NCR < 100% → `blocks_approval=True` 기본. 은행 스코프 합성 실행은 명시 opt-out.
2. **D6**: `_evidence_done` CL-10 "조건부" 완료 판정을 `ConditionalApproval` 존재 확인 후로 조건화. Gate 객체 직접 호출.
3. **D7**: `deliverables.build_deliverables` 가 `conditional: ConditionalApproval | None` 을 받아 `iv_gate.require(conditional)` 로 전달. CLI `--require-gate` 도 조건부 결재 지원.
4. **D8**: `_check_pillar2_evidence` p2r/p2g 부재 → WARN 유지, `blocks_approval=True` 는 실규제 스코프에 국한. 또는 profile intake 에서 hard error.
5. **D10**: `_check_large_exposure_sources` `n_engine is None` 시 `blocks_approval=True` (또는 별도 `engine_not_run` 플래그) 강제.

동시에 §2-3 D11 (KR/BIS id 재넘버링) 은 소스 파생 안정 id (`KR-<source>-<citation>-<hash>`) 로 전환. §2-3 D13 (내용 없는 중부적합 finding 으로 mismatch 무력화) 은 `recomputed`/`reported` 를 mismatch 설명 시 필수로 격상.

## 7. 리뷰 메타 (4 서브에이전트 · 병렬)

- 리뷰 도구: 4 개 병렬 서브에이전트 (general-purpose). 총 소요 약 425 초, 소비 토큰 약 520k.
- 리뷰 커버리지:
  - (A) 44주차 tracked BLOCKER 14 건 재점검 (agent #1).
  - (B) 델타 3e69926 (formula corrections) + a69e374 (fail-closed gate) 통합 리뷰 (agent #2).
  - (C) 델타 e75d564 (validation-team-agent 자기 점검) 리뷰 (agent #3).
  - (D) 델타 UI-Next 3 커밋 리뷰 (agent #4).
  - (E) 저장소 전수 정책 감사 (em/en dash, 벽시계, 사전 커밋 훅 배치).
- 자체검증 (2선), 상시 독립검증 (3선): 이 리뷰는 코드 리뷰이며 리스크 산출 아님. `RECALC_SCOPE` 대상 아님.
- 파일: `reports/code_review/2026-09-02_full_repo_review.md` (본 파일).

---

_Generated by [Claude Code](https://claude.ai/code)_
