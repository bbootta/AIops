# 전체 리뷰 결과 및 개선 조치

## 1. 리뷰 범위

본 리뷰는 양적검증 팀 에이전트 운영 패키지 전체를 대상으로 수행했다.

- 운영 문서: 프롬프트, 워크플로우, 역할맵, 판정 정책, 규제 매핑, UAT, Go/No-Go.
- 분류 체계: `validation_object_type` 1축, `risk_output_domain` 2축, deterministic fingerprint.
- 샘플 데이터: 9개 리스크 산출 영역 및 5개 검증대상 유형 커버리지.
- 산출물 생성: 엑셀 검증파일, 실무자 보고서, 경영진 보고서, md/html/hwpx/pdf 형식.
- 테스트: 샘플 데이터 검증과 산출물 패키지 검증.

## 2. 발견 사항 및 조치

| 번호 | 발견 사항 | 영향 | 조치 |
|---:|---|---|---|
| 1 | HTML 변환기가 Markdown 표 구분선 `|---|---|` 형태를 표 구분선으로 인식하지 못하고 본문 문단으로 렌더링할 수 있었다. | HTML 보고서에 불필요한 Markdown 구분선이 노출되어 공문형 보고서 품질 저하 가능 | `markdown_to_html`의 표 판별 로직을 `|` 시작/종료 형식 전체로 확장하고, `-`/`:`만 포함된 구분선 행을 건너뛰도록 수정했다. |
| 2 | 1축별 산출물 폴더가 재생성될 때 이전 실행의 잔여 파일이 남을 가능성이 있었다. | 샘플 또는 유형 변경 시 stale artifact가 매니페스트 외부에 남아 감사추적 혼선 가능 | `by_validation_object_type` 폴더를 재생성 전에 삭제하고 새로 쓰도록 변경했다. |
| 3 | 산출물 테스트가 매니페스트 artifact 개수를 상수 `55`로 고정했다. | 보고서 형식 또는 1축 유형 수가 바뀌면 테스트 유지보수성이 저하됨 | 기대 artifact 개수를 보고서 유형, 확장자, 1축 유형 수에서 계산하도록 변경했다. |
| 4 | HTML 테스트가 공문형 필드 존재 여부는 확인했지만 Markdown 표 구분선 노출 여부는 확인하지 않았다. | 동일 문제가 재발해도 테스트가 통과할 수 있음 | HTML에 `|---|` 구분선이 노출되지 않는지 검증을 추가했다. |
| 5 | 검증결과 산출물에 fingerprint와 판정 설명경로가 충분히 드러나지 않았다. | 동일 결과 재현과 감사 설명이 어려울 수 있음 | `case_fingerprint`, `decision_stage`, `explanation_summary`, `Reproducibility`, `Explainability` 시트 및 manifest 인덱스를 추가했다. |

## 3. 현재 남은 한계

- PDF 생성은 외부 PDF 엔진 없이 표준 라이브러리로 만든 샘플 PDF이므로, 한글 렌더링 품질은 실행환경 PDF 뷰어와 폰트 처리에 따라 달라질 수 있다.
- HWPX 생성은 국내 문서교환을 고려한 최소 패키지 샘플이며, 기관별 전자결재 시스템 반입 전에는 실제 HWPX 호환성 테스트가 필요하다.
- 샘플 데이터는 UAT용 가상 증적 식별자이므로 실제 은행 운영 전에는 내부 정책문서, 계산엔진, 데이터 lineage, 승인권자 매핑으로 교체해야 한다.

## 4. 추가 권고

1. 운영 반영 전 실제 전자결재/HWPX 뷰어에서 `outputs/**/*.hwpx` 열람 테스트를 수행한다.
2. 경영진용 PDF는 운영 환경에 WeasyPrint, LibreOffice, 또는 기관 표준 문서변환기를 연결해 한글 폰트 임베딩 품질을 검증한다.
3. 샘플 데이터 대신 익명화된 실제 검증 케이스를 투입해 1축별 산출물 row count와 Action Notice 흐름을 재검증한다.
4. CI에서는 다음 순서로 실행한다.
   - `python quant_validation_team_agent/scripts/generate_validation_outputs.py`
   - `python quant_validation_team_agent/tests/validate_output_artifacts.py`
   - `python quant_validation_team_agent/tests/validate_risk_domain_samples.py`
