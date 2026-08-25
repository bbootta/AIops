# T3/T4 제공 자산 인덱스 · "two-page note" 세그먼트별 6종

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/assets/00-index.md`
> 작성: deal-strategist · 기준일: 2026-08-19 · 상태: **outreach-qa 팩트체크 대기**
> 목적: 마스터 카피 T3의 "reply 'send it'" 제안과 T4 브레이크업의 오픈 오퍼가 가리키는
> 콘텐츠 자산의 실물. copy/00-index.md §5-6("실물 없이는 T3/T4 발송 불가") 해소용.

## 1. 노트 목록

| # | 파일 | 세그먼트 | 제목 (영문) | 이행하는 카피 | 규제 앵커 카드 |
|---|---|---|---|---|---|
| 1 | `note-us-banks.md` | 미국 은행 | SR 26-2 and your AI model inventory: what changes for validation teams | master-us-banks T3·T4 | EC-regwind-usuk-01 |
| 2 | `note-us-brokerdealers.md` | 미국 브로커딜러 | AI in FINRA's 2026 report and the SEC's FY2026 exam priorities: a WSP readiness view | master-us-brokerdealers T3·T4 | EC-regwind-us-bd-01 |
| 3 | `note-us-insurance-am.md` | 미국 보험(A)·자산운용(B) 통합 | AI oversight for US insurers and asset managers: the NAIC bulletin, the 12-state exam pilot, and the SEC's FY2026 priorities | master-us-insurance-am T3-A·T3-B·T4 | EC-regwind-us-ins-01 |
| 4 | `note-uk.md` | 영국 | SS1/23 Principle 4 in practice: independent validation as AI and ML models join the inventory | master-uk T3·T4 | EC-regwind-usuk-01 |
| 5 | `note-sg.md` | 싱가포르 | MAS's proposed AI risk management guidelines: a readiness note for the proposed 12-month transition | master-sg T3·T4 | EC-regwind-sg-01 |
| 6 | `note-au.md` | 호주 | APRA's AI letter and CPS 230: a practical view on moving towards continuous assurance | master-au T3·T4 | EC-regwind-au-01 |

- 전 노트 공통 인용: EC-krx-acl2025-01, EC-rynta-arch-01 (About OneLineAI 박스 한정. KRX 공동개발
  + ACL 2025 + RYNTA 아키텍처 1문장, 카드 승인 문구 범위 내).
- 전 노트 공통 요소: "as of August 2026" 날짜 기준 명시 + 하단 고지 "This note is for general
  information, not legal or compliance advice."
- 규제 서술은 전부 해당 카드의 [확인] 사실 범위 내. 체크리스트·실무 시사점은 본문에서
  "practical steps, in our words" 류로 규제 문언과 분리 표기(규제 격상 방지).

## 2. 사용 규칙 (발송 경로)

1. **수신자가 T3/T4에 긍정 답장("send it", "yes" 등)을 보내면**: PO가 해당 세그먼트 노트의
   상단 HTML 주석(INTERNAL 블록)을 제거하고 → PDF(A4, 2쪽)로 변환하고 → 회신 메일에
   첨부해 발송한다. **PDF 변환·첨부·발송은 전부 PO 몫이다. 에이전트·발송 도구가 첨부를
   보내지 않는다 [G1].**
2. **콜드 터치에 첨부 금지.** 이 노트는 답장 스레드(수신자 요청 기반)에서만 첨부한다.
   T1~T4 콜드 본문의 링크 0·첨부 0 원칙(copy/00-index §4-1)은 그대로 유효하다.
3. **변환 시 수정 금지.** 수치·주장 추가/삭제/개작 금지. About 박스와 고지문·날짜 기준은
   삭제 불가. 계정별 커스텀 금지(사실 왜곡 위험): 맥락화는 회신 메일 본문(커버 문장)에서만.
4. **회신 메일 본문**은 별도 초안(긍정 답장 처리·CTA 전환 문안) 요청 시 deal-strategist가
   작성하고 outreach-qa를 거친다. 노트 첨부와 미팅 시간 2개 제시를 한 회신에 결합 가능.

## 3. 발송 전 게이트 (fail-closed)

| # | 게이트 | 범위 | 상태 |
|---|---|---|---|
| 1 | outreach-qa 팩트체크 (노트 6종 전건, 특히 AU 원문 verbatim 대조) | 전 노트 | **대기** |
| 2 | legal-team 규제 해석 확인 (EC-regwind-* 5장 공통 선결, 카드 §5) | 전 노트 | 대기 (sales-compliance-officer 경유) |
| 3 | PO 발송 패키지 승인 + G4 보류 해제 | 전 노트 | 대기 |
| 4 | SG 트랙 착수 PO 승인 (compliance-frame-sg-au §9) | note-sg | 대기 |
| 5 | AU 컴플라이언스 프레임 확정 (Spam Act 증빙 5필드) | note-au | 대기 |

게이트 미충족 상태에서는 어떤 노트도 "발송 가능"으로 취급하지 않는다 [G3].

## 4. 재검증 트리거 (카드 개정 연동)

| 트리거 | 대상 | 액션 |
|---|---|---|
| MAS AIRG 확정 발표 | note-sg | **즉시 개정**: "proposed/finalised soon" 서술 전량 폐기, 확정본 기준 재작성 (EC-regwind-sg-01 §6) |
| NAIC 파일럿 종료(2026-09)·Fall National Meeting(2026-11) | note-us-insurance-am | 파일럿 상태·채택 관할 수 갱신 (EC-regwind-us-ins-01 §6) |
| APRA 원문 verbatim 대조 완료 | note-au | 직접 인용 허용 여부 반영, 요약 서술 완화 검토 (EC-regwind-au-01 §6) |
| FINRA 2027 보고서·SEC FY2027 우선순위 발표 | note-us-brokerdealers, note-us-insurance-am | 앵커 최신화 |
| 분기 재검증 (카드 공통) | 전 노트 | 카드 개정 시 인용 노트 전수 재점검 |

## 5. outreach-qa 전달 유의점

1. **T3-B(자산운용) 이행 정합성**: 카피 T3-B는 "SEC FY2026 노트"를 약속하는데 실물은
   보험·자산운용 통합 노트다. 제목이 두 청중을 모두 명시하고 자산운용 절이 자립적으로
   작성돼 있으나, (a) 이대로 수용 또는 (b) cold-email-writer가 T3-B 문구를 통합 노트에
   맞게 미세 조정, 중 판단 요청.
2. qa-review-master의 확정 지적 선반영: F-1(NAIC 관할 수 정밀 구분), F-3(수신자 주 파일럿
   참여 단정 없음), F-4(UK 적용 범위 정직 서술), I-2("as it applies to" 계열). 노트와 카피
   수정본 간 표현 정합 재확인 요청.
3. SR 21-8 대체 서술은 QA 재확인 전이라 note-us-banks에 미기재 (qa-review §7).
4. NAIC 파일럿 참여 12개 주 실명 목록은 2차 소스라 노트에 미기재("twelve states"까지만).
5. FINRA 프롬프트·출력 로깅 서술은 카드 §2-3 금지에 따라 FINRA 귀속 없이 "우리 실무
   제안"(기록 보존 결정) 프레임으로만 존재. 귀속 오독 여지 재확인 요청.

## 6. PO 결정 대기 항목 / PO가 직접 할 일

- **PO 결정 대기**: 게이트 3~5(§3), §5-1의 T3-B 이행 방식 선택.
- **PO가 직접 할 일**: 긍정 답장 수신 시 INTERNAL 주석 제거 → PDF 변환 → 회신 첨부 발송
  (§2). 발송 전 게이트 전건 충족 확인.

## 7. 운영 규칙

- 이 디렉터리 산출물은 검수·승인 전 워킹 파일이다. **git 커밋 금지.**
- 노트의 사실 주장 수정이 필요하면 카드를 먼저 개정하고 노트를 따라 고친다(카드 우선 원칙).
