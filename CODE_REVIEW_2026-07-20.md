# 전체 저장소 코드 리뷰 — 2026-07-20 (22주차)

## 요약

지난 라운드 (PR #36, 2026-07-18 21:11 UTC) 이후 ~48h. **감시 12개 PR 중 1개 (PR #10) head SHA 이동**, 8커밋 push (2026-07-18 23:20 UTC ~ 2026-07-20 11:00 UTC). 나머지 11개 무커밋. 신규 PR 0건.

- **신규 P0** — 0건.
- **신규 P1** — 0건 (PR #10 8커밋 스팟체크에서 신규 P1 무발생. 이전 라운드 P1 warden 관통은 미수정 → 아래 tracked LIVE 참조).
- **신규 P2** — 0건.
- **신규 P3** — 1건 (PR #10 `damage()` L2400 주석 stale — 위더 스톰 80% 감쇠 반영 안 됨).
- **Tracked 재확인** — PR #10 warden sonic 벽투과 **2주 연속 LIVE** (PR #36 지시 미이행), PR #5 · PR #4 tracked 전건 LIVE 유지.

## 이번 라운드 델타 커밋

| PR | 이전 head (PR #36) | 현재 head | 커밋 | 요지 |
|---|---|---|---|---|
| **#10** | `ceaf4922` | **`6601e55a`** | **8** | (1) `32ce62bb` 위더 스톰 5번째 변신 · (2) `7c202071` 위더 메시 재제작 + 지형 흡수 · (3) `420306dc` TNT 무기 (16-agent adversarial review 7건 수정) · (4) `67462b5e` 슈퍼 TNT (12500% blast, r=20) · (5) `8e0c8581` 포탈 오브 구체 렌더 · (6) `b11f6891` 5배 큰 포탈 + `findDryColumn` 물·용암 회피 · (7) `44ee3a77` 번개 TNT + 지진 TNT + 기반암 최하층 2칸 보존 · (8) `6601e55a` 피글린 몹 (네더 35%) |
| 그 외 11개 | 무변경 | — | 0 | PR #2/#3/#4/#5/#6/#7(dirty)/#8(dirty)/#9/#22/#30/#32 head 무커밋 |

**최근 커밋 시각**: PR #10 마지막 `6601e55a` `2026-07-20 11:00:14Z` (~10h 전). 다른 감시 PR 은 ≥48h 무커밋. PR #5 마지막 코드 커밋 `2026-07-17 01:55` (~92h), PR #4 는 `2026-07-17 01:52` (~92h).

## 이번 라운드 신규 P0 · 0건

## 이번 라운드 신규 P1 · 0건

PR #10 의 8커밋 대량 추가에도 신규 P1 이 나오지 않은 이유:

- **`420306dc` TNT 커밋 자체가 16-agent 적대적 리뷰를 거쳐 확정된 결함 7건 을 사전 수정**. `updateTNT` L1059 timeStop/playing() 게이트, 폭발 중심 +0.5 보정, editBlock+destroyBlocks 이중 리빌드 → setBlock+edits 로 정리, 포탈/상자 폭발 면역 (L921), 상자 아이템 소실 방지, 스모크 하니스 카메라 스텁 실측 방향 주입 등.
- **`44ee3a77`** 커밋에서 `destroyBlocks` L917 `if (y < 2 || y > Y_MAX) continue;` 로 최하층 2칸 보존 — 스폰 리스폰 루프 하드락 사전 방지.
- **`b11f6891`** 커밋에서 `findDryColumn` L4093 도입 — 오버월드 물 / 전 차원 용암 칼럼 회피 후 포탈 배치.

## 이번 라운드 신규 P2 · 0건

## 이번 라운드 신규 P3 · 1건

### PR #10 (`ab1af827` 이전부터 존재하나 `32ce62bb`/`7c202071` 로 실질 조건 확장) — `damage()` L2400 주석 stale

`minecraft/index.html:2397-2408`:

```javascript
function damage(n) {
  if (optPeace) return;
  if (n <= 0 || health <= 0) return;
  // 방어구 피해 감소 (아이언·스트레인지 60% / 헐크버스터 75%)
  const red = suitLevel === 4 ? 0.8 : suitLevel === 2 ? 0.75 : suit ? 0.6 : ([0, 0.3, 0.6][armor] || 0);
  n = Math.max(1, Math.ceil(n * (1 - red)));
  ...
}
```

**증상**: L2400 주석은 아이언·스트레인지 60% / 헐크버스터 75% 만 언급. L2401 실제 코드는 위더 스톰(레벨 4) 80% 감쇠 신규 추가. 리뷰어·향후 세션이 주석만 보고 로직을 오해할 위험. **로직 자체는 정상 동작** (헐크버스터 75%→0.25 배 유지, 위더 80%→0.2 배 적용).

**fix (1줄)**: 주석을 `// 방어구 피해 감소 (아이언·스트레인지 60% / 헐크버스터 75% / 위더 스톰 80%)` 로 갱신.

**우선순위 P3**: 실행 로직 정상, 순수 문서화 부채.

## Tracked LIVE 재확인

### PR #10 warden sonic 벽투과 — **2주 연속 LIVE (PR #36 지시 미이행)**

**`minecraft/index.html:2014-2026`** (현 head `6601e55a` 실측):

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

**상태**: PR #36 (21주차) 지시 (권고 #1: "`hasLineOfSight()` 체크 추가") 미이행. 코드 · 라인 번호 · 로직 완전 동일. **밀폐 셸터 무의미 계약 파괴 유지**. 워든 스폰율 오버월드 밤 4% / 보이드 20% 도 무변경.

**8커밋 사이에 warden 관련 수정은 0건**. Piglin(`6601e55a`) 커밋이 위더 관통 이슈보다 우선순위 후로 배치되지 말았어야 하는 사례.

**조치**: PR #10 owner 에게 22주차에도 **강제 fix 재지시** — `raycastBlock` (파일 L3410 근처 `blinkTeleport` 로직 재활용 가능) 로 `damage(5)` 를 감쌀 것.

### PR #10 `applyPos` NaN 방지 부재 — LIVE 유지

**L4170-4177** 그대로 (PR #36 실측과 동일):

```javascript
function applyPos(p) {
  if (!p) return false;
  player.pos.set(p.x, p.y, p.z);
  ...
}
```

세이브 데이터 손상 시 `player.pos` NaN 오염 리스크 유지. 8커밋 중 세이브 관련 변경(WORLD_VER 이동) 있었으나 NaN 가드는 추가 안 됨.

### PR #10 `blinkTeleport` 0.5-step 대각 관통 — LIVE 유지

**L3410** 그대로. 실질 위험도 낮음(마지막 non-colliding 위치로 스냅) — 기존 판정 유지.

### PR #5 corporate B RW = 1.00 — **8주 연속 LIVE**

`risk_lib/capital/rwa_sa.py:49` `"B": 1.00` 유지 (PR #5 무커밋). Basel III CRE20 = 1.50 미정정. 1줄 fix 8주 방치.

### PR #5 SRISK `(1-k)` — **8주 연속 LIVE**

`risk_lib/systemic.py:52` `srisk = prudential_ratio * debt - (1 - lrmes) * equity` 유지. Brownlees & Engle (2017) 정의 오적용 유지.

### PR #5 CoVaR own-loss mask — **8주 연속 LIVE**

`risk_lib/systemic.py:103` `mask = losses[:, i] >= thresh` 유지. Adrian & Brunnermeier (2016) 점조건 (quantile regression) 대신 구간조건 유지.

### PR #4 ERRATA-2026-07-14 미발행 — **5주 연속**

`docs/ERRATA-2026-07-14-icaap-post-stress-mislabel.md` 여전히 미존재. R39-R74 오라벨링 shipped 상태 지속. PR #4 무커밋 (Round 78 이후 ~92h+).

### PR #4 CHG-0143 재할당 미이행 — **5주 연속**

PR #36 지시 (권고 #4) 미이행. A11y 재사용 상태 유지.

### PR #4 `report_pack.py` P0/P1

- `~L3762` `cet1_min_pillar1 = 0.045` (SSoT 미위임)
- `~L3788` `total < cet1_required + 0.03` (Basel Total-cap surcharge 는 0.035)
- `~L4354` `salt = hashlib.sha256(...)` (재식별 위험 자체 시인)

모두 LIVE (PR #4 무커밋).

## 그 외 tracked LIVE (커밋 무변경 → 자동 유지)

- **PR #2 `stock_trading/harness.py` — 13주 방치**: sticky last_text L210 · run-level sticky APPROVED L82-141 · P0×2 + PARTIAL×2. **close 절차 진입 3주 연속 권고**.
- **PR #3 `quant_validation_team_agent/` — 12주 방치**: 6/15 대응 후 무커밋.
- **PR #6 codex trading agent — 12주 방치**: P1×1 LIVE.
- **PR #7 (dirty) — 11+주 방치**: P1×1 + P2×1 LIVE. close 권고.
- **PR #8 (dirty) — 11+주 방치**: P1×1 + P2×1 LIVE. base rebase 필요.
- **PR #9 `risk-research-harness` — 무변화**: P1×1 LIVE + PARTIAL 유지.
- **PR #22 `.claude/skills/` — 10주 방치**: `skills-lock.json` sourceCommit 부재 · `code-review/` slug 충돌 · `implement/SKILL.md` /code-review chain + auto-commit. **6주 연속 close 권고**.
- **PR #30 `CLAUDE.md §0` + `docs/ISO-42001-AGENT-REQUIREMENTS.md` — 6주 방치**: 소급 조항 부재, CI check 부재.
- **PR #32 `mecha-chameleon/index.html` — 5주 무변화**: `startBtn.blur()` 미도입, tongue CCD 미도입.

## 결과 매트릭스

| PR | 이번 커밋 | 이번 신규 | 이전 findings 상태 | 권고 |
|---|---|---|---|---|
| **#32** | 0 | — | P2×2 + P3×3 LIVE (**5주**) | mergeable — small polish |
| **#30** | 0 | — | P1×1 LIVE (**6주 방치**) | **block-merge** (소급 조항 필요) |
| **#10** | **8** (Wither 변신·TNT×4·Piglin·포탈오브) | **P3×1** (주석 stale) | tracked LIVE 12 (warden **2주 연속 미수정**) | **block-merge** (warden 관통 해결 후 mergeable) |
| **#5** | 0 | — | P0×3 + P1×1 + P2×2 LIVE (**8주 연속 P0 미수정**) | **block-merge / escalate** |
| **#4** | 0 | — | P0×1 + P1×2 LIVE + FIXED×1 · PARTIAL×3 (**5주 연속 errata 미발행**) | **changes requested + CHG-0143 재할당 강제** |
| **#3** | 0 | — | P1/P2 LIVE (**12주 방치**) | owner 미회신 시 close |
| **#2** | 0 | — | P0×2 LIVE + P0×2 PARTIAL (**13주 방치**) | **close 절차 진입** (3주 연속) |
| **#9** | 0 | — | P1×1 LIVE + PARTIAL 유지 | block-merge |
| **#22** | 0 | — | P0×3 LIVE (**10주 방치**) | **close 즉시 시행** (6주 연속) |
| **#6** | 0 | — | P1×1 LIVE (13주 방치) | close |
| **#7** | 0 (dirty) | — | P1×1 + P2×1 LIVE | close (#8 이 승계) |
| **#8** | 0 (dirty) | — | P1×1 + P2×1 LIVE | base rebase 후 재검토 |

## 누적 22회 결산

|  | #31 | #33 | #34 | #35 | #36 | **이번** |
|---|---|---|---|---|---|---|
| 신규 P0 | 0 | 0 | 0 | 0 | 0 | **0** |
| 신규 P1 | 2 | 1 | 0 | 1 | 1 | **0** |
| 신규 P2 | 6 | 3 | 0 | 1 | 0 | **0** |
| 신규 P3 | — | 4 | 0 | 0 | 0 | **1** |
| Tracked 재분류 | — | 2 | 0 | 5 | 3 | **0** |
| 누적 수정 | 8/88 | 8/89 | 8/89 | 8+/90 | 8/89 | **8/89** (신규 P3 1건 추가로 total 90 이나 fix 무변화) |

## 주요 시사점

1. **PR #10 warden 관통 fix 2주 연속 미이행** — PR #36 이 P1 로 명시하고 raycast 재사용 fix 도구까지 지목했음에도 3커밋 (`44ee3a77` 지진/번개 TNT · `6601e55a` 피글린 · `8e0c8581` 포탈 오브) 추가 여유가 있었으나 warden 은 손대지 않음. **owner 우선순위 신호와 리뷰어 P1 지정이 결합되지 못한 사례** — 22주차에 재지시.

2. **PR #10 TNT 커밋 자체가 16-agent 적대적 리뷰 통과** — 커밋 `420306dc` 메시지가 사전 리뷰로 결함 7건 을 확정·수정했음을 밝힘. 이번 라운드 스팟체크에서도 (a) `updateTNT` timeStop/playing() 게이트 L1059 · (b) 폭발 중심 +0.5 보정 L1083 · (c) `destroyBlocks` 포탈·상자 면역 L921 · (d) 최하층 2칸 기반암 보존 L917 (`44ee3a77` 추가) 등이 모두 실장 확인. **적대적 리뷰 워크플로 실효성 입증**. 이번 라운드가 신규 P1 을 낳지 않은 주 원인.

3. **PR #5 P0×3 · PR #4 ERRATA · PR #22 close · PR #2 close · PR #30 소급조항** — 리뷰가 5–13주 연속 지시하는 사안이 owner action 부재로 shipped 유지. **리뷰가 지시하는 close/fix 를 실제로 실행하는 프로세스 자체 부재가 근본 원인** (PR #36 요약과 동일 지속).

4. **재분류/오류 정정 사이클 안정화** — PR #35 의 grep 계측 오류를 PR #36 이 정정한 후 이번 라운드에선 tracked 재분류 0건. 상위 라운드 결과를 맹신하지 않는 spot-check 재검증 패턴이 안착 중.

5. **PR #10 신규 P3 (주석 stale)** — 22주 만에 P3 로 P0/P1/P2 가 아닌 문서화 부채가 발생. 스토리 진전(위더 4번째 변신 추가)에 따라 자연스럽게 발생한 부채로 판단, 실행 로직은 정상.

## 다음 라운드 (23주차) 권고

1. **PR #10 warden 벽투과 fix 강제 (3주째)** — `hasLineOfSight()` 체크 추가 (raycast/DDA 도구 이미 존재).
2. **PR #10 `damage()` L2400 주석 갱신** (1줄, 위더 스톰 80% 반영).
3. **PR #5 corporate B RW = 1.00 → 1.50 fix 강제 (8주 연속)** — 1줄 `risk_lib/capital/rwa_sa.py:49`.
4. **PR #5 SRISK · CoVaR fix** — `systemic.py:52` `k·assets` / `systemic.py:103` point mask.
5. **PR #4 CHG-0143 재할당 + ERRATA-2026-07-14 발행 강제 (5주 연속)**.
6. **PR #22 close 시행 (6주 연속)**.
7. **PR #2 close 시행 (13주 방치)**.
8. **PR #7 close, #8 base rebase**.

## 리뷰 방식

**메인 스레드 단일 세션, PR #10 신규 커밋 8건 실측 + PR #5/#4 tracked 스팟체크**:

- 12개 감시 PR head SHA 대조 → **1개 이동 (PR #10 `ceaf4922` → `6601e55a`)** 확인. 신규 PR 검색 `list_pull_requests state=all` → 페이지 1 상단 max=#36 (2026-07-18) 확인 → **신규 PR 0건**.
- PR #10 커밋 8건 message/date 확인 (`32ce62bb` 2026-07-18 23:20 → `6601e55a` 2026-07-20 11:00).
- **PR #10 `minecraft/index.html` 전문 fetch** (4414 lines, `6601e55a` head, +448 lines vs PR #36 3966 lines).
  - grep: `warden`/`sonic` L2014-2026 · `applyPos` L4170 · `blinkTeleport` L3410 · `safeSpawn` L4126 · `findDryColumn` L4093 · `damage()` L2397-2408 · TNT L932-1110 · Piglin/Wither L1565-1710/1911.
  - **warden**: PR #36 지적 라인 · 로직 완전 동일 → 2주 연속 LIVE 확인.
  - **TNT (4종)**: `destroyBlocks` L909 포탈/상자 면역 · 최하층 2칸 보존 · `updateTNT` timeStop 게이트 · `lightningExplosion` 동물 안전 · `updateQuakes` 링 밴드 알고리즘 확인 → 신규 P1 이상 미발생.
  - **damage() 주석 stale (L2400)**: 위더 스톰 80% 감쇠 미언급 → 신규 P3.
  - **Piglin**: `killMob` L2115 gold drop 정상, `makePiglinMesh` L1565 정상.
  - **Wither Storm 변신**: `makeWitherSuitMesh` L3245 · `SUIT_STATS[4]` L3113 · `damage()` 80% 감쇠 L2401 → 로직 정상.
- **PR #5 tracked 3건**: 무커밋 → 자동 LIVE 유지 (실측 재검증 생략, PR #36 실측 재활용).
- **PR #4 tracked**: 무커밋 → 자동 LIVE 유지, ERRATA-2026-07-14 미발행 상태 유지 확인.
- PR #2/#3/#6/#7/#8/#9/#22/#30/#32 head SHA 무변경 → 자동 LIVE 유지.

**단독 리뷰어 (에이전트 배정 없음), 저-중 위험도 라운드** 로 판단 — 대량 커밋 8건에도 신규 P1 이 나오지 않은 것은 `420306dc` TNT 커밋의 사전 적대적 리뷰 (16-agent) 실효성 덕분.

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
