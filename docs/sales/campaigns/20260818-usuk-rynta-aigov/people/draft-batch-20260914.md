# Gmail 초안 배치 기록: 신규 50명 (2026-09-14)

> 작성: sales-lead · PO 요청 "신규로 50명을 검색해서 그들에게 보낼 초안을 만들어줘"
> 원천: 본 디렉터리 인물 특정 파일 4종 (us-banks-1/2, us-brokers, us-insurance-am)
> 카피: copy/ 마스터 v1.1 T1 (세그먼트별) + 인물별 시그널 훅 충전
> 상태: **Gmail 초안함에 50건 생성 완료. 전건 수신자(To) 공란.**

## 0. 규칙 준수 기록

- 이메일 주소는 어떤 초안에도 넣지 않았다. 이 50명의 검증된 주소가 존재하지 않으며,
  패턴 추정은 목록 구축 원칙(list-build-spec §0) 위반이자 바운스로 발신 도메인을
  손상시킨다. 주소는 PO가 도구(ZoomInfo/Cognism/Lessie)로 추출해 채운다.
- 각 초안 첫 줄에 `[TO: 이름, 직함, 기관 | email via ZoomInfo | delete this line
  before sending]` 헤더를 넣어 수신자 식별이 가능하다. 발송 전 이 줄을 지운다.
- 미국행 전건 푸터에 `[postal address: replace before sending]` 자리가 있다
  (CAN-SPAM 물리 주소 필수).
- 발송 여부·순서·볼륨은 PO 전속 [G1]. 권장: 주 발신 도메인 보호를 위해 일 15~20건
  이하로 분산.

## 1. 선정 기준

- 오늘(2026-09-14) 특정한 113명 중 **미국 관할 + 적합도 강·중**만.
- 제외: 진행 중 시퀀스와 겹치는 기관(Raymond James, Fifth Third), 후보 등급
  (재검증 전 발송 불가), 관할 불명(IBKR Clarke), 재확인 미완 다수 항목 인물 14명,
  UK(LIA·프라이버시 노티스 미공급으로 발송 게이트 미충족), SG/AU(트랙 PO 승인 대기).
- 시그널 유효기간(G4): 8월 조사분 기준 2026-09-17~18 만료. 이번 주 발송이면 유효,
  이후면 훅 재확인 필요.

## 2. 세그먼트 구성 (50명)

| 세그먼트 | 제목줄 | 인원 |
|---|---|---|
| US 은행 (SR 26-2 앵커) | sr 26-2 and model inventory | 31 |
| US 브로커딜러 (FINRA 2026 앵커) | finra 2026 report and ai agents | 6 |
| US 보험 (NAIC 파일럿 앵커) | naic ai evaluation pilot | 10 |
| US 자산운용 (SEC 시험 앵커) | sec 2026 exam priorities | 3 |

## 3. 명단

### US 은행 31
Citizens: Richard Stein (CRO), Krish Swamy (CDAO) · Regions: Russ Zusi (CRO), Manav Misra (CDAO) · Pinnacle: Shellie Creson (CRO) · Synchrony: Nimrod Barak (CAIO), Paul Whynott (CRO) · Huntington: Senthil Kumar (CRO), Zach Wasserman (CFO/AI) · Truist: Brad Bender (CRO), Chandra Kapireddy (GenAI/ML) · PNC: Amy Wierenga (CRO), Ned Carroll (Data/Automation) · First Citizens: Tom Eklund (CRO), Scott Richardson (CDAO), Ash Kaduskar (Head of AI) · Old National: Scott Evernham (CRO), Matt Keen (CIO) · Schwab: Nigel Murtagh (CRO), Dennis Howard (CTO/Data) · U.S. Bancorp: Jodi Richard (CRO), Prashant Mehrotra (CAIO) · Western Alliance: Emily Nachlas (CRO), Sonny Sonnenstein (CIO) · First Horizon: Ashley Argo (CRO), Scott Serpico (Product), Catherine Wood (Strategy) · Valley: John Regan (CRO), Sanjay Sidhwani (CDAO) · Associated: Nicole Kitowski (CRO), Alexander Bush (CDO)

### US 브로커딜러 6
IBKR: Jonathan Gelman (CCO) · Edward Jones: Frank LaQuinta (Digital/Data/Ops) · LPL: Brent Simonich (CRO), Vaughn Harvey (CDAIO), Beth Hiatt (Responsible AI) · Stifel: James Marischen (CFO/CRO)

### US 보험 10
MetLife: Marlene Debel (CRO), Tamar Shapiro (CDAO) · Prudential: Bob Bastian (CDAIO), Meyrick Douglas (CRO) · Allstate: Mark Prindiville (CRO), Steven Armstrong (Chief Actuary) · Lincoln: Neel Adhya (CAIDAO), Paul Spurr (CRO/Chief Actuary) · MassMutual: Geoff Craddock (CRO), Sears Merritt (CIO)

### US 자산운용 3
T. Rowe Price: Vinit Agrawal · Franklin Templeton: Deep Ratna Srivastav · AllianceBernstein: Andrew Chin

## 4. 다음 단계

1. PO: 위 50명 주소를 도구로 추출·검증 → 세션에 붙여넣으면 To 필드 일괄 충전.
2. PO: 회사 우편 주소 1회 공급 → 푸터 자리 일괄 교체.
3. 발송 분산(일 15~20건), 바운스 2% 초과 시 중단 (KB05 서킷브레이커 기준 준용).
