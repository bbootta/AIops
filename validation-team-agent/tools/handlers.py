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
    "3.capital": capital_handler,
    "3.liquidity": liquidity_handler,
    "3.market": market_handler,
    "3.irrbb": irrbb_handler,
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
