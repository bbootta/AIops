---
name: independent-validation
description: 리스크 산출 작업이 끝날 때마다 적합성검증 팀에이전트(claude/validation-team-agent-Pw9F5)에 상시 독립검증을 요청하고 게이트를 확인한다. 자체검증(risk-validator)과는 별개이며 생략할 수 없다. RWA·BIS·ECL·스트레스·ALM·업무보고서 등 어떤 리스크 산출물이든 결재 상신 전에 반드시 실행한다.
---

# 상시 독립검증 위임 (3선)

## 왜 자체검증으로 부족한가

`risk-validator`(2선)는 **같은 코드·같은 가정**으로 점검한다. 그 결과만으로
결재하면 "우리 코드가 우리 코드를 통과시켰다"가 결재 근거가 된다.

3선인 **적합성검증 팀에이전트**는 개발조직과 분리된 기준셋으로 **다시 계산**한다.
가정을 공유하지 않는 것이 요점이므로 우리가 대신 판정할 수 없다.

| 구분 | 담당 | 무엇을 하나 | 누가 통과시키나 |
|---|---|---|---|
| 자체검증 (2선) | `risk-validator` | 정합성·규제기준·통계 체크 | 이 팀 |
| 상시 독립검증 (3선) | 적합성검증 팀에이전트<br>`claude/validation-team-agent-Pw9F5` | 독립 재계산·가정 도전 | **다른 팀** |

## 절차 — 매 작업 예외 없이

### 1. 요청 생성

```python
from risk_lib.validation.independent import build_request, check_gate

request = build_request(result, portfolio, tables, manifest=manifest)
path = request.write()          # docs/independent_validation/<run_id>.request.json
```

요청 패키지에는 다음이 들어간다. 하나라도 빠지면 3선이 재계산할 수 없다.

- **재현 명령** — seed·asof·파이프라인 호출
- **재계산 대상 21종** (`RECALC_SCOPE`, 개수는 코드가 정본): RWA 합계·펀드·
  유동화, CET1/총자본비율, 레버리지, ECL(가중 포함), LCR, NSFR, IRRBB(ΔEVE 비율·
  ΔNII·별표 9-1 두 값), 생존기간, 위기상황 CET1 저점, 역스트레스 임계 심도,
  대손준비금, LGD 백테스트 두 값, CCF 실현치
- **자체검증 결과 요약** — PASS/WARN/FAIL과 FAIL 항목명 (숨기지 않는다)
- **우리가 아는 가정 목록** (`KNOWN_ASSUMPTIONS`) — 3선이 도전해야 할 약한 고리
- **산출 지문·포트폴리오 지문** — 다른 실행의 응답이 승인으로 쓰이지 않게 한다

### 2. 위임

`claude/validation-team-agent-Pw9F5` 브랜치의 적합성검증 팀에이전트에 요청
파일 경로를 전달한다. 전달은 `dispatch_request(request)` (또는
`python -m risk_lib.cli validation-request --dispatch`) 로 기록한다: 요청 사본이
`docs/independent_validation/outbox/` 에 놓이고 `<run_id>.dispatch.json` 에
대상 브랜치·경로·인계 명령이 남는다. 이 기록이 없으면 요청은 만들어졌을 뿐
넘어가지 않은 것이다. 응답은 같은 디렉터리에 `<run_id>.response.json`으로 온다.

### 3. 게이트 확인 — 결재 상신 직전 필수

```python
gate = check_gate(request)
gate.require()      # 통과 못 하면 IndependentValidationPending
```

게이트는 **fail-closed**다.

| 상태 | 의미 | 결재 |
|---|---|---|
| `응답대기` | 응답 파일 없음 | **불가** |
| `부적합` | 중부적합 있음 · 재계산 불일치 · run_id 불일치 | **불가** |
| `조건부` | 판정 경부적합 + 중부적합 0건 + 재계산 전건 일치 | **기록 있을 때만** |
| `적합` | 판정 적합 + 재계산 전건 일치 | 가능 |

응답이 없을 때 조용히 통과시키면 위임 자체가 형식이 된다. `응답대기`를
`적합`으로 바꿔 부르지 말 것.

### `조건부` — 경부적합을 사람이 인수하는 경로

경부적합은 통과도 부적합도 아니다. 결재하려면 결재 책임자가 **잔여위험 ·
후속조건 · 이행기한 · 배포 범위**를 기록해야 한다. 기록이 없거나 항목이 비면
게이트는 통과하지 않는다.

```python
gate.require(ConditionalApproval(
    approver="리스크관리책임자",
    residual_risk="합성 자본의 규모 비례분이 CET1의 54.3%",
    conditions=("실 자본 원장 확보 후 재산출",),
    due_date="2026-09-30",
    scope="내부 검토용 제한 배포",
    findings_accepted=("F-201", "F-202")))
```

기계가 이 기록을 대신 만들지 않는다 — 잔여위험을 누가 지는지는 사람의 판단이다.
`조건부`를 `적합`으로 적지 않는다.

## 보고 시 표기

최종 보고에는 항상 두 줄을 함께 적는다.

```
자체검증 (2선)      PASS 49 · WARN 3 · FAIL 0        — risk-validator
상시 독립검증 (3선)  응답대기 (IVR-XXXXXXXXXXXX)       — 적합성검증 팀에이전트
```

독립검증이 `응답대기`인 상태에서 "검증 완료"라고 쓰지 않는다. 사용자가 결과를
요구하면 자체검증 결과를 주되 **독립검증 상태를 함께 명시**한다.

## 새 headline 수치를 만들었다면

`RECALC_SCOPE`에 추가한다. 여기 없는 수치는 3선이 다시 계산하지 않으므로,
빠뜨리면 그 수치는 독립검증을 받지 않은 채 결재로 넘어간다.
