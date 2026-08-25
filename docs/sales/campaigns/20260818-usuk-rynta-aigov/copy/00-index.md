# 마스터 시퀀스 카피 인덱스 · RYNTA 글로벌 아웃리치

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/copy/00-index.md`
> 작성: cold-email-writer · 기준일: 2026-08-19 · 상태: 마스터 수정본 v1.1 (QA 1회차 반영, outreach-qa 재검수 대기)
> 근거: kb/sales/01(카피 원칙), docs/sales/deals/_evidence/(증거 카드), icp-draft.md §1·§5.2·§7, compliance-frame.md, compliance-frame-sg-au.md, templates/sales/multichannel-sequence.md

## ⚠️ 발송 불가 조건 (전 파일 공통, 파일 상단에도 명기)

이 디렉터리의 카피는 **마스터 버전**이다. 아래 전부 충족 전에는 어떤 터치도 발송할 수 없다 [G1][G3][G4]:

1. `{{...}}` 치환자 전건 충전 (계정 리서치 산출물 research/ 의 시그널·훅으로)
2. outreach-qa 11항목 게이트 PASS + sales-compliance-officer 게이트 PASS
3. PO 발송 패키지 승인 + G4 발송 보류 해제 기록
4. EC-regwind-usuk-01의 legal-team 규제 해석 확인 (US 은행·UK 세그먼트 선결)
5. 신규 규제 앵커(FINRA/SEC, NAIC, MAS, APRA)의 증거 카드 신설·등급 판정 (§5 미해결 사항)
6. T3에서 제안하는 "two-page note" 콘텐츠 자산의 실물 제작 (없는 자료를 제안하는 발송 금지)

## 1. 세그먼트별 파일

| # | 파일 | 세그먼트 | "왜 지금" 앵커 | 타깃 역할 | 관할 푸터 |
|---|---|---|---|---|---|
| 1 | `master-us-banks.md` | 미국 은행 (슈퍼리저널·미드사이즈) | 연준 SR 26-2: 생성형·에이전틱 AI 별도 거버넌스 지목 | CRO, Head of Model Risk, Head of AI Governance | US (CAN-SPAM) |
| 2 | `master-us-brokerdealers.md` | 미국 브로커딜러·자산관리 | FINRA 2026 감독보고서(AI 에이전트 모니터링) + SEC FY2026 시험 우선순위 | CRO, CCO, Head of AI | US (CAN-SPAM) |
| 3 | `master-us-insurance-am.md` | 미국 보험(변형 A) / 자산운용(변형 B) | A: NAIC AI 불레틴 + 12개 주 검사 파일럿 / B: SEC FY2026 시험 우선순위(어조 한 단계 낮춤) | CRO, Head of Enterprise Risk, CCO, AI 리더십 | US (CAN-SPAM) |
| 4 | `master-uk.md` | 영국 빌딩소사이어티·챌린저 | PRA SS1/23 원칙 4 (독립 모델검증) | CRO, Head of Model Validation | UK (PECR + UK GDPR 제14조) |
| 5 | `master-sg.md` | 싱가포르 디지털 은행·자산관리 플랫폼 | MAS AI 리스크 관리 가이드라인(AIRG) 확정 임박 + 12개월 전환기간 제안 | CRO, Head of Risk, Head of Tech Risk | SG (PDPA BCI + SCA 소량 트랙) |
| 6 | `master-au.md` | 호주 미드티어 은행·챌린저 | APRA AI 서한(시점·표본 어슈어런스 한계) + CPS 230 | CRO, Head of Model Risk, Head of Operational Risk | AU (Spam Act 3요건) |

## 2. 치환자 규약 (전 파일 공통)

| 치환자 | 의미 | 채움 규칙 | 소스 |
|---|---|---|---|
| `{{first_name}}` | 수신자 이름 | 검증된 인물 레코드의 이름 | list-build 레코드 |
| `{{account}}` | 기관명 | 제목줄에 쓸 때는 2단어 이하 축약형(초과 시 제목줄 후보 1~2 사용) | research/ 파일 |
| `{{signal_hook}}` | 계정 시그널 관찰 1문장 | **12~25단어, 상대에 대한 관찰로 시작.** research/§5 영문 훅 초안에서 가져오되 수치·사실은 리서치 파일에 출처가 있는 것만 | research/§5 |
| `{{role_context}}` | 수신자 직무 축약 | 2~4단어 (예: model validation, AI governance, agent supervision) | 인물 레코드 직함 |
| `{{sender_name}}` | 발신자 실명 | 실명 필수 (sales@ 류 금지) | PO 지정 |
| `{{caller_name}}` | 전화 실행자 이름 | 전화·보이스메일은 PO 실행 | PO |
| `{{company_postal_address}}` | 물리 주소 | US 필수(CAN-SPAM), SG·AU 푸터에도 사용 | PO 공급 |
| `{{company_registration_line}}` | 회사 등록 정보 라인 | UK 푸터 발신자 신원 요소 | PO·compliance-officer |
| `{{data_source}}` | 데이터 출처 | UK 제14조 고지용 (예: "Cognism, a business contact database") | list-build 레코드 data_source |
| `{{privacy_notice_url}}` | 프라이버시 노티스 URL | UK 첫 메일 필수 [G10]. 본문 링크 0개 원칙과 별개인 법정 푸터 링크 | compliance-officer |
| `{{unsubscribe_email}}` | 수신거부 접수 주소 | SG SCA 대량 기준 도달 대비 | PO |
| `{{sender_email}}` | 발신자 연락처 | AU 발신자 식별(발송 후 30일 정확·유효) | PO |

## 3. 표준 터치맵 슬롯 (전 세그먼트 공통, G11)

| 터치 | Day | 채널 | 실행 주체 | 프레임워크 | 스레드 |
|---|---|---|---|---|---|
| T1 | 1 | Email 1 | 발송 도구 | PAS | 새 스레드 |
| L1 | 3 | LinkedIn 커넥션 노트 | **PO** | - | - |
| T2 | 5 | Email 2 | 발송 도구 | BAB + 증거 카드 1장 | 같은 스레드 (Re:) |
| C1 | 8 | 전화 → 부재 시 보이스메일 | **PO** | - | - (SG는 전화 금지, LinkedIn DM으로 대체) |
| T3 | 12 | Email 3 | 발송 도구 | 가치 제공형 (링크 0개) | 같은 스레드 (Re:) |
| T4 | 18 | Email 4 | 발송 도구 | 브레이크업 | **새 스레드 허용** |

- 이메일 4통, 이메일 단독 5터치 이상 아님 [G11]. 같은 날 같은 채널 중복 없음.
- LinkedIn 후속 DM 1건은 커넥션 **수락 후** L1 슬롯의 연속 동작으로 PO가 실행한다(새 터치 추가 아님, 권장 시점 Day 8~10).
- 터치 2~N 릴리스 전 `templates/sales/touch-release-checklist.md` PASS + suppression 델타 재대조 [G2][G5].

## 4. 사용 규칙

1. **링크 정책**: 전 이메일 본문 링크 0개, 이미지·첨부 0개. OLAF 허깅페이스 링크는 URL 확정 전 사용 금지(EC-olaf-v2-perf-01)라 이번 버전 T3도 링크 0개, "reply to receive" 방식. UK 푸터의 프라이버시 노티스 링크는 법정 고지 요소로 예외 [G10].
2. **스레드 전략**: T1~T3 같은 스레드 유지, T4 브레이크업만 새 스레드. 스팸함 착지 신호 시 리셋은 deliverability-engineer 협의 후.
3. **한국 수신자 사용 금지 [G7]**: 이 마스터는 한국 수신자에게 어떤 형태로도 재사용할 수 없다. 한국은 건별 개별 작성(1:1 사업 제안 서신체)만 가능하며 C/D 유형은 작성 거부 대상이다.
4. **일본 수신자**: 콜드 메일 트랙 아님. 파트너 채널(민카부)로 이관 (compliance-frame-sg-au §3).
5. **SG 채널 제한**: 전화·SMS 터치 금지(DNC 미대조, compliance-frame-sg-au §1.1). C1 슬롯은 LinkedIn DM으로 대체.
6. **SG 볼륨 감시**: 시퀀스 자동화 포함 누적 발송량이 SCA 대량 기준(100/24h, 1,000/30d, 10,000/1y)의 80%에 도달하면 알림, 초과 예상 시 <ADV> 요건 전면 적용 또는 볼륨 축소로 사전 전환.
7. **A/B 변형**: 이번 버전에는 없음. 요청 시 단일 변수만 바꾼 변형 + 가설 기록으로 작성한다. 판정 지표는 답장률.
8. **어조**: 자산운용(변형 B)은 구속력 규칙이 없으므로(SEC 예측분석 규칙 철회) 규제 강도를 과장하지 않고 어조를 한 단계 낮춘다.
9. **git 커밋 금지**: 이 산출물은 검수·승인 전 워킹 파일이다.

## 5. 미해결 사항 (outreach-qa · sales-lead 전달)

| # | 사항 | 블로킹 범위 | 처리 주체 |
|---|---|---|---|
| 1 | EC-regwind-usuk-01 legal-team 규제 해석 확인 미완 | US 은행·UK 세그먼트 발송 | sales-compliance-officer 경유 legal-team |
| 2 | FINRA 2026 보고서·SEC FY2026 시험 우선순위 증거 카드 미등재 (리서치 파일에 출처는 검증됨: research/us-d1 §2 등) | 브로커딜러·자산운용 세그먼트 발송 | deal-strategist (카드 신설, 가칭 EC-regwind-us-bd-01) |
| 3 | NAIC AI 불레틴(채택 약 25개 주 + DC)·12개 주 검사 파일럿 카드 **EC-regwind-us-ins-01 등재 완료(2026-08-19)**, legal-team 확인 대기 | 보험 세그먼트 발송 | sales-compliance-officer 경유 legal-team |
| 4 | MAS AIRG 컨설테이션·확정 임박·12개월 전환기간 증거 카드 미등재 (research/sg-s1 §2 검증) | SG 세그먼트 발송 | deal-strategist (가칭 EC-regwind-sg-01) |
| 5 | APRA AI 서한(2026-04-30)·CPS 230 증거 카드 미등재 (research/au-b1·b2 §2 검증, 단 2차 해설 출처) | AU 세그먼트 발송 | deal-strategist (가칭 EC-regwind-au-01) |
| 6 | T3 제공 자산("two-page note" 세그먼트별 5종 + SG 체크리스트) 실물 미제작 | 전 세그먼트 T3 발송 | sales-lead 배정 |
| 7 | UK LIA 문서 ID·보관기한, {{privacy_notice_url}} 미공급 | UK 발송 | sales-compliance-officer |
| 8 | AU 전화 터치의 텔레마케팅 규범(DNCR) 층위 확인 | AU C1 슬롯 | sales-compliance-officer |
| 9 | SG/AU 트랙 착수·볼륨 상한 PO 승인 대기 (compliance-frame-sg-au §9) | SG·AU 세그먼트 | PO |

## 6. 증거 카드 사용 요약 (주장 ↔ 카드)

| 주장 | 카드 | 사용 세그먼트 |
|---|---|---|
| SR 26-2가 생성형·에이전틱 AI를 별도 거버넌스로 지목 / SS1/23 원칙 4 독립검증 | EC-regwind-usuk-01 | US 은행, UK |
| NAIC 불레틴 채택 확산(more than 25 jurisdictions, 약 25개 주 + DC) + 12개 주 검사 파일럿 | EC-regwind-us-ins-01 (legal-team 확인 대기) | 보험 A (T1, T3, DM, 전화) |
| RYNTA 3층 구조·가드레일·감사 추적 (아키텍처 서술만) | EC-rynta-arch-01 | 전 세그먼트 |
| KRX-Bench, 약 233팀·1,100개+ 모델 평가 기준 | EC-krx-bench-01 | US 은행, 브로커딜러, 보험 A, UK, AU (AU는 T2 + LinkedIn 노트) |
| KRX 공동개발 모델 ACL 2025 게재 | EC-krx-acl2025-01 | 자산운용 B, SG, LinkedIn 노트 (US 은행·브로커딜러·보험·자산운용·UK·SG. AU 노트는 EC-krx-bench-01 사용) |
| 미사용 (이번 버전) | EC-minkabu-01 (SG T3 문장 삭제, QA §5.3 F-2), EC-kmmlu-01, EC-founder-team-01, EC-kr-references-01(익명), EC-olaf-v2-perf-01 | 디스커버리·트러스트 패키지 단계용으로 보존 |

## 7. 변경 이력

- 2026-08-19 v1.1 (cold-email-writer, QA 1회차 반려 반영): §6 AU LinkedIn 노트 카드 매핑을 EC-krx-bench-01로 수정(QA §7 지적), EC-minkabu-01 미사용 전환(SG T3 문장 삭제), EC-regwind-us-ins-01 사용 행 추가, §5-3 관할 수 표기·카드 등재 상태 갱신.
