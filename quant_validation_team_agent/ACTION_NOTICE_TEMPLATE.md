# ACTION_NOTICE_TEMPLATE

## 1. 목적

Yellow / Red / Gray 판정 후보에 대해 조치 소유자, 기한, 필요 증적, 재검증 조건, 에스컬레이션 기준을 명확히 하기 위한 Action Notice 템플릿이다.

## 2. 생성 조건

- `provisional_judgement = Yellow`이면 Action Notice를 생성한다.
- `provisional_judgement = Red`이면 Action Notice를 생성하고 에스컬레이션 후보를 표시한다.
- `provisional_judgement = Gray`이면 판단불가 사유코드와 필요 증적을 포함해 Action Notice를 생성한다.
- `provisional_judgement = Green`이면 Action Notice를 생성하지 않으며 제한사항은 보고서에 기록한다.

## 3. Gray 사유코드

| 코드 | 의미 | 예시 |
|---|---|---|
| `POLICY_UNDEFINED` | 정책 미정의 | 신규 변수 검증 기준 부재 |
| `DATA_INSUFFICIENT` | 데이터 부족 | 일부 기간 데이터 누락 |
| `SAMPLE_INSUFFICIENT` | 표본 부족 | default 건수 부족 |
| `ACCESS_LIMITED` | 권한 부족 | 회수자료 접근 불가 |
| `LINEAGE_UNCLEAR` | lineage 불명확 | 원천-입력 매핑 불명확 |
| `EVIDENCE_INSUFFICIENT` | 증적 부족 | 실행 로그/버전 부재 |

## 4. Action Notice 템플릿

```markdown
# Action Notice

## 1. 기본 정보
- Notice ID:
- case_id:
- request_id:
- 발행일:
- 발행 Agent:
- 검증대상:
- validation_object_type:
- 판정 후보: Yellow | Red | Gray
- Gray 사유코드:

## 2. 발생 사유
- 발견사항:
- 정책 기준:
- 계산엔진 결과 참조:
- 데이터/lineage/증적 공백:
- LLM 직접 계산 미수행 확인:

## 3. 영향 범위
- 영향 업무:
- 영향 모델/파라미터/보고서:
- 공식 보고 영향 가능성:
- 고객/자본/리스크관리 영향 후보:

## 4. 필요한 조치
- 조치 내용:
- 조치 소유자:
- 담당 부서:
- 목표 완료일:
- 우선순위:
- 필요한 증적:

## 5. 재검증 조건
- 재검증 트리거:
- 제출 필요 산출물:
- 계산엔진 재실행 필요 여부:
- 정책 승인 필요 여부:

## 6. 미조치 시 에스컬레이션 기준
- 에스컬레이션 조건:
- 에스컬레이션 대상:
- 임시 사용 제한 필요 여부:
- 공식 보고 보류 필요 여부:

## 7. 종결 기준
- 종결 확인자:
- 공식 종결 승인자:
- 종결일:
- 잔여 리스크:
```

## 5. 판정 예시와 Gray 사례 라이브러리

| 사례명 | 입력상황 | 판정 후보 | Notice 사유코드 | 필요한 조치 | 재검증 조건 |
|---|---|---|---|---|---|
| 정책 미정의 | 신규 거시변수 검증 기준 부재 | Gray | POLICY_UNDEFINED | 정책 담당부서 기준 수립 | 승인 정책문서 제출 |
| 데이터 부족 | PD 검증 기간 일부 월 누락 | Gray | DATA_INSUFFICIENT | 누락 구간 재추출 | 완전한 기간 데이터 제출 |
| 표본 부족 | 특정 등급 default 부족 | Gray | SAMPLE_INSUFFICIENT | 기간 확장 또는 pooling 검토 | 승인된 pooling 기준 제출 |
| 권한 부족 | 담보 회수자료 접근 불가 | Gray | ACCESS_LIMITED | 권한 승인 또는 대체 증적 | 회수자료 확인 가능 상태 |
| lineage 불명확 | 원천-계산엔진 입력 매핑 불명확 | Gray | LINEAGE_UNCLEAR | ETL 경로와 추출쿼리 제출 | lineage 재현성 확인 |
| 증적 부족 | 실행 로그/파라미터 부재 | Gray | EVIDENCE_INSUFFICIENT | 재현 가능한 실행 패키지 제출 | 실행 ID와 로그 확인 |
| 제한적 보완 | 결측 처리 설명 부족 | Yellow | 해당 없음 | 결측 처리 근거 제출 | 보완자료 검토 완료 |
| 중대 결함 | 미승인 버전 산출물 사용 | Red | 해당 없음 | 승인 버전으로 재산출 | 공식 보고 영향 검토 |

## 6. 운영상 가정

- Action Notice는 조치 이행 관리 문서이며 보고서 초안을 대체하지 않는다.
- Notice 종결은 에이전트가 아니라 지정된 인간 검증자 또는 공식 조직이 수행한다.
