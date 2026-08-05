# 핸드오프 — 리스크관리 팀에이전트

**작성 시점** 2026-08-05 · **브랜치** `claude/risk-management-agent-harness-B9Kxm` (origin과 동기)
**최종 커밋** `d47f866` · 작업 트리 clean

다음 세션은 이 문서부터 읽고 시작하면 된다. 대화 기록 없이도 이어갈 수 있게 썼다.

---

## 1. 지금 서 있는 자리

`risk_lib` — 한국 은행 리스크관리 산출 하네스. 원장 107장, 감독 서식 290장,
에이전틱 UI 화면 72개, 테스트 1,129건.

**최근 3개 커밋이 한 일**

| 커밋 | 내용 |
|---|---|
| `d0cb1f4` | '모형' 메뉴그룹 1레벨 신설 — 전 도메인 모형 거버넌스 5화면 |
| `89917da` | 구조화 익스포저(CRE60·CRE40)를 자본비율 분모에 통합 |
| `d47f866` | 콕핏 자본 KPI가 제약 계층을 따르게 |

**아티팩트** https://claude.ai/code/artifact/2613d0db-3fc5-4849-b35a-1041442c1b38
(재배포: 빌드 후 같은 URL을 `url` 인자로 넘긴다 — 안 넘기면 새 URL이 발급된다)

---

## 2. 현재 산출값 (asof 2026-06-30 · seed 42)

```
위험가중자산   13.4786조
  집합투자증권  3.3312조   LTA 7 · MBA 4 · fallback 1
  유동화        0.7971조   SEC-IRBA 11 · SEC-SA 11 · SEC-ERBA 5

CET1          8.1193%   요구 8.00%    여유 +0.119%p
기본자본       9.1580%   요구 9.50%    부족 −0.342%p
총자본        10.9386%   요구 11.50%   부족 −0.561%p
레버리지       9.6974%
역스트레스 임계 0.04917

자체검증 (2선)      PASS 49 · WARN 6 · FAIL 0   (파이프라인 단독)
                    PASS 60 · WARN 6 · FAIL 0   (스튜디오 — 서식 검사 포함)
상시 독립검증 (3선)  응답대기 (IVR-AC0EDF9E5A37, 17차)
게이트               부적합 — fail-closed, 결재 불가
```

**골든은 `tests/test_pipeline_e2e.py`의 `GOLDEN`에 고정돼 있다.** 헤드라인을
움직이는 변경을 하면 거기 재고정하고 **왜 움직였는지 주석으로 남긴다** — 그
파일의 재고정 1~5번 주석이 그 규약의 실물이다.

---

## 3. 지켜야 하는 것

1. **개발·커밋·푸시는 `claude/risk-management-agent-harness-B9Kxm`에만.**
   다른 브랜치로 푸시하려면 명시적 허가를 받는다.
2. **PR은 요청받았을 때만 만든다.**
3. **`CLAUDE.md` §5 — 검증의 두 층.** 리스크 산출 작업을 하면 매번 예외 없이:
   - 자체검증 (2선) `run_consistency_checks` → `val_check`
   - 독립검증 요청 (3선) `risk_lib.validation.independent.build_request`
     → `docs/independent_validation/`
   - 결재 상신 직전 `check_gate(...).require()` — 응답 없으면 `응답대기`,
     결재 불가. `경부적합`이면 `조건부`이며 `ConditionalApproval` 기록 필수.
   보고할 때 두 줄을 함께 적는다. 3선이 `응답대기`인데 "검증 완료"라고 쓰지 않는다.
4. **새 headline 수치를 만들면 `independent.RECALC_SCOPE`에 넣는다.**
   거기 없으면 3선이 그 수치를 다시 계산하지 않는다.
5. 경영진 보고서는 약어에 주석을 단다.

---

## 4. 다음에 할 일

### 4.1 막고 있는 것 — 3선 17차 응답

`IVR-AC0EDF9E5A37` 응답 대기. 게이트가 fail-closed라 결재 불가.
요청서는 `docs/independent_validation/RUN-20260630-42.request.json`.
검증 팀에이전트 브랜치는 `claude/validation-team-agent-Pw9F5`.

**이번 회차에 3선에 올린 1차 도전 지점** — 구조화 익스포저를 분모에 넣은 근거는
"두 원장이 은행계정 익스포저와 **모집단이 겹치지 않는다**"이다(자산군 5종에
펀드 수익증권도 유동화 트렌치도 없음). 그런데 **그건 합성 데이터 생성 방식의
결과이지 실무의 사실이 아니다.** 실 데이터에서 펀드 수익증권이 이미 유가증권
계정에 잡혀 있다면 이 통합은 누락 시정이 아니라 **이중계상**이 된다.
3선이 여기를 때리면 통합 방식을 다시 설계해야 한다.

주장은 `tests/test_pipeline_e2e.py::test_structured_population_does_not_overlap_the_banking_book`
으로 고정해 뒀다 — 자산군이 늘어 겹치기 시작하면 이 검사가 먼저 깨진다.

### 4.2 알려진 한계 (등록돼 있음, 미해결)

- **위기상황분석이 구조화 RWA를 고정한다.** 등급 하락 시 SEC-ERBA 위험가중치
  상승분이 자본 충격에 반영되지 않는다. `STRESS_MACRO` 모형의
  `known_limitations`에 등록 (`risk_lib/model_inventory.py`).
- **해외영업점 서식에 구조화를 배분하지 않았다.** 두 원장에 소재국 축이 없다.
  서식 9000 라인에 "0은 해외 몫이 없다가 아니라 배분 근거가 없다는 뜻"으로 명시.
- **자본이 합성이다.** `capital_source` WARN이 매 실행 그 사실과 규모 비례분
  비율을 드러낸다. 실제 자본 원장이 생기면 `run_pipeline(capital_ledger=...)`로
  넘긴다 — 합성기는 그때 자동으로 비켜난다.

### 4.3 사용자가 아직 답하지 않은 질문

없음. 직전 질문(구조화 RWA 분모 통합 여부)은 "응"으로 승인받아 반영 완료.

---

## 5. 자주 쓰는 명령

```bash
# 전체 스위트 (약 16분)
python -m pytest tests/ -q

# 헤드라인만 빠르게
python -m pytest tests/test_pipeline_e2e.py -q

# UI 스위트 (Playwright — Chromium은 /opt/pw-browsers/chromium에 이미 있다.
#            playwright install 을 절대 실행하지 않는다)
python -m pytest tests/test_ui_interactive.py tests/test_ui_studio.py -q

# 배포용 UI 빌드 (약 12분 · 기준일 2종)
python -c "
from risk_lib.cli import main
raise SystemExit(main(['ui-studio','--asof','2026-03-31,2026-06-30',
                       '--seed','42','--out','/tmp/studio_pub.html']))
"
# 그 다음 to_artifact.py 로 CSP 대응 변환 후 Artifact 툴에 URL 을 넘겨 재배포
```

---

## 6. 이미 밟은 지뢰 — 다시 밟지 말 것

이 저장소에서 반복해 나온 결함 유형이다. 새 기능을 붙일 때 이 목록을 훑으면
같은 실수를 줄일 수 있다.

**조용한 누락 (silent omission)** — 이 저장소의 주된 실패 양식이다.
- 원장에서 산출은 해놓고 합계에 넣지 않기 (구조화 RWA 4.13조가 그랬다)
- NaN이 `groupby`/`sum`에서 조용히 빠지기 (SA북 충당금이 '0'도 아닌 'NaN 무시'였다)
- 잔차로 항목 구하기 — `credit = total − a − b − c` 구조에서는 빠뜨린 항목이
  전부 `credit`이라는 틀린 이름을 달고 통과한다 (구 바젤 서식이 그랬다)
- 기본값을 사실처럼 표시하기 (비신용 모형의 `segment`가 전부 `corporate`였다)

**통제가 통제가 아니었던 경우**
- 테스트가 실제 환경엔 없는 도움을 주기 — Kill Switch 테스트가
  `page.on("dialog", ...)` 를 달아줘서, `prompt()`가 iframe에서 차단된다는
  사실을 가리고 있었다
- 검사가 코드와 같은 오해를 공유하기 — 계정별 집계를 `asset_class`로 조인해
  2.28배 부풀린 값을 "실측"이라 부르고 있었고, 테스트가 그 잘못된 계약을
  인코딩하고 있었다
- 임계값만 보고 요구치를 안 보기 — Pillar 1 최저(4.5/6/8)만 검사해서
  완충자본 미달이 `PASS 49 · FAIL 0`으로 통과했다

**화면이 사실이 아닌 것을 말한 경우**
- 콕핏이 CET1만 보고 초록 — 총자본이 −0.56%p인 순간에도
- 같은 원장을 두 화면이 각자 그리기 — 어느 쪽이 최신인지 물어야 한다
- 통제가 있어 보이는데 동작하지 않기 (`prompt()`/`alert()`는 아티팩트
  샌드박스에서 차단된다 — 화면 내 입력으로 만든다)

**결정론 / 재현성**
- `Date.now()`·`Math.random()`은 워크플로 스크립트에서 못 쓴다
- 원장 생성은 `(asof, seed)`로 고정한다. 같은 원장을 두 곳에서 만들면
  "같은 값이 나올 것"이라는 기대에 의존하게 된다 — 기대는 통제가 아니다.
  구조화 원장은 파이프라인이 만들고 스튜디오가 `result.structured.tables`로
  받는다
- 규제 상수는 **별사본 금지**. 엔진에서 import 한다 (`BIS_MINIMUMS` 등)

**월초 경계** — `bdate_range`가 주말 월초에 빈 배열을 낸다.
`month_business_days()` 공용 헬퍼를 쓴다.

---

## 7. 구조 빠르게 잡기

```
risk_lib/
  pipeline.py              산출 오케스트레이션. 4갈래 병렬:
                             신용(ECL→EAD→RWA) · 시장운영 · CCR · 구조화
                           갈래 안의 순서는 규정이 정한다 (ECL이 EAD보다 먼저 — CRE20)
  capital/                 RWA·BIS·output floor·CRM·CCR 엔진
  datamodel/
    catalog.py             107장 스펙 — 살아 있는 계약
    materialize.py         PipelineResult → 정규 테이블
    funds.py               집합투자증권 (CRE60 LTA/MBA/fallback)
    securitisation.py      유동화 (SEC-IRBA/ERBA/SA + 위험가중치 하한)
    derivatives.py         파생 (SA-CCR)
    exposure_agg.py        도메인별 집계 원장 5종
  validation/
    consistency.py         자체검증 (2선)
    cross_domain.py        도메인 교차 대사
    independent.py         독립검증 요청 (3선) · RECALC_SCOPE
  regulatory/              감독 서식 290장
  ui_studio/app.py         에이전틱 UI 72화면 (단일 HTML 산출)
```

**파이프라인 갈래를 늘릴 때** — `_branch_*` 함수를 만들고
`ThreadPoolExecutor`에 넣은 뒤, 그 산출이 자본비율에 들어가야 하면
`_stage_capital`의 `rwa_internal_total`·`rwa_standardised_total` **양쪽**과
레버리지 익스포저를 함께 손본다. RWA만 넣으면 두 비율이 서로 다른 은행을
설명하게 된다. 그리고 `cross_domain.py`의 구성요소 합 대사에 넣는다 —
안 넣으면 FAIL이 뜬다(그게 정상이다. 그 FAIL이 통합 누락을 잡는 장치다).
