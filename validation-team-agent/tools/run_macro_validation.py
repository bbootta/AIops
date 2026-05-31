"""거시 시나리오 / 예측 모형 전용 thin runner.

신용평가용 ``run_validation.py`` 와 분리되어 있으며, 거시 변수 시계열에 대한
정상성 (ADF/KPSS), 다중공선성 (VIF), 잔차 진단 (Durbin-Watson 등)을 통합 산출
하고 표준 10개 섹션 보고서 초안을 생성한다.

CLI:
    python -m tools.run_macro_validation --demo
    python -m tools.run_macro_validation --csv path/to/series.csv \
        --target target_macro --features gdp_growth,unemployment --period period
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from middleware.run_logger import log_step, run_logger
from middleware.schema_guard import check_schema, macro_schema
from tools.scenario_weights import check_weight_panel
from tools.regression_diagnostics import (
    calculate_vif,
    check_residual_basic,
    stationarity_summary,
)
from tools.report_template import build_validation_report


@dataclass
class MacroValidationRequest:
    title: str
    df: pd.DataFrame
    target_col: str
    feature_cols: Sequence[str]
    period_col: str | None = None
    alpha: float = 0.05
    extra_notes: list[str] = field(default_factory=list)
    scenario_weight_panel: pd.DataFrame | None = None
    scenario_weight_period_col: str = "period"
    scenario_weight_scenario_col: str = "scenario"
    scenario_weight_value_col: str = "weight"


def _series_diagnostics(req: MacroValidationRequest) -> dict:
    """target + 각 feature에 대해 정상성 라벨을 산출."""
    cols = [req.target_col, *req.feature_cols]
    result: dict[str, dict] = {}
    for col in cols:
        if col not in req.df.columns:
            raise KeyError(f"column missing: {col}")
        series = req.df[col].dropna().astype(float).values
        if series.size < 10:
            result[col] = {"label": "too_short", "n": int(series.size)}
            continue
        summary = stationarity_summary(series, alpha=req.alpha)
        result[col] = {
            "label": summary["label"],
            "n": int(series.size),
            "adf_p": summary["adf"]["p_value"],
            "kpss_p": summary["kpss"]["p_value"],
        }
    return result


def _vif_table(req: MacroValidationRequest) -> pd.DataFrame | None:
    feats = list(req.feature_cols)
    if len(feats) < 2:
        return None
    X = req.df[feats].dropna().astype(float)
    if X.shape[0] <= X.shape[1]:
        return None
    return calculate_vif(X)


def _ols_residual_diag(req: MacroValidationRequest) -> dict | None:
    """간단한 OLS 적합 후 잔차 진단을 반환한다."""
    import statsmodels.api as sm

    feats = list(req.feature_cols)
    sub = req.df[[req.target_col, *feats]].dropna().astype(float)
    if len(sub) <= len(feats) + 1:
        return None
    X = sm.add_constant(sub[feats], has_constant="add")
    model = sm.OLS(sub[req.target_col].values, X).fit()
    diag = check_residual_basic(model)
    diag["rsquared"] = float(model.rsquared)
    diag["nobs"] = int(model.nobs)
    return diag


def _format_results(diagnostics: dict) -> str:
    lines: list[str] = []
    src = "출처: `tools/regression_diagnostics.stationarity_summary`"
    lines.append(f"- 시계열 정상성 ({src}):")
    for col, info in diagnostics["series"].items():
        if info["label"] == "too_short":
            lines.append(f"    - `{col}` ({src}): 표본 부족 (n = {info['n']})")
        else:
            lines.append(
                f"    - `{col}` ({src}): label = {info['label']}, "
                f"adf_p = {info['adf_p']:.4f}, kpss_p = {info['kpss_p']:.4f}, n = {info['n']}"
            )
    vif = diagnostics.get("vif")
    if vif is not None:
        max_vif = float(vif["vif"].max())
        lines.append(
            f"- 다중공선성 (출처: `tools/regression_diagnostics.calculate_vif`): "
            f"max_vif = {max_vif:.3f}, 변수 수 = {len(vif)}"
        )
    res = diagnostics.get("residual")
    if res is not None:
        lines.append(
            f"- OLS 잔차 진단 (출처: `tools/regression_diagnostics.check_residual_basic`): "
            f"R² = {res['rsquared']:.4f}, DW = {res['durbin_watson']:.3f}, "
            f"n = {res['nobs']}, skew = {res['skew']:.3f}"
        )
    sw = diagnostics.get("scenario_weights")
    if sw is not None:
        n_fail = int((~sw["passed"]).sum())
        lines.append(
            f"- 시나리오 가중치 (출처: `tools/scenario_weights.check_weight_panel`): "
            f"period {len(sw)}개 / 위반 {n_fail}건"
        )
    return "\n".join(lines) if lines else "(산출 가능한 결과 없음)"


def _build_report(req: MacroValidationRequest, diagnostics: dict) -> str:
    series = diagnostics["series"]
    nonstationary = [c for c, v in series.items() if v["label"] in {"non_stationary", "inconclusive_likely_non_stationary"}]
    summary = (
        f"target = `{req.target_col}` / features = {len(req.feature_cols)}개. "
        f"비정상 가능 변수 수 = {len(nonstationary)}."
    )
    anomalies: list[str] = []
    if nonstationary:
        anomalies.append(
            f"- 비정상 가능 변수 (출처: `tools/regression_diagnostics.stationarity_summary`): "
            f"{', '.join('`' + c + '`' for c in nonstationary)}"
        )
    vif = diagnostics.get("vif")
    if vif is not None and (vif["vif"] > 10).any():
        flagged = vif.loc[vif["vif"] > 10, "variable"].tolist()
        anomalies.append(
            f"- 다중공선성 의심 (출처: `tools/regression_diagnostics.calculate_vif`): "
            f"VIF > 10 변수 = {', '.join('`' + v + '`' for v in flagged)}"
        )
    if not anomalies:
        anomalies.append("- 검출된 이상 징후 없음 (자동 점검 한정).")

    result_dict = {
        "title": req.title,
        "summary": summary,
        "purpose": "거시 변수 / forward-looking 모형 검증 보조 산출물 (자동 생성).",
        "input_data": [
            f"입력 행 수: {len(req.df)}",
            f"target: `{req.target_col}` / features: {', '.join('`' + c + '`' for c in req.feature_cols)}",
            f"period: `{req.period_col or '미지정'}`",
        ],
        "method": [
            "정상성: `tools/regression_diagnostics.adf_test`, `kpss_test`, `stationarity_summary`",
            "다중공선성: `tools/regression_diagnostics.calculate_vif`",
            "OLS 잔차: `tools/regression_diagnostics.check_residual_basic`",
        ],
        "results": _format_results(diagnostics),
        "anomalies": "\n".join(anomalies),
        "limitations": [
            "본 산출물은 OLS / 단변량 검정 한정. 비선형/구조변화/패널 모형은 별도 도구 필요.",
            "표본 길이가 한 사이클 미만일 경우 일반화 제한.",
            *req.extra_notes,
        ],
        "draft_opinion": (
            "본 자동 산출물은 정량 진단만 포함하며 시나리오 정합성·도메인 합리성 "
            "검토가 추가되어야 검증 의견 초안으로 사용 가능. 인간 검증자의 검토와 "
            "승인 후에만 효력을 가짐."
        ),
        "follow_ups": [
            "비정상 변수의 변환 (차분/로그) 사유 문서화",
            "구조변화 검정 (Chow / Bai-Perron 등) 별도 산출",
            "표본 외 검증 (rolling / expanding window)",
        ],
        "audit_trail": (
            "실행 로그: `logs/run.jsonl`. 변경 이력: `harness/change_manifest.json`."
        ),
    }
    return build_validation_report(result_dict)


def run(req: MacroValidationRequest, log_dir: str | Path | None = None) -> dict:
    """거시 모형 검증을 실행하고 보고서를 반환한다."""
    with run_logger(
        "run_macro_validation.run",
        inputs={"title": req.title, "n_rows": int(len(req.df)), "n_features": len(req.feature_cols)},
        log_dir=log_dir,
    ) as ctx:
        log_step("1.req", component="subagents/orchestrator.md", log_dir=log_dir)
        schema_result = check_schema(
            req.df,
            macro_schema(
                target_col=req.target_col,
                feature_cols=req.feature_cols,
                period_col=req.period_col,
            ),
        )
        log_step("2.schema", component="middleware/schema_guard.check_schema", log_dir=log_dir)
        log_step("3.macro", component="tools/regression_diagnostics.stationarity_summary", log_dir=log_dir)
        weights_table = None
        if req.scenario_weight_panel is not None:
            weights_table = check_weight_panel(
                req.scenario_weight_panel,
                period_col=req.scenario_weight_period_col,
                scenario_col=req.scenario_weight_scenario_col,
                weight_col=req.scenario_weight_value_col,
            )
            log_step(
                "3.weights",
                component="tools/scenario_weights.check_weight_panel",
                log_dir=log_dir,
            )
        diagnostics = {
            "schema": schema_result,
            "series": _series_diagnostics(req),
            "vif": _vif_table(req),
            "residual": _ols_residual_diag(req),
            "scenario_weights": weights_table,
        }
        report_md = _build_report(req, diagnostics)
        log_step("4.report", component="tools/report_template.build_validation_report", log_dir=log_dir)
        from middleware.draft_watermark_guard import check_watermarks
        from middleware.output_completeness_guard import check_numeric_citations, check_report

        completeness = check_report(report_md)
        log_step("5.complete", component="middleware/output_completeness_guard.check_report", log_dir=log_dir)
        citations = check_numeric_citations(report_md)
        log_step("5.cite", component="middleware/output_completeness_guard.check_numeric_citations", log_dir=log_dir)
        watermarks = check_watermarks(report_md)
        log_step("5.watermark", component="middleware/draft_watermark_guard.check_watermarks", log_dir=log_dir)
        log_step(
            "6.audit",
            component="harness/change_manifest.json (via tools/manifest.py)",
            status="skipped",
            log_dir=log_dir,
            extra={"reason": "runner does not write manifest entries; human-driven step"},
        )
        ctx["result_summary"] = {
            "completeness_passed": completeness["passed"],
            "citations_passed": citations["passed"],
            "watermarks_passed": watermarks["passed"],
            "n_nonstationary": sum(
                1 for v in diagnostics["series"].values()
                if v["label"] in {"non_stationary", "inconclusive_likely_non_stationary"}
            ),
        }
        return {
            "report_md": report_md,
            "diagnostics": diagnostics,
            "completeness": completeness,
            "citations": citations,
            "watermarks": watermarks,
        }


def _build_demo_request() -> MacroValidationRequest:
    rng = np.random.default_rng(7)
    n = 120
    gdp = rng.normal(0.5, 0.3, n)
    unemp = 4.0 + 0.2 * np.cumsum(rng.normal(0, 1, n)) * 0.05
    rate = rng.normal(2.0, 0.4, n)
    target = 0.6 * gdp - 0.4 * (unemp - 4.0) + rng.normal(0, 0.2, n)
    df = pd.DataFrame(
        {
            "period": pd.period_range("2010-01", periods=n, freq="M").astype(str),
            "gdp_growth": gdp,
            "unemployment": unemp,
            "interest_rate": rate,
            "target_macro": target,
        }
    )
    return MacroValidationRequest(
        title="Demo Macro Validation Report",
        df=df,
        target_col="target_macro",
        feature_cols=["gdp_growth", "unemployment", "interest_rate"],
        period_col="period",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="validation-team-agent macro runner")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--csv", type=str, default=None)
    parser.add_argument("--title", type=str, default="Macro Validation Report")
    parser.add_argument("--target", type=str, default="target_macro")
    parser.add_argument("--features", type=str, default=None, help="comma-separated feature columns")
    parser.add_argument("--period", type=str, default=None)
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args(argv)

    if not args.demo and not args.csv:
        parser.error("either --demo or --csv must be provided")

    if args.demo:
        req = _build_demo_request()
    else:
        if not args.features:
            parser.error("--features is required with --csv")
        df = pd.read_csv(args.csv)
        req = MacroValidationRequest(
            title=args.title,
            df=df,
            target_col=args.target,
            feature_cols=[c.strip() for c in args.features.split(",") if c.strip()],
            period_col=args.period,
        )

    out = run(req)
    if args.out:
        Path(args.out).write_text(out["report_md"], encoding="utf-8")
    else:
        sys.stdout.write(out["report_md"])
        sys.stdout.write("\n")
    return 0 if out["completeness"]["passed"] and out["citations"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
