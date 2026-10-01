# 전체 저장소 코드 리뷰 — 2026-07-24 (delta round)

**Baseline:** PR #41 (2026-07-23 21:10 UTC, 25주차) — 감시 13개 PR 전건 zero-delta, tracked LIVE ≈ 30건.
**이번 델타 창:** 2026-07-23 21:10 UTC ~ 2026-07-24 (약 24h).

## 델타 요약

| 항목 | 값 |
|---|---|
| main 신규 커밋 | **1건** — `281d601` (PR #42) |
| 신규 PR | **1건** — #42 (open→merge 3분, 리뷰 0건) |
| 감시 13개 PR head 변화 | **0건** (전건 zero-delta 2일 연속) |
| 신규 findings | **P1×1, P3×2** (전건 PR #42 대상) |
| Tracked LIVE | ≈ 30건 (전건 유지) |

---

## 신규 finding — 전건 `.claude/settings.json` (PR #42 / commit `281d601`)

### [P1-NEW] 프로젝트-스코프 플러그인이 커밋 SHA에 핀되지 않음 — 공급망 노출

**위치:** `.claude/settings.json:2-8`
```json
"extraKnownMarketplaces": {
  "openai-codex": {
    "source": { "source": "github", "repo": "openai/codex-plugin-cc" }
  }
}
```

**결함:** `source` 스펙에 `commit`/`ref`/`tag` 필드가 없다. Claude Code 는 세션 시작 시 `openai/codex-plugin-cc` 의 **기본 브랜치 현재 HEAD** 로 플러그인을 fetch 한다. 동시에 `enabledPlugins."codex@openai-codex": true` 가 프로젝트 스코프로 설정되어 있으므로 이 저장소를 여는 모든 세션에서 사용자 승인 프롬프트 없이 활성화된다.

**실패 시나리오:** PR 설명에 "3 harness-only hooks" 를 제공한다고 명시되어 있다. hooks 는 임의 셸 명령을 실행한다. 향후 `openai/codex-plugin-cc` 기본 브랜치에 커밋(정당한 릴리즈든 계정 침해든)이 들어가면 다음번 이 저장소를 여는 세션에서 그 코드가 자동으로 실행된다. 저장소 소유자는 사이에 아무런 조치를 하지 않았음에도 영향 범위에 들어간다. 이는 SLSA/OWASP 가 지목하는 전형적 종속성 자동-업데이트 공급망 취약점 패턴이다.

**권고 fix (1줄):**
```json
"source": { "source": "github", "repo": "openai/codex-plugin-cc", "commit": "<PR #42 install 시점 검증한 SHA>" }
```
또는 릴리즈 태그 사용. 업데이트는 SHA 변경을 명시적 커밋으로 남기고 리뷰를 거친다.

**보조 조치:** `enabledPlugins` 를 프로젝트 스코프에서 제거하고 사용자 스코프에서 opt-in 하도록 이동 — 저장소 열람 자체가 코드 실행 승인이 되지 않도록.

---

### [P3-NEW] `.claude/` 변경에 대한 리뷰 우회

**증거:**
- PR #42 open: 2026-07-24 05:52 UTC
- PR #42 merge: 2026-07-24 05:55 UTC (**3분 후, 리뷰 0건**)
- `get_reviews` 결과: `[]`
- 25주 연속 유지되어 온 **주간 리뷰 사이클을 우회**해서 main 에 진입 — 다음 26주차 리뷰(예상 2026-07-30)까지 6일간 미검토 상태로 방치될 뻔했다.

`.claude/settings.json` 은 세션 실행 환경 자체를 정의하므로 코드보다 오히려 더 엄격한 리뷰가 필요한 파일이다. 위 P1 finding 이 3분 셀프-머지가 아니었다면 리뷰 단계에서 걸렸을 사안.

**권고:** `.claude/**` 및 `**/settings.json` 경로에 대해 CODEOWNERS + branch protection 의 required review 규칙 적용.

---

### [P3-NEW] `.claude/settings.json` 스키마 검증 CI 부재

향후 이 파일이 수정될 때 오탈자 하나로 세션 로드가 실패할 수 있다. PR #42 처럼 3분 머지 관행이 유지된다면 특히 위험. 경량 JSON 스키마 체크 워크플로 추가 권고. (P3 — 낮음, 예방 목적)

---

## Tracked LIVE — PR #41 대비 변경 없음

지난 라운드 지시 13건 중 이행 0건 (감시 PR 전건 무커밋). PR #41 §"다음 라운드 (26주차) 권고" 항목 전건이 그대로 유지된다. 요약:

- **PR #5** Basel corporate B RW `1.00→1.50`, SRISK `(1-k)`, CoVaR own-loss mask — **11주 방치**
- **PR #4** CHG-0143 재할당 + ERRATA-2026-07-14 — **8주 방치**
- **PR #10** warden 벽투과 (`minecraft/index.html:2014-2026` LOS), `damage()` 주석 — **6주 방치**
- **PR #38** `removeEnemy` dispose (크리처·particle·tracer·wisp 4경로), 벽투과 사격, GPU dispose 3개소, window blur, Reflector textureWidth — **2~4주 방치**
- **PR #22, PR #2, PR #7, PR #8** — close/rebase 지시 미이행 (9~16주)

## 시사점

1. **PR #42 는 25주 리뷰 사이클의 첫 우회 사례**. `.claude/` 하위가 리뷰 게이트 밖에 있음이 드러남 — 프로세스 결함이 실제 P1 취약점을 통과시켰다.
2. **fix 채널 26일 연속 정지** (마지막 감시 PR 커밋 = PR #38 `3ffdf95`, 2026-07-22 12:39 UTC). PR #41 이 제안한 "close-only 라운드" 전환이 지연될수록 backlog 은 계속 증가.
3. **신규 P1 이 발생했으므로 26주차는 close-only 불가** — P1 fix 를 최우선 처리 후 close-only 로 복귀.

## 다음 라운드 (26주차) 권고 — 우선순위 재정렬

1. **[신규 P1]** `.claude/settings.json` 에 commit SHA 핀 (1줄 수정). **최우선**.
2. **[신규 P3]** `.claude/` CODEOWNERS + branch protection.
3. PR #41 §권고 1~13번 유지 (특히 PR #5 Basel 11주, PR #10 warden 6주).
