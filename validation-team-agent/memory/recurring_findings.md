# Recurring Findings

검증 과정에서 반복적으로 발견되는 패턴. 본 문서는 `memory/recurring_findings.json`에서
자동 생성된다. 직접 편집하지 말고 `python -m tools.findings sync` 또는 `add` 명령을
사용하라.

| ID | 발생 빈도 | 영역 | 설명 | 우선 점검 도구/스킬 |
|---|---|---|---|---|
| RF-001 | 빈번 | data | 운영 표본의 우측 꼬리 분포 변화 → PSI 상승. | `tools/metric_psi.py` |
| RF-002 | 빈번 | calibration | 등급 1~3 부도 건수 < 30 → 신뢰구간 넓음. | `middleware/sample_size_guard.py` |
| RF-003 | 보통 | methodology | 거시 변수 시차 변수 사용 사유 미문서화. | `skills/macro_scenario_validation.md` |
| RF-004 | 보통 | documentation | 한계 / 추가 확인사항 누락. | `middleware/output_completeness_guard.py` |
| RF-005 | 빈번 | scenario | severe 시나리오 PD multiplier가 floor 미달. | `tools/scenario_order_check.py` |
| RF-006 | 보통 | leakage | future_*, *_after 변수가 features에 잔존. | `middleware/leakage_guard.py` |
| RF-007 | 드묾 | data | 일자 컬럼에 한 달 이상 누락 구간 존재. | `tools/data_profile.check_date_coverage` |
| RF-008 | 보통 | documentation | 신규 CLI/정책 파일 추가 시 카탈로그(cli_index, vta dispatch, README 표) 동기화 누락 — R34 에서 CLI 22개 중 8개 미등재 발견. sync gate 테스트(test_v2_round34)로 재발 차단. | `tools/cli_index.py + tests/test_v2_round34.py` |
