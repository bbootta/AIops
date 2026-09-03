# 저장소 전수 코드 리뷰 (2026-09-03, 46주차)

**대상**: `bbootta/AIops` 전 저장소, base `origin/main` = `60bda57`, 리뷰 브랜치 `claude/stoic-ride-cl5gln` HEAD = `c750e93`
**직전 리뷰**: 2026-09-02 (45주차), PR #83 (`claude/stoic-ride-flvnxv`, 파일 `reports/code_review/2026-09-02_full_repo_review.md`은 저 브랜치에만 있고 이 브랜치에는 없음)
**델타 창**: 2026-09-02 (`9814480`) ~ 2026-09-03 (`c750e93`), 17 커밋, +851 / -643, 21 파일. 전량 `risk_lib/ui_studio/next/` + `tests/test_ui_next.py` + `risk_lib/ui_studio/app.py` (구 UI 카피 삭제)
**리뷰 방식**: 3 개 서브에이전트 병렬. (A) 45주차 tracked BLOCKER 14 건 재점검, (B) 델타 UI-Next 17 커밋 심사, (C) 저장소 전수 정책 감사 및 PR 소유권 상태

## 0. 총평 (한 문장)

45주차 tracked BLOCKER 14 건은 오늘 델타가 UI-Next 로만 국한된 결과 12 LIVE / 1 PARTIAL / 1 FIXED 그대로 무변동이고 (fix 신규 0, 회귀 신규 0, 앵커 드리프트 0), 이번 델타 자체는 게이트 전파·XSS·벽시계·규제 리터럴 누출 6 개 카테고리 게이트를 전량 PASS 하며 chart 라벨 폭 계산 정식화·`_x_capital` 상품 금액 vs 누적 비율 분리·`_npl_ratio` 원장 일원화 세 가지를 잡았으나, 정책 층에서는 45주차의 em/en dash 개선 (-498 회) 이 이번 회차에 그대로 되돌려져 **+478 회 재증가** 하고 벽시계 유출 +3 회 (+2 파일), 사전 커밋 훅 5주 연속 미배치, 3선 `Pw9F5` 29일 dormant 로 정책 층은 5주 연속 악화 방향이다.

| 층위 | 45주차 | 46주차 | 변화 |
|---|---|---|---|
| Tracked BLOCKER (§1, 14 샘플) | 12 LIVE / 1 PARTIAL / 1 FIXED | 12 LIVE / 1 PARTIAL / 1 FIXED | **무변동** |
| 벽시계 리크 파일·회수 (production) | 38 파일 / 49 회 | **40 파일 / 52 회** | +2 파일 / +3 회 (악화) |
| em/en dash 총합 (파일·회수) | 638 파일 / 9,289 회 | **625 파일 / 9,767 회** | -13 파일 / **+478 회 (45주차 개선분 -498 원상복귀)** |
| 델타 신규 결함 | HIGH 5·MEDIUM 6·LOW 2·MINOR 2 | HIGH 0·MEDIUM 2·LOW 4·MINOR 3 | 신규 9 (등급 하락) |
| 3선 RECALCULATORS 커버리지 | 10 / 21 (48%) | 10 / 21 (48%) | 무변동 |
| 사전 커밋 훅 | 미배치 | 미배치 | **5주 연속 무변동** |
| Pw9F5 (3선) dormant | 28 일 | 29 일 | +1 (누적) |
| B9Kxm dormant | (45주차 기록 27 일, 실측은 22 일) | **22 일** | 45주차 문서 상 수치 오기 지적 |
| 주간 리뷰 PR (#49~#83) | 29 draft open | **30 draft open** | +1 (PR #83 신설, 머지 0) |

**최대 성과 (기록)**:

1. UI-Next 차트 라벨 폭 정식화 (`charts.js` `labelFmt`·`axisAt`·`fitW`·`endLabel`·`rotCap`). 축 라벨 오버플로 뿌리 원인 해결.
2. `_x_capital` 이 상품 금액 (`instrument_amount`) 과 누적 비율 (`ratio`) 을 두 컬럼으로 분리. F2 검수 결함 재발 원천 봉쇄.
3. `_x_kpi` 조각·값 분리, `_npl_ratio` 를 `app._kpis` 에서 뽑아 구 UI 와 신 UI 가 같은 원장 값 사용.

**최대 위험 세 개**:

1. **정책 층 5주 연속 악화**: em/en dash -498 개선이 하루 만에 +478 로 복구. 사전 커밋 훅 부재가 이 패턴을 구조적으로 낳음.
2. **§2-1 M1 (UI 회귀)**: `provFoot` 이 서버가 계속 보내는 `x_screen_gate.scope` (in_scope/out_of_scope) 를 화면 어디에도 렌더하지 않음. 3선 커버리지 투명성 소실.
3. **주간 리뷰 PR 30 건 stack-up**: #49~#83 전량 draft, 머지 0. 5주째 파이프라인 정체. 리뷰가 축적되면서 산출물로 되먹임되는 채널이 실질적으로 닫힘.

## 1. 즉시 조치 (Tracked BLOCKER 재점검, 14 샘플)

45주차 §1 및 §1-7 항목 중 델타 커밋이 만지거나 관련성 높은 14 건 샘플 재검증. 오늘 델타는 UI-Next 국한이라 tracked BLOCKER 소재 파일 무터치. 그럼에도 라인 앵커·구체 코드 인용은 실측으로 확인.

| # | 항목 | 상태 | 근거 |
|---|---|---|---|
| 1 | `risk_lib/pipeline.py:1505` 벽시계 폴백 | LIVE | `pipeline.py:1505` `asof = date.today()` 유지 |
| 2 | `risk_lib/datamodel/decompose.py:190~191` 벽시계 폴백 | LIVE | `date.today().isoformat()` 유지. 45주차·44주차·43주차 3주 연속 재요구, 4주 연속 미이행 |
| 3 | `risk_lib/capital/rwa_sa.py:48` 기업 B 등급 RW | FIXED | `_RW_CORPORATE["B"]=1.50` 유지. CRE20.34 정합 |
| 4 | `risk_lib/capital/rwa_deep.py:291~293` FIRB_LGD 0.45 | LIVE | `np.where(np.isin(ac,("corporate","sovereign","bank")), 0.45, ...)` 하드코딩 유지 |
| 5 | `risk_lib/capital/rwa_irb.py:40~41` LGD 하한 코멘트 | LIVE | "the harness does not auto-floor LGD" 유지 |
| 6 | `risk_lib/models/rating.py:49` bisect off-by-one | LIVE | `bisect.bisect_left(uppers, pd_value)` 유지 |
| 7 | `risk_lib/integrations.py:303~307` IsolatingDispatcher | LIVE | `key = idempotency_key(...)` 산출 후 dedup 미사용, 재시도 sleep/backoff 없음 |
| 8 | `limit_engine.py:41~46` vs `limits_deep.py:55~62` 방향 반전 | LIVE | (CRITICAL ≥ 1.20 · BREACH ≥ 1.00 · WARN ≥ 0.90) vs (BREACH ≥ 1.00 · CRITICAL ≥ 0.90 · WARN ≥ 0.75). 동일 지표 정반대 의미 |
| 9 | `risk_lib/op_loss.py:88` NaN 오염 | LIVE | `float(lognet.std() or 1.0)` 유지. NaN truthy → VaR/ES 오염 |
| 10 | `risk_lib/regulatory/cross_form.py` 누락·오등록 | LIVE | `:32 tolerance=1.0`, BR-31 line `1110` (:61), `1510` (:77), ECL 참조 `("B2403","1020")` (:71) 유지 |
| 11 | `risk_lib/validation/independent.py:215` Finding severity | LIVE | `@dataclass(frozen=True)` `__post_init__` 부재, :257 `Finding(**f)` 검증 없이 삽입. severity 오타는 여전히 게이트 뒤집는다 |
| 12 | `validation-team-agent/tools/independent_recalc.py:230~253` RECALCULATORS | PARTIAL | 10 개 유지 (lcr, nsfr, cet1_ratio, leverage_ratio, icaap_ratio, portfolio_default_rate, rwa_final_total, total_ratio, ecl_total, reserve_shortfall). RECALC_SCOPE 21 중 48% |
| 13 | 사전 커밋 훅 (em/en dash, 벽시계) | LIVE | `.git/hooks/pre-commit` 부재 (샘플만), `.pre-commit-config.yaml` 부재, `.claude/settings.json` `hooks` 키 부재. **5주 연속** |
| 14 | `consistency.py:_check_market_portfolio_split` WARN 우회 | LIVE | `:537~540` `market_positions is None or market_rwa is None` 시 WARN 만, `blocks_approval` 미세팅. `:45~46 passes()` 는 FAIL 만 차단 |

**총 재점검**: 14 건 중 **1 FIXED / 1 PARTIAL / 12 LIVE**. 45주차와 동일. 오늘 델타는 소재 파일 무터치라 이동 없음. 45주차 §6 세 권고 (사전 커밋 훅, `decompose.py:191` 즉시 raise, 신규 fail-closed 게이트 표면 5 지점 봉합) 모두 46주차에도 미이행.

## 2. 델타 신규 결함 (46주차 신규)

델타 17 커밋 (2026-09-02 21:23 UTC 이후) 을 UI-Next 심사 서브에이전트로 병렬 리뷰. 신규 9 건 발굴. **HIGH 0 건** (게이트·XSS·벽시계·규제 리터럴 6 카테고리 전량 PASS).

### 2-1. 델타 UI-Next 17 커밋 (`ebff1bb` ~ `c750e93`)

| # | 파일:줄 | 등급 | 요약 | 재현 시나리오 |
|---|---|---|---|---|
| D1 | `risk_lib/ui_studio/next/static/core.js` `provFoot` 근방 | MEDIUM | `const scope=sg.scope&&sg.scope[id];` 를 읽지만 어디에도 렌더하지 않음. `gateBadge` 재작업 과정에서 "이 화면의 수치 {n}건이 RECALC_SCOPE 에 있고 {m}건은 재계산 대상 아님" 표시 라인이 삭제됐고 `metaDigest`·`gateBadge`·`provFoot` 어느 곳도 그 자리를 이어받지 않음 | 자본 판정 화면에서 헤드라인 수치 5 건 중 2 건이 3선 재계산 대상 아님인 경우, 결재자는 그 사실을 화면에서 알 수 없음. 서버 (`payload_ext.py:493~506`) 는 `in_scope`·`out_of_scope` 를 계속 보냄. `i18n_next.py:211` 대응 키 orphan |
| D2 | `risk_lib/ui_studio/next/payload_ext.py:920~960` `_x_kpi` | MEDIUM | `subs["0"]..subs["5"]` 를 `_app._kpis(studio)` 반환 리스트의 위치 인덱스로 하드코딩. `numeric` 도 `str(i)` 를 키로 씀. `app.py:_kpis` 순서 가정에 얽매임 | `app.py:_kpis` 앞에 신규 KRI (예: 레버리지비율) 삽입 시, "고정이하여신비율 {v}" 조각이 ECL 카드가 아닌 LCR 카드 아래로 이동. 조용한 매핑 오류. 라벨 매칭 (예: `label.startswith("기대신용손실")`) 로 인덱스 도출 필요 |
| D3 | `risk_lib/ui_studio/next/static/base.css:218~223` | LOW | `.aisum.blocked{border-left-color:var(--blocked)}` 는 죽은 규칙. `.aisum` 이 `border-bottom` 으로 톤 표시하도록 바뀌었으나 `blocked` 만 `border-left-color` 로 남음. `good/warn/bad` 는 `border-bottom-color` 로 갱신 완료 | 규칙 기반 요약이 `blocked` 톤을 받으면 상단 요약 스트립에 시각적 톤 표시 실패. 다른 톤은 색이 나오는데 blocked 만 보이지 않아 판정 대비 무너짐 |
| D4 | `risk_lib/ui_studio/next/static/base.css` `.aisum-tag` 중복 | LOW | `.aisum-tag{flex:none;...}` 이 이미 정의된 `.aisum .aisum-tag{...}` 를 넓은 특이도로 덮어씀. 실 영향은 `flex:none` 만이라 미미하나 규칙 중복 |
| D5 | `risk_lib/ui_studio/next/static/core.js` `sectionMeta` `<summary>` | LOW | 접힘 UI 로 만들었으나 접힘·확장 어느 상태에서도 스코프 정보 미노출. D1 과 연결 |
| D6 | `risk_lib/ui_studio/app.py` 구 UI 카피 대거 삭제 | LOW | 구 UI 각 화면 lead·meta·note 문장 절반 이상 삭제. 헤더 "약어" 각주도 사라짐. 규제 수치는 유지되나 실무자가 도메인 축약어 (CET1, LCR, ICAAP, IRRBB 등) 를 스크린만으로 해석 가능해야 한다는 원칙에서 후퇴 |
| D7 | `risk_lib/ui_studio/next/static/charts.js` `labelFmt` (SIG=4) | MINOR | 축·값 라벨을 4 자리 유효 자리로 반올림. `112.34%` → `112.3%`. 표·툴팁·계보는 원본 유지. 규제 수치 잘림은 아니나 자본비율 소수 둘째자리 이하가 라벨에서 사라짐 |
| D8 | `risk_lib/ui_studio/next/payload_ext.py` `_x_kpi` `bind=min(...)` | MINOR | `short` 가 빈 경우에도 계산 자체는 되지만 참조 안 함. `if short: bind = ...` 로 옮기면 의도 명확 |
| D9 | `risk_lib/ui_studio/next/static/charts.js` `EMW=7.9, UPW=9.1, CJKW=13` | MINOR | `test_payload_ext_carries_no_regulatory_literal` 검사 대상 아님. 다만 차트 폰트 (`--fs-op` 12.5px) 와 어긋나면 라벨 잘림. 토큰 변경 시 이 상수도 함께 갱신 필요 (주석 명기됨) |

**카테고리 게이트 요약 (46주차 델타)**:

| 항목 | 결과 |
|---|---|
| 규제 표시 안전 (숫자 조작·null 위장) | PASS |
| Fail-closed 게이트 전파 (`_x_gate` 무변경, `_x_kpi` 응답 파일 미독) | PASS |
| 벽시계 누출 (JS·Python 델타에 `new Date`/`datetime.now`/`date.today`/`time.time` 부재) | PASS |
| XSS 표면 (신규 `innerHTML=` 부재, 템플릿 문자열은 SVG 좌표 숫자만) | PASS |
| em/en dash 정책 (**델타 추가 라인 한정**) | PASS (U+2014·U+2013 0 건) |
| 규제 리터럴 누출 (`payload_ext.py` 신규 float 리터럴 `{"0.0"}` 만) | PASS |
| 번들 예산 (`control.js` 47,838 B < 50,000 B, 여유 4.3%; `models.js` 51,092 B < 52,000 B 여유 1.7% 로 가장 빠듯) | PASS |

## 3. 델타 라운드 긍정 (기록)

부정만 나열하면 실체가 왜곡된다. 46주차에 실제로 landed 한 것.

- **`_x_capital` 컬럼 분리** (ea54b39): 상품 금액과 누적 비율을 한 컬럼에 섞던 F2 검수 결함 재발 원천 봉쇄. `amount=누적`·`instrument_amount=상품` 두 컬럼으로 나누고 i18n 키·리포트 화면·자본 판정 화면·자체검증 툴팁까지 함께 정리.
- **`_x_kpi` 조각·값 분리 + `_npl_ratio` 원장 일원화** (55114b8, 9b62688): 헤드라인 카드의 한국어 산문이 영어 화면에 섞이던 결함을 서버 쪽에서 종결. 구 UI 와 신 UI 가 같은 `app._kpis` 값을 씀.
- **차트 라벨 폭 정식화** (582cfe4, 98fceaf, 6f65477): `labelFmt`·`axisAt`·`fitW`·`endLabel`·`rotCap` 로 축 라벨 오버플로 뿌리 해결. 이전 회차의 "차트 글자 잘림" 반복 결함이 뿌리에서 잡힘.
- **좁은 화면 정리** (5b80b1d, ad63d1e): 보류 사유 개수 서버 집계, 좁은 화면 가로 스크롤 제거, 마감 보드 접힘. 반응형 처리 진전.
- **번들 예산 서면 상향** (6bfa4d7): `control.js` 48 KB → 50 KB 서면 변경. 여유 4.3% 명기, 임의 확대 아님.
- **`test_ui_next.py`** 는 `provFoot` 회귀는 못 잡았으나 파일 크기·규제 리터럴 부재·응답 파일 읽지 않음 세 invariant 는 델타 후에도 통과.

## 4. MAJOR (누계·미소화)

42주차 §2 의 60+ 건, 43주차 §2·§A 의 99+ 건, 44주차 §2 의 20 건, 45주차 §2 의 15 건 전량 미소화 상태 유지. 46주차 델타에서 추가로 관찰된 것은 §2-1 신규 9 건 (HIGH 0 · MEDIUM 2 · LOW 4 · MINOR 3) 이 이에 해당. 등급 분포는 45주차 대비 하락 (HIGH 5 → 0). 단 이는 델타가 UI-Next 렌더링 조정으로 국한됐기 때문이며, 규제 산출 로직 델타 없음의 결과이지 처방의 성숙 결과 아님.

정책 층 3축 (dash 금지 · 벽시계 금지 · pre-commit 강제) 은 45주차 이후 자동화 계층 없이 문서 규범으로만 존재. 46주차 델타 방향은 세 축 모두 악화 (dash +478 · wall-clock +3 · hook 5주). 3선 (Pw9F5) 29일 dormant 는 헤드라인 산출에 대한 상시 독립검증 게이트를 사실상 무력화.

## 5. PR ownership 상태 (매주 확정)

- **`claude/stoic-ride-cl5gln`** (현재 리뷰 브랜치): 46주차 리뷰가 여기로 실림. head `c750e93`. `9814480` 대비 17 커밋 ahead.
- **`claude/stoic-ride-flvnxv`** (45주차 리뷰): PR #83, head `6a0b72c`, base `9814480`, draft 유지, 2026-09-02 이후 무커밋. `2026-09-02_full_repo_review.md` 파일은 저 브랜치에만 있고 이 브랜치에는 없음.
- **`claude/validation-team-agent-Pw9F5`** (3선): head `75c01af`, 마지막 커밋 2026-08-05. **29일 dormant** (+1). CLAUDE.md §6 상시 독립검증 게이트가 fail-closed 로 응답대기 고정. 신규 headline 은 `independent.RECALC_SCOPE` 등록 없이는 3선이 재계산하지 않음.
- **`claude/risk-management-agent-harness-B9Kxm`**: head `f7b532f`, 마지막 커밋 2026-08-12. **22일 dormant**. 45주차 문서상 "27일" 표기는 실측과 5일 어긋나므로 다음 회차부터 실측치 (22일 → 46주차 기준) 기재.
- **주간 리뷰 PR (#49~#83, 30 개)**: 46주차에도 30/30 open + draft 유지, 머지 0. 5주 연속 stack-up 지속. 저장소 전체 open PR 51 건 중 소급 최고령 PR #2 는 2026-05-05.

## 6. 권고 (재발 방지)

우선순위대로 세 개. 45주차 §6-1·§6-2 는 5주차·4주차 재요구. §6-3 는 45주차 §2-2 D3/D6/D7/D8/D10 (fail-closed 게이트 표면) 미봉합 지속.

### 6-1. 사전 커밋 훅 두 개 (**45주차 §6-1 재요구, 5주 연속 미이행**)

이번 회차 dash 재증가 +478 회는 정확히 45주차 개선 -498 회를 상쇄 (실질 -20). 이는 45주차 개선이 델타 커밋 `aec94b8` 의 테스트 파일 손질에서 부수적으로 발생한 일회성이었음을 확증. 자동 차단 없이는 매주 원상복귀 가능.

```bash
# .git/hooks/pre-commit (exec bit 필요)

# (1) em/en dash 차단
if git diff --cached --name-only | xargs grep -l $'\xe2\x80\x93\|\xe2\x80\x94' 2>/dev/null; then
  echo "em/en dash 발견. CLAUDE.md §5 위반." >&2; exit 1
fi

# (2) 벽시계 차단 (production paths)
if git diff --cached --name-only | grep -Pv '^(tests|\.claude|reports|docs)/' | \
   xargs grep -Pn '\bdate\.today\(\)|datetime\.now\(|time\.time\(\)' 2>/dev/null; then
  echo "벽시계 리크. AIMS §2-2 위반. asof 를 인자로 받으세요." >&2; exit 1
fi
```

배치 위치: `.git/hooks/pre-commit` (exec bit) 또는 `.pre-commit-config.yaml` + `pre-commit install`. 46주차 리뷰 시점에도 세 경로 (`.git/hooks/pre-commit`, `.pre-commit-config.yaml`, `.claude/settings.json` `hooks` 키) 전량 부재.

### 6-2. `decompose.py:191` 즉시 raise (**45주차 §6-2 재요구, 4주 연속 미이행**)

`decompose_from_result` 는 `result.meta["asof"]` 필수. 없으면 raise. 44주차·43주차·42주차 명시 지적. 46주차 델타는 datamodel/* 무터치라 이 한 줄 그대로. 44주차 §2 M2 (materialize.py `assert notna` production assert) 도 같은 계열이며 45주차 리뷰가 인용한 `risk_lib/materialize.py` 경로는 부재 (`risk_lib/datamodel/materialize.py` 등이 실경로). 인용 정정 필요.

### 6-3. `provFoot` 스코프 표시 복원 + `_x_kpi` 라벨 매핑 (**46주차 신규**)

§2-1 D1 (MEDIUM): `provFoot` 이 서버가 계속 보내는 `x_screen_gate.scope` (in_scope/out_of_scope) 를 화면 어디에도 렌더하지 않음. 결재자가 이 화면의 헤드라인 수치 중 몇 건이 3선 재계산 대상 아님인지 알 수 없음. 3선 커버리지 투명성 회귀. `sectionMeta` 또는 `provFoot` 안에 한 줄 표시 복원 필요. `i18n_next.py:211` 대응 키 살아있음.

§2-1 D2 (MEDIUM): `_x_kpi` 의 `subs["0"]..subs["5"]` 를 `app._kpis` 위치 인덱스 대신 라벨 매칭 (예: `label.startswith("기대신용손실")`) 으로 인덱스 도출. KPI 삽입·재정렬 시 조용한 매핑 오류 방지.

### 6-4. 45주차 §6-3 재요구 (fail-closed 게이트 표면 5 지점 봉합)

45주차 §2-2 D3, D6, D7, D8, D10 이 미봉합 상태 그대로. 46주차 델타는 `risk_lib/validation/consistency.py`, `risk_lib/close_workflow.py`, `risk_lib/deliverables.py` 무터치이므로 그 5 지점 코드 상태는 45주차 진단 그대로 유지.

## 7. 리뷰 메타 (3 서브에이전트 · 병렬)

- 리뷰 도구: 3 개 병렬 서브에이전트 (general-purpose). 총 소요 약 470 초, 소비 토큰 약 341k.
- 리뷰 커버리지:
  - (A) 45주차 tracked BLOCKER 14 건 재점검 (agent #1, 약 75k 토큰).
  - (B) 델타 UI-Next 17 커밋 심사 (agent #2, 약 195k 토큰).
  - (C) 저장소 전수 정책 감사 + PR 소유권 상태 (agent #3, 약 71k 토큰).
- 자체검증 (2선), 상시 독립검증 (3선): 이 리뷰는 코드 리뷰이며 리스크 산출 아님. `RECALC_SCOPE` 대상 아님.
- 파일: `reports/code_review/2026-09-03_full_repo_review.md` (본 파일).

---

_Generated by [Claude Code](https://claude.ai/code)_
