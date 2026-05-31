"""10만건 합성 데이터로 dynamic workflow 를 실행하고 보고서를 생성하는 데모 CLI.

사용:
    python -m tools.run_workflow_demo --n 100000 --out reports/workflow_100k.md
    python -m tools.run_workflow_demo --n 100000 --stress  # 자본 미달 escalation 시연

본 스크립트는 합성 데이터만 사용한다. 운영 데이터 / 외부 API 호출 없음.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.handlers import register_default_handlers
from tools.report_template import build_validation_report, render_html
from tools.sample_generators import (
    capital_ratio_sample,
    capital_stress_sample,
    ccr_exposure_sample,
    credit_scoring_sample,
    cva_counterparty_sample,
    ifrs9_weight_panel,
    macro_random_walk_series,
    macro_stationary_series,
    operational_bi_sample,
)
from tools.workflow import WorkflowEngine


def build_request(n: int, *, stress: bool, seed: int) -> dict:
    df = credit_scoring_sample(n=n, seed=seed, psi_shift=0.4 if stress else 0.0)
    base = {
        "title": f"Dynamic Workflow Demo (n={n:,})",
        "df": df,
        "score_col": "score",
        "target_col": "target",
        "set_col": "set",
        "grade_col": "grade",
        "pd_col": "pd",
    }
    # 부문별 공통 입력 (Round 18: macro/weights/operational/cva/ccr 추가)
    base.update(
        {
            "scenario_weight_panel": ifrs9_weight_panel(balanced=not stress),
            "op_business_indicator_eur_bn": operational_bi_sample(large=stress),
            "cva_counterparty_inputs": cva_counterparty_sample(),
            "cva_trading_book_size_eur_bn": 150.0 if stress else 30.0,
            **ccr_exposure_sample(),
        }
    )
    if stress:
        base.update(capital_stress_sample())
        base.update(
            {
                "market_var_exceptions": 12,  # red zone
                "liquidity_hqla": 80.0,
                "liquidity_outflow": 100.0,  # LCR 0.8 → below_min
                "irrbb_delta_eve_by_scenario": {
                    "parallel_up": -3_000_000,
                    "parallel_down": 100_000,
                    "steepener": -500_000,
                    "flattener": -1_000_000,
                    "short_rate_up": -500_000,
                    "short_rate_down": 200_000,
                },
                "irrbb_tier1": 10_000_000,
                "macro_series": macro_random_walk_series(n=250),
            }
        )
    else:
        base.update(capital_ratio_sample())
        base.update(
            {
                "market_var_exceptions": 3,
                "liquidity_hqla": 130.0,
                "liquidity_outflow": 100.0,
                "irrbb_delta_eve_by_scenario": {
                    "parallel_up": -500_000,
                    "parallel_down": 100_000,
                    "steepener": -200_000,
                    "flattener": -300_000,
                    "short_rate_up": -150_000,
                    "short_rate_down": 100_000,
                },
                "irrbb_tier1": 10_000_000,
                "macro_series": macro_stationary_series(n=250),
            }
        )
    return base


def run_demo(n: int, stress: bool, seed: int, log_dir: Path) -> dict:
    t0 = time.perf_counter()
    request = build_request(n, stress=stress, seed=seed)
    eng = WorkflowEngine()
    registered = register_default_handlers(eng)
    run = eng.run(request, log_dir=log_dir)
    elapsed = time.perf_counter() - t0
    return {
        "n_rows": len(request["df"]),
        "stress_mode": stress,
        "registered_handlers": registered,
        "plan": run.plan,
        "executed_order": run.executed_order,
        "results": {
            sid: {
                "status": r.status,
                "outputs": _coerce(r.outputs),
                "detail": r.detail,
            }
            for sid, r in run.context.results.items()
        },
        "summary": run.summary(),
        "elapsed_sec": round(elapsed, 3),
        "workflow_markdown": run.render_markdown(),
    }


def _coerce(obj):
    """numpy/pandas 객체를 JSON-friendly 로 변환."""
    import numpy as np
    import pandas as pd

    if isinstance(obj, dict):
        return {str(k): _coerce(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_coerce(x) for x in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    if isinstance(obj, pd.DataFrame):
        return f"<DataFrame {obj.shape}>"
    return obj


def build_report_markdown(demo: dict, *, stress: bool) -> str:
    results = demo["results"]
    summary = demo["summary"]
    cred_disc = results.get("3.disc", {})
    cred_psi = results.get("3.psi", {})
    cred_cal = results.get("3.cal", {})
    sample = results.get("2.sample", {})
    capital = results.get("3.capital", {})
    market = results.get("3.market", {})
    liquidity = results.get("3.liquidity", {})
    irrbb = results.get("3.irrbb", {})
    escal = results.get("9.escalate", {})

    title_suffix = " (stress / escalation 시연)" if stress else " (정상 case)"

    results_md_lines = []
    if cred_disc:
        o = cred_disc.get("outputs", {})
        results_md_lines.append(
            f"- 신용 변별력 (출처: `tools/metric_ks_auc.calculate_ks`): "
            f"KS = {o.get('ks', 0):.4f}, AUROC = {o.get('auc', 0):.4f}, "
            f"Gini = {o.get('gini', 0):.4f}, n = {o.get('n', 0)}"
        )
    if cred_psi:
        o = cred_psi.get("outputs", {})
        results_md_lines.append(
            f"- 안정성 PSI (출처: `tools/metric_psi.calculate_psi`): "
            f"dev↔oot = {o.get('psi', 0):.4f} ({cred_psi.get('status')})"
        )
    if cred_cal:
        o = cred_cal.get("outputs", {})
        results_md_lines.append(
            f"- 등급별 캘리브레이션 (출처: `tools/binomial_calibration.calibration_test_per_grade`): "
            f"reject {o.get('n_reject', 0)}/{o.get('n_grades', 0)}"
        )
    if sample:
        o = sample.get("outputs", {})
        results_md_lines.append(
            f"- 표본 적정성 (출처: `middleware/sample_size_guard.check_sample_size`): "
            f"passed={o.get('passed')}, violations={o.get('violations', 0)}"
        )
    if capital and capital.get("status") != "skipped":
        results_md_lines.append(
            f"- 자본적정성 (출처: `tools/risk_checks/capital.check_ratios`): "
            f"{capital.get('detail', '')}"
        )
    if market and market.get("status") != "skipped":
        o = market.get("outputs", {})
        results_md_lines.append(
            f"- 시장리스크 (출처: `tools/risk_checks/market.var_backtest_traffic_light`): "
            f"zone={o.get('zone')}, exceptions={o.get('exceptions')}"
        )
    if liquidity and liquidity.get("status") != "skipped":
        results_md_lines.append(
            f"- 유동성 (출처: `tools/risk_checks/liquidity`): {liquidity.get('detail', '')}"
        )
    if irrbb and irrbb.get("status") != "skipped":
        o = irrbb.get("outputs", {})
        results_md_lines.append(
            f"- IRRBB (출처: `tools/risk_checks/irrbb.check_eve_outlier`): "
            f"outlier={o.get('outlier')}, ratio={o.get('ratio', 0):.4f}, worst={o.get('worst')}"
        )

    anomalies = []
    for sid, r in results.items():
        if r["status"] in {"warning", "fail"}:
            anomalies.append(
                f"- `{sid}` ({r['status']}, 출처: `tools/handlers.py`): {r['detail']}"
            )
    if escal:
        o = escal.get("outputs", {})
        anomalies.append(
            f"- escalation 동적 활성 (출처: `tools/workflow.WorkflowEngine.run`): "
            f"trigger={o.get('triggered_by')}"
        )
    if not anomalies:
        anomalies.append("- 자동 점검 한정 이상 징후 없음.")

    result_dict = {
        "title": f"Dynamic Workflow End-to-End Demo {title_suffix}",
        "summary": (
            f"합성 데이터 {demo['n_rows']:,}건. 정적 plan {summary['n_planned']} step, "
            f"실제 실행 {summary['n_executed']} step, escalation={summary['escalated']}. "
            f"실행 시간 {demo['elapsed_sec']}초."
        ),
        "purpose": "Round 17 강화 검증: dynamic workflow 엔진의 end-to-end 동작 + escalation 분기 시연.",
        "input_data": [
            f"입력 행 수: {demo['n_rows']:,} (합성 데이터, seed=42)",
            f"컬럼: customer_id, obs_date, score, target, grade, pd, set",
            f"부문별 입력: capital_*, market_var_exceptions, liquidity_*, irrbb_*",
            f"운영 데이터 / 외부 API 호출 없음. 민감정보 패턴 없음.",
        ],
        "method": [
            "샘플 생성: `tools/sample_generators.credit_scoring_sample`",
            "Workflow: `tools/workflow.WorkflowEngine` (handler registry + 위상정렬 + 동적 escalation)",
            "Handler 등록: `tools/handlers.register_default_handlers` (9개 step)",
            "보고서: `tools/report_template.build_validation_report`",
        ],
        "results": "\n".join(results_md_lines)
        if results_md_lines
        else "(산출 가능한 결과 없음)",
        "anomalies": "\n".join(anomalies),
        "limitations": [
            "본 산출물은 합성 데이터 기반 데모이며 실제 운영 결과 아님.",
            "신용 임계(KS≥0.30, AUROC≥0.70, PSI<0.10/0.25)는 참고 임계.",
            "자본 / 유동성 / IRRBB 입력은 (unverified) 가정값.",
            "신뢰구간 / 통계적 검정의 다중 보정 한계.",
        ],
        "draft_opinion": (
            "본 자동 산출물은 합성 데이터에 대한 점검 결과만 포함. 실제 검증 의견은 "
            "운영 데이터 + 인간 검증자 + MRMC 검토 후에만 효력을 가짐."
        ),
        "follow_ups": [
            "운영 데이터로 동일 워크플로우 재실행 시 매트릭스 게이트 충족 여부 확인",
            "escalation 발생 시 매니페스트 CHG 항목 자동 추가 검토",
            "신용 모형 챌린저 비교 (`skills/challenger_model_review.md`)",
        ],
        "audit_trail": (
            f"실행 로그: `logs/run.jsonl`. 워크플로우 정적 plan: "
            f"{' → '.join(demo['plan'])}. 실제 실행 순서: "
            f"{' → '.join(demo['executed_order'])}. 등록 handler: "
            f"{', '.join(demo['registered_handlers'])}."
        ),
    }
    md = build_validation_report(result_dict)
    md += "\n\n---\n\n## Appendix — Workflow Trace\n\n" + demo["workflow_markdown"]
    return md


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="dynamic workflow demo with synthetic data")
    parser.add_argument("--n", type=int, default=100_000, help="row count (>=100)")
    parser.add_argument("--stress", action="store_true",
                        help="자본/시장/유동성/IRRBB 미달 case (escalation 시연)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=None,
                        help="markdown 보고서 출력 경로")
    parser.add_argument("--html-out", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None,
                        help="raw demo dict 를 JSON 으로 저장")
    parser.add_argument("--log-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    log_dir = args.log_dir or (Path(__file__).resolve().parent.parent / "logs")
    demo = run_demo(args.n, args.stress, args.seed, log_dir)

    md = build_report_markdown(demo, stress=args.stress)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md, encoding="utf-8")
    else:
        sys.stdout.write(md + "\n")

    if args.html_out:
        args.html_out.parent.mkdir(parents=True, exist_ok=True)
        args.html_out.write_text(
            render_html(md, title="Dynamic Workflow Demo"), encoding="utf-8"
        )

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        # workflow_markdown 은 별도 보관용. results 도 그대로.
        args.json_out.write_text(
            json.dumps(demo, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
