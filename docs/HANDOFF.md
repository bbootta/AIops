# 핸드오프 — 리스크관리 팀에이전트

**작성 시점** 2026-08-07 · **브랜치** `claude/risk-management-agent-harness-B9Kxm` (origin과 동기)
**최종 커밋** 데이터 엔지니어링 팀 검토 반영 6건 · 작업 트리 clean

다음 세션은 이 문서부터 읽고 시작하면 된다. 대화 기록 없이도 이어갈 수 있게 썼다.

---

## 1. 지금 서 있는 자리

`risk_lib` — 한국 은행 리스크관리 산출 하네스. 원장 107장, 감독 서식 290장,
에이전틱 UI 화면 72개, 테스트 **1,089 passed · 1 skipped** (14분 37초).

직전 판이 적은 1,129건은 이 컨테이너에서 재현되지 않는다. 원인을 찾았다 —
`tests/test_ui_interactive.py`(54건)가 `pytest.importorskip("playwright.sync_api")`
에서 멈춰 **0건 수집**된다. playwright 파이썬 패키지가 없기 때문이지 테스트가
죽은 것이 아니다. 있는 환경에서는 돈다. 다만 `test_req_trace.py`의 test 증빙
검사는 `tests/` 소스에 `def <이름>(`가 있는지만 보므로, **수집조차 안 되는
테스트도 증빙으로 통과한다** — 증빙이 곧 실행은 아니다.

**최근 3개 커밋이 한 일**

| 커밋 | 내용 |
|---|---|
| `d47f866` | 콕핏 자본 KPI가 제약 계층을 따르게 |
| `e5cca22` | 해외영업점 RWA 분모에 구조화 배분 — 본점 통합이 한 층 아래 남긴 누락 |
| `a9d9bb7` | RYNTA v9.6.0 요건 감사 시정 5건 — 추적표·ICAAP·완충자본·등급열·ECL 범위 |
| `50d2524` | 19차 독립검증 요청 (IVR-397316300BCF) — 재계산 13종 |
| `00733cd` | 산출물 Pack v03 보관 |
| (직전) | 데이터 엔지니어링 팀 검토 반영 6건 — 재현성·인제스트·동어반복·PK·문서 |

**아티팩트 (정본)** https://claude.ai/code/artifact/67ada379-c1f9-46d2-a3c0-4e9c5a21db50
(favicon 🏦 — 재배포 때 바꾸지 않는다. 사용자는 탭 아이콘으로 찾는다)

재배포: **같은 대화에서는 같은 파일 경로로** 다시 올리면 URL이 유지된다.
다른 대화에서는 위 URL을 `url` 인자로 넘긴다 — 안 넘기면 새 URL이 발급된다.
새 URL을 일부러 받고 싶으면 파일 경로를 바꾼다.

한 계정에 같은 내용의 판이 둘 있다 (`dfcd55df-8b06-43c6-b437-533974d7c3ee`가
2026-08-07 판, 위가 그 다음 발급분). 정리하려면 쓰지 않는 쪽을 아티팩트
갤러리에서 지운다 — 코드에서 지울 수단은 없다.

이전 URL `2613d0db-3fc5-4849-b35a-1041442c1b38`은 **다른 계정 소유**라 이
계정에서 갱신할 수 없다. `Artifact(action="list", scope="all")`에 뜨지 않고,
읽기가 공개(비멤버) 리더 경로로 떨어져 `url` 지정·`force`·`WebFetch`가 모두
거부된다 (4회 시도 동일). PM 원장 `products/rynta/PACKAGE-REGISTRY.md` §5에
아직 이 URL이 적혀 있으므로 PM 하네스 쪽에서 정정이 필요하다.

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

자체검증 (2선)      PASS 54 · WARN 6 · FAIL 0   (파이프라인 단독)
                    PASS 65 · WARN 6 · FAIL 0   (스튜디오 — 서식 검사 포함)
상시 독립검증 (3선)  응답대기 (IVR-8F60B82AE085, 20차) · 재계산 13종
게이트               부적합 — fail-closed, 결재 불가
```

해외영업점 서식(asof 동일)은 18차에서 분모가 바뀌었다. **본점 헤드라인은
무변**이고 해외 서식만 움직인다.

```
BF602   총자본비율    15.878% → 10.991%   (본점 10.939%와 거의 같아진다)
        기본자본비율   13.294% →  9.202%
BF602-1 보통주자본비율 11.786% →  8.159%
BF706   자본적정성 점수  20 → 12 · 총점 88 → 80 (2등급 유지)
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

### 4.1 막고 있는 것 — 3선 20차 응답

`IVR-8F60B82AE085` 응답 대기. 게이트가 fail-closed라 결재 불가.
요청서는 `docs/independent_validation/RUN-20260630-42.request.json`.
검증 팀에이전트 브랜치는 `claude/validation-team-agent-Pw9F5`.

3선의 정본 응답은 아직 15차(`IVR-8CDB13393503` · 경부적합)에 머물러 있다 —
16~19차는 응답을 받기 전에 지문이 바뀌어 무효가 됐고, 20차도 같은 경로다.
**요청을 쌓는 것과 응답을 받는 것은 다르다.** 회차가 계속 무효화되면 결재까지
가는 경로 자체가 열리지 않으므로, 다음 세션은 새 산출 변경을 얹기 전에
3선 응답을 받는 쪽을 먼저 볼 것.

**이번 회차에 3선에 올린 1차 도전 지점** — 구조화 익스포저를 분모에 넣은 근거는
"두 원장이 은행계정 익스포저와 **모집단이 겹치지 않는다**"이다(자산군 5종에
펀드 수익증권도 유동화 트렌치도 없음). 그런데 **그건 합성 데이터 생성 방식의
결과이지 실무의 사실이 아니다.** 실 데이터에서 펀드 수익증권이 이미 유가증권
계정에 잡혀 있다면 이 통합은 누락 시정이 아니라 **이중계상**이 된다.
3선이 여기를 때리면 통합 방식을 다시 설계해야 한다.

주장은 `tests/test_pipeline_e2e.py::test_structured_population_does_not_overlap_the_banking_book`
으로 고정해 뒀다 — 자산군이 늘어 겹치기 시작하면 이 검사가 먼저 깨진다.

### 4.2 알려진 한계 (등록돼 있음, 미해결)

**데이터 엔지니어링 팀 검토(2026-08-07)에서 남긴 것** — 전문은 20차 시정문서.

- **독립검증 교환이 단일 슬롯이다 (F-3).** `run_id`에 판(vNN)이 없어 회차마다
  같은 `RUN-<asof>-<seed>.request.json`을 덮어쓴다. 현재 response는 어느 요청과도
  일치하지 않는다. **지금의 게이트 교착은 스킴이 만든 것이다.** 다만 파일명은
  3선과 공유하는 프로토콜이라 우리 쪽만 바꾸면 검증팀이 요청을 못 찾는다 —
  양팀 합의 필요. 응답 서명·해시 체인 부재도 같은 이유로 양팀 사안이다.
- **차원 이력(SCD)이 없다 (F-4).** `rdm_obligor`·`rdm_exposure`·`rdm_collateral`이
  natural key 단독 PK다. 팩트는 asof로 축적되는데 차원은 최신본만 남아, 과거 asof
  팩트에 **오늘의 차주 속성이 소급 적용**된다. SCD2 도입이냐 "최신본만 유지"의
  명문화냐는 설계 결정이라 지어내지 않았다.
- **`TimeSeriesLedger`가 `archive()`에 배선돼 있지 않다 (F-5).** 영속화가 opt-in
  이고 리포에 원장 데이터가 0건이다. `add_from_manifest`는 asof 자리에 실행 종료
  시각을 기록한다.
- **README의 `sha256sum -c`가 클론 사용자에게 실패한다.** 팩은 디스크에 208파일이
  온전하지만 git은 정책상 7개만 추적한다(`.gitignore`에 근거 명시). 검토자는 이를
  "MANIFEST 불일치·정책 미문서화"로 봤는데 그건 틀렸고, 남는 실질은 README가
  클론 사용자를 상정하지 않은 것이다.
- **기후가 내부자본(ICAAP)에 전혀 반영되지 않는다.** `climate_cap`은 NGFS
  3시나리오×7시점의 CET1 **경로**이지 EC 금액이 아니라, 환산 방법론이 없으면
  넣을 수 없다. 방법론을 지어내지 않고 `BNK-OTH-004` note와 19차 도전 지점 3에
  올렸다. 넣을 때는 상관행렬(`ICAAP_CORRELATION`)에 위험유형을 늘릴지도 함께
  정해야 한다.
- **서식·충당금의 ECL 회계 기준이 TTC다.** IFRS 9 5.5.17은 확률가중(PIT)을
  요구한다. 지금은 TTC를 기준으로 두고 PIT를 병기·공표하며, 19차부터 3선이
  둘 다 재계산한다. 바꾸면 대손준비금(재계산 대상)·SA EAD 차감·서식 290장에
  파급되므로 방법론 결정으로 남겼다.
- **`_CREDIT_RWA_KEYS` 열거가 새 누락에 취약하다.** 파이프라인에 신용형 갈래를
  붙이고 이 목록에 넣지 않으면 `xd_ec_covers_rwa_components`가 그 갈래를 보지
  못한다. 갈래를 늘릴 때 §7 절차와 함께 이 목록을 손봐야 한다.
- **위기상황분석이 구조화 RWA를 고정한다.** 등급 하락 시 SEC-ERBA 위험가중치
  상승분이 자본 충격에 반영되지 않는다. `STRESS_MACRO` 모형의
  `known_limitations`에 등록 (`risk_lib/model_inventory.py`).
- ~~해외영업점 서식에 구조화를 배분하지 않았다.~~ **18차에서 해소.** 시장리스크·
  산출하한과 같은 근거(해외 EAD 비중)로 배분했다. 소재국 축이 여전히 없으므로
  실측이 아니라 배분이며, 라인 근거를 `혼합`으로 명시했다.
- **`BF602` 2020~2050(CCR·시장·운영·산출하한)이 실측으로 분류된다.** 전부
  배분값인데 문구에 파생 표지가 없어 `line_basis` 추론이 실측으로 떨어진다.
  18차 변경 범위 밖이라 손대지 않았고 3선 도전 지점 4로 올렸다. 고칠 때는
  `_DERIVED` 어휘를 넓히지 말 것 — 290장 전체가 재분류된다. 라인에 `basis`를
  명시하는 쪽이 범위가 좁다.
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

# 3선 요청 재생성 + 게이트 확인 (산출·서식을 바꿨으면 매번)
python -m risk_lib.cli validation-request --asof 2026-06-30 --seed 42

# 시정 문서의 generated 구간 재생성 — CLI가 없다. 서식이 바뀌면 자체검증에
# doc_figures_provenance FAIL 2건이 뜨고, 이걸 돌린 **뒤에** 요청을 다시 만든다
# (FAIL 을 안은 요청은 그 자체로 다른 요청이라 지문이 또 움직인다)
python -c "
from pathlib import Path
from risk_lib.data_gen import generate_portfolio
from risk_lib.pipeline import run_pipeline
from risk_lib.ui_studio.studio import build_studio
from risk_lib.regulatory import build_forms
from risk_lib.validation.doc_figures import REMEDIATION_DOC, fill_blocks, generated_blocks
p = generate_portfolio(seed=42); r = run_pipeline(p, seed=42, asof='2026-06-30')
built = build_forms(r, p, build_studio(r, p).tables)
d = Path(REMEDIATION_DOC)
d.write_text(fill_blocks(d.read_text(encoding='utf-8'),
                         generated_blocks(built, '2026-06-30')), encoding='utf-8')
"

# 배포용 UI 빌드 (약 12분 · 기준일 2종)
python -c "
from risk_lib.cli import main
raise SystemExit(main(['ui-studio','--asof','2026-03-31,2026-06-30',
                       '--seed','42','--out','/tmp/studio_pub.html']))
"
# 아티팩트용 변환 — Artifact 툴이 <!doctype><head></head><body> 를 직접 붙이므로
# 문서 골격 태그를 걷어낸다. <title>·<style>·<script> 는 그대로 둔다.
# (직전 판이 적어 둔 to_artifact.py 는 저장소에 없다 — 세션 스크래치패드에만
#  있었고 컨테이너와 함께 사라졌다. 변환은 이 여섯 줄이 전부다.)
python -c "
import re
s = open('/tmp/studio_pub.html', encoding='utf-8').read()
i = s.index('</head>')
head = re.sub(r'^<!doctype html>\s*<html[^>]*><head>', '', s[:i], flags=re.I)
head = re.sub(r'<meta charset=[^>]*>\s*', '', head, count=1, flags=re.I)
body = re.sub(r'^\s*<body[^>]*>', '', s[i+7:], flags=re.I)
body = re.sub(r'</body>\s*</html>\s*\$', '', body, flags=re.I)
open('/tmp/studio_artifact.html','w',encoding='utf-8').write(head.strip()+chr(10)+body.strip())
"
# 확인: 골격 태그 0건 · 외부 호스트 0건(SVG 네임스페이스 URI는 요청이 아니다) ·
#       크기 16MB 미만 (현재 11.7MB) · prompt()/alert() 실제 호출 0건
```

---

## 6. 이미 밟은 지뢰 — 다시 밟지 말 것

이 저장소에서 반복해 나온 결함 유형이다. 새 기능을 붙일 때 이 목록을 훑으면
같은 실수를 줄일 수 있다.

**조용한 누락 (silent omission)** — 이 저장소의 주된 실패 양식이다.
- 하드코딩한 목록으로 필터링해 목록 밖 행을 양쪽에서 떨어뜨리기 —
  `_stage_split_books`의 자산군 5종이 그랬다. 실데이터에서만 터지는 종류라
  합성 데이터로는 영원히 안 보인다. 목록을 상수로 꺼내고 완전성 대사를 붙인다
- salted `hash()`로 seed 유도 — 프로세스마다 값이 달라 재현성이 조용히 샌다.
  `hashlib`을 쓴다
- 원장에서 산출은 해놓고 합계에 넣지 않기 (구조화 RWA 4.13조가 그랬다)
- NaN이 `groupby`/`sum`에서 조용히 빠지기 (SA북 충당금이 '0'도 아닌 'NaN 무시'였다)
- 잔차로 항목 구하기 — `credit = total − a − b − c` 구조에서는 빠뜨린 항목이
  전부 `credit`이라는 틀린 이름을 달고 통과한다 (구 바젤 서식이 그랬다)
- 기본값을 사실처럼 표시하기 (비신용 모형의 `segment`가 전부 `corporate`였다)
- 표로 실체화하면서 열을 빠뜨려 **명시한 값이 추론으로 대체되기** —
  `provenance_stats_from_lines`가 `reg_form_line`의 `basis` 열을 읽지 않아,
  서식 객체로 세면 혼합인 배분 라인이 3선 요청서에서는 실측으로 실렸다.
  열은 있었고 읽지 않았을 뿐이다
- 배분 항목을 분모에서만 빼기 — 분자는 배분된 채 남아 비율이 부풀려진다
  (해외 자본비율이 본점보다 4.89%p 높았다)

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

**추적표·통제의 자기기만**
- 조용한 기본값 — `dict.get(key, 기본값)`으로 "판정해서 X"와 "아무도 안 봐서 X"가
  같은 칸에 들어갔다. 요건 56건이 그렇게 미반영으로 보고됐고 그중 9건은 구현이
  4개 층 다 있었다. 판정하지 않은 것은 판정하지 않았다고 적는다(`UNASSESSED`)
- 같은 사실을 말하는 표가 둘인데 대조가 없기 — `req_trace.TRACE`와 `rynta.COVERAGE`가
  DAT-006에서 정반대였다. 대조 검사를 붙이자 모순 4건이 더 나왔다
- 총량으로 대조하는 통제 — CCR의 경제자본 기여 15.5억은 Pillar 1 소요자본
  1,078조의 0.001%라, 총량 비교로는 빠져도 절대 걸리지 않는다. 작은 갈래의
  누락을 잡으려면 **구성요소 이름**으로 봐야 한다

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
