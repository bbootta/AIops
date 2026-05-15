# regulatory_framework_mapping.md

본 문서는 quant-validation-agent의 정량 검증 기능을 **공개적으로 알려진 감독 프레임워크 영역**에 매핑한 *작업 보조 문서*다.

> **중요 경고**
> - 본 문서는 **법률·규제 유권해석을 제공하지 않는다.** (`CLAUDE.md` §2 참조)
> - 인용된 영역명은 일반적으로 공개된 프레임워크의 **개념 영역**만 가리키며, 특정 조항·문구·번호는 포함하지 않는다.
> - 실제 규제 적용·해석은 반드시 컴플라이언스/감독당국 담당자의 확인을 거친다.
> - 본 문서의 매핑은 검증 *능력 분류*를 위한 것이며, **준수 증빙**이 아니다.

---

## 1. 기본 원칙

| 항목 | 입장 |
|---|---|
| 본 도구가 규제 준수를 *증명*하는가? | **아니오.** 정량 결과를 산출할 뿐 적합성 판단은 인간 검증자 몫. |
| 특정 조항 인용 | **하지 않는다.** 영역(`area`)명만 기록. |
| 임계값 | 정책 문서가 확정하기 전까지 RAG는 `Gray`. |
| 변경 절차 | 정책·매핑 수정은 `change_manifest.json`에 `human_approval_required: true`로 기록. |

---

## 2. 매핑 표

각 행은 quant-validation-agent의 도구·CLI·산출물이 **어느 프레임워크 영역**과 관련되는지를 표시한다.
각 영역 코드는 본 저장소 내부에서만 의미를 가지는 *태그*다.

| Area Code | 프레임워크 영역 (개념) | 관련 도구 / 산출물 |
|---|---|---|
| `basel_irb_pd` | Basel IRB — PD 추정 및 검증 (calibration, discrimination, backtesting) | `tools/metric_calibration.py`, `tools/metric_ks_auc_ar.py`, `tools/calibration_test.py`, `tools/backtest_traffic_light.py` |
| `basel_irb_lgd` | Basel IRB — LGD 추정 (downturn LGD 포함) | `tools/metric_lgd_ead.py`, `tools/downturn_lgd.py` |
| `basel_irb_ead` | Basel IRB — EAD/CCF 추정 | `tools/metric_lgd_ead.py` (EAD 분기), CLI `validate --model-type ead` |
| `basel_stress` | Basel — Stress testing / 시나리오 정합성 | `tools/scenario_regression_pipeline.py`, `tools/scenario_order_check.py` |
| `basel_moc` | Basel IRB — Margin of Conservatism | `tools/margin_of_conservatism.py` |
| `ifrs9_pd` | IFRS 9 — ECL의 PD 구성요소 (forward-looking) | `tools/metric_calibration.py`, `tools/scenario_regression_pipeline.py` |
| `mrm_basel` | Basel — 모형 리스크 관리(MRM) 일반 (변경관리·문서화·재현성) | `harness/`, `middleware/run_logger.py`, `harness/change_manifest.json` |
| `fss_bank_validation` | 한국 금감원 — 은행 모형 검증 관련 모범규준 영역 (개념적 매핑) | `harness/validation_workflow.md`, `docs/validation_output_spec.md`, `examples/sample_validation_full_request.md` |
| `fss_credit_scoring` | 한국 금감원 — 신용평가모형 운영·검증 관련 영역 (개념적 매핑) | `skills/credit_score_validation.md`, CLI `validate --model-type scoring` |
| `governance` | 일반 모형 거버넌스 (정책 lock, manifest 거버넌스) | `middleware/policy_change_guard.py`, CLI `policy-governance`, `policy-lock` |

---

## 3. 도구별 매핑 (역방향)

| 도구 / CLI | 적용 가능 area |
|---|---|
| `tools/metric_ks_auc_ar.py` | `basel_irb_pd`, `fss_credit_scoring` |
| `tools/metric_psi.py` | `basel_irb_pd`, `mrm_basel`, `fss_bank_validation` |
| `tools/metric_calibration.py` | `basel_irb_pd`, `ifrs9_pd` |
| `tools/calibration_test.py` | `basel_irb_pd`, `ifrs9_pd` |
| `tools/backtest_traffic_light.py` | `basel_irb_pd`, `mrm_basel` |
| `tools/metric_lgd_ead.py` | `basel_irb_lgd`, `basel_irb_ead` |
| `tools/downturn_lgd.py` | `basel_irb_lgd` |
| `tools/margin_of_conservatism.py` | `basel_moc` |
| `tools/scenario_regression_pipeline.py` | `basel_stress`, `ifrs9_pd` |
| `tools/scenario_order_check.py` | `basel_stress` |
| `tools/regression_diagnostics.py` | `basel_stress`, `mrm_basel` |
| `middleware/policy_change_guard.py` | `governance`, `mrm_basel` |
| `middleware/run_logger.py` | `mrm_basel`, `fss_bank_validation` |
| `tools/diff_reports.py` | `mrm_basel` (모형 성능 추이 추적) |

---

## 4. 정책 메타데이터

`harness/threshold_policy.json`의 각 metric block은 선택적으로
다음을 가질 수 있다.

```json
{
  "ks": {
    "model_types": ["scoring", "pd"],
    "direction": "higher_is_better",
    "green_threshold": 0.40,
    "yellow_threshold": 0.30,
    "regulatory_basis": ["basel_irb_pd", "fss_credit_scoring"]
  }
}
```

- `regulatory_basis`는 **태그 배열**이며, 본 저장소 내부 area 코드만 사용한다.
- 값을 추가/수정/삭제하면 `change_manifest.json`에 `human_approval_required: true`로 기록한다.

---

## 5. 한계

- 본 매핑은 **개념적 분류**다. 동일한 도구가 여러 프레임워크의 다른 측면을 동시에 만족시키거나 부족할 수 있다.
- 본 도구의 결과는 *준수 증빙*이 아니라 *정량 분석 산출물*이다.
- 운영 적용 시 컴플라이언스 / 모형리스크 관리부서의 추가 검토가 필수다.
