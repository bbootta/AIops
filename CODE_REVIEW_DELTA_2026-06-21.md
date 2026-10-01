# AIops 저장소 코드 리뷰 — 2026-06-21 델타 업데이트

**기준 리뷰:** `CODE_REVIEW_2026-06-19.md` (PR #13)
**리뷰 대상:** 2026-06-19 이후 업데이트된 PR — #4, #5, #10
**미변경 PR(#2, #3, #6, #7, #8, #9, #11, #12):** 기존 리뷰 결론 그대로 유효
**리뷰 방식:** 변경된 PR 3건 병렬 델타 검증 + commit 단위 비교

---

## TL;DR

| PR | 최근 활동 | 이전 P0/P1 결함 처리 | 결과 |
|---|---|---|---|
| **#5** | 6개 신규 commit (v0.17 → v0.22, 100+ 신규 테스트, XVA·FRTB·Pillar3 모듈) | **0/9 해결** | **여전히 머지 차단** |
| **#4** | 5개 신규 commit (Round 65–69, 리포팅·시각화) | **0/5 Critical 해결** (2건 부분 fix는 새 리스크 도입) | **여전히 변경 요청** |
| **#10** | 4개 신규 commit (허기, 설정, 활 차지샷, 갑옷·상자·바이옴) | **4/11 해결** (중대 1건 fix, 1건 부분) | **여전히 폴리시 필요** |

**가장 중요한 신호:** PR #5에서 6개 commit이 모두 신규 기능 추가로 소비됨. 이전 리뷰가 지적한 **Basel SA RW 표의 B 등급 50ppt 과소 산정** 등 P0 결함은 손도 안 댐. 작성자가 결함 알림을 받지 못했거나 무시 중일 가능성.

---

## PR #5 — Basel III / FSS 리스크 하니스 (`claude/risk-management-agent-harness-B9Kxm`)

### 2026-06-19 이후 commit (6건, 모두 신규 기능)
- `4bf28c2` v0.22.0: Pillar 3 disclosures + 다기간 자본 시뮬레이션
- `4c7ca5a` v0.21.0: Explainability + Action Recommender
- `5383afe` v0.20.0: FRTB IMA + Model Inventory (SR 11-7)
- `2649607` v0.19.0: Risk Committee board pack + 감사 ledger
- `d6bbea3` v0.18.0: XVA suite + 트레이딩북 Greeks + 시나리오 라이브러리
- `41bb76a` v0.17.0: 한국 Big4 + 인뱅3 케이스 스터디

**6개 commit 중 0건이 이전 리뷰에서 지적한 파일을 수정.**

### 이전 결함 상태

| # | 결함 | 상태 | 증거 |
|---|---|---|---|
| 1 | SA 기업/은행 RW 표에 B=150% 누락 (CRE20.41/CRE21.10) | 그대로 | `risk_lib/capital/rwa_sa.py:36` (`_RW_BANK_ECRA "B": 1.00`), `:46` (`_RW_CORPORATE "B": 1.00`) |
| 2 | validator 체크리스트 `pd_floor_3bp` vs 코드 5 bp | 그대로 | `.claude/agents/risk-validator.md:46` (`pd_floor_3bp`); `risk_lib/references.py:97` `PD_FLOOR_BPS = 5` |
| 3 | Past-due RW 무조건 150% (CRE20.45 위반) | 그대로 | `risk_lib/capital/rwa_sa.py:55, :131, :181` |
| 4 | 만기 조정 PD→1 회귀 미테스트 | 그대로 | `tests/test_capital.py:84,89` PD 5점만 (0, 1 미커버) |
| 5 | `fit_lgd_model` floor 예측에서만 적용 | 그대로 | `risk_lib/models/lgd_model.py:80, :100-108` |
| 6 | `compute_rwa_irb` LGD floor 미적용 | 그대로 | `risk_lib/capital/rwa_irb.py:128` (`np.clip(lgd, 0.0, 1.0)`만) |
| 7 | Hosmer-Lemeshow `max(dof-2, 1)` 강제 | 그대로 | `risk_lib/validation/backtest.py:46` |
| 8 | PSI 하한만 clip(상한 없음) | 그대로 | `risk_lib/models/pd_model.py:121-122` |
| 9 | `compute_rwa_sa` CRM 곱셈식 (E* 아님) | 그대로 | `risk_lib/capital/rwa_sa.py:230` `df["rwa"] = df["ead"] * df["rw"] * crm` |

### 권고
**머지 차단 유지.** P0 4건·Major 5건 전부 미수정. P0 #1만으로도 sub-investment-grade 익스포저의 SA RWA 가 50ppt 과소 산정됨 → docstring("Basel III CRE20 (revised SA, 2023)")과 실제 코드 직접 모순. 신규 모듈 6종은 아직 리뷰 미실시 (델타 범위 외).

---

## PR #4 — Validation Team Agent 하니스 (`claude/validation-team-agent-Pw9F5`)

### 2026-06-19 이후 commit (5건, 모두 리포팅/아카이브)
- `546263` Round 69 — `tools/report_pack.py` CSS 디자인 시스템
- `b7796f` Round 68 — `tools/pack_archive.py` 분기 아카이브, FIFO prune
- `ccd99d` Round 67 — `tools/pack_diff.py` 분기 비교 (KPI/heatmap/SHA diff)
- `859c34` Round 66 — `tools/governance_timeseries.py` 합성+감사 패널 트렌드
- `a9492d` Round 65 — `tools/findings_mapping.py` 감사→RF 자동 매핑

### 이전 결함 상태

| # | 결함 | 상태 | 증거 |
|---|---|---|---|
| 1 | PSI 양쪽 인구 모두 1e-4 clip | 그대로 | `tools/metric_psi.py:63-64, :91-92`. docstring 만 "industry practice" 로 보강 |
| 2 | `check_residual_basic` 가 excess kurtosis 를 `kurtosis` 로 명명 | 그대로 | `tools/regression_diagnostics.py:84` |
| 3 | `scan_dataframe` 가 `df.index` 노출 (PII) | 부분 해결 | `middleware/data_safety_guard.py:113` 인덱스 그대로 / 매치 본문은 salted SHA-256 으로 변경(`:115-116`, `_RUN_SALT` 추가 `:39`) — 텍스트 누출은 패치, 인덱스-식별자 누출 잔존 |
| 4 | `run_logger` 회전 race | 그대로 | `middleware/run_logger.py:31-49`. lock/RotatingFileHandler 미도입 |
| 5 | `permission_guard` 카드 정규식 false-positive | 부분 해결(회귀 유발) | `middleware/permission_guard.py:5-7` "audit, not enforce" 명시. 그러나 `_FALLBACK_PATTERNS(:55-69)` 에서 **카드 정규식을 통째로 삭제** — 오탐은 해소되었으나 카드번호 탐지 자체도 사라짐. matrix.json 부재 시 under-detect. |
| 6 | "27 pytest tests" vs 실제 110 파일 | **악화** | tests/ = **134 파일**, round 아티팩트 **45개** (`test_v2_round22..69.py`) |
| 7 | `change_manifest.json` 1940줄 시드 | **악화** | 2016줄 / 134 엔트리 (CHG-0001..CHG-0134) |
| 8 | `handlers/registry.py` 905줄 god-object | 해결(또는 이동) | `handlers/` 디렉토리 사라짐 — R65/R68 commit 메시지가 `src/vta/` 이전 언급. 신규 god-object 여부 미확인 |
| 9 | `leakage_guard` `_after$` 가 합법 feature 차단 | 그대로 | `middleware/leakage_guard.py:19` (`r"_after$"`, `r"_post$"` 그대로) |

### 신규 관찰
- **테스트 파일 sprawl 가속** — 2일 동안 `round65..69.py` 5개 추가, "994 passed" 주장. round-key 컨벤션이 내러티브에 묶여 정리 비용 증가.
- **manifest write 패턴** — 매 round 1 엔트리. 134 엔트리에 도달, 분기별 분리 또는 JSONL 이전 검토 권고.
- **카드 패턴 침묵 삭제** — 결함 #5 의 fix 방식이 "제거"라 `permission_matrix.json` 부재 시 카드 미탐지.

### 권고
**변경 요청 유지.** Critical 5건 중 3건 그대로(#1·#2·#4), 2건 부분 fix 후 새 리스크(#3·#5). 6·7번은 악화, 8번은 미확인. 최근 5개 commit 은 모두 리포트 스타일링 — 메트릭/미들웨어 결함 미손질.

---

## PR #10 — 브라우저 마인크래프트 (`claude/minecraft-game-tqv3ii`)

### 2026-06-19 이후 commit (4건, 모두 신규 기능, 2515줄로 증가)
- `9e2c687` 2026-06-21 — 갑옷, 상자, 사막·눈 바이옴
- `da2afed` 2026-06-20 — 활 차지샷, 음식 추가, pause-time-freeze
- `a89ef43` 2026-06-20 — 인게임 설정 (감도/볼륨/뷰거리/음악)
- `521a4f1` 2026-06-20 — 허기 시스템

### 이전 결함 상태

| # | 결함 | 상태 | 증거 |
|---|---|---|---|
| 1 | `InstancedMesh.dispose()` 오용 (블록 편집마다 호출) | 그대로 | `:654` (편집), `:2285` (차원 전환) |
| 2 | Y 천장 충돌 stick (`prevY` 도 침투 시) | 그대로 | `:1535-1538` 위쪽 분기에 `playerCollides(p)` 재검사 없음. 몹 경로도 `:952-955` 동일 |
| 3 | `inv[type] <= 0` 가 undefined slot 에서 false | 그대로 (잠재) | `:1942`, `:1280`, `:2104`. 현재는 `loadGame:2403` 가 `\| 0` 으로 강제 코어스 — 신규 아이템 타입이 inv 초기화 없이 추가되면 재발 |
| 4 | 프레임당 작은 배열 할당 (GC 압박) | 부분 정정 | `pickMob` 만 공격 시 할당(매프레임 아님). `playerCollides`/`mobCollides` 는 무할당 — 기존 critique 과장 |
| 5 | Creeper 5×5 청크 동기 리빌드 (100ms+ 스파이크) | 그대로 | `:1205` → `destroyBlocks(...,3)` → `:717-731` 7×7×7 + 9 청크 |
| 6 | `makeTexture` 16×16 fillRect × 256 | 그대로 | `:328-340` (ImageData 경로 미도입) |
| 7 | `pickBlock` 가 물 표면에서 안 멈춤 | 그대로 | `:1848` (`isSolid` 만 체크) |
| 8 | `dayTime` 가 오버레이 중에도 진행 | 해결(opt-in) | `:1409` `optFreeze=true` 기본, `:2482` `const active = playing() \|\| !optFreeze` |
| 9 | `saveGame` 조용한 catch | 그대로 | `:536, :540` |
| 10 | `HARDNESS` 가 `LAVA` 누락 | 그대로 (도달 불가) | `:269` |
| 11 | `spawnY()` dead assignment | 해결 | `:1396` 단순 return 으로 정리 |

### 신규 관찰
- 4개 신규 commit 에서 회귀 없음. 신규 기능(허기·설정·차지샷·갑옷·상자·바이옴)은 일관성 있음.
- 마이너: `pickBlock` 이 BOW 선택 + 상자 조준 시 `rightDown:2033-2038` 가 활 차지보다 상자 열기 우선 — 의도 확인 필요.
- 마이너: 상자를 깨면 `chests` 엔트리 삭제되지만 `chestOpen=true`, `chestKey` dangling → UI 가 빈 화면으로 남음 (코스메틱).

### 권고
**폴리시 이터레이션 유지.** 11개 중 4건 해결(부분 포함). 두 진정한 블로커(#1 GPU 메모리 누수, #5 폭발 동기 리빌드)는 그대로. 머지 전 #1·#2·#5·#7 처리 권고.

---

## 미변경 PR — 기존 결론 유효

| PR | 이전 결론 (변경 없음) |
|---|---|
| #2 | **머지 차단** — 존재하지 않는 SDK API (`anthropic.beta_tool`, `messages.tool_runner`), 발명된 모델 ID. import 시점 실패. |
| #3 | **Re-scope** — "docs-only" 표시 정정, PR #4/#5 와 어휘 통합 결정, 0-byte 출력 바이너리 제거. |
| #6 | **Defer/Block** — 트레이딩 결정 LLM 에서 가격·스톱로스 환각 방지 가드 0. |
| #7 | **Close** (PR #8 에 흡수). |
| #8 | **Rebase + revise** — YAML hunk 제거, CHG-0130 부터 재할당. |
| #9 | **Iterate** — Handoff contract YAML 블록 구조화, G2/G3 ownership 명시. |
| #11/#12 | 1건만 머지, 1건 close. |

---

## 가장 시급한 단일 액션

**PR #5 의 `risk_lib/capital/rwa_sa.py:36, :46` — B 등급 RW 를 1.00 → 1.50 으로 수정.** 한 줄 변경. CRE20.41/CRE21.10 명시. 이 fix 없이는 어떠한 sub-investment-grade 익스포저 시뮬레이션도 자본을 과소 산정함. 이전 리뷰에서 명시했음에도 6개 commit 동안 미수정 — 작성자에게 별도 통보 권고.

---

_본 리뷰는 2026-06-19 `CODE_REVIEW_2026-06-19.md` 의 결함 인벤토리를 기준으로 변경 commit 만 추적함. 전체 재리뷰는 변경된 코드량 대비 ROI 낮음 — 변경된 PR 의 신규 모듈 (PR #5 의 XVA/FRTB/Pillar3 등 6종) 은 별도 리뷰 사이클 권고._
