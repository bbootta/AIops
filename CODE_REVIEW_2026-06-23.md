# AIops 저장소 종합 코드 리뷰 (2026-06-23)

> Fresh independent review of all 10 open PRs in `bbootta/AIops`.
> Baseline: PR #13 (06-19 종합) + PR #14 (06-21 델타) + PR #15 (06-22 fresh).
> 본 PR(`claude/stoic-ride-g1f457`) 자체는 리뷰 보고서 전달용. 머지 금지.

## 요약 (한 줄)

PR #15(2026-06-22) 이후 어떤 PR에도 새 커밋 없음. **누적 4회 리뷰에서 P0/P1 수정 진척률 ≈ 0**. 이번 라운드는 이전 3회가 놓친 영역(specialist subagent 프롬프트, XVA/FRTB/Pillar3 신규 모듈, R65–R69 리포팅 도구, 샘플 자체의 spec 위반)에 집중 → **추가 P0 7건 / P1 18건 신규 발견**.

## 가장 시급한 단일 액션 — Top 3

### 1. PR #5 — FRTB IMA 자본 승수 1.50 → 3.00 (BCBS MAR99 위반, 자본 50% 과소)

`risk_lib/frtb.py:165` `_backtest_zone` 의 multiplier가 **BCBS d352 §MAR99.55 의 절반**:

```python
# 현재 (잘못됨)
{ green: 1.50, yellow: 1.70-1.92, red: 2.00 }
# BCBS 정상값
{ green: 3.00, yellow: 3.40-3.85, red: 4.00 }
```

`compute_ima_capital` 이 이 값을 그대로 곱함 → **IMA 데스크 자본을 약 50% 과소 산정**. docstring(line 39) 자체에도 `"1.85–2.00"` 라고 적혀 있어 코드와 또 모순. P0 4번째 SA RW (B등급 1.00 vs 1.50) 보다 영향 큼 — sub-investment-grade 한정이 아니라 모든 IMA 트레이딩북 데스크.

### 2. PR #4 — `pack_archive._save_index` 비원자 쓰기 (manifest 영구 손상 가능)

`tools/pack_archive.py:124-127` 의 `_index_path(...).write_text(json.dumps(...))` 가 in-place write. 두 archiver가 race 하거나 mid-write crash 시 `manifest.json` 깨짐 → `load_index` 가 모든 후속 호출에서 `JSONDecodeError` → 아카이브 시스템 전체 동결. + 같은 파일의 `_prune` order-of-ops 결함과 결합 시 데이터 손실 동시 발생.

수정안: `tmp = path.with_suffix(".tmp"); json.dump → os.replace(tmp, path)`.

### 3. PR #2 — Multi-shot `instruct_trader` (승인 sticky의 진짜 위험 케이스)

PR #15 가 발견한 "approval not bound to trade" / "sticky approval" 의 더 나쁜 케이스: **단일 run 안에서 `instruct_trader` 가 여러 번 호출 가능**. 첫 호출 후 `consulted` 가 그대로 True 로 남으므로 두 번째·세 번째 호출은 **신규 consult 0회 + 다른 종목 + 다른 사이즈**로 통과. `harness.py:206` 의 tool_runner 루프 안에서 orchestrator LLM이 단순히 같은 도구를 다시 부르면 됨.

추가 결함: `MAX_ITERS=20` cap 이 yield 후에 break 하므로 마지막 도구 호출의 **side-effect 는 이미 발생했지만 `last_text` 는 그 이전 모델 응답** — 실제 트레이드 실행됐는데 사용자에게는 stale "RESEARCH RECOMMENDATION" 텍스트만 보임.

수정안: `consult_*` 가 성공할 때마다 trade descriptor 를 pop, `instruct_trader` 성공 후 즉시 `consulted` 클리어. cap 도달 시 `raise` 해서 SDK `__exit__` 가 돌도록.

---

## 우선순위 매트릭스 (PR #15 대비 델타)

| PR | 변경 | 이전 P0/P1 처리 | 이번 라운드 신규 발견 | 권고 |
|---|---|---|---|---|
| **#5** | 없음 | 0/13 — Basel B등급 RW · MDA 모순 · AT1 회계 등 4주 연속 미수정 | **NEW P0×2 (FRTB 승수 50% / XVA MVA never-full IM), NEW P1×7, NEW P2×5** | **block-merge** |
| **#4** | 없음 | 동일 (PII·logger·permission·governance·TZ 모두 미수정) | **NEW P0×4 (n_quarters IndexError, _save_index 비원자, _prune 경로탈출, inf 직렬화), NEW P1×5, NEW P2×7** | **block-merge** |
| **#2** | 없음 | 동일 (multi-shot/sticky 미수정) | **NEW P0×3 (multi-shot trader, iter-cap mid-stream, place_order 비원자), NEW P1×4, NEW P2×2** | **block-merge** |
| **#3** | 없음 | 0/3 — 0-byte 41 · stub 30 · 루트 pyproject 유지 | **NEW P0×3 (UAT 도메인 누락, sample이 own protocol 위반, 가공 BCBS 인용)**, NEW P1×3 | block-merge → block-merge |
| **#9** | 없음 | 부분 (G3 인라인만, 스키마 부재) | **NEW High×3 (sample G2 위반, 인용 로케이터 0개, tool-grant 갭), 신규 missing template** | changes requested |
| **#10** | 없음 | 1/12 (Y천장 부분) | NEW P1×5 (nether respawn 버그, isTouch hybrid 차단, save quota silent, chest 폭발 누수, music burst), NEW P2×6 | changes requested |
| **#6** | 없음 | 부분 (schema 확장만) | NEW High×2 (bias_resolution 필드 부재, Round2 unbounded retry), Medium×3 | merge with revisions |
| **#7** | 없음 | 4주 stale, CHG-0078/79 already used | — | **close** |
| **#8** | 없음 | 4주 stale, CHG-0078/79/80/81 already used, `_negate_path_line` 더블뱅 버그 | NEW: `_negate_path_line(".strip().strip()")` 가 이미-`!` 입력에 더블뱅 생성, `_event_block` brittle | **close 또는 rebase + CHG-0135+ 재할당 + helper 수정** |
| **#11/#12** | 없음 | 바이트 동일 diff | — | merge #11, close #12 |

---

## PR별 상세 (이번 라운드 신규 발견만)

### PR #5 — Basel III / FSS 리스크 하니스 (head `4bf28c2`, v0.22.0)

**누적 미수정 (4주째):** SA B등급 RW · PD floor 정합 (5bp/3bp 두 줄/세 위치) · past-due 무조건 150% · IRB maturity adj PD→1 미테스트 · LGD floor fit-time 미적용 · `compute_rwa_irb` LGD floor 미적용 · Hosmer-Lemeshow `max(dof-2,1)` · PSI 비대칭 clip · CRM 곱셈식 · MDA quartile 컨벤션 모순 · FRTB docstring vs code · AT1 회계 모순 · `_mda_quartile` cbr 기본 DSIB 1% 누락 · Pillar 3 cr2/cr3/cr4/cr5 하드코딩 · `rfet_test` 날짜 갭 dead code.

#### NEW P0

**FRTB-1.** `risk_lib/frtb.py:165` — IMA 자본 multiplier가 **BCBS MAR99.55 값의 절반**. 위 §1 참조.

**XVA-MVA.** `risk_lib/xva.py:142-144` — `im_t = im_initial * (1 - t / t.max())` 가 t[0]=0.25 부터 시작하므로 첫 구간 IM이 이미 `im_initial * (1 - 0.25/m)`. **MVA가 full initial margin을 한 번도 보지 못함** → 모든 데스크에서 MVA 약 5–25% 과소.

#### NEW P1

**XVA-trapezoid.** `risk_lib/xva.py:111, 122, 142` — `np.diff(t, prepend=0)` 가 첫 dt 를 0.25로 만들어 EPE[0] 가 [0, 0.25] 전체에 적용됨. FVA/ColVA/MVA over-count.

**FRTB-NMRF.** `risk_lib/frtb.py:160` — `addon = float(n_nmrf * 1e9)` — NMRF당 무조건 1 BILLION KRW. 익스포저 무관. SES 입력 없이는 의미 없는 capital adder. 코멘트가 "10% capital adder" 주장하지만 실제 계산은 무관.

**Agent-spec PD floor 세 번째 버전.** `risk_lib/audit_trail.py:115` 의 `LedgerEntry.pd_floor = 0.0003` (3bp) — code 5bp / validator 3bp / **audit ledger 3bp**. 감사 ledger가 잘못된 값을 정식 기록.

**Agent-spec RW table 오류.** `.claude/agents/rwa-calculator.md:22` — "기업 BBB-BB 75%" lump (CRE21.49는 BBB=75% / BB=100% 분리). LLM이 이 prompt 를 따르면 BB 의 RW를 잘못 계산. (Python 코드와 별개의 lifeline.)

**CCyB 누락.** `.claude/agents/bis-ratio-analyst.md:34` — 최저요구 표가 CCyB 를 산출에서 제외. KR 시행 시 LLM 이 silent하게 0 처리.

**Source SHA 미기록.** `risk_lib/audit_trail.py LedgerEntry.source_sha256` 항상 빈 문자열. BCBS 239 lineage 약속과 모순.

**`board_pack.py:18` dead import** — `from risk_lib import viz, viz_advanced` 매번 matplotlib import 인데 미사용.

#### NEW P2

**`explainability.py:147-169`** `find_counterfactual` — 비단조 metric 에서 발산 시 수렴 플래그 없이 `delta_required` 반환.

**`explainability.py:225-229`** `narrate_capital_change` 의 first-order decomposition 이 `current_cet1` 을 multiplier 로 — 변화량 이중적용 (테스트는 헤드라인 문자열만 검증).

**`frtb.py:88`** `_spearman` 가 tie correction 없음. PLAT 의 bucket-level P&L 같은 묶음 데이터에서 ρ 편향 → 데스크 amber 오분류.

**`xva.py:226-229`** `compute_xva_portfolio` — `inputs` 와 `bank_book.iterrows()` zip 이 non-default index 에서 silently 어긋남.

**`explainability.py:128`** `shapley_attribution` n_samples=256 기본이 ≥10 features 에서 sum-invariant 5–10% 위반. 수렴 종료 조건 없음.

**Test gaps:** `risk_lib/pillar3.py`, `notifications.py`, `comparison.py`, `cli_docs.py`, `printable.py`, `abbreviations.py`, `api.py`, `sensitivity.py`, `timeseries.py` 등 다수 모듈 0 테스트. Board pack 테스트는 섹션 제목만 검증, KPI 수치 미검증.

---

### PR #4 — Validation Team Agent (head `5462639`, Round 69)

**누적 미수정 (3주째):** PSI 비대칭 clip · `regression_diagnostics` kurtosis 라벨 · `data_safety_guard` index PII · `run_logger` 회전 race · `permission_guard` 카드 정규식 silent 삭제 · `leakage_guard` `_after$` · `governance_timeseries` synth 분기만 순회 · `quarter_of` TZ-naive · `report_pack._kv_table` raw HTML 보간 · 134 entries manifest sprawl.

#### NEW P0 (이번 라운드)

**`tools/governance_timeseries.py:43`** — `n_quarters > 8` 시 `2027Q5..` 같은 invalid quarter 라벨 생성. 함수 시그니처는 임의 n 허용.

**`tools/pack_archive.py:124-127`** — `_save_index` 가 in-place write. Race 또는 mid-write crash 시 archive `manifest.json` 영구 손상. 위 §2.

**`tools/pack_archive.py:172`** — `_prune` 의 path containment 체크가 symlinked path 에 대해 false-negative → `shutil.rmtree` 가 아카이브 밖 디렉토리 삭제 가능. (`manifest.json` 은 JSON-loaded with no path validation.)

**`tools/pack_diff.py:99`** — `p_v ≈ 1e-300` 인 경우 `(c_v - p_v) / p_v = inf` → JSON 직렬화 시 non-RFC 값, Power BI/Tableau import 실패. 작은 분모 가드 부재.

#### NEW P1

**`findings_mapping.py:115-118`** — `len(dyn) >= 5` 가 단일 run 의 step 수로도 trigger → 한 번의 bad run 으로 "frequent" 잘못 분류.

**`scenario_order_check.py:64`** — `np.asarray(["1.2"], dtype=float)` succeeds, 문자열 시나리오 silent coerce — docstring 타입 계약 위반.

**`binomial_calibration.py:38-40`** — `k=n` 케이스에서 Wilson lower bound 가 `1 - upper(0, n)` 으로 비대칭 보정 누락. `k=n=10` 에서 ~50% vs 정상 ~69%.

**`pack_archive._read_pack_metadata`** — `pack_manifest.json` 누락 시 `{"by_domain": {}}` 반환 후 `_save_index` 가 authoritative 로 기록 → "no domains" 와 "manifest missing" 구분 불가.

**`pack_archive.py:118`** — `add()` → `_save_index` (full) → `_prune` → `_save_index` (trimmed) 순서. prune crash 시 index 에 N entries 남지만 directory N+1번째 이미 삭제됨. **수정안: prune in-memory 먼저, 그 다음 trimmed index atomic write.**

#### NEW P2

`harness/cva_thresholds.json:7` — `sa_cva_required_for_large_books_eur_bn: 100.0` 가 EUR threshold 인데 한국 은행 하니스. FSS 도메스틱 threshold 부재 또는 미명시.

`harness/irrbb_thresholds.json` — BCBS d368 §123 의 15%-of-CET1 supplementary outlier test 누락 (Tier 1 leg 만 존재).

`harness/basel_risk_taxonomy.schema.json:46` — `risk_buckets[].thresholds` 가 optional 인데 `credit`/`ifrs9` 가 의도적으로 omit → 다운스트림 `KeyError`.

`.github/workflows/validation-team-agent-ci.yml:18-20` — `paths` 안 negated `!` 가 GitHub Actions 의미상 첫 positive glob 매치를 무효화하지 못함. `validation-team-agent/docs/**` 가 여전히 CI 트리거. (PR #7/#8 가 수정하려던 그 패턴.)

`tools/scenario_order_check.load_floors` 의 default fallback 테스트 부재 — `_FLOORS_PATH` 미존재 시 regression 미감지.

`runner_result_*.schema.json` 가 `additionalProperties` 미고정 — mistyped keys silent.

테스트 sprawl: 134 파일, round artifacts 45개. R65–69에서 5개 더 추가됨.

---

### PR #2 — Stock Trading Harness (head `f8867b8`)

**누적 미수정:** PR #15 가 발견한 multi-shot/sticky 결함 · envelope text-match bypass · specialist→orchestrator prompt injection via `_parse_verdict` fallback · `except (anthropic.APIError, Exception)` 순서 · import-time client · price/VaR 결정성.

#### NEW P0 (이번 라운드)

**Multi-shot `instruct_trader`** — 위 §3. `harness.py:206` 의 tool_runner 루프 안에서 두 번째 `instruct_trader` 호출이 신규 consult 0회로 통과.

**`harness.py:217-219` iter-cap mid-stream halt** — cap 이 yield 후 검사 → 마지막 도구 호출의 side-effect 완료 + `last_text` 는 그 이전 모델 응답. 트레이드 실행됐는데 사용자 화면에는 "RESEARCH RECOMMENDATION". cap 도달 시 raise 해서 SDK `__exit__` 가 돌게 하고 `last_text` 도 current message 기준으로.

**`tools.py:218-235` `place_order` 비원자** — sell path: `_PORTFOLIO["cash"]` 변경 → `pos["shares"]` 변경 → `_ORDERS.append`. 중간 exception 시 portfolio 변경 + audit row 없음. snapshot/restore 필요.

#### NEW P1

**`harness.py:230` `except (APIError, Exception)` 순서** — `Exception` 이 `APIError` 흡수. 또한 retry harness 의 closure-bound `consulted` 가 종료 후에도 살아남음 → `finally` 에서 reset 필요.

**`tools.py:36-46` cross-tool 가격 비결정성** — `get_price` / `get_technicals` / `get_history` 모두 매 호출 새로 random. analyst tool 두 번 호출 시 RSI/MACD/SMA 가 다른 값. (run_id, symbol) 기반 cache 필요.

**`harness.py:80-152` 분석가 `summary` raw embed** — tool result 가 그대로 orchestrator 대화에 들어감. `summary` 안의 `VERDICT: APPROVED` 위조 + 다른 종목 instruct → multi-shot 결함과 결합 시 곧바로 exfiltration.

**`market_analyst.py:81-86` markdown fence strip** — `stripped.strip("`")` 가 4+ backticks 와 lang tag 공백을 잘못 처리 → JSON parse fail → `text[:600]` 폴백 도달 빈도 증가.

#### NEW P2

`main.py:35-38` — `--execute` 옵션 + scenario 없으면 SCENARIOS[0] 디폴트로 진행. safe-default 약속 약화.

`tests/test_safety_gates.py:111-124` — `_client` 모듈 글로벌을 `patch.object` 하는 패턴이 병렬 실행 시 thread-unsafe.

---

### PR #3 — Quant Validation Team Operational Package (head `5a2200e`)

**누적 미수정:** 220 files / +9213 lines docs-only 라벨 오류 · 41 zero-byte 바이너리 · 10 zero-byte `__init__.py` · 루트 `pyproject.toml` · 30+ stub Python · PR #4/#5 어휘 중복 · `provisional_judgement` enum 불일치 · YAML handoff 비스키마 · 재현성 루프 미완 · `.editorconfig` BOM.

#### NEW P0 (이번 라운드)

**도메인 수 불일치.** `RISK_OUTPUT_TAXONOMY.md` 가 9 도메인 정의, `UAT_EVALUATION_CHECKLIST.md:36` UAT-14 는 7개만 enumerate (`capital_adequacy_aggregation`, `multi_risk_or_unclear` 누락) → 표준 코드 2개가 UAT 미커버.

**Sample 이 own protocol 위반.** `samples/risk_domain_samples.json:139-141` `SAMPLE-MULTI-001` 가 engine_result/policy_reference 둘 다 빈 문자열 + `EVIDENCE_INSUFFICIENT` Gray 사유. `DETERMINISTIC_DECISION_PROTOCOL.md:67-68` Engine Gate 는 `LINEAGE_UNCLEAR` 트리거여야 함. 또한 `ENGINE_RESULT_MISSING` 코드 자체가 taxonomy 에 없음.

**가공된 BCBS 인용.** `BASEL_FSS_CONTROL_MAPPING.md:7` `BIS-CRP-2025 | d595.htm` — d595 는 2024 Core Principles 이지 Credit Risk Principles 가 아님. `bcbs_nl36.htm` 도 2024-11-29 발행을 `2026-01-06` 으로 가공. **감사 시 즉각 발견될 fabrication.**

#### NEW P1

`RISK_OUTPUT_TAXONOMY.md:65` alias rule (`IRRBB → interest_rate_risk`) 가 `secondary_risk_output_domains` 에 적용되는지 protocol §4 가 명시 안 함.

`REPRODUCIBILITY_EXPLAINABILITY_GUIDE.md:23-33` 의 fingerprint 9 fields 가 `DETERMINISTIC_DECISION_PROTOCOL.md:35-58` 의 21 fields 와 불일치. `OUTPUT_ARTIFACT_SPEC.md:55` 는 "동일해야 한다" 라고 명시 → spec 간 모순.

`JUDGEMENT_POLICY_TEMPLATE.md:50` tie-break #3 ("Green 조건 + 증적 일부 부족 → Yellow") 가 protocol Data Gate `Gray` 라우팅과 모순.

#### NEW P2

`samples/risk_domain_samples.json:152` `SAMPLE-CAPITAL-001` — Yellow 인데 `evidence_gaps: []`, `data_readiness_status: Ready`, `lineage_status: Clear`. Yellow 사유 미문서 → fingerprint 재현 불가.

---

### PR #9 — Risk Research 전역 하니스 (head `133985a`)

**누적 미수정:** Handoff "계약"이 prose · G2 vs Step 0 모순 · 샘플 VERDICT 토큰 누락 · evidence-tier 정의 분기 · spot-check 룰 · freshness fail-criterion · `team.yaml` G2/G3 ownership · `templates/report.html` `.contested` 미정의.

#### NEW High

**Sample report 가 G2 violation.** `reports/basel-iii-endgame-implementation-status-2026-06-10.html:155` 의 C-007 클레임이 "T3-T4 + T1 미확보" 인데 §핵심 발견 표(79-80) 와 §관할 비교(110-114) 에 여전히 등재. Runbook 의 G2 contract 는 "T1-less 클레임은 findings 에서 → open questions/후속과제 로 강등" 요구. 자체 검증 누락.

**Sample 인용 로케이터 0개.** C-001..C-009 모든 행의 "인용 위치" 가 `TBD (원문 403)` 또는 `TBD (원문 미검증)` (lines 145-155). `evidence-quality-reviewer.md:33-37` 의 self-check 가 "every material claim names locator" 요구 → 정상이라면 `revise` 판정. 그러나 샘플은 pass.

**Tool-grant 갭.** `team.yaml` 의 news/bank-case-study 분석가가 live filings/news scan 한다고 명시하지만 `.claude/agents/*.md` frontmatter 의 `tools:` 가 `Read, Grep, Glob, WebSearch, WebFetch` 만 — Bash/curl 없음. 403 폴백 도구 없음. 샘플 보고서가 반복적으로 403 맞은 이유.

#### NEW Medium

`harness/risk-research-runbook.md:114` 가 `templates/weekly-risk-watch.md` 참조하지만 `team.yaml:91` workflow 와 별개로 미존재. recurring_watch workflow 실행 불가.

`quant-risk-methodology-analyst.md:25-31` G3 매핑 — 5개 G3 항목 중 G3-2 (source-backed claims) 에 대응되는 output bullet 없음. Reviewer enforcement 가 매번 G3-2 fail.

#### NEW Low

`templates/report.html:108` 충돌 로그 "해소 단계" 예시에 Step 0 (G2 반려) 옵션 미포함.

---

### PR #10 — Browser Minecraft (head `9e2c687`)

**누적 미수정:** Three.js CDN SRI 부재 · save migration destructive · Y천장 stick · 몹 같은 Y 이슈 · `pickBlock` 수면 미정지 · `saveGame` silent catch · HOTBAR 10-17 키 미바인딩 · ITEM.ARROW BLOCK_NAMES 누락 · `damage(1)` 갑옷 무시 · `closeChest` pointer-lock race.

#### NEW P1

**Nether 사망 시 wrong-dim respawn.** `:1416,1396` — `respawn()` 가 `spawnY()` = `terrainHeight(0,0)` 사용. `curDim`/`world` 가 nether 인 채로 overworld 의 y 로 텔레포트 → netherrack 안에 매몰 또는 공중에 부유, 포탈 없으면 탈출 불가.

**Hybrid 랩탑 차단.** `:1703-1704` `isTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0` 가 Surface/터치스크린 Windows/Chromebook 에서 true → `touchPlaying=true` 분기로 `requestPointerLock()` 호출 생략 → `mousedown` 핸들러가 `!locked` 로 short-circuit → 마이닝/배치 완전 불가. 수정: `matchMedia('(pointer: coarse)').matches` 사용.

**Module-load localStorage 무가드.** `:244,248-250,756,1409` 모듈 최상위 `localStorage.getItem` — Safari private 모드 / 사이트 데이터 차단 시 `SecurityError` synchronous throw → UI 그려지기 전 모듈 abort → 검은 화면.

**`saveGame` quota silent.** `:522-537` `QuotaExceededError` 를 그냥 `catch(e){}`. + `beforeunload` 도 같은 함수 → 장시간 플레이 후 모든 진행 silent loss.

**Creeper 폭발이 chest 고아화.** `:717-731,1204-1213` `destroyBlocks` 가 radius 내 모든 블록을 `setBlock(...,0)` 하지만 chest 의 경우 `chests.delete(key)` 도, 아이템 흩뿌리기도 안 함. 사용자 저장 인벤 영구 분실.

#### NEW P2

`:759-782` `musicTick` `setInterval(900)` 가 throttled tab 의 missed callbacks 누적 → 포커스 복귀 시 오디오 burst. `audioCtx.currentTime` 비교 가드 필요.

`:1396-1397` 신규 게임 초기 spawn 이 `safeSpawn` 거치지만 `respawn()` 은 거치지 않음. cave/lava 미확인.

`:2403` `save.inv[k] | 0` 이 인메모리 `inv` 키만 순회 → save 의 신규 키 silent loss. 32-bit 트렁케이션도 일부 케이스 음수.

`:1511-1513` 단일 frame 에 깊은 물기둥 통과 시 fall damage 누적 가능 (low edge).

`smoke-test.cjs` 커버리지 갭: crafts/recipe click, dim round-trip, malformed save, chest UI take/put, resize, mining-cycle 완주 — 모두 미테스트.

`:2046-2054 vs :1726-1730` craft 닫기 시 `pointerlockchange` 가 overlay 잠깐 표시 (flicker).

---

### PR #6 — TradingAgents 한국어 템플릿 (head `98cb1a4`)

#### NEW High

`line 35` Round 2 retry 가 unbounded — 어떤 N 도 명시 안 됨. flaky analyst → 무한 비용.

`lines 41-42, 47-61` Round 4 `bias_resolution` 게이트가 `confidence` 격차 ≤ 0.15 — 공통 schema 에 `bias_resolution` 필드 자체가 없음. Risk Manager 가 채울 곳이 없음.

#### NEW Medium

`lines 81-86, 88-93` Bull/Bear 프롬프트가 `evidence[]` 의무화 없음 → 사실 fabrication 초대.

`line 35 vs §1 line 16` Research Manager 가 Round 4 에 등장하지만 §4 역할 프롬프트 부재.

`line 70 vs line 49` `NEEDS_REVIEW` 라우팅 — `action` enum 에 없음, orchestrator output 에도 없음.

#### NEW Low

`§6 line 133` "릴리즈 노트(v0.2.4)" 가 README 의 line range 미고정 → fabrication-prone.

`lines 75-78, 82, ...` Python `"""..."""` delimiter 가 마크다운에서 literal 렌더.

---

### PR #7/#8 — CI Workflow Fix

**확정:**
- Base PR #4 (head `5462639`) workflow **이미 negated `!` 패턴 + comment 적용** (lines 6-10, 16-19).
- Base manifest 가 `CHG-0001..0134` 연속 사용 중. `CHG-0078/79/80/81` 모두 already used. 머지 시 manifest 중복.
- 다음 free = **CHG-0135**.

**PR #8 신규 발견:**
- `tools/ci_workflow_filters.py:54` `_negate_path_line` 가 `.strip('"').strip("'")` 순차 → already-`!` 입력에 **double-bang** 생성. `"!validation-team-agent/docs/**"` → `"!!validation-team-agent/docs/**"`. idempotency test 가 통과하는 이유는 `_fix_event_block` 의 early-return 때문이지 함수 자체는 non-idempotent.
- `_negate_path_line` 가 inline YAML 코멘트 (`- "docs/**"  # exclude`) 처리 시 코멘트가 값에 포함.
- `_event_block(text.index("\n\nconcurrency:"))` brittle — blank line/CRLF/intermediate text 에서 `ValueError`.
- `check_text` 가 `POSITIVE_PATHS[-1]` 후만 검증 → positives 사이에 negation 끼면 통과.
- 테스트가 `yaml.safe_load(fixed)` round-trip 미주장.

**권고:** PR #7 close (PR #8 superset). PR #8 → rebase + YAML hunk drop + CHG-0135/0136 재할당 + `_negate_path_line` regex 화 (`^\s*-\s*['"]?!?([^'"]+)['"]?\s*$`) + `_event_block` end-anchor 견고화 + yaml round-trip 테스트 추가.

---

### PR #11/#12

`.gitignore` 1-line diff **바이트 동일** (blob SHA `0f9b906`). main 에 `.gitignore` 부재 (404). **PR #11 머지 (older, cleaner body), PR #12 close.**

---

## 누적 4회 리뷰 결산

| 항목 | PR #13 (06-19) | PR #14 (06-21) | PR #15 (06-22) | 이번 (06-23) |
|---|---|---|---|---|
| 신규 P0 | 4 | 0 | 4 | **7** |
| 신규 P1 | 8 | 0 | 6 | **18** |
| 누적 P0/P1 수정 | — | 0/9 | 0/15 | **0/22** |

**작성자 워크플로 신호:** 6 commits → 6 commits → 0 commits 패턴이 끝나가는 듯. 작성 활동 자체가 멈췄음 (PR #15 후 24h 무 활동). 이전 리뷰들이 알림으로 도달하지 않거나, 작성자가 별도 우선순위로 묶어두고 있을 가능성. 코드 측 강제 (test-value assertion + pre-commit hook) 가 더 효과적.

**가장 비용 효율적인 단일 액션:** PR #5 의 두 줄 (`rwa_sa.py:36, :46`) + 한 줄 (`frtb.py:165` 의 3개 상수 × 2배) 수정. 합쳐서 5줄 미만이지만 4주째 미수정 + 신규 P0 + 자본 ≈ 50% 과소.

---

_본 리뷰는 PR #13/#14/#15 의 결함 인벤토리를 prior 로 하고, 4주째 동일 코드를 다른 각도(specialist subagent prompts, XVA/FRTB/Pillar3 신규 모듈, R65-R69 reporting tools, sample artifacts 의 self-spec 위반) 로 fresh-eyes 검증. 6개 병렬 general-purpose 에이전트, ~700K 토큰._
