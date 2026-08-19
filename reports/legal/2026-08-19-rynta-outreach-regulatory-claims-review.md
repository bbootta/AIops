# RYNTA 콜드 아웃리치 규제 서술 자료: 법적 리스크 검토

> **내부 참고자료. 변호사 자문을 대체하지 않는다.** 이 문서는 원라인AI 내부
> 국제법무 기능의 검토 의견이며, 미국·영국·싱가포르·호주 어느 관할에서도
> 자격 있는 변호사의 법률 자문이 아니다.
> **검토 기준일: 2026-08-19.** 이후 규제 변경(특히 MAS AIRG 확정, NAIC 파일럿
> 종료 2026-09, Fall National Meeting 2026-11)은 반영되어 있지 않다.

## 0. 검토 범위와 전제

- 대상: (1) 증거 카드 5장 `docs/sales/deals/_evidence/EC-regwind-{usuk-01, us-bd-01,
  us-ins-01, sg-01, au-01}.md`, (2) 배포용 노트 6종
  `docs/sales/campaigns/20260818-usuk-rynta-aigov/assets/note-*.md`, (3) 맥락 문서
  `copy/qa-review-round2.md`.
- 전제: outreach-qa 2회차가 사실 불일치 0건을 확인했다(qa-review-round2 §3).
  이 검토는 사실 재확인이 아니라 **법적 리스크 관점**(오해 소지, 무자격 자문,
  벤더 발화 규범, 미확정 규제 서술)이다. 사실관계는 카드·QA 기록을 신뢰하되,
  법적 성격 규정(구속력 유무 등)은 독자적으로 판단했다.
- 발송 경로 전제: 노트는 콜드 터치 첨부가 아니라 수신자의 긍정 답장("send it")
  후 회신 스레드에 PDF로 첨부된다(assets/00-index §2). 이 "요청 기반 제공"
  구조는 무자격 자문·스팸 양쪽에서 리스크를 낮추는 방향이므로 유지가 중요하다.

## 1. 카드별 판정 표

| 카드 | 대상 규제 | 판정 | 조건/수정안 |
|---|---|---|---|
| EC-regwind-usuk-01 | 연준 등 SR 26-2, PRA SS1/23 | **조건부** | ① 카드 §4 승인 영문 "noting they **require** a separate governance framework"를 "noting they **call for** a separate governance framework"로 완화(원문 verbatim에서 require 확인 시 현행 유지 가능, §4.1). ② note-us-banks 동일 수정(L-1). UK(SS1/23) 부분은 조건 없음 |
| EC-regwind-us-bd-01 | FINRA 2026 보고서, SEC FY2026 시험 우선순위 | **사용 가능** | 조건 없음. 격상 방지 규칙("asks/recommends, not requires")이 카드 §5와 노트 본문에 이중으로 내장되어 있고 정확히 작동한다. FINRA 2027·SEC FY2027 발표 시 재검증 트리거만 유지 |
| EC-regwind-us-ins-01 | NAIC AI 불레틴, 12개 주 검사 파일럿, SEC PDA 철회 | **조건부** | ① 카드 §4 정밀 버전 "insurer AI use is now **regulated** in roughly 29 jurisdictions"를 "roughly 29 jurisdictions have **AI-specific regulatory guidance or frameworks** in place for insurers"로 개정(카드 우선). ② note-us-insurance-am 동일 수정(L-2). ③ 파일럿 서술("exam item" 계열)은 파일럿 기간(~2026-09-30) 한정 유효를 카드에 명시 |
| EC-regwind-sg-01 | MAS AIRG 컨설테이션, 2024-12 정보문서 | **사용 가능** | 신규 조건 없음. 카드 내장 조건(proposed 병기, 현재형 의무 단정 금지, MAS 답변 귀속 한정 인용, 확정 발표 시 즉시 개정) 유지가 곧 조건. 미확정 규제 서술의 모범 사례 |
| EC-regwind-au-01 | APRA AI 서한, CPS 230, ASIC REP 798 | **조건부** | ① APRA 원문 verbatim 대조 전 직접 인용 금지 유지(현 노트·카피 인용 0건, 준수 중). ② CPS 230 "applies in full" 서술에 2026-04-30 개정(일부 비전통 제공자 예외)을 카드 §2-3에 1줄 반영(QA O-4 연동) 후 노트 한정어 추가 또는 유지 판단. ③ "unusually direct"(카피 T1)는 발신자 논평으로 허용하되 verbatim 확인 후 완화 계획(카드 §4 주석) 유지 |

## 2. 관점 1: 규제 서술의 오해 소지 ("요구" vs "감독 기대")

관할별 규제 문서의 법적 성격과 자료의 서술을 대조한 결과다.

| 문서 | 법적 성격 | 자료의 서술 | 판정 |
|---|---|---|---|
| SR 26-2 (US) | 감독지침(supervisory guidance). 2018 기관 공동성명(2021 법규화)으로 **법적 구속력 없음이 명문화된 문서 유형**. 다만 검사관 기대를 프레임 | note-us-banks가 대체로 "supervisory expectation"으로 정확히 서술하나, 생성형·에이전틱 AI에 대해 "notes that they **require** a separate governance framework"로 "require"를 지침에 귀속 | **수정 필요 (L-1)**. 수신자(리스크·컴플라이언스 임원)는 이 어휘 차이를 정확히 읽는 집단이고, 벤더가 지침을 의무로 격상하면 신뢰 훼손 + 오도 소지. BD 카드 §5가 FINRA에 적용한 격상 금지 원칙을 동일 적용해야 일관적 |
| FINRA 2026 보고서 (US) | 관찰·effective practices. 규칙 아님 | 노트가 "observations and effective practices, not a new rulebook. The accurate verbs are 'asks' and 'recommends,' not 'requires.'"로 명시 | **적정.** 4개 관할 자료 중 가장 강한 방어. 카피 T3의 "now expected to cover"는 카드 §5가 허용한 "expects" 수위 내이나, 귀속을 붙인 "what FINRA's report asks WSPs to cover"가 더 정밀(선택, C-1) |
| SEC FY2026 시험 우선순위 (US) | 시험 우선순위 공표. 규칙 아님 | "priorities include..."로 서술 | **적정** |
| NAIC 불레틴 (US) | 기존 주법(불공정거래관행법 등) 하의 해석적 가이드. **신규 법적 의무 창설 아님을 불레틴 스스로 명시** | 불레틴 자체는 "asks insurers for..."로 적정 서술. 그러나 종합 문장 "insurer AI use is **regulated** in roughly 29 jurisdictions"는 불레틴 채택 주(약 25+DC, 비구속 가이드)까지 "규제 중"으로 묶음 | **수정 필요 (L-2)**. CO 3 CCR 702-10처럼 실제 규정인 관할과 가이드 관할이 섞여 있어 "regulated" 단일 동사가 과대 서술. "subject to AI-specific regulatory guidance or frameworks" 계열로 완화 |
| PRA SS1/23 (UK) | Supervisory statement = 감독 기대. 규칙(PRA Rulebook) 아님 | "makes independent model validation an explicit supervisory expectation" + 적용 범위(내부모형 승인 기관) 정직 서술 + 비적용 기관 무의무 명시 | **적정.** UK 감독 관행 어휘와 정확히 정합. "has been in force since May 2024"만 "has applied since May 2024"로 선택 수정(L-3): "in force"는 규칙 어휘 |
| MAS AIRG (SG) | 컨설테이션 단계. 확정 후에도 MAS Guidelines는 법적 구속력 없는 감독 기대(준수 정도가 감독 평가에 반영되는 유형) | 전면 "proposed/consulted/will be finalised soon" 규율, 현재형 의무 단정 0건 | **적정** (§5 참조) |
| APRA AI 서한 (AU) | 감독 기대·관찰 공표. 기준서 아님 | "warned/observed" + "our summary, not APRA's text" | **적정** |
| CPS 230 (AU) | **법적 집행력 있는 건전성 기준서** (Banking Act 등 근거) | "prudential standard... took effect... now applies in full" | **대체로 적정.** CPS 230은 실제 구속 규범이므로 강한 서술이 정당하다. 단 "applies in full"은 2026-04-30 개정 예외(비전통 제공자 한정)와의 정합을 위해 카드 보강 후 한정어 검토(L-4, 비차단) |

종합: 관할별 "요구 vs 기대" 구분은 6종 노트 전반에서 관행에 맞게 구현되어
있다. 예외는 US 쪽 2건(L-1, L-2)이며 둘 다 경수정이다.

## 3. 관점 2: 무자격 자문(unauthorized practice) 리스크

### 3.1 공통 판단 기준

무자격 법률 자문 규제는 4개 관할 모두에서 대체로 다음 요소로 판단된다:
(i) 특정인의 구체적 사실관계에 법을 적용한 조언인가, (ii) 법률가 자격을
표방하거나 그런 합리적 추론을 유발하는가, (iii) 대가를 받는가, (iv) 법률가의
배타적 직무(소송 수행, 법적 권리·의무에 대한 개별 자문, 법률문서 작성)인가.

노트 6종은 (i) 불특정 다수 대상 일반 정보이고 수신자별 커스텀이 금지되어
있으며(assets/00-index §2-3), (ii) 법률가 표방이 없고 About 박스가 "research-driven
team"으로 자기규정하며, (iii) 무상 마케팅 자료이고, (iv) 체크리스트·시사점을
"practical steps, in our words / not a restatement of regulator language"로 규제
문언과 분리한다. **4개 관할 모두 무자격 자문 리스크는 낮다.**

### 3.2 관할별

- **미국**: UPL은 주법 사안(예: NY Judiciary Law §478, Cal. Bus. & Prof. Code
  §6125). 일반적 법률·규제 정보의 출판은 UPL이 아니라는 것이 확립된 관행이며,
  로펌·컨설팅사의 client alert와 동일한 발화 유형이다. 리스크 낮음.
- **영국**: Legal Services Act 2007상 reserved legal activities(변론권, 소송 수행,
  등기·검인 문서, 공증, 선서)에 일반 법률 자문 자체가 포함되지 않는다. 규제
  해설 노트 배포는 자유. 실질 리스크는 UPL이 아니라 신뢰 유발 시 과실
  부실진술(negligent misstatement, Hedley Byrne 계열)이며, 고지·비신뢰 문구로
  완화한다. FSMA s21 금융판촉 규제는 비해당(투자활동 권유 아님).
- **싱가포르**: Legal Profession Act 1966 ss 32~33이 무자격자의 advocate and
  solicitor 활동을 금지하며, 판례·해설상 "법적 권리·의무에 대한 (개별) 자문,
  법률문서 작성" 등 변호사의 배타적 직무가 기준이다. 일반 규제 동향 요약은
  비해당 관행. 리스크 낮음.
- **호주**: Legal Profession Uniform Law s 10(NSW·VIC·WA, 타 주 상당 규정)이
  무자격 entity의 legal practice를 금지(벌금 + 최대 징역 2년). 기준은 "법률가가
  통상 하는 일을, 법률가라는 합리적 추론을 유발하는 방식으로" 하는가이다.
  일반 정보 노트는 비해당. 호주에서 실질적으로 더 중요한 규범은 Australian
  Consumer Law s 18(오도적·기만적 행위, B2B 적용, **고지문으로 배제 불가**)이며,
  이에 대한 실질 방어는 고지가 아니라 이 저장소의 카드·QA 정확성 통제다.
- **한국(발신 주체)**: 변호사법 §109는 대가를 받는 법률사무 취급을 금지한다.
  무상·일반 정보 제공은 해당하지 않는다. 리스크 낮음.

### 3.3 현행 고지의 충분성

현행 "This note is for general information, not legal or compliance advice.
Positions are stated as of August 2026 and may change."는 4개 관할 모두에서
**최소 기준을 충족한다.** 관할별 별도 고지 변형은 불요하다(4개 관할 모두
"일반 정보 vs 개별 자문" 구분이 핵심이고, 관할 특유의 필수 문구 요건이 이
문서 유형에 존재하지 않는다). 다만 §6의 보강 문안(3요소 추가)을 권고한다.

**행위 기준이 문서보다 중요하다**: 노트 자체보다, 후속 미팅·회신에서 세일즈가
특정 기관의 사실관계에 대해 "귀사는 이 규제상 X를 해야 한다"고 말하는 순간
개별 자문으로 넘어간다. 세일즈 토크트랙에 "규제 해석 질문을 받으면 '그건
귀사 법무·컴플라이언스가 판단할 사안'으로 되돌린다"는 한 줄 가이드를 추가할
것을 권고한다.

## 4. 관점 3: 벤더 발화 규범

점검 항목과 결과:

| 항목 | 결과 |
|---|---|
| 준수 보장("쓰면 준수된다") | **0건.** 오히려 반대 방향 정직 서술이 일관됨("The guidance names the gap; it does not fill it", "Neither mandates a particular tool or method" 등) |
| "규제가 우리 제품을 요구한다" | **0건.** 제품 언급은 전 노트 About 박스 밖 0건 |
| 감독당국 관계·보증 암시 | **0건.** About 박스의 KRX는 "operator of Korea's national securities market"으로 정확 기술(거래소 운영자, 감독당국 아님). 규제기관 명칭 사용은 공표 문서 서술 목적의 지명적 사용으로 적법. 로고 사용 금지 유지. §6 보강 문안에 무보증(no endorsement) 1줄 추가 권고 |
| 수신자 위반·미준비 단정 (공포 마케팅) | **0건.** "before an exam letter arrives" 등은 일반적 시험 현실 서술로 허용 범위 |
| 자사 AI 역량 과대표시 | About 박스는 EC-krx-acl2025-01·EC-rynta-arch-01 승인 문구 범위 내. 유의: SEC가 AI-washing을 심사하는 시장에 AI 역량을 파는 회사이므로, 자사 제품 서술의 정확성 기준을 수신자에게 요구하는 기준과 동일하게 유지할 것(AU ACL s 18, 미 주 UDAP, Lanham Act §43(a)의 B2B 부실표시 경로) |

**주의 관찰 2건 (비차단, 가드레일):**

1. **C-2** master-au T1: "RYNTA is our answer" 뒤 문장이 아키텍처 서술이므로
   "APRA 서한에 대한 답"이 아니라 "continuous assurance가 실무에서 어떤
   모습인가에 대한 답"으로 읽혀 허용. 단 후속 자료·구두에서 "RYNTA is the
   answer to APRA's letter / to SR 26-2" 류로 진화하면 준수 보장 암시가 된다.
   금지 표현으로 세일즈 가이드에 명시 권고.
2. **C-3** 보험 카피 짧은 형 "the NAIC's 12-state exam pilot making insurer AI
   governance an exam item": 파일럿 기간 중·파일럿 주에서만 문자 그대로
   참이다. **2026-09-30 이후 무수정 사용 금지**를 카드 §5에 명시 권고
   (재검증 트리거는 이미 존재, 문구 시효를 명문화하는 것).

## 5. 관점 4: 미확정 규제 서술

- **SG (AIRG "proposed")**: **안전. 모범 사례.** 도입부 캐비앗("not final
  guidelines; the word 'proposed' matters throughout"), 본문 "as consulted on /
  as proposed / may change", 12개월 전환 산술의 조건부 프레임("assuming the
  proposed transition survives finalisation broadly intact"), 푸터 추가 캐비앗,
  확정 시 즉시 개정 트리거까지 5중 방어다. "will apply to all AI use cases...
  will be finalised soon"은 MAS 국회 답변 귀속 인용으로 적법. 가짜 긴급성
  연출 없음.
- **US NAIC 파일럿 ("검사 국면")**: **안전.** 노트가 "this is a pilot, not a
  settled exam regime"과 2026-11 채택 검토를 명시하고, 4개 익시빗을 "a
  reasonable preview of how an AI-focused exam **could** organize its questions"로
  가정법 처리했다. 12개 주 실명 미기재(2차 소스)도 적절한 절제. 유일한
  리스크는 시효(§4 C-3)다.

## 6. 고지문 보강 권고 (전 노트 공통 1종)

현행 고지를 다음으로 교체 권고. 관할별 변형 불요:

> This note is provided for general information only. It is not legal,
> compliance, or regulatory advice, and it is not a substitute for advice from
> qualified counsel or your own legal and compliance functions in your
> jurisdiction. Summaries of regulatory documents are ours, not the
> regulators'; the original texts govern. No regulator referenced in this note
> has reviewed or endorsed this note or our products. Positions are stated as
> of August 2026 and may change.

- note-sg는 기존 마지막 문장("in particular, the final guidelines may differ
  from the consultation described here.")을 뒤에 유지.
- 추가된 3요소의 목적: ① 자격 변호사 자문 비대체(4개 관할 공통의 개별 자문
  구분 강화), ② 원문 우선(요약 드리프트·AU verbatim 미대조 리스크 방어),
  ③ 규제기관 무보증(벤더 발화 규범 §4 보강).

## 7. 노트별 지적 사항과 수정안 종합

| # | 노트 | 등급 | 현행 | 수정안 |
|---|---|---|---|---|
| L-1 | note-us-banks | **수정 필요** | "and notes that they require a separate governance framework" | "and notes that they **call for** a separate governance framework" (SR 26-2 원문 verbatim에서 "require" 확인 시 현행 유지 가능). 추가 권고 1줄: "Like other SR letters, SR 26-2 is supervisory guidance rather than a binding rule; it frames what examiners look for." 카드 §4 승인 영문도 동일 개정(카드 우선) |
| L-2 | note-us-insurance-am | **수정 필요** | "Taken together, insurer AI use is regulated in roughly 29 jurisdictions." | "Taken together, roughly 29 jurisdictions have adopted AI-specific regulatory guidance or frameworks that apply to insurers." 선택 추가 1줄: "The bulletin is regulatory guidance issued under existing state law rather than a new statute or regulation." 카드 §4 정밀 버전 선개정 |
| L-3 | note-uk | 선택 | "has been in force since May 2024" | "has applied since May 2024" (supervisory statement 어휘 정합) |
| L-4 | note-au | 선택 (카드 연동) | "so the standard now applies in full" | 카드 §2-3에 2026-04-30 개정 예외 1줄 보강(QA O-4) 후, 노트에 "(APRA has since made narrow carve-outs for certain non-traditional providers, which do not change the picture for regulated institutions)" 추가 또는 현행 유지 판단 |
| L-5 | note-us-banks | 선택 | "Each institution has to decide" | "Each institution is left to decide" (의무 뉘앙스 완화) |
| - | note-us-brokerdealers | 수정 불요 | - | 카피 T3 "now expected to cover"는 카드 허용 수위("expects") 내. 더 정밀하게는 "what FINRA's report asks written procedures to cover" (선택, C-1) |
| - | note-sg | 수정 불요 | - | - |

전 노트 공통: §6 고지문 교체.

## 8. 현지 전문가·후속 확인 필요 목록

1. **SR 26-2 원문 verbatim** (outreach-qa 또는 US counsel): 생성형·에이전틱 AI
   문단의 동사가 "require"인지 확인. 확인 결과에 따라 L-1 확정.
2. **APRA 서한 원문 PDF 확보** (기존 게이트, PO·deal-strategist 채널): 직접
   인용 허용 여부·"unusually direct" 완화 판단.
3. **미국**: 현 단계 US counsel 확인 불요. 단 향후 "compliance gap assessment"
   류 유료 서비스를 제안하는 시점에는 UPL·컨설팅 경계에 대해 US counsel 확인.
4. **호주**: ACL s 18 관점의 제품 역량 서술 점검은 선택. Spam Act 증빙 프레임은
   기존 게이트(compliance-frame-sg-au) 존속.
5. **싱가포르**: 현 단계 SG counsel 확인 불요. AIRG 확정 후 개정 노트에서
   확정 가이드라인의 법적 성격 서술(비구속 guidelines) 재확인 권장.
6. **세일즈 토크트랙 가이드 1줄 추가** (sales-compliance-officer): 개별 기관
   사실관계에 대한 규제 해석 질문은 수신자 법무·컴플라이언스로 되돌린다.
7. **시효 관리**: 2026-09-30(NAIC 파일럿 종료), 2026-11(Fall Meeting), MAS AIRG
   확정 발표. 기존 재검증 트리거 유지 + C-3 문구 시효 명문화.

## 9. 결론

**발송 관점의 법적 차단 사유: 없음.**

- 무자격 자문 리스크: 4개 관할 모두 낮음. 현행 고지는 최소 기준 충족, §6
  보강 권고.
- 벤더 발화 규범: 위반 0건. 가드레일 2건(C-2, C-3) 명문화 권고.
- 미확정 규제 서술(SG, NAIC 파일럿): 안전.
- 수정 필요는 경수정 2건(L-1, L-2)이며, 발송 전 반영을 권고한다. 둘 다 카드
  우선 원칙에 따라 카드(§4 승인 문구)를 먼저 개정하고 노트를 따라 고친다.
- 이 검토는 카드들이 요구하는 "legal-team 규제 해석 확인" 게이트의 입력으로
  사용할 수 있으나, 게이트 충족 판정은 sales-compliance-officer의 몫이고,
  기타 fail-closed 게이트(APRA verbatim, SG/AU 컴플라이언스 프레임, PO 승인,
  R-1 반영 등 qa-review-round2 §6)는 이 검토와 무관하게 전건 존속한다.

## 10. 참고 원천 (무자격 자문 관행 확인, 2026-08-19 접속)

- SG: Legal Profession Act 1966 (Singapore Statutes Online, sso.agc.gov.sg/Act/LPA1966) ·
  Singapore Law Gazette, "Unauthorised Practice of Law: What Constitutes Acting or
  Practising as a Solicitor?" (lawgazette.com.sg) · Law Society of Singapore,
  "Alternative Legal Service Providers and the Unauthorised Practice of Law"
- AU: Legal Profession Uniform Law (NSW) s 10 (AustLII) · Law Society of NSW,
  "Unqualified practitioners" · Law Society of NSW, "Engaging in legal practice
  and legal services under LPUL" (2025)
- US·UK·KR: 확립된 법령·관행(주별 UPL 법령, Legal Services Act 2007 s 12·Sch 2,
  변호사법 §109) 기반 내부 지식. 신규 검색 미실시.

## 11. 반영 기록 (검토 후 조치, sales-lead)

- 2026-08-19: L-1, L-2 반영 완료(카드 우선: EC-regwind-usuk-01·EC-regwind-us-ins-01
  §4 개정 후 노트 수정). L-3, L-5 반영. §6 고지문 전 노트 6종 교체(note-sg는
  기존 캐비앗 유지). L-4(CPS 230 개정 예외)와 C-1은 원문 확인 후 처리 예정으로
  미반영. C-2·C-3 가드레일과 토크트랙 가이드는 세일즈 가이드 반영 대기.
