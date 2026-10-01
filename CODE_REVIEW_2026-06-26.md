# 전체 저장소 코드 리뷰 — 2026-06-26 (5라운드 fresh-eyes)

## 1. 요약

PR #16(2026-06-23) 이후 10개 PR 모두 **새 커밋 0건**. 누적 5회 리뷰에서 P0/P1 수정 진척률 ≈ 0. 이번 라운드는 이전 4회가 놓친 더 깊은 영역(IFRS 9 PV, BA-CVA 공식, AT1 tier identity, MVA integrand alignment, parser silent-downgrade, 모바일 익스플로잇)에 집중 → **신규 P0 10건 / P1 24건 / Med-P2 20건+**.

집중 영역:
- PR #5: 회계·자본 정합 (IFRS 9 5.5.17, BCBS CRE50 BA-CVA, MAR, AT1 tier identity)
- PR #4: middleware security invariant (permission_guard secret echo) + 정책-구현 단절 (cva_thresholds)
- PR #2: 파서·플로트·envelope 잔여 표면
- PR #10: 게임 익스플로잇 (F-비행 fallDist) + 모바일 메인스레드 stall
- PR #9: 자체 demo 산출물이 자체 G2 floor 위반
- 교차 PR: IRRBB 시나리오 명명 불일치, 'validation' 패키지 어휘 중복

## 2. 가장 시급한 단일 액션 — Top 3

### 2.1 PR #5 — IFRS 9 Stage 3 ECL EIR 미할인 (`risk_lib/provisioning/ecl.py:226`)

```python
ecl_def = np.maximum(lgd, 0.0) * np.maximum(ead, 0.0)  # no EIR discount, no time factor
```

IFRS 9 5.5.17 은 lifetime ECL 의 PV(EIR 할인)를 명시. Stage 3 ECL 이 LGD×EAD 그대로 → 5년 horizon × 5% EIR 가정 시 **약 22% 과대계상**. 사후 회계 인정 거부 + Pillar 3 ECL 보고 inconsistency. 한 줄 fix (할인 인자 곱).

### 2.2 PR #4 — permission_guard 가 secret 을 finding 에 echo (`validation-team-agent/middleware/permission_guard.py:107`)

```python
for f in detect_permission_violations(cmd, patterns=pats):
    all_findings.append({'command': cmd, **f.to_dict()})  # cmd 원문 그대로
```

모듈 docstring 약속 "**Secret 비유출 원칙: 매칭된 원문... 절대 finding 또는 audit log 에 포함하지 않는다**" 와 직접 모순. `export AWS_SECRET=AKIA1234...` 입력 시 AKIA 토큰이 그대로 finding → audit log → PR 코멘트로 누출. middleware 의 핵심 invariant 위반.

### 2.3 PR #2 — Market Analyst `_parse_verdict` silent NEEDS_REVIEW (`stock_trading/agents/market_analyst.py:103-115, 72-92`)

```python
texts = []
for msg in _client.beta.messages.tool_runner(...):
    for block in msg.content:
        if block.type == "text" and block.text:
            texts.append(block.text)
return _parse_verdict("\n".join(texts))   # json.loads on concatenated narration → fails
```

분석가가 JSON 앞에 어떤 narration 이라도 emit 하면 join 결과가 invalid JSON → `_parse_verdict` 가 `verdict=NEEDS_REVIEW` 로 강등. 트레이드 게이트가 **모델의 verbosity 에 따라 동전 뒤집기**가 됨. Risk/Portfolio Manager 는 `VERDICT:` 라인 prefix 만 보므로 영향 없음 — 즉 analyst gate 만 silent fail.

---

## 3. 결과 매트릭스

| PR | 변경 | 누적 P0/P1 | 신규 발견 | 권고 |
|---|---|---|---|---|
| **#5** | 없음 | 0/22 | **P0×4 (IFRS9 Stage3 PV, AT1 tier identity, MVA integrand, BA-CVA 공식) + P1×9 + P2×7** | **block-merge** |
| **#4** | 없음 | 동일 | **P0×2 (permission_guard 시크릿 echo, CVA 정책-구현 단절) + P1×6 + P2×5** | **block-merge** |
| **#2** | 없음 | 부분 | P1×4 (cash float drift, untrusted_news_item escape, analyst parse, TOCTOU check_limits/place_order) + P2×4 | changes requested |
| **#10** | 없음 | 부분 | **P0×3 (F-비행 fallDist 익스플로잇, saveGame 10s sync stall, paused-renderer always-on) + P1×5 + P2×4** | changes requested |
| **#3** | 없음 | 0/3 | High×3 (root pyproject 가 quant_validation tests 미커버, prompt-only 무가드, UAT PR #4 와 책임 중복) + Med×3 | block-merge |
| **#6** | 없음 | 부분 | High×2 (bias_resolution 스키마 부재, entry_price prose-only) + Med×2 | changes requested |
| **#9** | 없음 | 부분 | High×2 (handoff.schema.json 부재, 자체 sample 이 자체 G2 floor 위반) + Med×3 | changes requested |
| **#7** | 없음 | stale | — | **close** |
| **#8** | 없음 | stale | helper 일부 reuse 가치 | **close 또는 helper-only PR 로 rebase + CHG-0082+ 재할당** |
| **#11/#12** | 없음 | 동일 | — | one merge, one close |

### 3.1 교차 PR P0

- **IRRBB 시나리오 명명 불일치** (PR #4 `harness/irrbb_thresholds.json:7-13` 의 `short_rate_up/_down` vs PR #5 `risk_lib/alm/irrbb.py:27` 의 `short_up/_down`) — 두 PR 머지 후 validation harness 가 risk_lib 출력의 `short_up` 을 unknown scenario 로 silent skip → outlier 은행이 검토 무사통과.

---

## 4. PR별 신규 P0 상세

### 4.1 PR #5 (risk_lib)

**P0-1 `risk_lib/provisioning/ecl.py:226` — Stage 3 ECL EIR 미할인** (위 §2.1)

**P0-2 `risk_lib/capital_simulation.py:188` — AT1 trigger 전환 tier identity 위반**

```python
cet1 += conversion
tier1 = cet1 + (tier1 - cet1 - conversion)  # conversion 이중차감
```

- `cet1 += conversion` 후 `(tier1 - cet1)` 는 이미 `old_AT1 - conversion`. 또 빼면 `old_AT1 - 2*conversion`.
- 결과: 새 Tier1 = Y - conversion (정상 변환은 Y 유지: AT1 → CET1 이동, 합계 보존).
- `total` 은 갱신 안 됨 → `total - tier1` (= T2) 가 silently `conversion` 만큼 증가.
- Pillar 3 KM1/OV1 행 합계 불일치.

Fix: 일반 AT1→CET1 전환은 `tier1` 불변. 영구상각(write-down) 변형은 `tier1 -= conversion; total -= conversion`.

**P0-3 `risk_lib/xva.py:159` — MVA integrand 가 period-END IM 사용 (period-START 사용해야 정확)**

```python
im_t = im_initial * (1 - t / t.max())
# t=t.max → im=0; t=t[0]=0.25 → im=im_initial*(1-0.25/m) (이미 감소)
```

3y 거래 기준 1분기 MVA ≈ 8% 과소, 누적 ≈ 50% 과소 (삼각형 vs 사다리꼴). MVA 가 신규 산정될수록 손실 누락 비율 커짐.

Fix: 평균 IM 사용 `im_avg = im_initial * (1 - (t + t_prev)/2 / t.max())`.

**P0-4 `risk_lib/ccr.py:80` — BA-CVA 공식 누락 (κ·√(ΣEAD²) 만)**

```python
def cva_capital_charge(ead: pd.DataFrame, *, kappa: float = 0.05) -> float:
    return float(kappa * np.sqrt((ead['ead'] ** 2).sum()))
```

BCBS CRE50.10:

```
K_BA = β · √( ρ² · (Σ S_i·M_i·EAD_i_eff)² + (1-ρ²) · Σ (S_i·M_i·EAD_i_eff)² )
β=1.4, ρ=0.5 (`harness/cva_thresholds.json` 에 이미 선언), S = 등급별 supervisory weight (0.5%~3%), M = effective maturity
```

코드는 ρ/S/M 모두 무시. IG 포트폴리오 M_eff=2y 가정 시 실제 BA-CVA 는 현 출력의 **3~6배**. Pillar 3 CV1 디스클로저 mismatch.

### 4.2 PR #4 (validation-team-agent)

**P0-1 `middleware/permission_guard.py:107` — secret echo** (위 §2.2)

**P0-2 `harness/cva_thresholds.json:5-6` vs `risk_lib/ccr.py:84` — 정책 SSoT 가 구현에서 미사용**

```json
// harness/cva_thresholds.json
{ "rho_correlation": 0.5, "alpha_ba_cva": 1.4 }
```

`risk_lib/ccr.py` 는 ρ/α 둘 다 load 안 함. 정책 문서가 decorative. 머지 후 감독당국 검토 시 정책-구현 분리 지적 100%.

Fix: ccr.py 가 모듈 로드 시 json 을 읽어 `cva_capital_charge(rho=..., alpha=...)` 로 파라미터화 + `tests/test_cva_uses_policy_constants.py` 추가.

### 4.3 PR #10 (Minecraft)

**P0-1 `minecraft/index.html:1447` — F(비행) 토글이 fallDist=0 + vel.y=0 → 낙하 데미지 익스플로잇**

```js
if (e.code === 'KeyF' && playing()) {
  flying = !flying;
  player.vel.y = 0;
  fallDist = 0;   // 비행 종료 시에도 0
}
```

공중 어떤 높이에서든 착지 직전 F 두 번 → 낙하 데미지 0. 용암 다이브도 안전. 게임 핵심 위험 요소 완전 무력화.

Fix: 비행 ON 시에만 fallDist=0, OFF 전환 시에는 fallDist 보존.

**P0-2 `minecraft/index.html:2473-2475, 522-536` — 10초마다 동기 `saveGame()` → 메인스레드 stall**

`setInterval(saveGame, 10000)` 가 변경 유무 무관 매 10초 전체 dim 직렬화 + 동기 localStorage IO. 수천 edits 누적 시 iOS Safari 100~500ms 프레임 드랍, 매 10초 입력 지연.

Fix: dirty 플래그 + `requestIdleCallback`. 변경 없을 때 skip.

**P0-3 `minecraft/index.html:2479-2512` — paused 상태에서도 `renderer.render` + `updateMinimap` 풀스피드, `visibilitychange` 일시정지 부재**

오버레이/제작/인벤이 열려 있어도 GPU 렌더 + 미니맵 fillRect 16K ops/s. `document.hidden` 시 rAF 중단 / setInterval 일시정지 부재 → 모바일 백그라운드에서도 배터리 누수.

Fix: `visibilitychange` → `cancelAnimationFrame`; overlay 표시 시 렌더 throttle.

---

## 5. PR별 신규 P1 요약 (단축)

### PR #5 (P1×9)
- `risk_lib/ccr.py:48` — SA-CCR maturity factor 가 margined 거래 분기 부재 (CRE52.51 MF=1.5·√(MPOR/1y) 무적용)
- `risk_lib/ccr.py:62` — bank 상대방 RW flat 50% 하드코딩, 등급 무시 (AAA 2.5× 과대, B 2× 과소)
- `risk_lib/capital_simulation.py:147` — adverse 시나리오 earnings 가 `base_rwa` (정적) 기반 → CET1 trough 과소
- `risk_lib/frtb.py:140` — `rfet_test` 가 'date' 열을 risk factor 로 처리 (loop 변수에 포함)
- `risk_lib/xva.py:108` — CVA discrete integration 이 첫 bucket 에 누적 PD 전부 할당 (mid-point integration 권장)
- `risk_lib/capital/rwa_sa.py:101` — `mortgage_rw_vector` 가 edge LTV 에서 scalar 와 silent 잠재 mismatch (현재 일치하나 테스트 lock 없음)
- `risk_lib/capital/output_floor.py:32` — floor=0 거부 (이력 시뮬레이션 차단)
- `risk_lib/validation/consistency.py:78` — `_check_pd_bounds` PD floor 위반 시 WARN, 통과 시 PASS 누락 → 보고서 incomplete
- `risk_lib/alm/irrbb.py:104` — per-scenario `pct_tier1` 부호 signed, summary `worst_pct_tier1` 는 magnitude (혼용)

### PR #4 (P1×6)
- `middleware/data_safety_guard.py:99` — `scan_dataframe` 가 row × col × pattern O(n·m·p) → 100k 스모크 테스트 ~4분
- `middleware/data_safety_guard.py:65` — card-number regex (Luhn 부재) 가 16자리 PK/거래ID 전부 false positive
- `middleware/leakage_guard.py:36` — `_after`/`_post` pattern 이 `re.search` vs `fullmatch` 혼용
- `middleware/output_completeness_guard.py:159` — `_NUMERIC_RE` 가 bullet `- ` 와 range `~` 를 음수 부호로 오인
- `tools/metric_psi.py:25` — `_EPS=1e-4` floor 가 sample size 의존성 무시
- `tools/binomial_calibration.py:54` — `exposure_count==0` 등급에서 `ValueError` (soft-skip 권고)

### PR #2 (P1×4)
- `tools.py:240-260` — `place_order` 가 unrounded `total_cost` 로 cash 차감, 주문 기록은 rounded → 누적 P&L drift
- `tools.py:120-135` — `<untrusted_news_item>` envelope 가 escape 부재, 닫는 태그 literal 페이로드 시 break
- `agents/market_analyst.py:103-115` — 위 §2.3 silent NEEDS_REVIEW
- `tools.py:200-272` — `check_limits` (read, lock-released) vs `place_order` (re-acquire, no re-check) TOCTOU

### PR #10 (P1×5)
- 1773-1799 — paused 메뉴 열린 상태에서 canvas touchmove → player yaw/pitch 회전
- 803-818 — `spawnParticles` 캡 off-by-one (120 → 130 가능)
- 1453-1457 — blur 핸들러가 joyVec/joyId/charging 미클리어
- 1431-1440 — `damage()` playSound 노드 누수 (osc.stop 만 호출, gain.disconnect 없음)
- 1773-1799, 1751-1769 — joy/canvas 가 동일 finger identifier 잡을 가능성 (iOS Safari 보고 기반)

### PR #3 High×3 / PR #6 High×2 / PR #9 High×2

PR #3:
- 루트 `pyproject.toml` 의 `testpaths=['tests']` 가 `quant_validation_team_agent/tests/` 를 안 잡음
- "LLM 직접 수치 계산 금지" 가 prompt-only, 런타임 가드 부재
- UAT_EVALUATION / GO_NO_GO / AUDIT_TRAIL 3개 체크리스트가 PR #4 와 동일 책임 중복

PR #6:
- `bias_resolution` 필드가 JSON 스키마에 부재 — Round 4 프로토콜이 schema 와 단절
- `entry_price` 환각 가드 prose only, JSON enum/oneOf 없음

PR #9:
- `harness/handoff.schema.json` 가 task 가 약속한 위치에 부재
- `reports/basel-iii-endgame-implementation-status-2026-06-10.html:67-70` 의 C-002 행이 T4-T5 only 인데도 finding 표에 발행 → 자체 G2 floor 직접 위반 (rapid-scan demo 자체가 결함)

---

## 6. 4주차 후속 — 누적 5회 리뷰 결산

| | PR #13 (06-19) | PR #14 (06-21) | PR #15 (06-22) | PR #16 (06-23) | 이번 (06-26) |
|---|---|---|---|---|---|
| 신규 P0 | 4 | 0 | 4 | 7 | **10** |
| 신규 P1 | 8 | 0 | 6 | 18 | **24** |
| 누적 수정 | — | 0/9 | 0/15 | 0/22 | **0/32** |

**작성자 워크플로 신호:** PR #15(06-22) 이후 **96시간** 무활동. 누적 32 개 결함 중 0건 수정. 6→6→0→0→0 commit 패턴. 알림 미도달 또는 별도 우선순위.

**권고:** 코드 측 강제 (test-value assertion + pre-commit hook + CI block) 가 prose 리뷰보다 효과적. 특히:

1. PR #5 의 IFRS9/AT1/MVA/CVA 4개 P0 는 모두 BCBS 정확 인용으로 표 값 테스트 가능 → `tests/test_basel_table_values.py` 추가
2. PR #4 의 permission_guard secret echo 는 `tests/test_no_secret_in_findings.py` 로 직접 잠금
3. PR #10 의 fallDist 익스플로잇은 `tests/exploit_test.html` (puppeteer 자동화) 로 잠금
4. 교차 PR IRRBB scenario 명명은 `tests/test_irrbb_scenarios_align.py` (양쪽 SSoT cross-import) 로 잠금

## 7. 리뷰 방식

4개 병렬 general-purpose 에이전트 (Sonnet/Opus mixed):

- (1) PR #2 trading harness — prompt injection 잔여 표면, float drift, parser
- (2) PR #4/#5 — BCBS/IFRS9/MAR 수치 정합 + middleware security invariant
- (3) PR #10 — animation frame / 모바일 / 익스플로잇
- (4) PR #3/#6/#9 + PR #7/#8 — 문서/하니스 정합 + PR #7/#8 정리

각 에이전트: `mcp__github__pull_request_read get_files` + `mcp__github__get_file_contents` 로 head SHA 의 파일 직접 읽기. 이전 4 라운드의 결함 인벤토리를 prior 로 제공, "fresh-eyes for NEW issues" 요청. 총 ~427K 출력 토큰.

전체 보고서: 본 파일 (`CODE_REVIEW_2026-06-26.md`)

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
