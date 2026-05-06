# quant-validation-agent

은행 리스크관리 검증팀의 **양적검증 전용** Claude Code 에이전트 하네스.
신용평가모형(스코어링), PD/LGD/EAD, 거시경제 시나리오 기반 PD multiplier(회귀모형)에 대한
정량 검증을 표준화·자동화·재현 가능한 형태로 수행한다.

---

## 1. 프로젝트 목적

1. 신용평가모형 양적검증을 표준화한다.
2. PD, LGD, EAD 등 신용위험 측정요소의 정량 검증을 지원한다.
3. 개발 검증과 운영 검증을 구분하여 성능, 안정성, 변별력, 보정력, 표본 적정성을 점검한다.
4. KS, AUROC, Gini/AR, PSI, CDR, SDR, calibration, backtesting, binning stability,
   regression diagnostics 등을 계산한다.
5. 거시경제 시나리오 기반 PD multiplier 또는 예측모형에 대해 시나리오 서열,
   회귀진단, 변수 안정성, 과적합 위험을 점검한다.
6. 모든 계산 로직은 테스트 가능하고 재현 가능해야 한다.
7. 모든 실행 결과와 변경 사항은 `logs/`와 `harness/change_manifest.json`에 기록된다.

---

## 2. 지원 모형 유형

- 신용평가모형 / 스코어링 모형
- PD 모형 (점수 기반, IFRS 9, 내부관리용)
- LGD 모형
- EAD/CCF 모형
- 거시경제 시나리오 기반 PD multiplier / 회귀모형
- 운영 모니터링 지표 산출
- 챌린저 모형 비교

상세는 `docs/model_type_mapping.md` 참조.

---

## 3. 지원 검증 지표

- 변별력: KS, AUROC, Gini, AR, decile lift
- 안정성: PSI, 등급 분포 비교, rank ordering
- 보정력: calibration table, Brier score, PD bias, observed vs predicted
- LGD/EAD 오차: MAE, RMSE, bias, segment 오차
- 회귀진단: R², adjusted R², p-value, VIF, condition index, residual basic
- 시나리오: base ≤ adverse ≤ severe 서열, multiplier floor
- 표본 적정성: 전체/등급/segment 표본 수, 부도건수
- 누수 점검: 사후정보성 컬럼 탐지

---

## 4. 디렉터리 구조

```
quant-validation-agent/
  CLAUDE.md                  # 양적검증 에이전트 운영 지침
  README.md
  requirements.txt
  pyproject.toml
  .gitignore
  harness/                   # 시스템 프롬프트, 정책, 변경 이력
  docs/                      # 사용자 문서
  skills/                    # 모형 유형별 검증 스킬
  subagents/                 # 서브에이전트 정의
  tools/                     # 계산 함수 (pandas/numpy/scipy/sklearn/statsmodels)
  middleware/                # 권한/안전/누수/출력 통제
  tests/                     # pytest
  examples/                  # 샘플 데이터 및 요청/출력 예시
  logs/                      # 실행 로그
  memory/                    # 반복 이슈, 모형별 특이사항
  reports/                   # 검증 산출물
```

---

## 5. 설치

```bash
pip install -r requirements.txt
```

본 프로젝트는 Python 3.10+ 환경을 가정한다.
`pandas`, `numpy`, `scipy`, `scikit-learn`, `statsmodels`를 사용한다.

---

## 6. 테스트 실행

```bash
cd quant-validation-agent
pytest -q
```

테스트는 외부 데이터 의존 없이 내부 DataFrame으로 실행된다.

---

## 7. 샘플 데이터 사용법

`examples/`에 다음 샘플이 포함되어 있다.

- `sample_credit_score_data.csv` — 스코어링 모형 검증용
- `sample_pd_timeseries.csv` — PD calibration / backtesting용
- `sample_lgd_ead_data.csv` — LGD/EAD 오차 검증용
- `sample_macro_scenario.csv` — 시나리오 회귀모형 검증용
- `sample_validation_request.md` — 검증 요청 양식
- `sample_validation_output.md` — 검증 결과 양식

샘플 데이터는 모두 합성 또는 익명화 데이터로 가정한다.
운영 데이터는 절대 본 저장소에 포함하지 않는다.

---

## 8. 운영계 접근 금지

본 에이전트는 다음을 절대 수행하지 않는다.

- 운영계 DB 접속
- 운영 테이블 변경
- 고객 식별정보 저장
- 외부 시스템 반영
- `git push`, 배포

미들웨어 `permission_guard.py`, `data_safety_guard.py`가 위 작업의 단서가 되는
키워드와 패턴을 차단/경고한다.

---

## 9. 인간 승인 필요 영역

다음은 반드시 인간 검증자의 명시적 승인을 받는다.

- 모형 적합/부적합 **확정** 의견
- 감독기관 제출 문안
- 정책 임계값(threshold) 변경
- 운영 반영 또는 모형 교체

검증 의견은 항상 **초안**으로 작성된다.

---

## 10. 한계

- 본 도구는 정량 지표 계산과 표준화된 점검을 목적으로 한다.
- 통계 지표만으로 모형의 적합성을 단정할 수 없다.
- 데이터 품질, 부도 정의, 관측창, 경기 사이클의 영향은 별도 검토가 필요하다.
- low default portfolio, 신규 모형, 짧은 관측기간에서는 결과 해석에 주의해야 한다.
- 회귀진단은 기본 진단에 한정되며, 구조적 모형 적합성은 별도 검토를 요한다.
