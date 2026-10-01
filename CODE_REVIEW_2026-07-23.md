# 전체 저장소 코드 리뷰 — 2026-07-23 (25주차)

## 요약

지난 라운드 (PR #40, 2026-07-22 21:12 UTC) 이후 ~24h. **감시 13개 PR 전건 head SHA 무변경**, **신규 PR 0건** (최신 PR 번호 #40 = 지난 리뷰 PR). 코드 활동 0. **zero-delta 라운드** — 19주차 (PR #34, 2026-07-16) 이후 6주 만의 완전 정지 라운드.

## 이번 라운드 카운트

| 항목 | 카운트 |
|---|---|
| 신규 P0 | **0** |
| 신규 P1 | **0** |
| 신규 P2 | **0** |
| 신규 P3 | **0** |
| Tracked 재확인 | 감시 13개 PR 전건 무커밋 → 이전 findings 전건 자동 LIVE 유지. PR #10 warden 벽투과 **5주 연속**, PR #5 P0×3 **11주 연속**, PR #4 ERRATA **8주 연속** 미발행, PR #38 (24주차 신규 P2×1 + P3×1 포함) P2×4 + P3×4 **미수정** |
| PR #40 지시 이행 | **0/13** — 감시 13개 PR 전건 무커밋으로 물리적 이행 불가 |

## 이번 라운드 델타 커밋

| PR | 이전 head (PR #40 기준) | 현재 head | 커밋 | 요지 |
|---|---|---|---|---|
| #2 | `f8867b8f` | `f8867b8f` | 0 | 무변경 (15+주 방치) |
| #3 | `5a2200e3` | `5a2200e3` | 0 | 무변경 (14+주 방치) |
| #4 | `fdb68cb8` | `fdb68cb8` | 0 | 무변경 (Round 78 이후 무커밋) |
| #5 | `8de106da` | `8de106da` | 0 | 무변경 (10주 방치) |
| #6 | `98cb1a46` | `98cb1a46` | 0 | 무변경 (14+주 방치) |
| #7 | `a60443b4` (dirty) | `a60443b4` (dirty) | 0 | 무변경 (13+주 방치) |
| #8 | `574f8a1c` (dirty) | `574f8a1c` (dirty) | 0 | 무변경 (13+주 방치) |
| #9 | `133985a2` | `133985a2` | 0 | 무변경 (14+주 방치) |
| #10 | `6601e55a` | `6601e55a` | 0 | 무변경 (마지막 커밋 2026-07-20 11:00, ~73h 무커밋) |
| #22 | `907839e2` | `907839e2` | 0 | 무변경 (12+주 방치) |
| #30 | `38376da7` | `38376da7` | 0 | 무변경 (8+주 방치) |
| #32 | `e63e5d26` | `e63e5d26` | 0 | 무변경 (7+주 방치) |
| **#38** | **`3ffdf95`** | **`3ffdf95`** | **0** | 무변경 (마지막 커밋 2026-07-22 12:39, ~32h 무커밋) — **24주차 이래 첫 후속 커밋 없음** |

**최근 커밋 시각**: 저장소 전체 최신 = PR #38 `3ffdf95` (2026-07-22 12:39 UTC, ~32h 전). 그 다음 = PR #10 (~73h 전). 그 외 감시 PR ≥ 7d 무커밋. `git log --all --since='2026-07-22T21:00:00Z' --oneline` 결과 = PR #40 리뷰 커밋 1건뿐 (`64075e9` 리뷰 문서).

## PR #40 지시사항 이행 현황 — 0/13 이행 · 감시 PR 전건 무커밋

| PR #40 권고 (25주차 대상) | 이행 여부 |
|---|---|
| 1. PR #38 `removeEnemy` dispose 추가 (신규 P2-1, 크리처 · particle · tracer · wisp 4경로) | **미이행** — PR #38 head 무변경, `hope-shooter/index.html:1060-1069` 여전히 dispose 부재 |
| 2. PR #38 벽투과 사격 fix (P2-1 tracked, 3주 연속) | **미이행** — L1328 `intersectObjects(enemyMeshes, false)` 유지 |
| 3. PR #38 GPU dispose particles/tracers/wisps (P2-2 tracked, 3주 연속) | **미이행** — L1573/1585/1589 여전히 `scene.remove` 만 |
| 4. PR #38 window blur 핸들러 (P2-3 tracked, 3주 연속) | **미이행** — `blur` 리스너 부재 (`resize` 만 L1596) |
| 5. PR #38 Reflector textureWidth 반응형 (신규 P3-1 from 24주차) | **미이행** — L497 `textureWidth: 1024` 고정 유지 |
| 6. PR #10 warden 벽투과 fix (**5주 연속**) | **미이행** — `minecraft/index.html:2014-2026` `for (let i=1; i<=8; i++)` 무조건 damage(5) 유지 |
| 7. PR #10 `damage()` 주석 갱신 | **미이행** |
| 8. PR #5 corporate B RW=1.00→1.50 (**11주 연속**) | **미이행** — `risk_lib/capital/rwa_sa.py:49` `"B": 1.00` 유지 |
| 9. PR #5 SRISK · CoVaR fix (**11주 연속**) | **미이행** — `risk_lib/systemic.py:52` 여전히 `srisk = prudential_ratio * debt - (1 - lrmes) * equity` (`(1-k)` 계수 누락) |
| 10. PR #4 CHG-0143 재할당 + ERRATA-2026-07-14 발행 (**8주 연속**) | **미이행** — `validation-team-agent/docs/` 하위에 `errata*` 파일 부재 |
| 11. PR #22 close (**9주 연속**) | **미이행** |
| 12. PR #2 close (**16주 방치**) | **미이행** |
| 13. PR #7 close, #8 base rebase | **미이행** |

**이행률 0/13**. 지난 라운드 (PR #38 `3ffdf95` 시각 리파인 커밋 1건) 대비 이번 라운드는 감시 PR 전건 무커밋 → PR 소유자 세션이 저장소 전체에 걸쳐 정지. 이는 4주차 (PR #34, 2026-07-16, 12/12 무커밋) 이후 두 번째 완전-정지 라운드.

## 이번 라운드 신규 P0 · 0건

## 이번 라운드 신규 P1 · 0건

## 이번 라운드 신규 P2 · 0건

## 이번 라운드 신규 P3 · 0건

_감시 PR 전건 무커밋 · 신규 코드 노출 없음 → 신규 finding 발생 불가. 새 finding 후보는 오직 신규 커밋에서만 발견되므로 zero-delta 라운드에서 신규 finding 0건은 정상._

## Tracked LIVE 재확인 (스팟체크 실측 완료)

이번 라운드는 감시 13개 PR 전건 head SHA 무변경 → 이전 findings 전건 자동 LIVE. 무결성 확보 차 5개 고위험 finding 을 원본 파일 실측으로 재검증.

### PR #5 corporate B RW = 1.00 — **11주 연속 LIVE (P0)**

`git show origin/claude/risk-management-agent-harness-B9Kxm:risk_lib/capital/rwa_sa.py` L40-50 실측:

```python
"AAA-AA": 0.20,
"A": 0.50,
"BBB": 0.75,
"BB": 1.00,
"B": 1.00,        # ← Basel III CRE20 = 1.50, 여전히 1.00
"CCC-": 1.50,
"UNRATED": 1.00,
```

Basel III CRE20 신용등급 B corporate exposure risk weight 는 1.50 (150%). 현 코드는 BB (1.00) 와 동일 취급 → corporate credit RWA 를 이론치 대비 저평가, CET1 buffer 여유 잘못 계산. **1줄 fix 11주 방치**.

### PR #5 SRISK `(1-k)` 누락 — **11주 연속 LIVE (P0)**

`systemic.py:52` 실측:

```python
srisk = prudential_ratio * debt - (1 - lrmes) * equity
```

NYU V-Lab 표준 정의: `SRISK_i = k · Debt_i − (1 − k) · (1 − LRMES_i) · Equity_i`. 현 구현은 `(1 − k)` 계수 누락 → equity 항이 규제 승수 없이 상계 → SRISK 를 과소 추정. system_shortfall 및 bank contribution ranking 왜곡. **11주 연속**.

### PR #5 CoVaR own-loss mask — **11주 연속 LIVE (P1)**

`systemic.py:103` 무변경. 뱅크 i 의 distress 시 시스템 VaR 산정에서 i 자신의 loss 를 마스킹하지 않아 ΔCoVaR self-contamination.

### PR #10 warden 벽투과 sonic — **5주 연속 LIVE (P2)**

`minecraft/index.html:2014-2026` 실측:

```javascript
} else if (z.warden) {
  // 워든: 느리게 다가오며 벽을 뚫는 음파 사격
  speed = z.chaseSpeed;
  z.sonicT -= dt;
  if (z.sonicT <= 0 && d < 18) {
    z.sonicT = 3.5;
    for (let i = 1; i <= 8; i++) { // 푸른 음파 궤적 (블록 무시)
      const t = i / 8;
      spawnFx(z.pos.x + dx * t, z.pos.y + 2 + (player.pos.y + 1 - z.pos.y - 2) * t, z.pos.z + dz * t, WARDEN_SOUL, 1, 1.2, 0.35);
    }
    damage(5);
    playSound(48, 0.5, 'square', 0.4);
  }
```

- 주석 (`벽을 뚫는`, `블록 무시`) 이 결함을 자백. 거리 <18 조건만으로 무조건 damage(5) 적용 → LOS/`raycast(world.children)` 부재.
- **5주 연속 지시 미이행**. PR #10 head `6601e55a` (2026-07-20 11:00 UTC 이래 ~73h 무커밋).

### PR #38 신규 P2-1 (24주차) removeEnemy dispose 부재 — LIVE

`hope-shooter/index.html:1060-1069` 실측:

```javascript
function removeEnemy(e) {
  scene.remove(e);
  enemies.splice(enemies.indexOf(e), 1);
  e.traverse((m) => {
    if (m.isMesh) {
      const i = enemyMeshes.indexOf(m);
      if (i >= 0) enemyMeshes.splice(i, 1);
    }
  });
}
```

`geometry.dispose()` · `material.dispose()` 미호출. `3ffdf95` 이후 크리처당 ~41 mesh + cloned material 유지. wave 20 20-30분 세션 = 8,200~16,400 leaked geometry.

### PR #38 raycast `world.children` 부재 (P2-1 tracked, 3주 연속) — LIVE

L1328 실측: `const hits = raycaster.intersectObjects(enemyMeshes, false);`. 벽 콜리전 미포함 → 총알이 벽을 관통해 뒤편 적 명중.

### PR #38 GPU dispose (P2-2 tracked, 3주 연속) — LIVE

L1573 (wisps), L1585 (particles), L1589 (tracers) 실측: 3개소 모두 `scene.remove(...)` 뿐, `.geometry.dispose()` / `.material.dispose()` 미호출.

### PR #38 resize `setPixelRatio` + Reflector RT 갱신 부재 (P3-2 tracked + P3-1 신규 확장) — LIVE

L1596-1600 실측:
```javascript
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  composer.setSize(window.innerWidth, window.innerHeight);
});
```

`renderer.setPixelRatio` 미호출, `roadReflector.getRenderTarget().setSize` 미호출, UnrealBloom Vector2 갱신 미호출. 초기값 hardcode + resize 무갱신 패턴 3개소 유지.

### PR #4 ERRATA-2026-07-14 미발행 — **8주 연속 LIVE (P1)**

`git ls-tree -r --name-only origin/claude/validation-team-agent-Pw9F5 | grep -i errata` → **결과 0건**. `validation-team-agent/docs/` 하위: `executive_summary.md · human_in_the_loop.md · operating_model.md · project_overview.md · risk_control_framework.md · v2_refactor_plan.md · validation_scope.md` — errata 문서 부재. R39-R74 오라벨링 shipped 유지.

### PR #4 CHG-0143 재할당 미이행 — **8주 연속 LIVE (P0/P1×2)**

`report_pack.py` (4417 lines) 무변경. Round 78 (2026-07-17) 이후 무커밋. cet1 SSoT · Basel Total-cap surcharge · salt 재식별 3건 모두 LIVE.

### PR #2 sticky APPROVED — **16주 방치 LIVE (P0×2)**

`stock_trading/harness.py:200-210` 실측: 스크린 output 은 `last_text = block.text` 로 축적, iteration_cap / tool_runner_failed 시에도 `last_text` 는 이전 상태 그대로 사용. `_build_tools` 내부에서 `consulted[key] = True` 를 verdict = "APPROVED" 시 설정하지만 리셋 로직 없음 → 한 번 approved 된 specialist 는 세션 종료까지 sticky. **close 절차 6주 연속 권고**.

### PR #22 skills-lock.json · code-review slug 충돌 — **9주 연속 LIVE (P0×3)**

`git ls-tree -r --name-only origin/claude/skills-plugin-install-nk7ez7 | grep -E 'skills-lock|code-review'`:
```
.claude/skills/code-review/SKILL.md
skills-lock.json
```
파일 존재 확인, sourceCommit 필드 부재 문제 무변경. **close 즉시 시행 권고 9주 연속**.

### 그 외 tracked LIVE (커밋 무변경 → 자동 유지)

- **PR #3 `quant_validation_team_agent/` — 15주 방치**: 6/15 대응 후 무커밋. P1/P2 LIVE.
- **PR #6 codex trading agent — 15주 방치**: P1×1 LIVE. close 권고.
- **PR #7 (dirty) — 14+주 방치**: P1×1 + P2×1 LIVE. close 권고.
- **PR #8 (dirty) — 14+주 방치**: P1×1 + P2×1 LIVE. base rebase 필요.
- **PR #9 `risk-research-harness` — 15주 방치**: P1×1 LIVE + PARTIAL 유지.
- **PR #30 `docs/ISO-42001-AGENT-REQUIREMENTS.md` — 9주 방치**: 소급 조항 부재, CI check 부재.
- **PR #32 `mecha-chameleon/index.html` — 8주 무변화**: `startBtn.blur()` 미도입, tongue CCD 미도입.

## 결과 매트릭스

| PR | 이번 커밋 | 이번 신규 | 이전 findings 상태 | 권고 |
|---|---|---|---|---|
| **#38** | **0** (32h 무커밋) | 0 | 이전 P2×4 + P3×4 **전건 LIVE** (24주차 신규 P2×1 + P3×1 포함, 무수정) | 벽투과 사격 · GPU dispose (크리처 포함 4경로) · blur 핸들러 · Reflector RT 5건 처리 후 mergeable |
| **#32** | 0 | — | P2×2 + P3×3 LIVE (**8주**) | mergeable — small polish |
| **#30** | 0 | — | P1×1 LIVE (**9주 방치**) | **block-merge** (소급 조항 필요) |
| **#10** | 0 | — | tracked LIVE 12 (warden **5주 연속 미수정**) | **block-merge** (warden 관통 해결 후 mergeable) |
| **#5** | 0 | — | P0×3 + P1×1 + P2×2 LIVE (**11주 연속 P0 미수정**) | **block-merge / escalate** |
| **#4** | 0 | — | P0×1 + P1×2 LIVE + FIXED×1 · PARTIAL×3 (**8주 연속 errata 미발행**) | **changes requested + CHG-0143 재할당 강제** |
| **#3** | 0 | — | P1/P2 LIVE (**15주 방치**) | owner 미회신 → close |
| **#2** | 0 | — | P0×2 LIVE + P0×2 PARTIAL (**16주 방치**) | **close 절차 진입** (6주 연속) |
| **#9** | 0 | — | P1×1 LIVE + PARTIAL 유지 | block-merge |
| **#22** | 0 | — | P0×3 LIVE (**13주 방치**) | **close 즉시 시행** (9주 연속) |
| **#6** | 0 | — | P1×1 LIVE (15주 방치) | close |
| **#7** | 0 (dirty) | — | P1×1 + P2×1 LIVE | close (#8 이 승계) |
| **#8** | 0 (dirty) | — | P1×1 + P2×1 LIVE | base rebase 후 재검토 |

## 누적 25회 결산

|  | #35 | #36 | #37 | #38(리뷰) | #39(리뷰) | #40(리뷰) | **이번** |
|---|---|---|---|---|---|---|---|
| 신규 P0 | 0 | 0 | 0 | — | 0 | 0 | **0** |
| 신규 P1 | 1 | 1 | 0 | — | 0 | 0 | **0** |
| 신규 P2 | 1 | 0 | 0 | — | 3 | 1 | **0** |
| 신규 P3 | 0 | 0 | 1 | — | 3 | 1 | **0** |
| Tracked 재분류 | 5 | 3 | 0 | — | 0 | 0 | **0** |
| 누적 수정 | 8/90 | 8/89 | 8/89 | — | 8/96 | 8/98 | **8/98** (신규 0건 → 총 findings 카운트 유지) |

_주: #38(리뷰) 열은 코드 PR 이 아닌 게임 PR — 리뷰 대상. #40(리뷰) 열이 지난 라운드 리뷰._

**Zero-delta 라운드 통계**: 25주 중 완전-정지 (감시 PR 전건 무커밋) 라운드 = **2회** (19주차 PR #34, 25주차 이번). 부분-정지 (12/13 무커밋) 라운드는 24주차 PR #40 포함 다수.

## 주요 시사점

1. **완전 zero-delta 라운드**. 저장소 최신 커밋은 지난 라운드 PR #38 `3ffdf95` (2026-07-22 12:39, ~32h 전), 그 이후 감시 PR 커밋 0건 · 신규 PR 0건. 지난 라운드 (PR #40) 지시 13건 중 물리적으로 이행 가능한 개수는 0 (모든 PR 이 무커밋). **워크플로 결함 극단 사례** — 리뷰 지시가 PR 소유자 세션에 도달하지 않는 것을 넘어, 저장소 전체 개발 활동이 24-48h 동안 정지.

2. **PR #38 24주차 신규 P2-1 (removeEnemy dispose) 이 즉시 fix 되지 않고 방치되기 시작**. 이 finding 은 이전 P2-2 (particles/tracers/wisps dispose) 를 sub-mesh 40배 증가로 실효 P2 승격한 사례 — 방치 시 wave 진행에 비례해 메모리 리크 규모 확대. 신규 P3-1 (Reflector textureWidth) 도 동시 미수정. **finding 발견 후 1주 이내 fix window 를 이미 상실**.

3. **PR #5 P0×3 11주 · PR #4 ERRATA 8주 · PR #22 close 9주 · PR #2 close 16주 · PR #30 소급조항 9주** — 실행 프로세스 부재의 누적 심화. 25주차 시점 total tracked LIVE findings ≈ 30 건, 그 중 **8건이 8주 이상 방치**. 저장소 차원에서 close/merge 결정 채널 부재가 근본 문제.

4. **감시 12개 PR 이 아닌 13개 PR 전건 무커밋**은 이번 라운드가 처음. 이전 완전-정지 라운드 (19주차 PR #34) 는 감시 PR 12개 기준. 감시 PR 수 증가 (12 → 13) 에도 불구하고 커밋 0건 = 활동 밀도 감소 신호.

5. **리뷰 세션 자체 (`stoic-ride-*` 시리즈) 는 25주 연속 정상 발행** — 리뷰 채널은 살아있으나 fix 채널이 죽어있는 비대칭. 리뷰 라운드마다 신규 findings 를 추가할수록 tracked LIVE 스택만 커짐. **다음 라운드에서 리뷰 채널의 목적 재정의 필요** (예: 신규 finding 발견 감속 / close 결정 위주 라운드 전환).

## 다음 라운드 (26주차) 권고

1. **PR #10 warden 벽투과 fix 강제 (6주째)** — `minecraft/index.html:2014-2026` `for (let i=1; i<=8; i++)` 루프에서 `raycast(world.children)` LOS 체크 후 damage 조건화. 지난 5주 연속 요청.
2. **PR #10 `damage()` 주석 갱신** (1줄, 위더 스톰 80% 반영). 6주 연속.
3. **PR #38 `removeEnemy` dispose 추가 (신규 P2-1, 2주 연속)** — 크리처 · particle · tracer · wisp 4경로 통합 처리, 7줄.
4. **PR #38 벽투과 사격 fix (P2-1 tracked, 4주 연속)** — `intersectObjects` 에 `world.children` 추가.
5. **PR #38 GPU dispose particles/tracers/wisps (P2-2 tracked, 4주 연속)** — 3개소 각 2줄.
6. **PR #38 window blur 핸들러 (P2-3 tracked, 4주 연속)** — 2줄.
7. **PR #38 Reflector textureWidth 반응형 (P3-1 tracked, 2주 연속)** — 2줄.
8. **PR #5 corporate B RW = 1.00 → 1.50 fix (11주 연속)** — `risk_lib/capital/rwa_sa.py:49` 1줄.
9. **PR #5 SRISK `(1-k)` 계수 추가 · CoVaR own-loss mask (11주 연속)** — `systemic.py:52` / `:103`.
10. **PR #4 CHG-0143 재할당 + ERRATA-2026-07-14 발행 (8주 연속)**.
11. **PR #22 close 시행 (9주 연속)** — merge 의도 없음 명시, 브랜치 삭제.
12. **PR #2 close 시행 (16주 방치)** — 승계 PR 없음 확인 시 close.
13. **PR #7 close, #8 base rebase**.
14. **[프로세스 권고]** 25주차 zero-delta + 8건 8주+ 방치 = 리뷰 채널만 활성인 비대칭 지속. 다음 라운드에서 **close-only 라운드** 로 전환하여 tracked LIVE 스택 정리 (신규 finding 발견 vs 기존 finding close 밸런스 조정).

## 리뷰 방식

**메인 스레드 단일 세션, 감시 13개 PR head SHA 대조 + 5건 고위험 finding 실측 재검증**:

- `mcp__github__list_pull_requests state=open perPage=50` → 페이지 1 max=#40 (2026-07-22 리뷰 PR). 신규 PR 0건.
- 감시 13개 PR head SHA 대조 → **전건 무변경**. `git fetch origin` 후 `git log --all --since='2026-07-22T21:00:00Z'` = PR #40 리뷰 커밋 `64075e9` 1건 (코드 PR 커밋 0건).
- 5건 고위험 finding 실측 재검증:
  1. PR #5 `rwa_sa.py:40-50` — `"B": 1.00` 확인 (P0 11주 LIVE)
  2. PR #5 `systemic.py:52` — `srisk = prudential_ratio * debt - (1 - lrmes) * equity` 확인 (`(1-k)` 누락, P0 11주 LIVE)
  3. PR #10 `minecraft/index.html:2014-2026` — `for (let i=1; i<=8; i++)` + 무조건 `damage(5)` 확인, 주석 자백 (`벽을 뚫는`, `블록 무시`) (P2 5주 LIVE)
  4. PR #38 `hope-shooter/index.html:1060-1069` — `removeEnemy` dispose 부재 확인 (P2 신규 2주차)
  5. PR #38 `hope-shooter/index.html:1596-1600` — resize 콜백에서 setPixelRatio / Reflector RT / UnrealBloom Vector2 갱신 부재 확인 (P3 tracked)
- PR #4 ERRATA 파일 존재 여부 스캔: `git ls-tree -r --name-only origin/claude/validation-team-agent-Pw9F5 | grep -i errata` = **0건**, `validation-team-agent/docs/` 하위 7개 문서 리스트 확인 (errata 없음). 8주 연속 미발행 확정.
- PR #22 skills-lock.json + code-review/SKILL.md 존재 확인 (P0×3 finding 대상 파일 유지).
- PR #2 `stock_trading/harness.py:200-210` sticky pattern 실측 (last_text 축적 + consulted[key] 리셋 로직 부재 확인).

**단독 리뷰어 (에이전트 배정 없음), zero 위험도 라운드**. 감시 PR 전건 무커밋으로 신규 코드 노출 없음 → 신규 P0/P1/P2/P3 발견 불가. 기존 tracked findings 는 대응 커밋 부재로 자동 LIVE 유지. 실측 스팟체크로 finding 상태 정확성 재확인.

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
