# 전체 저장소 코드 리뷰 — 9주차 (2026-07-04)

> **본 PR 은 리뷰 보고서 전달용. 머지 금지.**
>
> **9주차 관측:** 8주간 이어진 "author 커밋 0 / prior finding 수정 0" 패턴이 **깨졌음**. 2026-07-03(어제) PR #4·#5·#10 세 곳에 신규 커밋 총 **18건** 유입. 특히 PR #10 은 이전 리뷰 P0/P1 중 **6건이 실제로 fixed** 상태로 확인 — prose 채널이 늦게라도 도달했다는 첫 신호. 반면 PR #2 는 여전히 6/15 이후 무변화이고, PR #5 는 v0.23–v0.27 대규모 신규 기능(SRISK·CoVaR·intraday·CECL·external integrations)을 추가했으나 이전 지적 P0/P1 은 대부분 그대로.

## TL;DR

- **신규 커밋 18건** (PR #4×2, PR #5×12, PR #10×4) — 2026-07-03 09:00–09:15Z 사이 집중 커밋. PR #2/#3/#6/#7/#8/#9/#11/#12 는 이전 상태 유지 (마지막 활동 6/15 이하).
- **신규 P0 1건** — PR #5 `risk_lib/systemic.py:61` SRISK 공식이 `(1-k)` 인자 누락 → 은행별 SRISK 를 `k·(1-LRMES)·E` (~8%) 만큼 과소평가. 신규 시스테믹 모듈의 핵심 지표 오류.
- **신규 P1 8건 / P2 8건** — v0.23-v0.27 신규 모듈 위주 (CoVaR own-loss 편향, FRTB yellow-zone 계수, intraday PnL 부호 규약, webhook SSRF 미방어, CECL EIR 하드코딩 등).
- **PR #10 P0/P1 6건 실제 FIXED** — InstancedMesh dispose, Y-ceiling, chest pointer-lock race, F-flight fallDist, music burst, R keyup + hotbar 9-slot. 여전히 잔존: applyPos NaN, saveGame sync stall, nether respawn, chest-explosion 콘텐츠 유실.
- **PR #4 partial fix 확인** — `record_feedback` sensitivity guard 를 middleware 로 위임 (5개 영문 regex → data_safety_guard 델리게이션). 다만 (a) `try/except: return []` 침묵 우회, (b) `allow_sensitive=True` 시 원문 저장, (c) 한국어 freeform PII (이름·주소·비정형 계좌 ID) 미차단 → **P0 → P1 로 강등** 하되 유효 결함 유지.
- **이전 리뷰 오판 2건 정정:**
  1. **PR #5 `risk_lib/frtb.py` multiplier 1.5**: PR #16/#17/#18 이 "BCBS MAR99.55 값 3.0 의 절반 → 자본 50% 과소" 라 지적했으나, **FRTB IMA (ES 기반) 의 base 는 MAR33.44 에 따라 1.5 가 정확**. 3.0 은 Basel II VaR 프레임워크 (deprecated) 의 base. 단 yellow-zone plus-factor 매핑은 여전히 오류 (P1 신규 보고).
  2. **PR #5 `risk_lib/capital/rwa_sa.py` bank grade B RW=1.00**: PR #13/#14/#15 이 "1.50 (CRE21.10) 이어야 함" 이라 3주 연속 지적했으나, CRE20.18 에 따르면 **BB+~B- 은행 익스포저는 100% 가 정확**. 단, **corporate B (line 44) 는 여전히 150% 로 올려야 함 (CRE20.44)** — 이 부분만 잔존 P0.
- **누적 9회 리뷰 결산 (수정 진척률 갱신):** PR #10 실제 fixed 6/12 = **50%** ✅ / PR #4 partial 1건 / PR #2 0/많음 / PR #5 v0.23-v0.27 신규 코드 P0/P1 유입 vs 이전 P0/P1 미수정.

## 24h 활동 확인

```
git log --since=2026-06-30
  PR #2   f8867b8 (6/15 이후 무변화)
  PR #3   5a2200e (6/15 이후 무변화)
  PR #4   79460dc 2026-07-03 Round 70 (chart polish)
          ebe536a 2026-07-03 Round 71 (print media A4 + sticky TOC)
  PR #5   c6d03fb 2026-07-03 v0.23 time-series ledger
          a8990c3 2026-07-03 v0.24 intraday risk engine
          02007f4 2026-07-03 v0.25 external integrations
          3073722 2026-07-03 v0.26 systemic risk aggregation
          f338311 2026-07-03 v0.27 CECL vs IFRS 9 bridge
          3bcb224 2026-07-03 fix(repro) asof param
          3bc0bdc 2026-07-03 fix(abbreviations) duplicate keys
          b21a5b7 2026-07-03 perf(tests) shared conftest
          81ddc68 2026-07-03 test AST guard duplicate keys
          2b2b7a8 2026-07-03 refactor page registry
          f34b451 2026-07-03 docs ARCHITECTURE.md
          de32388 2026-07-03 refactor split html_ops_pages
  PR #10  ce1d4f9 2026-07-03 mobile hotbar slide
          0c0df7f 2026-07-03 mobile UI overflow fix
          3d61c90 2026-07-03 kid-friendly controls (auto-jump, peace mode)
          9fe7021 2026-07-03 first-run tutorial + reset confirmation + joystick size
  PR #6/#7/#8/#9/#11/#12  (6/15 이하 무변화)
```

## Top 3 시급 액션

### 1. PR #5 신규 P0 — SRISK 공식 `(1-k)` 인자 누락

**`risk_lib/systemic.py:61`** — v0.26 신규 코드:

```python
srisk = prudential_ratio * debt - (1 - lrmes) * equity
```

**정본 (Acharya-Engle-Richardson 2010; Brownlees-Engle 2017):**
```
SRISK = k·D − (1−k)·(1−LRMES)·E
```

`(1-k)` 인자가 자본 부족액 (Capital Shortfall) 을 계산할 때 위기 시 남는 자산 대비 필요 자본을 맞추는 핵심 계수. 코드가 이를 생략 → `E` 항이 `(1-k)` 없이 그대로 감산되어 각 은행 SRISK 가 **`k·(1-LRMES)·E`** 만큼 과소평가 (k=0.08, LRMES=0.4 가정 시 equity 의 **~4.8%**). 은행 규모 순위 (worst_contributor) 가 근접한 두 은행 사이에서 뒤집힐 수 있음.

**주목:** 함수 docstring (line 47) 은 정본 공식을 명시 — 문서와 코드 불일치. `tests/test_systemic.py` 는 SRISK 양수성·cascade determinism 만 검사, 공식 자체를 assert 하지 않음.

**Fix:** 한 줄 (`- (1 - prudential_ratio) * (1 - lrmes) * equity`) + `test_srisk_matches_ae_formula(k, D, E, LRMES)` 회귀 테스트.

### 2. PR #5 신규 P1 — CoVaR 가 자기 손실을 조건화

**`risk_lib/systemic.py:113,121-122`** — v0.26 신규 코드:

```python
system_loss = losses.sum(axis=1)             # ← column i 포함
mask_distress = losses[:, i] >= quantile(losses[:, i], 0.95)
covar_distress = quantile(system_loss[mask_distress], 0.05)
```

`ΔCoVaR(i)` = 은행 i 가 distress 일 때의 system loss VaR − 은행 i 가 median 일 때의 system loss VaR. 정본에서는 **system_loss 가 i 를 제외한 나머지 은행의 손실 합**. 현재 코드는 `losses.sum(axis=1)` 에 i 열을 포함 → mask 가 i 의 tail 을 선택할 때 `system_loss` 도 i 의 tail 을 그대로 반영 → ΔCoVaR 가 i 자신의 tail VaR 을 반영 → 시스테믹 기여도가 아닌 **개별 tail 리스크 순위**.

**실패 시나리오:** 작은 은행 (scale 0.02%) 이 자체 fat tail 을 가지면 top 5% distress mask 가 그 은행 자체의 tail 순간을 잡고, system_loss 는 그 은행 손실이 좌우 → ΔCoVaR 가 규모 대비 부풀림. 대형 은행 대비 시스테믹 순위 오정렬.

**Fix:** `system_loss = losses.sum(axis=1) - losses[:, i]` (한 줄).

### 3. PR #2 — Top 4 P0 완전 미수정 (9주 연속)

`stock_trading/harness.py:182` `thinking={"type":"adaptive"}` / `tools.py:218` `place_order` 음수 shares 미가드 / `harness.py:198` exception 흡수 → stale APPROVED / `consult_*` sticky approval + trade not bound to consult — **9주 연속 라인 동일, 커밋 0건**.

- PR #10 의 최근 6개 P0/P1 fix 는 저자가 리뷰 채널에 반응할 수 있음을 증명. PR #2 는 그 반응이 오지 않은 유일한 활성 PR.
- 4건 모두 **각 5~10 줄 이내 fix**. 예: `place_order` 음수 shares 는 함수 첫 줄에 `if not isinstance(shares, int) or shares <= 0: return {"status":"REJECTED","reason":"invalid_shares"}` 추가 1건.

## 결과 매트릭스

| PR | 커밋 (7/3) | 이번 신규 P0/P1/P2 | 이전 findings 상태 | 권고 |
|---|---|---|---|---|
| **#5** | **12건 (v0.23–v0.27 + refactor)** | **P0×1 (SRISK) + P1×4 (CoVaR own-loss / FRTB yellow-zone / BA-CVA 형식 / intraday PnL 규약) + P2×6** | Stage3 ECL 미할인 · MVA integrand · BA-CVA κ · corporate B RW=1.00 여전. **오판 정정 2건**: FRTB base 1.5 = 정확, bank grade B RW=1.00 = 정확 (corporate 만 잔존). | **block-merge** |
| **#4** | 2건 (Round 70/71) | P2×1 (gauge negative vmax) + P3×3 (팔레트 대비 자기모순, TOC regex 취약, sticky nav vs DRAFT) | permission_guard secret echo · scenario_weights dict-zip dedup · pack_archive non-atomic · leakage_guard 영문 전용 · governance TZ → **여전 라이브**. record_feedback → **partial fix** (P0→P1). | changes requested |
| **#10** | 4건 (모바일 + 튜토리얼) | P2×2 (auto-jump pogo / joystick 33px 시각 stick) + P3×5 | **6/12 FIXED** ✅ (dispose · Y-ceiling · chest race · fallDist · music burst · R keyup + hotbar). 잔존 5: saveGame 10s sync stall · applyPos NaN · load-time numeric NaN · nether respawn · creeper→chest 콘텐츠 유실. | changes requested (near-merge) |
| **#2** | **0건** | P1×4 (position-cap TOCTOU / cash float drift / specialist output un-quarantined / stale agents import risk) | Top 4 P0 (thinking=adaptive, negative shares, exception swallow, sticky approval) **9주 연속 라이브**. `_UNTRUSTED_NOTE` news wrapping 은 partial (2번째 hop 재래핑 필요). | **block-merge** |
| #3/#6/#9 | 0 | — | 이전 권고 유지 (docs-only / trader entry_price 환각 가드 부재 / handoff schema 부재) | changes requested |
| #7/#8 | 0 | — | 이전 권고 유지 (close 또는 rebase + CHG 재할당) | close 권고 |
| #11/#12 | 0 | — | 이전 권고 유지 (동일 .gitignore 변경 중복) | one merge, one close |

## 상세 리뷰

### PR #5 (risk-management, 12 신규 커밋)

**v0.23 Time-series accumulation ledger:** clean. Idempotent replace-if-exists on period, `end_utc[:10]` UTC-safe, `diff(4)` quarterly 가정 문서화. **P3**: 분기 연속성 체크 부재 — 결측 분기 시 QoQ 잘못 계산.

**v0.24 Intraday risk engine:**
- **P2 — PnL 부호 규약 혼란** (`intraday.py:118-120`): `pnl = -base_delta * equity_idx * 100 - dv01 * rate_10y * 1e4 - cs01 * credit_spread * 1e4`. `simulate_market_ticks` 가 `equity_idx` 를 09:00 부터 누적 수익률 경로로 생성 (line 63) → 각 tick 의 `pnl` 이 tick-to-tick PnL 이 아니라 open-to-now PnL. `peak_var` 지표는 영향 없으나 리포트 상 "이 tick 손익" 표기가 잘못.
- 무한 버퍼 아님 (`ticks: list[Tick]` 이 함수 스코프 종료 시 GC) — 누출 아님.

**v0.25 External integrations:**
- **P2 — 웹훅 SSRF/재시도** (`integrations.py:65-79`): URL 스킴/호스트 허용 목록 없음. 오퍼레이터 config 만 소싱하면 안전하나 CLI 인자·리포트 소싱 확장 시 `169.254.169.254` (AWS IMDS) 또는 `localhost` 컨트롤 플레인 대상 SSRF 표면. `Idempotency-Key` 없음 → 5xx 후 재시도 시 알림 중복.
- REST/GraphQL 스펙 파일: 필드 검증 엄격 여부는 caller 위임 상태.

**v0.26 Systemic risk:**
- **P0 — SRISK 공식 (1-k) 누락** (line 61) — 상세 위 참조.
- **P1 — CoVaR own-loss 편향** (line 113,121-122) — 상세 위 참조.
- **P2 — 제로 나눗셈 미가드** (`cecl.py:82,114-115`): `w_life = (df["ead"] * df["maturity"]).sum() / df["ead"].sum()`, 세그먼트 재분배 `seg["ead"] / ead_total * ifrs9_total`. 전량 zero-EAD 포트폴리오 시 DivisionError.

**v0.27 CECL bridge:**
- **P2 — EIR 하드코딩** (`cecl.py:40,63`): `eir=0.05` 스칼라 default. ASC 326-20-30-4 은 대출별 origination EIR 요구. `eir_col` 존재 시 우선하도록 확장 권고.
- 영문 board pack (`board_pack.py`) 문자열 삽입: 대부분 f-string 이고 taint 소스 없음. **P3**: `localization.py:89` `f'{k.grade}'` 미escape — `grade` 가 사용자 데이터가 될 경우 XSS. 현재는 상수 집합만.

**refactor (de32388 + 2b2b7a8): CLEAN.** AST 스캔 결과 `risk_lib/page_registry.py` 의 66개 `PageSpec` 항목의 `(module, func)` 페어 100% 해석 성공 (0 missing). 이전 `html_ops_pages.py` 의 `def` 집합이 `risk_lib/ops_pages/*.py` union 과 byte-identical. `risk_lib/pillar3.py` 는 deprecated 표시 되었으나 `ops_pages/governance.py:526`, `tests/test_cro_layers.py:261,268` 에서 여전히 import — soft link 유지, silent rename 없음.

**이전 P0 재확인:**
- `risk_lib/provisioning/ecl.py:218` Stage 3 ECL EIR 미할인 → 여전 라이브. Lifetime PV 미적용으로 KR FSS 관행 하 과대 provisioning.
- `risk_lib/xva.py:128-130` MVA integrand: `t=linspace(0.25, m, n_pts)` 시작점 0.25 → 첫 분기 IM 기여 누락. 소규모.
- `risk_lib/ccr.py:88-92` BA-CVA: κ=0.05 스칼라 folding, `(ρ, 1-ρ²)` combining term 부재. 이번 v0.25/v0.27 에서 미터치. Board pack page 7 이 "BA-CVA (κ=5%) 컴플라이언트" 라 주장 — 위원회 리더 오해 유도.
- `risk_lib/capital/bis.py:43-44` AT1 tier identity: **CLEAN**. `bis_deep.py:257` 이 `min(at1, at1_cap)` 로 T2 cap 분모 정확 처리.

**정정 (이전 리뷰 오판):**
- **FRTB `_backtest_zone` multiplier 1.50** (`frtb.py:161-162`): PR #16/#17/#18 이 BCBS MAR99.55 값 3.0 대비 1/2 이라 주장하며 "IMA 자본 50% 과소" 로 P0 지정. **정본:** BCBS MAR33.44 는 FRTB IMA (ES 기반) 의 base multiplier 를 1.5 로 명시. 3.0 은 이전 Basel II VaR 프레임워크의 base (deprecated). **본 base 는 정확. P0 취소.** 단 yellow-zone plus-factor 는 아래처럼 여전히 오류:
  - 현재: `{5:1.70, 6:1.76, 7:1.83, 8:1.88, 9:1.92}`
  - MAR33 정본: base 1.5 + plus `{5:0.40, 6:0.50, 7:0.65, 8:0.75, 9:0.85}` = `{1.90, 2.00, 2.15, 2.25, 2.35}`
  - 예: 7건 예외 → 코드 1.83 vs 정본 2.15 → ES 자본 ~15% 과소. **P1 재발행.**
- **`risk_lib/capital/rwa_sa.py` bank grade B RW=1.00** (line 34): PR #13/#14/#15 이 CRE21.10 위반이라 3주 연속 지적. **정본:** CRE20.18 은 BB+~B- 은행 익스포저를 100% 로 명시. **본 라인은 정확. P0 취소.** 단 **corporate B (line 44) 는 CRE20.44 에 따라 150% 로 상향 필요 (여전 P0)**.

### PR #4 (validation-team-agent, 2 신규 커밋)

**Round 70/71 (chart polish + print media A4 + sticky TOC):**
- **P2 — `svg_charts.py` gauge 음/영 vmax** (line ~156): `vmax = vmax if vmax is not None else max(value, minimum, warning or minimum) * 1.25 or 1.0`. `warning=0.0` (유효 임계) 를 falsy → `minimum` 폴백. `all-negative` 입력 시 `max()` 음수 × 1.25 여전 음수 truthy → `scale = negative / (width-90)` → 차트가 캔버스 밖 또는 반전 지오메트리. 예: `gauge(value=-0.5, minimum=-1.0, warning=-0.2)`.
- **P3 — 팔레트 대비 자기모순**: R70 커밋 메시지 "`#94a3b8` contrast 2.5:1 FAIL → `skipped` 를 `#64748b` 로 교체" 명시. 그러나 동일 커밋이 `INK_SUBTLE = "#94a3b8"` (line ~28) 를 도입 후 y-tick 라벨 (`trend_line` line ~471) 과 `min X.XXX` 주석 (line ~487) 에 사용. 10pt 텍스트 on white 에서 2.7:1 → WCAG AA (일반 3:1 / 본문 4.5:1) 미달.
- **P3 — TOC regex 취약** (`report_pack.py:402`): `_H2_RE = re.compile(r"<h2>([^<]+)</h2>")` — 속성 없는 순수 h2 만 매칭. 향후 `<h2 class="foo">` 또는 `<h2>text <code>x</code></h2>` 도입 시 silent 누락. crash 아닌 silent degradation. TOC 완전성 회귀 테스트 부재 (존재 유무만).
- **P3 — Sticky TOC + DRAFT banner ordering** (`report_pack.py:_page` ~445): `nav.toc` 은 sticky (`top:0`) 이나 `DRAFT_BANNER` 는 sticky 아님 → 스크롤 시 DRAFT 사라짐. "모든 화면에 DRAFT" 인바리언트 실질 위반 (HTML 뷰). print 에서는 무관.
- **XSS/HTML-injection 표면 신규 없음.** `_slugify` 가 `[\w가-힣-]` 로 ID sanitize, h2 콘텐츠 전부 하드코딩 리터럴, `m.group(1)` 왕복 무변화. `_inject_toc` 는 현재 trust surface 하 안전.
- **신규 import 무위험.** R70 = `math` 로컬만, R71 = `re` 재사용 (기존 import). 서드파티 dep 신규 없음. R42 hex 인바리언트 (하드코딩 hex 금지) 는 `PALETTE` 참조로 갱신 유지.

**이전 findings 재확인 (라이브 상태):**

| Finding | 위치 | 상태 |
|---|---|---|
| `check_weight_panel` dict-zip silent dedup | `tools/scenario_weights.py:82` | **LIVE** (`.astype()` 만 추가, dedup drop 유지) |
| `record_feedback` 원문 저장 | `tools/classify_error.py:~202` | **PARTIAL FIX → P1** (middleware 위임, 그러나 `try/except: return []` silent bypass + `allow_sensitive=True` + Korean freeform PII 통과) |
| `permission_guard.check_commands` secret echo | `middleware/permission_guard.py:107` | **LIVE (P0)** (`all_findings.append({"command": cmd, **f.to_dict()})` 그대로. 모듈 docstring 인바리언트 정면 위반.) |
| `data_safety_guard.scan_dataframe` `df.index` 노출 | (loop 내 `"row": int(idx) ... else idx`) | **LIVE (P1)** — 비수치 인덱스 (account ID) 원문 통과. |
| `pack_archive._save_index` 비원자 | `tools/pack_archive.py:124-127` | **LIVE (P1)** (`write_text` in-place. mid-crash → JSONDecodeError). |
| `pack_archive.add()` label sanitize 부재 | `tools/pack_archive.py:_add` | **LIVE (P1) — 신규 확인** `target = archive_root / label`, `../../etc/foo` label 시 copytree 가 resolve 이전에 실행. |
| `_prune` symlink | `tools/pack_archive.py:~172` | **FIXED** (`p.resolve()` + parents check). |
| `manifest.save` / `audit_retention._write` / `feedback_retention._write_records` 비원자 | 각 파일 | **LIVE (P1)** — 세 곳 모두 `write_text` / `open("w")` in-place. `tempfile + os.replace` 패턴 부재. |
| `_LEAK_PATTERNS` 영문 전용 | `middleware/leakage_guard.py` | **LIVE (P1)** — `부도여부`, `연체일수`, `연체월수`, `사고일` 등 한국어 컬럼 통과. |
| `governance_timeseries.quarter_of` TZ | naive dt | **LIVE (P2)** — Q 경계에서 ±TZ 오프셋 드리프트. |

### PR #10 (minecraft, 4 신규 커밋 — **가장 반가운 진척**)

**신규 4 커밋 (모바일 + 튜토리얼):**
- **P2 — Auto-jump pogo** (`index.html:1719`): `if (optAutoJump && hitWall && player.onGround && !flying && !swimming) { player.vel.y = 7.5; }`. `optAutoJump` default ON. 2블록 이상 벽에 전진 유지 시 landing 마다 재점프 (7.5 초기속도 → 최대 ~1.4블록 < 2) → 무한 pogo, hunger 소모. 벽 위 1블록 empty 여부 가드 부재.
- **P2 — Joystick 시각 stick 33px 하드코딩** (`index.html:1966`): `translate(${dx*33}px, ${dy*33}px)`. `optJoy` (90-160) 변경 시 링은 커지나 인디케이터는 33px 캡 유지 → 160px 링에서 반경 41% 만 도달. "kid-sized joystick" 기능 (9fe7021) 저하.
- **P3 — Reset 이 튜토리얼·설정 키 유지** (`index.html:1932-1942`): `resetBtnEl` 이 `SAVE_KEY` 만 제거. `mc_tut`, `mc_sens`, `mc_vol`, `mc_view`, `mc_music`, `mc_freeze`, `mc_autojump`, `mc_peace`, `mc_joy`, `mc_slot` 잔존. 라벨 `이 월드 초기화` 는 world-only 의도로 해석 가능하나 "새로 시작" 의도라면 partial reset.
- **P3 — Peace mode 이 진행 중인 크리퍼 폭발 미취소**: `updateZombies` cleanup 이 non-boss 좀비 제거하나 동일 프레임에서 `fuse >= 1.4` 인 크리퍼는 여전히 `explodeCreeper()` 실행 → `destroyBlocks()` 로 자식 건축물 파괴. 프레임 1개 폭 race, P1 아님.
- **P3 — hotbarTouch X-only clamp** (`index.html:2382-2401`): touchstart 가 `#hotbar` 시작 후 finger 가 세로로 크게 벗어나도 touchmove 계속 발생 → X 만 clamp → look-swipe 가 hotbar edge 스치면 slot 스왑. 실사용 harmless (Q/R 이 실제 사용) 이나 UX 노이즈.
- **P3 — tutEl touchstart 리스너 `passive:false` 미지정** (`index.html:2090`): 라인 2089 의 click 핸들러가 이미 dismissal 커버 → touchstart 리스너 잉여, `preventDefault` 만 방어 default 마스킹.
- **INFO — Joystick localStorage tamper NaN**: 슬라이더 90-160 바운드 이나 수동으로 `mc_joy=999999` 심으면 style width/height 999999px. self-inflicted, 무시.

**이전 P0/P1 상태 재확인 — 6건 FIXED ✅:**

| 이전 finding | 상태 | 근거 |
|---|---|---|
| `InstancedMesh.dispose()` per-edit GPU 유출 | **FIXED** | `rebuildChunk` / `removeAllChunkMeshes` 에 `m.dispose()` (line 821, 2575) |
| Y-ceiling stick | **FIXED** | line 1725-1738 이 ceiling & floor 양쪽 `vel.y=0` |
| Chest pointer-lock race | **FIXED** | `openChest` 이 `chestOpen=true` 설정, `playing()` gate mining (line 1918, 2549) |
| F-flight `fallDist` exploit | **FIXED** | `KeyF` 핸들러 `fallDist=0` (line 1635) |
| Music burst | **FIXED** | `startMusic`/`stopMusic` interval clear, `musicRunning` gate (line 950-963) |
| R keyup guard | **FIXED (effectively)** | `bowUp()` `if(charging)` gate, `loop()` `cancelCharge()` on `!playing()` (line 2789-2792). Blur-mid-charge 는 다음 frame drain. |
| Hotbar 9-slot + Q + R | **FIXED** | HOTBAR len 9, `if(n>=1 && n<=HOTBAR.length)` gate, Q=eatBest, R=bow (line 432, 1633-1644) |

**여전 라이브:**

| Finding | 상태 |
|---|---|
| `saveGame` 10s sync stall | **LIVE** — 동기 `JSON.stringify` + `localStorage.setItem` `setInterval(2776)`. offload 없음. |
| Paused-renderer always-on | **LIVE (by design)** — `renderer.render` 매 프레임, sim 만 `active` flag gate (2795, 2813). |
| Save quota / NaN pass-through | **PARTIAL** — 루트/shape 검증 (2662-2705) 추가, 그러나 `typeof save.health === 'number'` 이 NaN 통과. `Math.min(MAX_HEALTH, Math.max(1, NaN)) → NaN`. hunger, dayTime 동일. |
| `applyPos` NaN → collision fail | **LIVE** — line 2630-2637 `p.x/p.y/p.z` 대입 `Number.isFinite` 체크 부재. `pos:{x:NaN,y:NaN,z:NaN}` 시 playerCollides false 반환, teleport 통과 후 safeSpawn 폴백. |
| Nether respawn | **LIVE** — `respawn()` line 1585 `player.pos.set(0.5, spawnY(), 0.5)` 오버월드 terrain 사용. 네더 dim 스왑 없음, 네더랙/용암 내부 스폰 가능. |
| Chest explosion 콘텐츠 유실 | **LIVE** — `destroyBlocks()` (884-898) `BLOCK.CROP` 브랜치만, `BLOCK.CHEST` 브랜치 부재. `chests.get(key)` 고아 Map 엔트리, 콘텐츠 silent 유실. |

### PR #2 (stock-trading, 커밋 0)

**Top 4 P0 (9주 연속 라이브):**

| # | 위치 | 상태 |
|---|---|---|
| P0-1 | `stock_trading/harness.py:182` `thinking={"type":"adaptive"}` | LIVE. Anthropic Messages API `thinking` 은 `{"type":"enabled","budget_tokens":N}` 또는 `{"type":"disabled"}` 만. `"adaptive"` = `BadRequestError`. **모든 `harness.run()` 실패.** |
| P0-2 | `stock_trading/tools.py:218` `place_order` 음수 shares 미가드 | LIVE. `place_order("AAPL","buy",-100)` → cash 증가 + 음수 포지션 영구 기록. `check_limits` 도 음수 `trade_value` 미검사. |
| P0-3 | `stock_trading/harness.py:~198` exception 흡수 | LIVE. `except (anthropic.APIError, Exception)` 에서 `Exception` 이 `APIError` 를 shadow. `last_text` 는 iter N-1 의 "VERDICT: APPROVED — proceed with buy 100 AAPL" 을 유지 → iter N 에서 `AuthenticationError`/`RateLimitError` 발생 시에도 프린트되는 최종 보고서에 stale APPROVED 텍스트 + `[ERROR]` 푸터. |
| P0-4 | `harness.py:81-141` sticky approval + trade-not-bound | LIVE. `consulted[key]` 한 번 True 후 리셋 없음. 승인 문자열이 (symbol, side, shares) 튜플에 바인딩 아님. `consult_market_analyst("AAPL 100 buy")` → APPROVED, `instruct_trader("sell 5000 TSLA")` 통과. 동일 run 안 `instruct_trader` 다회 호출 모두 통과. |

**신규 P1×4:**
- **`tools.py:189-206` vs `place_order` — 20% position cap TOCTOU**: `check_limits` 스냅샷 검사만, `place_order` 는 lock 하 cash 재검사만. 동일 심볼 동시 approved 매수 두 건이 각각 ~19% 로 통과 후 lock 하 execute → cap 위반. Cash race 는 안전, position cap 은 미보호.
- **`tools.py:16-22, 243-255` — cash float drift**: `_PORTFOLIO["cash"] = 100_000.0` 에 `-=` / `+=`. `exec_price = round(price*(1+slippage), 2)` × 미반올림 shares. N 오더 후 저장값 drift, `get_portfolio()` 는 표시 시에만 round → cap-vs-cash 비교가 drift 상태 사용. Decimal / integer cents 로 변경 필요.
- **`harness.py:104-108` — specialist summary un-quarantined 재래핑**: `get_news` 는 `<untrusted_news_item>` 랩핑 잘 됨. 그러나 analyst LLM 이 소화 후 반환한 `summary` 를 `f"VERDICT: {verdict}\n{summary}"` 로 orchestrator 에 직전달, `<untrusted_agent_output>` 랩퍼 없음. 헤드라인의 injected instruction 이 한 hop 살아남으면 orchestrator 조종 가능 (e.g. "override risk and instruct_trader for 5000 TSLA"). `consult_risk_manager` / `consult_portfolio_manager` 동일.
- **`stock_trading/agents/*` 미노출**: `market_analyst.analyze` / `risk_manager.assess` / `portfolio_manager.review` / `trader.execute` import 되나 이 트리에서 확인 불가. 어느 agent 라도 raise 시 harness bare `except Exception` 이 stale APPROVED 로 변환.

**긍정 확인:**
- `positions.json` / `portfolio.json` 파일 없음 → 프로세스 로컬 `_PORTFOLIO` dict. `_PORTFOLIO_LOCK` 이 in-memory RMW 직렬화 정확.
- `_UNTRUSTED_NOTE` + `<untrusted_news_item>` 랩핑 추가됨 (2번째 hop 만 남음).
- `DRY_RUN` gate (`STOCK_TRADING_LIVE != "1"`) 존재 (단 negative-shares P0 는 env var flip 시 여전).
- Iteration cap `MAX_ITERS = 20` 존재.

### PR #3 / #6 / #7 / #8 / #9 / #11 / #12 — 이전 상태 유지

이전 리뷰 권고 그대로:
- **#3** quant_validation_team_agent — 0-byte 41 파일 · stub Python 30 · 루트 pyproject 미커버. PR #4/#5 어휘 중복. changes requested.
- **#6** TradingAgents 한국어 템플릿 — `bias_resolution` schema 부재, entry_price 환각 가드 prose-only. merge with note.
- **#7** validation-team-agent CI paths 수정 — base 에 이미 적용 + CHG-0078 중복. **close**.
- **#8** #7 확장 — 동일 + CHG-0080/81 추가 충돌. close 또는 rebase + CHG-0135+ 재할당.
- **#9** 리스크 리서치 하네스 — `handoff.schema.json` 부재, demo sample G2 floor 위반. changes requested.
- **#11/#12** 동일 `.gitignore` 1줄 변경. one merge, one close.

## 누적 9회 리뷰 결산 (수정률 갱신)

| | #13 (6/19) | #14 (6/21) | #15 (6/22) | #16 (6/23) | #17 (6/26) | #18 (6/28) | #19 (6/29) | #20 (6/30) | **이번 (7/4)** |
|---|---|---|---|---|---|---|---|---|---|
| 신규 P0 | 4 | 0 | 4 | 7 | 10 | 3 | 4 | 0 | **1** |
| 신규 P1 | 8 | 0 | 6 | 18 | 24 | 9 | 13 | 0 | **8** |
| 누적 수정 | — | 0/9 | 0/15 | 0/22 | 0/32 | 0/44 | 0/57 | 0/57 | **7/57** |
| 오판 정정 | — | — | 2 | — | — | — | — | — | **2 (누적 4)** |

**누적 수정 7건 breakdown (모두 PR #10):**
- InstancedMesh dispose leak (PR #13)
- Y-ceiling stick (PR #13/#14)
- Chest pointer-lock race (PR #15)
- F-flight fallDist exploit (PR #17)
- Music burst (PR #16)
- R keyup guard (PR #18)
- Hotbar 9-slot reachability (PR #18)

**작성자 워크플로 신호:**
- PR #10: **채널 도달 확인** — 프로즈 리뷰의 세부 지적 (특히 F-flight, chest race, dispose) 이 실제 코드 fix 로 반영. 7건 fix 는 이번 리뷰 세션이 아니라 이전 세션 (6/29~7/2) 의 누적으로 보이나 fix 커밋 시각(7/3)이 마지막 리뷰 (6/30) 직후 → author 가 리뷰를 실제로 소비 중.
- PR #4: 커밋 2건 (chart polish), record_feedback 만 partial fix. permission_guard / scenario_weights / non-atomic writes 는 미터치.
- PR #5: 12건 커밋으로 대규모 신규 기능, 이전 P0 (Stage3 ECL / MVA / BA-CVA / corporate B RW) 미터치. **회귀 우려**: 신규 SRISK P0 도입.
- PR #2: 9주 연속 무변화.

## 다음 라운드 권고

**A. Prose 리뷰 유지 (PR #10 채널 도달 증명)** — 다음 사이클에서:
1. PR #10 잔존 P1×5 (saveGame sync stall, applyPos NaN, load-time NaN, nether respawn, chest content leak) 를 별도 요약 이슈로 정리 → author 가 fix 리스트로 소비하기 용이하게.
2. PR #5 신규 P0 (SRISK) + P1 (CoVaR own-loss, FRTB yellow-zone, BA-CVA κ) 를 한 fix-PR 스켈레톤 + 회귀 테스트 스텁으로 제안.
3. PR #4 permission_guard secret echo · scenario_weights dedup 은 **각 1~3 줄 fix + 회귀 테스트** 제안 — 이 두 건은 domain-critical.
4. PR #2 는 여전히 무반응 → **routine 이 fix-PR 을 직접 제출**하는 옵션 (PR #20 A안) 재검토. Top 4 P0 모두 mechanical fix, domain check 불필요.

**B. 이전 잘못된 P0 지적 정리** — `CODE_REVIEW_2026-07-04_CORRECTIONS.md` 별도 파일로:
1. FRTB `_backtest_zone` multiplier 1.5 취소 (PR #16~#18).
2. `risk_lib/capital/rwa_sa.py` bank grade B RW=1.00 취소 (PR #13~#15).
   - Corporate B (line 44) 는 여전히 P0 로 별도 이슈 발행.

## 리뷰 방식

4개 병렬 general-purpose 에이전트 (PR #2, PR #4, PR #5, PR #10). 각 에이전트가 `mcp__github__pull_request_read get_files` + `mcp__github__get_file_contents ref=refs/pull/{N}/head` 로 HEAD SHA 파일 직접 읽기. 8회 prior 결함 인벤토리 input, NEW + partial fix status 요청. 총 출력 토큰 ~410K.

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
