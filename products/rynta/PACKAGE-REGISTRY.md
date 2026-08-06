# RYNTA 패키지 관리 원장 (Package Registry)

> RYNTA RiskOps Vol.1 패키지의 버전 계보, 소스 위치, 검수 상태를 추적하는 단일 관리 원장.
> 관리 주체: AIops PM 하네스 (Product Owner: 이재준 님 지원).
> 최종 갱신: 2026-08-06

## 1. 제품 개요

- **제품명**: RYNTA RiskOps Vol.1 (구명: Capvera RiskOps)
- **핵심 메시지**: "AI for RISK, RISK for AI" — 리스크 업무를 더 빠르게 실행하면서, 실행 과정과 AI 사용 자체는 더 엄격하게 통제
- **구성 도메인**: RDM(선행 기반) + 신용 · 시장 · 운영 · ALM · 통합위기상황분석 · 상시/독립 적합성검증 → 하나의 Agentic RiskOps 운영체계
- **통제 원칙**: 결정론적 계산, 독립 재계산, 책임자 승인(4-Eyes), Evidence Vault, Human-in-the-loop, 자동확정 금지
- **핵심 구성요소 명칭** (위탁테스트 신청서 v2 기준): **QV Engine**(Quantitative Validation Engine — 결정론 정량검증 계산엔진, FastAPI REST API) · **AVI**(Artificial Validation Agent — 모형검증 에이전트, Hub/Child 구조) · **ARI**(Artificial Risk Intelligence — 리스크 인텔리전스, AML·STR 확장 검토) · **Evidence Ledger**(증빙 원장). 특허 3건(RYNTA·AVI·ARI) 출원 진행(2026-07 착수)
- **규제 준거**: EU AI Act(2026-08-02 일반 적용), ISO/IEC 42001, PSMOR(BCBS), BCBS 239, IFRS 9
- **로드맵**: Vol.2 진단·ALM·IRRBB·유동성 / Vol.3 ECL·자본·RAPM·기후 / Vol.4+ NCR·CCR/XVA·기타리스크
- **사업 모델** (navigation.xlsx 기준, v9.3.4 검수로 수치 전수 대사 완료):
  - Tier 기본구축가격: A 26.40 / B 10.35 / C 2.64억원
  - Target ARR: 130 / 448.5 / 1,105억원 (고객수×ACV, 3개 시점)
  - 계획 인식매출: 148.2 / 562.6 / 1,381.1억원
  - 인도역량 배수: 3.13x / 4.25x / 4.51x

## 2. 버전 계보 (Version Lineage)

| 버전 | 일자 | 소스 위치 | 상태 | 비고 |
|---|---|---|---|---|
| Capvera v8.1 | — | Google Drive `Capvera_RiskOps_Vol1_v8.1_한국어_Pack` | 구본 | 개별 파일 접근 가능 |
| Capvera v8.3 | — | Google Drive `Capvera_RiskOps_Vol1_v8.3_한국어_Pack` | 구본 | README·BRD·수식랩·UI 스튜디오·제안메일. Q 125 / R 126 / 제품 12종 |
| RYNTA v9.2 | 2026-07-29 | Slack #ir `RYNTA_RiskOps_Vol1_v9-2.zip` (17.2MB, F0BMG7DPQAC) | 구본 | 대표님·부대표님 공유 설계안. 금액 산정 업데이트. BRD v9.2가 해설서 |
| RYNTA v9.3.4 | 2026-07-31 | (zip 미보존, 검수보고서만 Drive) | RC, 조건부 적합 | 파일 29개, 약 44MB. 검수: SHA-256 29/29, HTML 렌더 0오류, 수식오류 0. 보완 3건 권고 (아래 §4) |
| RYNTA v9.3.7 | 2026-08-01 | Slack `RYNTA_RiskOps_Vol1_v9.3.7_한국어_정리본.zip` (42.5MB, F0BM56PRJBX) | 구본 | |
| **RYNTA v9.6.1** | **2026-08-02** | **Slack #ir zip (50.7MB, F0BM9MBHTU3) + PO 로컬 Downloads 폴더(압축해제본)** | **Current 후보** | 도메인별(RDM, 신용/시장/운영/ALM, 통합위기상황분석, 적합성검증) Drill-down 반영. **리포 반입 대기** |

## 3. 패키지 표준 구성 (v9.3.4 검수 기준, 29개 파일)

| 파일 | 용도 | 고객 발송 |
|---|---|---|
| `00_패키지_안내.md` | 폴더 구성·사용 안내 | — |
| `01_*_As-is_To-be_영향도_*.html` | 6개 부문 As-is/To-be 프로세스·검증지표 | 미팅·내부용 |
| `02_*_내부개발용_합성데이터_수식랩_*.xlsx` | 엔지니어 산식·검증 개발용 (수식 44만+개) | **발송 금지** |
| `03_*_에이전틱_UI_스튜디오_*.html` | 정형·비정형 Agentic UI 인터랙션 데모 | 미팅용 |
| `04A`~`04E` 브로셔 5종 | 디자인 후보 (권장안: 04B 인스티튜셔널 에디토리얼) | **최종 1개만 발송** |
| `04_브로셔_디자인_비교_*.html` | 내부 디자인 비교·선정 | 발송 금지 |
| `05_*_통합_제안메일_*.html` | 제목·프리헤더·본문·수신자 미리보기 | 발송 준비용 |
| `*_navigation.xlsx` | 기준 사업·제품 원장 (Question 130 / Requirement 131 / Registry 30) | 내부/협의용 |
| `*_Business_Requirements_*.html` (BRD) | 기준 Excel과 동기화된 업무요건정의서 | 내부/협의용 |
| `SHA256SUMS_*.txt`, `QA_REPORT/QA_RESULT.json`, `capture_manifest.json` | 무결성·QA·캡처 계보 | — |
| UI 캡처 PNG 13종 (+임베드 WebP 9종) | 화면 증빙 | — |

## 4. 검수 이력 및 미해결 발견사항 추적

### v9.3.4 검수 (2026-07-31, 조건부 적합) — 원본: Drive `RYNTA_v9_3_4_정리본_검수보고서_20260731.md`

기술 무결성 전 항목 통과 (해시 29/29, 렌더 오류 0, 수식오류 0, 정량수치 전수 재계산 일치). 고객 배포 전 보완 권고:

| ID | 심각도 | 요지 | v9.6.1 반영 여부 |
|---|---|---|---|
| F-1 | 중 | 브로셔 5종 실질 차별성이 비교 문서 서술과 불일치 (테마 CSS만 상이) | **미확인** — v9.6.1 반입 후 검증 필요 |
| F-2 | 중 | 04B(기준본) 히어로 구체 "Agentic Assurance" 텍스트 겹침 | **미확인** |
| F-3 | 하 | `<small>CONTROL PLANE</small>` 인라인 렌더 줄엉킴 | **미확인** |
| F-4 | 중 | BRD 변경이력 v9.3~v9.3.3 구간 단절 (감사 추적성) | **미확인** |
| F-5~F-10 | 하 | 오탈자 2건, 푸터 날짜, xlsx 내부 라벨(v9.3.3), lineageCount 정의, 표기 통일(하이픈 U+2011 혼용), 교육자료 강사 실명 | **미확인** |

### 검수 프로세스 개선 시사점 (차기 검수에 적용)
1. 자동 렌더 QA에 **요소 겹침(occlusion) 검사** 추가 — 픽셀 diff 또는 bounding-box 교차 검사
2. 내부 라벨은 별도 표지 시트에만 두고 바이트 동결 대상에서 제외
3. 비교 문서류(메타 문서)는 본 문서 변경 시 **함께 회귀 검토** (F-1류 서술 잔존 방지)

## 5. 소스 맵 (어디에 무엇이 있는가)

| 소스 | 내용 | 접근성 (이 하네스 기준) |
|---|---|---|
| **PO 로컬 Downloads** (`RYNTA_RiskOps_Vol1_v9.6.1_한국어_정리본/`) | 최신 작업본 (압축해제) | ❌ 클라우드 세션에서 직접 접근 불가 → 반입 절차(§6) 필요 |
| Slack #ir (C0BK4SCJUBV) | v9.2 / v9.3.7 / v9.6.1 zip, 설계 논의 스레드, 데모 링크 | 🔶 메시지·10MB 미만 파일만 읽기 가능 (zip 3종 모두 10MB 초과 → 도구 반입 불가) |
| Google Drive | v9.3.4 검수보고서, Capvera v8.1/v8.3 팩 (개별 파일) | ✅ 읽기 가능 |
| 본 리포 `products/rynta/` | 관리 원장(본 문서) + 위탁테스트 워크스트림(`consignment-test/`) + 반입된 패키지 사본 | ✅ 관리 대상 |
| 데모 | https://rynta-agentic-ui-demo.bbootta.chatgpt.site (에이전틱 UI 데모 영상 샘플) | 외부 링크 |
| 아티팩트 (claude.ai, PO 소유) | 「RYNTA 에이전틱 UI 스튜디오 · 2026-06-30」 — 단일 HTML 11.7MB, 2026-08-06 갱신. RUN-20260630 · 지문 124a115b1da0 · 시드 42 · 테이블 107장/930열/52,441행, 기준일 2026-03-31/2026-06-30 멀티런, Kill Switch·4-Eyes·계보 칩 포함 | ✅ 읽기 가능 (WebFetch) |
| 아티팩트 (공유받음) | 「적합성검증 팀에이전트 — 아키텍처」 | ❌ 타인 소유 — 이 세션에서 열람 불가. PO가 브라우저에서 열람 후 내용 공유 필요 |

## 5.5 진행 중 워크스트림 — 위탁테스트 신청 (2026-08-06 착수)

한국핀테크지원센터 제12회 Meet-Up 위탁테스트 신청. **마감 2026-08-12(수) 15:00.**
클로드 코워크(데스크톱) 세션에서 신청서 초안 v2·체크리스트·IR 피칭 1페이지가 작성됐고(Drive), 스냅샷을 [`consignment-test/`](consignment-test/)에 포섭함. 상세 현황·미결 사항은 해당 폴더 README 참조. 선정 시 9월 민간협의체 IR 피칭 → 금융회사 매칭 → 6개월 병행 운영 테스트로 이어짐 — RYNTA 최초의 실데이터 실증 경로.

## 6. 관리 런북 (Runbook)

### 신규 버전 반입 (intake) — PO 액션 필요
로컬 Downloads의 최신본을 하네스 관리 하에 두는 방법 (하나 선택):
1. **이 세션에 업로드**: Claude Code 세션 채팅에 zip을 드래그&드롭 → 컨테이너 파일시스템에서 즉시 검수·반입
2. **Google Drive 업로드**: zip 또는 폴더째 Drive에 올리면 하네스가 개별 파일 단위로 자동 수집 (권장: `Capvera_Riskops_package` 폴더 옆에 `RYNTA_v9.6.1` 폴더)
3. **git 직접 커밋**: 로컬에서 이 리포 `products/rynta/releases/v9.6.1/`에 커밋·푸시

### 반입 시 자동 수행 (하네스 책임)
1. SHA256SUMS 전수 대사 + 파일 수 확인 (.DS_Store 제외 확인)
2. QA_RESULT.json 대사 + 직전 검수 미해결 발견사항(§4) 반영 여부 확인
3. 본 원장 §2 버전 계보 갱신, 변경이력 계보 연속성 확인 (F-4 재발 방지)
4. HTML 렌더 검사 (겹침 검사 포함 — 검수 시사점 ①)
5. 결과를 PO에게 보고 (Current 전환 승인은 4-Eyes 원칙에 따라 PO 결정)

### 버전 상태 규칙
`작업본(로컬) → RC(검수 통과) → Current(4-Eyes 승인) → 구본(신규 버전 Current 전환 시)`
- 고객 발송은 Current만. 발송 금지 파일(02 수식랩, 04 비교 문서, 미선정 브로셔) 준수.
- 재압축·배포 시 .DS_Store 제외, 수정 후 SHA256SUMS·QA 재생성.
