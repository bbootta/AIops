"""Orchestrator dry-run simulator.

``harness/orchestration_matrix.json`` 의 step 정의를 SSoT로 사용해 호출 plan을
생성한다. 실제 실행은 하지 않는다. ``run_validation.py`` 와 ``run_macro_validation.py``
가 어떤 단계를 수행하는지 미리 점검할 수 있다.

CLI:
    python -m tools.dry_run --demo
    python -m tools.dry_run --request request.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent.parent
MATRIX_PATH = ROOT / "harness" / "orchestration_matrix.json"


def load_matrix(path: Path | None = None) -> dict:
    p = path or MATRIX_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def _truthy(req: Mapping[str, Any], key: str) -> bool:
    val = req.get(key)
    if val is None or val is False:
        return False
    if isinstance(val, (str, list, tuple, set, dict)):
        return len(val) > 0
    return True


def _gate_passes(step: Mapping[str, Any], request: Mapping[str, Any]) -> bool:
    # activated_on_fail step 은 평소 plan 에서 제외 — 다른 step 의 on_fail_activate
    # 로만 동적 활성화된다 (tools.workflow 가 처리).
    if step.get("activated_on_fail"):
        return False
    if step.get("always"):
        return True
    if "requires_all" in step:
        if not all(_truthy(request, k) for k in step["requires_all"]):
            return False
    if "requires_any" in step:
        if not any(_truthy(request, k) for k in step["requires_any"]):
            return False
    return "requires_all" in step or "requires_any" in step


def simulate(
    request: Mapping[str, Any],
    matrix_path: Path | None = None,
) -> list[dict]:
    """검증 요청에 대해 호출 plan을 시뮬레이트한다."""
    matrix = load_matrix(matrix_path)
    plan: list[dict] = []
    for step in matrix["steps"]:
        if not _gate_passes(step, request):
            continue
        inputs: dict[str, Any] = {}
        for k in (
            *step.get("requires_all", []),
            *step.get("requires_any", []),
        ):
            inputs[k] = request.get(k)
        if step["id"] == "1.req":
            inputs = {
                "title": request.get("title", "(untitled)"),
                "columns_provided": sorted(
                    k for k in request if request.get(k) and k.endswith("_col")
                ),
            }
        elif step["id"] == "3.cal":
            inputs.setdefault("alpha", request.get("calibration_alpha", 0.05))
            inputs.setdefault("multitest", "holm")
        elif step["id"] == "6.audit":
            inputs.setdefault("status", "proposed")

        plan.append(
            {
                "id": step["id"],
                "name": step["name"],
                "component": step["component"],
                "inputs": inputs,
                "rationale": step["rationale"],
                "expected_outputs": list(step.get("expected_outputs", [])),
            }
        )
    return plan


def summarize_plan(plan: list[dict], *, max_items: int = 8) -> str:
    """plan을 보고서 audit_trail 섹션에 첨부할 짧은 1-line 목록으로 요약.

    `1.req → 2.schema → 2.safety → 3.disc → 4.report → 5.complete → 5.cite → 5.watermark (외 N건)`
    형태로 step id 시퀀스만 노출.
    """
    ids = [s["id"] for s in plan]
    if len(ids) <= max_items:
        return " → ".join(ids)
    head = " → ".join(ids[:max_items])
    return f"{head} → … (외 {len(ids) - max_items}건)"


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
        if step.get("expected_outputs"):
            outs = ", ".join(f"`{o}`" for o in step["expected_outputs"])
            lines.append(f"- expected_outputs: {outs}")
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
