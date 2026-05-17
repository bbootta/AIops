# Sample Macro Validation Request

`tools.run_macro_validation` 의 입력 예시. CSV 한 개 + (선택) 시나리오 가중치
패널을 받는다.

## 1. macro_series.csv (필수)
거시 변수 시계열. target_macro + feature 컬럼.

| period | target_macro | gdp_growth | unemployment | interest_rate |
|---|---|---|---|---|
| 2010-01 | 0.012 | 0.45 | 4.0 | 2.10 |
| 2010-02 | 0.013 | 0.50 | 4.1 | 2.15 |
| ... | ... | ... | ... | ... |

## 2. CLI 실행 예

```
python -m tools.run_macro_validation \
  --csv      ./macro_series.csv \
  --target   target_macro \
  --features gdp_growth,unemployment,interest_rate \
  --period   period \
  --title    "2024 거시 시나리오 모형 검증" \
  --out      ./reports/macro_2024.md
```

## 3. 시나리오 가중치 패널 (선택)

IFRS 9 결합 시는 `MacroValidationRequest.scenario_weight_panel` 인자를 코드에서
직접 주입한다 (CLI 미지원). 신용/IFRS9 runner와 동일한 long format
(period, scenario, weight) 사용.

## 4. 산출 보고서

- 정상성 라벨 (ADF + KPSS 결합)
- VIF 다중공선성
- OLS 잔차 진단 (DW, skew)
- 시나리오 가중치 (제공 시)
- 표준 10 섹션 + DRAFT 워터마크 + plan 첨부
