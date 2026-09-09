# 저장소 전수 코드 리뷰 (2026-08-29, 45주차)

**대상**: `bbootta/AIops` 전 저장소, HEAD = `60bda57`, base = `origin/main` = `00fb2c6`
**직전 리뷰**: `reports/code_review/2026-08-14_full_repo_review.md` (43주차)
**델타 창**: 2026-08-14 → 2026-08-29 (15 일), 40 커밋, +20,686 / -129
**리뷰 방식**: 서브에이전트 2 개 병렬. (A) 40 커밋 델타 신규 리뷰 (`risk_lib/market_portfolio.py` +297, `validation-team-agent/tools/pd_cyclicality.py` +492, 관련 테스트·데이터모델·JSON), (B) 43주차 §1 BLOCKER 6 계열 (13 항목) 재점검.

## 0. 총평 (한 문장)

15 일 델타 40 커밋의 90 % 가 세일즈·법무·아웃리치 문서·템플릿 (docs/sales, kb/legal, templates/sales) 이며 코어 코드 델타는 세 갈래 (시장 포지션 원장 일원화, 270 장 확장 정합, PD 순환성 검증기) 로 집중되어 그 세 갈래는 **깨끗하게 landed**. 그러나 43주차에 tracked 로 잡힌 13 개 BLOCKER 항목 전량이 여전히 LIVE 이고, em/en dash 정책 위반은 이번 사이클에 처음으로 소폭 축소 (**9,653 → 9,524**, -129) 되었지만 사전 커밋 훅은 여전히 미도입.

| 층위 | 43주차 | 45주차 | 변화 |
|---|---|---|---|
| BLOCKER (§1 tracked 13 항목) | 13 LIVE | 13 LIVE | 0 |
| 델타 신규 P1 | -, | 0 건 | 0 |
| 델타 신규 P2 | -, | 5 건 | +5 신규 |
| 델타 신규 P3 | -, | 7 건 | +7 신규 |
| em/en dash (U+2013+U+2014) | 9,653 chars / 633 파일 | **9,524 chars / 625 파일** | **-129 / -8 (첫 하락)** |
| 벽시계 파일 (`date.today`/`datetime.now`) | 25 파일 / 32 회 | 24 파일 / 그대로 | 실질 무변동 |

**최대 위험**: (a) 43주차 6 개 BLOCKER 계열이 두 사이클 (약 4 주) 동안 하나도 해소되지 않았다. tracked 라벨 자체가 통제 기능을 잃고 있다. (b) 델타 코드 자체는 정합적이지만 새 팬텀 갭이 두 곳 열렸다. `materialize.py:407` FK 게이트가 bare `assert` 라 `python -O` 에서 사라지고, `_check_market_portfolio_split` 가 입력 부재 시 fail-open WARN 을 낸다 (§2).

## 1. Tracked BLOCKER 재점검 (43주차 §1 재검증)

전량 LIVE. 커밋 로그로 확인하면 이번 델타 40 커밋 중 tracked BLOCKER 를 겨냥한 커밋은 0 건.

| ID | 항목 | 43주차 상태 | HEAD 상태 | 증거 (file:line) |
|---|---|---|---|---|
| §1-1 | `pipeline.py:1502` wall-clock `asof` | LIVE | LIVE | `risk_lib/pipeline.py:1502` `asof = date.today()`. 43주차에 :1500~1503 `asof_source` 태그만 추가, 폴백 미제거. |
| §1-1 | 18 개 벽시계 사이트 | LIVE | LIVE | 9 개 spot check 전부 미수정. `notifications.py:59`, `deliverables.py:101`, `adjustments.py:308`, `stress/path.py:110`, `archive.py:129`, `report.py:43`, `report_chrome.py:144`, `board_pack.py:87`, `work_report.py:84`. grep 결과 `risk_lib/` 안 `date.today()`/`datetime.now(` 24 파일. |
| §1-2 | `cross_form.py:61` BR-31/1110 | LIVE | LIVE | `risk_lib/regulatory/cross_form.py:61` `("BR-31", "1110")` 그대로. `forms_ext.py:545 br_camel` 여전히 `str(1000 + i*100 + 10)` 위치 기반, 1110 은 총자본비율이 아니라 첫 컴포넌트 지표값. |
| §1-2 | `cross_form.py:77` BR-31/1510 | LIVE | LIVE | `risk_lib/regulatory/cross_form.py:77` `("BR-31", "1510")` 그대로. |
| §1-2 | `forms.py:380` BR-08 tolerance | LIVE | LIVE | `risk_lib/regulatory/forms.py:380` `tol=float(lcr.inflow_capped) + 1.0` 그대로. 항등 통과 불변. |
| §1-3 | 응답 서명·해시 부재 | LIVE | LIVE | `risk_lib/validation/independent.py:185~189` `ValidationResponse.read` 는 `json.loads` + `Finding(**f)` 뿐. body_sha, signer_signature, program-hash 검증 어느 것도 없음. `Finding` (:147) 에 severity whitelist 를 강제하는 `__post_init__` 부재. |
| §1-3 | `RECALCULATORS` 6 / `RECALC_SCOPE` 21 | LIVE | LIVE | `validation-team-agent/tools/independent_recalc.py:140~153` 정확히 6 (lcr, nsfr, cet1_ratio, leverage_ratio, icaap_ratio, portfolio_default_rate). `independent.py:44~90` RECALC_SCOPE 21. **15 개 headline (71 %) 이 여전히 독립 재계산 없음**. |
| §1-4 | `integrations.py:302~314` isolation | LIVE | LIVE | 302~314 미수정. :303~304 `key` 생성 후 dedup 미사용, 저장은 :311~313 dead_letters 만. 재시도 :306~310 back-to-back, sleep/backoff/jitter 없음. |
| §1-4 | limit 심각도 반전 | LIVE | LIVE | `limit_engine.py:41` `if util &gt;= 1.20: return "CRITICAL"` vs `limits_deep.py:56~58` `if util &gt;= 1.00: return "BREACH"` then `if util &gt;= 0.90: return "CRITICAL"`. 같은 utilisation 이 두 엔진에서 정반대. |
| §1-4 | `op_loss.py:88` NaN std | LIVE | LIVE | `mu, sigma = float(lognet.mean()), float(lognet.std() or 1.0)` 그대로. `std()==nan` truthy → sigma=nan, VaR/ES 오염 불변. |
| §1-5 | `test_frtb_inventory.py:183` overdue | LIVE | LIVE | `assert not e.is_overdue()` 그대로. today= 없음. 2030-01-01 시한폭탄. |
| §1-5 | `test_frtb_inventory.py:72,:81` 미시드 RNG | LIVE | LIVE | `np.random.normal(100, 5, 200)` / `(100, 5, 20)` 둘 다 모듈 글로벌 RNG. |
| §1-5 | 4 개 `run_pipeline()` no asof | LIVE | LIVE | `test_frtb_inventory.py:192`, `test_monitoring_deep.py:262`, `test_stress_deep.py:336`, `:350`. |
| §1-6 | em/en dash | 9,653 / 633 파일 | **9,524 / 625 파일** | 첫 감소 (-129 chars, -8 파일, -1.3 %). `.githooks/` `.pre-commit-config.yaml` 여전히 없음. 이번 하락은 손으로 지운 것이지 통제가 아니다. |

**Net movement**: Fixed 0 / LIVE 13 / Regressed 0. 유일한 개선은 em/en dash 소폭 하락 (통제 아님).

## 2. 델타 신규 결함 (45주차 신규)

델타 40 커밋 중 코어 코드 델타 (commits `eaf8907`, `60bda57`, `3912f66`) 의 신규 리뷰. P1 은 없다.

### 2-1. P2: FK 게이트가 bare `assert`, `python -O` 에서 사라진다

- `risk_lib/datamodel/materialize.py:407~409`
- 현행: `assert trade.empty or trade["portfolio_id"].notna().all(), "포트폴리오 미배정 거래..."`
- 실패 시나리오: 하류에서 `synthesise_trading_book` 이 새 `kind` (예: `"future"`) 를 만들면 `KIND_TO_PORTFOLIO.get(...)` 이 None → `portfolio_id` NaN → `mkt_trade.portfolio_id` FK 가 소리 없이 깨진다. `python -O` 배포에서는 assert 자체가 스트립.
- 최소 수정: `if not (trade.empty or trade["portfolio_id"].notna().all()): raise ValueError("포트폴리오 미배정 거래...")`.

### 2-2. P2: `_check_market_portfolio_split` 가 입력 부재 시 fail-open WARN

- `risk_lib/validation/consistency.py:490~493`
- 현행: `if market_positions is None or market_rwa is None: report.add(ConsistencyCheck(name, "WARN", ...)); return`
- CLAUDE.md §6 계약은 "게이트는 fail-closed". 향후 `pipeline.py:1661` 에서 인자 하나가 빠지면 이 검사는 영구 WARN 이 되고 게이트 (2선 자체검증) 는 계속 통과한다.
- 최소 수정: 두 입력이 비대칭으로 None 이면 FAIL, 둘 다 None 이면 WARN (스킵 사유 명시) 로 분기.

### 2-3. P2: `reconciles` 는 검증 극장 (theater)

- `validation-team-agent/tools/pd_cyclicality.py:158` (`math.isclose(mix + level + inter, total_delta, abs_tol=1e-12)`)
- Mix / level / interaction 분해는 대수 항등식 (Σ(w1-w0)p0 + Σw0(p1-p0) + Σ(w1-w0)(p1-p0) = Σw1p1 - Σw0p0) 이라 정상 PD 크기에서는 절대 실패하지 않는다.
- 대응 테스트 `test_decomposition_reconciles_with_the_total` (`tests/test_pd_cyclicality.py:58~64`) 도 극장.
- 수정: 필드 삭제 또는 `mix_effect_share ∈ [0,1]` 같이 실제로 실패할 수 있는 조건으로 교체.

### 2-4. P2: `_by_period` 렉시코 정렬이 분기 라벨에서 순서를 뒤집는다

- `validation-team-agent/tools/pd_cyclicality.py:104`: `sorted(out.items())`
- `mix_level_decomposition` 이 `keys[0]` / `keys[-1]` 로 최초·최근 기간을 결정 → 연도 문자열 (`"2020"~"2025"`) 은 OK, 분기 라벨 (`"2020Q1"..."2020Q10"`) 은 Q10 이 Q2 앞으로 밀림. 테스트가 연도 라벨만 커버하므로 CLI 는 분기 패널에서 "현 시점" 을 잘못 잡고 이상 없이 결과를 낸다.
- 수정: 기간 정렬을 명시적으로 받거나 파싱해서 `(year, quarter)` 튜플로 비교.

### 2-5. P2: `split_positions` risk_class 중복 미제거 → PK 취약

- `risk_lib/market_portfolio.py:190~206` + `risk_lib/validation/consistency.py:497`
- `PORTFOLIO_CAPITAL.primary_key = ("asof","portfolio_id","risk_class")`. 향후 `market_positions` 에 같은 class 두 행 (부호 혼합 등) 이 나오면 `validate(cap, PORTFOLIO_CAPITAL)` 이 중복 PK 로 FAIL, 그 전에 `_check_market_portfolio_split` 는 여전히 대사 통과.
- 오늘 파이프라인은 class 당 1 행이라 latent, 그러나 `capital/market_risk.py:58` 가 이미 pre-aggregate 하는 것과 시맨틱이 어긋나 있다.
- 수정: `split_positions` 앞단에서 risk_class 로 groupby-sum.

### 2-6. P3: `test_a_broken_loading_table_dies_at_import` 이름·검증 미스매치

- `tests/test_market_portfolio.py:44~56`
- 이름은 "at import" 지만 실제로는 `_check_loading_table()` 을 수동 호출. `_PORTFOLIOS` 를 mutate 후 `finally` 복원, pytest-xdist 도입 시 프로세스 공유 워커에서는 위험.
- 두 번째 `pytest.raises(ValueError)` (line 53) 에 `match=` 부재. VaR limit sum 검사가 대신 raise 해도 통과한다.
- 수정: `match="음수"` 추가, 이름을 실체에 맞춰 `test_loading_table_check_rejects_negative_weights` 로 변경.

### 2-7. P3: `pit_tracking` 가중 정규자 분모에 NaN 등급의 가중치 포함

- `validation-team-agent/tools/pd_cyclicality.py:246~257`
- `tw = sum(weights[g] for g in usable)` 가 등급 g 의 필드값이 NaN 인 경우에도 weight 를 포함. 관측 ≥3 인 정상 상태에서는 fire 하지 않지만 분기 leg 자체가 어긋난다.
- 수정: `usable` 을 필드 non-NaN 기준으로 다시 필터링해 분모·분자 동일 집합.

### 2-8. P3: `allocate_var_es` zero-total 분기 무통제

- `risk_lib/market_portfolio.py:238~248`
- `total == 0` 이면 모든 포트폴리오 share=0, `Σvalue = 0 ≠ m["value"]` 인 상태가 소리 없이 통과. `_check_market_portfolio_split` 는 VaR/ES 할당 총계 대사가 없어서 이 어긋남을 잡지 못한다.
- 수정: `mkt_var_es_portfolio` non-empty 인데 total=0 인 경우 FAIL 을 추가하거나 zero-share 분기에서 raise.

### 2-9. P3: `materialize_detail` 상호 의존이 주석 하나에만 명시

- `risk_lib/datamodel/materialize_detail.py:787~789`
- `{**base, **out}` 로 이전 materializer 결과가 다음 materializer 입력에 섞인다. 현행 순서 (`mkt_var_alloc` 가 `mkt_detail` / `mkt_portfolio_detail` 뒤) 는 :771 주석에만 근거. `DETAIL_MATERIALIZERS` 재배열 시 `build_var_es_allocation` 이 조용히 빈 원장 반환.
- 수정: `build_var_es_allocation` 내부에서 `assert "mkt_portfolio_capital" in base` 로 순서 계약을 명시.

### 2-10. P3: `macro_correlation` n=3 에서 검정력 사실상 0

- `validation-team-agent/tools/pd_cyclicality.py:163~183`
- n=3 에서 `p_value &lt; 0.05` 는 |r| ≈ 0.997 필요, "유의하게 상관" 브랜치 사실상 사문화. 테스트 (`test_pit_data_claimed_as_ttc_is_detected`) 는 6 년 합성 패널이라 통과. 실 패널이 짧으면 macro finding 안 뜬다.
- 수정: 최소 n (예: 5) 을 별도 상수로 문서화하고 그 미만이면 skip.

### 2-11. P3: `EVIDENCE` 3/4 는 데드 상수

- `risk_lib/market_portfolio.py:40`, :185
- `EVIDENCE = ("내부기준(합성)", "원문확인", "2차자료", "미확인")` 중 실제 기록은 `"내부기준(합성)"` 하나. 나머지 3 개는 seam 만 있고 배선 없음. CLAUDE.md §2 "사변적 추상 금지" 위반의 미니 케이스.
- 수정: 실제 메타데이터 배선 시점까지 상수 삭제, 또는 각각의 배선 계획 주석 1 줄.

### 2-12. P3: `test_split_preserves_class_positions` 는 항등식

- `tests/test_market_portfolio.py:73~79`
- class 당 weight 합=1, 양수 share 라 대수적으로 항상 성립. split 로직을 실제로 검증하지 않음. `test_weights_sum_to_one_per_class_and_are_positive` 와 중복.
- 수정: 부호 혼합 입력으로 강화 또는 삭제.

## 3. 델타 라운드 긍정 (기록)

- **원장 일원화가 진짜다**. `rwa_market_component.position` 가 더 이상 `capital/0.08` 역산 (`materialize_detail.py:414~423` 제거) 이 아니라 `mkt_position` 집계 (`market_portfolio.build_component_tables:274~279`) 에서 온다. 원장 부재 시 NaN 명시. `test_component_position_comes_from_the_ledger_not_a_back_solve` (`tests/test_market_portfolio.py:154`) 가 이전 공식과의 anti-collision 으로 잠금 (line 164~165).
- **Lineage 가시성** 확보. `test_unification_is_visible_in_lineage` (:184~193) 가 `mkt_position` 을 `rwa_market_component` 의 upstream 으로 실제 발견하는지 확인. 그래서 `materialize_mkt_portfolio_detail` 이 `materialize_detail.py:751~753` 주석대로 비-`materialize*` 이름으로 carve out 된 것.
- **`_check_loading_table` 가 import 시 실행** (`market_portfolio.py:82`). weight 오설정 시 프로세스가 죽는다. 옳은 층에서의 fail-fast.
- **PD 순환성 검증기가 positive · negative control 을 함께 실었다**. `test_pit_data_claimed_as_ttc_is_detected` (`tests/test_pd_cyclicality.py:94`) 가 세 finding (cv, mix share, macro correlation) 을 동시에 걸도록 설계. 커밋 메시지에 초기 구현이 portfolio-average correlation 이라 mislabel TTC 를 +0.936 으로 통과시켰고, self-test 가 잡아 grade-level tracking (`pd_cyclicality.py:217~244`) 으로 수정된 이력이 기록되어 있다. ADV-CALC-06 패턴이 실제로 동작.
- **임계값 외부화 정합**. `pd_design_thresholds.json` 이 수치, `regulatory_criteria.json:1782~1799` 가 세칙 별표 3 원문 인용으로 `pd_min_observation_years=5` cross-check, `test_observation_period_threshold_is_cross_checked_against_the_source` (:133) 로 배선 잠금.
- **경로 안정**. `pd_cyclicality.py:44~45` 가 `Path(__file__).resolve().parent.parent` 앵커. 43주차 §2-2 `gen_flow_html.py:133` 부류의 CWD-상대 함정 없음.
- **270 장 확장 정합**. `NEW_LEDGER_TABLES` 에 `_MKT_PORTFOLIO_TABLES` 편입 (`catalog.py:2666`). `tests/test_architecture.py:56` 가 `ARCHITECTURE.md` 파싱해서 `(270, 2850)` 대사. `test_new_ledger_tables_are_all_in_all_tables` / `test_every_new_ledger_spec_is_registered_or_excluded_with_a_reason` (`tests/test_req_wiring.py:31`, :38) 가 orphan 방지. `GOLDEN_VALIDATION = {"PASS": 71, "WARN": 15}` (`tests/test_pipeline_e2e.py:216`) 도 `market_portfolio_split_reconciles` +1 반영, stale 픽스처 없음.
- **em/en dash 첫 하락**. 손으로 지운 결과지만, 이 지표가 상승 추세를 처음 꺾었다. 사전 커밋 훅을 붙이면 통제로 굳는다.

## 4. 권고 순서 (우선순위)

1. **43주차 tracked BLOCKER 13 항목 중 최소 5 개** (`pipeline.py:1502`, `cross_form.py:61/77`, `forms.py:380`, `limit_engine` 반전, `op_loss.py:88`) 는 물리적 fix 가 수 시간 규모다. 4 주째 미해소는 tracked 라벨 자체를 무의미하게 만든다.
2. **§2-1 `materialize.py:407` bare assert** → `raise ValueError` 로 승격. 5 분 작업.
3. **§2-2 `_check_market_portfolio_split` fail-open WARN** → 비대칭 None 은 FAIL. 5 분 작업.
4. **em/en dash 사전 커밋 훅** 도입. 43주차 §5-1 권고 재차. 이번 첫 하락을 통제로 굳혀야 다시 상승하지 않는다.
5. **§2-3 `reconciles` 필드·테스트 정리** (극장 제거) 와 **§2-4 quarterly period 정렬** 은 pd_cyclicality 커밋의 same-week 마무리.
6. 나머지 P3 는 다음 사이클로 이월 가능.

## 5. 리뷰 자체의 한계 (기록)

- 리뷰 대상 40 커밋 중 코드 커밋 3 개만 심층. 나머지 37 개 (세일즈·법무·아웃리치) 는 문서·템플릿·데이터로 이번 리뷰 스코프 밖. 문서 스코프의 QA 는 개별 팀 하네스 (outreach-qa, legal-red-team) 소관.
- BLOCKER 재점검은 43주차 §1 의 13 항목만 (grep 확인). §2 (MAJOR 65+ 건 누계) 는 이번 사이클 재점검에서 제외. 다음 사이클에 §2 spot check 필요.
- 델타 신규 P1/P2/P3 은 총 12 건. 이 이상의 잠복 결함은 남은 192 개 델타 파일 (대부분 docs) 에는 없을 가능성이 높지만 코드 3 파일 (market_portfolio.py, pd_cyclicality.py, materialize.py) 을 넘어서는 크로스 컷 (예: pipeline.py 배선 재점검) 은 이번 리뷰에서 수행하지 못했다.
