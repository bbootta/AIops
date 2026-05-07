"""End-to-end thin entry point implementing orchestrator's 6-step routine.

이 모듈은 검증 의견을 자동 확정하지 않는다. 데이터 품질 점검, 변별력/안정성
지표 산출, 보고서 초안 작성까지만 수행하고, 모든 단계는
``middleware/run_logger.run_logger`` 컨텍스트로 감싸서 ``logs/run.jsonl`` 에
기록한다. 외부 제출본 확정과 모형 의견 확정은 인간 검증자의 책임이다.

CLI:
    python -m tools.run_validation --demo
    python -m tools.run_validation --csv path/to/file.csv \
        --score score --target target --set-col set --grade grade

CSV는 비식별 처리된 검증용 추출 파일을 전제로 한다. 운영 DB 직접 접속은
지원하지 않는다.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from middleware.data_safety_guard import scan_dataframe
from middleware.draft_watermark_guard import check_watermarks
from middleware.leakage_guard import check_leakage
from middleware.output_completeness_guard import check_numeric_citations, check_report
from middleware.run_logger import run_logger
from middleware.sample_size_guard import check_sample_size
from middleware.schema_guard import check_schema, credit_scoring_schema
from tools.binomial_calibration import calibration_test_per_grade
from tools.data_profile import check_date_coverage, check_duplicates, check_missing
from tools.metric_ks_auc import calculate_auc_gini, calculate_ks
from tools.metric_psi import calculate_psi
from tools.report_template import build_validation_report


@dataclass
class ValidationRequest:
    title: str
    df: pd.DataFrame
    score_col: str
    target_col: str
    set_col: str | None = None
    grade_col: str | None = None
    pd_col: str | None = None
    date_col: str | None = None
    key_cols: tuple[str, ...] = ()
    feature_names: tuple[str, ...] = ()
    calibration_alpha: float = 0.05


def _split_dev_oot(df: pd.DataFrame, set_col: str | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not set_col or set_col not in df.columns:
        n = len(df)
        cut = max(1, n // 2)
        return df.iloc[:cut].copy(), df.iloc[cut:].copy()
    dev = df.loc[df[set_col].astype(str).str.lower() == "dev"].copy()
    oot = df.loc[df[set_col].astype(str).str.lower().isin({"oot", "mon"})].copy()
    return dev, oot


def _step_input_check(req: ValidationRequest) -> dict:
    df = req.df
    findings: dict[str, Any] = {}
    findings["schema"] = check_schema(
        df,
        credit_scoring_schema(
            score_col=req.score_col,
            target_col=req.target_col,
            set_col=req.set_col,
            grade_col=req.grade_col,
            pd_col=req.pd_col,
            date_col=req.date_col,
        ),
    )
    findings["safety"] = scan_dataframe(df)
    if req.feature_names:
        findings["leakage"] = check_leakage(req.feature_names, target_name=req.target_col)
    if req.key_cols:
        findings["duplicates"] = check_duplicates(df, list(req.key_cols))
    if req.date_col and req.date_col in df.columns:
        findings["date_coverage"] = check_date_coverage(df, req.date_col)
    findings["missing"] = check_missing(df).to_dict(orient="records")
    return findings


def _step_quant(req: ValidationRequest) -> dict:
    df = req.df.dropna(subset=[req.score_col, req.target_col]).copy()
    y = df[req.target_col].astype(int).values
    s = df[req.score_col].astype(float).values

    sample = check_sample_size(
        total=int(len(df)),
        default_count=int(y.sum()),
        per_grade_counts=(
            df[req.grade_col].value_counts().to_dict() if req.grade_col else None
        ),
    )

    out: dict[str, Any] = {"sample_size": sample}
    if len(np.unique(y)) >= 2:
        out["ks"] = calculate_ks(y, s)
        out["auc_gini"] = calculate_auc_gini(y, s)
    else:
        out["ks"] = None
        out["auc_gini"] = None

    dev_df, oot_df = _split_dev_oot(df, req.set_col)
    if len(dev_df) >= 100 and len(oot_df) >= 100:
        out["psi_dev_oot"] = calculate_psi(
            dev_df[req.score_col].values, oot_df[req.score_col].values, bins=10
        )
    else:
        out["psi_dev_oot"] = None

    if req.grade_col and req.pd_col and req.grade_col in df.columns and req.pd_col in df.columns:
        grades_input = []
        for grade, sub in df.groupby(req.grade_col):
            grades_input.append(
                {
                    "grade": grade,
                    "pd_estimated": float(sub[req.pd_col].mean()),
                    "default_count": int(sub[req.target_col].sum()),
                    "exposure_count": int(len(sub)),
                }
            )
        out["calibration"] = calibration_test_per_grade(
            grades_input, alpha=req.calibration_alpha, multitest="holm"
        )
    else:
        out["calibration"] = None
    return out


def _format_results(quant: dict) -> str:
    lines = []
    if quant.get("ks") is not None:
        ks = quant["ks"]
        lines.append(
            f"- 변별력 (출처: `tools/metric_ks_auc.calculate_ks`): "
            f"KS = {ks['ks']:.4f}, n = {ks['n']}, n_bad = {ks['n_bad']}"
        )
    if quant.get("auc_gini") is not None:
        ag = quant["auc_gini"]
        lines.append(
            f"- AUROC / Gini (출처: `tools/metric_ks_auc.calculate_auc_gini`): "
            f"AUC = {ag['auc']:.4f}, Gini = {ag['gini']:.4f}"
        )
    if quant.get("psi_dev_oot") is not None:
        p = quant["psi_dev_oot"]
        lines.append(
            f"- 안정성 (출처: `tools/metric_psi.calculate_psi`): "
            f"PSI(dev vs oot) = {p['psi']:.4f}, n_expected = {p['n_expected']}, n_actual = {p['n_actual']}"
        )
    sample = quant["sample_size"]
    lines.append(
        f"- 표본 적정성 (출처: `middleware/sample_size_guard.check_sample_size`): "
        f"passed = {sample['passed']}, violations = {len(sample['violations'])}"
    )
    cal = quant.get("calibration")
    if cal is not None:
        n_reject = int(cal["reject"].sum())
        worst = cal.loc[cal["p_value_adj"].idxmin()]
        lines.append(
            f"- 등급별 캘리브레이션 (출처: `tools/binomial_calibration.calibration_test_per_grade`): "
            f"reject = {n_reject}/{len(cal)}, worst_grade = {worst['grade']!r}, "
            f"p_value_adj_min = {worst['p_value_adj']:.4f}"
        )
    if not lines:
        lines.append("(산출 가능한 결과 없음)")
    return "\n".join(lines)


def _build_report(req: ValidationRequest, input_findings: dict, quant: dict) -> str:
    psi_dev = quant.get("psi_dev_oot")
    psi_text = f"{psi_dev['psi']:.4f}" if psi_dev else "n/a"
    sample = quant["sample_size"]
    summary = (
        f"표본 {sample.get('thresholds', {}).get('min_total', '?')} 임계 기준 적정성 "
        f"passed = {sample['passed']}. 개발/운영 PSI = {psi_text}."
    )
    result_dict = {
        "title": req.title,
        "summary": summary,
        "purpose": "정기 검증 보조 산출물 (자동 생성).",
        "input_data": [
            f"입력 행 수: {len(req.df)}",
            f"score: `{req.score_col}` / target: `{req.target_col}` "
            f"/ set: `{req.set_col or '미지정'}` / grade: `{req.grade_col or '미지정'}`",
        ],
        "method": [
            "변별력: `tools/metric_ks_auc.calculate_ks`, `calculate_auc_gini`",
            "안정성: `tools/metric_psi.calculate_psi` (개발 vs 운영)",
            "표본 적정성: `middleware/sample_size_guard.check_sample_size`",
            "민감정보/누수: `middleware/data_safety_guard`, `middleware/leakage_guard`",
        ],
        "results": _format_results(quant),
        "anomalies": (
            "- 표본 적정성 위반 항목 존재. 출처: `middleware/sample_size_guard.check_sample_size`"
            if not sample["passed"]
            else "- 표본 적정성 통과. 출처: `middleware/sample_size_guard.check_sample_size`"
        ),
        "limitations": [
            "본 산출물은 자동 생성 초안이며, 의견 확정은 인간 검증자의 책임.",
            "표본 부족 / 신뢰구간은 별도 산출 필요.",
            "PSI bin은 분위수 기반 default(10). 정책 bin이 필요하면 별도 산출.",
        ],
        "draft_opinion": (
            "본 자동 산출물은 정량 지표만 포함하며 정성적 적정성·내부통제·문서화 "
            "검토가 추가되어야 검증 의견 초안으로 사용 가능. 인간 검증자의 검토와 "
            "승인 후에만 효력을 가짐."
        ),
        "follow_ups": [
            "민감정보 / 누수 점검 결과 재확인",
            "등급별 캘리브레이션 (`tools/binomial_calibration`) 산출",
            "거시 변수가 있는 경우 정상성 검정 (`tools/regression_diagnostics.stationarity_summary`)",
        ],
        "audit_trail": (
            f"실행 로그: `logs/run.jsonl`. 변경 이력: `harness/change_manifest.json`. "
            f"입력 결측 컬럼 수: {sum(1 for r in input_findings['missing'] if r['missing_count'] > 0)}."
        ),
    }
    return build_validation_report(result_dict)


def run(req: ValidationRequest, log_dir: str | Path | None = None) -> dict:
    """6단계 루틴을 실행하고 보고서/점검 결과를 반환한다."""
    with run_logger(
        "run_validation.run",
        inputs={"title": req.title, "n_rows": int(len(req.df))},
        log_dir=log_dir,
    ) as ctx:
        ctx["inputs"]["score_col"] = req.score_col
        ctx["inputs"]["target_col"] = req.target_col
        input_findings = _step_input_check(req)
        quant = _step_quant(req)
        report_md = _build_report(req, input_findings, quant)
        completeness = check_report(report_md)
        citations = check_numeric_citations(report_md)
        watermarks = check_watermarks(report_md)
        ctx["result_summary"] = {
            "completeness_passed": completeness["passed"],
            "citations_passed": citations["passed"],
            "watermarks_passed": watermarks["passed"],
            "sample_passed": quant["sample_size"]["passed"],
        }
        return {
            "report_md": report_md,
            "input_findings": input_findings,
            "quant": quant,
            "completeness": completeness,
            "citations": citations,
            "watermarks": watermarks,
        }


def _load_request_from_csv(args: argparse.Namespace) -> ValidationRequest:
    df = pd.read_csv(args.csv)
    return ValidationRequest(
        title=args.title,
        df=df,
        score_col=args.score,
        target_col=args.target,
        set_col=args.set_col,
        grade_col=args.grade,
        date_col=args.date_col,
    )


def _build_demo_request() -> ValidationRequest:
    rng = np.random.default_rng(42)
    n_dev, n_oot = 1000, 600
    score_dev = np.concatenate([rng.normal(0, 1, n_dev // 2), rng.normal(2, 1, n_dev // 2)])
    target_dev = np.concatenate([np.zeros(n_dev // 2), np.ones(n_dev // 2)]).astype(int)
    score_oot = np.concatenate([rng.normal(0.3, 1, n_oot // 2), rng.normal(2.2, 1, n_oot // 2)])
    target_oot = np.concatenate([np.zeros(n_oot // 2), np.ones(n_oot // 2)]).astype(int)
    grades = rng.choice(list("ABCDE"), size=n_dev + n_oot)
    pd_map = {"A": 0.01, "B": 0.03, "C": 0.07, "D": 0.15, "E": 0.30}
    df = pd.DataFrame(
        {
            "score": np.concatenate([score_dev, score_oot]),
            "target": np.concatenate([target_dev, target_oot]),
            "set": ["dev"] * n_dev + ["oot"] * n_oot,
            "grade": grades,
            "pd": np.array([pd_map[g] for g in grades]),
        }
    )
    return ValidationRequest(
        title="Demo Validation Report",
        df=df,
        score_col="score",
        target_col="target",
        set_col="set",
        grade_col="grade",
        pd_col="pd",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="validation-team-agent thin runner")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--csv", type=str, default=None)
    parser.add_argument("--title", type=str, default="Validation Report")
    parser.add_argument("--score", type=str, default="score")
    parser.add_argument("--target", type=str, default="target")
    parser.add_argument("--set-col", dest="set_col", type=str, default=None)
    parser.add_argument("--grade", type=str, default=None)
    parser.add_argument("--date-col", dest="date_col", type=str, default=None)
    parser.add_argument("--out", type=str, default=None, help="report output md path")
    args = parser.parse_args(argv)

    if not args.demo and not args.csv:
        parser.error("either --demo or --csv must be provided")

    req = _build_demo_request() if args.demo else _load_request_from_csv(args)
    out = run(req)
    if args.out:
        Path(args.out).write_text(out["report_md"], encoding="utf-8")
    else:
        sys.stdout.write(out["report_md"])
        sys.stdout.write("\n")
    return 0 if out["completeness"]["passed"] and out["citations"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
