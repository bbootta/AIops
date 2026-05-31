# Policy — Macro Scenario / Forward-Looking Model

거시경제 시나리오 기반 예측모형의 검증 기준.

## 1. 시계열 점검
- 정상성 (`tools/regression_diagnostics.adf_test`,
  `kpss_test`, `stationarity_summary`)
- 결측·이상치 처리 기준 명시
- 변환·시차 변수 사용 사유 문서화

## 2. 변수 점검
- 다중공선성: VIF > 10 시 다중공선성 의심
- 변수 도메인 합리성

## 3. 모형 진단
- OLS의 잔차 자기상관·이분산·정규성
  (`tools/regression_diagnostics.check_residual_basic`)
- 비선형/패널/혼합 모형은 별도 라이브러리 사용 (한계 문서: `memory/known_limitations.md`)

## 4. 시나리오 정합성
- base ≤ adverse ≤ severe
- 변수 동시 변동의 합리성 (예: 실업률 상승 vs 금리 하락 정합)

## 5. 표본 외 검증
- hold-out / 시계열 cross-validation
- 한 사이클 미만 표본의 경우 일반화 한계 명시

## 6. 금지
- 시나리오 정의 임의 변경
- 정상성 가정 임의 완화
