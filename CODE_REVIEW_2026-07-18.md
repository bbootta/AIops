# 전체 저장소 코드 리뷰 — 2026-07-18 (21주차)

## 요약

지난 라운드 (PR #35, 2026-07-17 21:13 UTC) 이후 ~21h. **감시 12개 PR 중 1개 (PR #10) head SHA 이동**, 나머지 11개 무변경. PR #10 은 2커밋 push (2026-07-18 10:36 UTC, 14:16 UTC). 신규 PR 0건.

- **신규 P0** — 0건.
- **신규 P1** — 1건 (PR #10 워든 벽투과 음파, 셸터 서바이벌 계약 파괴).
- **신규 P2** — 0건.
- **신규 P3** — 0건.
- **Tracked 재분류** — **3건**: PR #10 `applyPos`/`blinkTeleport` **PR #35 판단 오류 정정 → LIVE 복귀** (2건), PR #5 FRTB 멀티플라이어 wired 확인 → **NOT A DEFECT 재분류** (1건).

## 이번 라운드 델타 커밋

| PR | 이전 head (PR #35) | 현재 head | 커밋 | 요지 |
|---|---|---|---|---|
| **#10** | `846a2567` | **`ceaf4922`** | 2 | (1) `ab1af827` 워든+광역 필살기+제3차원 보이드+몹별 통계+유성 (+310 lines index.html) · (2) `ceaf4922` 꽃 1400/네더 기둥 240/앰비언트 파티클 + 스폰 옆 상설 포탈 자동 생성 + 포탈 쿨다운 단축 (+86 lines) |
| 그 외 11개 | 무변경 | — | 0 | PR #2/#3/#4/#5/#6/#7(dirty)/#8(dirty)/#9/#22/#30/#32 head 무커밋 |

**최근 커밋 시각**: PR #10 `2026-07-18 10:36:02Z` · `2026-07-18 14:16:33Z` — 다른 감시 PR 은 ≥21h 무커밋. PR #5 마지막 코드 커밋은 `2026-07-17 01:55` (~44h), PR #4 는 `2026-07-17 01:52` (~44h).

## 이번 라운드 신규 P1 · 1건

### PR #10 (`ab1af827`) — 워든 벽투과 음파, 셸터 서바이벌 계약 파괴

`minecraft/index.html:1668-1678`:

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
}
```

**증상**: 워든이 반경 18블록 이내 발견 시 3.5s 마다 5데미지를 **블록·지형·셸터 관통** 하여 무조건 명중. 코드 주석 자체가 "블록 무시" 를 명시 (L1673). 워든 스폰 로직 (L1523/1529/1531): 오버월드 밤 4%, 보이드 20%. 초기 HP 10 (`health = 10`) → **7 hit (24.5s)** 로 사망.

**서바이벌 게임 계약 파괴 시나리오**:
1. 플레이어가 밤에 잠자리를 만들기 위해 완전 밀폐된 돌집 시공.
2. 워든이 30블록 이내 스폰 (밤 4% 확률).
3. **접근하지 않아도 18블록 내 진입 시 벽을 무시하고 24.5초 안에 사망**.
4. 사망 시 인벤토리 유지 (`respawn()` 는 위치·hp 만 리셋), 하지만 아이언·다이아 갑옷 착용 시 15%/40% 감쇠에도 5×0.85=4.25 / 5×0.6=3 = 27~40s 로 사망.

**설계 의도로 처리된 관통이지만**:
- 마인크래프트 원작 워든은 근접+"Sonic Boom" 원거리 공격 모두 하되, 소닉 붐은 라인-오브-사이트 요구 (블록 관통 안 함).
- **완전 밀폐 셸터가 무의미** → 서바이벌 게임에서 밤=위험, 셸터=안전 계약을 근본 파괴.
- 코드 스폰율 20% (보이드) 은 특히 심각: 보이드 방문 = 4-8분 내 사망 확정.

**fix (택일)**:
- (a) 라인-오브-사이트 체크 추가: `if (hasLineOfSight(z.pos, player.pos)) damage(5);` — DDA raycast 를 재사용 가능.
- (b) 최대 관통 거리 제한: 워든과 플레이어 사이 solid 블록 카운트 > 3 이면 데미지 미적용.
- (c) 관통 데미지 감쇠: 벽 개수당 50% 감쇠.

**관련**:
- `changeMob(z, 'warden')` — 워든 HP 60, meleeDmg 4, chaseSpeed 1.6 도 유지 (근접 위협).
- 스폰율 4%/20% 은 발견/체감 빈도로 튜닝 후 재검토 필요.

## 이번 라운드 신규 P2 · 0건

PR #10 신규 코드 (Warden/AoE/Void/portal beautification) 스팟체크에서 P1 이상 이슈 1건 (위) 외 P2/P3 은 확인 안 됨. **`suitUlt()` 쿨다운 6-8초 · 데미지 정상 · 동물 제외 로직 정상**. **`safeSpawn()` fallback (return 20)** 은 방어적 상수, `applyPos()` 실패 시 트리거로 실질 위험도 낮음.

## 이번 라운드 신규 P3 · 0건

## Tracked 재분류 · 3건

### 1-2. PR #10 `applyPos`·`blinkTeleport` — PR #35 판단 오류 정정 → **LIVE 복귀**

PR #35 (20주차) 결론:
> `applyPos` L3390 NaN 방지 → **완전 제거 (0 matches)** → 잠정 FIXED 로 재분류.
> `blinkTeleport` 벽 관통 → **완전 제거 (0 matches)** → 잠정 FIXED 로 재분류.

**실측 (2026-07-18 head `ceaf4922`)**:

```
$ grep -n -E "function applyPos|function blinkTeleport" minecraft/index.html
2996:function blinkTeleport() {
3732:function applyPos(p) {
```

**PR #35 의 grep 결과 "0 matches" 는 판단 오류**. PR #35 은 파일 총 라인 수도 "1687" 로 기록했으나 실제 846a2567 시점 파일은 이미 ~3800 라인 규모 (이번 라운드 2커밋 net +328 라인 반영해도 3966 라인 = 이전에도 ~3638 라인). PR #35 세션의 grep/wc 결과가 왜곡됐거나 다른 파일을 조회한 것으로 추정. 두 함수 모두 **본체 로직 유지, tracked 성격 그대로**:

**`applyPos` (L3732)**:
```javascript
function applyPos(p) {
  if (!p) return false;
  player.pos.set(p.x, p.y, p.z);
  player.yaw = p.yaw || 0;
  player.pitch = p.pitch || 0;
  player.vel.set(0, 0, 0);
  return true;
}
```
NaN 방지 부재 유지. `p = { x: NaN, ... }` 저장 데이터 (구 버전 세이브 손상) 로드 시 `player.pos` NaN 오염 → 물리·렌더 붕괴 (tracked 원인 그대로).

**`blinkTeleport` (L2996)**:
```javascript
function blinkTeleport() {
  camera.getWorldDirection(_dir);
  const p = player.pos;
  ...
  for (let d = 1; d <= 12; d += 0.5) {
    const nx = p.x + _dir.x * d;
    ...
    if (playerCollides(test)) break;
    tx = nx; ty = ny; tz = nz;
  }
  p.set(tx, ty, tz);
  ...
}
```
0.5 스텝 → 대각선 이동 시 `playerCollides` 미검사 구간 (블록 대각 격자 통과) 잔존. 다만 최종 tx/ty/tz 는 마지막 non-colliding 위치, 실질 위험도는 낮음.

**조치**:
- PR #35 의 잠정 FIXED 판정 정정 → 두 건 모두 **LIVE 복귀**.
- 지난 20주차 결산 표에서 "잠정 FIXED 2건" 은 무효, 누적 수정 카운트는 8/90 → **8/90 (수정 없음)** 유지.

### 3. PR #5 FRTB `frtb.py:170-174` — wired 확인, **NOT A DEFECT 재분류**

PR #35 지시 (권고 #4):
> PR #5 FRTB `frtb.py:170-174` wired 여부 재검토.

**실측**:

```python
# frtb.py:160-174
def _backtest_zone(n_exc: int) -> tuple[str, float, bool]:
    """BCBS MAR99 traffic light at 250 days."""
    if n_exc <= 4:
        return "green", 1.50, False
    elif n_exc <= 9:
        mult = {5: 1.70, 6: 1.76, 7: 1.83, 8: 1.88, 9: 1.92}[n_exc]
        return "yellow", mult, False
    else:
        return "red", 2.00, True

# frtb.py:225 (compute_ima_capital)
cap = es_97_5 * backtest.multiplier + rfet.nmrf_capital_addon
```

**결론**:
- multiplier 값 (1.50 green / 1.70-1.92 yellow / 2.00 red) 은 BCBS MAR99 FRTB 스펙 표준값과 정확히 일치 (FRTB IMA 는 base m_c = 1.5 + 추가 factor 0-0.5, Basel II 의 3.0 base 와 다름).
- **wired 됨**: `backtest.multiplier` 가 `_backtest_zone(n_exc)` 로부터 획득 → `compute_ima_capital` 이 `es_97_5 * backtest.multiplier` 로 IMA 자본 charge 에 적용.
- PLA red / backtest red 시 `pla_status="forced_SA"` + SA fallback +30% surcharge 도 정상 처리.

**조치**: 이전 tracked 리스트에서 "FRTB multiplier 미적용" 은 **NOT A DEFECT** 로 재분류. 4주 연속 P0×4 재환기 문구를 **P0×3** (rwa_sa corporate B + SRISK (1-k) + CoVaR mask) 로 정정.

## 재검증 결과 (스팟체크 3파일)

### PR #5 corporate B RW — LIVE 확인

**`risk_lib/capital/rwa_sa.py:44-52`**:
```python
_RW_CORPORATE = {
    "AAA-AA": 0.20,
    "A": 0.50,
    "BBB": 0.75,
    "BB": 1.00,
    "B": 1.00,      # Basel III CRE20 → 1.50
    "CCC-": 1.50,
    "UNRATED": 1.00,
}
```

7주 연속 LIVE. 이번 라운드 커밋 없음.

### PR #5 SRISK `(1-k)` — LIVE 확인

**`risk_lib/systemic.py:52`**:
```python
srisk = prudential_ratio * debt - (1 - lrmes) * equity
```

Brownlees & Engle (2017) 정의: `SRISK = k(D + (1-LRMES)E) - (1-LRMES)E = k·assets - (1-k+k·LRMES)·equity`. 현재 코드는 `k·debt` (assets - equity) 만 사용 → prudential ratio 를 자산 대신 부채에 적용, capital shortfall 계상 오차. 7주 연속 LIVE.

### PR #5 CoVaR own-loss mask — LIVE 확인

**`risk_lib/systemic.py:101-103`**:
```python
# condition on bank i near its VaR (top 5% of its own loss)
thresh = np.quantile(losses[:, i], 0.95)
mask = losses[:, i] >= thresh
```

Adrian & Brunnermeier (2016): `CoVaR^j|C(X^i)` where `C(X^i) = {X^i = VaR^i}` (점조건, quantile regression). 현재 코드는 `X^i ≥ VaR^i` 구간조건 (top-5% 영역) → tail-dependence 왜곡. 7주 연속 LIVE.

## 그 외 tracked LIVE (커밋 무변경 → 자동 유지)

- **PR #2 `stock_trading/harness.py` — 12주 방치**: sticky last_text L210 · run-level sticky APPROVED L82-141 · P0×2 + PARTIAL×2. **close 절차 진입 권고 2주 연속**.
- **PR #4 `validation-team-agent/tools/report_pack.py` — Round 78 (fdb68cb8) 이후 무커밋**:
  - `~L3762` `cet1_min_pillar1 = 0.045` (SSoT 미위임)
  - `~L3788` `total < cet1_required + 0.03` (Basel Total-cap surcharge 는 0.035)
  - `~L4354` `salt = hashlib.sha256(...)` (재식별 위험 자체 시인)
  - `docs/ERRATA-2026-07-14-icaap-post-stress-mislabel.md` 4주 연속 미발행 (R39-R74 오라벨링 shipped 유지)
  - CHG-0143 A11y 재사용 상태 유지 (PR #35 지시 CHG-0144 재할당 미이행)
- **PR #9 `risk-research-harness` — 무변화**: P1×1 LIVE + PARTIAL 유지.
- **PR #22 `.claude/skills/` — 9주 방치**: `skills-lock.json` sourceCommit 부재 · `code-review/` slug 충돌 · `implement/SKILL.md` /code-review chain + auto-commit. **5주 연속 close 권고**.
- **PR #30 `CLAUDE.md §0` + `docs/ISO-42001-AGENT-REQUIREMENTS.md` — 5주 방치**: 소급 조항 부재, CI check 부재.
- **PR #3/6/7(dirty)/8(dirty) — 11+주 무변화**.
- **PR #32 `mecha-chameleon/index.html` — 4주 무변화**: `startBtn.blur()` 미도입, tongue CCD 미도입.

## 결과 매트릭스

| PR | 이번 커밋 | 이번 신규 | 이전 findings 상태 | 권고 |
|---|---|---|---|---|
| **#32** | 0 | — | P2×2 + P3×3 LIVE (4주) | mergeable — small polish |
| **#30** | 0 | — | P1×1 LIVE (**5주 방치**) | **block-merge** (소급 조항 필요) |
| **#10** | 2 (Warden/AoE/Void + 미화) | **P1×1** | tracked LIVE 12 (재분류 후 12/12 그대로) | **block-merge** (Warden 관통 해결 후 mergeable) |
| **#5** | 0 | — (재분류 1건) | P0×3 + P1×1 + P2×2 LIVE (**7주 연속 P0 미수정**) | **block-merge / escalate** |
| **#4** | 0 | — | P0×1 + P1×2 LIVE + FIXED×1 · PARTIAL×3 (**4주 연속 errata 미발행**) | **changes requested + CHG-0143 재할당 강제** |
| **#3** | 0 | — | P1/P2 LIVE (**11주 방치**) | owner 미회신 시 close |
| **#2** | 0 | — | P0×2 LIVE + P0×2 PARTIAL (**12주 방치**) | **close 절차 진입** (2주 연속) |
| **#9** | 0 | — | P1×1 LIVE + PARTIAL 유지 | block-merge |
| **#22** | 0 | — | P0×3 LIVE (**9주 방치**) | **close 즉시 시행** (5주 연속) |
| **#6** | 0 | — | P1×1 LIVE (12주 방치) | close |
| **#7** | 0 (dirty) | — | P1×1 + P2×1 LIVE | close (#8 이 승계) |
| **#8** | 0 (dirty) | — | P1×1 + P2×1 LIVE | base rebase 후 재검토 |

## 누적 21회 결산

|  | #29 | #31 | #33 | #34 | #35 | **이번** |
|---|---|---|---|---|---|---|
| 신규 P0 | 0 | 0 | 0 | 0 | 0 | **0** |
| 신규 P1 | 2 | 2 | 1 | 0 | 1 | **1** |
| 신규 P2 | 3 | 6 | 3 | 0 | 1 | **0** |
| 신규 P3 | — | — | 4 | 0 | 0 | **0** |
| Tracked 재분류 | 2 | — | 2 | 0 | 5 | **3** (correction ×2 + NOT-A-DEFECT ×1) |
| 누적 수정 | 8/86 | 8/88 | 8/89 | 8/89 | 8+/90 | **8/89** (재분류로 잠정 FIXED 2건 취소, FRTB 1건 total 축소) |

## 주요 시사점

1. **PR #10 워든 벽투과 음파는 서바이벌 계약 근본 파괴** — 코드 주석 자체가 "블록 무시" 명시 (L1673). 설계 의도로 처리됐지만 밀폐 셸터가 무의미해지는 순간 서바이벌 게임의 기본 가정이 무너짐. `damage(5)` 를 line-of-sight 체크로 감싸는 것이 최소 fix (`applyPos`/`blinkTeleport` 처럼 raycast 도구는 이미 파일 내에 존재).

2. **PR #35 spot-check 오류 발견 → 이번 라운드 정정** — `applyPos`/`blinkTeleport` "완전 제거" 판정은 grep/파일-라인수 계측 오차. 파일이 이미 ~3800 라인 규모였음에도 "1687 lines" 로 기록. **한 세션 결과를 이후 라운드가 맹신하지 않도록 스팟체크 재검증 필수 패턴 재확인**. 재분류 시스템 자체는 정상 작동 (이번 라운드가 상위 라운드 오류 발견).

3. **PR #5 FRTB re-audit 결과 wired 확인 → NOT A DEFECT** — 값 자체 (1.70-1.92 yellow) 는 FRTB IMA base multiplier m_c 스펙 정확 일치, `compute_ima_capital` 에서 `es_97_5 * backtest.multiplier` 로 실적용. **7주 연속 P0×4 재환기 문구를 P0×3 으로 정정 필요** — 나머지 3건 (rwa_sa corporate B RW=1.00 · SRISK (1-k) · CoVaR mask) 는 여전히 LIVE.

4. **PR #4 errata 4주 연속 미발행 + CHG-0143 재할당 미이행** — 지난 라운드 지시가 이행되지 않은 상태 그대로. Round 78 이후 무커밋 → owner 대응 부재 지속.

5. **PR #2 12주 · PR #22 9주 · PR #3/6/7/8 11+주 방치** — owner action fully absent. 21주차 리뷰 시점 close 절차 실질 진입 필요. **리뷰가 지시하는 close 를 실제로 실행하는 프로세스 자체가 없는 것이 근본 원인**.

## 다음 라운드 (22주차) 권고

1. **PR #10 워든 벽투과 음파 fix 강제** — `hasLineOfSight()` 체크 추가 (raycast/DDA 도구 이미 존재).
2. **PR #5 corporate B RW=1.00 → 1.50 fix 강제** (**7주 연속**) — 1줄 수정 `risk_lib/capital/rwa_sa.py:49`.
3. **PR #5 SRISK · CoVaR fix** — `systemic.py:52` `k·assets` 로 정정 · `systemic.py:103` point mask 로 정정 (or 구간 유지 시 문서 명시).
4. **PR #4 CHG-0143 재할당 + ERRATA-2026-07-14 발행 강제** (**4주 연속** 미이행).
5. **PR #22 close 시행** (**5주 연속** 권고).
6. **PR #2 close 시행** (12주 방치).
7. **PR #7 close, #8 base rebase**.

## 리뷰 방식

**메인 스레드 단일 세션, PR #10 신규 커밋 실측 + PR #5 스팟체크 3파일 raw fetch**:

- 12개 감시 PR head SHA 대조 → **1개 이동 (PR #10)** 확인. 신규 PR 검색: `list_pull_requests state=open sort=created desc` 첫 페이지 max=#35 확인 → **신규 PR 0건**.
- PR #10 커밋 2건 stat/message 확인 (ab1af827 +322/-56 · ceaf4922 +88/-12).
- **PR #10 `minecraft/index.html` 전문 raw fetch** (3966 lines, ceaf4922 head).
  - grep: `applyPos` L3732 · `blinkTeleport` L2996 · `WORLD_VER` L346 · `saveGame` L700 · `destroyBlocks` L898 · `safeSpawn` L3694 · `warden`/`sonic` L1667+.
  - **PR #35 판정 오류 발견**: `applyPos`/`blinkTeleport` 은 REMOVED 가 아니라 그대로 존재. 재분류 정정.
  - `warden` sonic 로직 L1668-1678 실측 → "블록 무시" 주석 확인, damage(5) 무조건 명중 확인 → 신규 P1 도출.
  - `placeSpawnPortal` L3667-3683 실측 → `genDim()` 흐름에서 edits replay 이전 실행, 사용자 편집 우선순위 정상.
  - `suitUlt` L2965-2992 실측 → 쿨다운 6-8초, 동물 제외, 데미지 수치 정상.
- **PR #5 `risk_lib/capital/rwa_sa.py` 전문 raw fetch** → `_RW_CORPORATE["B"] = 1.00` L49 실측. LIVE.
- **PR #5 `risk_lib/systemic.py` 전문 raw fetch** → SRISK L52 · CoVaR mask L103 실측. LIVE.
- **PR #5 `risk_lib/frtb.py` 전문 raw fetch** → `_backtest_zone` L160-174 · `compute_ima_capital` L215-235 실측. **wired 확인 → NOT A DEFECT 재분류**.
- PR #4 `report_pack.py` 무커밋 → 자동 LIVE 유지 (Round 78 이후 head SHA 무변경).
- PR #2/3/6/7/8/9/22/30/32 head SHA 무변경 → 자동 LIVE 유지.

**단독 리뷰어 (에이전트 배정 없음), 중 위험도 (신규 P1×1 + 상위 라운드 오류 정정 3건)** 라운드로 판단.

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
