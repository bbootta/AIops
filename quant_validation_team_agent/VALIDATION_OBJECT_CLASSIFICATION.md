# VALIDATION_OBJECT_CLASSIFICATION

## 1. 목적

검증 요청을 초기에 일관되게 분류하여 적절한 체크리스트, 검증방법 후보, 계산엔진 산출물 요청, 보고서 템플릿으로 연결한다.

## 2. 분류 원칙

- 요청은 가능한 한 5개 분기 중 하나로 분류한다.
- 복수 유형이 섞인 경우 주된 산출물의 사용 목적과 리스크 영향 기준으로 1차 유형을 정하고, 보조 유형을 기록한다.
- 분류에 필요한 정보가 부족하면 분류불가로 기록하고 Gray 후보로 전환한다.
- 분류 결과는 최종 판단이 아니라 워크플로우 라우팅 목적이다.

## 3. 분기별 기준

### 3.1 `credit_rating_model`: 신용평가모형

- 대표 사례: 기업여신 등급모형 정기검증, 소매 스코어카드 검증, 등급전이 모니터링, override 적정성 점검.
- 필수 입력자료: 모형개발문서, 승인문서, 등급 산출 로직, 개발·검증 데이터, 계산엔진 성능지표, override 정책.
- 주요 검증 질문: 모형의 변별력, 보정, 안정성, 등급전이, cut-off, override가 정책 기준과 일관되는가.
- 권장 검증방법 후보: 변별력 검토, calibration 검토, population stability 검토, backtesting 결과 검토, 등급별 default 관찰 검토.
- Gray 조건: 모형문서 부재, 개발/검증 데이터 lineage 불명확, 계산엔진 결과 부재, 승인 cut-off 기준 부재.
- 후속 Agent: Data Readiness & Lineage, Quant Validation Method.

### 3.2 `credit_risk_parameter`: PD/LGD/EAD

- 대표 사례: PD 정기검증, LGD 산출식 변경 검증, EAD/CCF 산출 검증, 위험가중자산 입력요소 점검.
- 필수 입력자료: 파라미터 정의서, 산출 정책, default 정의, 관측기간, 계산엔진 결과, 상품·등급·담보 구분 기준.
- 주요 검증 질문: 위험측정요소가 승인된 정의와 기간 기준에 따라 산출되었는가, 결과가 정책 기준 내에서 해석 가능한가.
- 권장 검증방법 후보: PD calibration/backtesting 결과 검토, LGD workout 및 discounting 검토, EAD CCF 검토, segment 안정성 검토.
- Gray 조건: default 정의 불명확, 회수자료 권한 부족, 표본 부족, 계산엔진 실행 로그 부재, 정책 임계값 미정의.
- 후속 Agent: Data Readiness & Lineage, Quant Validation Method.

### 3.3 `risk_factor_validation`: 위험요소·거시변수

- 대표 사례: 실업률 변수 사용 적합성, 부동산가격지수 시나리오 변수 검증, 금리·환율 위험요소 정의 점검.
- 필수 입력자료: 변수 정의서, 원천 출처, 시계열 이력, 개정 이력, 결측 처리 근거, 정책상 사용 목적.
- 주요 검증 질문: 변수의 경제적 타당성, 정의 안정성, 개정 가능성, 시나리오 적합성, 모형 목적과의 연결성이 충분한가.
- 권장 검증방법 후보: 시계열 안정성 결과 검토, 결측·개정 이력 검토, 상관·민감도 계산엔진 결과 검토, 전문가 판단 증적 검토.
- Gray 조건: 공식 변수 정의 부재, 원천 출처 불명확, 정책 미정의, 개정 이력 미제공, 시나리오 승인 근거 부재.
- 후속 Agent: Data Readiness & Lineage, Regulation Monitoring.

### 3.4 `aggregation_reporting`: 집계·보고

- 대표 사례: 포트폴리오 리스크 집계, 월간 리스크 대시보드, 경영진 보고서, 규제 보고서 숫자 검증.
- 필수 입력자료: 집계 로직, 원천 테이블, 기준일, 필터 조건, 보고서 버전, 계산엔진 또는 BI 실행 결과.
- 주요 검증 질문: 집계 대상과 제외 대상이 정책과 일치하는가, 원천부터 보고서까지 lineage가 재현 가능한가.
- 권장 검증방법 후보: reconciliation 결과 검토, completeness 점검, 중복·누락 점검, 보고서 버전 비교.
- Gray 조건: 원천-보고서 매핑 불명확, 기준일 불일치, 실행 로그 부재, 수동 조정 증적 부족.
- 후속 Agent: Data Readiness & Lineage, Calculation Result Reviewer.

### 3.5 `hybrid_risk_output`: ST/ICAAP/IRRBB 등

- 대표 사례: 스트레스테스트 결과 검증, ICAAP 자본계획 입력 검증, IRRBB 민감도 산출물 검토.
- 필수 입력자료: 시나리오 승인문서, 모델 및 파라미터 참조, 산출 배치 로그, 집계 결과, 정책 기준.
- 주요 검증 질문: 시나리오·모형·파라미터·집계가 승인된 절차에 따라 연결되었는가.
- 권장 검증방법 후보: 입력-산출 reconciliation 검토, 시나리오 적용 여부 검토, 민감도 결과 계산엔진 산출물 검토, 정책 기준 매핑.
- Gray 조건: 시나리오 승인근거 부재, 모델·파라미터 버전 불명확, 계산엔진 결과 미제공, 정책 적용 범위 미정의.
- 후속 Agent: Quant Validation Method, Policy & Judgement.

## 4. 분류불가 처리

분류에 필요한 정보가 부족하거나 대상 업무가 위 5개 분기에 명확히 들어가지 않으면 다음과 같이 처리한다.

- `validation_object_type`: 분류불가
- `provisional_judgement`: Gray
- Action Notice 사유코드: 정보 부족 성격에 따라 `POLICY_UNDEFINED`, `EVIDENCE_INSUFFICIENT`, `LINEAGE_UNCLEAR` 등을 적용
- 후속조치: 요청 범위 명확화, 공식 정책문서 제출, 데이터·계산엔진 결과 제출 요청

## 5. 운영상 가정

- 분류는 워크플로우 배정을 위한 실무 도구이며, 모델 또는 파라미터의 적정성을 의미하지 않는다.
- 복합 산출물은 감사추적을 위해 주분류와 보조분류를 모두 기록한다.

## 6. LLM 하네스 및 후속 판정 연결

- 분류 Agent는 LLM 기반 라우팅 보조 역할이며 수치 계산, 정량 결론, 최종 승인을 수행하지 않는다.
- 분류 이후 판정 후보는 Green / Yellow / Red / Gray만 사용할 수 있다.
- 분류 불가, 정책 미정의, 데이터·증적 부족은 Gray와 Action Notice로 연결하고 인간 검증자 검토를 요청한다.
