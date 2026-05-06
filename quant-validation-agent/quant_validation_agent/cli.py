"""Command-line interface for quant-validation-agent.

Subcommands:
- run         Read a validation request markdown and print a structured plan.
- thresholds  Print thresholds (optionally for a specific metric/model).
- check       Run the permission/PII guards against an input string or file.

The CLI never executes operational actions. It only prepares plans, reads
local files, and runs guards. It exits non-zero when guards fail.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

# Make sibling top-level packages (tools/, middleware/) importable when
# invoked from the project root via `python -m quant_validation_agent`.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from middleware import data_safety_guard, permission_guard  # noqa: E402
from tools import threshold_loader  # noqa: E402


def _read_text(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _parse_request_metadata(text: str) -> dict:
    """Extract simple key:value metadata from a request markdown.

    Looks for lines like '- 모형명:', '- 모형 유형:', etc. Returns the matched
    fields. Unknown formats are returned as an empty dict.
    """
    fields = {
        "model_name": ["모형명"],
        "model_type": ["모형 유형"],
        "validation_type": ["검증 구분"],
        "data_path": ["경로"],
        "target_col": ["target"],
        "score_col": ["score"],
    }
    out: dict = {}
    for line in text.splitlines():
        s = line.strip().lstrip("-").strip()
        for key, labels in fields.items():
            for label in labels:
                prefix = f"{label}:"
                if s.startswith(prefix):
                    out[key] = s[len(prefix):].strip()
    return out


def cmd_run(args: argparse.Namespace) -> int:
    text = _read_text(args.request)
    risky = permission_guard.detect_risky_commands(text)
    pii = data_safety_guard.detect_pii_in_text(text)
    meta = _parse_request_metadata(text)
    plan = {
        "request_path": os.path.abspath(args.request),
        "parsed_metadata": meta,
        "guards": {
            "risky_commands": risky,
            "pii_matches": pii,
        },
        "next_steps": [
            "1. data_contract_checker — 입력 데이터 스키마 점검",
            "2. metric_calculator — 모형 유형별 지표 계산",
            "3. stability_checker / calibration_checker / regression_diagnostics_reviewer / scenario_validator (해당 시)",
            "4. validation_summary — 표준 9개 섹션 통합",
            "5. change_manifest 기록 + run_logger 저장",
        ],
        "notes": [
            "본 CLI는 실행 계획만 출력한다. 실제 데이터 분석은 tools/* 함수 호출로 수행한다.",
            "운영계 통신, git push, 배포는 자동 수행되지 않는다.",
        ],
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    # `run` only emits a plan; do not fail on guard findings here.
    # Use `check` for a strict gate.
    return 0


def cmd_thresholds(args: argparse.Namespace) -> int:
    policy = threshold_loader.load_threshold_policy(args.path) if args.path else threshold_loader.load_threshold_policy()
    if args.metric:
        out = threshold_loader.get_metric_threshold(policy, args.metric)
        print(json.dumps({args.metric: out}, ensure_ascii=False, indent=2))
        return 0
    if args.model_type:
        metrics = threshold_loader.list_metrics_for_model(policy, args.model_type)
        out = {m: threshold_loader.get_metric_threshold(policy, m) for m in metrics}
        print(json.dumps({args.model_type: out}, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(policy, ensure_ascii=False, indent=2))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    text = _read_text(args.path) if args.path else (args.text or "")
    risky = permission_guard.detect_risky_commands(text)
    pii = data_safety_guard.detect_pii_in_text(text)
    print(
        json.dumps(
            {"risky_commands": risky, "pii_matches": pii},
            ensure_ascii=False,
            indent=2,
        )
    )
    if risky:
        return 2
    if pii:
        return 3
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quant_validation_agent",
        description="Quantitative validation agent — local-only CLI.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Read a validation request and print a plan.")
    p_run.add_argument("--request", required=True, help="Path to a request markdown file.")
    p_run.set_defaults(func=cmd_run)

    p_th = sub.add_parser("thresholds", help="Print threshold policy.")
    p_th.add_argument("--metric", help="Single metric to look up.")
    p_th.add_argument("--model-type", dest="model_type", help="List metrics for a model type.")
    p_th.add_argument("--path", help="Override path to threshold_policy.json.")
    p_th.set_defaults(func=cmd_thresholds)

    p_chk = sub.add_parser("check", help="Run permission/PII guards on input.")
    grp = p_chk.add_mutually_exclusive_group(required=True)
    grp.add_argument("--path", help="Path to a text file to scan.")
    grp.add_argument("--text", help="Inline text to scan.")
    p_chk.set_defaults(func=cmd_check)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
