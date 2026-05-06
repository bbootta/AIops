# project_overview.md

## 무엇인가
quant-validation-agent는 신용평가모형과 신용위험 측정요소(PD/LGD/EAD), 거시경제 시나리오
회귀모형을 정량적으로 검증하기 위한 Claude Code용 에이전트 하네스다.

## 무엇을 하는가
- 검증 요청을 표준 절차로 분해
- 입력 데이터 계약 점검
- 모형 유형별 정량 지표 계산 (KS/AUROC/AR/PSI/CDR/SDR/Calibration/MAE/RMSE/Bias/VIF/CI 등)
- 시나리오 서열, 회귀진단, 시계열 안정성 점검
- 표준 검증 리포트 산출 (RAG 등급 포함)
- 모든 실행을 logs/와 change_manifest로 추적

## 무엇을 하지 않는가
- 운영계 DB 접근, 운영 테이블 변경
- 모형 적합/부적합 확정
- 임계값 임의 변경
- 외부 시스템 반영, git push, 배포

## 핵심 컴포넌트
- `harness/` 정책
- `tools/` 계산 함수
- `middleware/` 통제
- `tests/` pytest
- `docs/`, `examples/` 사용자 인터페이스
- `memory/` 반복 이슈 / 모형별 특이사항
- `logs/`, `reports/` 산출물
