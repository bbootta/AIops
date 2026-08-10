# risk_lib 아키텍처

한국 은행 리스크관리 에이전트 하니스. 합성 포트폴리오 생성 → 전 부문 리스크 산출
(`run_pipeline`) → 경영진/실무진 HTML 보고서 패키지 산출까지 단방향 파이프라인이다.

에이전트 팀(.claude/agents)의 거버넌스·역할·검증/심사 절차는 ISO/IEC 42001 기준의
**AIMS_POLICY.md**를 따른다 (인적 감독, 재현성, 부적합·시정조치, 내부심사).

## 레이어링 (위 → 아래로만 의존)

```
CLI / Agents            cli.py, .claude/agents/*
  ↓
Delivery (산출물)        ui_studio/ (에이전틱 UI — 조립·조회·레이아웃·렌더),
                        regulatory/ (금감원 업무보고서 서식 34장·엑셀),
                        deliverables(패키징·ZIP·매니페스트)
  ↓
Reports (표현 계층)      html_report(빌드 오케스트레이터), report_chrome(CSS/NAV/헬퍼),
                        ops_pages/ (core_* 핵심 + 도메인별 심층 페이지), html_exec,
                        board_pack, printable, localization, report(markdown),
                        page_registry
  ↓
Canonical data model    datamodel/ (spec·catalog·decompose·materialize·
                        materialize_detail·materialize_ledgers) — 261 테이블 / 2708 컬럼
  ↓
Orchestration           pipeline.run_pipeline → PipelineResult
  ↓
Domain engines          capital/, provisioning/, models/, stress/, alm/, icaap/,
                        limits/, monitoring/, performance/, validation/,
                        prudential/ (재무제표·국내유동성·자산운용한도·
                        경영실태평가·적기시정조치),
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

## 정규 데이터모델 (datamodel/)

`catalog.ALL_TABLES`가 단일 소스다 — 테이블 261장 / 컬럼 2708개. 각 컬럼은 타입·
단위·허용값·범위·규정 근거를 스펙으로 선언하고, DDL·검증·DQ 규칙이 모두 여기서
파생된다.

- **R1~R9** 부문 결과 테이블 (`materialize.py`)
- **R11 세분화** (`materialize_detail.py`) — 규제 라인·UI 통제가 요구하는 입도로
  쪼갠 46장. 예: `rwa_sa_bucket`(자산군×위험가중치), `rwa_irb_pool`(PD 구간),
  `alm_lcr_item`(항목별 잔액·적용률·가중액), `rdm_asset_quality`(건전성 5단계).
- **PRD-REG** 업무보고서 원장 (`regulatory.forms.form_frames`)
- **PRD-UIX** UI 통제 원장 (`ui_studio.governance`)
- **R14 ALM 원장 23장** (`catalog.ALM_LEDGER_TABLES`) — 계수 10장
  (`alm_time_bucket`·`alm_product_terms`·행동모형 3장·`alm_nmd_param`·
  `alm_lcr_factor`·`alm_nsfr_factor`·`alm_liquidity_stress_param`·
  `alm_post_shock_floor`) + 시나리오 2장(`alm_rate_shock_param`·
  `alm_scenario_def`) → 계약(`alm_contract`) → 현금흐름
  (`alm_cashflow_contract`·`_behavioural`·`_bucket`) → 산출 7장
  (`alm_irrbb_bucket_pv`·`alm_irrbb_result`·`alm_nii_result`·`alm_lcr_flow`·
  `alm_nsfr_item`·`alm_maturity_ladder`·`alm_survival_path`).
  규제표·승인값을 적재하는 자리는 각 엔진 모듈의 `build_*` 한 군데뿐이고
  엔진 함수는 원장을 인자로 받는다. 스펙도 그 모듈이 정의하고 카탈로그가
  가져온다 — 스펙과 그것을 채우는 코드가 갈라지지 않게 한다.
  파이프라인 `_stage_alm`이 채워 `PipelineResult.alm_tables`로 내보내고
  `materialize_alm`이 그대로 받는다. `alm_repricing_gap`(잔액 사다리)과
  `alm_maturity_ladder`(현금흐름 사다리)는 **다른 축**이며 섞지 않는다.

전 테이블을 채우는 진입점은 `ui_studio.studio.build_studio(result, portfolio)`다.
부문 엔진만 돌리면 카탈로그에 선언만 되고 산출은 없는 테이블이 생긴다.

**도메인 값은 반드시 실제 데이터에서 가져온다.** 추정으로 적으면 정상 산출이
위반으로 잡히거나(거짓 경보) 신규 값이 조용히 통과한다. `GRADES`는
`models.rating.DEFAULT_MASTER_SCALE`에서, `REPRICING_BUCKETS`는
`alm_time_bucket` 원장의 헤드라인 계정(`표2_19`) 라벨에서 파생한다. 카탈로그가
라벨 사본을 들고 있었고, 헤드라인 사다리가 [별표 9-1] <표2>의 19구간으로 바뀐
뒤 그 사본이 낡아 정상 산출이 도메인 위반으로 잡혔다.

### R15 신규 요건 원장 (`catalog.NEW_LEDGER_TABLES`, 130장)

거시 마스터·한도 정의·[별표 9-1] 국내 고유 요건·제22항 공시서식·LGD/CCF
실측검증·내부등급법 추정·신용평가시스템·CRM 담보배분·거액익스포져·고객행동모형·
ICAAP 리스크 인벤토리·조달·증거금·상품·RCSA·시장데이터 피드·PMA·경영조치·
변경통제·가격통제·모형 생애주기·RBAC·감사체인·보존·통합실행·마감·외부연계·
AI 추적. 산출 경로는 세 갈래다.

1. `pipeline._stage_ledgers` — 거시 마스터 → 한도 정의 → [별표 9-1] 국내
   금리리스크 → LGD·CCF 실측검증 → 나머지 신규 요건. `PipelineResult.
   ledger_tables`로 나가고 근거가 없어 건너뛴 항목은 `ledger_warnings`에 남는다.
2. `datamodel.materialize_ledgers.materialize_ledgers` — `crm_model`·
   `rwa_result`·`mkt_ipv`를 입력으로 쓰는 신용평가시스템·CRM 배분·가격통제.
3. `datamodel.materialize_ledgers.materialize_run_control` — 조립이 끝나야
   원장 목록이 확정되는 RBAC·마감·감사체인·보존·통합실행·AI 추적.
   `build_studio` 마지막에 부른다.

**등재하지 않은 신규 스펙 8장.** [별표 9-1] 2014년 판(금리 EaR·VaR)의 산출
원장 6장은 2019.11.29 개정으로 폐지된 체계이므로 실체화하지 않는다. 제11항
자동금리옵션 재평가 원장 2장은 옵션 인벤토리 원천이 없어 산출하지 않는다.
사유는 `catalog.py`의 R15 구간에 적혀 있다.

## 감독보고 (regulatory/)

금융감독원 배포 기준 업무보고서 서식 **34장**을 은행업감독규정 편제 순으로 낸다.

| 편 | 서식 |
|---|---|
| 제1편 재무·손익 | BA1101 재무상태표 · BA1201 손익계산서 |
| 제2편 자본적정성 | BA2101 총괄 · BA2102 자본명세 · BA2201/2202 신용 SA·IRB · BA2203 CRM · BA2301 시장 · BA2302 위험요소·백테스팅 · BA2401 운영 · BA2402 운영손실 · BA2501 레버리지 · BA2601 산출하한 · BA2701 완충자본·MDA |
| 제3편 유동성 | BA3101 LCR · BA3201 NSFR · BA3301 원화유동성 · BA3401 외화유동성 · BA3501 예대율 |
| 제4편 자산건전성 | BA4101 건전성분류 · BA4102 자산군별 · BA4201 대손준비금 · BA4301 부실채권·연체 |
| 제5편 자산운용 한도 | BA5101 거액여신·동일차주 · BA5201 대주주 · BA5301 유가증권·자회사·부동산 |
| 제6편 금리리스크 | BA6101 IRRBB |
| 제7편 내부자본·위기 | BA6201 스트레스테스트 · BA6301 ICAAP · BA6401 위기상황 산출과정 |
| 제8편 경영실태·조치 | BA7101 경영실태평가 · BA7201 적기시정조치 |
| 제9편 집중도·거래상대방 | BA8101 집중도·거액익스포저 · BA8201 CCR·CVA |

편제와 서식 순서의 단일 소스는 `form_ids.SECTIONS`다. 라인마다 값·산식·규정근거·산출
모듈을 함께 남기고, 소계·비율은 서식이 **스스로 대사**한다(`FormCheck`).
검증 실패가 하나라도 있으면 `reg_submission.status`가 `approved`로 올라가지 않는다.

서식번호는 `regulatory/form_ids.py` 한 장이 단일 소스다. `internal_code`(BA####,
감독규정 편제 대응)와 `official_code`(금감원 배포본) 두 칸으로 나눠 두고, 공식
번호가 없으면 화면·엑셀에 `(내부)` 표시가 붙는다. 공개 웹에서 공식 번호표를
확보하지 못해 **추측해서 채우지 않았다** — 배포본을 받으면 `official_code`만
채우면 서식·라인·검증·UI가 모두 따라온다.

## 위기상황분석 — 전 축 동시 충격 (stress/axes.py · multi_axis.py · trace.py)

신용 파라미터만 충격하는 스트레스는 "신용 스트레스"이지 통합위기상황분석이
아니다. `axes.py`가 **14개 축**을 정의하고, 시나리오 경로가 준 분기별 심도에서
전부 동시에 발동한다 (축마다 다른 경로를 쓰면 어느 분기가 최악인지 말할 수 없다).

| 유형 | 축 |
|---|---|
| 신용 (5) | GDP 충격 → PD 위성모형 · LGD 경기침체가산 · 담보가치 하락 · 미인출 약정 인출 · 외부등급 하향 |
| 시장 (4) | 금리 평행상승 · 신용스프레드 확대 · 주가 하락 · 환율 변동 |
| 운영 (1) | 운영손실 증가 → ILM → 운영 RWA |
| 유동성 (2) | 예금 이탈률 가산 · HQLA 가치 하락 |
| 수익 (2) | 순이자이익 축소 · 수수료수익 감소 |

전이 경로 (`multi_axis.evaluate_point`):

```
거시·축 → 신용파라미터(PD·LGD·EAD·LTV·등급) → 신용RWA(IRB·SA)
        → 시장(4-leg 손익 · 시장RWA) → 은행계정금리(ΔEVE·ΔNII)
        → 운영(손실·ILM·RWA) → 유동성(HQLA·유출·LCR)
        → 손익(이자·수수료·비용·충당금·운영손실·트레이딩·세금)
        → 자본(CET1 = 기준 + 이익변화) → RWA합계·산출하한 → 비율 → 판정
```

두 가지가 특히 중요하다:

- **자본은 증분 ECL이 아니라 세후이익 변화로 롤포워드된다.** 충당금 전입이
  이익에 이미 들어 있으므로 ECL을 따로 빼면 이중계상이다.
- **산출하한 분모도 함께 충격받는다.** 기준 상태 분모를 그대로 쓰면 스트레스에서
  하한이 절대 구속되지 않는 착시가 생긴다.

`trace.py`는 엔진이 남긴 중간값을 13블록 72단계로 펼친다. 각 단계가 산식·
투입값·단위·규정 근거를 갖는다.

불변식: 추적표 값이 `st_capital_path`와 **정확히(rel 1e-12)** 일치하고, 심도 0에서
기준 상태(CET1 비율·RWA·LCR)가 정확히 재현된다. 어긋나면 그건 설명이 아니라 두
번째 모형이다. `tests/test_stress_trace.py`가 전 셀에서 이를 고정하며, 전 축이
신용 단독보다 반드시 더 가혹함도 함께 고정한다.

역스트레스도 전 축을 쓴다 — 신용만 보면 임계 심도가 과대평가된다 (2.35 → 0.94).

## 검증의 두 층 (validation/)

**자체검증(2선)과 상시 독립검증(3선)은 서로 대체할 수 없다.**

| 층 | 담당 | 무엇을 | 구현 |
|---|---|---|---|
| 자체검증 | `risk-validator` | 정합성·규제기준·통계 체크. **같은 코드·같은 가정** | `validation/consistency.py` · `backtest.py` |
| 상시 독립검증 | 적합성검증 팀에이전트<br>`claude/validation-team-agent-Pw9F5` | 개발조직과 분리된 기준셋으로 **독립 재계산**·가정 도전 | `validation/independent.py` |

자체검증만으로 결재하면 "우리 코드가 우리 코드를 통과시켰다"가 결재 근거가
된다. 그래서 `build_studio`는 **매 조립마다** 요청을 만들고 게이트를 판정한다 —
"필요할 때만" 만들면 결국 만들지 않게 된다.

요청 패키지(`build_request`)에 담기는 것:

- 재현 명령 (seed·asof·파이프라인 호출)
- 재계산 대상 10종 (`RECALC_SCOPE`) — RWA·CET1·총자본·레버리지·ECL·LCR·NSFR·
  위기상황 저점·역스트레스 임계 심도·대손준비금
- 자체검증 결과 요약과 **FAIL 항목명** (숨기지 않는다)
- 우리가 아는 가정 8건 (`KNOWN_ASSUMPTIONS`) — 3선이 도전해야 할 약한 고리
- 산출 지문·포트폴리오 지문

게이트(`check_gate`)는 **fail-closed**다.

| 상태 | 조건 | 결재 |
|---|---|---|
| `응답대기` | 응답 파일 없음 | 불가 |
| `부적합` | 중부적합 · 재계산 불일치 · run_id/request_id 불일치 · 파일 손상 | 불가 |
| `적합` | 판정 적합 + 재계산 전건 일치 | 가능 |

교환 디렉터리는 `docs/independent_validation/`이며, CLI `validation-request`는
게이트가 `적합`이 아니면 **종료코드 1**을 낸다. 절차는
`.claude/skills/independent-validation/SKILL.md`, 정책은 `AIMS_POLICY.md` §2-4·§3.

## 에이전틱 UI (ui_studio/)

- `nl_query.py` — 자연어 → Filter AST → 정책검증 → 실행 (PLT-009 · RDM-008).
  제한 문법이며 인식하지 못한 필드는 조용히 무시하지 않고 **차단 사유로 남긴다**.
  마스킹(최소 집계단위 > 1) 필드는 조회조건으로 쓸 수 없다.
- `layout.py` — 프롬프트 → 레이아웃 제안 → 3중 검증(필드권한·스키마·집계
  최소단위) → 사람 승인 (PLT-011~013). 검증 미통과 제안은 `approve()` 자체가 실패.
- `governance.py` — View·필드정책·에이전트·활동·비상정지·변경·증빙 원장. 값은
  저장소의 실제 구성(카탈로그·page_registry·`.claude/agents`)에서 유도한다.
- `engine.js` — 위 두 규칙의 **브라우저 실행판**. 화면에서 문장·프롬프트를
  고치면 서버 왕복 없이 조회계획과 레이아웃이 즉시 다시 만들어진다. 구현이 둘이
  되므로 `tests/test_ui_engine_parity.py`가 node로 돌려 동일 입력 → 동일 AST·
  지문·판정을 고정한다(SHA-256도 자체 구현해 파이썬 해시와 일치).
- `studio.py` / `app.py` — 조립과 렌더. HTML은 자체 완결(외부 CDN 없음)이며
  조회·필터가 화면 안에서 돌도록 View별 데이터를 임베드한다(시연 대상 테이블
  3,000행, 그 외 200행 — 잘린 사실은 화면에 표시된다).

불변식: **어떤 에이전트도 `write_allowed=True`가 아니다** (NO AUTONOMOUS WRITE).

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
- 이름이 비슷한 모듈 구분 (각 모듈 docstring에도 상호참조 명시):
  - `timeseries.py` 차트용 합성 KRI back-history ↔ `timeseries_ledger.py`
    실제 분기 산출 축적 원장 (신규 시계열 기능은 ledger에)
  - `comparison.py` 2-스냅샷 bridge (ops 26 전용) ↔ `timeseries_ledger.py` 다기간 추세
  - `sensitivity.py` 전행 what-if 그리드 ↔ `sensitivities.py` 트레이딩북 Greeks
