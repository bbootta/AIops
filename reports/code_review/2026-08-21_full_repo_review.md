# 저장소 전수 코드 리뷰 (2026-08-21, 44주차)

**대상**: `bbootta/AIops` 전 저장소, base 브랜치 `claude/stoic-ride-7r1foz` HEAD `60bda57`
**직전 리뷰**: 43주차 (2026-08-14, `origin/main` `153d7d6`), 파일 `reports/code_review/2026-08-14_full_repo_review.md`
**델타 창**: 2026-08-14 ~ 2026-08-21 (7일), 38 커밋, +20,344 / -129, 194 파일 (py 개편 총량 +1,365 라인)
**리뷰 방식**: 8 서브에이전트 병렬 sweep.
- (A) 델타 38 커밋 신규 리뷰
- (B) 43주차 · PR #67 tracked BLOCKER 45건 재점검
- (C) `risk_lib/regulatory/` 전면 (36파일, 25,686줄)
- (D) `risk_lib/capital/` · `alm/` · `monitoring/` + 관련 top-level (36파일, 15,467줄)
- (E) `risk_lib/limits/` · `governance/` · `validation/` + inventory
- (F) `risk_lib/pipeline.py` · cli · report · html · integrations · datamodel · ops_pages · case_studies · tools · examples
- (G) `tests/` 96파일 + CI 워크플로우 · 회귀 통제 커버리지
- (H) `validation-team-agent/` 서브레포 + 전 저장소 정책 지표

## 0. 총평 (한 문장)

델타 38 커밋은 시장 포지션 원장 일원화, PD 설계 판정기 신설, 규정 카탈로그 확장 3축에 좁게 집중되어 신규 코드 자체 P1 결함은 없다. 그러나 tracked BLOCKER 45건 중 44건이 여전히 LIVE (FIXED 유지는 `independent.py check_gate` identity binding 1건뿐), 이번 8병렬 전수 sweep 에서 신규 BLOCKER 15건이 추가 발굴되었으며 그 중에는 SA 코퍼레이트 B등급 위험가중치 100% (규정 150%), NaN-truthy `or 1.0` 4지점, DPD 결측이 자동으로 정상(Current) 분류, `IsolatingDispatcher.send_with_isolation` 3중 즉시 크래시, `_table` XSS 삼항 반전, cross_form BR-05/06 항등식 대사 등 규제 산출과 회로차단기·리포팅에 직결되는 축이 여럿이다. 매주 리뷰가 새 BLOCKER 를 파낸다는 사실 자체가 CI 무커버·사전 커밋 훅 부재로 통제 밀도가 부족하다는 신호다.

### 층위 요약

| 층위 | 43주차 | 44주차 | 변화 |
|---|---|---|---|
| Tracked BLOCKER LIVE | 44 (11건 tracked + 45건 sweep 잔존) | 44 | 무변동 (FIXED 유지 1건) |
| 신규 BLOCKER 발굴 | 11 | 15 | +4 |
| 신규 MAJOR 발굴 | 66 | 34 | -32 (스코프 다름) |
| 신규 MINOR 발굴 | 19 | 24 | +5 |
| CI risk_lib 커버 | 불포함 | 불포함 (mention 0회) | 무변동 (F-01 지속) |
| LICENSE 파일 | 부재 | 부재 | 무변동 (F-02 지속) |
| RECALCULATORS 커버 | 6/21 (29%) | 6/21 (29%) | 무변동 (C-02 지속) |
| 벽시계 risk_lib 지점 | 25 | 25 | 무변동 (grep 카운트 축소는 파일 이동 가능성) |
| 벽시계 VTA 지점 (신규 측정) | (미측정) | 11 (7파일) | 기록 |
| em/en dash 회 (grep -o) | 9,653 | 213,286 | 스코프 재정의 필요 (§4 참조) |
| em/en dash 파일 | 633 | 636 | +3 |

**최대 위험 세 축**:
1. **`capital/rwa_sa.py:44` 코퍼레이트 B bucket 100%** (CRE20.36 은 150%). SA-RWA 저계상. 감독 검사 시 즉시 지적 가능성 높음.
2. **`integrations.py:302-314` `IsolatingDispatcher.send_with_isolation` 3중 즉시 크래시**. 회로차단기 코드가 첫 호출에서 부러진다. 재해 알림·에스컬레이션이 전달되지 않을 수 있다.
3. **`report_chrome.py:159` `_table` XSS 삼항 반전**. `_table` 은 저장소 사실상 모든 HTML 표를 생성한다.

## 1. Tracked BLOCKER 재점검 (45항목, 44 LIVE)

PR #67 및 43주차 sweep 이 지적한 45개 앵커를 HEAD (`60bda57`) 에서 재검증. 요약표 뒤에 LIVE/PARTIAL 만 상세.

| 코드 | 항목 | 상태 |
|---|---|---|
| A-01 | `risk_lib/pipeline.py:1502` 벽시계 폴백 | LIVE |
| A-02 | `risk_lib/notifications.py:59` `datetime.now(timezone.utc)` | LIVE |
| A-03 | `risk_lib/deliverables.py:101` `datetime.now(timezone.utc)` | LIVE |
| A-04 | `risk_lib/adjustments.py:308` `date.today().isoformat()` 폴백 | LIVE |
| A-05 | `risk_lib/stress/path.py:110` `asof or date.today()` | LIVE |
| A-06 | `risk_lib/archive.py:129` `date.today().isoformat()` 폴백 | LIVE |
| A-07 | `risk_lib/archive.py:154` `datetime.now(timezone.utc)` | LIVE |
| A-08 | `risk_lib/report.py:43` `date.today().isoformat()` | LIVE |
| A-09 | `risk_lib/report_chrome.py:144` `date.today().isoformat()` | LIVE |
| A-10 | `risk_lib/board_pack.py:87` `date.today().isoformat()` | LIVE |
| A-11 | `risk_lib/board_pack.py:418` `meeting_date = date.today().isoformat()` | LIVE |
| A-12 | `risk_lib/work_report.py:84` `date.today().isoformat()` 폴백 | LIVE |
| A-13 | `risk_lib/ops_pages/core_overview.py:332` 폴백 | LIVE |
| A-14 | `risk_lib/case_studies/bank7_2026q1.py:286` | LIVE |
| A-15 | `risk_lib/case_studies/ib3_report.py:228` | LIVE |
| A-16 | `risk_lib/case_studies/ib3_report.py:237` | LIVE |
| A-17 | `risk_lib/case_studies/ib3_report.py:280` | LIVE |
| A-18 | `risk_lib/case_studies/ib3_2026q1.py:198` | LIVE |
| A-19 | `risk_lib/market_data.py:521` 폴백 | LIVE |
| A-20 | `risk_lib/localization.py:100` meeting_date | LIVE |
| A-21 | `risk_lib/localization.py:152` As of | LIVE |
| A-22 | `risk_lib/model_inventory.py:45` days_overdue 기본값 | LIVE |
| A-23 | `risk_lib/model_inventory.py:61` today 폴백 | LIVE |
| A-24 | `risk_lib/model_risk.py:36` default_factory | LIVE |
| A-25 | `risk_lib/datamodel/decompose.py:191` 폴백 (43주차 신규 §2-1 P1) | LIVE |
| B-01 | `risk_lib/regulatory/cross_form.py:61` `("BR-31","1110")` orphan | 정정 (아래 §1-B 참조) |
| B-02 | `risk_lib/regulatory/cross_form.py:77` `("BR-31","1510")` orphan | 정정 |
| B-03 | `cross_form.py:32` RWA tol default 1.0 KRW | LIVE |
| B-04 | `cross_form.py:38-83` 6개 라인 미등록 | LIVE |
| B-05 | `risk_lib/regulatory/forms.py:380` BR-08 tol 항등 통과 | LIVE |
| C-01 | `risk_lib/validation/independent.py:662-708` `check_gate` identity binding | FIXED (유지) |
| C-02 | `validation-team-agent/tools/independent_recalc.py:140-153` RECALCULATORS 6/21 | LIVE |
| C-03 | `risk_lib/validation/independent.py:39` `Finding.__post_init__` 부재 | LIVE |
| D-01 | `risk_lib/integrations.py:302-314` `IsolatingDispatcher` 결함 | LIVE (§3-4 신규 확장) |
| D-02 | `limits/limit_engine.py:41-47` vs `limits/limits_deep.py:55-62` CRITICAL 반전 | LIVE (§3-3 3자 분열) |
| D-03 | `risk_lib/op_loss.py:88` `float(lognet.std() or 1.0)` nan 오염 | LIVE (§3-2 4지점 확장) |
| E-01 | `tests/test_frtb_inventory.py:183` 시한폭탄 | LIVE |
| E-02 | `tests/test_frtb_inventory.py:72,:81` 미시드 rng | LIVE |
| E-03 | `tests/test_frtb_inventory.py:192` `run_pipeline()` no asof | LIVE |
| E-04 | `tests/test_monitoring_deep.py:262` no asof | LIVE |
| E-05 | `tests/test_stress_deep.py:336,:350` no asof | LIVE |
| F-01 | `.github/workflows/` 에 risk_lib CI 무존재 | LIVE (§3-5 mention 0회) |
| F-02 | LICENSE 파일 부재, pyproject license 필드 부재 | LIVE |
| F-03 | `cross_form.py:55-84` 비율 불변식 항등 | LIVE |
| F-04 | `capital/rwa_sa.py:22-46` SA B-bucket 100% | LIVE (§3-2 상세) |
| F-05 | `capital/rwa_irb.py:40-45,74-105` IRB LGD floor 미적용 | LIVE |
| F-06 | `capital/rwa_deep.py:262-289` FIRB LGD 40% 미반영, residential_mortgage 오배정 | LIVE |
| F-07 | `capital/op_risk.py:19-23,58,83` EUR 원문, use_ilm=True | LIVE (§3-2 MAJOR-2) |
| F-08 | `models/rating.py:41-52` bisect_left 경계 off-by-one | LIVE |
| F-09 | `capital/rwa_sa.py:214-228` `crm_factor` post-multiplication CRM 이중적용 창구 | LIVE |

### §1-A. 벽시계 25지점 (A-01~A-25)

25/25 LIVE. 43주차 대비 무변동. 43주차 §1-1 이 "18지점" 이라 부른 것은 파일 단위 합산 결과이며 라인 단위 재열거하면 25지점 그대로다. `datamodel/decompose.py:191` 폴백은 43주차 §2-1 (P1) 로 raise 승격 권고되었으나 미이행.

### §1-B. cross_form BR-31 orphan 주장 정정

Agent C 재검증 결과, `cross_form.py:61,77` 의 `("BR-31","1110")` 와 `("BR-31","1510")` 는 `br_camel` (`forms_ext.py:545`) 이 실제로 생성한다:
- pru_camel 6부문 순서에서 자본적정성 i=1 → base+10*1 = 1110
- 유동성 i=5 → base+10*5 = 1510

cross_form_checks 9건 전부 PASS 확인 (seed=42, asof=2026-06-30). PR #67 §1-2 및 43주차 §1-2 의 "orphan" 주장은 오판이다. B-01/B-02 를 tracked 목록에서 **삭제 처리**한다. 단, 이 통과는 다수가 같은 변수의 복사를 대사한 결과이므로 (`check_strength_sentence` provenance.py:479 가 이미 F-703 세기 경고), §3-1 신규 BLOCKER BR-05/06 항등식 대사 문제가 이어진다.

### §1-C. FSS cross-form 잔여 (B-03, B-04, B-05)

- **B-03 LIVE**: `cross_form.py:32` `CrossFormInvariant.tolerance: float = 1.0` 그대로. 위험가중자산 합계 스프레드가 1원 이상이어야 잡히는 구조 불변.
- **B-04 LIVE**: `cross_form.py:38-85` 등록 목록에 43주차 지적 6지점 (`B2506/3000`, `B2403/1010`, `B2431/1010`, `B2506/2000`, `B2916/1000`, `B2602-2/1000`) 전부 미등록. B2403/1020, B2431/1020, B2913/3300, B2916/2000 만 등록되어 있어 다른 라인의 조용한 표류를 잡지 못한다.
- **B-05 LIVE**: `forms.py:380` `tol=float(lcr.inflow_capped) + 1.0` 그대로. BR-08 `_sum_check` 가 `inflow_capped` 크기만큼의 tol 을 허용해 부호 반전을 흡수한다. §3-1 MAJOR-3 에서 상세 재기술.

### §1-D. 3선 독립검증 (C-01 FIXED 유지, C-02·C-03 LIVE)

- **C-01 FIXED (유지)**: `independent.py:662-708` `check_gate`. :674-677 run_id, :678-680 request_id, :684-690 recalc 커버리지 강제 모두 유지. 서명·해시 추가는 아직 없으나 identity binding 자체는 landed 상태 지속.
- **C-02 LIVE**: `independent_recalc.py:140-153` `RECALCULATORS` 여전히 6개 (`lcr`, `nsfr`, `cet1_ratio`, `leverage_ratio`, `icaap_ratio`, `portfolio_default_rate`). `RECALC_SCOPE` 는 21개이므로 15개 headline (71%) 재계산 미커버. Pw9F5 브랜치 진행 없음 지속. 44주차 델타의 PD 신설도 이 격차를 좁히지 못했다 (`pd_cyclicality` 는 설계 라벨 판정 도구이지 재계산기가 아니다).
- **C-03 LIVE**: `independent.py:39` `VERDICTS`, `STATUSES` 튜플만 정의. `Finding` (`:146-153`), `ValidationResponse` (`:156-164`) 모두 `__post_init__` 부재. `ValidationResponse.read` (`:186-189`) 가 `Finding(**f)` 로 severity 문자열을 검증 없이 삽입.

### §1-E. 리스크 코어 (D-01, D-02, D-03 LIVE, 신규 확장)

- **D-01 LIVE + 확장**: `integrations.py:302-314` `send_with_isolation`. 43주차 지적 (미사용 dedup key, 재시도 sleep 부재) 에 더해 §3-4 sweep 에서 3중 즉시 크래시가 확인되었다 (아래 참조).
- **D-02 LIVE + 확장**: `limit_engine.py:41-47` (CRITICAL >= 1.20) vs `limits_deep.py:55-62` (CRITICAL >= 0.90) 반전. §3-3 에서 `concentration_deep.py:83-87` 을 포함한 3자 분열 확인.
- **D-03 LIVE + 확장**: `op_loss.py:88` `nan or 1.0 == nan`. §3-2 에서 같은 패턴이 `rwa_deep.py:58,454,566` 3지점에 추가로 존재함을 확인.

### §1-F. 테스트 회귀 통제 (E-01~E-05 LIVE)

`test_frtb_inventory.py:183` (2030-01-01 시한폭탄), :72/:81 (미시드 rng), :192 (asof 미전달), `test_monitoring_deep.py:262`, `test_stress_deep.py:336,:350` 모두 LIVE. §3-5 sweep 에서 `run_pipeline(...)` no-asof 호출이 11파일 22지점으로 확대 확인.

### §1-G. 43주차 신규 BLOCKER (F-01~F-09) 재점검

- **F-01 LIVE**: `.github/workflows/` 에 `validation-team-agent-ci.yml` 단일 워크플로우만 존재. paths 필터가 `validation-team-agent/**` 로만 제한되어 `risk_lib/**`, `tests/**` 어떤 변경에도 CI 트리거 없음. 2,187 개 top-level 테스트 함수가 서버 사이드에서 한 번도 안 돌고 있다.
- **F-02 LIVE**: 루트 `LICENSE` 부재, pyproject license 필드 부재 (양 저장소).
- **F-03 LIVE**: cross_form 비율 5개 불변식 (BR-07/08/09, BR-01) 이 같은 result 에서 파생되어 산술적 항등, falsifiable 아님.
- **F-04 LIVE**: SA B-bucket 100% (§3-2 상세).
- **F-05 LIVE**: IRB LGD floor 미적용. `apply_floor` 는 PD 하한만 적용, LGD 하한 정의만 되어 있고 미사용.
- **F-06 LIVE**: `FIRB_LGD["corporate_senior_unsecured"] = 0.45` 하드코딩 (Basel III 확정판 40% 미반영). `residential_mortgage` 에 FIRB LGD 배정 (FIRB retail 미적용 규칙 위반).
- **F-07 LIVE**: `_BI_BUCKETS` EUR 원문, `use_ilm=True` 기본 (§3-2 MAJOR-2).
- **F-08 LIVE**: `models/rating.py:49` `bisect_left` 로 upper-inclusive 규약과 어긋남.
- **F-09 LIVE**: `crm_factor` post-multiplication 이 `apply_crm` 을 도는 포트폴리오와 결합 시 CRM 이중 적용.

## 2. 델타 신규 결함 (2026-08-14 → 2026-08-21, 38 커밋)

38 커밋 중 py 개편은 3축에 집중된다: (1) 시장 포지션 원장 일원화 (`market_portfolio.py` 신설, `mkt_position → rwa_market_component` 계보 배선, 정합성 대사 `market_portfolio_split_reconciles` 추가), (2) PD 설계 구분 검증 (`validation-team-agent/tools/pd_cyclicality.py` +492, 테스트 +157, 세칙 별표 3 인용, 임계 SSoT 5년 등재), (3) 세일즈 하네스 유입에 따른 `tests/risk_agents.py` 명부 반영. 리스크 코어 py 변경 총량 +1,365 라인. **벽시계 리크·CWD 상대 경로·미시드 rng 신규 발생 없음. RECALC_SCOPE 헤드라인 신규 없음. 델타는 좁고 손이 얌전한 편이며 자체 P1 없음.**

### 2-1. P2 (다음 스프린트)

**2-1-1. 적재 표가 SSA_SCALING 의 부분집합만 배분해 확장 시 조용히 샌다** `risk_lib/market_portfolio.py:36,46-55,63-79`
- 요약: `RISK_CLASSES = tuple(sorted(SSA_SCALING))` 는 `interest_rate`, `equity`, `fx`, `commodity`, `credit_spread` 5개인데 `_PORTFOLIOS` 는 앞 3개에만 가중치를 배정한다. `_check_loading_table()` 은 배정된 클래스만 순회하므로 `commodity`, `credit_spread` 는 합=1.0 검사에서 아예 제외.
- 재현: 앞으로 `pipeline._market_op(...)` 또는 스트레스 축이 `risk_class="commodity"` 인 `mkt_positions` 을 태우면 `mp.split_positions` 는 `w.get("commodity", 0.0)=0` 으로 그 행을 통째로 버린다 (배정·검증 없이 사라짐).
- 완충: `_check_market_portfolio_split` 이 FAIL 로 잡기는 하지만 실패 메시지가 "합계 불일치" 로만 나와 배분표 누락을 드러내지 못한다.
- 제안 수정: `_check_loading_table()` 앞에 `if set(SSA_SCALING) - {c for *_, w, _ in _PORTFOLIOS for c in w}: raise ValueError("미배분 위험군: ...")` 한 줄 추가.

**2-1-2. `portfolio_id` 미배정 트레이드를 막는 통제가 `assert` 라 `-O` 로 벗겨진다** `risk_lib/datamodel/materialize.py:406-409`
- 요약: `trade["portfolio_id"] = tr["kind"].map(mp.KIND_TO_PORTFOLIO)` 뒤의 `assert trade.empty or trade["portfolio_id"].notna().all(), (...)` 이 `python -O` (또는 `PYTHONOPTIMIZE=1`) 실행 시 통째로 삭제된다.
- 재현: 훗날 `synthesise_trading_book` 이 `"future"` 같은 유형을 추가하면서 `KIND_TO_PORTFOLIO` 갱신을 잊으면, non-optimize 모드에서는 AssertionError 로 죽지만 optimize 모드에서는 `TRADE.portfolio_id` (nullable=False, FK) 가 NaN 인 채 원장에 실린다.
- 제안 수정: `if not (trade.empty or trade["portfolio_id"].notna().all()): raise ValueError("포트폴리오 미배정 거래 유형: " + ...)` 로 승격.

### 2-2. P3 (백로그)

**2-2-1. `_check_market_portfolio_split` 이 스펙 위반 sentinel `"0000-00-00"` 을 asof 로 넣는다** `risk_lib/validation/consistency.py:497-499`
- 대사용 임시 `split` 프레임에 `asof="0000-00-00"`. `mp.POSITION` 스펙은 `asof` 를 `date` 타입으로 못박고 있어 이 프레임을 `validate(...)` 로 검증하면 실패한다 (현재는 검증 없이 곧바로 `capital_frame` 만 태우므로 무해).
- 제안 수정: `asof=str(market_positions["asof"].iloc[0]) if "asof" in market_positions else "1970-01-01"`.

**2-2-2. `pd_cyclicality.synthetic_panel(years=N)` 이 `N > 8` 이면 `IndexError`** `validation-team-agent/tools/pd_cyclicality.py:362-365`
- `cycle = np.array([...])[:years]` 원 배열이 8개. `python -m tools.pd_cyclicality demo --years 10` 으로 부르면 `cycle[8]` 접근에서 `IndexError`.
- 제안 수정: CLI `--years` 에 `choices=range(2, 9)` 를 걸거나 `cycle` 을 `rng.normal(0, 1.5, size=years)` 로 길이에 맞춰 생성.

### 2-3. CLEAN (특기)

- `market_portfolio.py` 는 import-time 게이트 (`_check_loading_table`) 로 잘못된 배분표에서 시작 전에 죽고, `test_a_broken_loading_table_dies_at_import` 가 그 실패 경로를 실증한다. 계보 가시성 요구 (`test_unification_is_visible_in_lineage`) 를 테스트가 직접 지킨다.
- `pd_cyclicality.py` 는 `Path(__file__).resolve().parent.parent` 로 앵커링, 벽시계 미사용, 합성 표본 `np.random.default_rng(seed)` 결정적, 왕복 항등 (`ttc→pit→ttc`) 이 해석적으로 참이고 테스트가 대역 넓게 확인. 음성 통제 (`test_pit_data_claimed_as_ttc_is_detected`, `test_flat_prediction_claimed_as_pit_is_detected`) 로 판정이 실제로 뒤집힐 수 있음을 고정.
- `gen_regulatory_criteria.py` 확장 (+49) 은 `BASEL_MAP_BY_CRITERION` 신설로 같은 조문·별표라도 대응 바젤 Chapter 를 문장 단위로 재지정하는 경로를 열었다. 임계 SSoT (`pd_min_observation_years=5`) 가 `THRESHOLDS` 원장에 등재되어 원문 대조를 받는다.
- 신규 `_check_market_portfolio_split` 은 `market_positions is None` 에서 fail-open 대신 WARN 을 남기고, 골든 (`GOLDEN_VALIDATION` PASS 70→71) 에 그 PASS 를 반영해 무통제 통과를 배제.
- 새 원장 4장 (`mkt_portfolio`, `mkt_position`, `mkt_portfolio_capital`, `mkt_var_es_portfolio`) 의 FK 는 모두 기존 표 (`mkt_portfolio`) 로만 향해 참조 무결성 위반 없음. `TRADE` 에 신규 `portfolio_id` NOT NULL FK 를 얹은 것도 데이터 생성부 (`materialize_market`) 가 같은 커밋에서 채우도록 정렬됨.

## 3. 서브시스템 sweep 결과 (신규 결함)

### 3-1. regulatory/ (36파일, 25,686줄, agent C)

**정합성 벤치**: FORMS_BY_ID=290건, FSS builder=256건, BR-01~34 누락 0건, form_id 중복 0건, cross_form_checks 9건 PASS. fss_master 마스터-빌더 매핑 정합.

**신규 BLOCKER 2건 (모두 F-703 항진명제 계열)**:

- **BR-05 소계 대사 항등식** `risk_lib/regulatory/forms.py:266-267`
  - `FormCheck("위험군 합 = 소요자기자본 합계", float(t["capital"].sum()), sum(float(x) for x in t["capital"]), 1.0)`. 좌우 두 변이 같은 시리즈의 합이라 어떤 자료에서도 정확히 같다.
  - 수정: 좌변을 서식 라인값 합으로. `sum(_val(L, f"11{i:02d}") for i in range(1, len(t)+1))`.

- **BR-06 ORC·RWA 정의식 항등** `risk_lib/regulatory/forms.py:303-305`
  - `FormCheck("ORC = BIC × ILM", float(od.bic)*float(od.ilm), float(od.orc), 1.0)` 와 `FormCheck("RWA = ORC × 12.5", float(od.orc)*12.5, float(od.rwa), 1.0)`. `capital/op_risk.py:88-89` 가 `orc = bic*ilm; rwa = orc*12.5` 로 산출하므로 좌우변이 같은 표현식.
  - 수정: 서식 라인값을 좌변으로. `_val(L,"2000")*_val(L,"3000")` vs `_val(L,"4000")`.

**신규 MAJOR 2건**:
- **BR-08 순현금유출 검증이 tol 로 통과** `forms.py:379-380` (PR #67 §1-2 B-05 tracked 확장). tol 이 `inflow_capped + 1.0` 이라 어떤 자료에서도 통과. 수정: `_val(L,"2000") - float(lcr.inflow_capped)` vs `_val(L,"4000")` 로 재작성.
- **BR-05 RWA 검증도 tautology** `forms.py:268-269`. `tests/test_datamodel_domains.py:407` 이 `row["rwa"] == row["capital"]*12.5` 를 불변으로 강제하므로 정의식.

**신규 MINOR 1건**:
- **엑셀 서식 시트 text 라인 중복** `excel.py:170-195`. 본문 루프가 `unit=="text"` 라인 값 셀에 채운 뒤 하단 각주 블록이 같은 텍스트를 "※" 로 다시 쓴다.

### 3-2. capital / alm / monitoring / (37파일, 15,467줄, agent D)

**신규 BLOCKER 3건**:

- **SA 코퍼레이트 "B" 위험가중치 100% (규정 150%)** `capital/rwa_sa.py:44`
  - `_RW_CORPORATE["B"] = 1.00`. Basel III CRE20.36 "Below BB-" 는 150% 이며 B+~B- 는 이 구간. 소버린·뱅크는 BB+~B- 100% 가 맞아 그대로 유지하되 코퍼레이트만 잘못됐다.
  - 원문 표: AAA~AA- 20% · A+~A- 50% · BBB+~BBB- 75% · BB+~BB- 100% · **Below BB- 150%** · Unrated 100%.
  - 수정: `"B": 1.50` 로 교체.

- **NaN-truthy `or 1.0` 패턴 4지점** `op_loss.py:88`, `capital/rwa_deep.py:58,454,566`
  - `float(x) or 1.0` 은 x 가 nan 이면 nan (nan 은 truthy). PR #67 §1-4 에서 op_loss.py 1건만 잡혔는데 rwa_deep 에 3건 더 존재.
  - 재현: `sa_results["rwa"]` 가 전부 NaN → sum() 이 nan → `total_rwa=nan` → `g["rwa_share"] = g["rwa"]/nan = nan` 이 화면·서식 전 행에 전파.
  - 수정: `_safe_denom(x, default=1.0)` 헬퍼로 4지점 치환.

- **DPD 결측이 자동 "Current(0dpd)" 슬로팅** `monitoring/deep.py:42-44`
  - `_bucketise(dpd)` 가 `pd.isna(dpd)` 일 때 "Current" 반환 → NPL·roll-rate·markov projection 전반이 낙관 편향.
  - 재현: 포트폴리오에 DPD NaN 3만건 → `dpd_bucket_matrix` 전부 Current → `npl_ratio` 실제 대비 하방 편향.
  - 수정: NaN → `"unknown"` 반환. `delinquency.py:_bucket(28)` 도 `int(dpd)` 이전 `pd.isna` 가드 필요.

**신규 MAJOR 6건**:
- 연체 flat 150% (`rwa_sa.py:56,126-127`). CRE20.56.1 은 90일 초과 연체 주거용 부동산 여신 100%. 코드는 모든 asset_class 에 `_RW_PAST_DUE=1.50` 무조건.
- Op risk BI 버킷 EUR 상수 (`op_risk.py:19-23`). F-07 tracked 상세.
- CCR SA-CCR 담보 임계액 미반영 (`ccr.py:74-75`). RC = max(V-C, TH+MTA-NICA, 0) 미구현.
- `cure.py:48` `default_col == 1` 이 nullable Int64 + NaN 조합에서 실제 부도를 skip.
- `xva.py:87` 지역 `pd = _hazard_curve(...)` 가 모듈 `pandas as pd` 를 섀도잉.
- `alm/nii.py:148-176` `_years(asof_d, iso=None)` 이 `date.fromisoformat("None")` → ValueError 로 hard fail.

**신규 MINOR 5건**:
- `vintage_deep.py:49` 월간 PD 근사 `pd_eff/12` (정확식 `1-(1-pd_eff)^(1/12)`).
- `delinquency.py:69-71` 세그먼트 없을 때 스칼라 broadcast.
- `cecl.py:55-66` 만기 0.3년 → 1년 이산화 → ECL 과대.
- `rcsa.py:253-258` 잔여점수 6.0 경계 판정 유닛테스트 부재.
- `ccr.py:47` asset_class 확률 함수 본문 하드코드.

### 3-3. limits / governance / validation / (agent E)

**신규 BLOCKER 3건**:

- **심각도 임계 3자 분열 (지속·확대)** `limits/limit_engine.py:41-47` vs `limits/limits_deep.py:55-62` vs `concentration_deep.py:83-87`
  - 같은 소진율에 세 개의 다른 severity. util=0.95 인 동일차주에 대해 `LimitBreach.severity`="OK", `_severity(0.95)`="CRITICAL", `large_exposure_test.sev(0.95)`="CRITICAL". 같은 로우가 CRO 대시보드에 정반대 이름으로 올라간다.
  - 수정: `limits_deep._severity` 를 정본으로, 나머지가 import 해 단일 함수 호출.

- **`Finding.severity` 검증 부재 (지속)** `validation/independent.py:146-153,186` (C-03 tracked)
  - `Finding(**f)` 가 severity 오타를 통과시키고 `passes()` 는 문자열 리터럴 `"중부적합"` 만 검사해 게이트가 반대로 뒤집힌다.
  - 수정: `Finding.__post_init__` 에서 `if self.severity not in VERDICTS: raise ValueError(...)`.

- **`_check_pd_rwa` 가 gap 있어도 PASS** `validation/cross_domain.py:83-88`
  - `if gaps` 분기와 `else` 분기가 둘 다 `status="PASS"`. WARN 이 PASS 로 조용히 승격.
  - 수정: 라인 85 `"PASS"` → `"WARN"`.

**신규 MAJOR 6건**:
- 벽시계 리크 4지점 (`model_inventory.py:45,61`, `model_risk.py:36`, `audit_trail.py:36`) - A-22~A-24 tracked 확장.
- `governance/retention.py:136-157` 6개 자료 구분 전건 `min_retention_years=None`. 폐기 통제가 한 번도 동작하지 않는다.
- `limits_master.py:139-155,206-217` 미승인 한도가 산출에 그대로 실린다. 게이트 부재.
- `concentration_deep.large_exposure_test` 가 함수 기본값 `limit_pct=0.25` 사용 (`concentration_deep.py:53-88`). 원장 (`lex_setting`) 을 우회.
- `audit_chain.append` 가 chain 검증 없이 record 삽입 (`governance/audit_chain.py:94-111`). head 손상 후 append 하면 손상된 chain 위에 정상 seq 가 얹힌다.
- `_check_stress_baseline_matches_bis` 허용오차 0.5%p 과대 (`validation/cross_domain.py:33,275-281`). Baseline stress 와 현재 BIS 는 같은 자본·같은 RWA 에서 나오므로 tol 은 1e-6 규모.

**신규 MINOR 5건**:
- `_check_reproducibility` 조기 반환 침묵 (`validation/cross_domain.py:311-313`).
- HL calibration DOF 처리 `dof = max(dof-2, 1)` (`validation/backtest.py:51`).
- `binomial_test_per_grade` alpha=0.05 근거 명시 필요 (`validation/backtest.py:60,79-84`).
- `ModelInventoryEntry.is_overdue()` docstring 시한폭탄 원인 (`model_inventory.py:49-50`).
- `rbac.decide_access` 의 `denied.iloc[0]` 비결정적 (`governance/rbac.py:308-311`).

### 3-4. 오케스트레이션 · 리포팅 (agent F)

**신규 BLOCKER 5건**:

- **`IsolatingDispatcher.send_with_isolation` 첫 호출 시 크래시 (3중 결함)** `integrations.py:302-314` (D-01 tracked 확장)
  - (a) `req.kind` 는 `WebhookRequest` 에 없는 속성 → `AttributeError` 즉시.
  - (b) 그 줄을 고치면 `sha256(req.body)` 가 str 를 bytes 로 넘김 → `TypeError: Strings must be encoded before hashing`.
  - (c) 그 다음 `self.send(req)` 가 `WebhookRequest` 를 dict 로 취급 → `TypeError: Object of type WebhookRequest is not JSON serializable`.
  - 재시도 루프에 sleep/backoff 도 없다.
  - 수정: `key = idempotency_key(self.kind, run_id, hashlib.sha256(req.body.encode("utf-8")).hexdigest())` 로 고치고, `self.send(req)` 대신 dict payload 를 별도 헬퍼로 넘기며, 실패 재시도 앞에 `time.sleep(self.policy.delays()[attempt-1])`.

- **`_table()` XSS 삼항 반전** `report_chrome.py:159`
  - `v if isinstance(v, str) and ('<' in v) else _esc(v)` 삼항이 뒤집혀 있어 `<` 가 들어 있는 문자열이 오히려 무필터로 삽입된다.
  - 재현: `_table(["obligor"], [["Bank <script>alert(1)</script>"]])` 가 `<td>Bank <script>alert(1)</script></td>` 로 렌더. `_table` 은 저장소 사실상 모든 HTML 표를 만든다.
  - 수정: `cells.append(f"<td{cls}>{_esc(v)}</td>")` 로 단순화, 이미 HTML 인 셀은 `raw_cols=` 명시.

- **재현성 벽시계 리크가 리포트 본문·zip 지문까지 관통** `pipeline.py:1502` 외 (A-01, A-03 확장)
  - `asof` 미전달 시 `date.today()` 폴백이 살아 있고, 하류 `deliverables.py:101` MANIFEST.txt 에 `datetime.now(timezone.utc).isoformat()` 이 실려 zip sha256 이 재실행마다 달라짐. `notifications.py:59` Slack/이메일/MD 페이로드도 벽시계 실림.
  - 수정: 각 진입점에서 폴백 제거하고 `result.meta["asof"]` 필수 승격. `zipfile.ZipInfo` 로 결정론적 mtime 지정.

- **`tools/gen_flow_html.py:133` CWD 상대** (PR #67 §2-2 tracked)
  - `nav_groups()` 가 `Path("risk_lib/ui_studio/app.py").read_text(...)`. 같은 파일 :22 는 `__file__` 을 쓰는데 이 함수만 CWD 상대. 저장소 밖 실행 시 `FileNotFoundError`.
  - 수정: `_ROOT = Path(__file__).resolve().parent.parent` 앵커링.

- **`tools/gen_fss_master.py:17` CWD 상대** (PR #67 §2-5 tracked)
  - `OUT = Path("risk_lib/regulatory/fss_master.py")`. 저장소 밖에서 돌리면 CWD 밑에 엉뚱한 디렉토리를 만들어 조용히 성공 (최악의 실패 모드).
  - 수정: `OUT = Path(__file__).resolve().parent.parent / "risk_lib/regulatory/fss_master.py"`.

**신규 MAJOR 5건**:
- `market_portfolio.build_component_tables:274-279` 결과 행 순서가 caller dict 순서 의존. 수정: `sorted(by_class.items())` 또는 `RISK_CLASSES` 순서로.
- `notifications.build_email_payload:160-167` HTML 표에 escape 부재. `Alert.title/detail/citation`, `k.name`, `c.detail` 등이 raw 삽입. 수정: `from html import escape as _h` 후 f-string 안 값에 감싸기.
- `deliverables.write_manifest:101` 매 실행 벽시계 헤더로 zip 지문 안 잡힘. 수정: 헤더 생성시각 라인 제거 또는 `result.meta['asof']` 사용.
- `board_pack._briefing_block:158-165` 정규식 `<a ...>.*?</a>` 가 `< 100bp` 같은 문장에서 잘못된 구간 삭제.
- `cli._cmd_notify` (`cli.py:100-121, 142-155`) `notify`/`dispatch`/`printable`/`serve`/`export-json`/`api-spec` 모두 `--asof` 인자 부재. 벽시계 폴백을 태워 재현성 무너짐.

**신규 MINOR 4건**:
- `market_portfolio.split_positions:198-206` `iterrows()` O(rows×portfolios).
- `repro.py:106-107` `except Exception: pass` 로 `git_revision=""` 이 배포본 metadata 에 실림.
- `html_exec._exec_page:553-556` `_esc` 관행상 f-string 안 각 값 적용 권장.
- `api.py:143,265-282` `endpoint_alm(result, leg)` 이 알 수 없는 leg 에서 `KeyError` → 스택트레이스 노출.

### 3-5. tests / (96파일, agent G)

**collect 결과**: `tests/` 2,187 tests / 5.03s collect 통과 (에러 0, numpy·sklearn·scipy·statsmodels·openpyxl 설치 환경). `validation-team-agent/tests/` 20파일 pydantic 요구.

**신규 BLOCKER 2건**:

- **`tests/` 를 도는 워크플로우가 저장소 전체에 없다** `.github/workflows/` (F-01 tracked 확장)
  - `validation-team-agent-ci.yml` 하나만 존재. `paths:` 필터가 `validation-team-agent/**` 만 트리거. `risk_lib/pipeline.py` 를 고쳐 PR 을 열어도 CI 는 뜨지 않는다. 2,187 개 top-level 테스트 함수가 서버 사이드에서 한 번도 안 돌고 있다.
  - 수정: `.github/workflows/risk-lib-ci.yml` 신설, `paths: [risk_lib/**, tests/**, conftest.py, pyproject.toml]` 로 트리거, `python -m pytest -q tests/` 실행.

- **`tests/test_frtb_inventory.py:183` 시한폭탄** (E-01 tracked)
  - `assert not e.is_overdue()` 가 `today=` 없이 wall clock 을 읽는다. `next_due="2030-01-01"` 이므로 2030-01-01 부터 뒤집힌다.
  - 수정: `assert not e.is_overdue(today="2026-06-11")`, `conftest.py` `PINNED_ASOF` 재사용.

**신규 MAJOR 5건**:
- **`run_pipeline(...)` 호출 22 곳이 `asof=` 없이 wall clock 을 먹는다** (E-03~E-05 tracked 확장). 11 파일 22 지점: `test_credit_models.py:141,215`, `test_explainability.py:131,138,145,157`, `test_extras.py:181,191,204`, `test_final_validation.py:225,226`, `test_frtb_inventory.py:192`, `test_limits_deep.py:326`, `test_monitoring_deep.py:262`, `test_rapm_deep.py:241`, `test_stress_deep.py:336,350`, `test_timeseries.py:23`, `test_xva_sensitivities.py:177`. 43주차 5지점 지적 대비 22지점으로 확대 확인.
- cross_form BR-31 오식별 회귀 테스트 부재 (§1-B 정정 후 재정의 필요) → `tests/test_regulatory_cross_form.py` 신설, `assert set(cross_form.PAIRS) <= set(br_camel(form).keys())` 로 존재 라인코드 계약 명시.
- IsolatingDispatcher retry/dedup 테스트 0 건 (`tests/test_integrations.py:21-52`). fake clock 으로 backoff·dedup 검증 케이스 신설 필요.
- `check_refs` 조용한 `continue` 회귀 테스트 부재 (PR #67 §2-3). `fk_ref_column_missing` 위반이 반드시 남는다는 계약 케이스 필요.
- 결정성 테스트 same-process 항등 (`tests/test_erd.py:164`, `tests/test_pipeline_flow.py:162`). PYTHONHASHSEED=random subprocess 로 재실행.

**신규 MINOR 4건**:
- `test_frtb_inventory.py:72,81` legacy `np.random.normal` 미시드 (E-02 tracked).
- `test_wall_clock_asof_is_disclosed_not_silent:442` 는 helper 계약만 검증. 실제 `run_pipeline()` 이 wall clock 잡아 태깅하는지 미검증.
- `test_sec_batch2.py:250-256` 이행폐포 로직 없이도 통과.
- `.github/workflows/validation-team-agent-ci.yml:114-115` coverage/JUnit 미배출.

### 3-6. validation-team-agent + 정책 지표 (agent H)

**신규 BLOCKER 2건**:

- **응답 파일 무서명·무해시 신뢰** `validation/independent.py:186-189` (C-03 tracked 확장)
  - `ValidationResponse.read` 는 `json.loads(Path(path).read_text(...))` 한 줄. 해시·서명·검증자 지문 대조 없음. `check_gate` 는 identity 를 강제하지만 응답 파일의 **출처** 는 검증하지 않는다. `docs/independent_validation/{run_id}.response.json` 위치에 매칭 ID·`recalc_matches={key:True}×21`·`verdict="적합"` 을 채운 평문 JSON 을 놓으면 게이트 통과. `Finding.__post_init__` 부재와 결합해 통제 우회 경로 완성.

- **RECALCULATORS 커버리지 71% 결손** `independent_recalc.py:140-153` (C-02 tracked)
  - `RECALCULATORS` = 6개 vs `RECALC_SCOPE` = 21개. 격차 15건: RWA 3종, total_ratio, ECL 2종, IRRBB 2종, 생존기간, 스트레스 2종, 대손준비금, 별표 9-1 표6 2종, LGD, CCF 실측검증 3종은 3선에서 재계산되지 않는다. 44주차 델타의 PD 신설도 이 격차를 좁히지 못했다.

**신규 MAJOR 4건**:
- `pd_cyclicality.py` (신규 +492) 파일 안에 em/en dash 92회. CLAUDE.md §5 정면 충돌.
- VTA 벽시계 11회 (7파일): `conditional_approval.py:173,:274`, `validation_finding.py:297,:358`, `escalation_report.py:27`, `validation_scope.py:122`, `audit_retention.py:53`, `manifest.py:94,:147`, `validation_trigger.py:188,:278`. 특히 `manifest.py:94/:147` 은 `timestamp` 필드에 `datetime.now().strftime(...)` 무조건 삽입 (인자 폴백 없음).
- VTA CWD 상대 경로: `tools/benchmark.py:53`, `tools/findings_mapping.py:207`, `tools/report_export.py:43,:53,:88`, `tools/report_pack.py:1737/:1826/:1922`.
- 광범위 `except Exception` 10+ 지점: `classify_error.py:159`, `policy_lint.py:158`, `provenance.py:112/:133/:150`, `report_pack.py:3211/:3461/:3657`. provenance 3지점은 산출 지문이 조용히 부실화될 수 있음.

**신규 MINOR 3건**:
- `pd_cyclicality.py` 자체는 견고 (임계 SSoT, 시드 고정, 벽시계·CWD 상대 무, 양성·음성·경계·CLI 종료코드·임계-원문 대조 커버).
- `pd_cyclicality.classify` TTC/PIT 분기가 대칭 아님 (로직상 문제는 없음).
- `mix_level_decomposition` 이 `keys[0]` 과 `keys[-1]` 만 비교. 중간 기간 무시.

## 4. 정책 지표 (43주차 → 44주차)

| 지표 | 43주차 | 44주차 | 변화 | 비고 |
|---|---|---|---|---|
| em/en dash 회 (grep -o) | 9,653 | 213,286 | +203,633 | 스코프 재정의 필요 |
| em/en dash 파일 | 633 | 636 | +3 | |
| 벽시계 risk_lib 파일 | 25 | 20 | -5 | 라인 이동 가능성 |
| 벽시계 risk_lib 회 | 32 | 25 | -7 | 대표 앵커 25개 여전 LIVE |
| 벽시계 tests 회 | 미측정 | 0 | 청정 | |
| 벽시계 VTA 회 | 미측정 | 11 (7파일) | 기록 | |
| LICENSE 파일 | 부재 | 부재 | 무변동 | F-02 지속 |
| pyproject license 필드 | 부재 | 부재 | 무변동 | 양 저장소 |
| CI risk_lib 커버 | 불포함 | 불포함 (mention 0회) | 무변동 | F-01 지속 |
| RECALCULATORS 커버 | 6/21 (29%) | 6/21 (29%) | 무변동 | C-02 지속 |

**dash 폭증 해석**: 44주차 카운트를 지배하는 것은 `validation-team-agent/harness/reference/bank_supervision_rules_20260630.md` (12,651회) + `bank_supervision_regulation_20260401.md` (2,373회) 두 규정 원문 지문이다. 두 파일이 43주차 카운트에 잡히지 않았다면 지표의 시계열 연속성이 깨진 것이며 지표 정의부터 재확정해야 한다. 신규 코드 유입분도 있다: `pd_cyclicality.py` 자체에 92회 (§3-6 MAJOR).

**risk_lib 벽시계 감소 해석**: 43주차 §1-1 LIVE 18지점의 앵커를 재확인하면 여전히 살아 있고 (`pipeline.py:1502`, `datamodel/decompose.py:191` 등), 재열거하면 25지점 (§1-A). grep 카운트 감소는 다른 파일에서 사용이 사라졌기 때문일 수도, grep 스코프 차이일 수도 있다. 대표 앵커 기준으로는 개선 없음.

## 5. 총결

### 5-1. 이번 주 얻은 것

- 델타 3축 (시장 포지션 원장, PD 설계 판정, 규정 카탈로그 확장) 이 모두 자체 P1 없이 landed. 특히 `pd_cyclicality.py` 는 저장소 표준을 따르는 모범 코드 (임계 SSoT, 시드 고정, 벽시계·CWD 상대 무, 양성·음성 통제, CLI 종료코드, 임계-원문 대조).
- 43주차 §1-2 의 cross_form BR-31 orphan 주장이 오판임을 재검증에서 확인, tracked 목록에서 제거 (§1-B).

### 5-2. 매주 리뷰가 새 BLOCKER 를 파낸다는 사실이 말하는 것

- 43주차: 신규 BLOCKER 11건. 44주차: 신규 BLOCKER 15건.
- **CI 무커버 (F-01)** 이 근본 원인. 2,187 개 top-level 테스트가 서버 사이드에서 한 번도 안 돌고 있어, 리뷰가 지적한 결함이 그 다음 커밋에서 회귀해도 게이트가 없다.
- **사전 커밋 훅 부재** (PR #67 §5-1) 로 em/en dash·벽시계·CWD 상대 경로가 계속 유입.
- **`RECALCULATORS` 확장 3주째 정체** (C-02). 3선 게이트가 71% headline 에 대해 재계산 없이 통과 가능.
- 다음 리뷰가 열리기 전에 최소 셋 중 하나는 반드시 진전해야 한다. 우선순위 제안: (1) F-01 (CI 워크플로우 1개 신설), (2) C-02 (RECALCULATORS 최소 5개 추가), (3) 사전 커밋 훅 (em/en dash + 벽시계 + CWD 상대 3종).

### 5-3. 감독 검사 시 즉시 지적 가능성 높은 3건

1. **`capital/rwa_sa.py:44` SA 코퍼레이트 B bucket 100%** (규정 150%). SA-RWA 저계상 → 자본비율 과대 → BIS 신고 왜곡. Basel III CRE20.36 원문 대조 시 즉시 확인 가능.
2. **`capital/rwa_deep.py:262-289` FIRB LGD 40% 미반영 + `residential_mortgage` 오배정**. FIRB 확정판 규칙 위반. 4단계 감독당국 검증 시 IRB 승인 심사 반려 가능.
3. **`capital/op_risk.py:19-23` `_BI_BUCKETS` EUR 원문 + `use_ilm=True` 기본**. 국내 감독 재량 (Bucket 1 ILM=1) 미반영. Op RWA 부풀림. 감독당국 공표 KRW 환산치를 주입해야 함.

### 5-4. 회로차단기·통제경로 즉시 조치

1. `integrations.py:302-314` `IsolatingDispatcher.send_with_isolation` 3중 크래시. 재해 알림·에스컬레이션 전달 실패 위험. 유닛 테스트 신설 + 세 결함 동시 수정.
2. `report_chrome.py:159` `_table` XSS 삼항 반전. 저장소 사실상 모든 HTML 표에 노출. `<td>{_esc(v)}</td>` 로 단순화.
3. `validation/independent.py:186-189` 응답 파일 무서명. 3선 게이트를 우회하는 평문 JSON 위조 가능. 해시·서명 필드 추가.

---

자체검증 (2선)      해당 없음 (본 리뷰는 리스크 산출물이 아니라 코드 리뷰 산출물)
상시 독립검증 (3선)  해당 없음 (RECALC_SCOPE 밖의 리뷰 산출)

리뷰 도구: 8 병렬 서브에이전트, 소비 약 1.1M subagent tokens, 소요 6~13분 (병렬).
