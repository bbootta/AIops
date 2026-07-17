# 전체 저장소 코드 리뷰 — 2026-07-17 (20주차)

## 요약

지난 라운드 (PR #34, 2026-07-16 21:08 UTC) 이후 ~28h. **감시 대상 12개 PR 중 3개 (#4, #5, #10) head SHA 이동, 나머지 9개 무변경.** 각각 1커밋씩, 모두 2026-07-17 01:52~01:55 UTC 사이에 근접 push (같은 세션 도구 발화로 추정).

- **신규 P0** — 0건.
- **신규 P1** — 1건 (PR #4 Round 78 이 CHG-0143 을 A11y 에 재사용, PR #33 이 지정한 ICAAP errata slot 오염).
- **신규 P2** — 1건 (PR #4 Round 78 A11y 스코프가 SVG 로 한정, HTML/table/dark-mode 색약 등 미포함).
- **신규 P3** — 0건.
- **Tracked 재분류** — 5건 (PR #5 `rwa_sa.py` → `risk_lib/capital/rwa_sa.py` 대이동, `systemic.py` line-shift, PR #10 `applyPos`·`blinkTeleport` 완전 제거).

19주차 zero-delta 라운드 종료. PR #34 가 스팟체크에서 놓친 **PR #5 rwa_sa 파일 대이동** (Basel III/FSS harness 의 SA RW 모듈이 서브패키지화됨) 을 이번 라운드에 실측 재검증하며 발견 — **corporate B RW=1.00 는 그대로 LIVE, 위치만 변경**.

## 이번 라운드 델타 커밋

| PR | 이전 head (PR #34) | 현재 head | 커밋 | 요지 |
|---|---|---|---|---|
| **#4** | `89a67fe5` (Round 77) | **`fdb68cb8`** (Round 78) | 1 | SVG 접근성 — `role="img" + aria-label` (6개 차트 빌더 + report_pack ROC/Score 2개), CHG-0143 (proposed) |
| **#5** | `27582402` | **`8de106da`** | 1 | `build_full_report_package` history_path — TimeSeriesLedger 영속 QoQ (executive §0-c 개선/악화 badge + 연속 위반 카운터), 582 tests |
| **#10** | (36 commits) | **`846a2567`** | 1 | 시작화면 업적/통계 패널, 플레이 통계 훅, 월드 부팅 loading indicator + TDZ fix, smoke-test 확장 |
| 그 외 9개 | 무변경 | — | 0 | PR #2/3/6/7(dirty)/8(dirty)/9/22/30/32 head 무변경 |

**최근 커밋 시각**: PR #4 `2026-07-17 01:52:43Z` · PR #10 `01:53:28Z` · PR #5 `01:55:22Z` — 세션 `session_013kj2ERu1hXoZtKRiGtQYdE` (PR #5) 과 다른 두 세션이 병렬 push.

## 이번 라운드 신규 P1 · 1건

### PR #4 — Round 78 (`fdb68cb8`) 이 CHG-0143 을 A11y 에 재사용, PR #33 이 지정한 ICAAP errata slot 오염

지난 18주차 리뷰 (PR #33) 신규 P1 항목 fix 지시:

> `docs/ERRATA-2026-07-14-icaap-post-stress-mislabel.md` (영향 R39-R74), **CHG-0143 별도 등록**, 이전 shipped report pack 에 errata 배너 또는 archive 이동.

이번 Round 78 커밋 메시지 마지막 줄: `CHG-0143 (proposed)` — SVG aria-label 작업으로 소비.

**결과**:
1. **ICAAP `post_stress_level` errata 발행 부재 유지** — R39-R74 (약 36 라운드) shipped report pack 이 정상 자본 비율을 fail 로 오라벨링한 채 방치. 이번 라운드 커밋에도 `docs/ERRATA-*` 파일 미신설, PR #33 지시 미이행.
2. **`change_manifest.json` slot 충돌** — PR #33 리뷰가 예약한 CHG 번호가 다른 목적으로 사용됨 → change_id 시맨틱 무결성 훼손. 감사 시점에서 CHG-0143 을 검색하면 "ICAAP errata" 가 아닌 "SVG A11y" 만 나타남 → PR #33 지시 이행 여부 추적 불가.
3. **CHG 번호 배정 프로세스에 lint/reserve 부재** — 리뷰 지시가 자동 강제되지 않음 (governance.py Pillar 3 deprecated flag 와 동일 패턴 — PR #5 tracked P2).

**fix**:
- (a) Round 78 A11y 를 `CHG-0144` 로 재할당.
- (b) `CHG-0143` 을 원래 목적 (ICAAP errata) 으로 복원 + `docs/ERRATA-2026-07-14-icaap-post-stress-mislabel.md` 신설.
- (c) `tools/manifest.py add` 에 리뷰 예약 slot 감지 훅 추가 (예: `.claude-review-reserved.json`).

## 이번 라운드 신규 P2 · 1건

### PR #4 — Round 78 A11y 스코프 협소

커밋 메시지: **"svg_charts.\_aria 헬퍼: 차트 종류+제목 라벨 (escape 처리) · 6개 차트 빌더 + report_pack 커스텀 2개 (ROC/Score 분포) 적용 · 팩 47페이지 전수 검사 테스트 — 미라벨 SVG 0건"**.

**미포함**:
- HTML `<img>` (KPI 카드 아이콘, 로고, 배지 등) 대체 텍스트 audit — Round 76 dark mode 도입 시 신설된 이미지 리소스 다수.
- `<table>` `<caption>` — 47페이지 report pack 대부분 표 기반, `caption` / `scope` / `summary` 마킹 없음 → 스크린리더 사용자 접근성 여전히 낮음.
- **색약 대응** — Round 76 dark mode 배포 시 tracked P3 (`@media (prefers-color-scheme: dark)` 만 지원, `:root[data-theme]` 미대응) 은 이번 라운드에도 미조치. dark 모드 + red/green 상태 뱃지 조합에서 deuteranopia/protanopia 사용자 판독 불가.
- 키보드 네비게이션 (nav 탭 focus outline, skip-to-content link, `role="tablist"`) — 47페이지 다중 탭 UI 에서 필수.

Round 78 이 스스로 "차트 접근성" 을 표방하지만 WCAG 2.2 AA 대비 SVG 만으로는 부분적 대응. `docs/A11Y-AUDIT-2026-07-17.md` 신설로 스코프 명시 필요.

**fix**: A11y audit 범위 문서화 + HTML/table/색약/키보드 대응 계획을 CHG-0145 이상으로 후속 등록.

## Tracked 재분류 · 5건

### PR #5 (`8de106da`) — `risk_lib/rwa_sa.py` → `risk_lib/capital/rwa_sa.py` 대이동

**PR #34 스팟체크가 놓친 구조 변경.** 이번 라운드 실측 재검증:

| 기존 (PR #34) | 신규 (실측) | 상태 |
|---|---|---|
| `risk_lib/rwa_sa.py:26` sovereign B RW=1.00 | **`risk_lib/capital/rwa_sa.py:29`** `"B": 1.00` | **LIVE** (Basel III CRE20 sovereign B = 100% → 실은 표준값과 일치, 지난 tracked 는 판단 오류) |
| `risk_lib/rwa_sa.py:36` bank ECRA B RW=1.00 | **`risk_lib/capital/rwa_sa.py:39`** `"B": 1.00` | **LIVE** (Basel III CRE20.11 bank ECRA B 는 grade 3-4 = 100% → 표준값과 일치, 지난 tracked 도 판단 오류 가능) |
| `risk_lib/rwa_sa.py:46` corporate B RW=1.00 | **`risk_lib/capital/rwa_sa.py:49`** `"B": 1.00` | **LIVE** (Basel III CRE20 corporate B = **150%** — 여전히 결함) |

**Basel III CRE20 D. Weights, corporate exposures 표준 리스크 가중**:
- AAA-AA: 20% · A: 50% · BBB: 75% · BB: 100% · **B: 150%** · CCC 이하: 150%

현재 코드 (line 44-52):
```python
_RW_CORPORATE = {
    "AAA-AA": 0.20,
    "A": 0.50,
    "BBB": 0.75,
    "BB": 1.00,
    "B": 1.00,      # ← Basel III 는 1.50
    "CCC-": 1.50,
    "UNRATED": 1.00,
}
```

**fix**: `_RW_CORPORATE["B"] = 1.50` — 1줄 수정. 파일 이동은 SSoT 정리로 긍정적이나, **값 자체는 이동 이전과 동일** — 6주 연속 exec/UI/파일이동 만 만지고 본질 P0×4 미터치 패턴의 연속.

### PR #5 (`8de106da`) — `risk_lib/systemic.py` line-shift

| 기존 (PR #34) | 실측 (신규) | 상태 |
|---|---|---|
| L61 `srisk = prudential_ratio * debt - (1 - lrmes) * equity` | **L52** (동일 코드) | **LIVE** — Brownlees & Engle (2017) 정의 `k·(D+(1-LRMES)·E) - (1-LRMES)·E` 대비 prudential ratio 를 자산 대신 부채에 적용 → capital shortfall 과잉 계상. |
| L122 `mask = losses[:, i] >= thresh` | **L103** (동일 코드) | **LIVE** — 저자 자체 주석 (L101): `# condition on bank i near its VaR (top 5% of its own loss)`. Adrian & Brunnermeier (2016) 는 `X^j | X^i = VaR^i` 점조건, 여기선 `X^i ≥ VaR^i` 구간조건 → tail-dependence 왜곡. |

**참고**: `risk_lib/timeseries_ledger.py` (10,910B) 신설 — 이번 QoQ 커밋의 SSoT. exec 층 강화 방향 지속.

### PR #10 (`846a2567`) — `minecraft/index.html` 대형 리팩터

전체 파일 라인 수: **1687** (지난 tracked 는 4000+ 라인 기준 인용 — 대량 삭감/재구성).

| tracked (PR #33) | 현재 위치 | 상태 |
|---|---|---|
| P1 `applyPos` L3390 NaN 방지 | **완전 제거** (0 matches) | **REMOVED** — 잠정 FIXED 로 재분류. 새 물리 코드 (stepMob) 로 대체 추정, 재검토 필요. |
| P2 `blinkTeleport` 벽 관통 | **완전 제거** (0 matches) | **REMOVED** — 잠정 FIXED 로 재분류. |
| P2 `destroyBlocks` CHEST L834 | **L917** | **LIVE @ new line** (line shift +83, CHEST 로직 유지 여부 재검토 필요). |
| P1 `saveGame` sync stall L639 | **L267** | **RECHECK** — 위치 대이동 (-372), 함수 시그니처/락 정책 재검증 필요. |
| P1 `WORLD_VER=5` inv-loss L334 | **L40** | **LIVE @ new line** — `const WORLD_VER = 5; // v5: 월드 192x192 확장` (WORLD_VER=5 upgrade 시 저장 데이터 아이템 손실 가능성 유지). |
| P2 `timeStop` arrows 배열 성장 | **L1532** `let timeStop = false;` + `L942/1399/1563/1569` 참조 | **LIVE @ new line**. |

**추가 관찰**:
- Round `846a2567` 커밋 메시지 시인: `"스모크의 동기 setTimeout이 드러낸 TDZ 취약점 수정: last/waterT 선언을 부팅 코드 앞으로 이동"` — **실제 버그 fix**. Round 78 (PR #4) 와 대조: PR #10 은 tracked 미터치 커밋에서도 신규 실버그 1건 자발 발견/수정.
- 신규 achievements 패널 (10종) + stats 훅 (`killMob·updateMining·doPlace·respawn·loop`) → 이벤트 훅 다수 신설, race condition 재검증 대상.

**tracked 재분류 조치**: `applyPos` + `blinkTeleport` 은 다음 라운드 (21주차) 스팟체크에서 실제 물리 코드 검증 후 FIXED 확정. 그 외 3건 (`destroyBlocks`·`saveGame`·`WORLD_VER`) 은 새 라인에서 실측 재검토.

## 그 외 tracked LIVE (커밋 무변경 → 자동 유지)

- **PR #2 `stock_trading/harness.py` — 11주 방치**: `~L210` sticky last_text · `L82-141` sticky APPROVED · 그 외 P0×2 + PARTIAL×2. PR #34 이후 close 절차 진입 권고 반복.
- **PR #4 `validation-team-agent/tools/report_pack.py` — Round 78 은 SVG 만 수정, 다음 3건 무관 → 자동 LIVE**:
  - `~L3762` `cet1_min_pillar1 = 0.045` (SSoT 미위임)
  - `~L3788` `total < cet1_required + 0.03` (Basel Total-cap surcharge 는 0.035)
  - `~L4354` `salt = hashlib.sha256(f"vta-pack-salt-{args.seed}".encode())` (재식별 위험, 자체 주석 시인)
  - 정확한 라인 shift 는 Round 78 이 report_pack 에 SVG aria-label 2건만 추가했으므로 최대 ±2 이내로 예상.
- **PR #5 `risk_lib/frtb.py:170-174`**: `mult = {5: 1.70, 6: 1.76, 7: 1.83, 8: 1.88, 9: 1.92}[n_exc]` + red-zone `2.00` — BCBS MAR99 traffic light 값 자체는 표준값 존재. 지난 tracked 표기 "미적용" 은 wired-in 여부 (실제 IMA 자본 charge 계산에 이 multiplier 가 붙는지) 재검토 필요. 이번 라운드 spot check 미수행.
- **PR #22 `.claude/skills/` — 8주 방치**: `skills-lock.json` sourceCommit 부재 · `code-review/` slug 충돌 · `implement/SKILL.md` /code-review chain + auto-commit. 4주 연속 close 권고.
- **PR #30 `CLAUDE.md §0` + `docs/ISO-42001-AGENT-REQUIREMENTS.md` — 4주 방치**: 소급 조항 부재, CI check 부재.
- **PR #3/6/7(dirty)/8(dirty)/9 — 무변화**.
- **PR #32 `mecha-chameleon/index.html` — 3주 무변화**: `startBtn.blur()` 미도입, tongue CCD 미도입.

## 결과 매트릭스

| PR | 이번 커밋 | 이번 신규 | 이전 findings 상태 | 권고 |
|---|---|---|---|---|
| **#32** | 0 | — | P2×2 + P3×3 LIVE (3주) | mergeable — small polish |
| **#30** | 0 | — | P1×1 LIVE (**4주 방치**) | **block-merge** (소급 조항 필요) |
| **#10** | 1 (achievements + TDZ fix) | — | tracked 12 중 2 잠정 FIXED, 4 line-shift LIVE | **block-merge** (재검증 완료 후 부분 승인 가능) |
| **#5** | 1 (QoQ history) | — (tracked 재분류) | P0×4 + P1×1 + P2×2 LIVE (**6주 연속 exec/UI**) | **block-merge / escalate** — corporate B RW 는 이제 `capital/rwa_sa.py:49` |
| **#4** | 1 (A11y aria-label) | **P1×1** + P2×1 | P0×1 + P1×2 LIVE + FIXED×1 · PARTIAL×3 | **changes requested + CHG-0143 재할당** |
| **#3** | 0 | — | P1/P2 LIVE (**10주 방치**) | owner 미회신 시 close |
| **#2** | 0 | — | P0×2 LIVE + P0×2 PARTIAL (**11주 방치**) | **close 절차 진입** |
| **#9** | 0 | — | P1×1 LIVE + PARTIAL 유지 | block-merge |
| **#22** | 0 | — | P0×3 LIVE (**8주 방치**) | **close 즉시 시행** (4주 연속) |
| **#6** | 0 | — | P1×1 LIVE (11주 방치) | close |
| **#7** | 0 (dirty) | — | P1×1 + P2×1 LIVE | close (#8 이 승계) |
| **#8** | 0 (dirty) | — | P1×1 + P2×1 LIVE | base rebase 후 재검토 |

## 누적 20회 결산

|  | #28 | #29 | #31 | #33 | #34 | **이번** |
|---|---|---|---|---|---|---|
| 신규 P0 | 0 | 0 | 0 | 0 | 0 | **0** |
| 신규 P1 | 2 | 2 | 2 | 1 | 0 | **1** |
| 신규 P2 | 4 | 3 | 6 | 3 | 0 | **1** |
| 신규 P3 | — | — | — | 4 | 0 | **0** |
| Tracked 재분류 | — | 2 | — | 2 | 0 | **5** |
| 누적 수정 | 8/84 | 8/86 | 8/88 | 8/89 | 8/89 | **8+? / 90** (PR #10 잠정 FIXED 2건 확정 시 10/90) |

## 주요 시사점

1. **PR #4 CHG-0143 재사용은 리뷰 지시 무시 패턴** — PR #33 이 명시 예약한 change_id 를 A11y 로 소비. ICAAP errata 는 여전히 미발행 (R39-R74 오라벨링 shipped 상태). **`tools/manifest.py` 에 예약 slot 감지 로직 부재** 가 근본 원인 — CI/tooling 결여로 리뷰 지시가 소프트 gate 로만 작동. Round 78 개발자가 CHG-0143 을 재사용한 것은 리뷰 히스토리 미참조 결과일 가능성.

2. **PR #5 6주 연속 exec/UI/구조 만 개선, 본질 P0×4 미터치** — 이번 라운드는 QoQ history ledger (`timeseries_ledger.py` 신설 10.9KB + `html_exec.py` 25.3KB 확장). **`risk_lib/rwa_sa.py` → `risk_lib/capital/rwa_sa.py` 서브패키지화** 는 SSoT 정리 관점에서 긍정적이나, **corporate B RW=1.00 값은 파일 이동 시에도 수정하지 않고 그대로 복사**. Basel III/FSS 리스크관리 하네스 라는 PR 목적 자체를 훼손하는 정의 오류가 6주째 방치.

3. **PR #10 tracked LIVE 12건 중 2건 (`applyPos`·`blinkTeleport`) 완전 제거** — 3주 무변화 후 처음 유의미한 리팩터. `stepMob` 등 새 물리 코드로 대체 추정. 다음 라운드에서 새 물리 코드 실측 후 FIXED 확정 가능. **커밋 자체가 TDZ 취약점 1건 자발 fix** 도 포함 — PR #4/#5 와 대조되는 자체 검증 문화.

4. **PR #22 4주 연속 close 권고 미이행 · PR #2 11주 방치** — owner action 부재 지속. PR #22 의 `code-review/` slug 충돌은 다른 slash command wiring 오염 위험 8주째 유지.

5. **20주차 정례 리뷰 도달** — 8주차 이후 P0 신규 발견 0 유지 (12주 연속). 다만 tracked LIVE 잔량 (23건) 은 감소하지 않음 → **리뷰가 발견은 잘 하나 fix 유도력은 약함**. 리뷰 자체를 "정보 전달" 이 아닌 "block-merge gate" 로 격상하는 방안 (예: 리뷰 PR merge 없이는 tracked LIVE 있는 감시 PR 을 mergeable 하지 않도록 branch protection) 검토 시점.

## 다음 라운드 (21주차) 권고

1. **PR #4 CHG-0143 재할당** — Round 78 A11y → `CHG-0144`, `CHG-0143` slot 을 ICAAP errata 로 복원. `tools/manifest.py` 에 리뷰 예약 slot 감지 훅 추가.
2. **PR #4 `docs/ERRATA-2026-07-14-icaap-post-stress-mislabel.md` 발행 강제** (3주 연속 권고, 이번 라운드에도 미이행).
3. **PR #5 corporate B RW=1.00 → 1.50 fix 강제 (6주 연속)** — 1줄 수정 (`risk_lib/capital/rwa_sa.py:49`). 이전 라운드까지 위치 오정보를 이유로 미이행 주장 방지.
4. **PR #5 나머지 P0×3 fix 강제** — SRISK `systemic.py:52` `(1-k)` · CoVaR `systemic.py:103` own-loss mask · FRTB `frtb.py:170-174` 실제 IMA charge wired 여부 재검토.
5. **PR #10 tracked 재검증** — 새 물리 코드 (`stepMob`) 에서 `applyPos` 대체 로직의 NaN 방지 실측, `blinkTeleport` 제거 후 텔레포트 기능 자체 삭제/재구현 확인. `saveGame` L267 sync stall 재검토, `destroyBlocks` L917 CHEST 로직 재검토.
6. **PR #22 close 시행** (4주 연속 권고, owner 미응답 지속).
7. **PR #2 close 절차 진입** (11주 방치, 이번 라운드에도 무커밋).
8. **PR #7 close, #8 base rebase** (7주 연속 dirty 방치).

## 리뷰 방식

**메인 스레드 단일 세션, 지난 라운드 zero-delta 대비 확대 스팟체크**:

- 12개 감시 PR head SHA 대조 → **3개 신규 커밋** 확인 (PR #4/#5/#10 각 1건).
- 신규 PR 검색: `list_pull_requests state=open sort=created desc` 첫 페이지 max=#34 확인 → **신규 PR 0건**.
- **PR #5 `risk_lib/` 파일 트리 실측 fetch** → `risk_lib/capital/` 서브패키지 신설 확인. `capital/rwa_sa.py` (9,437B) 로 이동 확인.
- **PR #5 `capital/rwa_sa.py` L20-70 raw fetch** → `_RW_CORPORATE["B"] = 1.00` at L49 실측. `_RATING_BUCKETS` L20 · sovereign/bank/corporate 3개 테이블 L24-52 문법 확인.
- **PR #5 `risk_lib/systemic.py` L50-70 + L95-125 raw fetch** → SRISK L52 · CoVaR mask L103 실측.
- **PR #5 `risk_lib/frtb.py` L160-185 raw fetch** → BCBS traffic light multiplier table L170-174 실측.
- **PR #10 `minecraft/index.html` 전문 pattern search** → `applyPos`/`blinkTeleport` 0 matches (완전 제거), `WORLD_VER=5` L40, `saveGame` L267, `destroyBlocks` L917, `timeStop` L1532 실측. 파일 총 1687 lines.
- **PR #4 `validation-team-agent/tools/report_pack.py`**: WebFetch 응답이 파일 크기 (~4400 lines) 로 인해 truncate → 정확한 3762/3788/4354 실측 불가. Round 78 커밋 diff 는 A11y aria-label 만 → 3건 tracked LIVE 는 무관 파트, 자동 LIVE 유지.
- Round 78 vs PR #33 리뷰 지시 대조: CHG-0143 예약 사실 확인 → 재사용 P1 finding 도출.

**단독 리뷰어 (에이전트 배정 없음), 저 위험도 (신규 P0 없음)** 라운드로 판단.

---

_본 PR 은 리뷰 보고서 전달용. 머지 금지._
