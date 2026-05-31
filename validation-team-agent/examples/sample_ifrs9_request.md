# Sample IFRS 9 ECL Validation Request

`tools.run_ifrs9_validation`이 받는 입력 예시. CSV 모드로 사용한다면 아래 4개
파일을 준비하고 `--weights-csv`/`--pd-csv`/`--multipliers-csv`/`--calibration-csv`
인자에 지정한다.

## 1. weights.csv (필수)
시점·시나리오·가중치 패널. 시점별로 가중치 합 = 1.

| period | scenario | weight |
|---|---|---|
| 2024-Q1 | base | 0.5 |
| 2024-Q1 | adverse | 0.3 |
| 2024-Q1 | severe | 0.2 |
| 2024-Q2 | base | 0.5 |
| 2024-Q2 | adverse | 0.3 |
| 2024-Q2 | severe | 0.2 |

## 2. pd.csv (선택)
시나리오별 PD long format. 시나리오 서열 점검(base ≤ adverse ≤ severe)에 사용.

| scenario | pd |
|---|---|
| base | 0.010 |
| base | 0.020 |
| adverse | 0.015 |
| adverse | 0.025 |
| severe | 0.025 |
| severe | 0.040 |

## 3. multipliers.csv (선택)
시나리오별 PD multiplier. `harness/scenario_floors.json` 의 floor 정책과 비교.

| scenario | multiplier |
|---|---|
| base | 1.0 |
| adverse | 1.5 |
| severe | 2.5 |

## 4. calibration.csv (선택)
등급별 추정 PD vs 실측. binomial test + Holm 보정.

| grade | pd_estimated | default_count | exposure_count |
|---|---|---|---|
| A | 0.01 | 12 | 1000 |
| B | 0.05 | 55 | 1000 |
| C | 0.10 | 105 | 1000 |

## 5. CLI 실행 예

```
python -m tools.run_ifrs9_validation \
  --weights-csv      ./weights.csv \
  --pd-csv           ./pd.csv \
  --multipliers-csv  ./multipliers.csv \
  --calibration-csv  ./calibration.csv \
  --title            "IFRS 9 ECL 정기 검증 — 2024-Q2" \
  --out              ./reports/ifrs9_2024Q2.md
```

생성 보고서는 표준 10 섹션 + DRAFT 워터마크 + dry_run plan 첨부를 포함한다.
