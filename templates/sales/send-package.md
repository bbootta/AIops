# 발송 패키지: {캠페인ID}

> 저장 경로: `docs/sales/outbox/{캠페인ID}/send-package.md`
> 실제 발송과 LinkedIn/전화 터치 실행은 항상 PO가 한다. 에이전트는 발송 도구를 실행하지 않는다 [G1].

| 항목 | 내용 |
|---|---|
| 캠페인ID | {YYYYMMDD-<region>-<슬러그>} |
| 작성 에이전트 | sales-lead (조립) |
| 검토 | outreach-qa / sales-compliance-officer / deliverability-engineer (게이트 판정, §2) |
| 승인 | PO {서명/날짜 또는 미승인} (§7) |
| 기준일 | {YYYY-MM-DD} |

## 1. 패키지 상태

- **상태: {승인 대기 / PO 승인 완료 / 반려}**
- 요약: {세그먼트} 대상, 터치 1 발송 대상 {n}명, 발송 예정 {일자/윈도}, 시퀀스 총 {n}터치 {n}일
- PO가 할 일: ① §2 게이트 대조표 확인 ② §7 승인란 서명 ③ 발송 도구에서 터치 1 실행 ④ LinkedIn/전화 터치 캘린더 확인 (§6)
- 게이트 미통과 항목이 하나라도 있으면 이 패키지는 "발송 가능" 상태로 PO에게 상신되지 않는다 [G1][G2].

## 2. 게이트 통과 기록 대조표 (4종)

| 게이트 | 담당 | 판정 | 기록 문서 | 판정일 |
|---|---|---|---|---|
| QA: 11항목 + 시퀀스 구조 + 영어 네이티브 관용성·톤 (전 채널 카피) [G3][G11] | outreach-qa | {PASS/FAIL} | {경로} | {…} |
| 컴플라이언스: 게이트 A/B/C + 한국 분기 [G2][G7][G9] | sales-compliance-officer | {PASS/FAIL} | `docs/sales/compliance/{캠페인ID}-gate.md` | {…} |
| 딜리버러빌리티 프리플라이트: 리스트 검증·웜업·안전장치 설정 검증 [G5][G6] | deliverability-engineer | {PASS/FAIL} | {경로} | {…} |
| LIA (EU/영국 레코드 포함 시) [G10] | sales-compliance-officer 초안 / **PO 승인** | {승인 / 해당 없음} | `docs/sales/compliance/{LIA-ID}.md` | {…} |

- [ ] [G2] 4종 전부 PASS/승인(또는 해당 없음) 확인. FAIL·대기 항목: {없음 / 목록}

## 3. 구성물

| 구성물 | 경로 |
|---|---|
| 캠페인 브리프 | `docs/sales/campaigns/{캠페인ID}/campaign-brief.md` |
| 터치맵 (Day-by-Day, 실행 주체 명기) | `docs/sales/campaigns/{캠페인ID}/touchmap.md` |
| 전 채널 최종 카피 (이메일, LinkedIn 노트/DM, 콜/보이스메일) | `docs/sales/campaigns/{캠페인ID}/copy.md` |
| 리스트 요약 | §4 (원본: {경로}) |
| 계정 리서치 (Tier 1~2 전건) [G4] | `docs/sales/campaigns/{캠페인ID}/research/` |
| 발송 스케줄 | §6 |

## 4. 리스트 요약

| 관할 | 등급 | 레코드 수 | 제외/보류 | LIA ID |
|---|---|---|---|---|
| {US} | 가능 | {n} | {n} | 해당 없음 |
| {EU-FR} | 조건부 | {n} | {n} | {LIA-…} |

- [ ] [G9] 필수 필드(jurisdiction, 출처, 수집일, 증빙, LIA ID, 보관기간 만료일) 완비
- [ ] [G4] Tier 1~2 전건 30일 이내 리서치 존재, 보류 레코드는 큐 제외

## 5. 터치 2~N 릴리스 조건

- 각 후속 터치는 발송 예정일에 `templates/sales/touch-release-checklist.md` **PASS 기록이 있어야 릴리스**된다 [G2][G5]. 발송 도구에 스케줄이 걸려 있어도 PASS 없이는 실행 금지.
- 릴리스 게이트 분담: sales-ops-analyst (답장 로그 분류) / sales-compliance-officer (suppression 델타 재대조, 전 채널 제외 확인) / deliverability-engineer (도구 동기화, 잔여 한도, 직전 터치 지표)
- 자동 제외 트리거: 수신거부(링크/자연어), 답장, 하드바운스, 스팸 신고 → 즉시 전 채널 시퀀스 제외 [G2]
- 캠페인 개시와 볼륨 증량 후 3일간, 그리고 발송 활성 기간 매 영업일 sales-ops-review daily 모드 필수 실행 [G6]

| 터치 | 예정일 | 릴리스 조건 | 체크리스트 기록 |
|---|---|---|---|
| T{2} | {…} | touch-release PASS | {경로 또는 예정} |
| T{N} | {…} | touch-release PASS | {…} |

## 6. 발송 스케줄

| 터치 | 일자 | 수신자 시간대 윈도 (현지) | 실행 주체 | 메일박스 / 일일 한도 |
|---|---|---|---|---|
| T1 | {…} | {평일 업무시간} | {발송 도구 / PO} | {…} |

## 7. PO 승인란 [G1]

| 항목 | 기록 |
|---|---|
| 판정 | {승인 / 조건부 승인(조건) / 반려(사유)} |
| PO 서명 | {…} |
| 날짜 | {YYYY-MM-DD} |

- 이 승인은 패키지(터치 1과 시퀀스 구조·카피 전체)에 대한 것이며, 터치 2~N의 릴리스는 §5 조건 충족을 전제로 한다.
- 초기 캠페인은 100% 검수, 안정화 후에도 샘플링 검수를 유지한다 [G1].
