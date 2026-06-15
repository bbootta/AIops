# 은행 리스크감리팀 양적검증 팀 에이전트 운영 패키지

## 1. 목적

본 패키지는 은행 리스크감리팀이 신용평가모형, PD/LGD/EAD, 위험요소·거시변수, 집계·보고, ST/ICAAP/IRRBB 등 하이브리드 리스크 산출물을 검증할 때 사용할 수 있는 **양적검증 팀 에이전트 운영 기준**이다. 목표는 코드베이스가 아니라, 향후 AVI 하위 서브에이전트로 편입 가능한 역할·프로세스·체크리스트·프롬프트·산출물 템플릿을 제공하는 것이다.

## 2. 적용 업무

- 신용평가모형 검증: 등급모형, 스코어카드, 내부등급법 관련 모형, override 및 등급전이 점검.
- 신용위험측정요소 검증: PD, LGD, EAD, CCF, downturn 조정, backtesting 결과 검토.
- 위험요소 및 거시변수 검증: 변수 정의, 경제적 타당성, 시계열 안정성, 데이터 개정 이력, 시나리오 적합성 점검.
- 리스크 산출 영역 검증: 신용, 시장, 운영, 금리, 유동성, 전략, 평판리스크 및 자본적정성·복합 리스크 산출물의 영역별 입력·계산엔진·정책 기준 점검.
- 정기 모니터링: 월·분기·반기·연간 모니터링 산출물의 누락, 추세, 임계값 초과 후보 확인.
- 수시 검증: 정책 변경, 데이터 이슈, 모형 변경, 규제 이슈, 경영진 요청에 따른 ad-hoc 검증 지원.
- 보고서 초안: 검증대상, 범위, 증적, 계산엔진 결과, 발견사항, 판정 후보, 제한사항 정리.
- 비Green 조치안내: Yellow, Red, Gray 판정 후보에 대한 Action Notice 초안 생성.

## 3. 핵심 하네스 원칙

1. LLM은 직접 수치 계산, 재계산, 추정 계산, 임계값 산출을 수행하지 않는다.
2. 계산엔진 결과, 승인된 리포트, 공식 데이터 증적 없이 정량 결론을 내리지 않는다.
3. 판정 라벨은 `Green`, `Yellow`, `Red`, `Gray`만 허용한다.
4. `Amber` 용어는 금지한다. 입력에 등장해도 출력 판정으로 사용하지 않는다.
5. 정책 미정의, 데이터 부족, 표본 부족, 권한 부족, lineage 불명확, 증적 부족은 `Gray`로 분류한다.
6. `Green`은 최종 승인이나 무결성 보증이 아니라, 제공 증적 기준 중대 이슈 후보가 발견되지 않았다는 상태다.
7. `Yellow`, `Red`, `Gray`는 반드시 Action Notice를 생성한다.
8. 최종 판단과 공식 승인은 인간 검증자 및 공식 승인 조직에 귀속된다.
9. 규제 변화는 후보 검증통제 제안까지만 수행하고 자동 반영하지 않는다.

## 4. 공통 가정

- 은행 내부 정책문서, 승인된 모형문서, 계산엔진 산출물, 데이터 lineage 증적이 공식 판단의 기준이다.
- 본 팀 에이전트는 검증업무 보조, 문서화, 점검 누락 방지, 감사추적 보강을 목적으로 한다.
- 수치 계산과 최종 승인 판단은 에이전트의 역할이 아니다.
- AVI 편입을 고려해 각 문서는 독립적으로도 읽히고, 상위 오케스트레이터가 참조하기 쉬운 고정 섹션 구조를 사용한다.
- 은행별 정책 임계값, 규제 해석, 조직 승인권자는 내부 규정에 따라 별도로 매핑한다.

## 5. 산출물 구성 및 사용 순서

| 순서 | 문서 | 사용 목적 |
|---:|---|---|
| 1 | `TEAM_AGENT_SYSTEM_PROMPT.md` | 팀 에이전트 최상위 운영 프롬프트와 금지행위 정의 |
| 2 | `TEAM_AGENT_ROLE_MAP.md` | 10개 Agent의 책임, 입출력, 핸드오프 기준 정의 |
| 3 | `VALIDATION_OBJECT_CLASSIFICATION.md` | 검증대상 초기 분기와 분류 실패 시 Gray 처리 |
| 4 | `TEAM_AGENT_WORKFLOW.md` | 접수부터 인간 검토까지 End-to-End 절차 정의 |
| 5 | `DATA_READINESS_CHECKLIST.md` | 데이터, 권한, lineage, 증적 준비성 확인 |
| 6 | `QUANT_VALIDATION_METHOD_GUIDE.md` | 계산엔진에 요청할 검증방법 후보와 결과 해석 포인트 정의 |
| 7 | `JUDGEMENT_POLICY_TEMPLATE.md` | Green/Yellow/Red/Gray 판정 정책 템플릿 |
| 8 | `REPORT_TEMPLATE.md` | 검증보고서 초안 표준 양식 |
| 9 | `ACTION_NOTICE_TEMPLATE.md` | Yellow/Red/Gray 조치안내 표준 양식 |
| 10 | `RISK_OUTPUT_TAXONOMY.md` | 신용·시장·운영·금리·유동성·전략·평판리스크 등 산출 영역 세분화 |
| 11 | `BASEL_FSS_CONTROL_MAPPING.md` | 최신 바젤·국내 감독 기준과 검증통제 매핑 |
| 12 | `DETERMINISTIC_DECISION_PROTOCOL.md` | 동일 요청-동일 결과를 위한 fingerprint와 판정 우선순위 |
| 12-1 | `REPRODUCIBILITY_EXPLAINABILITY_GUIDE.md` | 검증결과 재현가능성·설명가능성 운영 기준 |
| 13 | `REG_CHANGE_CANDIDATE_CONTROL.md` | 규제 변화 후보 영향분석 및 후보 통제 제안 절차 |
| 14 | `AUDIT_TRAIL_CHECKLIST.md` | 요청, 입력, 계산결과, 판정, 인간검토 감사추적 |
| 15 | `UAT_EVALUATION_CHECKLIST.md` | 운영 전 사용자 인수 테스트 시나리오와 합격 기준 |
| 16 | `GO_NO_GO_CHECKLIST.md` | 운영 전 최종 Go/No-Go 판단 체크리스트 |
| 17 | `OUTPUT_ARTIFACT_SPEC.md` | 엑셀·실무자 보고서·경영진 보고서 및 md/html/hwpx/pdf 산출물 명세 |
| 18 | `scripts/generate_validation_outputs.py` | 샘플 기반 산출물 생성 스크립트 |
| 19 | `samples/risk_domain_samples.json` | 모든 리스크 산출 영역별 UAT 샘플 데이터 |
| 20 | `tests/validate_risk_domain_samples.py` | 샘플 데이터 완전성·재현성 검증 테스트 |
| 21 | `tests/validate_output_artifacts.py` | 엑셀·보고서 산출물 형식 검증 테스트 |
| 22 | `README.md` | 패키지 개요와 전체 활용 안내 |

## 6. 운영 방식 요약

1. Intake 단계에서 요청 목적, 대상, 기준일, 산출물 기대 수준을 확인한다.
2. 검증대상을 5개 초기 분기 중 하나로 분류하고, `RISK_OUTPUT_TAXONOMY.md`에 따라 `risk_output_domain`을 별도 태깅한다.
3. 데이터 준비성, lineage, 증적, 권한 상태를 점검한다.
4. 정량검증 방법 후보를 선정하되 계산은 승인된 계산엔진에 위임한다.
5. 계산엔진 결과의 존재, 버전, 실행 로그, 입력 데이터 ID를 확인한다.
6. `BASEL_FSS_CONTROL_MAPPING.md`로 기준 출처, 국내 적용 여부, 내부 승인조건을 매핑한다.
7. `DETERMINISTIC_DECISION_PROTOCOL.md`의 fingerprint와 판정 우선순위로 동일 입력에 동일 판정 후보가 나오도록 고정한다.
8. 정책문서와 계산결과를 근거로 판정 후보를 생성한다.
9. 보고서 초안을 작성하고, 비Green은 Action Notice를 별도 생성한다.
10. 감사추적 패키지를 구성해 인간 검증자와 공식 조직의 최종 판단으로 넘긴다.

## 7. AVI 하위 서브에이전트 편입 고려사항

- 모든 산출물은 `case_id`, `request_id`, `case_fingerprint`, `validation_object_type`, `risk_output_domain`, `policy_reference`, `calculation_engine_result_reference`, `provisional_judgement`를 키 필드로 연결한다.
- 상위 오케스트레이터는 Agent별 결과를 순차 또는 병렬로 호출할 수 있으나, 데이터 준비성 미충족 또는 계산엔진 결과 부재 시 정량 결론 단계로 진행하지 않는다.
- 에이전트 출력은 감사추적 가능한 문서 초안이며, 운영계 반영 또는 정책 변경의 자동 실행 트리거가 아니다.

## 8. 감독기준 및 재현성 보강

- `BASEL_FSS_CONTROL_MAPPING.md`는 2026-05-14 기준 공식 BIS/BCBS 및 국내 감독 기준을 운영 통제 항목으로 매핑한다.
- `RISK_OUTPUT_TAXONOMY.md`는 신용, 시장, 운영, 금리, 유동성, 전략, 평판리스크 등 산출 영역을 표준 코드로 세분화한다.
- `DETERMINISTIC_DECISION_PROTOCOL.md`는 동일한 요청, 동일한 리스크 산출 영역, 동일한 정책 버전, 동일한 데이터 해시, 동일한 계산엔진 결과 ID가 제공될 때 동일한 검증결과가 나오도록 fingerprint, 정규화 규칙, 판정 우선순위, tie-break 규칙을 정의한다.
- `REPRODUCIBILITY_EXPLAINABILITY_GUIDE.md`는 `case_fingerprint`, `decision_stage`, `explanation_summary`를 통해 결과 재현성과 설명가능성을 산출물에 남기는 기준을 정의한다.
- 기준 출처 최신성 또는 국내 적용 여부가 불명확하면 자동으로 결론을 확정하지 않고 `Gray`와 Action Notice로 전환한다.

## 9. 샘플 데이터 및 테스트

- `samples/risk_domain_samples.json`은 신용, 시장, 운영, 금리, 유동성, 전략, 평판, 자본적정성·집계, 복합·불명확 영역별 샘플 검증 요청을 포함한다.
- 각 샘플은 `validation_object_type`, `risk_output_domain`, 주영역/부영역, 정책·감독기준 참조, 계산엔진 결과 참조, 증적 공백, 기대 판정 후보, Action Notice 필요 여부를 포함한다.
- `scripts/generate_validation_outputs.py`는 샘플 데이터를 기반으로 통합 엑셀 검증파일, 통합 실무자용/경영진 보고서, 그리고 `validation_object_type` 1축별 산출물 패키지를 생성한다.
- `tests/validate_risk_domain_samples.py`는 모든 표준 영역 코드가 샘플에 존재하는지, 비Green Action Notice 규칙이 지켜지는지, Gray 사유코드가 유효한지, fingerprint가 입력 순서와 무관하게 안정적인지 검증한다.
- `tests/validate_output_artifacts.py`는 통합 및 1축별 xlsx, md, html, hwpx, pdf 산출물의 존재와 기본 패키지 구조를 검증한다.
- `scripts/run_full_sample_tests.py`는 산출물 생성, 산출물 구조 검증, 샘플 데이터 검증을 순서대로 실행하고 상세 결과를 `outputs/sample_test_report.html`로 저장한다.
- 실행 명령: `python quant_validation_team_agent/scripts/generate_validation_outputs.py && python quant_validation_team_agent/tests/validate_output_artifacts.py && python quant_validation_team_agent/tests/validate_risk_domain_samples.py`
- HTML 상세 보고서 생성 명령: `python quant_validation_team_agent/scripts/run_full_sample_tests.py`
