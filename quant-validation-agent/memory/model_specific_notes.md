# model_specific_notes.md

모형별 특이사항 및 사전 합의된 검증 메모.

## 양식
- 모형명 / 모형 버전
- 적용 검증 방법
- 임계값 (정책 문서 출처)
- 주의 사항
- 누적 이슈

## 예시
### 개인고객 신용평가모형 v3.2
- 적용 검증: KS/AUROC/AR/PSI/등급별 bad rate
- 임계값: 정책 문서 PMv3.2-validation-spec
- 주의: 신규 가입자 비중 변화 시 PSI 해석 주의
- 누적 이슈: 등급 E 표본 부족 (반복)

### 기업 PD 모형 v2.1
- 적용 검증: calibration / Brier / CDR / SDR / backtest
- 임계값: 정책 문서 CCM-PD2.1
- 주의: LDP 포트폴리오, 다년 누적 표본 사용 필요

### 시나리오 회귀 (FLI) v1.4
- 적용 검증: R²/p-value/VIF/CI/scenario order/floor
- 주의: severe에서 음의 GDP 성장률 영향 검토 필요
- 누적 이슈: 동일 변수의 다중 시차 사용 → 다중공선성 경고
