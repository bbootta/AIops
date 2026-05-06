# metric_policy.md

모형 유형별 적용 지표 및 계산 원칙.
지표 정의는 `docs/metric_definition.md`, 임계값 입력은 `harness/threshold_policy.md` 참조.

---

## 0. 공통 원칙

- 모든 지표는 입력 검증 → 계산 → 수치 범위 확인 → 결과 dict/DataFrame 반환의 4단계.
- 분모 0, NaN, inf는 명시적으로 처리한다.
- 표본 부족, 등급 부족은 지표 산출 자체를 막거나 결과에 표시한다.
- 방향성(higher_is_better)은 인자로 명시한다.
- 운영 DB 접속 코드는 작성하지 않는다.

---

## 1. 신용평가모형 / 스코어링 모형

### 필수 지표
- KS
- AUROC
- Gini 또는 AR (`AR = 2*AUROC - 1`)
- 등급별 bad rate
- 등급별 건수 및 부도건수
- PSI (개발 vs 운영, train vs OOT 등)
- rank ordering (등급↑ 시 bad rate 단조성)
- 개발/운영 성능 비교

### 점검 사항
- score 방향성
- target 정의
- 개발/운영 표본 분리
- 표본 수 부족
- 등급별 역전 현상
- 특정 구간 쏠림
- calibration 저하
- 데이터 누수 가능성

---

## 2. PD 모형

### 필수 지표
- predicted PD vs observed default rate 비교
- calibration table (bucket별)
- Brier score
- bin별 default rate
- CDR (cumulative default rate)
- SDR (survival default rate, 생존기반 부도율)
- backtesting (시점별)
- 시계열 안정성
- 장기평균 PD 대비 단기 관측 괴리

### 점검 사항
- PD 0~1 범위
- 장기평균/단기 혼동
- 부도 정의 일관성
- 관측창 일관성
- LDP 여부
- 경기순환 효과 반영 여부

---

## 3. LGD 모형

### 필수 지표
- predicted LGD vs realized LGD 비교
- MAE, RMSE, bias
- segment별 오차
- 담보유형별 오차
- 회수기간별 안정성
- downturn LGD 여부

### 점검 사항
- LGD 범위
- 회수금액 정의
- 할인율 적용
- 미완료 회수건 처리
- 음수 LGD 또는 100% 초과 처리
- 담보가치 업데이트 기준

---

## 4. EAD/CCF 모형

### 필수 지표
- predicted EAD vs realized EAD 비교
- CCF 오차
- MAE, RMSE, bias
- 상품군별 오차
- 한도사용률 구간별 오차

### 점검 사항
- 미사용한도 정의
- 부도시점 EAD 산정 기준
- off-balance exposure 처리
- 음수/과도한 CCF
- 약정한도 변경 영향

---

## 5. 거시경제 시나리오 / PD multiplier 회귀

### 필수 지표
- R², adjusted R²
- 변수별 p-value
- VIF
- condition index
- 잔차 기본 진단 (평균 ≈ 0, 분산 일정 여부 시각/수치 체크)
- 계수 부호 일관성 (사전 기대 부호)
- scenario order: `base ≤ adverse ≤ severe`
- 시차 구조
- 챌린저 모형 비교

### 점검 사항
- 설명변수 수 과다 여부
- 동일 변수의 다중 시차 중복 사용
- 정상성 변환 여부
- 과적합 가능성
- 표본 수 대비 변수 수
- 시나리오 서열 위반
- stress scenario에서 PD multiplier floor 적용 여부
- 기본 시나리오에 floor를 부적절하게 적용했는지 여부

---

## 6. 모니터링 (운영 검증)

### 필수 지표
- 시점별 PSI
- 등급 분포 변화
- 등급별 default rate 추이
- calibration 추이
- segment별 분포 안정성

### 점검 사항
- 모형 모니터링 임계값 변경 이력
- 분모 변화 (포트폴리오 구성 변화) vs 분자 변화 (실제 부도 증가) 구분

---

## 7. RAG 부여 원칙 (요약)

- **Green**: 임계 충족, 시계열 안정, 표본 적정.
- **Yellow**: 일부 임계 미달, 단일 시점 이상, 표본은 충분.
- **Red**: 다수 임계 미달, 시계열 추세적 악화, 시나리오 서열 위반, calibration 큰 괴리.
- **Gray**: 표본 부족, 데이터 결측 다수, 정의 불명확, 관측창 부족.
