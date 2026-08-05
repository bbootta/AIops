# HANDOVER.md

계정·세션이 바뀌어도 작업을 이어갈 수 있도록 정리한 인수인계 문서.

- **작성 기준일**: 2026-08-05
- **기준 커밋**: `main` = `281d601` (2026-07-24)
- **저장소**: https://github.com/bbootta/AIops

---

## 0. 30초 요약

- `main` 브랜치에는 **실행 가능한 코드가 없다.** `CLAUDE.md`, `.claude/settings.json`, `.gitkeep` 세 파일이 전부다.
- 실제 작업물은 **전부 미머지 feature 브랜치**에 있다. 열린 PR **54건**(프로젝트 PR 15건 + `claude/stoic-ride-*` 39건), 머지된 PR은 **3건**뿐이다 — `main`으로 머지된 것은 #1, #42 둘뿐이고, #44는 `main`이 아니라 Pw9F5 브랜치로 머지됐다.
- 저장소는 사실상 **"한 브랜치 = 한 프로젝트" 형태의 에이전트 하네스/프로토타입 샌드박스**로 운영되고 있다.
- 2026-05-19경부터 **매일 1회 전체 저장소 코드 리뷰 PR**(`claude/stoic-ride-*`)이 자동 생성된다. 최신은 PR #56(36주차).
- 가장 큰 미해결 이슈는 **코드가 아니라 프로세스**다 — 리뷰에서 지적된 tracked LIVE 69건이 최장 19주째 미시정 상태다.

---

## 1. 프로젝트 개요와 현재 목표

### 성격

`AIops`는 단일 제품 저장소가 아니라, **에이전트 하네스와 앱 프로토타입을 여러 개 병렬로 실험하는 저장소**다. 도메인이 서로 겹치지 않는 작업들이 브랜치 단위로 독립 존재한다.

크게 세 갈래:

| 갈래 | 내용 | 대표 브랜치 |
|---|---|---|
| **은행 리스크/검증 하네스** (주력) | Basel III·금감원 기준 리스크 산출, 모형 적합성 검증, 리서치 | `B9Kxm`, `Pw9F5`, `qytpk`, `1v9b78` |
| **앱·게임 프로토타입** | 웹/데스크톱 앱 실험 | `i79qef`(네일), `khpuk3`(3D 슈팅), `tqv3ii`(마인크래프트) |
| **거버넌스·리뷰 자동화** | 일일 전체 저장소 코드 리뷰, ISO 42001 준수 문서 | `stoic-ride-*`, `exq9qe` |

### 현재 목표 (관측된 우선순위)

1. **주력 하네스 2종 완성** — `risk-management-agent-harness-B9Kxm`(PR #5)과 `validation-team-agent-Pw9F5`(PR #4). 두 브랜치가 전체 커밋의 대부분을 차지한다(각 160 / 120 커밋).
2. **일일 리뷰에서 누적된 결함 소화** — tracked LIVE 69건(P0×8 · P1×12 · P2×22 · P3×27).
3. **머지 전략 부재 해소** — 54건이 열린 채 쌓여 있고 `main`은 3개월째 사실상 비어 있다. 이건 아직 아무도 결정하지 않은 문제다(§6 참조).

---

## 2. 폴더 구조와 주요 모듈 요약

### 2.1 `main` 브랜치 (현 체크아웃)

```
.
├── .claude/settings.json   # openai/codex-plugin-cc 마켓플레이스 등록 + codex 플러그인 활성화
├── .gitkeep                # 저장소 초기화용 빈 파일 (제거 금지, 히스토리상 유일한 최초 파일)
├── CLAUDE.md               # LLM 코딩 행동 지침 (프로젝트 지침 겸용)
└── HANDOVER.md             # 본 문서
```

`main`에는 소스 코드, 테스트, CI 워크플로가 **없다**. 빌드·테스트할 대상이 없으므로 `main`만 클론하면 실행할 것이 없다.

### 2.2 브랜치 = 프로젝트 목록

| 브랜치 | PR | 내용 | 파일 수 | 최근 커밋 | main 대비 |
|---|---|---|---|---|---|
| `claude/risk-management-agent-harness-B9Kxm` | #5 | **[주력]** Basel III / FSS 리스크관리 하네스 (Python `risk_lib` + 13 서브에이전트) | 306 | 2026-08-03 | +160 |
| `claude/validation-team-agent-Pw9F5` | #4 | **[주력]** 모형 적합성검증 팀에이전트 하네스 (AHE 기반, CI 있음) | 362 | 2026-08-02 | +120 |
| `claude/minecraft-game-tqv3ii` | #10 | 브라우저 마인크래프트 클론 | — | 2026-07-31 | +53 |
| `claude/3d-shooting-game-khpuk3` | #38 | 영화 '호프' 기반 3D 슈팅 (Electron `hope-shooter` + UE 프로젝트 `hope-ue`) | 51 | 2026-08-02 | +13 |
| `claude/nail-simulation-program-i79qef` | #46 | 네일샵 시뮬레이터 (빌드리스 웹앱) | 14 | 2026-07-27 | +11 |
| `claude/quant-validation-agent-qytpk` | (없음) | 계량 검증 에이전트 문서·하네스 패키지 | 201 | 2026-06-06 | +20 |
| `claude/stock-trading-agent-harness-ZuSJc` | #2 | 주식 트레이딩 팀에이전트 (안전 게이트 포함) | 15 | 2026-06-15 | +8 |
| `claude/global-harness-enhancement-1v9b78` | #9 | 리스크 리서치 하네스 고도화 (품질 게이트 G1–G5) | 22 | 2026-06-15 | +7 |
| `claude/iso-42001-agent-compliance-exq9qe` | #30 | ISO/IEC 42001 에이전트 준수 요구사항 문서 | 4 | 2026-07-13 | +1 |
| `claude/mecha-chameleon-game-xyiguj` | #32 | 메카 카멜레온 게임 | — | 2026-07-14 | +1 |
| `codex/*` (4개) | #3,#6,#7,#8 | Codex 세션이 만든 검증/트레이딩 패키지 및 CI 수정 | — | ~2026-06 | — |
| `claude/stoic-ride-*` (30+개) | #13~#56 | 일일 전체 저장소 코드 리뷰 보고서 (`CODE_REVIEW_YYYY-MM-DD.md` 1파일씩) | 1 | 매일 | +1 |

### 2.3 주력 모듈 상세

#### `risk_lib` — B9Kxm 브랜치

Python 패키지(`pyproject.toml`, `requires-python >=3.10`, numpy/pandas/scipy/scikit-learn).

```
risk_lib/
├── capital/      rwa_sa.py(CRE20 표준방법) rwa_irb.py(CRE31) bis.py crm.py
│                 market_risk.py(MAR40) op_risk.py(OPE25) output_floor.py(72.5%) leverage.py
├── models/       pd_model.py(로지스틱 PD + Gini/KS/PSI) lgd_model.py rating.py(17등급)
├── provisioning/ ecl.py (IFRS9 3-stage)
├── monitoring/   delinquency.py(DPD 버킷·전이행렬) recovery.py
├── limits/       limit_engine.py concentration.py(HHI)
├── performance/  rapm.py (RAROC·경제자본)
├── stress/       scenario.py axes.py(충격 축 14) multi_axis.py trace.py
├── validation/   consistency.py(2선 정합성 21종) backtest.py independent.py(3선 게이트, fail-closed)
├── datamodel/    spec.py catalog.py(81테이블/594컬럼) materialize.py
└── alm/          balance_sheet.py irrbb.py lcr.py
.claude/agents/   13개 서브에이전트 (risk-orchestrator가 코디네이터, risk-validator가 필수 마지막 단계)
tests/            pytest 1,009건
```

#### `validation-team-agent` — Pw9F5 브랜치

```
validation-team-agent/
├── harness/     system_prompt.md, threshold_policy.{md,json,schema.json}, change_manifest.json
├── skills/      도메인별 절차 지식
├── subagents/   서브에이전트 역할 정의
├── tools/       검증용 Python 함수
├── middleware/  실행 전후 통제 미들웨어
├── tests/       pytest
├── memory/      반복 finding·모형별 노트·알려진 한계
└── docs/        운영 모델·위험통제·HITL 정책
.github/workflows/validation-team-agent-ci.yml   # 유일한 CI. Python 3.10/3.11 매트릭스
docs/independent_validation/                     # B9Kxm과 주고받는 3선 검증 요청/의견/승인 파일
```

> **연결점**: B9Kxm의 `risk_lib/validation/independent.py`가 Pw9F5로 상시 독립검증을 위임한다. 두 브랜치는 `docs/independent_validation/RUN-*.json` 파일 규약으로 느슨하게 연결돼 있다. 한쪽만 보고 판단하면 안 된다.

---

## 3. 지금까지의 주요 변경사항과 그 이유

### 3.1 `main` 커밋 전체 (9개)

| 커밋 | 날짜 | 내용 | 이유 |
|---|---|---|---|
| `e7dfe8f` | 2026-05-03 | 저장소 초기화 (`.gitkeep`) | 빈 저장소 생성 |
| `6871d69` | 2026-05-05 | CLAUDE.md 최초 작성 | 저장소가 비어 있다는 사실 자체를 문서화, 코드 유입 후 `/init` 재실행 안내 |
| `d8d14d0` | 2026-05-05 | CLAUDE.md를 행동 지침으로 교체 | 빈 저장소에 구조 설명은 무의미 → LLM 코딩 실수 감소용 지침이 더 유용하다고 판단 |
| `cad0f4a` | 2026-05-06 | PR #1 머지 | 위 두 커밋 반영 |
| `401c40f` | 2026-05-17 | 리스크 리서치 에이전트 하네스 추가 (8 에이전트 + harness/ + templates/ + reports/) | Basel·감독규정·논문·뉴스를 다루는 전문 리서치 팀 구성 |
| `143e6e9` | 2026-05-17 | 하네스를 `codex/` 하위로 이동 | Codex 도구용 레이아웃으로 분리 |
| `d4b32e6` | 2026-05-17 | `.claude/agents/` → `agents/`, `AGENTS.md` 추가 | Claude 전용 경로 의존 제거, 도구 중립화 |
| `ebb9e8a` | 2026-05-17 | `codex/` 경로 전체 삭제 (-1,905줄) | `main`에서 Codex 경로를 걷어냄. 하네스는 `1v9b78` 브랜치에서 계속 발전 |
| `281d601` | 2026-07-24 | codex 플러그인을 프로젝트 스코프로 설치 (PR #42) | 이후 세션에서도 저장소가 플러그인을 들고 있도록 `.claude/settings.json`에 고정 |

**요점**: `main`의 역사는 "하네스를 올렸다가 다시 내린" 것이다. 그래서 지금 비어 있다. 하네스 자체는 사라지지 않았고 `1v9b78` 브랜치에 살아 있다.

### 3.2 브랜치 쪽 흐름 (요약)

- **2026-05**: 리서치 하네스(#9), 트레이딩 하네스(#2), 검증팀 하네스(#4), 리스크 하네스(#5)가 연달아 개설.
- **2026-06**: 게임 프로토타입(#10) 합류. **2026-06-19 PR #13부터 전체 저장소 코드 리뷰 시리즈 시작.**
- **2026-07**: 3D 슈팅(#38), 네일 시뮬레이터(#46) 추가. 리뷰 시리즈는 "신규 결함 발견"에서 **"미시정 항목 추적"** 으로 성격이 바뀜. 07-25 **PR #44가 Pw9F5 브랜치로 머지**(저장소 유일의 feature 브랜치 머지) — ruff 규칙셋 고정으로 CI 복구(§5.2).
- **2026-08**: B9Kxm 대확장(35주차, 9커밋 +5,312 LOC) 후 활동 정지. 36주차는 zero-delta.

---

## 4. 진행 중 작업의 마지막 상태와 바로 다음 단계

### 4.1 마지막 상태 (2026-08-05 기준)

**최신 리뷰: PR #56 — 36주차 (2026-08-04 21:08 UTC)**

- **zero-delta 라운드**: 감시 대상 6개(B9Kxm / Pw9F5 / PR #38 / PR #10 / PR #46 / main) 전부 24h 무커밋. 신규 P0/P1/P2/P3 = 0/0/0/0.
- **tracked LIVE 69건 유지** (P0×8 · P1×12 · P2×22 · P3×27).
- **35주차 즉시 항목 8건 전건 미이행.**
- **최장 방치 기록**: B9Kxm Basel B RW/SRISK/CoVaR (P0) — **19주**. PR #10 벽투과 (P1) — **14주**. PR #46 dead-store — **9주 확정**.
- **B9Kxm과 Pw9F5가 동시에 멈춘 것은 25주차 이후 처음.** 37주차에도 재개가 없으면 dormant 판정 대상.

**이 세션 브랜치 (`claude/project-handover-docs-pyic2r`)**: `main`과 동일한 지점에서 시작해 본 문서와 CLAUDE.md 갱신만 담고 있다.

### 4.2 바로 다음 단계

우선순위 순. 1~3은 36주차 리뷰가 지정한 "37주차 즉시 항목"을 그대로 승계한 것이다.

1. **B9Kxm P1 4건 수정** — 가장 실질적인 결함들이다.
   - 9300 borrower 방향 오류
   - fund SA-CCR PFE 4.4배 과소 산출
   - NaN이 문자열 `"nan"` 버킷으로 새는 문제
   - SEC-SA `K_A` NaN 무방어
2. **B9Kxm P2×6 + P3×4** — 합쳐서 약 40줄. 1번과 같은 브랜치에서 한 번에 처리하는 게 효율적이다.
3. **PR #46 dead-store 결정** — 9주 = 60일 이상 미시정. 리뷰는 "자기수정 사이클로는 도달 불가, 외부 채널 필요"로 판정했다. **수정하거나, PR을 닫거나, 의도된 코드라면 NOT-A-DEFECT로 종결**하고 추적에서 빼야 한다. 방치는 선택지가 아니다.
4. **Pw9F5 재개 시** — `reg_rules.py` P3×2 및 `conditional_approval.json` P1 처리.
5. **B9Kxm 19주 tracked P0×3** (Basel B RW / SRISK / CoVaR) — 가장 오래된 항목. 난이도가 높아 계속 밀린 것으로 보이므로, 별도 세션에서 집중해서 다루는 편이 낫다.
6. **머지 전략 결정** (§6.2) — 위 전부와 독립적으로, 사용자 판단이 필요한 항목.

> 작업 시작 전에 최신 리뷰 PR의 `CODE_REVIEW_YYYY-MM-DD.md`(218줄)를 먼저 읽을 것. 각 항목의 파일·라인·재현 절차가 거기 있다. 본 문서에는 요약만 담았다.

---

## 5. 실행·테스트 방법

### 5.1 `main`

```bash
# 실행·빌드·테스트 대상 없음. 아래 명령으로 확인만 가능.
git ls-files          # → .claude/settings.json, .gitkeep, CLAUDE.md, HANDOVER.md
```

### 5.2 브랜치별

작업할 브랜치를 먼저 체크아웃한다.

```bash
git fetch origin <브랜치명>
git checkout -b <브랜치명> origin/<브랜치명>
```

#### risk_lib (B9Kxm)

```bash
pip install -e .
pytest -q                                          # 1,009건

python -m risk_lib.cli run --report report.md      # 합성 데이터 전체 파이프라인
python -m risk_lib.cli run --data book.csv --seed 7
python examples/run_end_to_end.py                  # 단계별 데모
python -m risk_lib.cli reg-report --out 업무보고서.xlsx --asof 2026-06-30 --institution "○○은행"
python -m risk_lib.cli ui-studio --out studio.html --asof 2026-06-30
python -m risk_lib.cli validation-request --asof 2026-06-30
```

> **종료코드 게이트**: `run`은 검증 FAIL이 하나라도 있으면 1을 반환한다. `validation-request`는 게이트가 `적합`이 아니면 1, `reg-report`는 서식 자체대사 실패 시 1을 반환한다. **CI나 스크립트에서 이 종료코드를 무시하면 게이트가 무력화된다.**

#### validation-team-agent (Pw9F5)

```bash
cd validation-team-agent
pip install -r requirements.txt
pytest -q
```

CI: `.github/workflows/validation-team-agent-ci.yml` (Python 3.10 / 3.11 매트릭스). 트리거 `paths`에 **부정 패턴(`!`)이 들어 있다** — GitHub Actions가 같은 트리거에서 `paths`와 `paths-ignore` 병용을 막기 때문이다(PR #8). 이 필터를 건드릴 때는 `startup_failure`가 나기 쉬우니 주의.

`pyproject.toml`의 `[tool.ruff.lint]`는 `extend-select`가 아니라 **`select = ["E4", "E7", "E9", "F", "E741"]`로 명시 고정**돼 있다(PR #44). `requirements.txt`의 `ruff>=0.5`에 상한이 없어 CI가 ruff 0.16.0을 설치했고, 0.16.0에서 기본 규칙셋이 확장되면서 소스 변경 없이 lint 284건이 터졌기 때문이다. `requirements.txt`의 `mypy>=1.10`도 같은 구조로 상한이 없다 — 언젠가 같은 방식으로 깨질 수 있다.

#### 네일 시뮬레이터 (i79qef)

```bash
xdg-open index.html               # 빌드 불필요
python3 -m http.server 8000       # 또는 로컬 서버 → http://localhost:8000
python3 build-single-file.py      # dist/nail-simulator.html 단일 파일 빌드
```

#### 호프 3D 슈팅 (khpuk3)

```bash
cd hope-shooter
npm install
npm start          # 빌드 + Electron 실행
npm run dev        # 브라우저 확인 (http://localhost:8080)
npm run dist       # 배포 패키지 (electron-builder)
```

`hope-ue/`는 별도 Unreal Engine 프로젝트(`HopeLastStreet.uproject`)로 UE 에디터가 필요하다.

#### 주식 트레이딩 하네스 (ZuSJc)

```bash
pip install -r requirements.txt
python -m stock_trading.main '<시나리오>'              # 리서치 전용 (기본값)
python -m stock_trading.main --execute '<시나리오>'    # Trader 도구 활성화
pytest stock_trading/tests/test_safety_gates.py
```

> **안전 게이트**: `--execute`를 줘도 `place_order`는 no-op이다. 실제 주문은 환경변수 `STOCK_TRADING_LIVE=1`이 함께 설정돼야만 동작한다. **이 이중 게이트를 임의로 제거하지 말 것.**

---

## 6. 알려진 이슈, 보류 사항, 건드리지 말아야 할 부분

### 6.1 알려진 이슈

| 이슈 | 상태 |
|---|---|
| tracked LIVE 69건 (P0×8 · P1×12 · P2×22 · P3×27) | 미시정. 상세는 최신 `CODE_REVIEW_*.md` §8 |
| B9Kxm Basel B RW / SRISK / CoVaR (P0×3) | **19주** 방치 — 최장 기록 |
| PR #10 warden 벽투과 (P1) | **14주** 방치 |
| PR #46 dead-store (blob `0e0288c9…`) | **9주 확정**. 외부 판단 필요 |
| B9Kxm 신규 P1×4 (9300 방향 / SA-CCR PFE 4.4× / NaN 버킷 / SEC-SA K_A) | 35주차 발견, 미착수 |
| B9Kxm·Pw9F5 동시 활동 정지 | 37주차까지 재개 없으면 dormant 판정 |
| 리뷰 warden 프로세스가 강제력 없음 | 30주차에 "저자 = 시정 주체" 가정 미성립 판정. 5주째 무액션 |

### 6.2 보류 사항 (사용자 결정 필요)

- **머지 전략**: 열린 PR 54건, `main` 머지 이력 2건. `main`을 계속 빈 허브로 둘 것인지, 완성된 하네스를 머지할 것인지 결정된 바 없다. **임의로 머지하지 말 것.**
- **PR 정리**: 2026-06 이후 커밋이 없는 브랜치가 다수(`ZuSJc`, `1v9b78`, `qytpk`, `codex/*`). 종결/보류 판단이 필요하다.
- **`qytpk` 브랜치**에는 열린 PR이 없다(파일 201개). 의도적인지 확인 필요.
- **일일 리뷰 자동화 지속 여부**: 리뷰는 계속 쌓이는데 시정이 따라가지 못하고 있다. 리뷰 주기를 늦추거나, 시정 세션을 별도로 돌리는 편이 나을 수 있다.

### 6.3 건드리지 말아야 할 부분

1. **`claude/stoic-ride-*` PR은 머지하지 않는다.** 본문에 "머지 금지 — 리뷰 보고서 전달용 draft"로 명시돼 있다. 브랜치 삭제도 하지 말 것 — 리뷰 간 delta 계산의 기준점이다.
2. **`.gitkeep`을 지우지 않는다.** 최초 커밋의 유일한 파일이고, 여러 브랜치가 이 파일을 공통 조상으로 갖는다.
3. **`.claude/settings.json`의 codex 플러그인 설정.** PR #42로 의도적으로 고정한 것이다. 다만 PR #43이 이 설정을 **공급망 노출(P1)** 로 지적했으니, 손볼 때는 그 지적을 먼저 읽을 것.
4. **다른 브랜치의 파일을 `main`으로 끌어오지 않는다.** `main`이 비어 있는 것은 사고가 아니라 `ebb9e8a`의 의도적 결과다.
5. **안전 게이트 3종**: `risk_lib` CLI 종료코드 게이트, `independent.py`의 fail-closed 위임, `stock_trading`의 이중 실행 게이트. 테스트를 통과시키려고 이것들을 완화하지 말 것.
6. **Pw9F5 CI의 `paths` 부정 패턴** — PR #7/#8에서 두 번 고친 부분이다. 이유는 §5.2 참조.
7. **Pw9F5 `pyproject.toml`의 ruff `select`** — PR #44에서 `extend-select`로 인한 CI 실패를 고치며 명시 고정한 것이다. `extend-select`로 되돌리면 ruff 버전업 시 CI가 다시 깨진다. 규칙셋을 넓히는 것 자체는 별도 판단 사항으로 남아 있다.
8. **본인이 만들지 않은 P0/P1 지적을 "재분류"로 처리하지 않는다.** 리뷰 시리즈에는 이미 재분류·정정 이력이 있으므로, 판단이 바뀌면 근거를 남겨야 한다.

---

## 7. 인수인계 체크리스트

새 세션·새 계정에서 시작할 때:

1. `git log --oneline -10` — `main`이 여전히 `281d601`인지 확인.
2. 최신 `claude/stoic-ride-*` PR의 `CODE_REVIEW_*.md`를 읽는다 — 현재 결함 목록의 단일 출처(single source of truth)다.
3. 작업할 브랜치를 체크아웃한다(`main`에서 작업 시작하지 말 것).
4. §4.2의 다음 단계 목록에서 하나를 골라 착수한다.
5. 본 문서에서 바뀐 사실이 있으면 갱신한다.
