# threshold_policy.md

본 문서는 RAG(Green/Yellow/Red) 부여를 위한 **임계값 입력 위치**와
**임계값 사용 원칙**을 정의한다.

> **중요:** 본 파일에 적힌 수치는 **참고 예시**이며, 실제 운영 임계값은
> 모형별/포트폴리오별 정책 문서를 따른다. 에이전트는 임의로 기준값을
> 완화·강화하지 않는다.

---

## 1. 임계값 사용 원칙

1. 임계값은 코드에 하드코딩하지 않는다. 함수 인자로 받거나 정책 파일을 참조한다.
2. 임계값 미정의 상태에서 RAG를 **Green**으로 부여하지 않는다. **Gray**로 둔다.
3. 임계값 변경은 인간 검증자 승인이 필요하며, `change_manifest.json`에 기록한다.

---

## 2. 참고 예시 (정책 문서 미확보 시 임시 기준)

| 지표 | 적용 모형 | Green | Yellow | Red | 방향 |
|---|---|---|---|---|---|
| KS | 스코어링 | ≥ 0.40 | 0.30 ~ 0.40 | < 0.30 | higher_is_better |
| AUROC | 스코어링/PD | ≥ 0.75 | 0.65 ~ 0.75 | < 0.65 | higher_is_better |
| AR (Gini) | 스코어링/PD | ≥ 0.50 | 0.30 ~ 0.50 | < 0.30 | higher_is_better |
| PSI (전체) | 스코어링/PD | < 0.10 | 0.10 ~ 0.25 | ≥ 0.25 | lower_is_better |
| Brier | PD | ≤ 0.10 | 0.10 ~ 0.20 | > 0.20 | lower_is_better |
| MAE (LGD) | LGD | ≤ 0.10 | 0.10 ~ 0.20 | > 0.20 | lower_is_better |
| Bias (PD) | PD | abs ≤ 0.01 | 0.01 ~ 0.03 | > 0.03 | abs lower_is_better |
| VIF | 회귀 | ≤ 5 | 5 ~ 10 | > 10 | lower_is_better |
| Condition index | 회귀 | < 15 | 15 ~ 30 | ≥ 30 | lower_is_better |

---

## 3. 표본 적정성 임계 (예시)

| 항목 | Green | Yellow | Red |
|---|---|---|---|
| 전체 표본 수 | ≥ 5,000 | 1,000 ~ 5,000 | < 1,000 |
| 부도건수 | ≥ 200 | 50 ~ 200 | < 50 |
| 등급별 표본 | ≥ 30 | 10 ~ 30 | < 10 |

LDP 포트폴리오는 별도 기준이 필요하다.

---

## 4. 시나리오 서열

- `base_pd ≤ adverse_pd ≤ severe_pd` 위반은 자동 **Red**.
- `multiplier`는 base ≥ 1.0 floor 미적용, severe < base 발생 시 **Red**.
