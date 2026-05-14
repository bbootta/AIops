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

from . import __version__  # noqa: E402
from tools import threshold_loader  # noqa: E402


def _read_text(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _load_validated_policy(path: Optional[str] = None) -> dict:
    """Load the threshold policy and schema-validate it.

    Centralized so every CLI command operates on a policy that has passed
    structural validation (validate_policy raises ValueError on failure).
    """
    policy = threshold_loader.load_threshold_policy(path) if path else threshold_loader.load_threshold_policy()
    threshold_loader.validate_policy(policy)
    return policy


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
    try:
        policy = _load_validated_policy(args.path)
    except (ValueError, FileNotFoundError) as e:
        print(json.dumps({"error": "policy_invalid", "detail": str(e)}, ensure_ascii=False))
        return 6
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
        try:
            policy = _load_validated_policy()
        except ValueError as e:
            print(json.dumps({"error": "policy_invalid", "detail": str(e)}, ensure_ascii=False))
            return 6
        report["metrics"]["ks"] = _rag_with_threshold(ks, policy, "ks", segment=args.segment)
        report["metrics"]["auroc"] = _rag_with_threshold(auc, policy, "auroc", segment=args.segment)
        report["metrics"]["ar"] = _rag_with_threshold(ar, policy, "ar", segment=args.segment)
        if getattr(args, "decile_rag", False):
            from tools import decile_lift

            try:
                lift = decile_lift.build_lift_table(
                    df[args.target], df[args.score], n_bins=10,
                    higher_is_worse=higher_is_worse,
                )
                top = float(lift.iloc[0]["lift"]) if not lift.empty else None
                report["metrics"]["lift_top_decile"] = _rag_with_threshold(
                    top, policy, "lift_top_decile", segment=args.segment
                )
            except Exception as e:
                report["issues"].append({
                    "issue": "lift_top_decile_failed",
                    "severity": "Gray",
                    "evidence": str(e),
                })
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
        try:
            policy = _load_validated_policy()
        except ValueError as e:
            print(json.dumps({"error": "policy_invalid", "detail": str(e)}, ensure_ascii=False))
            return 6
        if args.model_type == "lgd":
            report["metrics"]["mae"] = _rag_with_threshold(mae, policy, "mae_lgd", segment=args.segment)
            report["metrics"]["rmse"] = _rag_with_threshold(rmse, policy, "rmse_lgd", segment=args.segment)
            report["metrics"]["bias"] = _rag_with_threshold(bias, policy, "bias_lgd", segment=args.segment)
        else:
            # EAD: normalize errors using the policy-defined normalizer.
            ead_settings = threshold_loader.get_ead_metric_settings(policy)
            normalizer_name = args.ead_normalizer or ead_settings["normalizer"]
            if normalizer_name not in ead_settings["allowed_normalizers"]:
                report["issues"].append(
                    {
                        "issue": "ead_normalizer_invalid",
                        "severity": "Red",
                        "evidence": f"--ead-normalizer={normalizer_name} not in allowed list",
                    }
                )
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 4
            if normalizer_name == "mean_realized":
                divisor = float(df[args.actual].mean())
            elif normalizer_name == "mean_predicted":
                divisor = float(df[args.predicted].mean())
            elif normalizer_name == "total_exposure":
                if "limit" not in df.columns:
                    report["issues"].append(
                        {
                            "issue": "total_exposure_unavailable",
                            "severity": "Red",
                            "evidence": "'limit' column required for total_exposure normalizer",
                        }
                    )
                    print(json.dumps(report, ensure_ascii=False, indent=2))
                    return 4
                divisor = float(df["limit"].sum() / max(int(df.shape[0]), 1))
            else:  # safety net
                divisor = 0.0
            report["ead_normalizer"] = normalizer_name
            if divisor == 0:
                report["metrics"]["mae"] = {"value": mae, "rag": "Gray", "source": "normalizer_zero"}
                report["metrics"]["rmse"] = {"value": rmse, "rag": "Gray", "source": "normalizer_zero"}
                report["metrics"]["bias"] = {"value": bias, "rag": "Gray", "source": "normalizer_zero"}
            else:
                mae_ratio = mae / divisor
                rmse_ratio = rmse / divisor
                bias_ratio = bias / divisor
                report["metrics"]["mae_ratio"] = _rag_with_threshold(mae_ratio, policy, "mae_ead_ratio", segment=args.segment)
                report["metrics"]["rmse_ratio"] = _rag_with_threshold(rmse_ratio, policy, "rmse_ead_ratio", segment=args.segment)
                report["metrics"]["bias_ratio"] = _rag_with_threshold(bias_ratio, policy, "bias_ead_ratio", segment=args.segment)
                report["metrics"]["mae_raw"] = {"value": mae, "rag": "Gray", "source": "raw_currency_units"}
                report["metrics"]["rmse_raw"] = {"value": rmse, "rag": "Gray", "source": "raw_currency_units"}
                report["metrics"]["bias_raw"] = {"value": bias, "rag": "Gray", "source": "raw_currency_units"}
        if getattr(args, "segment_detail", False):
            seg_col = args.segment_col
            if not seg_col or seg_col not in df.columns:
                report.setdefault("issues", []).append({
                    "issue": "segment_detail_skipped",
                    "severity": "Gray",
                    "evidence": f"--segment-col={seg_col!r} not present in data",
                })
            else:
                from tools import metric_lgd_ead

                try:
                    seg_df = metric_lgd_ead.summarize_error_by_segment(
                        df, args.actual, args.predicted, seg_col
                    )
                    report["segment_detail"] = {
                        "segment_col": seg_col,
                        "rows": seg_df.to_dict(orient="records"),
                    }
                except Exception as e:
                    report.setdefault("issues", []).append({
                        "issue": "segment_detail_failed",
                        "severity": "Gray",
                        "evidence": str(e),
                    })
    else:
        report["issues"].append({"issue": "unsupported_model_type", "severity": "Red", "evidence": args.model_type})
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 4

    # Aggregate worst RAG across emitted metrics. Caller can rely on this
    # single field for triage instead of inspecting every metric block.
    rag_states = [
        m.get("rag", "Gray") for m in report.get("metrics", {}).values()
        if isinstance(m, dict)
    ]
    if "Red" in rag_states:
        report["overall_rag"] = "Red"
    elif "Yellow" in rag_states:
        report["overall_rag"] = "Yellow"
    elif rag_states and "Gray" not in rag_states:
        report["overall_rag"] = "Green"
    else:
        report["overall_rag"] = "Gray"

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
    if getattr(args, "explain", False):
        print("\n--- markdown ---")
        print(_render_report_markdown(report))
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
        autocorr_lags=int(args.autocorr_lags),
        run_stationarity_check=not args.skip_stationarity,
        stationarity_alpha=float(args.stationarity_alpha),
    )
    mp = getattr(args, "max_predictions", None)
    if mp is not None:
        if mp < 1:
            print(json.dumps({"error": "max_predictions_invalid", "detail": "must be >= 1"},
                             ensure_ascii=False))
            return 4
        preds = out.get("predictions") or []
        if len(preds) > mp:
            out["predictions_total"] = len(preds)
            out["predictions_truncated"] = len(preds) - mp
            out["predictions"] = preds[:mp]
    # Single-field overall RAG combining severity, floors, and (when policy
    # is loaded for the report) future fit_rag. Severity / floor violations
    # alone are sufficient to force Red.
    n_vio = ((out.get("severity") or {}).get("order") or {}).get("n_violation_total", 0)
    floor_violation = any(f.get("violation") for f in (out.get("multiplier_floors") or []))
    if getattr(args, "include_stationarity_rag", False):
        fit = out.get("fit") or {}
        stationarity = fit.get("stationarity")
        if stationarity:
            target_col = fit.get("target_col")
            target_row = next(
                (r for r in stationarity if r.get("variable") == target_col), None
            )
            target_stationary = bool(target_row and target_row.get("stationary_at_alpha"))
            non_stat = [
                r["variable"] for r in stationarity
                if r.get("stationary_at_alpha") is False
            ]
            if not target_stationary:
                rag = "Red"
            elif non_stat:
                rag = "Yellow"
            else:
                rag = "Green"
            out["stationarity_rag"] = {
                "rag": rag,
                "non_stationary_variables": non_stat,
                "caveat": "ADF는 단일 단위근 검정이며 표본 크기에 민감하다.",
            }
        else:
            out["stationarity_rag"] = {
                "rag": "Gray",
                "non_stationary_variables": [],
                "caveat": "stationarity 결과 없음 (skip 또는 실패).",
            }
    stat_rag = (out.get("stationarity_rag") or {}).get("rag")
    if n_vio > 0 or floor_violation or stat_rag == "Red":
        out["overall_rag"] = "Red"
    elif stat_rag == "Yellow":
        out["overall_rag"] = "Yellow"
    else:
        out["overall_rag"] = "Yellow"  # fit-metric RAG is computed by `report`
    out_path = args.out
    if not out_path and getattr(args, "out_pattern", None):
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        out_path = args.out_pattern.replace("{ts}", ts)
        out["resolved_out_path"] = out_path
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
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
            artifacts=[out_path] if out_path else [],
            test_results={},
            incomplete_items=[],
            log_dir=args.log_dir,
        )
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


def _render_report_markdown(report: dict, max_rows: Optional[int] = None) -> str:
    """Render a validate JSON report into the standard 9-section markdown."""
    from tools import markdown_renderers as mr
    from tools import validation_summary

    metrics = report.get("metrics", {}) or {}
    issues = report.get("issues", []) or []
    rag_states = [m.get("rag", "Gray") for m in metrics.values() if isinstance(m, dict)]
    if "Red" in rag_states:
        overall = "Red"
    elif "Yellow" in rag_states:
        overall = "Yellow"
    elif "Green" in rag_states and "Gray" not in rag_states:
        overall = "Green"
    elif rag_states:
        overall = "Yellow"
    else:
        overall = "Gray"

    summary_df = validation_summary.build_metric_summary(
        {k: v.get("value") if isinstance(v, dict) else v for k, v in metrics.items()}
    )
    issue_df = validation_summary.build_issue_table(issues)
    commentary = validation_summary.build_validation_commentary(summary_df, issue_df)

    schema = report.get("schema", {}).get("required_columns", {})
    schema_pass = "Pass" if schema.get("pass") else "Fail" if schema.get("missing") else "—"
    schema_note = f"missing={schema.get('missing', [])}" if schema else ""

    out = []
    out.append("## 1. 검증 요약")
    out.append(f"- 모형 유형: {report.get('model_type', '—')}")
    out.append(f"- 세그먼트: {report.get('segment', '—')}")
    out.append(f"- 데이터 경로: {report.get('data_path', '—')}")
    out.append(f"- 표본 수: {report.get('n_rows', '—')}")
    if "ead_normalizer" in report:
        out.append(f"- EAD 정규화: {report['ead_normalizer']}")
    out.append(f"- RAG 상태: **{overall}**")
    out.append("")
    out.append("## 2. 입력 데이터 점검")
    out.append("")
    out.append("| 항목 | 결과 | 비고 |")
    out.append("|---|---|---|")
    out.append(f"| 필수 컬럼 | {schema_pass} | {schema_note} |")
    out.append("")
    out.append("## 3. 주요 지표")
    out.append("")
    out.append(mr.render_metrics_table(metrics, max_rows=max_rows))
    out.append("## 4. 세부 분석")
    out.append("")
    out.append("- 본 섹션은 인간 검증자가 작성한다. CLI는 정량 결과만 채운다.")
    out.append("")
    out.append("## 5. 이상 징후")
    out.append("")
    out.append(mr.render_issue_table(issues, max_rows=max_rows))
    out.append("## 6. 한계")
    out.append("- `docs/limitation_and_risk.md` 참조.")
    out.append("- 본 자동 리포트는 정량 지표만 포함하며, 데이터 정의 일관성·시점 정합성·정책 임계값 적정성은 인간 검증자가 별도로 점검해야 한다.")
    out.append("")
    out.append("## 7. 검증 의견 초안")
    out.append("")
    out.append(commentary)
    out.append("")
    out.append("## 8. 추가 확인사항")
    out.append("- 데이터 담당: 입력 파일의 출처 및 추출 기준 확인")
    out.append("- 정책 담당: 적용 임계값 정책 확인")
    out.append("- 모형 개발부서: 이상 지표가 있을 경우 원인 분석 협의")
    out.append("")
    out.append("## 9. 감사추적")
    out.append(f"- 입력 파일: {report.get('data_path', '—')}")
    out.append("- 산출 도구: tools/* (정확한 함수 호출은 logs/ 참조)")
    out.append("- change_manifest 기록 여부: 별도 운영 절차에 따라 추가")
    out.append("")
    return "\n".join(out)


def _render_scenario_report_markdown(
    scenario_report: dict,
    policy: Optional[dict] = None,
    include_stationarity_rag: bool = False,
    max_rows: Optional[int] = None,
) -> str:
    """Render a validate-scenario JSON output as the standard 9-section markdown.

    When `policy` is provided, fit-metric RAG is computed for R², the
    maximum VIF, and the maximum condition index using policy thresholds.
    When `include_stationarity_rag` is True, an aggregate stationarity RAG
    is added (Green only when all variables are stationary at the alpha
    used during validate-scenario; sample-size sensitive).
    """
    from tools import markdown_renderers as mr

    fit = scenario_report.get("fit", {}) or {}
    severity = scenario_report.get("severity", {}) or {}
    floors = scenario_report.get("multiplier_floors", []) or []

    fit_rag: dict = {}
    stationarity_rag: Optional[dict] = None
    if policy:
        summary = fit.get("summary", {}) or {}
        r2 = summary.get("r_squared")
        if r2 is not None:
            fit_rag["r_squared"] = _rag_with_threshold(r2, policy, "r_squared")
        vif_rows = fit.get("vif", []) or []
        if vif_rows:
            try:
                vif_max = max(float(r["vif"]) for r in vif_rows
                              if r.get("vif") is not None and r.get("vif") != float("inf"))
            except ValueError:
                vif_max = None
            if vif_max is not None:
                fit_rag["vif_max"] = _rag_with_threshold(vif_max, policy, "vif")
        ci = (fit.get("condition_index") or {}).get("max_condition_index")
        if ci is not None:
            fit_rag["condition_index_max"] = _rag_with_threshold(ci, policy, "condition_index")

    if include_stationarity_rag:
        stationarity = fit.get("stationarity")
        if stationarity:
            target_col = fit.get("target_col")
            target_row = next(
                (r for r in stationarity if r.get("variable") == target_col), None
            )
            target_stationary = bool(target_row and target_row.get("stationary_at_alpha"))
            non_stat = [
                r["variable"]
                for r in stationarity
                if r.get("stationary_at_alpha") is False
            ]
            if not target_stationary:
                rag = "Red"
            elif non_stat:
                rag = "Yellow"
            else:
                rag = "Green"
            stationarity_rag = {
                "rag": rag,
                "non_stationary_variables": non_stat,
                "caveat": "ADF는 단일 단위근 검정이며 표본 크기에 민감하다.",
            }
        else:
            stationarity_rag = {
                "rag": "Gray",
                "non_stationary_variables": [],
                "caveat": "stationarity 결과 없음 (skip 또는 실패).",
            }
    summary = fit.get("summary", {}) or {}
    pvals = fit.get("pvalues", []) or []
    vif = fit.get("vif", []) or []

    n_vio = (severity.get("order") or {}).get("n_violation_total", 0)
    floor_violation = any(f.get("violation") for f in floors)
    fit_rag_states = [v.get("rag", "Gray") for v in fit_rag.values()]
    stat_state = stationarity_rag.get("rag") if stationarity_rag else None
    rag_states = list(fit_rag_states)
    if stat_state:
        rag_states.append(stat_state)
    if n_vio > 0 or floor_violation or "Red" in rag_states:
        overall = "Red"
    elif "Yellow" in rag_states:
        overall = "Yellow"
    elif rag_states and "Gray" not in rag_states:
        overall = "Green"
    else:
        overall = "Yellow"  # no fit-metric thresholds applied

    out: List[str] = []
    out.append("## 1. 검증 요약")
    out.append("- 모형 유형: PD multiplier / 시나리오 회귀")
    out.append(f"- 표본 수 (역사 데이터): {fit.get('n', '—')}")
    out.append(f"- 설명변수 수: {fit.get('k', '—')}")
    out.append(f"- 자기상관 검정 lag: {fit.get('autocorr_lags', '—')}")
    out.append(f"- 시나리오 서열 위반: {n_vio}")
    out.append(f"- Multiplier floor 위반: {sum(1 for f in floors if f.get('violation'))}/{len(floors)}")
    out.append(f"- RAG 상태: **{overall}**")
    out.append("")

    out.append("## 2. 입력 데이터 점검")
    stationarity = fit.get("stationarity")
    if stationarity:
        import pandas as pd

        df = pd.DataFrame(stationarity)
        out.append("**ADF stationarity**\n")
        cols = [c for c in df.columns if c in ("variable", "adf_stat", "pvalue", "stationary_at_alpha", "error")]
        out.append(mr.render_dataframe_markdown(
            df, columns=cols, aligns={"adf_stat": "right", "pvalue": "right"}, max_rows=max_rows
        ))
    else:
        out.append("- ADF stationarity 정보 없음 (skip 또는 실패).")
        out.append("")
    if stationarity_rag is not None:
        out.append("**Stationarity RAG (opt-in)**\n")
        out.append(f"- RAG: **{stationarity_rag['rag']}**")
        if stationarity_rag.get("non_stationary_variables"):
            out.append(f"- 비정상 변수: {', '.join(stationarity_rag['non_stationary_variables'])}")
        out.append(f"- caveat: {stationarity_rag['caveat']}")
        out.append("")

    out.append("## 3. 주요 지표")
    out.append("")
    if fit_rag:
        out.append("**적합도 RAG**\n")
        out.append(mr.render_metrics_table(fit_rag, max_rows=max_rows))
    out.append(mr.render_regression_summary(summary, pvals, vif))

    out.append("## 4. 세부 분석")
    out.append("")
    out.append(mr.render_scenario_severity(severity, floors, max_rows=max_rows))
    out.append("")
    out.append("**시계열 진단**\n")
    out.append(
        f"- Durbin–Watson: {fit.get('durbin_watson', '—')}\n"
        f"- Breusch–Godfrey: {json.dumps(fit.get('breusch_godfrey', {}), ensure_ascii=False)}\n"
        f"- ARCH: {json.dumps(fit.get('arch_test', {}), ensure_ascii=False)}\n"
        f"- Condition Index (max): {(fit.get('condition_index') or {}).get('max_condition_index', '—')}\n"
    )

    out.append("## 5. 이상 징후")
    issues = []
    if n_vio > 0:
        issues.append(
            {
                "issue": "scenario_order_violation",
                "severity": "Red",
                "evidence": f"n_violation_total={n_vio}",
                "candidate_cause": "시나리오 입력 또는 모형 비선형성",
                "next_action": "시나리오 입력값 재검토",
            }
        )
    for f in floors:
        if f.get("violation"):
            issues.append(
                {
                    "issue": "multiplier_floor_violation",
                    "severity": "Red",
                    "evidence": f"scenario={f.get('scenario_type')}, n_below={f.get('n_below_floor')}",
                    "candidate_cause": "floor 정책 미적용",
                    "next_action": "정책 확정 및 사후 검증",
                }
            )
    out.append(mr.render_issue_table(issues, max_rows=max_rows))

    out.append("## 6. 한계")
    out.append(
        "- 본 자동 리포트는 정량 진단만 포함하며, 시나리오 정의·정책 floor·구조적 모형 적합성은 인간 검증자가 별도로 점검한다.\n"
        "- ADF는 단일 단위근 검정이며, 다중 단위근·구조 변화 점검은 미포함.\n"
    )

    out.append("## 7. 검증 의견 초안")
    out.append("")
    out.append(
        "- 시나리오 회귀 진단 결과는 정량 결과에 근거한 초안이며, 모형 적합/부적합을 단정하지 않는다.\n"
        "- 데이터 정의, 시차 구조, floor 정책에 대한 인간 검증자의 확인이 필요하다.\n"
    )

    out.append("## 8. 추가 확인사항")
    out.append("- 정책 담당: scenario floor·서열 정책 확인")
    out.append("- 데이터 담당: 시계열 변환·정상성·시차 정합성 확인")
    out.append("- 모형 개발부서: 비유의 변수 / 부호 위배 / 다중공선성 대응")
    out.append("")

    out.append("## 9. 감사추적")
    out.append("- 산출 도구: tools/scenario_regression_pipeline.py + tools/markdown_renderers.py")
    out.append("- change_manifest 기록 여부: 별도 운영 절차에 따라 추가")
    out.append("")
    return "\n".join(out)


def cmd_report(args: argparse.Namespace) -> int:
    """Render a validate JSON report into a 9-section markdown file.

    Accepts either:
      --input <validate JSON>       (scoring/PD/LGD/EAD)
      --scenario-input <JSON>       (validate-scenario)

    With --scenario-input, the report attaches fit-metric RAG using the
    threshold policy. Use --threshold-overrides PATH to point at an
    alternative policy file (still schema-validated).
    """
    is_scenario = bool(args.scenario_input)
    if is_scenario:
        path = args.scenario_input
    elif args.input:
        path = args.input
    else:
        print(json.dumps({"error": "either --input or --scenario-input is required"}, ensure_ascii=False))
        return 4
    if not os.path.exists(path):
        print(json.dumps({"error": f"input not found: {path}"}, ensure_ascii=False))
        return 4
    with open(path, "r", encoding="utf-8") as f:
        report = json.load(f)
    max_rows = getattr(args, "max_rows", None)
    if max_rows is not None and max_rows < 1:
        print(json.dumps({"error": "max_rows_invalid", "detail": "must be >= 1"}, ensure_ascii=False))
        return 4
    if is_scenario:
        try:
            policy = _load_validated_policy(args.threshold_overrides)
        except (ValueError, FileNotFoundError) as e:
            print(json.dumps({"error": "policy_invalid", "detail": str(e)}, ensure_ascii=False))
            return 6
        md = _render_scenario_report_markdown(
            report,
            policy=policy,
            include_stationarity_rag=bool(getattr(args, "include_stationarity_rag", False)),
            max_rows=max_rows,
        )
    else:
        md = _render_report_markdown(report, max_rows=max_rows)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
    else:
        print(md)
    return 0


def _expand_aggregated_pd(
    df, count_col: str, default_col: str, pred_col: str, grade_col: Optional[str] = None
):
    """Expand pre-aggregated (count, defaults, predicted_pd) rows into
    per-observation rows of (pred_pd, default_flag, [grade]).
    """
    import pandas as pd

    rows = []
    for _, row in df.iterrows():
        n = int(row[count_col])
        d = int(row[default_col])
        if d > n:
            raise ValueError(f"defaults {d} > count {n}")
        p = float(row[pred_col])
        grade = row[grade_col] if grade_col and grade_col in df.columns else None
        for i in range(n):
            rec = {"pred_pd": p, "default_flag": 1 if i < d else 0}
            if grade is not None:
                rec["grade"] = grade
            rows.append(rec)
    return pd.DataFrame(rows)


def cmd_validate_pd_calibration(args: argparse.Namespace) -> int:
    """Run an integrated PD calibration validation.

    Computes Brier, PD bias, Hosmer-Lemeshow, Spiegelhalter Z, and a
    per-bucket binomial test. Accepts either:
      - row-level data (each row is an observation with pred_pd + default_flag)
      - pre-aggregated data (count, defaults, predicted_pd per bucket)
        when --count-col is supplied.
    """
    import pandas as pd

    from middleware import schema_guard
    from tools import (
        calibration_test,
        io_utils,
        metric_calibration,
    )

    df = io_utils.read_csv_safely(args.data)
    df = io_utils.normalize_column_names(df)

    if args.count_col:
        # Aggregated path
        required = [args.count_col, args.default_col, args.pred_col]
        sch = schema_guard.check_required_columns(df, required)
        if not sch["pass"]:
            print(json.dumps({"schema": sch, "issues": ["required columns missing"]},
                             ensure_ascii=False, indent=2))
            return 4
        expanded = _expand_aggregated_pd(
            df, args.count_col, args.default_col, args.pred_col, grade_col=args.bucket_col
        )
        pred_pd = expanded["pred_pd"]
        actual = expanded["default_flag"]
        bucket_series = expanded["grade"] if "grade" in expanded.columns else None
        n_rows = int(expanded.shape[0])
    else:
        required = [args.pred_col, args.default_col]
        sch = schema_guard.check_required_columns(df, required)
        if not sch["pass"]:
            print(json.dumps({"schema": sch, "issues": ["required columns missing"]},
                             ensure_ascii=False, indent=2))
            return 4
        pred_pd = df[args.pred_col]
        actual = df[args.default_col]
        bucket_series = df[args.bucket_col] if args.bucket_col and args.bucket_col in df.columns else None
        n_rows = int(df.shape[0])

    try:
        policy = _load_validated_policy()
    except ValueError as e:
        print(json.dumps({"error": "policy_invalid", "detail": str(e)}, ensure_ascii=False))
        return 6

    brier = metric_calibration.calculate_brier_score(actual.tolist(), pred_pd.tolist())
    bias_df = pd.DataFrame({"pred": pred_pd, "actual": actual})
    bias_info = metric_calibration.calculate_pd_bias(bias_df, "pred", "actual")
    hl = calibration_test.hosmer_lemeshow_test(
        actual.tolist(),
        pred_pd.tolist(),
        n_bins=int(args.hl_bins),
        min_per_bin=int(args.hl_min_per_bin) if args.hl_min_per_bin else None,
    )
    spiegel = calibration_test.spiegelhalter_z_test(actual.tolist(), pred_pd.tolist())

    binomial_records = None
    if bucket_series is not None:
        full = pd.DataFrame({"pred_pd": pred_pd, "default_flag": actual, "bucket": bucket_series})
        try:
            binomial_records = calibration_test.binomial_calibration_test(
                full, "pred_pd", "default_flag", "bucket", alpha=float(args.binomial_alpha)
            ).to_dict(orient="records")
        except Exception as e:
            binomial_records = [{"error": str(e)}]
    binomial_summary = None
    if binomial_records and "error" not in (binomial_records[0] or {}):
        n_buckets = len(binomial_records)
        n_rejecting = sum(1 for r in binomial_records if r.get("reject_h0"))
        binomial_summary = {
            "n_buckets": n_buckets,
            "n_buckets_rejecting_h0": n_rejecting,
            "alpha": float(args.binomial_alpha),
        }

    report = {
        "data_path": os.path.abspath(args.data),
        "n_rows": n_rows,
        "metrics": {
            "brier": _rag_with_threshold(brier, policy, "brier", segment=args.segment),
            "pd_bias": _rag_with_threshold(bias_info["abs_bias"], policy, "pd_bias", segment=args.segment),
        },
        "hosmer_lemeshow": hl,
        "spiegelhalter_z": spiegel,
        "binomial_per_bucket": binomial_records,
        "binomial_summary": binomial_summary,
        "bias_detail": bias_info,
    }
    if args.hl_rag:
        report["metrics"]["hl_pvalue"] = _rag_with_threshold(
            hl.get("pvalue"), policy, "hl_pvalue", segment=args.segment
        )
        report["metrics"]["spiegel_pvalue"] = _rag_with_threshold(
            spiegel.get("pvalue"), policy, "spiegel_pvalue", segment=args.segment
        )
        report["hl_rag_enabled"] = True
        report["hl_rag_caveat"] = (
            "HL/Spiegelhalter RAG는 표본 크기에 민감하며, 단독으로 적합/부적합을 단정하지 않는다."
        )
    if getattr(args, "decile_rag", False):
        from tools import decile_lift, target_validation

        try:
            # PD acts as a risk score: higher PD => higher default risk.
            # Cross-check with infer_score_direction and record the result.
            try:
                inferred = target_validation.infer_score_direction(
                    actual.tolist(), pred_pd.tolist()
                )
            except Exception as ie:
                inferred = {"error": str(ie)}
            report.setdefault("score_direction", inferred)
            lift = decile_lift.build_lift_table(
                actual.tolist(), pred_pd.tolist(), n_bins=10, higher_is_worse=True,
            )
            top = float(lift.iloc[0]["lift"]) if not lift.empty else None
            report["metrics"]["lift_top_decile"] = _rag_with_threshold(
                top, policy, "lift_top_decile", segment=args.segment
            )
        except Exception as e:
            report.setdefault("issues", []).append({
                "issue": "lift_top_decile_failed",
                "severity": "Gray",
                "evidence": str(e),
            })
    out_path = args.out
    if not out_path and getattr(args, "out_pattern", None):
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        out_path = args.out_pattern.replace("{ts}", ts)
        report["resolved_out_path"] = out_path
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    if getattr(args, "log_dir", None):
        from middleware import run_logger

        run_logger.write_run_log(
            request_summary="validate-pd-calibration",
            inputs=[args.data],
            functions_used=[
                "metric_calibration.calculate_brier_score",
                "metric_calibration.calculate_pd_bias",
                "calibration_test.hosmer_lemeshow_test",
                "calibration_test.spiegelhalter_z_test",
                "calibration_test.binomial_calibration_test",
            ],
            main_results={
                "brier": brier,
                "pd_bias": bias_info["abs_bias"],
                "hl_pvalue": hl.get("pvalue"),
                "spiegel_pvalue": spiegel.get("pvalue"),
            },
            errors=[],
            artifacts=[out_path] if out_path else [],
            test_results={},
            incomplete_items=[],
            log_dir=args.log_dir,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_policy_governance(args: argparse.Namespace) -> int:
    """Policy governance audit.

    Inspects:
      - change_manifest entries that reference threshold_policy.json
      - whether each entry has human_approval_required: true
      - the lock-file digest vs the current policy digest

    Exit codes:
      0 — all checks pass
      1 — soft warning (only when --exit-on-yellow): lock is missing or
          digest does not match, but governance approval is fine
      6 — manifest entries violate the approval rule
      7 — policy lock is missing or out of sync (only when --require-lock)
    """
    from middleware import policy_change_guard

    policy_path = args.policy_path or os.path.join(_PROJECT_ROOT, "harness", "threshold_policy.json")
    manifest_path = args.manifest_path or os.path.join(_PROJECT_ROOT, "harness", "change_manifest.json")
    lock_path = args.lock_path or os.path.join(_PROJECT_ROOT, "harness", "threshold_policy.lock.json")

    try:
        manifest = policy_change_guard.load_manifest(manifest_path)
    except FileNotFoundError as e:
        print(json.dumps({"error": "manifest_missing", "detail": str(e)}, ensure_ascii=False))
        return 6
    governance = policy_change_guard.policy_governance_status(manifest)
    lock_info = policy_change_guard.verify_against_lock(policy_path, lock_path)
    out = {
        "policy_path": policy_path,
        "manifest_path": manifest_path,
        "lock_path": lock_path,
        "manifest_governance": governance,
        "lock": lock_info,
    }
    if getattr(args, "json_only", False):
        print(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    if not governance["all_require_human_approval"]:
        return 6
    if args.require_lock and not lock_info["is_synced"]:
        return 7
    if getattr(args, "exit_on_yellow", False) and not lock_info["is_synced"]:
        return 1
    return 0


def cmd_policy_lock(args: argparse.Namespace) -> int:
    """Update or inspect the policy lock file.

    Default behavior: dry-run. Reports what would be written without
    modifying the lock file. Pass --confirm to actually write.

    Pre-checks (unless --skip-manifest-check is set):
      - the manifest contains an entry with the given change_id
      - that entry has component referencing threshold_policy.json
      - that entry has human_approval_required: true
    Failures exit with code 6.
    """
    from middleware import policy_change_guard

    policy_path = args.policy_path or os.path.join(_PROJECT_ROOT, "harness", "threshold_policy.json")
    lock_path = args.lock_path or os.path.join(_PROJECT_ROOT, "harness", "threshold_policy.lock.json")
    manifest_path = args.manifest_path or os.path.join(_PROJECT_ROOT, "harness", "change_manifest.json")

    try:
        current_digest = policy_change_guard.compute_policy_digest(policy_path)
    except FileNotFoundError as e:
        print(json.dumps({"error": "policy_missing", "detail": str(e)}, ensure_ascii=False))
        return 4
    if not args.change_id or not args.change_id.startswith("CHG-"):
        print(json.dumps({"error": "change_id_invalid",
                          "detail": "--change-id must be 'CHG-####'"}, ensure_ascii=False))
        return 4

    # Manifest pre-check
    if not args.skip_manifest_check:
        try:
            manifest = policy_change_guard.load_manifest(manifest_path)
        except FileNotFoundError as e:
            print(json.dumps({"error": "manifest_missing", "detail": str(e)}, ensure_ascii=False))
            return 6
        policy_entries = policy_change_guard.find_policy_change_entries(manifest)
        match = next((e for e in policy_entries if e.get("change_id") == args.change_id), None)
        if match is None:
            print(json.dumps({
                "error": "change_id_not_in_manifest",
                "detail": f"{args.change_id} not found among policy-change entries",
                "policy_entry_ids": [e.get("change_id") for e in policy_entries],
            }, ensure_ascii=False))
            return 6
        if not match.get("human_approval_required"):
            print(json.dumps({
                "error": "approval_missing",
                "detail": f"{args.change_id} does not have human_approval_required=true",
            }, ensure_ascii=False))
            return 6

    existing = policy_change_guard.load_lock(lock_path)
    plan = {
        "policy_path": os.path.abspath(policy_path),
        "lock_path": os.path.abspath(lock_path),
        "manifest_path": os.path.abspath(manifest_path),
        "current_digest": current_digest,
        "previous_lock": existing,
        "change_id": args.change_id,
        "manifest_check_skipped": bool(args.skip_manifest_check),
        "would_write": not args.confirm,
    }
    if args.confirm:
        rec = policy_change_guard.update_lock(policy_path, args.change_id, lock_path)
        plan["lock_written"] = rec
        plan["would_write"] = False
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    """Aggregate one-line RAG summary across multiple validate* JSON outputs.

    Reads every --input path and emits a JSON list of
        {path, kind, overall_rag, n_metrics, severity_violations}.
    Exit code is 0 unless --fail-on-red is set and any input is Red.
    """
    items = []
    worst = "Gray"
    rank = {"Gray": 0, "Green": 1, "Yellow": 2, "Red": 3}

    for path in args.input or []:
        if not os.path.exists(path):
            items.append({"path": path, "kind": "missing", "overall_rag": "Gray"})
            continue
        with open(path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                items.append({"path": path, "kind": "invalid_json",
                              "overall_rag": "Gray", "error": str(e)})
                continue
        if "fit" in data and "severity" in data:
            kind = "scenario"
            n_vio = ((data.get("severity") or {}).get("order") or {}).get("n_violation_total", 0)
            rag = data.get("overall_rag", "Yellow" if n_vio == 0 else "Red")
            items.append({
                "path": path,
                "kind": kind,
                "overall_rag": rag,
                "severity_violations": n_vio,
            })
        else:
            kind = "validate"
            metrics = data.get("metrics") or {}
            rag = data.get("overall_rag")
            if rag is None:
                states = [m.get("rag", "Gray") for m in metrics.values() if isinstance(m, dict)]
                if "Red" in states:
                    rag = "Red"
                elif "Yellow" in states:
                    rag = "Yellow"
                elif states and "Gray" not in states:
                    rag = "Green"
                else:
                    rag = "Gray"
            items.append({
                "path": path,
                "kind": kind,
                "overall_rag": rag,
                "n_metrics": len(metrics),
            })
        if rank[items[-1].get("overall_rag", "Gray")] > rank[worst]:
            worst = items[-1]["overall_rag"]

    out = {"items": items, "worst_rag": worst}
    if getattr(args, "out", None):
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    if getattr(args, "json_only", False):
        print(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    if getattr(args, "fail_on_red", False) and worst == "Red":
        return 6
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """Emit version metadata as JSON."""
    import platform
    import sys as _sys

    payload = {
        "package": "quant_validation_agent",
        "version": __version__,
        "python": _sys.version.split()[0],
        "platform": platform.platform(),
    }
    if getattr(args, "json_only", False):
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_docs_cli(args: argparse.Namespace) -> int:
    """Capture --help output for each subcommand into a markdown reference.

    Reads its own parser and emits a deterministic markdown file. Local-only;
    no network, no external API.
    """
    parser = build_parser()
    sub = next(
        (a for a in parser._actions if isinstance(a, argparse._SubParsersAction)),
        None,
    )
    if sub is None:
        print(json.dumps({"error": "no_subparsers"}, ensure_ascii=False))
        return 4
    lines: List[str] = []
    lines.append("# CLI Reference")
    lines.append("")
    lines.append("자동 생성 (`python -m quant_validation_agent docs-cli`). 직접 편집하지 말 것.")
    lines.append("")
    lines.append(f"버전: `{__version__}`")
    lines.append("")
    lines.append("## Top-level")
    lines.append("")
    lines.append("```")
    lines.append(parser.format_help().rstrip())
    lines.append("```")
    lines.append("")
    for name in sorted(sub.choices.keys()):
        sp = sub.choices[name]
        lines.append(f"## `{name}`")
        lines.append("")
        lines.append("```")
        lines.append(sp.format_help().rstrip())
        lines.append("```")
        lines.append("")
    md = "\n".join(lines) + "\n"
    out_path = args.out or os.path.join(_PROJECT_ROOT, "docs", "cli_reference.md")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(json.dumps({"out": out_path, "n_subcommands": len(sub.choices)},
                     ensure_ascii=False))
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
    from . import __version__ as _pkg_version

    parser = argparse.ArgumentParser(
        prog="quant_validation_agent",
        description="Quantitative validation agent — local-only CLI.",
    )
    parser.add_argument(
        "--version", action="version",
        version=f"quant_validation_agent {_pkg_version}",
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
    p_v.add_argument("--decile-rag", dest="decile_rag", action="store_true",
                     help="Also emit RAG for the top-decile lift (scoring/PD only).")
    p_v.add_argument("--ead-normalizer", dest="ead_normalizer", default=None,
                     choices=["mean_realized", "mean_predicted", "total_exposure"],
                     help="Override the EAD-error normalizer from threshold_policy.json.")
    p_v.add_argument("--segment-detail", dest="segment_detail", action="store_true",
                     help="LGD/EAD: emit per-segment MAE/RMSE/bias under report.segment_detail.")
    p_v.add_argument("--explain", dest="explain", action="store_true",
                     help="Also append a 9-section markdown report to stdout for human review.")
    p_v.add_argument("--segment-col", dest="segment_col", default=None,
                     help="Column to group by for --segment-detail.")
    p_v.add_argument("--out", help="Optional path to write the JSON report.")
    p_v.add_argument("--log-dir", dest="log_dir",
                     help="Optional directory to write a run-log JSON via middleware.run_logger.")
    p_v.set_defaults(func=cmd_validate)

    p_pg = sub.add_parser(
        "policy-governance",
        help="Audit threshold_policy governance: manifest approvals + lock digest.",
    )
    p_pg.add_argument("--policy-path", dest="policy_path", default=None)
    p_pg.add_argument("--manifest-path", dest="manifest_path", default=None)
    p_pg.add_argument("--lock-path", dest="lock_path", default=None)
    p_pg.add_argument("--require-lock", dest="require_lock", action="store_true",
                      help="Exit 7 when the lock is missing or drifted.")
    p_pg.add_argument("--json-only", dest="json_only", action="store_true",
                      help="Emit compact single-line JSON for jq pipelines.")
    p_pg.add_argument("--exit-on-yellow", dest="exit_on_yellow", action="store_true",
                      help="Exit 1 when the lock is missing/drifted, even though manifest "
                           "approvals are intact. Useful as a CI 'warning' gate that does "
                           "not block hard like --require-lock (which exits 7).")
    p_pg.set_defaults(func=cmd_policy_governance)

    p_pl = sub.add_parser(
        "policy-lock",
        help="Inspect or update threshold_policy.lock.json. Defaults to dry-run.",
    )
    p_pl.add_argument("--change-id", dest="change_id", required=True,
                      help="Approved change_id of the form CHG-####.")
    p_pl.add_argument("--confirm", dest="confirm", action="store_true",
                      help="Required to actually write the lock file.")
    p_pl.add_argument("--policy-path", dest="policy_path", default=None)
    p_pl.add_argument("--lock-path", dest="lock_path", default=None)
    p_pl.add_argument("--manifest-path", dest="manifest_path", default=None,
                      help="Path to change_manifest.json (defaults to harness/change_manifest.json).")
    p_pl.add_argument("--skip-manifest-check", dest="skip_manifest_check", action="store_true",
                      help="Skip the manifest pre-check (advanced; not recommended).")
    p_pl.set_defaults(func=cmd_policy_lock)

    p_sm = sub.add_parser(
        "summary",
        help="Aggregate one-line RAG summary across multiple validate* JSON outputs.",
    )
    p_sm.add_argument("--input", action="append", required=True,
                      help="Repeatable. JSON file produced by validate / validate-pd-calibration / validate-scenario.")
    p_sm.add_argument("--fail-on-red", dest="fail_on_red", action="store_true",
                      help="Exit 6 when any input is Red.")
    p_sm.add_argument("--json-only", dest="json_only", action="store_true",
                      help="Compact single-line JSON for jq pipelines.")
    p_sm.add_argument("--out", default=None,
                      help="Optional path to write the summary JSON.")
    p_sm.set_defaults(func=cmd_summary)

    p_ver = sub.add_parser(
        "version",
        help="Emit version metadata as JSON (package, version, python, platform).",
    )
    p_ver.add_argument("--json-only", dest="json_only", action="store_true",
                       help="Compact single-line JSON.")
    p_ver.set_defaults(func=cmd_version)

    p_dc = sub.add_parser(
        "docs-cli",
        help="Capture every subcommand --help into docs/cli_reference.md.",
    )
    p_dc.add_argument("--out", default=None,
                      help="Override output path (defaults to docs/cli_reference.md).")
    p_dc.set_defaults(func=cmd_docs_cli)

    p_n = sub.add_parser("note", help="Append a recurring-finding note.")
    p_n.add_argument("subaction", choices=["add"])
    p_n.add_argument("--text", required=True, help="The note text (single line).")
    p_n.add_argument("--model", help="Model name or type for the note.")
    p_n.add_argument("--path", help="Override target file path.")
    p_n.set_defaults(func=cmd_note)

    p_r = sub.add_parser(
        "report",
        help="Render a validate JSON report into the standard 9-section markdown.",
    )
    p_r.add_argument("--input", help="Path to a validate JSON report (scoring/PD/LGD/EAD).")
    p_r.add_argument("--scenario-input", dest="scenario_input",
                     help="Path to a validate-scenario JSON report.")
    p_r.add_argument("--threshold-overrides", dest="threshold_overrides", default=None,
                     help="Optional path to an alternative threshold_policy.json. "
                          "Always schema-validated before use.")
    p_r.add_argument("--include-stationarity-rag", dest="include_stationarity_rag",
                     action="store_true",
                     help="Opt-in: emit a stationarity RAG block (target stationary => Green; "
                          "any non-stationary feature => Yellow; non-stationary target => Red). "
                          "Sample-size sensitive — see CLAUDE.md limitations.")
    p_r.add_argument("--max-rows", dest="max_rows", default=None, type=int,
                     help="Truncate every table in the report to this many rows. "
                          "A note is appended indicating the number of truncated rows.")
    p_r.add_argument("--out", help="Optional path to write the markdown report.")
    p_r.set_defaults(func=cmd_report)

    p_pdc = sub.add_parser(
        "validate-pd-calibration",
        help="PD calibration validation (Brier, bias, Hosmer-Lemeshow, Spiegelhalter Z, binomial).",
    )
    p_pdc.add_argument("--data", required=True, help="Path to the CSV file.")
    p_pdc.add_argument("--pred-col", dest="pred_col", required=True,
                       help="Column with predicted PD (0-1).")
    p_pdc.add_argument("--default-col", dest="default_col", required=True,
                       help="Column with realized default count or 0/1 flag.")
    p_pdc.add_argument("--count-col", dest="count_col", default=None,
                       help="If set, treat data as pre-aggregated and expand to row level.")
    p_pdc.add_argument("--bucket-col", dest="bucket_col", default=None,
                       help="Optional bucket column for the per-bucket binomial test.")
    p_pdc.add_argument("--hl-bins", dest="hl_bins", default=10, type=int)
    p_pdc.add_argument("--hl-min-per-bin", dest="hl_min_per_bin", default=None, type=int,
                       help="If set, use greedy min-per-bin packing instead of quantile bins.")
    p_pdc.add_argument("--binomial-alpha", dest="binomial_alpha", default=0.05, type=float)
    p_pdc.add_argument("--hl-rag", dest="hl_rag", action="store_true",
                       help="Opt-in: also assign RAG to HL and Spiegelhalter p-values. "
                            "Output is sample-size sensitive; do not use alone for adequacy.")
    p_pdc.add_argument("--decile-rag", dest="decile_rag", action="store_true",
                       help="Opt-in: also emit RAG for the top-decile lift of pred_pd vs default.")
    p_pdc.add_argument("--segment", help="Segment label for threshold overrides.")
    p_pdc.add_argument("--out", help="Optional path to write the JSON report.")
    p_pdc.add_argument("--out-pattern", dest="out_pattern", default=None,
                       help="Optional path with strftime tokens; auto-replaces {ts} with the "
                            "current YYYYMMDD_HHMMSS_ffffff. Useful for accumulating reports.")
    p_pdc.add_argument("--log-dir", dest="log_dir",
                       help="Optional directory for run-log JSON via middleware.run_logger.")
    p_pdc.set_defaults(func=cmd_validate_pd_calibration)

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
    p_vs.add_argument("--autocorr-lags", dest="autocorr_lags", default=1, type=int,
                      help="Lags for Breusch-Godfrey and ARCH tests (default 1).")
    p_vs.add_argument("--skip-stationarity", dest="skip_stationarity",
                      action="store_true", help="Skip ADF stationarity check.")
    p_vs.add_argument("--stationarity-alpha", dest="stationarity_alpha",
                      default=0.05, type=float, help="Alpha for ADF test (default 0.05).")
    p_vs.add_argument("--max-predictions", dest="max_predictions", default=None, type=int,
                      help="Truncate the predictions list to this many rows in the output JSON. "
                           "Truncated count is reported under 'predictions_truncated'.")
    p_vs.add_argument("--include-stationarity-rag", dest="include_stationarity_rag",
                      action="store_true",
                      help="Opt-in: derive stationarity_rag from the ADF results and fold into "
                           "overall_rag. Sample-size sensitive; see CLAUDE.md limitations.")
    p_vs.add_argument("--out", help="Optional path to write the JSON report.")
    p_vs.add_argument("--out-pattern", dest="out_pattern", default=None,
                      help="Optional path with the literal token {ts}; auto-replaces with the "
                           "current YYYYMMDD_HHMMSS_ffffff timestamp.")
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
