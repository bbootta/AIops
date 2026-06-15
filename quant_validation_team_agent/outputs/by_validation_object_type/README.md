# 1축(validation_object_type) 기준 산출물 구성

| validation_object_type | 케이스 수 | 산출물 폴더 | 최적화 목적 |
|---|---:|---|---|
| `credit_rating_model` | 1 | `by_validation_object_type/credit_rating_model/` | 모형문서·등급체계·override·성능검증 중심 검토 |
| `credit_risk_parameter` | 1 | `by_validation_object_type/credit_risk_parameter/` | PD/LGD/EAD 파라미터와 계산엔진 결과 중심 검토 |
| `risk_factor_validation` | 1 | `by_validation_object_type/risk_factor_validation/` | 위험요소·거시변수·외부지표 정의와 lineage 중심 검토 |
| `aggregation_reporting` | 3 | `by_validation_object_type/aggregation_reporting/` | 집계 로직·reconciliation·보고서 증적 중심 검토 |
| `hybrid_risk_output` | 4 | `by_validation_object_type/hybrid_risk_output/` | ST/ICAAP/IRRBB 등 복합 산출물의 주영역·부영역 중심 검토 |

각 폴더에는 해당 1축 유형에 필터링된 `validation_workbook.xlsx`, `practitioner_report.md/html/hwpx/pdf`, `executive_report.md/html/hwpx/pdf`가 생성된다.
모든 산출물은 샘플 증적과 계산엔진 결과 참조를 정리할 뿐, 수치 계산이나 최종 승인 판단을 수행하지 않는다.
