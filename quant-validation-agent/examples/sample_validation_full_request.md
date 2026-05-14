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

---

## 부록 A. 보조 CLI

### A.1 `thresholds` — 정책 조회

```bash
# 단일 지표 (글로벌)
python -m quant_validation_agent thresholds --metric ks

# 세그먼트 override 적용
python -m quant_validation_agent thresholds --metric ks --segment ldp_corporate

# 모형 유형으로 적용 가능한 지표 일괄 조회
python -m quant_validation_agent thresholds --model-type pd

# 대체 정책 파일 사용 (스키마 검증 통과 필요)
python -m quant_validation_agent thresholds --path /path/to/alt_policy.json
```

`thresholds`는 진입 시 `validate_policy`를 자동 실행한다. 정책이 schema를
위반하면 종료 코드 6과 함께 `policy_invalid` 에러가 출력된다.

### A.2 `check` — 위험 키워드 / PII 게이트

```bash
# 인라인 텍스트 점검
python -m quant_validation_agent check --text "DROP TABLE customers"   # → exit 2
python -m quant_validation_agent check --text "user@example.com"        # → exit 3

# 파일 점검
python -m quant_validation_agent check --path examples/sample_validation_request.md
```

- exit 2 : 위험 키워드 (DROP/DELETE/git push/production/운영계 등)
- exit 3 : 개인정보 패턴 (이메일/주민/카드/계좌/전화)
- exit 0 : 통과

### A.3 `note add` — 반복 이슈 노트

```bash
python -m quant_validation_agent note add \
    --text "등급 E 표본 부족 재확인" \
    --model "PD-corp" \
    --path memory/recurring_validation_findings.md
```

- PII / 위험 키워드가 본문에 포함되면 즉시 `exit 5`로 차단되며 파일은 수정되지 않는다.
- 기본 경로는 `memory/recurring_validation_findings.md`.

### A.4 `policy-governance` — 거버넌스 점검

```bash
# 매니페스트 + 로크 파일 종합 점검
python -m quant_validation_agent policy-governance

# lock 파일 동기화까지 강제 (CI 권장)
python -m quant_validation_agent policy-governance --require-lock

# 대체 매니페스트 / 로크 경로 사용
python -m quant_validation_agent policy-governance \
    --manifest-path harness/change_manifest.json \
    --lock-path     harness/threshold_policy.lock.json \
    --policy-path   harness/threshold_policy.json
```

종료 코드:

| 코드 | 의미 |
|---:|---|
| 0 | 매니페스트 거버넌스 통과 (그리고 `--require-lock`이면 lock 동기화도 통과) |
| 6 | `threshold_policy.json`을 변경한 매니페스트 항목 중 하나 이상이 `human_approval_required: true`를 누락 |
| 7 | `--require-lock` 사용 시 lock 부재 또는 digest 불일치 |

### A.5 `report --scenario-input` — 시나리오 회귀 RAG 적용 리포트

```bash
python -m quant_validation_agent validate-scenario \
    --hist-data examples/sample_macro_history.csv \
    --scenario-data examples/sample_macro_scenario.csv \
    --target pd_multiplier \
    --features gdp_growth,unemployment,bond_spread \
    --period-col period --pred-col-in-scenario pd_multiplier \
    --multiplier-floors base=1.0,adverse=1.0,severe=1.0 \
    --out reports/scenario.json

# 시나리오 결과에 R²/VIF/condition_index RAG 자동 부여
python -m quant_validation_agent report \
    --scenario-input reports/scenario.json \
    --out reports/scenario.md

# 대체 정책으로 RAG 부여 (always schema-validated)
python -m quant_validation_agent report \
    --scenario-input reports/scenario.json \
    --threshold-overrides /path/to/alt_policy.json \
    --out reports/scenario_alt.md
```

---

## 부록 C. Makefile 기반 워크플로

`Makefile`은 본 튜토리얼의 모든 흐름을 단일 명령으로 묶는다. 운영계 통신·`git push`·외부 API 호출은 절대 포함하지 않는다.

```bash
make help          # 사용 가능한 타겟 목록
make test          # pytest 전체 (opt-in 테스트는 skip)
make test-strict   # QVA_STRICT_MANIFEST=1 + QVA_STRICT_POLICY_LOCK=1
make governance    # policy-governance --json-only
make smoke         # 4개 모형 + 시나리오 validate*
make report        # smoke 결과를 9-section markdown으로 일괄 변환
make ci            # test + governance + smoke (권장 CI 기본)
make clean         # __pycache__ 및 reports/_smoke_* 정리
```

`make report`는 `make smoke` 의존성을 자동 호출하여 다음 산출물을 생성한다.

| 입력 JSON | 출력 markdown |
|---|---|
| `reports/_smoke_scoring.json` | `reports/_smoke_scoring.md` |
| `reports/_smoke_pd_calibration.json` | `reports/_smoke_pd_calibration.md` |
| `reports/_smoke_lgd.json` | `reports/_smoke_lgd.md` |
| `reports/_smoke_ead.json` | `reports/_smoke_ead.md` |
| `reports/_smoke_scenario.json` | `reports/_smoke_scenario.md` (`--include-stationarity-rag` 적용) |

권장 CI 흐름 예시:

```bash
# 1. 정책 거버넌스 (lock 동기화 강제)
make governance
python -m quant_validation_agent policy-governance --require-lock --json-only

# 2. 테스트 + smoke + report
make ci
make report

# 3. 정책 변경 시 (인간 승인 후)
python -m quant_validation_agent policy-lock --change-id CHG-XXXX           # dry-run
python -m quant_validation_agent policy-lock --change-id CHG-XXXX --confirm  # 실제 갱신
```

---

## 부록 B. 종료 코드 정리

| 코드 | 발생 조건 |
|---:|---|
| 0 | 정상 종료 |
| 2 | `check`에서 위험 키워드 탐지 |
| 3 | `check`에서 PII 탐지 |
| 4 | 입력/스키마 오류 (`validate*`, `report` 입력 누락 등) |
| 5 | `note add`에서 PII/위험 키워드로 차단 |
| 6 | 정책 schema 검증 실패 또는 `policy-governance` 매니페스트 거버넌스 위반 |
| 7 | `policy-governance --require-lock` 사용 시 lock 미존재/불일치 |
