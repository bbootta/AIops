# 저장소 전수 코드 리뷰 (2026-08-17, 45주차)

**대상**: `bbootta/AIops` 전 저장소, base `origin/main` = `153d7d6`
**직전 리뷰**: `reports/code_review/2026-08-16_full_repo_review.md` (44주차, PR #69 draft·미머지, commit `45be97e`)
**델타 창**: 2026-08-16 21:27 → 2026-08-17 (약 24 시간), **0 코드 커밋** (44주차 이후 66 시간 연속 무변경)
**리뷰 방식**: 5 개 서브에이전트 병렬. (1·2·3·5) 미리뷰 표면 신규 발굴 (`integration/`, `models/`, `aig/`, `case_studies/`, `.claude/agents/`, `risk_lib/` top-level 미리뷰), (4) 44주차 §B-x 결함 10 건 반대검증.

## 0. 총평 (한 문장)

45주차 창에도 **코드가 한 줄도 바뀌지 않았다** (누적 66 시간). 그럼에도 5-병렬 sweep 이 이전 리뷰가 다루지 않은 표면에서 **BLOCKER 2, MAJOR 32, MINOR 11 (합 45)** 를 새로 발굴했고, 44주차 §B-x 결함 10 건 반대검증은 **9 CONFIRMED, 1 PARTIAL, 0 REFUTED** 로 44주차 지적 품질을 재확인했다. Tracked BLOCKER 는 43주차 21 + 44주차 8 = 29 건 중 **28 LIVE + 1 PARTIAL + 0 FIXED**. 3주째 (43주차 이후) 순 감소 없음.

| 층위 | 43주차 (2026-08-14) | 44주차 (2026-08-16) | 45주차 (2026-08-17) | 변화 |
|---|---|---|---|---|
| 코드 델타 (커밋) | 8 | 0 | **0** | 66 시간 연속 무변경 |
| Tracked BLOCKER | 21 (LIVE 20, PARTIAL 1) | 29 (LIVE 28, PARTIAL 1) | **29 (LIVE 28, PARTIAL 1)** | -0 |
| 신규 결함 (본 리뷰) | 99 | 52 | **45** | 표면 잔여 여지 확인 |
| 신규 BLOCKER | 11 | 8 | **2** | 재계·아이덴티티 |
| 44주차 결함 sample 반대검증 | , | , | **9/10 CONFIRMED** | 44주차 품질 견고 |
| 3선 RECALCULATORS ∩ RECALC_SCOPE | 6/21 | 4/21 | **4/21 재확인** | -0 |
| em/en dash | 9,653 회 · 633 파일 | 9,119 회 · 633 파일 | **9,513 회 · 623 파일** | +394 회 · -10 파일 (측정 스코프 차 유지) |

**최대 발견 (45주차 신규)**: 두 곳에서 **위치 인덱싱으로 인한 무관 개체 매칭**이 통과 판정 상태로 잔존했다.
- `models/explain.py:106-131` `grade_transition_matrix` 가 `.iloc[:n]` 로 t0/t1 프레임을 위치 페어링, 차주 집합이 다르면 무관 차주끼리 등급 이주 산출 (§B-2 #1).
- `case_studies/__init__.py:285-388` `synthesise_bank_portfolio` 가 클래스별 표본수 계수와 EAD lognormal 평균이 서로 어긋나 KAKAO target 8/32/60 % 가 실측 43/9/48 % 로 조립 (§B-3 #1). 7사 비교 보고서 전체가 이 왜곡 위에 서 있음.

**두 번째로 놀라운 것**: **NaN silent-drop 패턴이 3 모듈에 반복**. `models/estimation/lgd_est.py:397`, `pd_est.py:216` 의 `float(max(raw, fl))` 는 raw=NaN 이면 하한이 조용히 사라지고, 자체검사 `check_pd_floor`/`check_lgd_floor` 는 `dropna` 로 이 케이스를 필터해 결함이 통과 (§B-2 #2, #3). 44주차 §B-1..B-3 이 지적한 silent-drop 계열이 IRB 추정 파이프라인의 하한 강제까지 확장.

**세 번째**: **44주차 결함이 실제로 견고**. 반대검증 10/10 중 9 CONFIRMED, 1 PARTIAL (코드 스니펫 표기 오류만, 결함 방향 유지), 0 REFUTED. 코드 델타 0 인 창에 8 BLOCKER 를 새로 발굴한 44주차의 자기 주장은 이번 sample 에서 그대로 서 있다. "저장소가 리뷰 결과를 소비하지 않는다" 는 44주차 총평도 이번 반대검증으로 재확인.

## 1. Tracked BLOCKER 재확인 (0 커밋 델타, mechanical)

44주차 §1 이 tracked 한 21 건 + 44주차 §B 신규 8 건 = **총 29 건**. 델타 창에 어떤 커밋도 없었으므로 anchor 그대로. Sample 검증으로 §1-2 (BR-31), §1-4 (limits CRITICAL 반전), §A8-2 (LICENSE 부재), §A8-3 (CI validation-team-agent-only), §B6-1 (RECALC 4/21) 실제 확인. §B-x 6 건은 §3 반대검증에서 별도 CONFIRMED.

**요약: LIVE 28, PARTIAL 1 (3선 §1-3), FIXED 0.**

| 원천 | 개수 | 상태 |
|---|---|---|
| 43주차 §1-1..§1-6 (PR #67 기원) | 6 | LIVE 5, PARTIAL 1 |
| 43주차 §A-x 부록 A BLOCKER | 15 | LIVE 15 |
| 44주차 §B-x 신규 BLOCKER | 8 | LIVE 8 |
| **합** | **29** | **LIVE 28, PARTIAL 1, FIXED 0** |

sample-verify 결과 5 지점 (`cross_form.py:61,77`, `limit_engine.py:42` vs `limits_deep.py:59`, `LICENSE*` 부재, `.github/workflows/` 에 `validation-team-agent-ci.yml` 만 존재, `RECALCULATORS ∩ RECALC_SCOPE = {cet1_ratio, leverage_ratio, lcr, nsfr}` 4 개) 모두 44주차 anchor 그대로.

## 2. 45주차 신규 결함 (5-병렬 sweep, 45 건)

**총 신규 결함 45 건** (§B-1 12 · §B-2 13 · §B-3 10 · §B-4 10). §B-5 는 44주차 결함 반대검증 (본 리뷰 §3).

### §B-1. `risk_lib/integration/` (12 신규 결함)

리뷰 파일: `__init__.py, connector.py, engine_adapter.py, inbound.py, resilience.py`.

| # | 심각도 | 파일:줄 | 요약 |
|---|---|---|---|
| B1-1 | MAJOR | `risk_lib/integration/engine_adapter.py:121, 154` | `check_engine_io`는 정의만 되고 `build_engine_adapter`/pipeline 어느 곳에서도 호출되지 않아 (테스트에서만 실행), 도크스트링이 약속한 fail-closed 실행불가/출력누락 판정이 실산출에서 절대 원장에 남지 않는다. 필수 입력이 빠져도 산출은 통과된다. |
| B1-2 | MAJOR | `risk_lib/integration/inbound.py:179` | `sorted({str(v) for v in payload[asof_col].tolist()})`가 `pd.Timestamp('2026-06-30')` 을 `'2026-06-30 00:00:00'` 으로 문자열화한다. 콜러가 parquet/CSV 에서 date/Timestamp 컬럼을 넘기면 실제로 기준일이 맞아도 전건 '기준일불일치' 로 오탐된다. |
| B1-3 | MAJOR | `risk_lib/integration/resilience.py:189, 198, 208` | 격리된 키가 이후 ok=True 로 다시 들어오면 `seen.add(key)` 후 '성공' 으로 기록되지만 QUARANTINE 원장의 `released=False`는 갱신되지 않아, 감사원장은 '격리·미해제' 인데 데이터는 이미 적재된 모순 상태가 조용히 발생한다. |
| B1-4 | MAJOR | `risk_lib/integration/connector.py:172` | `connectors.set_index("connector_id")["access_mode"].to_dict()`가 중복 connector_id 를 무경보로 마지막 행 값으로 덮어쓴다. 실수로 CN-COR 이 두 번 들어가 뒤 행이 '쓰기포함' 이면 조회전용 위반 판정이 사라진다. |
| B1-5 | MAJOR | `risk_lib/integration/resilience.py:197` | `if item.get("ok")`가 'ok' 키 자체가 없는 이벤트를 조용히 False 로 취급한다. 프로듀서가 필드명을 'success' 등으로 잘못 보내면 정상 수신분이 재시도 예산을 소진하고 최종 격리된다. |
| B1-6 | MAJOR | `risk_lib/integration/engine_adapter.py:134` | `for engine_id in adapters["engine_id"]:` 만 순회하므로 `int_engine_io`에 있는데 어댑터에 없는 orphan 선언 (오타·스키마 드리프트) 이 무경보 무시된다. 잘못 배선된 출력은 판정 결과에 흔적을 남기지 않는다. |
| B1-7 | MAJOR | `risk_lib/integration/resilience.py:216, 220` | 첫 격리 시점의 `n_attempts` 만 기록되고 이후 동일 키의 추가 시도는 격리 원장을 갱신하지 않아 실제 재시도 부하가 원장에서 은닉된다. 프로듀서 측 재시도 제한이 원장 기준으로 강제되지 않는다. |
| B1-8 | MINOR | `risk_lib/integration/inbound.py:131, 135` | `cols = sorted(map(str, payload.columns))` 후 `payload[cols]` 로 인덱싱하므로 컬럼 라벨이 int/date/tuple 이면 KeyError 로 `verify_delivery` 가 실패한다. 스키마 오류가 아니라 트레이스백으로 튀어나와 원장에 상태로 남지 않는다. |
| B1-9 | MINOR | `risk_lib/integration/resilience.py:143` | 도크스트링·스펙은 sha256 이라 명시하지만 `hexdigest()[:32]` 로 128 비트만 남긴다. 64 자 hex 를 기대하는 하류 시스템이나 문서 대사에서 형식 불일치를 조용히 감내해야 한다. |
| B1-10 | MINOR | `risk_lib/integration/connector.py:185` | '접근모드 미승인' 위반이 `operation="*"` 로 기록되는데 "*" 는 `CONNECTOR_OPERATION.operation` 에 실제로 쓸 수 있는 문자열이라, 미래에 진짜 "*" 오퍼레이션이 등록되면 `CONNECTOR_VIOLATION` 의 PK `(cid, "*", kind)` 가 실제 위반과 충돌한다. |
| B1-11 | MINOR | `risk_lib/integration/inbound.py:170` | `required_columns` 파싱이 중복 제거를 하지 않아 계약이 'a,a,b' 이면 missing 리스트가 'a' 를 두 번 담고 detail 문자열이 부풀려진다. 계약 오탈자에 취약. |
| B1-12 | MINOR | `risk_lib/integration/inbound.py:130` | 체크섬 입력이 `_ALGO` · `",".join(cols)` · `str(shape)` · CSV 를 도메인 구분자 없이 연쇄한다. 병리적 컬럼명 (예: 'sha256' 로 시작) 이면 서로 다른 페이로드가 동일 체크섬을 낼 이론적 여지가 있다. 실무 확률은 낮으나 함수가 injective 가 아니다. |

**서브시스템 총평**: `integration/` 는 원장·판정·적재 함수를 분리하고 fail-closed 원칙을 도크스트링과 스펙에 명문화한 점, 결정론적 백오프와 내용 지문 기반 멱등키를 도입한 점이 강점이다. 다만 판정 함수 중 `check_engine_io` 가 pipeline 에 실제로 배선되지 않아 광고된 통제가 산출에서 작동하지 않고, `payload[asof_col]` 의 str 강제 변환·격리 후 무경보 재적재·중복 connector_id 흡수 등 조용한 데이터 무결성 훼손 경로가 계층 내에 여러 곳 남아 있다. 원장 (rows) 과 판정 (logic) 이 분리된 구조는 유지하되, 판정 함수를 pipeline 이 반드시 호출하도록 배선하고 dtype·중복·orphan 을 명시적으로 원장에 상태로 남기는 방어층을 한 겹 더 얹어야 지금의 "기록만 있고 검증은 없다" 상태에서 벗어난다.

### §B-2. `risk_lib/models/` + `risk_lib/aig/` (13 신규 결함)

리뷰 파일: `models/discrimination.py, models/explain.py, models/lgd_ead_backtest.py, models/lgd_model.py, models/pd_model.py, models/rating.py, models/estimation/*, aig/trace.py`.

| # | 심각도 | 파일:줄 | 요약 |
|---|---|---|---|
| B2-1 | **BLOCKER** | `risk_lib/models/explain.py:106-131` | `grade_transition_matrix` 가 `.iloc[:n]` 로 짧은 쪽을 자르고 위치로 페어링. 차주 집합이 t0/t1 에서 다르면 (신규 취급·이탈 발생 시) A→B, B→C 처럼 무관 차주끼리 매칭되어 이주율 행렬이 완전히 잘못 나온다. 인덱스 기반 inner join 필요. |
| B2-2 | MAJOR | `risk_lib/models/estimation/lgd_est.py:397, 399` | `float(max(raw, fl))` 에서 `raw=NaN` (예: 회수종료 표본이 없거나 `lgd_realised` 가 전건 NaN 인 세그먼트) 이면 파이썬 `max` 는 첫 인자 NaN 을 그대로 반환 → `after_floor=NaN`, `floor_binding=None`, `final_applied=NaN`. 하한이 조용히 사라진다. `check_lgd_floor` 는 `dropna(subset=["floor_value","final_applied"])` 라 잡지도 않는다. |
| B2-3 | MAJOR | `risk_lib/models/estimation/pd_est.py:216` | 동일 패턴. `after_floor = float(max(raw, fl))`, `raw=NaN` (등급의 코호트 부도율이 전건 NaN, `nanmean` 이 NaN 반환) 일 때 하한이 미적용 상태로 산출을 통과한다. `check_pd_floor` 도 dropna 로 걸러 못 잡는다. |
| B2-4 | MAJOR | `risk_lib/models/pd_model.py:98-103` (`ks_statistic:110` 도 동일) | `gini` 가 `np.argsort` (안정정렬 아님) 후 1..n 을 그대로 배정, 동점 평균순위 처리 없음. 마스터스케일 중위값에 묶인 PD 처럼 동점이 많은 입력에서 결과가 입력 행 순서에 따라 흔들리고 `discrimination.py:auc_roc` (평균순위 처리) 와 값이 어긋난다. 결정론·정확도 이중 결함. |
| B2-5 | MAJOR | `risk_lib/models/estimation/validation.py:292-305` | 표본 표준편차 `se==0` (모든 실측이 동일한 값) 일 때 `p/lo/hi/inside/breach` 가 전부 None 으로 남지만 `status` 는 `"판정완료"` 가 유지된다. `checks.py:244` 의 `check_backtest_inside_range` 는 이 행을 판정완료로 세고 `breach_direction` 이 없으니 최종적으로 PASS 로 보고한다. 검정을 수행하지 못한 케이스가 통과로 둔갑. |
| B2-6 | MAJOR | `risk_lib/aig/trace.py:248-252` | `chain_hash` 가 `redaction_hits`·`redaction_rules`·`prompt_text`·`payload_text` (마스킹 후 본문) 를 포함하지 않는다. 감사자가 사후에 `redaction_rules` 를 `DLP-RRN 3건` 에서 `DLP-EMAIL 1건` 으로 바꿔도 `verify_chain` 이 통과한다. 실제 마스킹 대상·건수가 원장 위조로 사라져도 사슬 무결성이 지켜지지 않음. |
| B2-7 | MAJOR | `risk_lib/models/estimation/ccf_est.py:187`, `validation.py:274` | `groupby(["ccf_type", ...])`/`groupby(group_cols)` 가 pandas 기본값 `dropna=True` 이라 `ccf_type` 이 NaN 인 행이 조용히 산출에서 제외된다. 같은 모듈이 line 137~141 에서 분모 0/음수를 원장에 명시적으로 남기는 정책과 모순. `n_facilities` 에서 이 유형 표본이 사라진다. |
| B2-8 | MAJOR | `risk_lib/models/lgd_ead_backtest.py:695-696` | `cell["workout_complete"] == True/False` 두 필터 모두 None (회수기간 원장 승인 전, `workout_complete=None`) 을 매치시키지 못한다. 결과적으로 `done=0`, `n_censored=0`, `n_defaults=0` 이 되고 `censoring_status='판정불가'` 상태였던 부도건이 원장에서 완전히 사라진다. 재현: `criteria` 에서 `workout_period_months` 를 승인하지 않은 채 `build_lgd_backtest` 실행 → 관측중단 건수가 0 으로 잡힘. |
| B2-9 | MAJOR | `risk_lib/models/estimation/lgd_est.py:544`, `build_defaulted_lgd` | `r["workout_open"].astype(bool)` 가 NaN 을 True 로 변환 (NaN 은 truthy). 회수 원장에 `workout_open` 결측 행이 섞이면 회수종료 건이 부도상태 건으로 분류되어 `n_defaulted_open`·`ead_open` 이 과대집계, ELBE 산식이 잘못된 모집단 위에 선다. |
| B2-10 | MINOR | `risk_lib/models/estimation/pd_est.py:285-289` | 세그먼트에 등급이 하나도 없으면 `moc_statuses=[]` 이고 `all([]) is True` 라 `moc_status='기준미승인'` 이 붙는다. 실제로는 MoC 를 계산조차 하지 않았는데 "기준 미승인으로 계산 안 함" 이라는 완전히 다른 원인을 라벨링. |
| B2-11 | MINOR | `risk_lib/models/discrimination.py:160-178`, `lgd_model.py:184-196` | `calibration_curve`/`lgd_bucket_calibration` 이 `np.linspace(0, n, n_bins+1)` 로 위치를 잘라 버킷 배정. 마스터스케일 등급 midpoint 로 묶인 PD 처럼 동점이 많으면 같은 값이 서로 다른 버킷에 뿌려져 `lower_pd == upper_pd` 인 이웃 버킷이 생기고, HL 검정과 정합성이 깨진다. `pd.qcut(..., duplicates='drop')` 등 동점 처리 필요. |
| B2-12 | MINOR | `risk_lib/aig/trace.py:225`, `_sha256` | `_sha256(prompt_text, payload_text)` 가 각 인자에 `str(p).encode()` 을 수행. `str(None)=="None"` 이라 실제 None 본문과 리터럴 문자열 `"None"` 이 동일한 `raw_sha256` 을 낸다. 필드 경계 `\x1f` 가 필드간 충돌은 막지만 필드 내 None 표현 충돌은 남아 있다. |
| B2-13 | MINOR | `risk_lib/models/estimation/checks.py:219` | `~backtest["out_of_sample"].astype(bool)`. `out_of_sample` 이 NaN 이면 `astype(bool)` 결과가 True (NaN 은 truthy) 로 잡혀 `~True=False`. 표본외 여부 미상 행이 표본외로 조용히 통과. NaN 명시 처리 필요. |

**서브시스템 총평**: 내부등급법 추정 파이프라인 (pd_est/lgd_est/ccf_est) 은 승인 게이팅·미해결 입력 공시·MoC 세 원천 분리 등 조문 대응 자체는 견고하나, **NaN 이 `max()` 안에서 전파되어 하한과 판정을 조용히 무력화하는 패턴이 세 모듈에 반복**되고 자체검사 (`check_*_floor`) 는 `dropna` 로 이 케이스를 필터해 결함을 잡지 못한다. 사후검증 (`validation.py`) 과 사슬 로그 (`aig/trace.py`) 에서도 검정 불가 케이스가 "판정완료" 로, 원장 위조 가능 필드가 사슬 밖으로 각각 새는 구조적 갭이 있어 3선 재계산 이전에 2선 계산기 자체의 fail-closed 원칙을 다시 걸어야 한다. 반면 `discount_capm`/`plgd`/`moc` 는 신뢰수준·베타 표준오차·꼬리표본수를 원장에 나란히 남기는 등 승인·미승인 상태 관리가 모범적이다.

### §B-3. `risk_lib/case_studies/` + `.claude/agents/` (10 신규 결함)

리뷰 파일: `case_studies/__init__.py, bank7_2026q1.py, ib3_2026q1.py, ib3_report.py`, `.claude/agents/*.md` (55 파일).

| # | 심각도 | 파일:줄 | 요약 |
|---|---|---|---|
| B3-1 | **BLOCKER** | `risk_lib/case_studies/__init__.py:285-388` | `synthesise_bank_portfolio` 가 자산군별 표본수를 서로 다른 계수 (기업 0.50·리테일 0.60·주담대 0.20) 로 정하고, EAD lognormal 평균이 클래스별로 20 배 이상 차이 남 (기업 ~0.66B, 리테일 ~29M, 주담대 ~249M). line 389 의 균일 스케일링은 클래스 비중을 바꾸지 못하므로 KAKAO (target 8/32/60 %) 의 실제 EAD 믹스는 약 43/9/48 % 로 산출됨. 이 mix 위에서 계산된 RWA·ECL·스트레스 결과 전체가 신뢰 불가. |
| B3-2 | MAJOR | `risk_lib/case_studies/__init__.py:396-400` | `dlq_mask` 는 `delinquency_ratio*2` 확률로 dpd 1~89 를 부여하고, 이후 `past_due` (default_12m ∩ 0.7) 행에 dpd 90~360 을 덮어씀. 결과적으로 실제 연체율 (dpd>0) = 2·delinq + 0.7·PD 로 프로파일 값 (예: 카뱅 0.51 %) 의 3 배 이상 과대 표본이 만들어져 자산건전성 스냅샷이 공시치와 어긋남. |
| B3-3 | MAJOR | `risk_lib/case_studies/bank7_2026q1.py:137` | 7사 × 3 시나리오 heatmap 의 baseline 열이 `float(0.115)` 로 전 은행 동일 하드코딩. 각 은행의 실제 baseline CET1 (`r.bis.cet1_ratio` 또는 baseline stress 결과) 이 아니라 규제기준선을 표시하므로, "시나리오별 CET1 비율 (7사 비교)" 라는 제목과 달리 baseline 열은 은행 비교가 아니다 (독자 오독 유발). |
| B3-4 | MAJOR | `risk_lib/case_studies/bank7_2026q1.py:109-128` | 그룹 평균 계산에서 시중4·인뱅3 분모를 `sum(...)/4`, `sum(...)/3` 으로 하드코딩. `len(big4)`/`len(ib3)` 가 아니므로 호출자가 BANK7_2026Q1 이 아닌 다른 조합 (예: 은행 5 + 인뱅 3, 또는 데이터 로드 실패로 6사만 남은 경우) 을 넘기면 조용히 잘못된 평균이 산출된다. |
| B3-5 | MAJOR | `.claude/agents/rwa-calculator.md:3, 70-85` vs `:107` | 자기모순: description (line 3) 과 절차 §"시장리스크 RWA (MAR40)"·"운영리스크 RWA (SA)" (line 70~85) 는 이 에이전트가 시장/운영 RWA 를 직접 산출한다고 명시하는데, 같은 파일 line 107 금지 사항은 "시장리스크/운영리스크 RWA 는 별도 영역, credit RWA 만 산출" 이라고 반대로 지시. 에이전트가 자기 스코프를 결정할 근거가 없다. |
| B3-6 | MAJOR | `.claude/agents/market-risk-analyst.md:3` vs `.claude/agents/rwa-calculator.md:3` | 두 에이전트의 description 모두 "시장리스크 RWA (MAR40)" 를 자기 담당으로 광고. `risk-orchestrator.md` line 15·22 의 라우팅 규칙 (RWA→rwa-calculator, 시장리스크→market-risk-analyst) 도 같은 산출을 두 에이전트에 분배하므로, 사용자가 "시장리스크 RWA 계산" 이라 요청하면 어느 쪽이 호출될지 결정 불가. |
| B3-7 | MAJOR | `.claude/agents/terminology-curator.md:26,50` & `translation/knowledge/qa-checklist.md:44` | terminology-curator 는 공식 표기 확인 실패 시 `[미확인]` 마커를 termbase 에 남기지만, accuracy-reviewer / fluency-editor / translation-qa 어디에서도 이를 수집·게이팅하지 않음 (`qa-checklist §D 44 행` 은 `[TN: ...]` 만 수집). 확인되지 않은 기관명·인명 번역이 최종 인도 보고서까지 조용히 통과 (fail-open). |
| B3-8 | MAJOR | `.claude/agents/risk-orchestrator.md:53-56` | validator FAIL 시 "원인 에이전트에 재작업 지시 → 재검증" 루프를 강제하지만 최대 반복 횟수·시간 예산·에스컬레이션 조건이 없음. 만성적으로 실패하는 산출 (예: 데이터 누락으로 매번 `sa_irb_no_overlap` FAIL) 에 대해 무한 재작업하고 audit ledger·부적합 기록만 무한 누적되는 종료 미보장. |
| B3-9 | MAJOR | `.claude/agents/aims-compliance-auditor.md:48` | 재현성 심사 절차가 "실데이터 패키지는 재실행 대신 포트폴리오 지문 (portfolio.sha256) 대조로 갈음" 이라고 예외를 명시. 심사자 툴셋 (Bash, Read, Glob, Grep) 에는 원자재 포트폴리오 접근 경로가 없으므로 대조 대상이 manifest 자신뿐인 자기순환 검증. 조작·손상된 manifest 도 "재현성 적합" 으로 통과할 수 있는 신뢰 오류. |
| B3-10 | MINOR | `.claude/agents/legal-corporate-advisor.md:3` & `.claude/agents/legal-contract-reviewer.md:3` | 두 에이전트 description 모두 "투자계약" 을 자기 담당으로 명시 ("M&A 구조 설계, 투자계약, 공시" vs "계약서·약관·투자계약의 조항 분석"). 사용자가 SAFE·주주간계약 검토를 요청할 때 legal-lead·legal-team 스킬의 라우팅이 무엇을 기준으로 선택할지 규정되지 않음. |

**서브시스템 총평**: case_studies 는 공시치를 프로파일로 받아 파이프라인을 태우는 구조인데, `synthesise_bank_portfolio` 가 자산군 표본수와 EAD 분포를 어긋나게 조합하는 바람에 사용자가 지정한 mix (주담대 60 % 등) 가 실제 산출에는 반영되지 않는다: 이 저장소의 7사 비교 보고서 전체가 이 왜곡 위에 서 있어 CLAUDE.md §6 의 "결재용 헤드라인 수치" 로 쓰기에 부적합하다. 에이전트 층은 rwa-calculator·market-risk-analyst 의 시장 RWA 이중 담당과 rwa-calculator 자기 문서의 상호모순처럼 스코프 경계가 서로 어긋난 지점이 남아있고, orchestrator 의 무한 재작업 가능성과 aims-compliance-auditor 의 실데이터 재현성 자기순환 검증은 fail-closed 원칙과 정면 충돌한다. 번역 파이프라인의 `[미확인]` fail-open 도 같은 계열의 결함으로, 세 층 모두 "누락된 종료·검증 조건" 이 공통 원인이니 44주차 미해결 항목과 함께 다음 스프린트 게이트로 묶는 것을 권한다.

### §B-4. `risk_lib/` top-level 미리뷰 (10 신규 결함)

리뷰 파일 (샘플): `explainability.py, market_feed.py, audit_trail.py, html_exec.py, board_pack.py, concentration_deep.py, funding.py, model_risk.py, notifications.py, printable.py`.

| # | 심각도 | 파일:줄 | 요약 |
|---|---|---|---|
| B4-1 | MAJOR | `risk_lib/explainability.py:226, 253` | `narrate_capital_change` 의 기본 `bis_required=0.08` 이 총자본 최저치를 CET1 임계로 오용. line 253 의 `current_cet1 < bis_required + 0.025` 검사가 CET1 < 10.5 % 에서 "MDA 분배제한 고려 필요" 문구를 붙임. 실제 MDA 트리거는 CET1 < 7 % (4.5 % P1 + 2.5 % CCB), 350bp 위. `ops_pages/governance.py:212` 가 기본값으로 호출해 정상 자본 은행에 허위 경고 문장이 board pack narrative 에 실림. |
| B4-2 | MAJOR | `risk_lib/market_feed.py:263` | `probe()` 가 `"staleness_days": None if pd.isna(f["last_sync"]) else 0.0` 으로 `last_sync` 값 자체를 참조하지 않음. `last_sync` 가 2020-01-01 이고 asof 가 2026-08-17 이어도 staleness=0.0 으로 기록되어 "방금 받은 것" 으로 읽힘. `FEED_HEALTH` 스펙 line 98 이 정확히 이 안티패턴을 경고하는데 코드가 그대로 저지름. staleness 모니터링 무력화. |
| B4-3 | MAJOR | `risk_lib/audit_trail.py:246-254` | `top = conc.loc[conc["normalised_hhi"].idxmax()]` 로 행을 뽑고 `value=float(top["hhi"])` (raw HHI) 로 원장 등재. label 은 "최대 HHI" 이나 실제 선택 기준은 normalised_hhi 라 두 순서가 갈릴 때 감사원장이 실측 최대치와 다른 값을 담음. figure_id `concentration.worst_hhi` 재계산 대상에서 어긋남. |
| B4-4 | MAJOR | `risk_lib/html_exec.py:107, 132` | `briefing_facts` 가 같은 정합 오류. `top = conc.loc[conc["normalised_hhi"].idxmax()]` 후 `conc_hhi = float(top["hhi"])`. CRO 브리핑, 영문 board pack (`localization.py:66`) 에 감사원장과도 서로 다른 HHI 가 표기될 여지. B4-3 과 세 곳이 같은 코드 패턴을 공유해 하나가 틀리면 세 곳이 함께 틀린다. |
| B4-5 | MAJOR | `risk_lib/html_exec.py:382-384`, `printable.py:156-158` | `zip(adv_path, sev_path)` / `zip(base_path, adv_path)` 가 시나리오 경로 길이 불일치 시 조용히 최소 길이로 자름. line 382 게이트는 각 경로 비어있는지만 검사. severely_adverse 가 12 분기이고 adverse 가 8 분기이면 fan chart 의 lower band 가 8 분기에서 잘리고 나머지 분기는 시나리오 정보 없이 표기됨. |
| B4-6 | MAJOR | `risk_lib/board_pack.py:143` | CET1 잉여 카드가 부호와 무관하게 `class="kpi-val good"` 고정. `bis.surplus_shortfall['cet1']` 가 음수 (자본 부족) 인 은행도 리스크위원회 표지에 초록으로 렌더링. Tier1/Total 행은 톤 지정 자체가 없어 CET1 만 오도. |
| B4-7 | MAJOR | `risk_lib/concentration_deep.py:37-39` | `top_obligors` 에서 `sector=("sector", lambda s: s.iloc[0])`, country/asset_class 도 동일. 다업종 차주 (포지션이 여러 섹터에 걸친 obligor_id) 에서 정렬 없는 원 데이터의 첫 행을 취해 섹터·국가·자산군이 파이프라인 삽입 순서에 따라 비결정적으로 귀속. Top-20 표에 표시되는 부문 라벨이 실행마다 달라질 수 있음. |
| B4-8 | MAJOR | `risk_lib/funding.py:200-213` | `build_ladder` 의 마지막 버킷 상한이 3650 일. `tenor_days > 3650` 인 조달거래 (예: 초장기 은행차입, 신규 상품) 는 어느 버킷에도 들어가지 못하고 조용히 사라져 `share` 합·`cumulative_share` 가 1.0 에 못 미침. 스펙이 `cumulative_share max=1.0` 을 강제해 검증 통과하지만 정합성이 깨진 채 원장에 남음. |
| B4-9 | MAJOR | `risk_lib/model_risk.py:91` | `verdict = "CHALLENGER" if challenger.get("gini", 0) > champion.get("gini", 0) + 0.01 else "CHAMPION"`. gini 키가 어느 쪽에도 없으면 0 으로 대체, 챌린저에 gini=0.02 만 있어도 라이브 챔피언을 조용히 대체 승자로 판정. 모델 승격 결정에 silent default. |
| B4-10 | MINOR | `risk_lib/notifications.py:100-107, 160-167` | Slack Block Kit `text.mrkdwn` 과 email HTML 에 `a.title`/`a.detail`/`a.citation` 을 이스케이프 없이 삽입. 검증 체크나 KRI 이름이 mrkdwn 메타문자 (`*_~\`>`) 를 포함하면 서식으로 렌더링되고, HTML 이메일에는 태그 (`<code>`, 또는 임의 마크업) 가 그대로 실려 사내 수신자에게 전달됨. Slack payload 는 `bundle.alerts[:10]` 컷오프에만 의존해 방어 부재. |

**서브시스템 총평**: 이번 주 표본에서 반복 관찰된 패턴은 **"기본값·기본선택이 규제 의미를 넘어 조용히 대신 판정한다"** 이다. `explainability.narrate_capital_change` 의 CET1 을 총자본 임계로 판단한 기본값 (0.08), `market_feed.probe` 의 staleness_days=0.0 강제, `model_risk.challenger_comparison` 의 gini=0 폴백이 모두 같은 방식으로 산출물의 정합성을 훼손한다. 두 번째 축은 **집중도 최대값 선정과 fan chart 경로 정렬에서 raw/normalised 또는 길이 불일치를 조용히 감추는 정합 오류**로, `audit_trail`·`html_exec`·`printable` 이 같은 코드 패턴을 공유해 하나가 틀리면 세 곳이 함께 틀린다. 세 번째는 표시 계층의 하드코딩 (board_pack 의 무조건 green, top_obligors 의 iloc[0] 비결정성) 인데, 화면·감사원장이 실측 부호와 최악 차원을 각각 왜곡할 수 있어 CRO·감독 대응 시 신뢰가 먼저 깨질 자리다.

## 3. 44주차 §B-x 결함 반대검증 (10 sample, Reviewer #4)

44주차 리뷰의 지적 품질을 검증하기 위해 §B-1..§B-6 에서 10 건을 무작위 sample, 실제 파일을 다시 읽어 CONFIRMED / REFUTED / PARTIAL 판정.

| # | 44주차 ID | 판정 | 근거 |
|---|---|---|---|
| 1 | B1-1 | CONFIRMED | `risk_lib/ops_pages/governance.py:498-500` 실제로 `_won(c.computed) if abs(c.computed) > 1 else f"{c.computed:.6g}"` 이며, LCR 1.42 는 `abs>1` 조건에 걸려 `_won(1.42)` 로 렌더된다. |
| 2 | B1-3 | CONFIRMED | `risk_lib/ops_pages/credit.py:1010-1015` 가 `attribution_waterfall([...], [bridge.gap * 0.85, bridge.gap * 0.15], ...)` 로 하드코딩. `compute_cecl` 결과는 `reconcile_ifrs9_cecl` 에만 전달되고 워터폴 분할과 무관. |
| 3 | B2-1 | CONFIRMED | `data_quality.py:143-184` 가 `cap/result.bis.rwa` vs `result.bis.cet1_ratio`, `hqla/net_outflow` vs `lcr.lcr`, `asf/rsf` vs `nsfr.nsfr` 를 비교. 우변 정의 (`bis.py:89`, `lcr.py:449`, `nsfr.py:235`) 가 정확히 같은 나눗셈이라 산술 항등. |
| 4 | B2-2 | CONFIRMED | `catalog.py:1829-1917` 스펙에서 `RDM_FUND_MASTER`, `RDM_FUND_HOLDING`, `RDM_FUND_MANDATE`, `RWA_FUND_RESULT` 모두 `C("asof", "string", ..., nullable=False)` 선언. date-format 미강제. |
| 5 | B2-7 | CONFIRMED | `studio.py:187-189` 가 `rdm_dq_result = dq_result_frame(validate_all(tables, ...), ...)` 로 미리 잠그고, 이후 :194 form_frames, :197-209 UIX/gov, :214-215 run_control, :247 iv request frames 가 추가되므로 이들은 DQ 원장에 나타나지 않는다. |
| 6 | B3-1 | CONFIRMED | `alm/lcr.py:352-354` 실제로 `cat = funding_category_of.get(code); if cat is None: continue` 이며 warn·log 없이 부채 계약을 drop. |
| 7 | B4-1 | CONFIRMED | `.claude/agents/legal-statute-researcher.md:4` 와 `legal-case-researcher.md:4` 모두 `tools: Read, Grep, Glob, WebSearch, WebFetch` (Edit 없음). 반면 `legal-kb-update.js:63,74` 는 "Edit 로 수정" 지시. |
| 8 | B4-8 | PARTIAL | 실코드 :194 는 `r.verdict === 'ACCEPT' \|\| r.verdict === 'MINOR_REVISION'` 로 short-circuit 표현 버그는 존재 안 함. 다만 :192 `.filter(Boolean)` + 고정 `positive >= 2` 임계는 리뷰가 schema 실패로 drop 되면 축소된 분모에서 accept 가능하다는 아키텍처 우려는 실재. |
| 9 | B6-1 | CONFIRMED | `independent_recalc.py:140-153` RECALCULATORS 6 개 (lcr, nsfr, cet1_ratio, leverage_ratio, icaap_ratio, portfolio_default_rate). `independent.py:44-103` RECALC_SCOPE 21 개. 교집합 정확히 4 개, icaap_ratio·portfolio_default_rate 는 scope 밖. |
| 10 | B6-4 | CONFIRMED | `RUN-20260630-42.response.json` 은 request_id·run_id·verdict·validated_by 자유 필드만 담은 plain JSON. HMAC, signature, publisher key, envelope 없음. `validated_by: "적합성검증 팀에이전트"` 는 자유서식. |

**반대검증 총평**: 10 건 sample 중 9 건 CONFIRMED, 1 건 PARTIAL, 0 건 REFUTED. 44주차 리뷰는 파일·라인·산식이 대체로 정확하게 재현되어 지적 품질이 견고하다. 유일한 PARTIAL (B4-8) 도 지적된 결함 클래스 (`.filter(Boolean)` 후 고정 `>= 2` 임계로 축소된 분모 통과 위험) 자체는 실재하며, 다만 예시로 든 `|| 'MINOR_REVISION'` 코드 스니펫이 실제 코드와 다르다는 표기 오류일 뿐 결함의 방향은 유지된다. 코드 델타 0 인 창에서 8 BLOCKER 를 새로 발굴한 44주차의 자기 주장은 이 sample 에서는 그대로 서 있으며, "저장소가 리뷰 결과를 소비하지 않는다" 는 총평도 이번 반대검증으로 재확인된다.

## 4. 총평·권고 (재발 방지)

45 신규 결함 중:

- **BLOCKER 2 건**: B2-1 (`explain.py` 등급 이주 위치 페어링, 무관 차주 매칭), B3-1 (`case_studies` EAD 믹스 왜곡, 7사 보고서 전체가 이 위에 섬).
- **MAJOR 32 건**: 요약: silent-drop (integration/, models/estimation/, ccf_est), 위치 인덱싱 (models/pd_model gini, aig/trace, concentration_deep top_obligors), 정합 오류 (audit_trail/html_exec/printable HHI 세 곳 공유), 기본값 오용 (explainability MDA, market_feed staleness, model_risk gini), 에이전트 스코프 상호모순 (rwa-calculator vs market-risk-analyst, 자기모순 rwa-calculator, legal 두 에이전트 투자계약 중복), 종료 조건 부재 (risk-orchestrator 무한 재작업), 자기순환 검증 (aims-compliance-auditor 재현성).
- **MINOR 11 건**: 표기·이스케이프 (notifications 인젝션), 라벨 오귀속 (pd_est moc), 하드코딩된 순서 (calibration_curve), None → "None" 충돌 등.

**44주차 tracked BLOCKER 우선순위 (43주차 §6 재요구)** 는 45주차에도 동일:

### 4-1. 사전 커밋 훅 두 개 (43·44주차 §6 미이행, 3주째 재요구)

43주차가 권고했고 44주차가 재확인했으나 여전히 미도입. 델타 0 창에서도 em/en dash 는 여전히 저장소 전반 (9,513 회 · 623 파일). `.claude/hooks/` 디렉터리 없음, `settings.json` 에도 훅 항목 없음. 도입이 하루라도 앞당겨졌으면 이후 신규분은 없었다. 다시 요구한다.

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

### 4-2. Reviewer #5 top-5 land-first list (44주차 §2 재확인)

`A8-3` (CI risk_lib 미커버) → `§1-2 / A2-1` (cross_form 항등 통과) → `§1-4` (limit_engine ↔ limits_deep CRITICAL 반전) → `A3-1 / A3-3 / A3-5` (자본·rating 표준 오적용) → `A6-2` (conditional_approval substring bypass). 45주차 신규 중에는 **B2-1 (등급 이주 위치 페어링)** 과 **B3-1 (case_studies EAD 왜곡)** 이 이 리스트에 즉시 얹혀야 한다: B2-1 은 감독당국 IRB 심사에 직접 노출, B3-1 은 이 저장소 7사 비교 보고서 전체의 신뢰 기반.

### 4-3. 3선 RECALCULATORS 확장 (Pw9F5 명시 재요구, 3주째 재확인)

`validation-team-agent/tools/independent_recalc.py:RECALCULATORS` 는 43주차·44주차·45주차 모두 4 개 (RECALC_SCOPE 21 개와의 교집합) 로 확인. `icaap_ratio`·`portfolio_default_rate` 두 개는 아예 RECALC_SCOPE 밖 (fossil). Pw9F5 브랜치 head 는 2026-08-05 (`75c01af`) 이후 dormant, 12 일간 무커밋. 45주차 sample 반대검증도 §B6-1 재CONFIRMED. warden 개입 조건 성숙 (43주차 §6-3 로부터 3주 경과).

## 5. PR ownership 상태

| PR | 상태 | 45주차 |
|---|---|---|
| #69 44주차 리뷰 | draft, 미머지 | 이번 리뷰 이후 정본 대체, close 권고 후 45주차 PR 로 이관 |
| #67 42주차 리뷰 | draft, 미머지 | 45주차 tracked BLOCKER 로 흡수, close 권고 |
| #46 nail-simulation | draft, unowned | **17 주 확정** (last commit 2026-07-27) |
| #38 3D shooter | draft, unowned | 7 주 (last commit 2026-08-02) |
| #57 HANDOVER.md | draft | 7 주 (last commit 2026-08-05) |

- `origin/main` 은 44주차 리뷰 커밋 이후 **66 시간 무변경** (`153d7d6`). 43주차·44주차 리뷰가 요구한 어떤 fix 도 landed 되지 않았다.
- **B9Kxm** (`claude/risk-management-agent-harness-B9Kxm`) 브랜치 head 는 `f7b532f` (2026-08-12 06:18). 5 일간 dormant.
- **Pw9F5** (`claude/validation-team-agent-Pw9F5`) 브랜치 head 는 `75c01af` (2026-08-05 16:34). **12 일간 dormant**. 3선 RECALCULATORS 확장이 이 브랜치 소관.

## 6. 리뷰 메타

- 리뷰 도구: 5 개 병렬 서브에이전트 (general-purpose).
- 커버리지: (1) `risk_lib/integration/` 5 파일 (~40 KB), (2) `risk_lib/models/` 6 파일 + `estimation/` + `risk_lib/aig/trace.py` (~85 KB), (3) `risk_lib/case_studies/` 4 파일 (~65 KB) + `.claude/agents/*.md` 55 파일, (4) 44주차 §B-1..§B-6 sample 10 건 반대검증, (5) `risk_lib/*.py` top-level 미리뷰 (~150 KB, 10 파일 sample).
- 자체검증 (2선), 상시 독립검증 (3선): 이 리뷰는 코드 리뷰이며 리스크 산출이 아님. RECALC_SCOPE 대상 아님.
- 42주차 60+, 43주차 99, 44주차 52, 45주차 45 신규. **누계 256+ MAJOR-이상 결함, 순 감소 없음**. 코드 델타 없이도 리뷰가 계속 새 결함을 발굴 = 저장소 결함 밀도 감소하지 않음. 이 관찰은 44주차와 동일하며, 이번 반대검증이 그 관찰 자체의 신뢰를 강화한다.

---
_Generated by [Claude Code](https://claude.ai/code)_
