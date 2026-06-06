# 검증 결과 산출물 패키지 명세

## 1. 목적

본 문서는 양적검증 팀 에이전트가 검증 결과를 실무자가 바로 검토할 수 있는 산출물 패키지로 구성하기 위한 표준이다. 산출물은 엑셀 검증파일, 실무자용 상세 보고서, 경영진 보고서로 분리하고, 보고서는 `md`, `html`, `hwpx`, `pdf` 형식을 모두 제공한다.

## 2. 공통 가정 및 하네스

- 모든 수치성 내용은 계산엔진 결과 ID, 승인된 리포트, 공식 증적의 참조값으로만 기록한다.
- LLM 또는 산출물 생성 스크립트는 VaR, PD, LGD, EAD, LCR, EVE/NII, 운영손실, 경제적자본 등 리스크 지표를 계산하지 않는다.
- 판정 라벨은 `Green`, `Yellow`, `Red`, `Gray`만 사용한다.
- `Yellow`, `Red`, `Gray`는 Action Notice 대상이며, `Green`은 최종 승인 아님 문구를 포함한다.
- 공문형 문서 양식은 내부 검토 초안이며, 공식 발송·시행·결재는 인간 검증자와 공식 조직이 수행한다.

## 3. 산출물 구성

| 산출물 | 파일명 예시 | 주요 사용자 | 목적 |
|---|---|---|---|
| 엑셀 검증파일 | `validation_workbook.xlsx` | 실무자, 검증자, 감사추적 담당 | 케이스 목록, 증적 공백, Action Notice, 감사추적 항목을 표 형태로 검토 |
| 실무자용 보고서 | `practitioner_report.md/html/hwpx/pdf` | 리스크감리 실무자, 모델/데이터 담당자 | 상세 검토 근거, 영역별 이슈, 필요 증적, 재검증 조건 확인 |
| 경영진 보고서 | `executive_report.md/html/hwpx/pdf` | 부서장, 임원, 위원회 | 핵심 현황, 비Green 요약, 의사결정 필요사항 확인 |
| 산출물 매니페스트 | `artifact_manifest.json` | 운영자, 감사추적 담당 | 생성 파일 목록, 생성 기준일, 원천 샘플, `sample_fingerprints`, `explainability_index`, `fingerprint_fields`, fingerprint, 설명 인덱스 확인 |
| 전체 샘플 테스트 상세 보고서 | `sample_test_report.html` | UAT 수행자, 리뷰어 | 전체 샘플 테스트 명령별 결과, 판정/영역 분포, 케이스별 fingerprint와 설명가능성 확인 |
| 1축별 산출물 패키지 | `by_validation_object_type/<type>/` | 업무유형별 실무자, 검증 책임자 | `validation_object_type` 기준으로 필터링된 엑셀·실무자·경영진 보고서 검토 |


## 4. 1축 기준 산출물 최적화

1축인 `validation_object_type` 기준으로 산출물을 별도 폴더에 분리한다. 통합 산출물은 전체 현황과 경영진 총괄 보고에 사용하고, 1축별 산출물은 담당 실무자의 상세 검토와 증적 보완 요청에 사용한다.

| validation_object_type | 산출물 폴더 | 최적화 초점 |
|---|---|---|
| `credit_rating_model` | `outputs/by_validation_object_type/credit_rating_model/` | 모형문서, 등급체계, override, 성능검증 결과 중심 |
| `credit_risk_parameter` | `outputs/by_validation_object_type/credit_risk_parameter/` | PD/LGD/EAD 방법론, 계산엔진 결과, backtesting 중심 |
| `risk_factor_validation` | `outputs/by_validation_object_type/risk_factor_validation/` | 위험요소·거시변수 정의, 원천, lineage, 시계열 증적 중심 |
| `aggregation_reporting` | `outputs/by_validation_object_type/aggregation_reporting/` | 집계 로직, reconciliation, 보고서 수치 출처 중심 |
| `hybrid_risk_output` | `outputs/by_validation_object_type/hybrid_risk_output/` | ST/ICAAP/IRRBB 등 복합 산출물의 주영역·부영역과 정책 매핑 중심 |

각 폴더는 `validation_workbook.xlsx`, `practitioner_report.md/html/hwpx/pdf`, `executive_report.md/html/hwpx/pdf`를 포함한다.

## 5. 공공기관 공문형 보고서 구성

보고서는 최대한 공공기관 공문 형식을 따르되, 공식 공문이 아니라 내부 검토 초안임을 표시한다.

- 문서번호
- 시행일자
- 공개구분
- 보존기간
- 수신
- 참조
- 제목
- 검토 목적
- 검토 근거
- 주요 검토 결과
- 비Green 조치안내
- 인간 검증자 확인사항
- 붙임 목록
- 결재란 또는 검토란

## 6. 형식별 원칙

| 형식 | 생성 원칙 |
|---|---|
| `md` | 원문 관리와 리뷰 편의를 위한 기준 형식 |
| `html` | 브라우저 열람과 공문형 스타일 확인용 |
| `hwpx` | 국내 공공기관 문서교환을 고려한 HWPX 패키지 형식의 샘플 |
| `pdf` | 경영진 배포용 고정 레이아웃 샘플. 한글 폰트 렌더링은 실행환경 PDF 뷰어와 폰트에 의존 |
| `xlsx` | 실무 검증표, 필터링, 증적 추적을 위한 워크북 |

## 7. 생성 및 검증 명령

```bash
python quant_validation_team_agent/scripts/generate_validation_outputs.py
python quant_validation_team_agent/tests/validate_output_artifacts.py
python quant_validation_team_agent/tests/validate_risk_domain_samples.py
python quant_validation_team_agent/scripts/run_full_sample_tests.py
```

## 8. 운영 전 확인사항

- 생성된 엑셀 파일의 케이스 수가 샘플 데이터의 케이스 수와 일치해야 한다.
- 엑셀 파일은 `Reproducibility`와 `Explainability` 시트를 포함해야 한다.
- Governance & Audit Trail Agent는 `artifact_manifest.json`을 생성하고, Report & Visualization Agent는 보고서 생성 시 매니페스트 입력 목록을 확정해야 한다.
- 매니페스트는 `sample_fingerprints`, `explainability_index`, `fingerprint_fields`를 포함해야 한다.
- `fingerprint_fields`는 `DETERMINISTIC_DECISION_PROTOCOL.md`의 `case_fingerprint_inputs`와 동일해야 하며, 누락 시 `validate_output_artifacts.py` 실패 및 `Gray` 후보로 처리한다.
- 통합 보고서 2종과 1축별 보고서 2종은 각각 md/html/hwpx/pdf 형식이 모두 존재해야 한다.
- HWPX와 XLSX는 ZIP 패키지로 열리고 필수 내부 파일을 포함해야 한다.
- PDF는 `%PDF-` 헤더와 `%%EOF` 종료 마커를 포함해야 한다.
- 산출물에는 “최종 승인 아님”과 “LLM 수치 계산 금지” 취지의 문구가 포함되어야 한다.
