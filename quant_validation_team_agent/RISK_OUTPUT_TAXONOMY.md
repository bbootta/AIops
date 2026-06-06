# 리스크 산출 영역 세분화 기준

## 1. 목적

본 문서는 검증 요청을 기존 검증대상 유형(`validation_object_type`)과 별도로 **리스크 산출 영역(`risk_output_domain`)**으로 세분화하기 위한 기준이다. 동일한 검증대상이라도 신용, 시장, 운영, 금리, 유동성, 전략, 평판리스크 중 어느 산출 영역에 속하는지에 따라 입력자료, 계산엔진 결과, 정책 기준, 보고서 독자가 달라지므로 Intake 단계에서 반드시 별도 태깅한다.

## 2. 공통 가정 및 하네스

- `risk_output_domain`은 판정 라벨이 아니며, 판정은 계속 `Green`, `Yellow`, `Red`, `Gray`만 사용한다.
- LLM은 각 영역의 수치 산출, VaR, EVE/NII, LCR/NSFR, 운영손실, 경제적자본, 민감도, 평판지표 계산을 수행하지 않는다.
- 계산엔진 결과, 승인된 리포트, 공식 정책 없이 정량 결론을 내리지 않는다.
- 영역 분류가 불명확하거나 복수 영역 영향이 있으나 주영역을 정할 증적이 없으면 `risk_output_domain = multi_risk_or_unclear`와 `Gray` 후보를 기록한다.
- 같은 요청에 같은 입력과 같은 정책 버전이 제공되면 동일한 `risk_output_domain`이 산출되어야 한다.

## 3. 표준 리스크 산출 영역 코드

| 코드 | 명칭 | 대표 산출물 | 대표 계산엔진/증적 | 주요 검증 포인트 | Gray 조건 |
|---|---|---|---|---|---|
| `credit_risk` | 신용리스크 | PD/LGD/EAD, EL, RWA, 등급전이, 부도율, 여신 포트폴리오 모니터링 | 신용평가시스템, IRB/표준방법 산출물, 부도·회수·한도 데이터 | default 정의, 등급체계, 파라미터 산출, calibration, backtesting, concentration | default 정의 불명확, PD/LGD/EAD 산출물 부재, 신용 데이터 lineage 불명확 |
| `market_risk` | 시장리스크 | VaR/SVaR, IRC/CRM, sensitivities, Greeks, P&L attribution, backtesting exception | 시장리스크 엔진, 가격검증, 포지션·시장데이터, P&L 시스템 | 포지션 완전성, 시장데이터 출처, 가격모형, backtesting, P&L explain, limit breach | 포지션 기준일 불명확, 시장데이터 출처 부재, 가격모형 승인 증적 부족 |
| `operational_risk` | 운영리스크 | 운영손실, KRI, RCSA, 시나리오 분석, 내부통제 이슈, BIC/ILM 후보 산출물 | 손실사건 DB, KRI 시스템, RCSA, 내부통제/감사 지적 | 손실사건 완전성, 경계사건 분류, 원인·영향 매핑, 시나리오 승인, 통제 개선 추적 | 손실사건 기준 불명확, 사건 누락 의심, RCSA 증적 부족 |
| `interest_rate_risk` | 금리리스크 | IRRBB EVE/NII, repricing gap, duration, basis risk, optionality risk | ALM/IRRBB 엔진, 금리곡선, 계정계 현금흐름, 행동모형 | 금리곡선 출처, 행동가정, 만기·repricing 매핑, 시나리오 승인, 민감도 산출물 | 행동가정 미승인, 현금흐름 lineage 불명확, 금리곡선 버전 부재 |
| `liquidity_risk` | 유동성리스크 | LCR/NSFR, liquidity gap, survival horizon, cash flow projection, funding concentration | 유동성 엔진, 현금흐름 데이터, 예수금/조달/담보 시스템 | 현금흐름 완전성, run-off 가정, HQLA 적격성, stress scenario, intraday liquidity | HQLA 분류 증적 부족, 현금흐름 기준일 불명확, run-off 정책 미정의 |
| `strategic_risk` | 전략리스크 | 사업계획 리스크, 수익성·자본계획 민감도, 신규사업/철수 영향, 중장기 KPI | 경영계획, ICAAP, 예산/실적, 시나리오 분석 | 전략가정 승인, 사업계획-리스크 지표 연결, 자본·수익성 영향, 경영진 승인 증적 | 전략가정 미승인, KPI 정의 불명확, 시나리오 출처 부족 |
| `reputational_risk` | 평판리스크 | 민원/분쟁, 언론·SNS 지표, 고객이탈, conduct issue, 브랜드 영향 평가 | 민원 시스템, 소비자보호, 컴플라이언스, 외부 모니터링 리포트 | 사건 정의, 심각도 기준, 데이터 출처, 중복 제거, 리스크 전이 경로, 조치 추적 | 평판 사건 기준 미정의, 외부 데이터 사용권한 불명확, 증적 부족 |
| `capital_adequacy_aggregation` | 자본적정성·집계 | ICAAP, 경제적자본, RWA aggregation, stress capital impact, risk appetite dashboard | 자본관리/리스크 집계 엔진, 재무·리스크 데이터마트 | 위험유형 간 합산 로직, diversification 가정, reconciliation, 이사회 보고 일관성 | 위험유형 매핑 불명확, 합산 로직 미문서화, reconciliation 부재 |
| `multi_risk_or_unclear` | 복합·불명확 | ST/ICAAP/Recovery Plan 등 복합 산출물 또는 분류 불가 산출물 | 복수 엔진 결과, 시나리오 패키지, 경영진 보고서 | 주영역/부영역 구분, 산출물 소유자, 기준 중복·충돌, 복합 lineage | 주영역 불명확, 복수 정책 충돌, 증적 부족 |


## 3-A. 텍스트 입력 alias 정규화

사용자가 표준 코드 대신 한글 명칭, 영문 명칭, 약어를 입력한 경우 에이전트는 Gray로 즉시 전환하지 않고 아래 alias를 먼저 표준 코드로 정규화한다. 정규화 가능한 텍스트 입력은 `case_fingerprint` 불일치 사유가 아니며, fingerprint에는 정규화 후 코드만 사용한다.

| 표준 코드 | 허용 alias 예시 |
|---|---|
| `credit_risk` | 신용리스크, 신용 위험, Credit Risk |
| `market_risk` | 시장리스크, 시장 위험, Market Risk |
| `operational_risk` | 운영리스크, Operational Risk |
| `interest_rate_risk` | 금리리스크, IRRBB, Interest Rate Risk |
| `liquidity_risk` | 유동성리스크, Liquidity Risk |
| `strategic_risk` | 전략리스크, Strategic Risk |
| `reputational_risk` | 평판리스크, Reputational Risk |
| `capital_adequacy_aggregation` | 자본적정성 집계, ICAAP/RWA 집계, Capital Adequacy Aggregation |
| `multi_risk_or_unclear` | 복합, 불명확, Multi Risk or Unclear |

Alias 매핑 후에도 표준 코드가 결정되지 않거나 주영역 근거가 없을 때만 `multi_risk_or_unclear` 및 `Gray` 후보로 처리한다.

## 4. 2축 분류 원칙

검증 요청은 아래 2개 축으로 동시에 분류한다.

| 축 | 필드 | 예시 |
|---|---|---|
| 검증대상 유형 | `validation_object_type` | `credit_risk_parameter`, `risk_factor_validation`, `aggregation_reporting`, `hybrid_risk_output` |
| 리스크 산출 영역 | `risk_output_domain` | `credit_risk`, `market_risk`, `interest_rate_risk`, `liquidity_risk` |

예시:

- PD backtesting 요청: `validation_object_type = credit_risk_parameter`, `risk_output_domain = credit_risk`.
- IRRBB EVE 민감도 검토: `validation_object_type = hybrid_risk_output`, `risk_output_domain = interest_rate_risk`.
- LCR 산출 검증: `validation_object_type = aggregation_reporting`, `risk_output_domain = liquidity_risk`.
- 시장 VaR backtesting: `validation_object_type = risk_factor_validation` 또는 `hybrid_risk_output`, `risk_output_domain = market_risk`.
- 운영손실 시나리오 분석: `validation_object_type = hybrid_risk_output`, `risk_output_domain = operational_risk`.

## 5. 영역별 필수 입력자료

| 리스크 영역 | 필수 입력자료 |
|---|---|
| 신용리스크 | 여신·차주·담보·부도·회수·한도 데이터, 신용평가모형 문서, PD/LGD/EAD 방법론, 계산엔진 결과 |
| 시장리스크 | 포지션 원장, 시장데이터, 가격모형 승인문서, VaR/민감도/P&L 결과, limit breach 이력 |
| 운영리스크 | 손실사건 원장, KRI 정의, RCSA 결과, 시나리오 승인문서, 내부통제 조치 이력 |
| 금리리스크 | ALM 현금흐름, 금리곡선, 행동가정, EVE/NII 결과, IRRBB 정책 및 시나리오 |
| 유동성리스크 | 현금흐름, HQLA 분류, 예수금/조달 데이터, LCR/NSFR 결과, stress 가정 |
| 전략리스크 | 경영계획, 예산·실적, 자본계획, 전략 시나리오, 경영진 승인문서 |
| 평판리스크 | 민원·분쟁·언론·소셜 데이터, 사건 분류 기준, 심각도 기준, 조치 이력, 데이터 사용권한 |
| 자본적정성·집계 | 위험유형별 산출물, 합산 로직, diversification 가정, reconciliation, 이사회 보고자료 |

## 6. 영역별 Action Notice 예시 사유

| 리스크 영역 | 비Green 예시 사유 | 기본 처리 |
|---|---|---|
| 신용리스크 | default 정의와 계산엔진 입력 정의 불일치 | Gray 또는 Red 후보, 정의 정합성 증적 요청 |
| 시장리스크 | 시장데이터 vendor 버전과 가격검증 데이터 불일치 | Gray, 데이터 출처 reconciliation 요청 |
| 운영리스크 | 손실사건 누락 가능성이 있으나 사건 등록 기준 불명확 | Gray, 사건 기준 및 누락 점검 요청 |
| 금리리스크 | 행동가정이 승인 문서와 다르게 적용됨 | Red 또는 Gray 후보, 승인 가정과 엔진 설정 비교 요청 |
| 유동성리스크 | HQLA 적격성 증적 없이 LCR 결과만 제출 | Gray, HQLA 증적 및 계산 로그 요청 |
| 전략리스크 | 사업계획 시나리오가 공식 승인되지 않음 | Gray, 경영진 승인 증적 요청 |
| 평판리스크 | 외부 데이터 사용권한과 수집 기준 불명확 | Gray, 권한·출처·중복제거 기준 요청 |

## 7. 감사추적 요구사항

- 모든 산출물에는 `risk_output_domain`, 주영역/부영역 여부, 영역 분류 근거를 기록한다.
- 복합 산출물은 `primary_risk_output_domain`과 `secondary_risk_output_domains`를 분리한다.
- 동일 요청-동일 결과 검증을 위해 `risk_output_domain`은 `case_fingerprint` 입력 필드에 포함한다.
- 영역 분류가 바뀌면 기존 fingerprint와 다른 건으로 처리하고, 변경 사유를 감사추적에 기록한다.

