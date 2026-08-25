# 계정 리서치: Allstate

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/research/us-i5-allstate.md`
> Tier 1~2 레코드는 이 산출물(30일 이내 작성분) 없이 시퀀스에 투입할 수 없다 [G4].
> 규제 프레임 주의(6차 배치): 손보는 SR 26-2가 아니라 NAIC 모델 불레틴·주 감독(요율 규제 포함) 프레임이다. CO 3 CCR 702-10은 생보 전용이므로 인용 금지.

| 항목 | 내용 |
|---|---|
| 계정 / 티어 | Allstate (US-I5) / Tier 2 (가배정, PO 확정 대기) |
| 캠페인ID | 20260818-usuk-rynta-aigov |
| 작성 에이전트 | prospect-researcher |
| 검토 | sales-lead (대기) |
| 승인 | PO (앵글 선택 §7, 보류 해제 §1에 한함) 미서명 |
| 기준일 | 2026-08-19 (유효기간: 2026-09-18까지) |

## 1. 판정 요약

- **투입 판정: 발송 보류 (G4 해제 상신 권고, 강. 단 S1 근접 강주의: "내부 전용 AI" 원칙 공표 = 자체 구축 성향이 확인된 계정. 독립검증·어슈어런스 보완의 좁은 접근 전제이며 전제 승인은 PO)**
- [G4] "왜 이 사람, 왜 지금" 한 문장: 2026-08-07 자체 LLM 생태계 ALLIE를 공개하며 250+ 분석 모델 위에 생성·에이전틱 AI를 얹어 클레임 처리와 3개 주 직접 판매까지 넣었고, 같은 시기 NAIC AI Systems Evaluation Tool 검사 파일럿(2026-03~09)이 손보사 AI 거버넌스를 검사 표면으로 만들고 있기 때문이다.
- **보류 해제는 PO만 할 수 있다 [G1].** 해제 기록: 없음.

## 2. 시그널 (강제 필드)

| 종류 | 내용 | 일자 | 출처 (URL) |
|---|---|---|---|
| AI 플랫폼 공개 | 자체 대규모 언어모델 생태계 ALLIE 공개: 생성·에이전틱 AI 사용례(고객 응대, 3개 주 직접 보험 판매, 클레임 처리), 250+ 분석 모델·40PB 데이터 기반, 언더라이팅 도구 보호를 위해 내부 AI만 사용 | 2026-08-07 | https://www.insurancejournal.com/news/national/2026/08/07/880719.htm |
| AI 운영 규모 (보조) | 클레임 커뮤니케이션 대부분을 생성형 AI가 초안 작성(일 약 5만 건, 상담 인력 2.3만 명 규모) 보도 | 게재일 미확인 | https://futurism.com/allstate-almost-all-insurance-communications-ai |
| 업계 분석 (보조) | ALLIE의 비용 절감·성장 목표, 에이전틱 역량 분석 | 게재일 미확인 | https://coverager.com/allstate-allie-and-the-beast/ |
| 세그먼트 공통 (규제) | NAIC AI Systems Evaluation Tool 12개 주 파일럿(2026-03~09), 시장행위 검사에서 비도메스틱 보험사에도 적용 검토. 2026-11 채택 검토 | 2026-03 (개시) | https://www.fenwick.com/insights/publications/naic-expands-ai-systems-evaluation-tool-pilot-program-to-12-states-key-updates-for-insurers-and-ai-vendors-supporting-insurers |

- 유효기간 판정(KB03 §5.2): 핵심 시그널 12일 전 실측, 유효창 정중앙. 요율·텔레매틱스 모델 밀도(§1.3 편입 사유)와 정면으로 겹친다.
- 정직 표기: 모델검증·AI 거버넌스 조직·채용의 직접 증거는 미발견 [검증 필요]. 내부 전용 원칙 공표는 외부 벤더 일반에 대한 저항 신호이기도 하다(아래 §6).

## 3. 가설

내부 전용 LLM 생태계가 요율·언더라이팅 모델(주 감독 인가 대상) 위에 얹히는 구조는, 생성·에이전틱 계층의 산출이 규제 모델의 입력·운영에 스며드는 경로를 만들고, 그 경계의 감사 가능성(어떤 에이전트가 무엇을 제안했고 누가 승인했나)이 검사 국면에서 쟁점이 된다는 가설. 자체 구축 성향이 강하므로 "플랫폼 교체"가 아니라 "3선 독립검증·어슈어런스 보완"의 좁은 제안만 성립한다. 단정하지 않는다: ALLIE의 내부 거버넌스 체계는 미확인이다.

## 4. 타깃 인물

실명·이메일은 기재하지 않는다(PO 도구, list-build-spec §1.2).

| 이름 | 직함(타깃 수준) | jurisdiction | 이메일 출처 / 수집일 | 직무 관련성 근거 |
|---|---|---|---|---|
| (PO 특정) | Chief Risk Officer | US | 미수집 (PO 도구) | EB. AI·모델리스크 소유 |
| (PO 특정) | Chief Actuary / Head of Pricing & Actuarial Models | US | 미수집 (PO 도구) | 요율·계리모델 검증 라인 |
| (PO 특정) | Head of Model Risk / Model Validation | US | 미수집 (PO 도구) | 챔피언 후보 (PRD-VAL) |
| (PO 특정) | Head of AI Governance / Responsible AI (실재 여부 [검증 필요]) | US | 미수집 (PO 도구) | 챔피언 후보 (PRD-AIG) |

- [ ] [G9] 인물 레코드 0건 상태. 수집 출처·수집일은 PO(도구) 공급 후 충족. US 수신 근거: CAN-SPAM 옵트아웃 기준. 충족 전 발송 큐 진입 불가.
- [x] [G2] 회피 등급 관할 인물 없음 (계정 관할 US 확정)

## 5. 훅 1문장

- 국문 메모: 가장 강한 시그널 1개: 2026-08-07 ALLIE 공개(내부 전용, 250+ 모델 위 생성·에이전틱).
- 영문 초안: `Allstate just unveiled ALLIE, an internal-only LLM ecosystem running on top of 250-plus analytical models, weeks before NAIC examiners wrap up the pilot of their new AI Systems Evaluation Tool.`

## 6. Anti-ICP 배제 확인

- [x] H1~H4 해당 없음: 주 보험감독 규제 대형 손보, 요율 모델 밀도 최상급, 관할 US
- [x] H5 해당 없음: 경쟁사 아님
- [x] S1 검토: **S1 근접 강주의.** "내부 AI만 사용" 원칙 공표 = 자체 구축 성향 확인. 전사·플랫폼 제안 부적합, 3선 독립검증·어슈어런스 보완의 좁은 접근만 검토. 전제 승인은 PO
- [x] Anti-ICP 제외 규칙 icp-draft.md §6 (PO 확정 2026-08-18) 대조 완료
- [ ] [G2] suppression 리스트 대조: 미완 (전역 suppression 리스트 미구축, list-build-spec 대기)

## 7. 공략 앵글 후보 (선택은 PO)

| # | 앵글 | 근거 시그널 | 예상 채널 |
|---|---|---|---|
| 1 | 내부 구축 AI의 3선 독립검증 보완: 자체 플랫폼을 대체하지 않고 검증 계층만 얹는 제안 (PRD-VAL) | ALLIE 2026-08-07 | 이메일 |
| 2 | 에이전틱·생성 계층과 규제 요율 모델의 경계 감사 가능성 (PRD-AIG, 좁은 범위) | ALLIE + NAIC 파일럿 | 이메일 |
| 3 | 디자인 파트너: 검사 국면의 AI 거버넌스 증빙 선례 (기능 단위) | NAIC 파일럿 2026-03~09 | 이메일 |

- **앵글 선택은 PO 전속 결정이다 [G1].** 선택 기록: 미선택 / PO 서명 없음 / 날짜 없음
