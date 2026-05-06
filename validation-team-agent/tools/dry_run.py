"""Orchestrator dry-run simulator.

``subagents/orchestrator.md`` 의 호출 매트릭스를 따라, 주어진 검증 요청
컬럼/플래그에 대해 어떤 도구가 어떤 인자로 호출될지 plan 형태로 출력한다.
실제 실행은 하지 않는다.

사용:
    plan = simulate({
        "title": "Credit Score Demo",
        "score_col": "score",
        "target_col": "target",
        "set_col": "set",
        "grade_col": "grade",
        "pd_col": "pd",
    })
    render_markdown(plan) -> str

CLI:
    python -m tools.dry_run --demo
    python -m tools.dry_run --request request.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass
class Step:
    name: str
    component: str
    inputs: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "component": self.component,
            "inputs": self.inputs,
            "rationale": self.rationale,
        }


def _cols(req: Mapping[str, Any]) -> set[str]:
    return {k for k in ("score_col", "target_col", "set_col", "grade_col", "pd_col", "date_col") if req.get(k)}


def simulate(request: Mapping[str, Any]) -> list[dict]:
    """검증 요청에 대해 호출 plan을 시뮬레이트한다."""
    cols = _cols(request)
    title = request.get("title", "(untitled)")
    plan: list[Step] = []

    plan.append(
        Step(
            "1. 요청 재구성",
            "subagents/orchestrator.md",
            inputs={"title": title, "columns_provided": sorted(cols)},
            rationale="목적/사용자/맥락/제약/성공 기준 명시.",
        )
    )

    plan.append(
        Step(
            "2.1 데이터 안전 점검",
            "middleware/data_safety_guard.scan_dataframe",
            inputs={"text_columns": "auto"},
            rationale="민감정보 패턴 탐지 (탐지 시 분석 차단).",
        )
    )
    if request.get("feature_names"):
        plan.append(
            Step(
                "2.2 누수 점검",
                "middleware/leakage_guard.check_leakage",
                inputs={"target_name": request.get("target_col", "target")},
                rationale="설명변수에 target/outcome 변수가 섞였는지 확인.",
            )
        )
    if request.get("date_col"):
        plan.append(
            Step(
                "2.3 기간 누락 점검",
                "tools/data_profile.check_date_coverage",
                inputs={"date_col": request["date_col"]},
                rationale="월 단위 누락 탐지.",
            )
        )
    if request.get("key_cols"):
        plan.append(
            Step(
                "2.4 중복 점검",
                "tools/data_profile.check_duplicates",
                inputs={"key_cols": list(request["key_cols"])},
                rationale="키 기준 중복 행 식별.",
            )
        )
    plan.append(
        Step(
            "2.5 표본 적정성 점검",
            "middleware/sample_size_guard.check_sample_size",
            inputs={"per_grade_aware": bool(request.get("grade_col"))},
            rationale="총 표본/부도/등급별 임계 점검.",
        )
    )

    if request.get("score_col") and request.get("target_col"):
        plan.append(
            Step(
                "3.1 변별력",
                "tools/metric_ks_auc.calculate_ks + calculate_auc_gini",
                inputs={"score": request["score_col"], "target": request["target_col"]},
                rationale="KS / AUROC / Gini 산출.",
            )
        )
        if request.get("set_col"):
            plan.append(
                Step(
                    "3.2 안정성 (dev vs oot)",
                    "tools/metric_psi.calculate_psi",
                    inputs={"split_by": request["set_col"], "bins": 10},
                    rationale="개발 vs 운영 score 분포 안정성.",
                )
            )
    if request.get("grade_col") and request.get("pd_col") and request.get("target_col"):
        plan.append(
            Step(
                "3.3 등급별 캘리브레이션",
                "tools/binomial_calibration.calibration_test_per_grade",
                inputs={"alpha": request.get("calibration_alpha", 0.05), "multitest": "holm"},
                rationale="추정 PD vs 실측 부도율 이항검정 + Holm 보정.",
            )
        )
    if request.get("macro_features"):
        plan.append(
            Step(
                "3.4 거시 변수 정상성",
                "tools/regression_diagnostics.stationarity_summary",
                inputs={"features": list(request["macro_features"])},
                rationale="ADF + KPSS 결합 라벨링.",
            )
        )

    plan.append(
        Step(
            "4. 보고서 초안",
            "tools/report_template.build_validation_report",
            inputs={"title": title},
            rationale="표준 10개 섹션 마크다운 생성.",
        )
    )
    plan.append(
        Step(
            "5.1 완결성 점검",
            "middleware/output_completeness_guard.check_report",
            inputs={},
            rationale="필수 섹션 / 한계 / 추가 확인사항 점검.",
        )
    )
    plan.append(
        Step(
            "5.2 인용 점검",
            "middleware/output_completeness_guard.check_numeric_citations",
            inputs={},
            rationale="결과/이상징후 섹션의 수치-출처 인용 점검.",
        )
    )
    plan.append(
        Step(
            "6. 변경 이력 기록",
            "harness/change_manifest.json (via tools/manifest.py)",
            inputs={"status": "proposed"},
            rationale="실행 결과 / 정책 변경 시 매니페스트에 기록.",
        )
    )
    return [s.to_dict() for s in plan]


def render_markdown(plan: list[dict]) -> str:
    """plan dict 리스트를 사람이 읽기 좋은 마크다운으로 변환."""
    lines = ["# Orchestrator Dry-Run Plan", ""]
    for step in plan:
        lines.append(f"## {step['name']}")
        lines.append(f"- component: `{step['component']}`")
        if step["inputs"]:
            lines.append(f"- inputs: `{json.dumps(step['inputs'], ensure_ascii=False)}`")
        if step["rationale"]:
            lines.append(f"- rationale: {step['rationale']}")
        lines.append("")
    lines.append("> 본 plan은 시뮬레이션이며 실제 도구를 실행하지 않습니다.")
    return "\n".join(lines)


def _demo_request() -> dict:
    return {
        "title": "Demo Credit Scoring",
        "score_col": "score",
        "target_col": "target",
        "set_col": "set",
        "grade_col": "grade",
        "pd_col": "pd",
        "date_col": "obs_date",
        "key_cols": ["customer_id", "obs_date"],
        "feature_names": ["score", "income", "ltv"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="orchestrator dry-run simulator")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--request", type=Path, default=None, help="JSON request file")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.demo and args.request:
        parser.error("use either --demo or --request, not both")
    if not args.demo and not args.request:
        parser.error("either --demo or --request is required")

    req = _demo_request() if args.demo else json.loads(args.request.read_text(encoding="utf-8"))
    plan = simulate(req)
    md = render_markdown(plan)
    if args.out:
        args.out.write_text(md, encoding="utf-8")
    else:
        sys.stdout.write(md + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
