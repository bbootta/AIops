# Skill — Credit Scoring Model Validation

## 목적
신용평가모형의 변별력·안정성·등급분포·캘리브레이션을 점검한다.

## 입력
- `customer_id`, `obs_date`, `score`, `target`
- 등급체계 (등급 경계, 등급명)
- 개발 기간 / 운영 기간 구분

## 절차
1. 데이터 품질 점검 (`skills/data_quality_review.md`)
2. 변별력
   - `tools/metric_ks_auc.calculate_ks(target, score)`
   - `tools/metric_ks_auc.calculate_auc_gini(target, score)`
3. 안정성
   - 개발 vs 운영 분포에 대해 `tools/metric_psi.calculate_psi`
   - 등급 단위 비교에는 `calculate_psi_by_bucket`
4. 등급분포
   - 등급별 표본 수 / 부도 수 / 부도율의 단조성
5. 캘리브레이션
   - 등급별 추정 PD 대비 CDR
6. 챌린저 모형 비교 필요성 검토 (`skills/challenger_model_review.md`)

## 산출물
- KS / AUROC / Gini 표
- PSI 표 (전체, 등급별)
- 등급분포 표
- 캘리브레이션 표
- 검증 의견 초안

## 참고 임계 (참고용, 임의 완화 금지)
- KS ≥ 0.30
- AUROC ≥ 0.70
- PSI < 0.10 안정 / 0.10~0.25 주의 / ≥ 0.25 불안정

## 금지
- 임계값 임의 완화
- 표본 부족 시 강한 결론
- 등급 재정의 제안의 자동 확정

## 완료 기준
- 모든 지표가 표본 수와 함께 보고되었는가
- 한계와 추가 확인사항이 명시되었는가
