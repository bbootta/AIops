"""Command-line interface for quant-validation-agent.

Subcommands:
- run         Read a validation request markdown and print a structured plan.
- thresholds  Print thresholds (optionally for a specific metric/model/segment).
- check       Run the permission/PII guards against an input string or file.
- validate    Run a small end-to-end validation pass on a local CSV (scoring/PD).
- note        Append a recurring-finding note to memory/.

The CLI never executes operational actions. It only prepares plans, reads
local files, and runs guards. It exits non-zero when guards fail.
"""
from __future__ import annotations

import argparse
import datetime as _dt
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
    segment = getattr(args, "segment", None)
    if args.metric:
        out = threshold_loader.get_metric_threshold(policy, args.metric, segment=segment)
        print(json.dumps({args.metric: out}, ensure_ascii=False, indent=2))
        return 0
    if args.model_type:
        metrics = threshold_loader.list_metrics_for_model(policy, args.model_type)
        out = {
            m: threshold_loader.get_metric_threshold(policy, m, segment=segment)
            for m in metrics
        }
        print(json.dumps({args.model_type: out}, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(policy, ensure_ascii=False, indent=2))
    return 0


def _rag_with_threshold(value, policy, metric, segment=None):
    from tools import validation_summary

    try:
        cfg = threshold_loader.get_metric_threshold(policy, metric, segment=segment)
    except KeyError:
        return {"value": value, "rag": "Gray", "source": None}
    rag = validation_summary.assign_rag_status(
        value,
        green_threshold=cfg["green_threshold"],
        yellow_threshold=cfg["yellow_threshold"],
        direction=cfg["direction"],
    )
    return {
        "value": value,
        "rag": rag,
        "green_threshold": cfg["green_threshold"],
        "yellow_threshold": cfg["yellow_threshold"],
        "direction": cfg["direction"],
        "source": cfg["source"],
    }


def cmd_validate(args: argparse.Namespace) -> int:
    """Run a minimal end-to-end pass on a local CSV.

    Supports two modes:
    - model_type='scoring' or 'pd': requires --target and --score
    - model_type='lgd' or 'ead': requires --actual and --predicted
    """
    import pandas as pd

    from middleware import leakage_guard, schema_guard
    from tools import (
        io_utils,
        metric_ks_auc_ar,
        metric_lgd_ead,
        metric_psi,
        target_validation,
    )

    df = io_utils.read_csv_safely(args.data)
    df = io_utils.normalize_column_names(df)

    report: dict = {
        "data_path": os.path.abspath(args.data),
        "model_type": args.model_type,
        "segment": args.segment,
        "n_rows": int(df.shape[0]),
        "metrics": {},
        "issues": [],
        "schema": {},
    }

    if args.model_type in ("scoring", "pd"):
        required = [args.target, args.score]
        sch = schema_guard.check_required_columns(df, required)
        report["schema"]["required_columns"] = sch
        if not sch["pass"]:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 4
        # Leakage check on non-target/score features
        feature_candidates = [c for c in df.columns if c not in (args.target, args.score)]
        leak = leakage_guard.detect_leakage_candidates(feature_candidates)
        if leak:
            report["issues"].append(
                {
                    "issue": "leakage_candidates",
                    "severity": "Yellow",
                    "evidence": [c["column"] for c in leak],
                }
            )
        try:
            target_validation.validate_binary_target(df[args.target])
        except ValueError as e:
            report["issues"].append({"issue": "binary_target_invalid", "severity": "Red", "evidence": str(e)})
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 4
        higher_is_worse = bool(args.higher_is_worse)
        ks = metric_ks_auc_ar.calculate_ks(df[args.target], df[args.score], higher_is_worse=higher_is_worse)
        auc = metric_ks_auc_ar.calculate_auc(df[args.target], df[args.score], higher_is_worse=higher_is_worse)
        ar = metric_ks_auc_ar.calculate_accuracy_ratio(df[args.target], df[args.score], higher_is_worse=higher_is_worse)
        policy = threshold_loader.load_threshold_policy()
        report["metrics"]["ks"] = _rag_with_threshold(ks, policy, "ks", segment=args.segment)
        report["metrics"]["auroc"] = _rag_with_threshold(auc, policy, "auroc", segment=args.segment)
        report["metrics"]["ar"] = _rag_with_threshold(ar, policy, "ar", segment=args.segment)
        if args.dataset_col and args.dataset_col in df.columns and args.baseline_value is not None:
            base = df[df[args.dataset_col] == args.baseline_value][args.score]
            cur = df[df[args.dataset_col] != args.baseline_value][args.score]
            if len(base) > 0 and len(cur) > 0:
                psi = metric_psi.calculate_psi(base, cur, bins=10)
                report["metrics"]["psi"] = _rag_with_threshold(psi, policy, "psi", segment=args.segment)
            else:
                report["issues"].append({"issue": "psi_skipped", "severity": "Gray", "evidence": "empty baseline or current sample"})
    elif args.model_type in ("lgd", "ead"):
        required = [args.actual, args.predicted]
        sch = schema_guard.check_required_columns(df, required)
        report["schema"]["required_columns"] = sch
        if not sch["pass"]:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 4
        mae = metric_lgd_ead.calculate_mae(df[args.actual], df[args.predicted])
        rmse = metric_lgd_ead.calculate_rmse(df[args.actual], df[args.predicted])
        bias = metric_lgd_ead.calculate_bias(df[args.actual], df[args.predicted])
        policy = threshold_loader.load_threshold_policy()
        if args.model_type == "lgd":
            report["metrics"]["mae"] = _rag_with_threshold(mae, policy, "mae_lgd", segment=args.segment)
            report["metrics"]["rmse"] = _rag_with_threshold(rmse, policy, "rmse_lgd", segment=args.segment)
            report["metrics"]["bias"] = _rag_with_threshold(bias, policy, "bias_lgd", segment=args.segment)
        else:
            # EAD: normalize errors by mean realized to make thresholds portable
            mean_actual = float(df[args.actual].mean())
            if mean_actual == 0:
                report["metrics"]["mae"] = {"value": mae, "rag": "Gray", "source": "mean_actual_zero"}
                report["metrics"]["rmse"] = {"value": rmse, "rag": "Gray", "source": "mean_actual_zero"}
                report["metrics"]["bias"] = {"value": bias, "rag": "Gray", "source": "mean_actual_zero"}
            else:
                mae_ratio = mae / mean_actual
                rmse_ratio = rmse / mean_actual
                bias_ratio = bias / mean_actual
                report["metrics"]["mae_ratio"] = _rag_with_threshold(mae_ratio, policy, "mae_ead_ratio", segment=args.segment)
                report["metrics"]["rmse_ratio"] = _rag_with_threshold(rmse_ratio, policy, "rmse_ead_ratio", segment=args.segment)
                report["metrics"]["bias_ratio"] = _rag_with_threshold(bias_ratio, policy, "bias_ead_ratio", segment=args.segment)
                report["metrics"]["mae_raw"] = {"value": mae, "rag": "Gray", "source": "raw_currency_units"}
                report["metrics"]["rmse_raw"] = {"value": rmse, "rag": "Gray", "source": "raw_currency_units"}
                report["metrics"]["bias_raw"] = {"value": bias, "rag": "Gray", "source": "raw_currency_units"}
    else:
        report["issues"].append({"issue": "unsupported_model_type", "severity": "Red", "evidence": args.model_type})
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 4

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    if getattr(args, "log_dir", None):
        from middleware import run_logger

        run_logger.write_run_log(
            request_summary=f"validate {args.model_type}",
            inputs=[args.data],
            functions_used=[
                "io_utils.read_csv_safely",
                "schema_guard.check_required_columns",
                "tools.metric_*",
            ],
            main_results=report.get("metrics", {}),
            errors=[],
            artifacts=[args.out] if args.out else [],
            test_results={},
            incomplete_items=list(report.get("issues", [])),
            log_dir=args.log_dir,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_validate_scenario(args: argparse.Namespace) -> int:
    """Run the scenario regression pipeline against local CSVs."""
    import pandas as pd

    from tools import io_utils, scenario_regression_pipeline

    hist = io_utils.read_csv_safely(args.hist_data)
    sc = io_utils.read_csv_safely(args.scenario_data)
    hist = io_utils.normalize_column_names(hist)
    sc = io_utils.normalize_column_names(sc)

    feats = [c.strip() for c in args.features.split(",") if c.strip()]
    if not feats:
        print(json.dumps({"error": "no features parsed from --features"}, ensure_ascii=False))
        return 4
    expected_signs = None
    if args.expected_signs:
        expected_signs = {}
        for kv in args.expected_signs.split(","):
            if "=" not in kv:
                continue
            k, v = kv.split("=", 1)
            expected_signs[k.strip()] = v.strip()
    floors = None
    if args.multiplier_floors:
        floors = {}
        for kv in args.multiplier_floors.split(","):
            if "=" not in kv:
                continue
            k, v = kv.split("=", 1)
            try:
                floors[k.strip()] = float(v.strip())
            except ValueError:
                continue
    out = scenario_regression_pipeline.run_pipeline(
        hist,
        target_col=args.target,
        feature_cols=feats,
        scenario_df=sc,
        scenario_col=args.scenario_col,
        period_col=args.period_col,
        pred_col_in_scenario=args.pred_col_in_scenario,
        expected_signs=expected_signs,
        multiplier_floor_by_scenario=floors,
        severity_direction=args.direction,
    )
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    if getattr(args, "log_dir", None):
        from middleware import run_logger

        run_logger.write_run_log(
            request_summary="validate-scenario",
            inputs=[args.hist_data, args.scenario_data],
            functions_used=["scenario_regression_pipeline.run_pipeline"],
            main_results={
                "fit_summary": out["fit"]["summary"],
                "severity_violations": out["severity"]["order"]["n_violation_total"],
            },
            errors=[],
            artifacts=[args.out] if args.out else [],
            test_results={},
            incomplete_items=[],
            log_dir=args.log_dir,
        )
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_note(args: argparse.Namespace) -> int:
    """Append a single bullet to memory/recurring_validation_findings.md."""
    text = (args.text or "").strip()
    if not text:
        print(json.dumps({"error": "empty note"}, ensure_ascii=False))
        return 4
    risky = permission_guard.detect_risky_commands(text)
    pii = data_safety_guard.detect_pii_in_text(text)
    if risky or pii:
        print(
            json.dumps(
                {
                    "error": "guard_violation",
                    "risky_commands": risky,
                    "pii_matches": pii,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 5
    target_path = args.path or os.path.join(_PROJECT_ROOT, "memory", "recurring_validation_findings.md")
    today = _dt.datetime.now().strftime("%Y-%m-%d")
    bullet = f"- {today} / {args.model or 'unspecified'} / {text}\n"
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    if not os.path.exists(target_path):
        with open(target_path, "w", encoding="utf-8") as f:
            f.write("# recurring_validation_findings.md\n\n")
    with open(target_path, "a", encoding="utf-8") as f:
        f.write(bullet)
    print(
        json.dumps(
            {"appended_to": target_path, "bullet": bullet.rstrip()},
            ensure_ascii=False,
            indent=2,
        )
    )
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
    p_th.add_argument("--segment", help="Apply segment-level overrides if present.")
    p_th.add_argument("--path", help="Override path to threshold_policy.json.")
    p_th.set_defaults(func=cmd_thresholds)

    p_chk = sub.add_parser("check", help="Run permission/PII guards on input.")
    grp = p_chk.add_mutually_exclusive_group(required=True)
    grp.add_argument("--path", help="Path to a text file to scan.")
    grp.add_argument("--text", help="Inline text to scan.")
    p_chk.set_defaults(func=cmd_check)

    p_v = sub.add_parser("validate", help="Run a small end-to-end validation pass on a local CSV.")
    p_v.add_argument("--data", required=True, help="Path to the CSV file.")
    p_v.add_argument("--model-type", dest="model_type", required=True,
                     choices=["scoring", "pd", "lgd", "ead"])
    p_v.add_argument("--target", help="Target column (scoring/pd).")
    p_v.add_argument("--score", help="Score or PD column (scoring/pd).")
    p_v.add_argument("--actual", help="Realized column (lgd/ead).")
    p_v.add_argument("--predicted", help="Predicted column (lgd/ead).")
    p_v.add_argument("--higher-is-worse", dest="higher_is_worse",
                     action="store_true",
                     help="Set when higher score implies higher risk (default off).")
    p_v.add_argument("--dataset-col", dest="dataset_col",
                     help="Column splitting baseline vs current for PSI.")
    p_v.add_argument("--baseline-value", dest="baseline_value",
                     help="Value of dataset-col denoting baseline (e.g., dev).")
    p_v.add_argument("--segment", help="Segment label for threshold overrides.")
    p_v.add_argument("--out", help="Optional path to write the JSON report.")
    p_v.add_argument("--log-dir", dest="log_dir",
                     help="Optional directory to write a run-log JSON via middleware.run_logger.")
    p_v.set_defaults(func=cmd_validate)

    p_n = sub.add_parser("note", help="Append a recurring-finding note.")
    p_n.add_argument("subaction", choices=["add"])
    p_n.add_argument("--text", required=True, help="The note text (single line).")
    p_n.add_argument("--model", help="Model name or type for the note.")
    p_n.add_argument("--path", help="Override target file path.")
    p_n.set_defaults(func=cmd_note)

    p_vs = sub.add_parser(
        "validate-scenario",
        help="Run the scenario regression pipeline on local CSV inputs.",
    )
    p_vs.add_argument("--hist-data", dest="hist_data", required=True,
                      help="Historical data CSV for OLS fitting.")
    p_vs.add_argument("--scenario-data", dest="scenario_data", required=True,
                      help="Scenario data CSV with base/adverse/severe rows.")
    p_vs.add_argument("--target", required=True,
                      help="Target column in hist data.")
    p_vs.add_argument("--features", required=True,
                      help="Comma-separated feature column names.")
    p_vs.add_argument("--scenario-col", dest="scenario_col", default="scenario",
                      help="Scenario label column in scenario data.")
    p_vs.add_argument("--period-col", dest="period_col", default=None,
                      help="Optional period column for time-aligned severity check.")
    p_vs.add_argument("--pred-col-in-scenario", dest="pred_col_in_scenario", default=None,
                      help="If set, use this column instead of model prediction.")
    p_vs.add_argument("--expected-signs", dest="expected_signs", default=None,
                      help="Optional comma-separated expected signs, e.g. gdp=-,unemp=+")
    p_vs.add_argument("--multiplier-floors", dest="multiplier_floors", default=None,
                      help="Optional comma-separated floors per scenario, e.g. base=1.0,severe=1.0")
    p_vs.add_argument("--direction", default="higher_is_worse",
                      choices=["higher_is_worse", "lower_is_worse"])
    p_vs.add_argument("--out", help="Optional path to write the JSON report.")
    p_vs.add_argument("--log-dir", dest="log_dir",
                      help="Optional directory to write a run-log JSON via middleware.run_logger.")
    p_vs.set_defaults(func=cmd_validate_scenario)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
