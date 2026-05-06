# 검증 요청 예시

본 양식은 사용자가 검증 요청을 작성할 때 권장하는 표준 양식이다.

---

## 1. 모형명
- 예: 개인고객 신용평가모형 v3.2

## 2. 모형 유형
- (택1) 스코어링 / PD / LGD / EAD / PD multiplier / 시나리오 회귀 / 모니터링 / 챌린저 비교

## 3. 검증 목적
- 예: 2025년 운영 검증, 개발 표본 대비 운영 표본 안정성 점검

## 4. 검증 구분
- (택1) 개발 검증 / 운영 검증 / 정기 모니터링 / 모형 변경 검증 / 챌린저 비교

## 5. 데이터 파일
- 경로: `examples/sample_credit_score_data.csv`
- 익명화/검증용 추출 여부: 익명화 완료
- 보안 등급: 내부 검증용 한정

## 6. 컬럼 매핑
- target: `target` (1=불량/부도)
- score: `score` (방향성: 높을수록 양호)
- 개발/운영 구분: `dataset` (`dev`/`prod`)
- 등급: `grade`
- 기준일: `obs_date`
- segment: `segment`

## 7. 요청 지표
- KS, AUROC, AR, PSI(개발 vs 운영), 등급별 bad rate, rank ordering

## 8. 특이사항
- 신규 모형, 운영 표본은 3개월 누적
- segment는 retail만 포함
- LDP 여부: 아니오

## 9. 임계값 정책
- `harness/threshold_policy.md`의 참고 기준을 사용하되, 운영 정책 미확보 항목은 Gray로 처리.

## 10. 성공 기준
- 표준 검증 리포트 9개 섹션 충족
- 모든 적용 지표에 RAG 등급 부여
- 한계 및 추가 확인사항 명시
