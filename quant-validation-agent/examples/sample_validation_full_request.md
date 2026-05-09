# 통합 검증 튜토리얼

본 문서는 quant-validation-agent의 4가지 검증 흐름을 한 번에 실행하는
표준 튜토리얼이다. 모든 데이터는 `examples/`의 합성 샘플이며, 실 운영
데이터는 절대 본 저장소에 포함하지 않는다.

선행 조건:
- `pip install -r requirements.txt`
- 작업 디렉터리는 `quant-validation-agent/` (이 README 위치 기준 한 단계 위)

> **중요**: 본 CLI는 정량 결과만 산출한다. 적합/부적합 결정·외부 보고는
> 인간 검증자의 명시적 승인을 거쳐야 한다.

---

## 0. 환경 점검

```bash
python -m pytest -q                      # 전체 테스트가 통과해야 한다
python -m quant_validation_agent thresholds --metric ks   # 정책 로드 확인
```

---

## 1. 신용평가 / 스코어링 모형

```bash
python -m quant_validation_agent validate \
    --data examples/sample_credit_score_data.csv \
    --model-type scoring \
    --target target \
    --score score \
    --dataset-col dataset \
    --baseline-value dev \
    --segment retail \
    --out reports/scoring.json \
    --log-dir logs/

python -m quant_validation_agent report \
    --input reports/scoring.json \
    --out reports/scoring.md
```

산출:
- `reports/scoring.json` — KS / AUROC / AR / PSI + RAG
- `reports/scoring.md`  — 9-섹션 표준 검증 리포트
- `logs/run_*.json`     — 실행 메타데이터

---

## 2. PD calibration

```bash
python -m quant_validation_agent validate-pd-calibration \
    --data examples/sample_pd_timeseries.csv \
    --pred-col predicted_pd \
    --default-col defaults \
    --count-col count \
    --bucket-col grade \
    --hl-bins 5 \
    --out reports/pd_calibration.json \
    --log-dir logs/
```

옵션 `--hl-rag`를 추가하면 Hosmer-Lemeshow / Spiegelhalter p-value에도
RAG가 부여된다(표본 의존적이므로 해석 시 주의).

```bash
python -m quant_validation_agent validate-pd-calibration \
    --data examples/sample_pd_timeseries.csv \
    --pred-col predicted_pd \
    --default-col defaults \
    --count-col count \
    --bucket-col grade \
    --hl-bins 5 --hl-rag \
    --out reports/pd_calibration_hl_rag.json
```

---

## 3. LGD / EAD

```bash
# LGD: bounded ratio metrics
python -m quant_validation_agent validate \
    --data examples/sample_lgd_ead_data.csv \
    --model-type lgd \
    --actual realized_lgd \
    --predicted predicted_lgd \
    --segment retail \
    --out reports/lgd.json

# EAD with mean_realized normalizer (default)
python -m quant_validation_agent validate \
    --data examples/sample_lgd_ead_data.csv \
    --model-type ead \
    --actual realized_ead \
    --predicted predicted_ead \
    --out reports/ead_mean_realized.json

# EAD with explicit total_exposure normalizer
python -m quant_validation_agent validate \
    --data examples/sample_lgd_ead_data.csv \
    --model-type ead \
    --actual realized_ead \
    --predicted predicted_ead \
    --ead-normalizer total_exposure \
    --out reports/ead_total_exposure.json
```

각 산출 JSON을 `report --input`에 입력하면 9-섹션 markdown이 생성된다.

---

## 4. 거시경제 시나리오 / PD multiplier 회귀

```bash
python -m quant_validation_agent validate-scenario \
    --hist-data examples/sample_macro_history.csv \
    --scenario-data examples/sample_macro_scenario.csv \
    --target pd_multiplier \
    --features gdp_growth,unemployment,bond_spread \
    --period-col period \
    --pred-col-in-scenario pd_multiplier \
    --multiplier-floors base=1.0,adverse=1.0,severe=1.0 \
    --expected-signs gdp_growth=-,unemployment=+,bond_spread=+ \
    --autocorr-lags 4 \
    --stationarity-alpha 0.05 \
    --out reports/scenario.json \
    --log-dir logs/

python -m quant_validation_agent report \
    --scenario-input reports/scenario.json \
    --out reports/scenario.md
```

산출은 회귀 적합 / ADF stationarity / DW · BG · ARCH / 시나리오 서열 / floor
점검을 모두 포함한다.

---

## 5. 거버넌스 점검

```bash
# manifest 일관성 + 정책 변경 거버넌스
python -m pytest tests/test_change_manifest.py tests/test_policy_change_guard.py -q

# 정책 변경 발생 시: 로컬 lock 파일 갱신 (운영팀이 승인 후 수행)
python -c "from middleware.policy_change_guard import update_lock; \
update_lock('harness/threshold_policy.json', 'CHG-XXXX', 'harness/threshold_policy.lock.json')"
```

`assert_policy_changes_approved`는 `threshold_policy.json`을 건드리는 모든
manifest 항목에 `human_approval_required: true`가 있는지 자동 확인한다.

---

## 6. 종료 코드 요약

| 코드 | 의미 |
|---:|---|
| 0 | 정상 |
| 2 | check 서브커맨드에서 위험 키워드 탐지 |
| 3 | check 서브커맨드에서 PII 탐지 |
| 4 | 입력/스키마 오류 (validate, report, validate-pd-calibration) |
| 5 | note add에서 PII/위험 키워드로 차단 |

---

## 7. 한계와 주의

- 본 튜토리얼의 데이터는 합성이며, 결과는 코드 동작 검증 외 의미가 없다.
- 임계값은 정책 미확정 시 `Gray`로 보고된다.
- 운영계 데이터·고객 식별정보는 본 저장소에 절대 저장하지 않는다.
