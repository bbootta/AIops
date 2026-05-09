"""IFRS 9 ECL 통합 검증 thin runner.

신용평가용 ``run_validation.py`` / 거시용 ``run_macro_validation.py`` 와 분리되어
IFRS 9 ECL 산출 과정을 점검한다.

- 시나리오 가중치 합 = 1, 음수, 알 수 없는 시나리오 (`tools/scenario_weights`)
- PD/손실 시나리오 서열 base ≤ adverse ≤ severe (`tools/scenario_order_check`)
- PD multiplier floor (`tools/scenario_order_check.check_pd_multiplier_floor`)
- 등급별 PD 캘리브레이션 (`tools/binomial_calibration` — 등급+PD 입력 시)
- 실행 로깅 / 보고서 완결성 / 인용 / 워터마크

CLI:
    python -m tools.run_ifrs9_validation --demo
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from middleware.draft_watermark_guard import check_watermarks
from middleware.output_completeness_guard import check_numeric_citations, check_report
from middleware.run_logger import log_step, run_logger
from tools.binomial_calibration import calibration_test_per_grade
from tools.report_template import build_validation_report
from tools.scenario_order_check import check_pd_multiplier_floor, check_scenario_order
from tools.scenario_weights import check_weight_panel


@dataclass
class IFRS9ValidationRequest:
    title: str
    weight_panel: pd.DataFrame
    weight_period_col: str = "period"
    weight_scenario_col: str = "scenario"
    weight_value_col: str = "weight"
    pd_by_scenario: dict[str, np.ndarray] | None = None
    pd_multipliers: dict[str, Iterable[float]] | None = None
    grade_calibration: list[dict] | None = None
    extra_notes: list[str] = field(default_factory=list)


def _step_weights(req: IFRS9ValidationRequest) -> pd.DataFrame:
    return check_weight_panel(
        req.weight_panel,
        period_col=req.weight_period_col,
        scenario_col=req.weight_scenario_col,
        weight_col=req.weight_value_col,
    )


def _step_scenario_order(req: IFRS9ValidationRequest) -> dict | None:
    if not req.pd_by_scenario:
        return None
    needed = ("base", "adverse", "severe")
    for k in needed:
        if k not in req.pd_by_scenario:
            return {"error": f"missing scenario {k!r}", "passed": False}
    return check_scenario_order(*[req.pd_by_scenario[k] for k in needed])


def _step_floors(req: IFRS9ValidationRequest) -> dict[str, dict] | None:
    if not req.pd_multipliers:
        return None
    out: dict[str, dict] = {}
    for scenario, values in req.pd_multipliers.items():
        out[scenario] = check_pd_multiplier_floor(list(values), scenario)
    return out


def _step_calibration(req: IFRS9ValidationRequest) -> pd.DataFrame | None:
    if not req.grade_calibration:
        return None
    return calibration_test_per_grade(req.grade_calibration, alpha=0.05, multitest="holm")


def _format_results(diag: dict) -> str:
    lines: list[str] = []

    panel = diag["weights"]
    n_periods = len(panel)
    n_fail = int((~panel["passed"]).sum())
    lines.append(
        f"- 시나리오 가중치 정합성 (출처: `tools/scenario_weights.check_weight_panel`): "
        f"period {n_periods}개 / 위반 {n_fail}건"
    )

    order = diag.get("scenario_order")
    if order is not None and "error" not in order:
        lines.append(
            f"- PD 시나리오 서열 (출처: `tools/scenario_order_check.check_scenario_order`): "
            f"passed = {order['passed']}, n = {order['n']}, violations = {len(order['violations'])}"
        )
    elif order is not None:
        lines.append(
            f"- PD 시나리오 서열 (출처: `tools/scenario_order_check.check_scenario_order`): "
            f"오류 = {order['error']}"
        )

    floors = diag.get("floors")
    if floors:
        for scenario, info in floors.items():
            lines.append(
                f"- PD multiplier floor `{scenario}` "
                f"(출처: `tools/scenario_order_check.check_pd_multiplier_floor`): "
                f"floor = {info['floor']}, n_violation = {info['n_violation']}/{info['n']}"
            )

    cal = diag.get("calibration")
    if cal is not None:
        n_reject = int(cal["reject"].sum())
        lines.append(
            f"- 등급별 캘리브레이션 (출처: `tools/binomial_calibration.calibration_test_per_grade`): "
            f"reject = {n_reject}/{len(cal)}"
        )

    return "\n".join(lines)


def _build_report(req: IFRS9ValidationRequest, diag: dict) -> str:
    panel = diag["weights"]
    n_fail = int((~panel["passed"]).sum())
    summary = (
        f"시나리오 가중치 위반 period 수 = {n_fail}/{len(panel)}. "
        f"PD 서열 점검 = {'수행' if diag.get('scenario_order') else '미수행'}, "
        f"floor 점검 = {'수행' if diag.get('floors') else '미수행'}, "
        f"캘리브레이션 = {'수행' if diag.get('calibration') is not None else '미수행'}."
    )

    anomalies: list[str] = []
    if n_fail > 0:
        offending = panel.loc[~panel["passed"], "period"].astype(str).tolist()
        anomalies.append(
            f"- 가중치 위반 period (출처: `tools/scenario_weights.check_weight_panel`): "
            f"{', '.join(offending[:5])}{'...' if len(offending) > 5 else ''}"
        )
    order = diag.get("scenario_order")
    if order and isinstance(order, dict) and order.get("passed") is False:
        anomalies.append(
            "- 시나리오 서열 위반 (출처: `tools/scenario_order_check.check_scenario_order`)"
        )
    floors = diag.get("floors") or {}
    for scenario, info in floors.items():
        if info["n_violation"] > 0:
            anomalies.append(
                f"- floor 미달 `{scenario}` (출처: `tools/scenario_order_check.check_pd_multiplier_floor`): "
                f"{info['n_violation']}건"
            )
    if not anomalies:
        anomalies.append("- 검출된 이상 징후 없음 (자동 점검 한정).")

    result_dict = {
        "title": req.title,
        "summary": summary,
        "purpose": "IFRS 9 ECL 산출 과정의 정합성 자동 점검 (시나리오 가중치 / 서열 / floor / 캘리브레이션).",
        "input_data": [
            f"가중치 패널 행 수: {len(req.weight_panel)}",
            f"시나리오별 PD 입력: {'예' if req.pd_by_scenario else '아니오'}",
            f"PD multiplier floor 입력: {'예' if req.pd_multipliers else '아니오'}",
            f"등급 캘리브레이션 입력: {'예' if req.grade_calibration else '아니오'}",
        ],
        "method": [
            "가중치: `tools/scenario_weights.check_weight_panel`",
            "서열: `tools/scenario_order_check.check_scenario_order`",
            "floor: `tools/scenario_order_check.check_pd_multiplier_floor`",
            "캘리브레이션: `tools/binomial_calibration.calibration_test_per_grade`",
        ],
        "results": _format_results(diag),
        "anomalies": "\n".join(anomalies),
        "limitations": [
            "본 산출물은 자동 점검 한정. 스테이지 분류 정합성, FLI 변수 적정성은 미포함.",
            "시나리오 가중치의 정성적 적정성 (예: 거시 변동의 합리성) 은 별도 검토 필요.",
            *req.extra_notes,
        ],
        "draft_opinion": (
            "본 자동 산출물은 IFRS 9 ECL의 일부 정합성 점검만 포함. 스테이지 정책·FLI 변수·"
            "회계 기준 해석은 인간 검증자 책임이며, 최종 의견은 검토와 승인 후에만 효력을 가짐."
        ),
        "follow_ups": [
            "스테이지 분류 일관성 점검 (별도)",
            "FLI 변수 검정 (`tools/regression_diagnostics`)",
            "ECL 합계 정합성 (스테이지별 합산 vs 총계) 별도 산출",
        ],
        "audit_trail": (
            "실행 로그: `logs/run.jsonl`. 변경 이력: `harness/change_manifest.json`."
        ),
    }
    return build_validation_report(result_dict)


def run(req: IFRS9ValidationRequest, log_dir: str | Path | None = None) -> dict:
    """IFRS 9 ECL 정합성 점검을 실행하고 보고서를 반환한다."""
    with run_logger(
        "run_ifrs9_validation.run",
        inputs={"title": req.title, "n_weight_rows": int(len(req.weight_panel))},
        log_dir=log_dir,
    ) as ctx:
        log_step("1.req", component="subagents/orchestrator.md", log_dir=log_dir)
        diagnostics = {
            "weights": _step_weights(req),
            "scenario_order": _step_scenario_order(req),
            "floors": _step_floors(req),
            "calibration": _step_calibration(req),
        }
        log_step("3.weights", component="tools/scenario_weights.check_weight_panel", log_dir=log_dir)
        if diagnostics.get("scenario_order") is not None:
            log_step("3.macro", component="tools/scenario_order_check.check_scenario_order", log_dir=log_dir)
        if diagnostics.get("calibration") is not None:
            log_step("3.cal", component="tools/binomial_calibration.calibration_test_per_grade", log_dir=log_dir)

        report_md = _build_report(req, diagnostics)
        log_step("4.report", component="tools/report_template.build_validation_report", log_dir=log_dir)
        completeness = check_report(report_md)
        log_step("5.complete", component="middleware/output_completeness_guard.check_report", log_dir=log_dir)
        citations = check_numeric_citations(report_md)
        log_step("5.cite", component="middleware/output_completeness_guard.check_numeric_citations", log_dir=log_dir)
        watermarks = check_watermarks(report_md)
        log_step("5.watermark", component="middleware/draft_watermark_guard.check_watermarks", log_dir=log_dir)
        ctx["result_summary"] = {
            "completeness_passed": completeness["passed"],
            "citations_passed": citations["passed"],
            "watermarks_passed": watermarks["passed"],
            "weight_violations": int((~diagnostics["weights"]["passed"]).sum()),
        }
        return {
            "report_md": report_md,
            "diagnostics": diagnostics,
            "completeness": completeness,
            "citations": citations,
            "watermarks": watermarks,
        }


def _build_demo_request() -> IFRS9ValidationRequest:
    panel = pd.DataFrame(
        {
            "period": ["2024-Q1"] * 3 + ["2024-Q2"] * 3 + ["2024-Q3"] * 3,
            "scenario": ["base", "adverse", "severe"] * 3,
            "weight": [0.5, 0.3, 0.2, 0.5, 0.3, 0.2, 0.5, 0.3, 0.2],
        }
    )
    return IFRS9ValidationRequest(
        title="Demo IFRS 9 ECL Validation",
        weight_panel=panel,
        pd_by_scenario={
            "base": np.array([0.01, 0.02, 0.03]),
            "adverse": np.array([0.015, 0.025, 0.035]),
            "severe": np.array([0.025, 0.04, 0.05]),
        },
        pd_multipliers={
            "base": [1.0, 1.0, 1.0],
            "adverse": [1.5, 1.4, 1.3],
            "severe": [2.5, 2.0, 1.8],
        },
        grade_calibration=[
            {"grade": "A", "pd_estimated": 0.01, "default_count": 12, "exposure_count": 1000},
            {"grade": "B", "pd_estimated": 0.05, "default_count": 55, "exposure_count": 1000},
            {"grade": "C", "pd_estimated": 0.10, "default_count": 105, "exposure_count": 1000},
        ],
    )


def _load_request_from_csv(args: argparse.Namespace) -> IFRS9ValidationRequest:
    """CSV 입력에서 IFRS9ValidationRequest를 구성한다.

    weights_csv: 필수. 컬럼 = (period, scenario, weight) (이름은 인자로 조정)
    pd_csv: 선택. 컬럼 = (scenario, pd) - long format
    multipliers_csv: 선택. 컬럼 = (scenario, multiplier)
    calibration_csv: 선택. 컬럼 = (grade, pd_estimated, default_count, exposure_count)
    """
    panel = pd.read_csv(args.weights_csv)

    pd_by_scenario: dict[str, np.ndarray] | None = None
    if args.pd_csv:
        pd_df = pd.read_csv(args.pd_csv)
        for col in ("scenario", "pd"):
            if col not in pd_df.columns:
                raise KeyError(f"{args.pd_csv}: missing column {col!r}")
        pd_by_scenario = {
            sc: sub["pd"].astype(float).values
            for sc, sub in pd_df.groupby("scenario")
        }

    pd_multipliers: dict[str, list[float]] | None = None
    if args.multipliers_csv:
        m_df = pd.read_csv(args.multipliers_csv)
        for col in ("scenario", "multiplier"):
            if col not in m_df.columns:
                raise KeyError(f"{args.multipliers_csv}: missing column {col!r}")
        pd_multipliers = {
            sc: sub["multiplier"].astype(float).tolist()
            for sc, sub in m_df.groupby("scenario")
        }

    grade_calibration: list[dict] | None = None
    if args.calibration_csv:
        cal_df = pd.read_csv(args.calibration_csv)
        for col in ("grade", "pd_estimated", "default_count", "exposure_count"):
            if col not in cal_df.columns:
                raise KeyError(f"{args.calibration_csv}: missing column {col!r}")
        grade_calibration = cal_df.to_dict(orient="records")

    return IFRS9ValidationRequest(
        title=args.title,
        weight_panel=panel,
        weight_period_col=args.weight_period_col,
        weight_scenario_col=args.weight_scenario_col,
        weight_value_col=args.weight_value_col,
        pd_by_scenario=pd_by_scenario,
        pd_multipliers=pd_multipliers,
        grade_calibration=grade_calibration,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="validation-team-agent IFRS 9 runner")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--weights-csv", type=str, default=None,
                        help="CSV with columns: period, scenario, weight")
    parser.add_argument("--pd-csv", type=str, default=None,
                        help="optional CSV: scenario, pd (long format)")
    parser.add_argument("--multipliers-csv", type=str, default=None,
                        help="optional CSV: scenario, multiplier (long format)")
    parser.add_argument("--calibration-csv", type=str, default=None,
                        help="optional CSV: grade, pd_estimated, default_count, exposure_count")
    parser.add_argument("--title", type=str, default="IFRS 9 ECL Validation")
    parser.add_argument("--weight-period-col", type=str, default="period")
    parser.add_argument("--weight-scenario-col", type=str, default="scenario")
    parser.add_argument("--weight-value-col", type=str, default="weight")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.demo and args.weights_csv:
        parser.error("use either --demo or --weights-csv, not both")
    if not args.demo and not args.weights_csv:
        parser.error("either --demo or --weights-csv is required")

    req = _build_demo_request() if args.demo else _load_request_from_csv(args)
    out = run(req)
    if args.out:
        args.out.write_text(out["report_md"], encoding="utf-8")
    else:
        sys.stdout.write(out["report_md"])
        sys.stdout.write("\n")
    return 0 if out["completeness"]["passed"] and out["citations"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
