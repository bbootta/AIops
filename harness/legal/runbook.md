# 법무 에이전트팀 운영 런북

법무 요청이 들어왔을 때 팀을 어떻게 돌리는지 정의한다. 오케스트레이터
(메인 세션)가 이 런북대로 에이전트를 투입한다.

## 공통 절차 (모든 시나리오)

1. **인테이크**: 의뢰인 지위(회사/개인, 갑/을, 원고/피고), 목적, 시한,
   관할·준거법을 확정한다. 불명확하면 착수 전에 사용자에게 묻는다.
   시효·제척기간·불변기간이 걸린 사안은 기간 계산부터 한다.
2. **KB 우선**: `kb/legal/00-index.md`에서 관련 문서를 찾아 읽고 시작한다.
   KB 기준일 이후의 변경 가능성이 있는 쟁점만 웹 조사로 보강한다.
3. **인용 규율**: 사건번호·조문은 검증된 것만. 미확인 인용은
   `[사건번호 미확인]` 표기. 산출물에 인용을 "장식"으로 추가하지 않는다.
4. **품질 게이트**: 의견서·전략메모·대외문서·치명 등급 계약검토는
   `legal-red-team` 검증(PASS)을 받아야 전달한다. FAIL이면 지적사항을
   반영해 재검토 후 재검증한다.
5. **고지**: 모든 산출물에 검토 기준일과 "내부 참고자료, 변호사 자문 대체
   아님" 고지를 넣는다.

## 시나리오 A — 법률자문 (사내 법무 질의, 컨설팅)

> 예: "이 사업 모델이 ○○법에 걸리나요", "이사회 결의 없이 가능한가요"

1. `legal-lead`: 쟁점 분해, 검토 계획 수립
2. 쟁점별 병렬 투입:
   - `legal-statute-researcher` — 적용 법령·조문
   - `legal-case-researcher` — 관련 판례
   - 영역 전문가(corporate/compliance/labor/ip-tech 중 해당) — 실무 검토
3. `legal-lead`: 종합 결론(쟁점별 결론 + 리스크 등급 + 권고)
4. `legal-red-team`: 반대검증 → PASS까지 반복
5. `legal-writer`: `templates/legal/legal-opinion.md`로 의견서 작성
- **워크플로**: `.claude/workflows/legal-consult.js` (질문을 args로)

## 시나리오 B — 계약 검토

> 예: "이 공급계약 검토해줘", "투자계약 텀시트 봐줘"

1. 인테이크에서 추가 확정: 우리가 어느 당사자인지, 거래 목적, 협상력
2. `legal-contract-reviewer`: 전체 조항 분석 + 누락 조항 점검
3. 검토 중 발견된 전문 쟁점을 해당 전문가에 병렬 위임
   (예: 지재권 귀속 → ip-tech, 하도급법 → compliance, 해외 상대방 → international)
4. 치명(Deal-breaker) 판단이 있으면 `legal-red-team` 검증
5. `legal-writer`: `templates/legal/contract-review-report.md`로 보고서 작성
- **워크플로**: `.claude/workflows/contract-review.js` (계약서 경로를 args로)

## 시나리오 C — 분쟁·소송 대응 (민사/형사/행정)

> 예: "거래처가 대금을 안 줍니다", "압수수색이 나왔습니다", "소장을 받았습니다"

1. `legal-lead`: 분쟁 구도 정리. **기간(시효·불변기간) 체크 최우선**
   - 소장 수령: 답변서 제출 기한(30일) 즉시 확인
   - 형사(압수수색·소환): 초동 대응 수칙을 먼저 전달
2. `legal-litigation-strategist`: 전략 골격(승소 전망, 트랙 선택, 보전 조치)
3. 병렬 투입:
   - `legal-case-researcher` — 쟁점별 판례 (승소 전망의 근거)
   - `legal-statute-researcher` — 요건사실·절차 규정
   - 영역 전문가 — 실체 쟁점 (노동 분쟁이면 labor, 주주 분쟁이면 corporate 등)
4. `legal-red-team`: **상대방 최선 전략 시뮬레이션** (이 시나리오에선 필수)
5. `legal-litigation-strategist`: 시뮬레이션 반영해 전략 확정
6. `legal-writer`: `templates/legal/litigation-strategy-memo.md`로 전략메모,
   필요시 `templates/legal/demand-letter.md`로 내용증명 초안
- **워크플로**: `.claude/workflows/litigation-prep.js`

## 시나리오 D — 컴플라이언스 점검·규제 대응

> 예: "개인정보 처리 실태 점검해줘", "공정위 조사가 나왔습니다", "신사업 규제 검토"

1. `legal-compliance-officer`: 적용 규제 지도 작성, 점검 범위 확정
2. 영역별 병렬 점검 (공정거래/개인정보·AI/금융/노동·중대재해 등 해당 영역):
   각 영역에 compliance-officer + statute-researcher 조합
3. 위반 발견 시: 제재 노출 분석(행정/형사/민사/평판) + 자진신고·감경 전략
4. 조사 대응 국면이면 `legal-litigation-strategist` 합류(진술·자료제출 전략)
5. `legal-writer`: `templates/legal/compliance-checklist.md` 기반 점검 보고서
   또는 `templates/legal/regulatory-briefing.md` 기반 규제 브리핑
- **워크플로**: `.claude/workflows/compliance-audit.js` (점검 영역을 args로)

## 시나리오 E — 국제거래·해외 사안

> 예: "미국 회사와 공급계약", "EU에 SaaS 출시", "해외 중재 조항 검토"

1. `legal-international-counsel`: 준거법·관할·역외규제 3축 확정
2. 병렬 투입:
   - 해당 국가 쟁점 — international-counsel이 KB(global) + 웹 조사
   - 국내법 접점(외환신고, 국외이전, 수출통제) — statute-researcher/compliance
   - 계약이면 contract-reviewer 합류
3. "현지 변호사 확인 필요" 사항을 명시적으로 분리
4. 이후 시나리오 A/B와 동일한 검증·작성 절차

## 에스컬레이션 규칙

다음은 에이전트가 결론 내리지 않고 사용자에게 보고한다:

- 변호사 선임이 즉시 필요한 국면(구속 위험, 임박한 불변기간, 대규모 소송)
- 사실관계 확인 없이는 결론이 갈리는 사안(추가 자료 요청)
- 이해충돌 가능성(회사 vs 임원 개인의 이익이 갈리는 사안)
- 외국법이 결론을 좌우하는데 공개 자료로 확인 불가능한 사항

## KB 유지보수

- KB 기준일은 `kb/legal/00-index.md`에 기록되어 있다.
- 분기 1회 또는 큰 입법 이벤트(정기국회 통과, 대형 전합 판결) 후
  `.claude/workflows/legal-kb-update.js`로 해당 분야를 재조사·갱신한다.
- 자문 중 KB의 오류·공백을 발견하면 해당 KB 파일을 바로 수정하고
  갱신일을 문서 헤더에 기록한다.
