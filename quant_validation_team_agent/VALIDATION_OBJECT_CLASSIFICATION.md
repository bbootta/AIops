# 검증대상 분류 기준

## 1. 목적

요청을 초기에 일관되게 분류해 적절한 데이터 점검, 검증방법 후보, 보고서 양식, Action Notice 절차로 연결한다. 검증대상 유형과 리스크 산출 영역은 별도 축으로 분류한다.

## 2. 공통 가정 및 통제

- 검증대상 분류가 불명확하면 임의 확정하지 않고 `Gray` 후보로 처리한다.
- `Amber`는 분류 또는 판정 용어로 사용하지 않는다.
- 분류 결과는 검증 범위 설정을 위한 후보이며 인간 검증자가 최종 확인한다.

## 3. 2축 분류 원칙

- `validation_object_type`: 무엇을 검증하는지 나타내는 업무·산출물 유형이다.
- `risk_output_domain`: 산출물이 어느 리스크 영역에 속하는지 나타내며 `RISK_OUTPUT_TAXONOMY.md`의 표준 코드를 사용한다.
- 모든 요청은 두 필드를 모두 기록한다. 어느 한 축이라도 불명확하면 해당 축을 불명확으로 두고 `Gray` 후보 및 추가자료 요청을 생성한다.

## 4. 초기 분기 요약

| 코드 | 명칭 | 대표 대상 | 후속 Agent |
|---|---|---|---|
| `credit_rating_model` | 신용평가모형 | 내부등급모형, 스코어카드, 등급전이, override | Data Readiness, Quant Method |
| `credit_risk_parameter` | PD/LGD/EAD | PD, LGD, EAD, CCF, downturn 조정 | Data Readiness, Quant Method |
| `risk_factor_validation` | 위험요소·거시변수 | 금리, 환율, GDP, 실업률, 부동산지수, 산업지표 | Data Readiness, Quant Method |
| `aggregation_reporting` | 집계·보고 | 포트폴리오 집계, 리스크 보고서, 대시보드, 규제보고 | Data Readiness, Report |
| `hybrid_risk_output` | ST/ICAAP/IRRBB 등 | 스트레스테스트, ICAAP, IRRBB, 시나리오 기반 산출물 | Data Readiness, Policy, Report |
| `분류불가` | 분류불가 | 요청 설명만으로 5개 유형 중 하나를 결정할 수 없는 대상 | Action Notice, 인간 검증자 재범위 지정 |

## 5. 리스크 산출 영역 빠른 매핑

| risk_output_domain | 대표 요청 | 자주 결합되는 validation_object_type |
|---|---|---|
| `credit_risk` | PD/LGD/EAD, 등급전이, RWA, 여신 포트폴리오 | `credit_rating_model`, `credit_risk_parameter`, `aggregation_reporting` |
| `market_risk` | VaR, 민감도, P&L attribution, 시장데이터 검증 | `risk_factor_validation`, `hybrid_risk_output`, `aggregation_reporting` |
| `operational_risk` | 운영손실, KRI, RCSA, 시나리오 분석 | `hybrid_risk_output`, `aggregation_reporting` |
| `interest_rate_risk` | IRRBB EVE/NII, repricing gap, 금리곡선 검증 | `risk_factor_validation`, `hybrid_risk_output` |
| `liquidity_risk` | LCR/NSFR, liquidity gap, survival horizon | `aggregation_reporting`, `hybrid_risk_output` |
| `strategic_risk` | 사업계획·자본계획 민감도, 전략 시나리오 | `hybrid_risk_output`, `aggregation_reporting` |
| `reputational_risk` | 민원·언론·소셜 지표, conduct issue 영향 | `risk_factor_validation`, `aggregation_reporting` |
| `capital_adequacy_aggregation` | ICAAP, 경제적자본, risk appetite dashboard | `aggregation_reporting`, `hybrid_risk_output` |
| `multi_risk_or_unclear` | 복합 산출물 또는 주영역 불명확 | 모든 유형 |

## 6. 상세 분류 기준

### 4.1 `credit_rating_model`: 신용평가모형

- 대표 사례: 기업여신 등급모형, 소매 스코어카드, 신청평점/행동평점, 등급전이 모니터링, override 적정성 점검.
- 필수 입력자료: 승인된 모형문서, 개발/검증 데이터 명세, 등급 정의, 모형 버전, cut-off 정책, override 정책, 계산엔진 성능지표 산출물.
- 주요 검증 질문: 모형 목적과 사용처가 일치하는가, 변별력과 보정 결과가 정책 기준에 비추어 해석 가능한가, 등급별 표본과 부도 관측이 충분한가, override가 정책에 맞게 관리되는가.
- 권장 검증방법 후보: 변별력, 안정성, calibration, 등급전이, backtesting, override 분석, champion/challenger 비교 결과 리뷰.
- Gray 조건: 모형 승인문서 부재, 등급 정의 불명확, 개발/검증 데이터 lineage 불명확, 계산엔진 성능지표 부재, 표본 부족.

### 4.2 `credit_risk_parameter`: PD/LGD/EAD

- 대표 사례: PD 장기평균, LGD workout 산출, EAD/CCF 추정, downturn 조정, IRB 파라미터 검증.
- 필수 입력자료: 파라미터 방법론, default 정의, 관측기간, 원천 데이터, 회수·담보·한도 데이터, 계산엔진 결과, 승인 임계값.
- 주요 검증 질문: default 정의가 일관되는가, 관측기간과 표본이 충분한가, downturn 적용 근거가 있는가, 계산엔진 결과의 입력·버전·로그가 재현 가능한가.
- 권장 검증방법 후보: PD calibration/backtesting, LGD 회수현금흐름 검토, EAD CCF 분석, segment 안정성, 민감도 분석 결과 리뷰.
- Gray 조건: default 정의 불명확, 회수자료 접근권한 부족, 표본 부족, 계산엔진 결과 미제공, 정책 임계값 미정의.

### 4.3 `risk_factor_validation`: 위험요소·거시변수

- 대표 사례: 스트레스테스트 거시변수, 산업위험 변수, 금리·환율·부동산 지표, 시나리오 설명변수.
- 필수 입력자료: 변수 정의서, 원천기관, 시계열 데이터, 개정 이력, 결측 처리 정책, 경제적 타당성 근거, 시나리오 문서.
- 주요 검증 질문: 변수 정의와 원천이 명확한가, 개정 이력이 관리되는가, 결측·이상치 처리 근거가 있는가, 모형 또는 시나리오 목적과 경제적 연결성이 있는가.
- 권장 검증방법 후보: 시계열 안정성, 상관구조, 결측·개정 이력 검토, 경제적 방향성 검토, 시나리오 적합성 리뷰.
- Gray 조건: 공식 원천 미확인, 정책 미정의, 개정 이력 부재, 변수 lineage 불명확, 경제적 타당성 증적 부족.

### 4.4 `aggregation_reporting`: 집계·보고

- 대표 사례: 월간 리스크 대시보드, 규제보고 수치 집계, 포트폴리오 세그먼트별 요약, 경영진 보고서.
- 필수 입력자료: 보고서 정의서, 집계 로직, 데이터 기준일, 필터 조건, reconciliation 결과, 승인된 계산엔진 산출물.
- 주요 검증 질문: 원천 데이터와 보고 수치가 reconciliation 되는가, 집계 기준과 필터가 문서화되어 있는가, 보고 기준일과 버전이 명확한가.
- 권장 검증방법 후보: 집계 로직 리뷰, reconciliation 결과 검토, 전월 대비 변동 사유 확인, 보고서 내 수치 출처 확인.
- Gray 조건: 집계 로직 미문서화, 기준일 불명확, 원천-보고 reconciliation 부재, 계산결과 ID 부재.

### 4.5 `hybrid_risk_output`: ST/ICAAP/IRRBB 등

- 대표 사례: 스트레스테스트 결과, ICAAP 내부자본 적정성 산출, IRRBB 금리위험 산출, 복합 시나리오 결과.
- 필수 입력자료: 시나리오 문서, 정책 기준, 산출물 정의서, 모형/계산엔진 결과, 이사회·위원회 승인 이력, 데이터 lineage.
- 주요 검증 질문: 시나리오와 산출 목적이 일치하는가, 입력 데이터와 계산결과가 재현 가능한가, 정책 기준과 보고 형식에 부합하는가.
- 권장 검증방법 후보: 시나리오 타당성 검토, 산출물 reconciliation, 민감도 결과 리뷰, 정책 기준 매핑, 제한사항 검토.
- Gray 조건: 시나리오 승인 이력 부재, 정책 미정의, 계산엔진 결과 미제공, 복합 산출물 lineage 불명확.

## 7. 분류 실패 처리

- 요청 설명만으로 분류가 불가능하면 `validation_object_type = 분류불가`로 기록한다. Section 4 요약표를 룩업으로 사용하는 구현자도 이를 비표준 오류가 아니라 표준 Gray/검토 분기로 처리해야 한다.
- `validation_object_type` 분류불가 또는 `risk_output_domain` 분류불가는 `Gray` 후보이며, 추가 자료 요청 Action Notice를 생성한다.
- 인간 검증자가 업무 범위를 재지정하기 전까지 정량검증 방법 선정 단계로 진행하지 않는다.
