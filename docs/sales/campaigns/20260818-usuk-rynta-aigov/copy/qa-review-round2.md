# QA 검수 기록 2회차: 카피 v1.1 재판정 + T3 노트 6종 팩트체크

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/copy/qa-review-round2.md`
> 검수: outreach-qa · 검수일: 2026-08-19 · 루프 회차: **2회차** (1회차 기록: qa-review-master.md)
> 범위: (A) 마스터 카피 v1.1 수정분 재판정 (T2/T3 전 세그먼트 14건 + 보험 T1-A/T1-B, diff 전량 확인) · (B) assets/ 노트 6종 팩트체크 (EC-regwind-* 카드 5장 + 2026-08-19 웹 재검증 대조)
> git 커밋 금지 대상 워킹 파일.

---

## 1. 종합 판정

**PASS_WITH_FIXES** : 1회차 반려 6건 전건 반영 확인(수정 부작용 0건), 노트 6종 팩트체크 전건 일치(사실 FAIL 0건). 잔여 수정 1건: T3-B/T4-B 문구를 통합 노트에 맞게 미세조정(§5 R-1). 그 외는 전부 비차단 권고.

- 이 판정은 **QA 게이트 판정이지 발송 승인이 아니다** [G1]. 발송·터치 실행·최종 승인은 PO 몫.
- 치환자 미충전 마스터 상태의 판정. 계정 충전본은 터치 릴리스 전 재검수 대상 [G3][G5].
- 2회차가 FAIL이 아니므로 sales-lead 캠페인 재설계 규칙은 발동하지 않는다. R-1은 경수정이며 반영분은 diff 스팟 확인으로 종결한다(3회차 전량 재검수 불요).

## 2. (A) 카피 v1.1 재판정: PASS

### 2.1 수정 터치 16건 재계수 (QA 직접 계수, writer 병기 수치 대조)

| 터치 | 병기 단어 수 | QA 실측 | you:self 병기 | QA 실측 | CTA | 판정 |
|---|---|---|---|---|---|---|
| US은행 T2 | 86 | 86 | 3:2 | 3:2 (your team·your reviewers·your roadmap vs our·we) | 1 | PASS |
| US은행 T3 | 61 | 61 | 3:2 | 3:2 | 1 | PASS |
| BD T2 | 85 | 85 | 3:2 | 3:2 (your AI supervision·your agent rollout·to you vs we're·we) | 1 | PASS |
| BD T3 | 68 | 68 | 3:2 | 3:2 | 1 | PASS |
| 보험 T1-A | 고정 90 (102~115) | 90 | - | 1+훅 : 0 | 1 | PASS |
| 자산운용 T1-B | 고정 76 (88~101) | 76 | - | 1+훅 : 0 | 1 | PASS |
| 보험 T2-A | 85 | 85 | 3:2 | 3:2 | 1 | PASS |
| 자산운용 T2-B | 75 | 75 | 3:2 | 3:2 | 1 | PASS |
| 보험 T3-A | 63 | 63 | 3:2 | 3:2 | 1 | PASS |
| 자산운용 T3-B | 63 | 63 | 3:2 | 3:2 | 1 | PASS (문구 R-1) |
| UK T2 | 79 | 79 | 3:2 | 3:2 | 1 | PASS |
| UK T3 | 64 | 64 | 3:2 | 3:2 | 1 | PASS |
| SG T2 | 72 | 72 | 3:2 | 3:2 | 1 | PASS |
| SG T3 | 66 | 66 | 3:2 | 3:2 | 1 | PASS |
| AU T2 | 82 | 82 | 3:2 | 3:2 | 1 | PASS |
| AU T3 | 62 | 62 | 3:2 | 3:2 | 1 | PASS |

- 병기 수치와 QA 실측 16/16 완전 일치(1회차의 ±1 오차도 이번 재계수 구간에서는 0건). 전 터치 50~125 구간 내(T1은 훅 12~25 합산 기준).
- you:self 전 터치 you > self, 동수 0건. 1회차 게이트 5 FAIL(T2·T3 전 세그먼트) **해소 확정**.
- CTA 각 1개, interest-based 유지. 링크 0 유지.

### 2.2 F-1 해석 판정: "more than 25 jurisdictions" **허용**

- 카드 EC-regwind-us-ins-01 §5의 금지는 ① "불레틴이 29개 관할에 채택됐다"는 범주 합산 부풀림, ② "약/roughly" 없는 관할 수 **단정**이다. "more than 25 jurisdictions"는 점추정 단정이 아니라 **보수적 하한 표현**으로, 헤지 기능상 "roughly"와 동등하며 카드 §4 정합성 플래그가 요구한 "채택(약 25개 주 + DC)과 합산 29의 구분"을 정확히 지킨다.
- 사실 대조(2026-08-19 웹 재확인): 채택 = 25개 주 + DC = **26개 관할** (Quarles·aipmo Q2 2026 현황, 추가 8개 주 진행 중). 26 > 25이므로 참이고, 채택 수는 증가 추세라 하한 표현의 안전 마진도 유지된다.
- 조건: 카드 §6의 분기 갱신 규칙 유지. 발송 시점에 채택 수가 하향 정정되는 이례 상황 발생 시 재검토(가능성 낮음).
- 노트(note-us-insurance-am)의 "roughly 25 states plus DC" 서술과도 정합.

### 2.3 SG T3 시퀀스 정합 (Minkabu 문장 삭제 후)

- PASS. 삭제 후 구조 = 오프너("something worth having either way") + 노트 서술 + reply-to-receive CTA. 고아 참조 없음, 새 가치(readiness note) 1개 유지, ACL 신뢰 훅은 T2에 존치. you:self 1:4 → 3:2 동시 해소 확인.
- copy/00-index §6에서 EC-minkabu-01 미사용 전환 기재 확인. 카드 자체는 디스커버리 단계용 보존, 적정.

### 2.4 1회차 지적 반영 diff 확인 (6건 전건) + 부작용 검사

| 1회차 지적 | 반영 확인 |
|---|---|
| 1. 보험A T1 "roughly 29" 수정 | 반영 (권장안 (a) "more than 25 jurisdictions", §2.2 판정 허용) |
| 2. T2·T3 전 세그먼트 you:I | 반영 (전건 3:2, §2.1 실측) |
| 3. SG T3 "across Asia" 삭제 | 반영 (문장 삭제, §2.3) |
| 4. 보험A T3 "before your state joins in" | 반영 ("before an exam letter arrives", 파일럿 12개 주 소재 계정에도 사실 정합) |
| 5. 관용성 I-1~I-4 (+선택 I-5) | 반영: I-1 (T1-B "Worth comparing with how you handle this today?"), I-2 (UK T3 "as it applies to"), I-3 (콜 오프닝 6종 전건 "and you can tell me"), I-4 (UK 푸터 §8.1·§8.2 "you won't hear from me again"), I-5 채택 (BD T2 "Since we're probably a new name to you") |
| 6. copy/00-index §6 AU 노트 매핑 | 반영 (EC-krx-bench-01로 수정, EC-regwind-us-ins-01 행 추가 확인) |

- 수정 과정의 부작용(새 안티패턴, 링크 추가, CTA 증식, 제목줄 변경, 팩트 이탈): **0건**. 제목줄·T4·푸터(UK I-4 제외)·LinkedIn 카피는 무변경 확인.
- 경미 관찰(비차단): 보험 T2-A 오프너 "Today your AI inventory..."는 T2-B("Today, your...")와 달리 쉼표 없음. 문법상 허용, 통일은 선택.

## 3. (B) 노트 6종 팩트체크: PASS (사실 FAIL 0건)

### 3.1 카드 대조 결과 (규제 서술 전수)

| 노트 | 대조 카드 | 카드 범위 밖 주장 | 판정 |
|---|---|---|---|
| note-us-banks | EC-regwind-usuk-01 | 0건. SR 26-2 발효일(2026-04-17)·3개 기관·SR 11-7 대체·$30bn 관련성·생성형/에이전틱 범위 밖·전통 검증 유지 전부 카드 §2-1 내. SR 21-8 대체는 의도적 미기재(1회차 §7 권고 준수, 안전) | PASS |
| note-us-brokerdealers | EC-regwind-us-bd-01 | 0건. WSP 3주제(거버넌스·벤더 리스크·에이전트 모니터링), GenAI 권고 4항, "첫 AI 에이전트 관찰", SEC FY2026(2025-11-17) 전부 카드 §2 내. "asks/recommends, not requires" 명문화로 격상 금지 준수 | PASS |
| note-us-insurance-am | EC-regwind-us-ins-01 | 0건. 불레틴(2023-12) 요구 5항, 채택 약 25주+DC / 자체 프레임 4주(CA·CO·NY·TX) / 합산 roughly 29 정밀 구분(F-1), 파일럿 4익시빗·2026-03~09·2026-11 채택 검토, 파일럿 12개 주 실명 미기재, PDA 철회(2025-06-12)·"no binding rule" 정직 병기 전부 카드 정합 | PASS |
| note-uk | EC-regwind-usuk-01 | 0건. SS1/23 발효(2024-05)·5원칙·원칙 4, 적용 범위(내부모형 승인 기관) 정직 서술 + 비적용 기관 무의무 명시(F-4 반영). 원칙 4 외 개별 원칙 미서술(카드 한계 준수) | PASS |
| note-sg | EC-regwind-sg-01 | 0건. 컨설테이션 2025-11-13·마감 2026-01-31, 국회 답변 2026-08-05("will be finalised soon"), 12개월 전환 "proposed" 병기, 2024-12 정보문서 모범 관행, 확정 전 현재형 의무 단정 0건 | PASS |
| note-au | EC-regwind-au-01 | 0건. 서한 2026-04-30·최초 AI 특정·표적 검토(은행·보험·수퍼), "not keeping pace" 요약 서술, 어슈어런스 한계는 "in substance" 요약 프레임, CPS 230(2025-07-01 시행, 기존 계약 전환 2026-07-01 종료), ASIC REP 798(2024-10) 전부 카드 §2 내 | PASS |

공통 요소: About 박스(₩ON=Won KRX 공동개발 + ACL 2025 + RYNTA 아키텍처 1문장)는 EC-krx-acl2025-01·EC-rynta-arch-01 승인 범위 내. "as of August 2026" 기준일 + 비자문 고지 전 노트 부착 확인.

### 3.2 웹 재검증 (2026-08-19)

| # | 항목 | 결과 |
|---|---|---|
| 1 | SR 26-2 서술 | **일치.** Fed SR2602 페이지·PDF + Sullivan & Cromwell·Baker Tilly: 2026-04-17, Fed·FDIC·OCC 공동, SR 11-7(및 SR 21-8) 대체, $30bn 초과 기관에 가장 관련, 생성형·에이전틱 범위 밖·별도 거버넌스, 핵심 원칙 재확인 |
| 2 | NAIC 채택 수 | **일치.** 채택 25개 주 + DC = 26개 관할(mid-2026), 8개 주 진행 중. 노트 "roughly 25 states plus DC" + 카피 "more than 25 jurisdictions" 모두 정합. 합산 roughly 29(자체 프레임 4주 포함)도 카드·1회차 실측과 일치 |
| 3 | MAS AIRG "proposed" 유지 | **적정.** 2026-08 현재 확정본 미발행 확인(컨설테이션 상태 지속, 2026-03 MindForge 툴킷은 별건). 노트의 "proposed/will be finalised soon" 서술 유지가 맞다. 확정 발표 시 즉시 개정 트리거(assets/00-index §4) 유효 |
| 4 | APRA 서한 | **일치.** 2026-04-30, 최초 AI 특정 서한, 표적 감독 검토, "governance, risk management, assurance and operational resilience not keeping pace with scale, speed, complexity" 복수 2차 교차(Kennedys·Clayton Utz·MinterEllison·regulationtomorrow). **원문 전문 직접 열람은 이번에도 프록시 차단으로 실패** → verbatim 대조 미완 유지, 직접 인용 금지 원칙 존속 |
| 5 | AU 직접 인용 0건 | **확인.** note-au에 APRA 귀속 따옴표 인용 0건. 본문 내 따옴표 2곳("we checked it last year", "working now")은 가상 내부 답변·자체 정의로 APRA 귀속 아님. "our summary, not APRA's text" 이중 방어 명기 확인 |
| 6 | CPS 230·REP 798 | **일치.** 시행 2025-07-01, 기존 중요 서비스 제공자 계약 전환 2026-07-01 종료·전면 적용. REP 798은 2024-10-29 발행. 참고: 2026-04-30 APRA가 일부 비전통 제공자(중앙은행·결제 스킴 등) 한정 예외 개정을 냈으나 노트의 "applies in full" 서술을 뒤집는 수준 아님(§4 O-4 카드 개정 권고) |
| 7 | FINRA "첫 AI 에이전트 관찰" | **일치.** "For the first time, the 2026 Report discusses the risks of AI agents"(Debevoise 계열), WSP 3주제 원문 "advises members to make sure their WSPs cover" 교차. 발행 2025-12-09 |

### 3.3 FINRA/SEC 귀속 정확성 ("우리 제안" vs 규제 요구 구분)

**PASS.** note-us-brokerdealers는 3중 방어가 정확히 작동한다: ① 도입부 "observations and effective practices, not a new rulebook. The accurate verbs are 'asks' and 'recommends,' not 'requires.'" ② 체크리스트 헤더 "practical preparation steps, in our words. They are not a restatement of FINRA or SEC language." ③ 체크리스트 7번(기록 보존 결정)은 "our practical suggestion rather than regulator language"로 추가 명시. 프롬프트·출력 로깅 서술은 노트 전체에 부재(카드 §2-3 금지 준수). 다른 노트도 동일 패턴("practical steps, in our words", "Our practical reading", "not supervisory language") 확인.

### 3.4 톤 검사 (교육적 중립성)

**PASS.** 제품 언급은 전 노트 About 박스 밖 0건. "규제가 우리를 요구한다" 류 단정 0건. 오히려 반대 방향의 정직 서술이 일관됨: "The guidance names the gap; it does not fill it"(US은행), "not a new rulebook"(BD), "this is a pilot, not a settled exam regime"·"There is no deadline forcing this work"(보험/AM), "nothing in this note creates an obligation... a choice, not a requirement"(UK), "the word 'proposed' matters throughout"(SG), "Neither mandates a particular tool or method"(AU). 수신자 기관 위반·미준비 단정 0건. SG 노트의 "this checklist is an export... it is a project" 문장은 제품 무언급의 일반 서술로 허용 범위.

### 3.5 T3-B 이행 정합 판정 (assets/00-index §5-1 판단 요청)

**판정: (b) 문구 미세조정 필요.** 근거:

- 카피 T3-B는 "a two-page note **for advisers and asset managers** on the AI items in the SEC's FY2026 exam priorities"를 약속하는데, 실물은 보험·자산운용 통합 노트이고 본문 비중은 보험(NAIC·파일럿)이 과반이다. 약속 내용 자체는 노트의 자산운용 절이 전부 이행하므로 **허위·환각 아님**(FAIL 아님). 그러나 "for advisers and asset managers"는 노트의 실제 청중 구성과 어긋나 수신 시 기대 불일치를 만든다.
- T4-B "The two-page **SEC exam note**"도 같은 문제: 노트 제목은 SEC 단독 노트로 읽히지 않는다.
- 수정 방향(cold-email-writer, 예시): T3-B `a two-page note for advisers and asset managers on...` → `a two-page note covering AI oversight for insurers and asset managers, including the AI items in the SEC's FY2026 exam priorities` 계열. T4-B `The two-page SEC exam note` → `The two-page AI oversight note` 계열. 수정 후 단어 수 50~125·you>self·CTA 1개 유지 조건.
- 참고(비차단): T3-A "for insurance risk teams"·T4-A "NAIC pilot note"는 노트의 지배적 내용과 일치하므로 이대로 수용 가능. UK T3의 "evidence supervisors tend to ask your team for first"는 노트가 더 보수적으로("in our words") 이행하므로 허용.

### 3.6 영어 관용성 스팟 체크

전반 우수(네이티브 리듬, 세그먼트별 철자 정합: US "organize/finalized", UK "judgement/behaviour/organisation", SG "finalised", AU "artefact/prioritised"). 경미 지적 2건(선택 수정):

| # | 원문 | 위치 | 문제 | 개선 방향 |
|---|---|---|---|---|
| N-1 | `More models and deeper reviews with the same headcount pushes validation into annual cycles` | note-uk §Where independence... 1번 | 복합 주어 + 단수 동사. 단일 상황으로 읽는 관용 용법이라 경계선상이나, 감수자에 따라 오탈로 보일 수 있음 | `pushes` → `push`, 또는 `Having more models and deeper reviews with the same headcount pushes...` |
| N-2 | 보험 T2-A `Today your AI inventory...` | 카피 (§2.4 관찰 재기록) | T2-B와 쉼표 불일치 | `Today,` 통일 (선택) |

## 4. 비차단 관찰·권고 (우선순위 낮음)

| # | 항목 | 권고 |
|---|---|---|
| O-1 | note-au·note-us-brokerdealers의 INTERNAL 주석이 카피 v1.0 문구를 인용(현행 v1.1과 자구 불일치) | INTERNAL 블록은 PDF 변환 시 삭제되므로 비차단. 다음 개정 시 v1.1 문구로 동기화 |
| O-2 | assets/00-index §1의 BD 노트 제목에 "for broker-dealers" 누락(실물 제목과 불일치) | 인덱스 자구 동기화 |
| O-3 | SG 카피 T3 "the MAS AI risk management guidelines"에 "proposed" 미병기 | 같은 스레드 T1이 "consulted... proposed"를 선행 서술하므로 허용(1회차 판정 유지). 스레드 분리 재사용 금지 |
| O-4 | CPS 230 "now applies in full"(note-au): 2026-04-30 개정으로 비전통 제공자 한정 예외 존재 | 카드 우선 원칙에 따라 EC-regwind-au-01 §2-3에 예외 존재를 1줄 추가 권고(분기 재검증 시). 노트 서술 자체는 카드 정합이라 유지 가능 |

## 5. 수정 요구 목록 (우선순위 순) · 루프 2회차

1. **[R-1, 수정 필요] T3-B·T4-B 문구 미세조정** (§3.5, cold-email-writer). 반영분은 QA diff 스팟 확인으로 종결(전량 3회차 불요).
2. [선택] N-1(note-uk 주어-동사), N-2(T2-A 쉼표), O-1·O-2(인덱스·주석 동기화), O-4(카드 1줄 보강).

## 6. 발송 전 선결 조건 최신화 (1회차 §10 대비)

### 해소됨

| 1회차 # | 조건 | 해소 근거 |
|---|---|---|
| 1 | 반려 사항 수정 → QA 재검수 PASS | 본 2회차 PASS_WITH_FIXES. 잔여는 R-1 반영 + diff 스팟 확인뿐 |
| 3 | 신규 앵커 카드 4종 신설·등급 판정 | EC-regwind-us-bd-01 / us-ins-01 / sg-01 / au-01 등재 완료, 본 검수에서 QA 원출처 대조 완료(웹 재검증 §3.2). 잔여는 아래 미해소 2·3으로 이관 |
| 4 | T3 자산 실물 제작 + 자산 QA 팩트체크 | 노트 6종 제작 완료 + 본 2회차 팩트체크 PASS. 잔여는 R-1 문구 정합뿐 |

### 미해소 (전건 이행 전 발송 불가, fail-closed)

1. **R-1 반영 + QA diff 스팟 확인** (자산운용 B 세그먼트 T3·T4)
2. **legal-team 규제 해석 확인: EC-regwind-* 카드 5장 전건** (sales-compliance-officer 경유. US 은행·UK = usuk-01, BD·자산운용 = us-bd-01, 보험 = us-ins-01, SG = sg-01, AU = au-01. 카드 §5 공통 게이트)
3. **APRA 원문 PDF 확보(PO·deal-strategist 채널)**: QA 웹 접근이 프록시 차단이라 verbatim 대조 미완. 확보 전까지 직접 인용 금지 원칙 유지(현 카피·노트는 인용 0건이므로 이 항목 단독으로 발송을 막지는 않으나, "unusually direct"(AU T1) 완화 여부 판단과 카드 §2-2 갱신을 위해 필요)
4. UK: LIA 문서 ID·보관기한·{{privacy_notice_url}} 공급, sole trader·일반 파트너십 분리 (compliance-frame §2~3)
5. UK: 계정별 SS1/23 적용 지위(내부모형 승인) 확인 절차 (1회차 F-4, 릴리스 조건)
6. AU: 레코드별 증빙 5필드 + DNCR 층위 확인 (C1 전화 전)
7. SG/AU: 트랙 착수·볼륨 상한 PO 승인 (compliance-frame-sg-au §9)
8. 치환자 전건 충전(훅은 research/§5 승인 훅 한정) → 충전본 터치 릴리스 체크리스트 [G2][G5]
9. sales-compliance-officer 게이트 PASS → PO 발송 패키지 승인 + G4 보류 해제 기록 [G1]
10. 노트 발송 경로 게이트(assets/00-index §3): PO의 INTERNAL 블록 제거·PDF 변환·회신 첨부는 PO 전속 [G1], 콜드 터치 첨부 금지 유지

### 상시 트리거 (선결 아님, 감시)

- MAS AIRG 확정 발표 → note-sg·EC-regwind-sg-01·SG 카피 즉시 개정 (확정 임박 서술 전량 폐기)
- NAIC 파일럿 종료(2026-09)·Fall Meeting(2026-11) → 채택 수·파일럿 상태 갱신
- FINRA 2027 보고서·SEC FY2027 발표 → BD·보험/AM 앵커 최신화

## 7. 웹 검증 출처 (2026-08-19 접속)

- SR 26-2: https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm · https://www.sullcrom.com/insights/memo/2026/April/OCC-Fed-FDIC-Issue-Revised-Guidance-Model-Risk-Management · https://www.bakertilly.com/insights/updated-interagency-guidance-on-model-risk-management
- NAIC 채택 수: https://www.quarles.com/newsroom/publications/nearly-half-of-states-have-now-adopted-naic-model-bulletin-on-insurers-use-of-ai · https://aipmo.co/naic-ai-bulletin-q2-2026-status/ · https://actuary.info/insights/ai-regulation-insurance-naic-2026
- MAS AIRG: https://www.mas.gov.sg/publications/consultations/2025/consultation-paper-on-guidelines-on-artificial-intelligence-risk-management · https://www.stephensonharwood.com/insights/understanding-the-mas-consultation-paper-on-ai-risk-management-for-financial-institutions/
- APRA·CPS 230·REP 798: https://www.apra.gov.au/news-and-publications/apra-letter-industry-artificial-intelligence-ai (원문, 프록시 차단으로 열람 미완) · https://www.kennedyslaw.com/en/thought-leadership/article/2026/apra-provides-new-minimum-expectations-amid-growing-ai-security-risks/ · https://www.claytonutz.com/insights/2026/may/apras-ai-letter-a-shift-from-framework-to-targeted-expectations · https://www.regulationtomorrow.com/2026/05/apra-calls-for-a-step-change-in-ai-related-risk-management-and-governance/ · https://www.dwyerharris.com/blog/cps-230-and-material-service-providers-what-you-need-to-do-before-1-july-2026
- FINRA 2026: https://www.debevoisedatablog.com/2025/12/11/finras-2026-regulatory-oversight-report-continued-focus-on-generative-ai-and-emerging-agent-based-risks/ · https://www.sidley.com/en/insights/newsupdates/2025/12/finra-issues-2026-regulatory-oversight-report · https://www.mcguirewoods.com/client-resources/alerts/2025/12/finras-2026-annual-regulatory-oversight-report-same-priorities-new-focus-on-ai-and-cybersecurity/
