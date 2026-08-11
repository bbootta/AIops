"""Runner 결과 dict의 schema 검증 헬퍼.

run_validation/run_macro_validation/run_ifrs9_validation 의 ``run()`` 결과는
공통적으로 ``report_md`` / ``completeness`` / ``citations`` / ``watermarks`` 키를
가진다. 본 헬퍼는 이를 ``harness/runner_result.schema.json`` 으로 검증한다.

본 모듈은 자동 호출되지 않는다. 호출자가 명시적으로 ``validate_result(out)`` 또는
CLI ``python -m tools.runner_result --runner credit`` 를 통해 사용한다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "harness" / "runner_result.schema.json"
SUB_SCHEMA_PATHS = {
    "credit": ROOT / "harness" / "runner_result_credit.schema.json",
    "macro": ROOT / "harness" / "runner_result_macro.schema.json",
    "ifrs9": ROOT / "harness" / "runner_result_ifrs9.schema.json",
}


def load_schema(path: Path | None = None) -> dict:
    return json.loads((path or SCHEMA_PATH).read_text(encoding="utf-8"))


def load_sub_schema(runner: str) -> dict:
    if runner not in SUB_SCHEMA_PATHS:
        raise ValueError(f"unknown runner: {runner!r}")
    return json.loads(SUB_SCHEMA_PATHS[runner].read_text(encoding="utf-8"))


def validate_result_subschema(result: dict, runner: str) -> None:
    """runner별 sub-schema로 결과를 검증한다.

    quant.sample_size.passed / diagnostics.series / diagnostics.weights 같은
    runner-specific 필드까지 강제. report_md / completeness / citations /
    watermarks 는 sub-schema에서도 그대로 검증.
    """
    import jsonschema

    schema = load_sub_schema(runner)
    minimal: dict = {
        "report_md": result.get("report_md"),
        "completeness": {
            "passed": bool(result.get("completeness", {}).get("passed", False))
        },
        "citations": {
            "passed": bool(result.get("citations", {}).get("passed", False))
        },
        "watermarks": {
            "passed": bool(result.get("watermarks", {}).get("passed", False))
        },
    }
    if runner == "credit":
        quant = result.get("quant", {})
        sample = quant.get("sample_size", {})
        minimal["quant"] = {
            "sample_size": {"passed": bool(sample.get("passed", False))}
        }
    elif runner == "macro":
        diag = result.get("diagnostics", {})
        minimal["diagnostics"] = {
            "series": {
                str(k): {"label": str(v.get("label"))}
                for k, v in (diag.get("series") or {}).items()
            }
        }
    elif runner == "ifrs9":
        diag = result.get("diagnostics", {})
        # weights는 DataFrame이라 JSON 불가; 존재만 확인.
        weights_present = "weights" in diag
        minimal["diagnostics"] = {"weights": weights_present}
    jsonschema.validate(minimal, schema)


def validate_result(result: dict, schema_path: Path | None = None) -> None:
    """jsonschema로 결과 dict를 검증. 위반 시 jsonschema.ValidationError 전파.

    runner 결과 dict의 일부 필드(예: pandas.DataFrame)는 schema에 노출되지 않는다.
    schema는 핵심 필드만 강제하므로 추가 필드는 자유롭게 보존된다.
    """
    import jsonschema

    schema = load_schema(schema_path)
    # report_md만 추출해 상위 필드만 검증한다 (DataFrame 등 비-JSON 필드 우회).
    minimal = {
        "report_md": result.get("report_md"),
        "completeness": {
            "passed": bool(result.get("completeness", {}).get("passed", False))
        },
        "citations": {
            "passed": bool(result.get("citations", {}).get("passed", False))
        },
        "watermarks": {
            "passed": bool(result.get("watermarks", {}).get("passed", False))
        },
    }
    jsonschema.validate(minimal, schema)


def _cmd_validate_runner(args: argparse.Namespace) -> int:
    """선택한 runner를 demo로 한 번 실행하고 결과를 schema로 검증."""
    if __package__ in (None, ""):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    if args.runner == "credit":
        from tools.run_validation import _build_demo_request, run
    elif args.runner == "macro":
        from tools.run_macro_validation import _build_demo_request, run
    elif args.runner == "ifrs9":
        from tools.run_ifrs9_validation import _build_demo_request, run
    else:  # pragma: no cover - argparse choices 강제
        raise ValueError(f"unknown runner: {args.runner}")

    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix=f"runner_result_{args.runner}_"))
    out = run(_build_demo_request(), log_dir=tmp)
    try:
        validate_result(out)
    except Exception as exc:
        print(f"invalid: {exc}", file=sys.stderr)
        return 2
    print(f"runner_result schema OK ({args.runner})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="runner result schema validator")
    parser.add_argument(
        "--runner",
        required=True,
        choices=["credit", "macro", "ifrs9"],
        help="선택한 runner를 demo로 1회 실행 후 결과를 schema 검증",
    )
    parser.set_defaults(func=_cmd_validate_runner)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
