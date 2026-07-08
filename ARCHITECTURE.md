# risk_lib 아키텍처

한국 은행 리스크관리 에이전트 하니스. 합성 포트폴리오 생성 → 전 부문 리스크 산출
(`run_pipeline`) → 경영진/실무진 HTML 보고서 패키지 산출까지 단방향 파이프라인이다.

## 레이어링 (위 → 아래로만 의존)

```
CLI / Agents            cli.py, .claude/agents/*
  ↓
Reports (표현 계층)      html_report(빌드 오케스트레이터), report_chrome(CSS/NAV/헬퍼),
                        ops_pages/ (core_* 핵심 + 도메인별 심층 페이지), html_exec,
                        board_pack, printable, localization, report(markdown),
                        page_registry
  ↓
Orchestration           pipeline.run_pipeline → PipelineResult
  ↓
Domain engines          capital/, provisioning/, models/, stress/, alm/, icaap/,
                        limits/, monitoring/, performance/, validation/,
                        + 단일 모듈 도메인 (xva, frtb, cecl, systemic, intraday,
                        climate, ccr, op_loss, capital_simulation, ...)
  ↓
Foundations             data_gen, references, repro, abbreviations, viz, viz_advanced
```

규칙:
- **아래 계층은 위 계층을 import하지 않는다.** 도메인 엔진은 보고서/파이프라인을 모른다.
- **모든 수치는 PipelineResult를 통해서만 보고서로 전달된다.** 보고서 빌더가 도메인
  엔진을 직접 호출해 재계산하지 않는다 (재현성·감사추적을 위해).
- **재현성**: `run_pipeline(seed=, asof=)` 두 입력이 같으면 모든 산출값이 동일해야
  한다. 벽시계(`date.today()`)를 새로 참조하는 코드를 도메인/보고서에 넣지 말 것 —
  기준일은 `asof`로 주입한다. (repro.py: SHA-256 포트폴리오 지문, RunManifest)
- **참조·기준값은 references.py에만** (BIS 최저비율, 버퍼, 인용 조항). 매직넘버 금지.
- **약어 사전은 abbreviations.py 단일 소스** — 경영진 보고서의 약어 주석은 여기서만
  나온다. 중복 키는 tests/test_architecture.py의 AST 가드가 차단한다.

## 보고서 페이지 등록 (page_registry)

ops 심층 페이지(66개)의 단일 소스는 `page_registry.PAGES` (PageSpec 튜플)이다.
NAV·빌더 해석(`build_report_set`)이 모두 여기서 파생된다.

**새 페이지 추가 절차**: ① `risk_lib/ops_pages/<도메인>.py`에
`page_xxx(result) -> str` 빌더 작성 (chrome은 report_chrome에서 import)
② `page_registry.PAGES`에 PageSpec 한 줄 추가. 끝. 빌더는 (module, func)
문자열로 등록되고 build 시점에 importlib으로 해석된다.

ops_pages 모듈: core_overview(요약/검증/결재) · core_credit(PD~RAPM) ·
core_capital_alm(RWA/BIS/스트레스/ICAAP/ALM) — 핵심 페이지 0~12 · 27 · 28 · 52,
그리고 심층: credit(신용/충당금) · capital_stress(자본/스트레스) ·
market_trading(시장/트레이딩) · concentration_limits(집중/한도) ·
performance(성과) · nonfinancial(비재무) · governance(거버넌스/공시).

의존 방향: ops_pages/* → report_chrome → page_registry (무순환).
html_report는 build_report_set/build_full_report_package만 가지며, 기존 소비자
(board_pack, printable, localization, html_exec, systemic, case_studies)를 위해
chrome 이름을 re-export한다.

- `needs_portfolio=True`: 빌더 시그니처가 `(result, portfolio)`이며 portfolio 미제공
  시 해당 페이지는 생략된다 (20 Pillar3 / 24 Vintage / 25 DQ).
- `in_nav=False`: ALM 서브탭(11a/b/c)처럼 메인 NAV에 노출하지 않는 페이지.

## 산출물 패키지 (`build_full_report_package`)

```
out/
├── executive.html      # 경영진 요약 (html_exec) — 약어 주석 필수
├── printable.html      # 브라우저 Print-to-PDF 용 (printable.py; OS 한글 폰트)
├── board_pack.html     # 리스크위원회 12p A4 (board_pack.py)
├── board_pack_en.html  # 영문판 (localization.py)
├── audit_ledger.json   # 수치별 산출 근거 원장 (audit_trail.py, BCBS 239)
├── manifest.json       # RunManifest (repro.py)
└── ops/                # index + 01..62 실무 심층 페이지 (page_registry 주도)
```

## 테스트

- `tests/conftest.py`: session-scoped `portfolio`/`result` 공유 픽스처
  (seed=42, asof=2026-06-11 고정). **테스트 파일에 자체 파이프라인 픽스처를 만들지
  말 것** — 전체 스위트가 파이프라인을 한 번만 돌린다.
- `tests/test_pipeline_e2e.py`: 골든 수치 (rel 1e-9). 의도적 수치 변경 시 골든을
  재고정하고 커밋 메시지에 근거(규정 조항)를 남긴다.
- `tests/test_architecture.py`: 구조 불변식 (약어 중복 키, page_registry 정합성).

## 알려진 부채 / 주의

- `pillar3.py`는 legacy (ops 20 요약 전용). 신규 공시 템플릿은
  `pillar3_disclosures.py`(13종, ops 59)에 추가.
- `comparison.py`(2시점 비교)와 `timeseries_ledger.py`(다기간 원장)는 역할이 겹침 —
  신규 시계열 기능은 timeseries_ledger에.
