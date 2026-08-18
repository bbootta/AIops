# 세일즈 에이전트팀 운영 런북

세일즈 요청이 들어왔을 때 팀을 어떻게 돌리는지 정의한다. 오케스트레이터
(메인 세션)가 이 런북대로 에이전트를 투입한다. 팀 구성과 품질 게이트
전문은 `harness/sales/team.yaml`, 지식베이스는 `kb/sales/00-index.md`.

## 대전제 (모든 시나리오)

1. **에이전트는 발송하지 않는다 (G1)**: 모든 대외 발신물은
   `docs/sales/outbox/`에 발송 패키지로 저장되고, 발송·LinkedIn/전화 터치
   실행·최종 승인은 PO가 한다.
2. **KB 우선**: `kb/sales/00-index.md`에서 관련 문서를 찾아 읽고 시작한다.
3. **PO 전속 결정**: ICP 확정, 자격검증 최종 판정, LIA 승인, 발송 승인,
   서킷브레이커 실행, 회고 확대/폐기 판정은 에이전트가 내리지 않는다.
   초안·채점·권고까지 만들고 판정란을 비워 상신한다.
4. **게이트는 fail-closed**: QA(G3)·컴플라이언스(G2)·프리플라이트(G5)
   PASS 기록 없는 산출물은 "발송 가능" 상태로 PO에게 올라가지 않는다.
5. **카피는 영어, 보고는 한국어**: 아웃리치 산출물(제목줄·본문·시퀀스)은
   영어가 기본이다. 한국 수신자만 예외적으로 건별 개별 국문 작성(G7).

## 시나리오 A : 발신 인프라 셋업 (캠페인 개시 최소 2~4주 전 선행)

> 예: "아웃바운드 시작하려고 해", "발신 도메인 세팅해줘"

1. `deliverability-engineer`: 볼륨 역산으로 도메인·메일박스 구성 설계
   (루트 도메인 onelineai.com 발송 금지), DNS 인증 명세(SPF/DKIM/DMARC),
   웜업 스케줄, 발송 도구 안전장치 설정 명세
2. `sales-compliance-officer`: 전역 suppression 저장소와 수신거부 처리
   플로우, EU 보관기간 정책 확인
3. `sales-lead`: 준비 완료/미완료 판정 보고. 미완료 항목은 캠페인 착수
   차단 목록으로 PO에 보고
- **워크플로**: `.claude/workflows/outreach-infra-setup.js`
- 이 워크플로의 완료 판정 없이 시나리오 B는 발송 단계로 갈 수 없다.

## 시나리오 B : 콜드 아웃리치 캠페인

> 예: "미국 자산운용사 리서치팀 대상으로 캠페인 돌려줘"

1. `sales-lead`: 캠페인 브리프. 착수 조건: PO 승인 서명이 있는 ICP 문서
   (초안 상태면 착수 중단), 인프라 셋업 완료, region 관할 판정
   (회피 등급 국가면 대체 채널 트랙으로 분기)
2. `prospect-researcher`: 리스트 구축·검증, 관할·출처·증빙 태깅(G9),
   Tier 1~2 전건 계정 리서치(G4), suppression 대조
3. `channel-strategist`: 멀티채널 터치맵(G11: 이메일 3~4통 + LinkedIn/전화
   슬롯), 회피 등급 레코드는 대체 채널 플레이로 이관
4. `cold-email-writer`: 터치맵 전 채널 영문 카피 (증거 카드만 인용)
5. `outreach-qa`: 11항목 게이트 + 팩트체크 + 시퀀스 구조 검수(G3).
   FAIL이면 4단계로 반려, 최대 2회 루프
6. `sales-compliance-officer`: 게이트 A/B/C 심사(G2), EU/영국이면 LIA
   초안 작성 후 PO 승인 상신(G10), 한국 수신자면 KB06 §8 분기(G7)
7. `deliverability-engineer`: 프리플라이트(G5)와 발송 스케줄 배정
8. `sales-lead`: 발송 패키지 조립 → `docs/sales/outbox/<캠페인ID>/` 저장
   → PO 승인 요청. **발송은 PO가 한다**
- **워크플로**: `.claude/workflows/cold-outreach-campaign.js`

## 시나리오 C : 발송 활성 기간 운영 (터치 릴리스 게이트)

캠페인 개시·볼륨 증량 후 3일간, 그리고 후속 터치(2~N) 발송 예정일마다
`sales-ops-review`를 **daily 모드**로 돌린다:

1. `deliverability-engineer`: 도달 지표 점검, 서킷브레이커 판정(G6).
   임계 초과 시 즉시 PO에 중단 실행 요청
2. `sales-ops-analyst`: 답장 로그 분류(긍정/부정/OOO/수신거부성),
   시퀀스 제외 목록 갱신
3. `sales-compliance-officer`: suppression 델타 재대조, 발송 도구 동기화
   정합성 확인(G2)
4. `sales-lead`: 터치 릴리스 가능/차단 현황 보고.
   touch-release-checklist PASS 없이 해당 터치는 발송 불가(G5)
- **워크플로**: `.claude/workflows/sales-ops-review.js` (mode: daily)

## 시나리오 D : 딜 지원 (미팅·파일럿·제안·보안 심사)

> 예: "내일 A사 디스커버리 콜 준비해줘", "파일럿 제안서 만들어줘"

1. `sales-lead`: 요청 분류(prep/debrief/pilot/proposal/security)
2. `prospect-researcher`: (필요 시) 계정 최신 시그널 갱신
3. `deal-strategist`: 단계별 산출물. debrief면 SPICED 채점 초안 +
   판정 권고, **최종 판정(진행/조건부/탈락)은 PO 판정란에 위임**(G8)
4. `outreach-qa`: 대외 전달물 팩트체크. 규제 해석이 걸린 답변은
   `sales-compliance-officer` 경유 legal-team 확인
5. `sales-lead`: 종합. 상단에 "PO가 직접 할 일 / PO 결정 대기 /
   에이전트가 준비한 것" 구분 표기
- **워크플로**: `.claude/workflows/deal-support.js`

## 시나리오 E : 주간 운영 리뷰

매주 `sales-ops-review`를 **weekly 모드**로: 3층 지표 리포트, 파이프라인
위생 플래그(다음 단계 없는 딜, 싱글스레드 딜), 시그널 스캔과 티어 상향
후보, 블랙리스트·Postmaster 점검, 격주 캠페인 회고, 규제 개정 모니터링.
최상단에 "PO가 이번 주 할 일"을 배치한다.

## 에스컬레이션 규칙

다음은 에이전트가 결론 내리지 않고 PO 또는 legal-team으로 올린다:

- 규제 해석이 갈리는 경계 사안 → legal-team (회신 전 해당 레코드 발송
  금지, 잔여 레코드는 부분 진행)
- 서킷브레이커 임계 초과 → PO 즉시 보고 (중단 실행은 PO)
- KB08 "확인 필요" 항목에 의존하는 카피 주장 → 창업팀 확인 전 사용 금지
- 개인정보 침해 소지가 있는 리서치 요청(비공개 정보 수집 등) → 수행하지
  않고 사유 보고

## KB 유지보수

- KB 기준일은 `kb/sales/00-index.md`에 기록되어 있다.
- 분기 1회 또는 큰 규제·정책 이벤트 후 해당 KB를 재조사·갱신한다.
- 캠페인 회고에서 나온 학습(잘 먹힌 앵글, 실패 패턴)은
  `sales-ops-analyst`가 KB 갱신 제안으로 만든다.
- `kb/sales/08-oneline-ai-context.md`의 "확인 필요" 목록은 창업팀 확인을
  받는 대로 소거하고 갱신일을 기록한다.
