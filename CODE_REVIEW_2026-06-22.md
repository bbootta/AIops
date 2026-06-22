# 전체 저장소 코드 리뷰 (2026-06-22)

> Fresh independent review of all 10 open PRs in `bbootta/AIops`.
> Baseline: PR #13 (2026-06-19 종합 리뷰) + PR #14 (2026-06-21 델타).
> 본 PR(`claude/stoic-ride-kbanif`) 자체는 리뷰 보고서 전달용. 머지 금지.

## 요약 (한 줄)

PR #14(2026-06-21) 이후 어떤 PR에도 새 커밋 없음. 이전 P0/P1 결함의 **수정 진척률 ≈ 0**. 이번 리뷰에서 **추가 P0 4건 발견**.

## 우선순위 매트릭스 (PR #14 대비 델타)

| PR | 변경 | 이전 P0/P1 처리 | 신규 발견 (이번 리뷰) | 권고 |
|---|---|---|---|---|
| **#5** | 없음 | 0/9 — Basel B등급 RW 여전히 1.00 | **NEW P1×4**: MDA quartile 모순 / AT1 trigger 회계 / Pillar3 하드코딩 / RFET dead code | **block-merge** |
| **#4** | 없음 | 3/5 (PSI/manifest/binary는 fixed); PII·logger race·permission 미수정 | **NEW P1×2**: governance_timeseries 분기 누락 + TZ 오프바이원 | changes requested |
| **#2** | 없음 | 7/7 fixed (SDK·모델 ID·DRY_RUN·RLock·iter cap·envelope·JSON 분석가) | **NEW P0×2**: 승인이 trade에 묶이지 않음 / 승인 sticky | **changes requested → block-merge** |
| **#10** | 없음 | 1/4 (Y천장 부분개선); CDN SRI·세이브 마이그·체스트 UI race 미수정 | **NEW P0×1**: 체스트 pointer-lock 거부 race / 다수 P2 (slot 10–17 키 미바인딩, 1-dmg 갑옷 우회) — **이전 P0 dispose() 누수는 오진**: `InstancedMesh.dispose()`는 instanceMatrix 버퍼만 해제하며 정상 패턴 | changes requested |
| **#9** | 없음 | 부분 — G3 매핑 인라인 추가 / 여전히 스키마 부재 | 후속과제: `harness/handoff.schema.json` 추가 | merge with follow-up |
| **#6** | 없음 | 부분 — schema 확장 + Bull/Bear tie-break 추가 / `entry_price` 환각 가드는 여전히 prose-only | Trader 프롬프트에 "evidence[] 인용 없으면 null" 조항 추가 권고 | merge with note |
| **#3** | 없음 | 0/3 — 0-byte placeholder 41 + stub Python 30 + 루트 pyproject 유지 | — | changes requested |
| **#7** | 없음 | 워크플로 변경이 base에 이미 적용됨. CHG-0078/79 base에 존재 | mergeable_state: dirty | **close** (PR #8과 중복) |
| **#8** | 없음 | 동일 + CHG-0080/81 추가 충돌 | mergeable_state: dirty | **close 또는 ci_workflow_filters.py만 남기고 rebase + CHG-0135부터 재할당** |
| **#11/#12** | 없음 | `.gitignore` 1줄. 둘 중 하나 머지, 나머지 close | — | one merge, one close |

---

## 가장 시급한 단일 액션 (3개 후보)

### 1. PR #2 — 트레이더 게이트 실효성 복구 (~10줄)

`stock_trading/harness.py:80–152` 의 `consult_*` / `instruct_trader` 가 다음 두 가지 결함을 동시에 가짐:

- **승인이 거래에 묶이지 않음**: 오케스트레이터가 *AAPL 100주* 에 대해 세 전문가 모두에게 승인을 받은 뒤, `instruct_trader("Execute buy 10000 TSLA")` 를 호출하면 `consulted` 가 모두 True 이므로 게이트 통과.
- **승인이 sticky**: `consulted["analyst"] = True` 는 한 번 True 가 되면 재상담에서 NEEDS_REVIEW 가 나와도 리셋되지 않음.

수정안:
```python
# 각 consult_* 안에서
consulted["analyst"] = (verdict == "APPROVED")  # OR 가 아닌 대입
trade_key = canonical_trade(symbol, side, shares)
last_approved_trade["analyst"] = trade_key if verdict == "APPROVED" else None

# instruct_trader 안에서
if not all(last_approved_trade[k] == requested_trade_key for k in ("analyst","risk","portfolio_manager")):
    return {"error": "approvals_missing_or_stale_or_different_trade"}
```

PR #13 이 깔아둔 게이트 자체는 정상이지만, **PR #13/#14 가 이 두 결함을 놓쳤음**. PR #2 의 안전성 약속의 핵심이므로 머지 차단이 필요.

### 2. PR #5 — Basel B등급 RW 두 줄 수정 (3주 연속 미해결)

`risk_lib/capital/rwa_sa.py:22–31, 33–41`:
```python
_RW_BANK_ECRA["B"] = 1.00   # → 1.50 (CRE21.10)
_RW_CORPORATE["B"] = 1.00   # → 1.50 (CRE20.41)
```
PR #13(06-19) → PR #14(06-21) → 이번 리뷰(06-22) 세 번 연속 지적, 6+ commits 동안 미수정. 매 sub-investment-grade exposure 마다 자본을 50ppt 과소 산정. `tests/test_capital.py` 에 `assert sa_risk_weight("corporate","B") == 1.50` 한 줄 추가하면 회귀도 방지.

### 3. PR #4 — `data_safety_guard.scan_dataframe` PII 해시 적용 (한 줄 수정)

`validation-team-agent/middleware/data_safety_guard.py:107`:
```python
"row": int(idx) if isinstance(idx, (int,float)) else idx
# → "row": _hash_match(str(idx))
```
DataFrame 인덱스가 고객번호/주민번호/전화번호인 경우 finding dict 에 평문 노출. 모듈 docstring 의 "PII 비공개" 약속과 직접 모순. 3주째 미수정.

---

## PR별 상세

### PR #2 — Stock-trading harness (head: `f8867b8`)

**Fixed since PR #13 (모두 검증):**
- 실제 SDK API (`beta_tool`, `client.beta.messages.tool_runner`) 사용
- 실제 모델 ID (`claude-opus-4-7`, `claude-sonnet-4-6`) — *주의: PR #13/#14 가 `claude-opus-4-7` 을 "발명된 ID" 로 잘못 지적함. 실제 모델임. 정정 필요*
- 트레이더 게이트 코드 존재 (`harness.py:140–149`)
- `DRY_RUN` 가드 (`tools.py:217–228`) 상태 변이 차단
- `_PORTFOLIO_LOCK = RLock()` 으로 동시 매수 직렬화
- `MAX_ITERS=20` 모든 specialist 에 적용
- `<untrusted_news_item>` envelope 적용
- `market_analyst` 구조화 JSON 출력, raw evidence 드롭

**NEW P0 (이번 리뷰):**
- **승인이 trade 에 비결합**: `consulted` 가 booleans 만 저장 → 다른 종목으로 트레이드 실행 가능 (위 § 1)
- **승인 sticky**: 재상담 NEEDS_REVIEW 가 이전 True 를 덮지 않음

**NEW P1/P2:**
- envelope wrapping 이 텍스트 패턴 매칭만 — 헤드라인에 `</untrusted_news_item>` 포함 시 우회 가능. inner content 의 `<`/`>` escape 필요 (`tools.py:142–152`).
- specialist → orchestrator 방향 프롬프트 인젝션 — `_parse_verdict` JSON 실패 시 `summary = text[:600]` 이 orchestrator LLM 에 그대로 전달됨 (`market_analyst.py:81–86`). Python 게이트는 안전하지만 LLM 단계는 노출.
- `except (anthropic.APIError, Exception)`: `Exception` 이 `APIError` 를 흡수, 프로그래머 오류 silent 처리
- `_client = anthropic.Anthropic()` import-time 인스턴스화 → 테스트 모듈 import 만으로 API 키 요구
- `test_place_order_dry_run_default` 가 모듈 전역 상태 snapshot/restore 없음 → 테스트 순서 의존성

**Verdict: changes requested → block-merge** (트레이더 게이트가 안전 약속의 핵심)

---

### PR #5 — Risk-management harness (head: `4bf28c2`, v0.22.0)

**P0 — 3주째 미수정:**
- `_RW_BANK_ECRA["B"] = 1.00`, `_RW_CORPORATE["B"] = 1.00` → 각각 1.50 (CRE20.41 / CRE21.10) (위 § 2)

**NEW P1:**
- **MDA quartile 컨벤션 모순**: `mda.py` 의 `_MDA_RETENTION = {1:1.00, 2:0.80, 3:0.60, 4:0.40}` (q1 = 가장 깊은 침범) vs `capital_simulation.py` 의 `_mda_retention = {0:0.0, 1:0.40, 2:0.60, 3:0.80, 4:1.00}` (q1 = 가장 얕은 침범). 두 모듈이 같은 필드명을 정반대 방향으로 노출 → 보드팩/Pillar 3 에서 "Q1" 의 뜻이 모순.
- **FRTB backtest docstring vs code 불일치**: `frtb.py` 상단 docstring `yellow: multiplier 1.85–2.00` 인데 `_backtest_zone` 은 `{5:1.70, ... 9:1.92}` (코드가 맞음, MAR99 준수). 감사자 docstring 신뢰 시 잘못된 숫자.
- **AT1 트리거 회계 모순** (`capital_simulation.py:218–225`): `cet1 += conversion; tier1 = cet1 + (tier1 - cet1 - conversion)` 가 write-down 과 conversion 의 half-action 을 동시에 적용 → Tier1 < CET1 가능.
- **`_mda_quartile` 기본 `cbr=0.025`** 에 DSIB 1% 미반영. KR 주요 은행에서 MDA quartile 한 단계 오분류 가능.
- **`find_counterfactual`**: 비단조 metric 에서 발산 가능, 수렴 플래그 없음.
- **Pillar 3 `cr2/cr3/cr4/cr5` 가 하드코딩 시연 데이터**: 35% mortgage / 25% other collateral, `prev_npe = cur_npe * 0.92` 등 만들어낸 prior period. 테스트는 합계만 검증 → 규제 disclosure 가 marketing-deck 상수. 라벨 명시 또는 실 데이터 인풋 강제 필요.
- **`rfet_test` 날짜 갭 체크 dead code**: `if "date" in price_history.columns` 분기 자체가 작동 안 함. 광고된 30일 갭 검사 실제로는 미실행.

**Test gaps:**
- `test_pillar3_capsim.py` 의 다수 테스트가 tautological (other = residual, hardcoded shares sum = 1.0)
- SA 위험가중 테이블 값 자체에 대한 테스트 부재 → P0 가 7+ commits 살아남은 근본 원인
- `_backtest_zone(4)` / `_backtest_zone(10)` 경계 테스트 없음
- `_correlation` 의 Basel 참조값 회귀 테스트 없음

**Verdict: block-merge**

---

### PR #4 — Validation-team-agent (head: `5462639`, Round 69)

**Fixed since PR #13 (검증):**
- `metric_psi.py:61–62, 93–94` PSI 대칭 clip 적용, `_EPS = 1e-4` 명시
- `change_manifest.json` CHG-ID 134개 모두 unique
- 0-byte HTML placeholder 모두 제거

**Still unfixed (P1 — 3주째):**
- `data_safety_guard.py:107` `scan_dataframe` 가 `df.index` 평문 노출. 모듈 docstring 의 PII 비공개 약속과 모순 (위 § 3).
- `run_logger.py:39–51` `_rotate_if_needed` race — `fcntl.flock` / 원자 CAS 없음. 두 워커가 동시에 `replace(.1)` 호출 시 회전된 `.1` 덮어쓰기.
- `permission_guard.py` + `permission_matrix.json` 가 여전히 다음 누락: `git push -f` 단축형, `git push --force-with-lease`, `chmod 777`, `chown`, `sudo`, `su -`, `eval`/`exec`, `curl | bash`, `nc/netcat`, `python -m http.server`, `rsync --delete` (원격), `env`/`printenv` exfil.

**NEW P1 (이번 리뷰):**
- **`governance_timeseries.py:96–111` 가 live audit 데이터를 조용히 누락**: `build_panel` 은 `synth` 의 분기만 순회. `n_quarters=4` 고정 시 audit log 가 `synth` 분기를 벗어나면 라이브 분기가 통째로 사라짐.
- **`quarter_of` 가 timezone 누락**: `run_logger._now_iso()` 가 local TZ 로 기록하는데 `quarter_of` 는 naive parsing → Asia/Seoul 에서 1/1, 4/1 근처 분기 경계가 하루 오프바이원.

**NEW P2:**
- `report_pack._archive_index_page` 가 `e['stress']` / `e['meta']` 를 `_esc` 없이 보간 (`report_pack.py:1213–1214`).
- `_kv_table` (`report_pack.py:407`) 가 raw `{v}` 보간. 미래 contributor 가 user-derived 데이터 넘기면 XSS. 함수 분리 또는 docstring 경고 필요.
- `pack_archive.add()` 와 `_prune()` 사이에 트랜잭션 경계 없음. 인덱스에 저장된 path 가 prune 도중 크래시로 사라질 수 있음.
- `pack_diff` 가 missing key 를 `0` 으로 fallback → 100% relative drop 오보고.

**Verdict: changes requested.** 위 3개 P1 (PII 해시, logger flock, permission 누락) 머지 전 필수. 신규 governance_timeseries 2건도 같은 PR 에서 처리 권고 (규제 보고용 페이지에 직접 영향).

---

### PR #10 — Minecraft (head: `9e2c687`)

**Fixed since PR #13 (검증):**
- Y천장 충돌 일부 개선 (line 1535–1538: `prevY` 복원 + `vel.y = 0`) — 단, 이미 블록 안에서 시작한 엣지 케이스는 남음
- WORLD_VER 충돌 시 사용자 안내 토스트 추가 (line 2444)
- 활 차지 슬롯 인덱스 보정

**Disputing prior P0 (오진 정정):**
- ~~`InstancedMesh.dispose()` 가 GPU 버퍼 누수~~ — **틀린 진단**. `InstancedMesh.dispose()` 는 per-instance `instanceMatrix` 버퍼만 해제. 공유 `boxGeo` / `MATERIALS[t]` 는 그대로. 호출하지 *않으면* 매 rebuild 마다 누수가 발생. **현재 패턴이 정답**.

**Still unfixed P1:**
- **Three.js CDN SRI 부재** (`minecraft/index.html:218`): `https://unpkg.com/three@0.160.0/...` 에 `integrity=` 없음. 공급망 공격 노출.
- **세이브 마이그레이션 비파괴 처리 안 됨**: WORLD_VER 변경 시 그냥 `localStorage.removeItem(SAVE_KEY)`. 토스트만 추가됨, 사용자 블록 편집은 여전히 소실.

**NEW P0:**
- **체스트 닫기 시 `requestPointerLock` 거부 race** (`closeChest()` line 2268): 브라우저가 락 요청을 거부하면 `pointerlockchange` 가 fire 안 됨 → 오버레이 숨겨진 채로 게임 상태 정지. Esc 후 비보안 컨텍스트에서 재현 가능.

**NEW P1/P2:**
- HOTBAR 17 슬롯이지만 키바인딩은 1–9. `BLOCK.CHEST`, foods, `ITEM.SEEDS`, `ITEM.BOW`, `BLOCK.PORTAL` 키보드 접근 불가.
- `ITEM.ARROW (105)` 가 `BLOCK_NAMES` 에 없음 → chest UI/인벤토리에서 "105" raw 표시.
- `damage(1)` 이 갑옷 무시 — `Math.max(1, Math.ceil(n*(1-red)))` 가 1뎀 공격 (드라우닝, 굶주림, 작은 낙뎀, 용암 tick) 에서 다이아몬드 갑옷 60% 감소 적용해도 ceil(0.4)=1 → 항상 1. 의도와 다를 듯.
- `closeChest()` 자체와 별개로, `for (const it in data) inv[it] += data[it]` 가 nested chest scenario 에서 double-count.
- 몹 리스폰 race: 야간 `respawn()` 직후 인접 좀비의 `atkT` 가 0 으로 초기화되지 않아 즉사 루프 가능.
- Settings 슬라이더가 `input` 이벤트마다 `localStorage.setItem` → 드래그 중 ~60 writes/sec. 메인 스레드 블로킹.
- `spawnAnimals()` 가 최초 오버월드 진입에만 호출 → 죽인 동물 재로딩 전까지 미리스폰.
- 청크 rebuild 가 매 편집마다 self + 4 카디널 → 분당 수백 InstancedMesh 재할당. 연속 채굴 시 성능 문제.

**Verdict: changes requested.** SRI 핀 + 체스트 race 두 건은 머지 전 필수. 나머지는 후속 Round.

---

### PR #3 — Quant validation team agent (head: `5a2200e`)

**State change:** PR #13 이후 PR description 만 갱신. 코드 변경 없음. 베이스 (`cad0f4a`) 와의 rebase 도 안 됨.

**미해결:**
- 220 files / +9213 lines — 여전히 "docs-only" 라벨이 부정확
- 41개 0-byte 바이너리 placeholder (`outputs/**/*.pdf|hwpx|xlsx`)
- 10개 0-byte `__init__.py`
- 루트 `pyproject.toml` (+18 lines) docs-only 와 모순
- 30+ stub Python 파일 (2-5 줄짜리) under `risk_team_agent_harness/app/**`, `scripts/**`
- PR #9 의 `risk-research-lead` 와 디렉토리/어휘 겹침

**Verdict: changes requested.** 0-byte 제거, 루트 빌드 설정 분리 또는 정당화, stub Python 완성 또는 제거.

---

### PR #6 — TradingAgents Korean template (head: `98cb1a4`)

**Fixed since PR #13:**
- `size`, `stop_loss`, `time_horizon` schema 추가
- Analyst quorum 규칙 (>=3/4 valid JSON) 추가
- Bull/Bear tie-break 프로토콜 (Risk Manager `bias_resolution` 게이트)
- Confidence range `[0.0, 1.0]` + HOLD-floor 0.5 문서화

**남은 결함:**
- `entry_price` / `stop_loss` 환각 가드 여전히 prose-only. 시장 데이터 없이 ticker 만 받은 LLM Trader 가 임의 십진수 발행 가능. 스키마 validator 도, "evidence 인용 없으면 null" 규칙도 없음.

**Verdict: merge with note.** Trader 프롬프트에 1줄 추가: *"`evidence[]` 에 시장-데이터 출처 인용 없을 시 `entry_price` / `stop_loss` 는 반드시 null."*

---

### PR #7 — CI path-filter fix v1 (head: `a60443b`)

- 베이스 브랜치 `claude/validation-team-agent-Pw9F5` 에 동일 워크플로 수정 이미 적용됨 → 워크플로 diff 는 no-op
- 베이스 manifest 가 CHG-0078, 0079 이미 사용 중 (현재 CHG-0134 까지)
- GitHub `mergeable_state: dirty`

**Verdict: close** — PR #8 에 흡수.

---

### PR #8 — CI path-filter fix v2 + fixer tool (head: `574f8a1`)

- PR #7 동일 문제 + CHG-0080/81 추가 충돌
- `tools/ci_workflow_filters.py` 헬퍼 자체는 유용 (single-quote handling, reversed-order ValueError, idempotency 테스트)
- `mergeable_state: dirty`

**Verdict: close 또는 강제 정리.** 정리 안: ① 워크플로 YAML 편집 drop, ② `tools/ci_workflow_filters.py` + 테스트만 유지, ③ CHG-0135 부터 재할당, ④ 베이스에 rebase.

---

### PR #9 — Global risk research harness (head: `133985a`)

**Fixed since PR #13:**
- 각 specialist Output bullet 에 G3-1..G3-5 매핑 인라인 주석 추가
- `team.yaml` root nesting 수정
- G2 강화: T1-absent claim 은 findings 가 아닌 open questions 로
- Rapid-scan 자체-체크 enumeration 추가

**남은 결함:**
- G3 handoff contract 가 prose 인라인 주석 — 머신 체크 가능한 schema 가 아님
- `harness/handoff.schema.json` 없음
- `team.yaml` 가 contract 를 형식화 안 함 → 향후 drift 검출 불가

**Verdict: merge with follow-up.** 다음 PR 에서 `handoff.schema.json` 추가 + `team.yaml` 에서 reference.

---

### PR #11 / #12 — `.gitignore` 1줄 (`.claude/worktrees/`)

PR #13 결론 그대로: 동일 변경의 중복. 하나만 머지, 나머지 close.

---

## 교차 PR 관찰

1. **PR #14 의 PR #5 P0 지적이 효과를 못 냄.** 어제(06-21) 명시했음에도 06-22 현재 미수정. 알림 채널이 작성자에게 닿지 않거나 작성 워크플로가 리뷰 코멘트를 읽지 않을 가능성. 코드 측 강제 수단(table-value 테스트, pre-commit `assert sa_risk_weight("corporate","B") == 1.50`)이 필요.

2. **PR #13/#14 가 `claude-opus-4-7` 을 "발명된 ID" 로 잘못 단정.** 실제 Anthropic 모델임을 정정. 모델 ID 검증은 향후 리뷰에서 `claude-api` 스킬 또는 SDK 모델 목록으로 교차 확인 권고.

3. **PR #10 의 `InstancedMesh.dispose()` P0 오진 정정.** Three.js 의 `dispose()` 는 per-instance 버퍼만 해제하며 현재 패턴이 정답. PR #13/#14 의 "GPU 버퍼 유출" 항목은 철회.

4. **PR #4 의 PII / logger race / permission 3건이 13→14→이번 3주 연속 미해결.** PR #5 와 같은 채널 문제. 작성자가 변경하기 쉬운 1줄짜리 수정인데도 손대지 않음.

5. **PR #7/#8/#11/#12 의 중복 정리** — 4건 모두 본질이 base 와 충돌하거나 서로 중복. base 정리 후 매 PR 별 1줄 머지 결정 필요.

## 리뷰 방식

- 6개 병렬 general-purpose 에이전트 (#2, #4, #5, #10 단일 + #3+#6+#7+#8+#9 그룹)
- 각 에이전트: `mcp__github__pull_request_read get_diff` + `mcp__github__get_file_contents` 로 head SHA 의 파일 직접 읽기
- 이전 리뷰 (PR #13, PR #14) 의 결함 인벤토리를 입력으로 제공, "fresh independent" 시각 요청
- 약 ~780K 토큰 (PR #13 ~500K 대비 큰 PR #2/#5 에 더 깊이 들어감)

---

_본 PR(`claude/stoic-ride-kbanif`) 은 리뷰 보고서 전달용. 머지하지 말 것._
