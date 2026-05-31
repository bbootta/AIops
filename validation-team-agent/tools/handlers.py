"""Workflow step handler 모음.

``tools.workflow.WorkflowEngine`` 에 등록할 수 있는 handler 들. 각 handler 는
``(request, ctx) -> StepResult`` 시그니처를 따른다. handler 는 점검만 수행하고
검증 의견을 확정하지 않는다 (CLAUDE.md HITL).

사용:
    from tools.workflow import WorkflowEngine
    from tools.handlers import register_default_handlers
    eng = WorkflowEngine()
    register_default_handlers(eng)
"""

from __future__ import annotations

from typing import Any, Mapping

from tools.workflow import StepResult, WorkflowContext, WorkflowEngine


def _has(req: Mapping[str, Any], *keys: str) -> bool:
    return any(req.get(k) is not None for k in keys)


# ---------- 신용 부문 (credit metrics) ----------

def credit_discrimination_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """KS / AUROC / Gini. df + score_col + target_col 필요."""
    import numpy as np

    from tools.metric_ks_auc import calculate_auc_gini, calculate_ks

    df = req.get("df")
    if df is None:
        return StepResult("3.disc", "skipped", {}, "df 미제공")
    y = df[req["target_col"]].to_numpy()
    s = df[req["score_col"]].to_numpy()
    ks = calculate_ks(y, s)
    ag = calculate_auc_gini(y, s)
    # 참고 임계: KS >= 0.30, AUROC >= 0.70
    passed = ks["ks"] >= 0.30 and ag["auc"] >= 0.70
    return StepResult(
        "3.disc",
        "ok" if passed else "warning",
        {"ks": ks["ks"], "auc": ag["auc"], "gini": ag["gini"], "n": ks["n"]},
        f"KS={ks['ks']:.4f}, AUROC={ag['auc']:.4f}, Gini={ag['gini']:.4f}",
    )


def credit_psi_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """dev vs oot score PSI."""
    from tools.metric_psi import calculate_psi

    df = req.get("df")
    set_col = req.get("set_col")
    if df is None or not set_col:
        return StepResult("3.psi", "skipped", {}, "df/set_col 미제공")
    dev = df.loc[df[set_col] == "dev", req["score_col"]].to_numpy()
    oot = df.loc[df[set_col] == "oot", req["score_col"]].to_numpy()
    if len(dev) < 100 or len(oot) < 100:
        return StepResult("3.psi", "skipped", {}, "dev/oot 표본 < 100")
    out = calculate_psi(dev, oot, bins=10)
    psi = out["psi"]
    # < 0.10 안정 / 0.10~0.25 주의 / >= 0.25 불안정
    status = "ok" if psi < 0.10 else "warning" if psi < 0.25 else "fail"
    return StepResult(
        "3.psi", status, {"psi": psi}, f"PSI(dev vs oot)={psi:.4f}"
    )


def credit_calibration_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """등급별 PD vs 실측 부도율 binomial test."""
    from tools.binomial_calibration import calibration_test_per_grade

    df = req.get("df")
    grade_col = req.get("grade_col")
    pd_col = req.get("pd_col")
    if df is None or not grade_col or not pd_col:
        return StepResult("3.cal", "skipped", {}, "grade/pd 미제공")
    grades_input = []
    for grade, sub in df.groupby(grade_col):
        grades_input.append(
            {
                "grade": grade,
                "pd_estimated": float(sub[pd_col].mean()),
                "default_count": int(sub[req["target_col"]].sum()),
                "exposure_count": int(len(sub)),
            }
        )
    cal = calibration_test_per_grade(grades_input, alpha=0.05, multitest="holm")
    n_reject = int(cal["reject"].sum())
    status = "ok" if n_reject == 0 else "warning"
    return StepResult(
        "3.cal", status, {"n_reject": n_reject, "n_grades": len(cal)},
        f"calibration reject={n_reject}/{len(cal)}",
    )


def sample_size_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """표본 적정성."""
    from middleware.sample_size_guard import check_sample_size

    df = req.get("df")
    if df is None:
        return StepResult("2.sample", "skipped", {}, "df 미제공")
    target_col = req["target_col"]
    grade_col = req.get("grade_col")
    per_grade = (
        df[grade_col].value_counts().to_dict() if grade_col else None
    )
    out = check_sample_size(
        total=int(len(df)),
        default_count=int(df[target_col].sum()),
        per_grade_counts=per_grade,
    )
    return StepResult(
        "2.sample", "ok" if out["passed"] else "warning",
        {"passed": out["passed"], "violations": len(out["violations"])},
        f"sample passed={out['passed']}, violations={len(out['violations'])}",
    )


# ---------- 자본 부문 ----------

def capital_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """CET1/Tier1/BIS + buffer 충족 (감독시행세칙)."""
    from tools.risk_checks import capital

    if not _has(req, "capital_cet1", "capital_leverage"):
        return StepResult("3.capital", "skipped", {}, "자본 입력 미제공")
    out = {}
    detail = []
    status = "ok"
    if _has(req, "capital_cet1"):
        r = capital.check_ratios(
            cet1_ratio=req["capital_cet1"],
            tier1_ratio=req.get("capital_tier1", req["capital_cet1"]),
            total_ratio=req.get("capital_total", req["capital_cet1"]),
            countercyclical_buffer=req.get("capital_ccyb", 0.0),
            dsib_surcharge=req.get("capital_dsib", 0.0),
        )
        out["ratios"] = r
        if not r["passed"]:
            status = "fail"
            detail.append(f"violations={[v['metric'] for v in r['violations']]}")
        else:
            detail.append("ratios passed")
    if _has(req, "capital_leverage"):
        lev = capital.check_leverage(req["capital_leverage"])
        out["leverage"] = lev
        if not lev["passed"]:
            status = "fail"
            detail.append(f"leverage {lev['ratio']:.4f} < {lev['minimum']}")
        else:
            detail.append(f"leverage {lev['ratio']:.4f} ok")
    return StepResult("3.capital", status, out, "; ".join(detail))


# ---------- 유동성 부문 ----------

def liquidity_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """LCR / NSFR."""
    from tools.risk_checks import liquidity

    out = {}
    status = "ok"
    detail = []
    if _has(req, "liquidity_hqla") and req.get("liquidity_outflow"):
        lcr = liquidity.check_lcr(req["liquidity_hqla"], req["liquidity_outflow"])
        out["lcr"] = lcr
        detail.append(f"LCR {lcr['ratio']:.3f} ({lcr['status']})")
        if lcr["status"] == "below_min":
            status = "fail"
        elif lcr["status"] == "warning" and status == "ok":
            status = "warning"
    if _has(req, "liquidity_asf") and req.get("liquidity_rsf"):
        nsfr = liquidity.check_nsfr(req["liquidity_asf"], req["liquidity_rsf"])
        out["nsfr"] = nsfr
        detail.append(f"NSFR {nsfr['ratio']:.3f} ({nsfr['status']})")
        if nsfr["status"] == "below_min":
            status = "fail"
        elif nsfr["status"] == "warning" and status == "ok":
            status = "warning"
    if not out:
        return StepResult("3.liquidity", "skipped", {}, "유동성 입력 미제공")
    return StepResult("3.liquidity", status, out, "; ".join(detail))


# ---------- 시장 부문 ----------

def market_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """VaR backtest traffic light."""
    from tools.risk_checks import market

    if req.get("market_var_exceptions") is None:
        return StepResult("3.market", "skipped", {}, "VaR exceptions 미제공")
    tl = market.var_backtest_traffic_light(int(req["market_var_exceptions"]))
    status = {"green": "ok", "yellow": "warning", "red": "fail"}[tl["zone"]]
    return StepResult(
        "3.market", status, {"zone": tl["zone"], "exceptions": tl["exceptions"]},
        f"VaR backtest zone={tl['zone']} ({tl['exceptions']} exceptions)",
    )


# ---------- IRRBB 부문 ----------

def irrbb_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """ΔEVE outlier test."""
    from tools.risk_checks import irrbb

    eve = req.get("irrbb_delta_eve_by_scenario")
    tier1 = req.get("irrbb_tier1")
    if eve is None or tier1 is None:
        return StepResult("3.irrbb", "skipped", {}, "IRRBB 입력 미제공")
    out = irrbb.check_eve_outlier(eve, tier1)
    status = "fail" if out["outlier"] else "ok"
    return StepResult(
        "3.irrbb", status,
        {"outlier": out["outlier"], "ratio": out["ratio"], "worst": out["worst_scenario"]},
        f"ΔEVE outlier={out['outlier']} (ratio={out['ratio']:.3f}, worst={out['worst_scenario']})",
    )


# ---------- 거시 시계열 부문 ----------

def macro_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """거시 시계열 정상성 (ADF + KPSS 결합)."""
    from tools.regression_diagnostics import stationarity_summary

    series = req.get("macro_series")
    if series is None:
        return StepResult("3.macro", "skipped", {}, "macro_series 미제공")
    try:
        summary = stationarity_summary(series)
    except Exception as exc:  # noqa: BLE001
        return StepResult("3.macro", "fail", {}, f"stationarity 산출 실패: {exc}")
    label = summary["label"]
    status = "ok" if label == "stationary" else "warning"
    return StepResult(
        "3.macro", status, {"label": label, "n": len(list(series))},
        f"stationarity label={label}",
    )


# ---------- IFRS 9 시나리오 가중치 부문 ----------

def scenario_weights_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """IFRS 9 시나리오 가중치 panel sum=1 / non-neg 점검."""
    from tools.scenario_weights import check_weight_panel

    panel = req.get("scenario_weight_panel")
    if panel is None:
        return StepResult("3.weights", "skipped", {}, "panel 미제공")
    out = check_weight_panel(
        panel,
        period_col=req.get("scenario_weight_period_col", "period"),
        scenario_col=req.get("scenario_weight_scenario_col", "scenario"),
        weight_col=req.get("scenario_weight_value_col", "weight"),
    )
    n_fail = int((~out["passed"]).sum())
    status = "ok" if n_fail == 0 else "fail"
    return StepResult(
        "3.weights", status, {"n_periods": len(out), "n_fail": n_fail},
        f"weight panel periods={len(out)}, 위반={n_fail}",
    )


# ---------- 운영리스크 부문 (OPE25 SMA) ----------

def operational_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """BI → BIC → ORC (감독시행세칙 ILM=1)."""
    from tools.risk_checks import operational

    bi = req.get("op_business_indicator_eur_bn")
    if bi is None:
        return StepResult("3.operational", "skipped", {}, "BI 미제공")
    bic = operational.compute_bic(bi)
    orc = operational.compute_orc_domestic(bic["bic_eur_bn"])
    return StepResult(
        "3.operational", "ok",
        {"bi": bi, "bic_eur_bn": bic["bic_eur_bn"], "orc_eur_bn": orc["orc"]},
        f"BI={bi:.2f}bn → BIC={bic['bic_eur_bn']:.4f}bn → ORC(ILM=1)={orc['orc']:.4f}bn",
    )


# ---------- CVA 부문 (MAR50) ----------

def cva_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """BA-CVA 산식 + SA-CVA 의무 점검."""
    from tools.risk_checks import cva

    inputs = req.get("cva_counterparty_inputs")
    book = req.get("cva_trading_book_size_eur_bn")
    if inputs is None and book is None:
        return StepResult("3.cva", "skipped", {}, "CVA 입력 미제공")
    out = {}
    detail = []
    if inputs is not None:
        ba = cva.compute_ba_cva(inputs)
        out["ba_cva"] = ba["ba_cva"]
        detail.append(f"BA-CVA={ba['ba_cva']:.4f} (n={ba['n_counterparties']})")
    if book is not None:
        sa = cva.check_sa_cva_required(book)
        out["sa_cva_required"] = sa["sa_cva_required"]
        detail.append(f"SA-CVA required={sa['sa_cva_required']} (book={book:.1f}bn)")
    return StepResult("3.cva", "ok", out, "; ".join(detail))


# ---------- CCR 부문 (CRE52 SA-CCR) ----------

def ccr_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """EAD = α × (RC + PFE)."""
    from tools.risk_checks import ccr

    rc = req.get("ccr_rc")
    pfe = req.get("ccr_pfe")
    if rc is None or pfe is None:
        return StepResult("3.ccr", "skipped", {}, "RC/PFE 미제공")
    out = ccr.compute_ead(replacement_cost=rc, pfe=pfe)
    return StepResult(
        "3.ccr", "ok",
        {"alpha": out["alpha"], "ead": out["ead"]},
        f"EAD={out['ead']:.4f} (α={out['alpha']}, RC={rc}, PFE={pfe})",
    )


# ---------- 보고서 산출 / 점검 ----------

def report_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """이전 step 결과로 표준 10 섹션 보고서 초안 산출."""
    from tools.report_template import build_validation_report

    title = req.get("title", "Workflow Validation Report")
    results_lines = []
    anomalies = []
    for sid, r in ctx.results.items():
        if r.status in {"ok", "warning"} and r.detail:
            results_lines.append(f"- `{sid}` ({r.status}, 출처: `tools/handlers.py`): {r.detail}")
        if r.status in {"warning", "fail"}:
            anomalies.append(f"- `{sid}` ({r.status}, 출처: `tools/handlers.py`): {r.detail}")
    if not results_lines:
        results_lines.append(
            "- 등록 handler 결과 부재 (출처: `tools/workflow.WorkflowEngine`): 모든 step simulated"
        )
    if not anomalies:
        anomalies.append("- 자동 점검 한정 이상 징후 없음.")

    result_dict = {
        "title": title,
        "summary": (
            f"워크플로우 step {len(ctx.results)}개 실행. "
            f"fail={sum(1 for r in ctx.results.values() if r.status == 'fail')}, "
            f"warning={sum(1 for r in ctx.results.values() if r.status == 'warning')}."
        ),
        "purpose": "Dynamic workflow 자동 점검 보조 산출물.",
        "input_data": [
            f"request keys: {sorted(req.keys())}",
            "운영 데이터 / 외부 API 없음. 본 step 은 합성/입력 데이터 기반.",
        ],
        "method": [
            "Workflow: `tools/workflow.WorkflowEngine` (handler registry + 위상정렬)",
            "Handler: `tools/handlers.py`",
            "보고서: `tools/report_template.build_validation_report`",
        ],
        "results": "\n".join(results_lines),
        "anomalies": "\n".join(anomalies),
        "limitations": [
            "본 산출물은 자동 점검 한정. 정성 판단·MRMC 의견은 별도 인간 검증자 책임.",
            "참고 임계는 BCBS 표준 + 감독시행세칙 기준이며 모형 정책에 의해 강화 가능.",
        ],
        "draft_opinion": (
            "본 자동 산출물은 검증 보조 자료이며 의견 확정은 인간 검증자 + MRMC 검토 후에만 효력."
        ),
        "follow_ups": [
            "fail step 발생 시 escalation 보고서(`tools.escalation_report`) 참조",
            "운영 데이터 재실행 시 매니페스트 CHG 항목 추가",
        ],
        "audit_trail": (
            f"실행 step: {' → '.join(ctx.results.keys())}. "
            f"엔진: `tools/workflow.py`."
        ),
    }
    md = build_validation_report(result_dict)
    return StepResult(
        "4.report", "ok", {"report_md": md, "length": len(md)},
        f"보고서 초안 {len(md)} chars",
    )


def completeness_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    from middleware.output_completeness_guard import check_report

    rep = ctx.result("4.report")
    if rep is None or "report_md" not in (rep.outputs or {}):
        return StepResult("5.complete", "skipped", {}, "보고서 부재")
    out = check_report(rep.outputs["report_md"])
    status = "ok" if out["passed"] else "fail"
    return StepResult(
        "5.complete", status,
        {"missing": out["missing_sections"], "empty_critical": out["empty_critical"]},
        f"completeness passed={out['passed']}",
    )


def citation_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    from middleware.output_completeness_guard import check_numeric_citations

    rep = ctx.result("4.report")
    if rep is None or "report_md" not in (rep.outputs or {}):
        return StepResult("5.cite", "skipped", {}, "보고서 부재")
    out = check_numeric_citations(rep.outputs["report_md"])
    status = "ok" if out["passed"] else "warning"
    return StepResult(
        "5.cite", status,
        {"violations": len(out["violations"])},
        f"citation passed={out['passed']} (violations={len(out['violations'])})",
    )


def watermark_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    from middleware.draft_watermark_guard import check_watermarks

    rep = ctx.result("4.report")
    if rep is None or "report_md" not in (rep.outputs or {}):
        return StepResult("5.watermark", "skipped", {}, "보고서 부재")
    out = check_watermarks(rep.outputs["report_md"])
    status = "ok" if out["passed"] else "fail"
    return StepResult(
        "5.watermark", status,
        {"has_header": out["has_header"], "has_footer": out["has_footer"]},
        f"watermark passed={out['passed']}",
    )


# ---------- escalation ----------

def escalation_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """위험 부문 fail 시 동적 활성. fail 한 step 들을 수집해 보고."""
    failed = [sid for sid, r in ctx.results.items() if r.status == "fail"]
    return StepResult(
        "9.escalate", "ok",
        {"triggered_by": failed},
        f"escalation 권고: {failed} → 인간 검증자 / MRMC 보고 필요",
    )


_DEFAULT = {
    "2.sample": sample_size_handler,
    "3.disc": credit_discrimination_handler,
    "3.psi": credit_psi_handler,
    "3.cal": credit_calibration_handler,
    "3.macro": macro_handler,
    "3.weights": scenario_weights_handler,
    "3.capital": capital_handler,
    "3.liquidity": liquidity_handler,
    "3.market": market_handler,
    "3.operational": operational_handler,
    "3.irrbb": irrbb_handler,
    "3.cva": cva_handler,
    "3.ccr": ccr_handler,
    "4.report": report_handler,
    "5.complete": completeness_handler,
    "5.cite": citation_handler,
    "5.watermark": watermark_handler,
    "9.escalate": escalation_handler,
}


def register_default_handlers(engine: WorkflowEngine) -> list[str]:
    """엔진에 기본 handler 를 등록한다. 매트릭스에 없는 step 은 건너뛴다."""
    registered = []
    for sid, handler in _DEFAULT.items():
        if sid in engine.steps_by_id:
            engine.register(sid, handler)
            registered.append(sid)
    return registered
