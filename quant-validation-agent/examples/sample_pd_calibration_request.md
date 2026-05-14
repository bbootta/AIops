# PD Calibration 검증 요청 예시

본 양식은 PD 모형 calibration 검증 요청 시 권장하는 표준 양식이다.
모든 결과는 정량 결과에 근거한 **초안**이며, 인간 검증자의 확인이 필요하다.

---

## 1. 모형명
- 예: 기업 PD 모형 v2.1

## 2. 모형 유형
- PD (calibration 중점)

## 3. 검증 목적
- 정기 운영 검증 (분기 단위)

## 4. 입력 데이터
- 경로: `examples/sample_pd_timeseries.csv`
- 형식: pre-aggregated (등급 × 시점)
- 컬럼: `obs_date`, `grade`, `count`, `defaults`, `predicted_pd`
- 익명화 완료 / 검증용 추출

## 5. 컬럼 매핑
- pred_col: `predicted_pd`
- default_col: `defaults`
- count_col: `count`  (사전 집계 데이터)
- bucket_col: `grade`

## 6. 적용 지표
- Brier score
- PD bias (abs_lower_is_better)
- Hosmer–Lemeshow goodness-of-fit (`hl_bins=5`, LDP 시 `--hl-min-per-bin`)
- Spiegelhalter Z
- Per-bucket binomial test (`--binomial-alpha 0.05`)
- 선택: top-decile lift RAG (`--decile-rag`)
- 선택: HL / Spiegelhalter p-value RAG (`--hl-rag`, 표본 의존 caveat 포함)

## 7. 실행 예
```bash
python -m quant_validation_agent validate-pd-calibration \
    --data examples/sample_pd_timeseries.csv \
    --pred-col predicted_pd \
    --default-col defaults \
    --count-col count \
    --bucket-col grade \
    --hl-bins 5 \
    --decile-rag \
    --out reports/pd_calibration.json \
    --log-dir logs/

python -m quant_validation_agent report \
    --input reports/pd_calibration.json \
    --out reports/pd_calibration.md
```

## 8. 임계값 정책
- `harness/threshold_policy.json` 기준.
- 정책 미확정 지표는 `Gray`.
- `--hl-rag` 사용 시 출력에 포함된 caveat 문구를 반드시 보고서에 인용한다.

## 9. 성공 기준
- 검증 리포트 9개 섹션 충족
- `overall_rag` 필드 존재
- Brier / pd_bias / binomial_summary 모두 산출
- HL `binning` 필드 명시 (quantile 또는 greedy_min_per_bin)
- 결측 / 표본 부족 / LDP 여부는 한계 섹션에 명시

## 10. 한계 / 주의
- HL은 표본 수에 매우 민감하다. LDP 포트폴리오에서는 `--hl-min-per-bin`로 그리디 패킹을 권장한다.
- Spiegelhalter Z는 0/1에 가까운 PD에 대해 분산이 매우 작아져 결과 해석이 불안정할 수 있다.
- 본 CLI 결과만으로 모형 적합/부적합을 단정하지 않는다.
