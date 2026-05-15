# 규제 프레임워크 정렬 검증 요청 예시

본 양식은 Basel / 한국 금감원 프레임워크의 *개념 영역*과 정렬된 정량 검증 요청 표준이다.

> **주의**
> - 본 양식은 **준수 증빙이 아니다.** 정량 분석을 어느 프레임워크 영역과 매핑할지 정리하는 용도다.
> - 특정 조항·문구·번호는 인용하지 않는다. 영역명은 `docs/regulatory_framework_mapping.md`의 내부 코드만 사용한다.
> - 본 결과의 규제 적용·해석은 컴플라이언스/감독당국 담당자가 별도 확인한다 (`CLAUDE.md` §2).

---

## 1. 모형명 / 버전
- 예: 기업 PD 모형 v2.1

## 2. 모형 유형
- (택1) `scoring` / `pd` / `lgd` / `ead` / `pd_multiplier` / `monitoring`

## 3. 적용 영역 (내부 area code)
- `basel_irb_pd`: PD 추정 + 검증 (calibration / discrimination / backtest)
- `basel_irb_lgd`: LGD 추정 (downturn 포함)
- `basel_irb_ead`: EAD/CCF 추정
- `basel_stress`: 시나리오 정합성
- `basel_moc`: Margin of Conservatism
- `ifrs9_pd`: forward-looking PD (IFRS 9 ECL)
- `mrm_basel`: 모형 리스크 관리 일반
- `fss_bank_validation` / `fss_credit_scoring`: 한국 금감원 관련 영역 (개념적 매핑)

복수 선택 가능. 각 area에 대응되는 도구는 `docs/regulatory_framework_mapping.md` 참조.

## 4. 데이터
- 경로 / 추출 기준 / 익명화 여부 / 관측창
- 부도 정의 (예: 90DPD), forbearance 처리 기준 (해당 시)

## 5. 적용 지표 및 임계
- 정책 파일: `harness/threshold_policy.json` (각 metric의 `regulatory_basis` 태그 참조)
- 임계 미확정 항목은 `Gray`로 보고
- 본 요청 단계에서 임계값을 **임의 완화 금지** (`CLAUDE.md` §2)

## 6. 실행 흐름 예시 (Basel IRB PD)
```bash
python -m quant_validation_agent validate \
    --data examples/sample_credit_score_data.csv \
    --model-type scoring \
    --target target --score score \
    --decile-rag --out reports/pd_v2_1.json

python -m quant_validation_agent validate-pd-calibration \
    --data examples/sample_pd_timeseries.csv \
    --pred-col predicted_pd --default-col defaults \
    --count-col count --bucket-col grade \
    --hl-bins 5 --segment-detail \
    --out reports/pd_v2_1_calibration.json

# Backtest 영역 점검 (binomial traffic light)은 tools/backtest_traffic_light.py 직접 호출
python -c "
from tools.backtest_traffic_light import traffic_light_per_bucket, aggregate_zone
import pandas as pd, json, sys
df = pd.read_csv('examples/sample_pd_timeseries.csv')
out = traffic_light_per_bucket(df, 'count', 'defaults', 'predicted_pd', bucket_col='grade')
print(json.dumps({'per_bucket': out.to_dict(orient='records'),
                  'aggregate_zone': aggregate_zone(out)},
                 ensure_ascii=False, indent=2))
" > reports/pd_v2_1_backtest.json
```

## 7. 실행 흐름 예시 (LGD downturn)
```python
import pandas as pd
from tools.downturn_lgd import identify_downturn_periods, compute_downturn_lgd

obs = pd.read_csv("examples/sample_lgd_ead_data.csv")
indicator = pd.read_csv("examples/sample_macro_history.csv")
flags = identify_downturn_periods(indicator, "period", "unemployment", threshold=0.05)
# obs needs a 'period' column aligned with the indicator; in a real run join by
# the default date → period mapping before calling compute_downturn_lgd.
```

## 8. 실행 흐름 예시 (Margin of Conservatism)
```python
from tools.margin_of_conservatism import aggregate_moc, apply_moc

moc = aggregate_moc([
    {"category": "A", "label": "short_history", "value": 0.002,
     "rationale": "obs window 3y"},
    {"category": "B", "label": "estimation_error", "value": 0.001,
     "rationale": "bootstrap CI half-width"},
    {"category": "C", "label": "cycle_uncertainty", "value": 0.0005},
])
adjusted = apply_moc(point_estimate=0.020, total_moc=moc["total_moc"])
```

## 9. 산출물
- 검증 9-section markdown (`report` 서브커맨드)
- area 별 산출 매핑 (본 요청 §3과 일치)
- governance: `policy-governance` + `policy-lock` 결과
- summary: `summary` 서브커맨드로 worst_rag 집계

## 10. 한계 / 면책
- 본 도구의 정량 결과만으로 모형 적합/부적합을 결정하지 않는다.
- 영역 코드는 *작업 매핑*용이며 규제 준수 증빙이 아니다.
- 시나리오·downturn·MoC 정의는 인간 검증자/모형 개발부서가 확정한다.
