---
name: sales-team
description: 원라인AI 세일즈 에이전트팀 하네스 진입점. 글로벌 타깃 콜드 아웃리치 캠페인, 발신 인프라 셋업, 딜 지원(미팅 준비·파일럿·ROI·보안 심사), 세일즈 운영 리뷰 요청이 들어오면 사용. 콜드 메일은 영어가 기본이고, QA·관할별 컴플라이언스·딜리버러빌리티 3중 게이트를 거치며, 발송과 최종 판정은 항상 PO가 한다.
---

# 세일즈 에이전트팀 (Sales Agent Team)

세일즈 요청을 받으면 이 하네스로 처리한다. 원라인AI PO의 founder-led
sales를 지원하는 글로벌 타깃 팀이며, 운영 절차는 `harness/sales/runbook.md`,
팀 구성과 품질 게이트(G1~G11) 전문은 `harness/sales/team.yaml`에 정의되어
있다.

## 처리 절차

1. **인테이크**: 캠페인이면 타깃 region·세그먼트·티어·목표를, 딜 지원이면
   계정·단계(prep/debrief/pilot/proposal/security)를 확정한다. 불명확하면
   착수 전에 사용자에게 묻는다(AskUserQuestion).
2. **KB 우선 참조**: `kb/sales/00-index.md`에서 관련 문서를 찾아 읽는다.
3. **착수 조건 확인**: 캠페인은 (1) 발신 인프라 셋업 완료 판정, (2) PO
   승인 서명이 있는 ICP 문서가 선행 조건이다. 없으면 캠페인 대신 해당
   선행 작업을 먼저 제안한다.
4. **요청 유형별 라우팅**:

   | 요청 유형 | 처리 방법 |
   |---|---|
   | 콜드 아웃리치 캠페인 | Workflow `cold-outreach-campaign` : args `{date, region, segment, tier, goal, list_source}` |
   | 발신 인프라 셋업·점검 | Workflow `outreach-infra-setup` : args `{date, target_daily_volume, providers, existing_domains}` |
   | 미팅·파일럿·제안·보안 심사 지원 | Workflow `deal-support` : args `{date, account, stage, ask, notes}` |
   | 주간 운영 리뷰 | Workflow `sales-ops-review` : args `{date, mode: "weekly"}` |
   | 캠페인 활성 기간 일간 점검·터치 릴리스 | Workflow `sales-ops-review` : args `{date, mode: "daily", campaigns}` |
   | 간단한 단일 질문 | Agent 도구로 해당 전문가 1명만 투입 (아래 표) |

   가벼운 질문에 워크플로 전체를 돌리지 않는다. 전문가 1~2명으로 답이
   되면 그렇게 한다. 단, Workflow 도구는 사용자가 멀티에이전트 실행에
   동의한 경우에만 사용한다. 워크플로 args의 `date`는 오늘 날짜
   (YYYY-MM-DD)를 넣어 호출한다.

5. **단일 전문가 매핑**:

   | 주제 | 에이전트 |
   |---|---|
   | 계획 수립·종합·PO 의사결정 큐 | `sales-lead` |
   | ICP 초안·리스트·계정 리서치·시그널 | `prospect-researcher` |
   | 터치맵·대체 채널·파트너 채널 | `channel-strategist` |
   | 콜드 메일 카피(영문)·시퀀스 문안 | `cold-email-writer` |
   | 카피 검수·팩트체크 | `outreach-qa` |
   | 관할별 규제 심사·LIA·suppression | `sales-compliance-officer` |
   | 발신 도메인·웜업·도달률·서킷브레이커 | `deliverability-engineer` |
   | 미팅 준비·자격검증·파일럿·ROI·보안 설문 | `deal-strategist` |
   | 지표·답장 분류·회고·CRM 스키마 | `sales-ops-analyst` |

## 품질 규칙 (모든 산출물에 적용)

- **G1 무발송 원칙**: 에이전트는 발송 도구를 실행하지 않는다. 발송
  패키지는 `docs/sales/outbox/`에 저장하고 발송·LinkedIn/전화 터치·최종
  승인은 PO가 한다. ICP 확정, 자격검증 최종 판정, LIA 승인, 회고
  확대/폐기 판정 등 PO 전속 결정(team.yaml 목록)은 판정란을 비워
  상신한다.
- **3중 게이트 fail-closed**: QA(G3) → 컴플라이언스(G2, 관할별
  매트릭스·LIA·한국 분기) → 딜리버러빌리티 프리플라이트(G5) PASS 기록
  없는 산출물은 "발송 가능" 상태로 전달하지 않는다. 게이트 기록은
  `docs/sales/compliance/`에 보존한다.
- **팩트 무결성**: 카피의 수치·고객명·성과 주장은
  `kb/sales/08-oneline-ai-context.md`의 [확인] 등급 또는 원출처 확인을
  거친 것만 쓴다. 미검증 주장은 1개라도 있으면 FAIL이다.
- **관할 규율**: "EU" 단일 세그먼트 금지, 국가 단위로 판정한다. 회피
  등급 국가(독일 등, 캐나다, 한국)는 콜드 메일 대신 대체 채널 플레이로
  접근한다. 경계 사안은 legal-team 하네스로 에스컬레이션하고 회신 전까지
  해당 레코드만 분리 보류한다.
- **산출물 경로**: 캠페인 작업물 `docs/sales/campaigns/<캠페인ID>/`, 딜
  지원 `docs/sales/deals/<계정슬러그>/`, 리포트·회고 `reports/sales/`,
  캠페인ID는 `YYYYMMDD-<region>-<slug>`.
