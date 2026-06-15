# 바젤·금감원 기준 매핑 및 검증통제 레지스터

## 1. 목적

본 문서는 양적검증 팀 에이전트 운영 패키지가 최신 바젤 및 국내 감독 기준을 검증업무 통제 항목으로 연결하도록 돕는 기준 매핑표다. 에이전트는 기준을 자동 해석하거나 자동 반영하지 않고, 공식 출처와 내부 승인 정책에 근거해 후보 통제와 점검 항목을 제안한다.

## 2. 기준일 및 공식 출처

- 기준일: 2026-05-14.
- 바젤 기준은 BIS/BCBS 공식 페이지의 현행 상태와 Basel Framework를 우선 참조한다.
- 국내 감독 기준은 국가법령정보센터의 `은행업감독규정`, `은행업감독업무시행세칙`, 관련 별표·별지를 우선 참조하고, 금융감독원·금융위원회 공문 및 승인조건을 내부 정책문서로 매핑한다.
- 출처가 최신인지 확인되지 않거나, 국내 시행일·경과조치·은행별 승인조건이 불명확하면 `Gray`로 처리한다.


## 3. 공식 출처 레지스터

아래 표의 `ID` 값은 감사추적, 보고서, `case_fingerprint`에 기록하는 `regulatory_source_reference`의 표준 허용값이다. 에이전트는 동일 출처를 자유 텍스트로 재기재하지 말고 이 ID를 사용해야 하며, 신규 출처가 필요한 경우 레지스터 ID를 먼저 추가한 뒤 참조한다.

| ID | 출처 | 기준 상태 | 운영상 사용 방식 |
|---|---|---|---|
| BIS-BF | https://www.bis.org/baselframework/background.htm | Basel Framework 구조 및 현행/미래 버전 확인 출처 | CRE, SRP, DIS 등 관련 장의 현재 적용 버전 확인 |
| BIS-CRP-2025 | https://www.bis.org/bcbs/publ/d595.htm | 2025-04-30 현행 Credit Risk Principles | 신용위험 환경, 측정·모니터링, 통제 프레임 점검 |
| BIS-BCBS239-2026 | https://www.bis.org/publ/bcbs_nl36.htm | 2026-01-06 BCBS 239 implementation newsletter | 데이터 governance, lineage, ad-hoc reporting, 보완통제 점검 |
| BIS-IRB-VALIDATION | https://www.bis.org/publ/bcbs_wp14.htm | 현행 IRB validation working paper | PD/LGD/EAD 및 rating system 검증방법 후보 점검 |
| BIS-BCP-2024 | https://www.bis.org/bcbs/publ/d573.htm | 2024-04-25 통합 Basel Framework 반영 Core Principles | 감독검사 대응, 독립검증, 공식 판단권 점검 |
| KR-BANK-SUP-DETAIL-ANNEX3 | https://law.go.kr/LSW/flDownload.do?flSeq=131147849 | 은행업감독업무시행세칙 별표 3 공식 다운로드 | 신용평가시스템, PD/LGD/EAD, 내부등급법 최소요건 점검 |
| KR-STRESS-ANNEX19 | https://www.law.go.kr/LSW/flDownload.do?bylClsCd=200201&flNm=%5B%EB%B3%84%ED%91%9C+19%5D+%EC%9C%84%EA%B8%B0%EC%83%81%ED%99%A9%EB%B6%84%EC%84%9D+%EC%8B%A4%EC%8B%9C+%EA%B8%B0%EC%A4%80&flSeq=161246687 | 위기상황분석 실시 기준 | ST/ICAAP/거시변수/신용리스크 스트레스 검증 점검 |
| KR-ICAAP-ANNEX3-9 | https://www.law.go.kr/LSW/flDownload.do?bylClsCd=200201&flNm=%5B%EB%B3%84%ED%91%9C+3%EC%9D%989%5D+%EB%82%B4%EB%B6%80%EC%9E%90%EB%B3%B8%EC%A0%81%EC%A0%95%EC%84%B1+%ED%8F%89%EA%B0%80%C2%B7%EA%B4%80%EB%A6%AC%EC%B2%B4%EC%A0%9C+%EA%B5%AC%EC%B6%95%C2%B7%EC%9A%B4%EC%9A%A9+%EB%B0%8F+%EC%A0%90%EA%B2%80+%EA%B8%B0%EC%A4%80&flSeq=137870347 | ICAAP 구축·운영 및 점검 기준 | 포트폴리오, default 정의, CRM 잔여리스크, 내부자본 적정성 점검 |

## 4. 공통 가정 및 하네스

- 본 문서는 법률 자문 또는 감독당국 유권해석이 아니다.
- LLM은 수치 계산, 규제자본 산출, 임계값 산출, 정책 자동 개정을 수행하지 않는다.
- 규제 변화는 후보 영향분석과 후보 검증통제 제안까지만 수행한다.
- 최종 기준 적용 여부는 준법, 리스크정책, 리스크감리, 공식 승인 조직이 결정한다.
- 동일한 공식 출처 버전, 내부 정책 버전, 입력 증적 버전, 계산엔진 결과 ID가 주어지면 동일한 통제 매핑과 판정 후보가 산출되어야 한다.

## 5. 공식 기준 매핑표

| 기준 영역 | 공식 기준/출처 | 에이전트 검증통제 | 관련 문서 | 미충족 시 기본 판정 |
|---|---|---|---|---|
| Basel Framework 현행성 | Basel Framework는 BCBS의 통합 기준이며 CRE는 신용리스크 RWA 산출 기준 영역이다. | 기준일 현재 적용 버전, 장·문단, 국내 이행 여부, 은행별 승인조건을 기록한다. | `REG_CHANGE_CANDIDATE_CONTROL.md`, `AUDIT_TRAIL_CHECKLIST.md` | Gray |
| 바젤 신용리스크 관리 원칙 | 2025년 개정 Credit Risk Principles는 신용위험 환경, 여신 프로세스, 신용관리·측정·모니터링, 통제 체계를 강조한다. | 검증 범위가 정책환경, 여신등급/파라미터, 모니터링, 통제·독립검증을 포함하는지 확인한다. | `TEAM_AGENT_WORKFLOW.md`, `REPORT_TEMPLATE.md` | Yellow 또는 Gray |
| IRB 승인 및 PD/LGD/EAD 사용 | IRB는 감독당국 명시 승인 하에 내부등급시스템과 PD/LGD/EAD 등 내부 추정치를 사용할 수 있다. | 내부등급법 적용 여부, 승인조건, FIRB/AIRB 구분, 자체 추정 허용 파라미터를 확인한다. | `VALIDATION_OBJECT_CLASSIFICATION.md`, `QUANT_VALIDATION_METHOD_GUIDE.md` | Gray |
| 내부등급시스템 검증 | 바젤 검증 연구는 PD/LGD/EAD 및 기초 등급의 soundness 평가 도구 필요성을 제시한다. | 변별력, calibration, backtesting, LGD/EAD 검증, benchmarking 산출물 존재 여부를 확인한다. | `QUANT_VALIDATION_METHOD_GUIDE.md`, `JUDGEMENT_POLICY_TEMPLATE.md` | Gray |
| BCBS 239 데이터·보고 | BCBS 239 및 2026 뉴스레터는 정확·포괄·적시 데이터 집계, governance, data lineage, ad-hoc reporting, 보완통제를 강조한다. | 데이터 오너, lineage, 품질 KPI, 보고 재현성, 임시/수기 보완통제, 이사회·경영진 보고 경로를 확인한다. | `DATA_READINESS_CHECKLIST.md`, `AUDIT_TRAIL_CHECKLIST.md` | Gray |
| 리스크 산출 영역별 감독 정합성 | 신용·시장·운영·금리·유동성·전략·평판리스크는 서로 다른 정책, 데이터 원천, 계산엔진, 보고 기준을 가진다. | `risk_output_domain`별 필수 입력자료, 계산엔진 결과, 정책 기준, 주영역/부영역 근거를 확인한다. | `RISK_OUTPUT_TAXONOMY.md`, `DETERMINISTIC_DECISION_PROTOCOL.md` | Gray |
| Basel Core Principles | 2024 개정 Core Principles는 은행감독의 최소 기준으로 통합 Basel Framework에 반영되었다. | 감독검사 대응 가능성, 독립검증, 조기개입 후보, 공식 조직 판단권을 확인한다. | `GO_NO_GO_CHECKLIST.md`, `AUDIT_TRAIL_CHECKLIST.md` | Yellow 또는 Gray |
| 국내 신용평가시스템 최소요건 | `은행업감독업무시행세칙` 별표 3은 신용리스크 평가, 내부등급 부여, PD/LGD/EAD 추정치 계량화와 관련된 방법론, 업무절차, 데이터 수집, 통제 및 전산시스템 마련을 요구한다. | 방법론·절차·데이터·통제·전산시스템 증적을 필수 입력으로 요구한다. | `DATA_READINESS_CHECKLIST.md`, `AUDIT_TRAIL_CHECKLIST.md` | Gray |
| 복수 신용평가시스템 일관성 | 같은 자산분류 내 복수 시스템을 사용할 경우 문서화된 절차에 따라 일관되게 사용해야 한다. | 동일 요청-동일 결과 프로토콜, segmentation/version lock, 임의 적용 금지 확인을 수행한다. | `DETERMINISTIC_DECISION_PROTOCOL.md`, `TEAM_AGENT_ROLE_MAP.md` | Yellow 또는 Gray |
| 기업 등 익스포져 등급 구조 | 차주등급과 여신등급의 독립 시스템, 차주등급 기준 명확성, 동일 차주 동일 등급 원칙 및 예외가 요구된다. | 차주등급/여신등급 분리, 예외 사유, 보증·국가리스크 예외 증적을 확인한다. | `VALIDATION_OBJECT_CLASSIFICATION.md`, `QUANT_VALIDATION_METHOD_GUIDE.md` | Gray |
| ICAAP 신용리스크 관리 | 국내 ICAAP 기준은 포트폴리오 수준 관리, 모든 익스포져 인식·측정, 부도정의 적합성, CRM 잔여리스크 통제를 요구한다. | 포트폴리오 단위 검토, default 정의, 편중리스크, CRM 정책과 주기점검 증적을 확인한다. | `TEAM_AGENT_WORKFLOW.md`, `REPORT_TEMPLATE.md` | Yellow 또는 Gray |
| 위기상황분석 | 국내 위기상황분석 기준은 내부등급법 승인 여부와 관계없이 신용리스크 스트레스테스트, 거시요인, credit losses, 소요자기자본 변화, PD 변화 또는 등급전이를 고려하도록 한다. | `hybrid_risk_output`과 위험요소 검증에서 시나리오 승인, 거시변수, PD/등급전이, 자본영향 산출물의 계산엔진 결과를 요구한다. | `VALIDATION_OBJECT_CLASSIFICATION.md`, `QUANT_VALIDATION_METHOD_GUIDE.md` | Gray |

## 6. 감독기준 체크 게이트

각 검증 건은 판정 전 아래 게이트를 순서대로 통과해야 한다.

1. **Source Gate**: 공식 기준 출처, 발행기관, 시행일, 국내 적용 여부, 내부 정책 버전을 확인한다.
2. **Approval Gate**: 내부등급법·모형·파라미터·보고서의 감독당국 승인조건 또는 내부 승인조건을 확인한다.
3. **Data Gate**: 데이터 오너, 기준일, 모집단, 표본, lineage, 권한, 재현성 증적을 확인한다.
4. **Method Gate**: 검증방법이 승인된 방법론 및 대상 업무와 일치하는지 확인한다.
5. **Engine Gate**: 계산엔진 결과 ID, 버전, 입력 데이터 ID, 실행 로그, 파라미터 파일을 확인한다.
6. **Judgement Gate**: 판정 후보가 정책 근거, 증적, 우선순위 규칙에 따라 결정되었는지 확인한다.
7. **Governance Gate**: 비Green Notice, 인간 검토자, 공식 조직 결정, 감사추적 보관 위치를 확인한다.

하나라도 필수 게이트를 통과하지 못하면 `Gray` 또는 사안별 `Yellow/Red` 후보를 검토하되, 정량 결론은 금지한다.

## 7. 기준 최신성 운영 절차

| 주기 | 확인 항목 | 담당 후보 | 산출물 |
|---|---|---|---|
| 매 검증 건 | 적용 기준 버전, 내부 정책 버전, 계산엔진 버전 | Intake, Governance | Audit Trail |
| 월간 | 국내 감독규정·시행세칙 개정 여부 | Regulation Monitoring | 후보 영향분석 |
| 분기 | Basel Framework, BCBS 뉴스레터, FSS/FSC 공지 | Regulation Monitoring | 기준 레지스터 업데이트 후보 |
| 반기 | UAT 시나리오와 Go/No-Go 기준의 기준 정합성 | Governance, UAT 담당 | UAT 보완 계획 |
| 수시 | 감독당국 승인조건, 검사 지적, 내부 정책 변경 | Policy Owner | 후보 통제 및 Action Notice |

## 8. 판정 영향 원칙

- 공식 기준 또는 내부 승인조건과 충돌하는 자동화 결과는 사용하지 않는다.
- 기준 출처가 상충하면 국내 법규·감독당국 승인조건·은행 내부 승인정책·Basel 원칙 순으로 인간 검증자에게 상정한다.
- 정량 결과가 양호해도 감독기준 게이트의 필수 증적이 없으면 `Gray`가 우선한다.
- 동일 기준 버전과 동일 증적에 대해 다른 판정 후보가 생성되면 결정 재현성 결함으로 기록하고 `Gray`로 전환한다.
