# Validation Scope

본 하니스가 자동화/반자동화로 지원하는 검증 범위와 그 한계.

---

## 1. 모형군별 지원 범위

| 모형군 | 지원 항목 | 비지원 (인간 전담) |
|---|---|---|
| 신용평가모형 | KS, AUROC, Gini, PSI, 등급분포, 안정성, 챌린저 비교 코드 | 모형 승인 / 부적합 의견 |
| PD | 캘리브레이션, CDR/SDR, 등급별 표본 점검 | 등급 재정의 |
| LGD | 회수율 분포, 부도시점 LGD 표본 적정성 | 회수실적 정성 판단 |
| EAD | CCF 추정, 한도 사용률 분포, 표본 적정성 | 한도 정책 판단 |
| IFRS 9 ECL | 스테이지 분류 일관성, 시나리오 가중치 합 = 1, FLI 변수 정합성 | 스테이지 정책 변경 |
| 거시 시나리오 | 정상성, VIF, 잔차 진단 | 거시 변수 선택 정책 |
| 스트레스 테스트 | 시나리오 서열, PD 배수 floor, 이탈 케이스 | 시나리오 자체 적정성 |
| 모니터링 | PSI 추이, 부도율 추이, 트리거 발동 | 트리거 임계 변경 |

---

## 2. 검증 관점

| 관점 | 지원 도구 |
|---|---|
| 데이터 | `tools/data_profile.py`, `middleware/data_safety_guard.py` |
| 정량 | `tools/metric_ks_auc.py`, `tools/metric_psi.py`, `tools/metric_cdr_sdr.py` |
| 방법론 | `tools/regression_diagnostics.py`, `tools/scenario_order_check.py` |
| 운영/내부통제 | `middleware/permission_guard.py`, `middleware/sample_size_guard.py`, `middleware/leakage_guard.py` |
| 문서화 | `middleware/output_completeness_guard.py`, `tools/report_template.py` |
| 감사추적 | `middleware/run_logger.py`, `harness/change_manifest.json` |

---

## 3. 명시적 한계

- 본 하니스의 산출물은 **검증 보조 자료**이며, 최종 의견과 책임은 인간 검증자에게 있다.
- 본 하니스는 운영계 데이터에 직접 접근하지 않는다. 모든 데이터는 사전에
  비식별화된 샘플 또는 검증용 추출 데이터를 전제로 한다.
- 모형의 정성적 적정성, 사업 전략 정합성, 리스크 관리 정책 정합성은
  자동화 대상이 아니다.
