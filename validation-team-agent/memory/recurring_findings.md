# Recurring Findings

검증 과정에서 반복적으로 발견되는 패턴을 누적한다. 향후 유사 검증에서 사전
점검 항목으로 활용한다. 신규 항목은 사용자/검증자가 추가한다.

| ID | 발생 빈도 | 영역 | 설명 | 우선 점검 도구/스킬 |
|---|---|---|---|---|
| RF-001 | 빈번 | 데이터 | 운영 표본의 우측 꼬리 분포 변화 → PSI 상승 | `tools/metric_psi.py` |
| RF-002 | 빈번 | 캘리브레이션 | 등급 1~3 부도 건수 < 30 → 신뢰구간 넓음 | `middleware/sample_size_guard.py` |
| RF-003 | 보통 | 방법론 | 거시 변수 시차 변수 사용 사유 미문서화 | `skills/macro_scenario_validation.md` |
| RF-004 | 보통 | 문서화 | 한계 / 추가 확인사항 누락 | `middleware/output_completeness_guard.py` |
| RF-005 | 빈번 | 시나리오 | severe 시나리오 PD multiplier가 floor 미달 | `tools/scenario_order_check.py` |
| RF-006 | 보통 | 누수 | future_*, *_after 변수가 features에 잔존 | `middleware/leakage_guard.py` |
| RF-007 | 드묾 | 데이터 | 일자 컬럼에 한 달 이상 누락 구간 존재 | `tools/data_profile.check_date_coverage` |
