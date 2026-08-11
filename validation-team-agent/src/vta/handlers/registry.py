"""vta.handlers.registry — workflow step handler 모음 (Phase 3 canonical).

``vta.core.workflow.WorkflowEngine`` 에 등록할 수 있는 handler 들. 각 handler 는
``(request, ctx) -> StepResult`` 시그니처를 따른다. handler 는 점검만 수행하고
검증 의견을 확정하지 않는다 (CLAUDE.md HITL).

사용:
    from vta.core.workflow import WorkflowEngine
    from vta.handlers.registry import register_default_handlers
    eng = WorkflowEngine()
    register_default_handlers(eng)
"""

from __future__ import annotations

from typing import Any, Mapping

from vta.core.workflow import StepResult, WorkflowContext, WorkflowEngine


def _has(req: Mapping[str, Any], *keys: str) -> bool:
    return any(req.get(k) is not None for k in keys)


def _bad_scalar(*values: Any) -> bool:
    """NaN / Inf / None 중 하나라도 있으면 True. 산식이 정의되지 않는 입력 점검."""
    import math

    for v in values:
        if v is None:
            return True
        try:
            f = float(v)
        except (TypeError, ValueError):
            return True
        if math.isnan(f) or math.isinf(f):
            return True
    return False


def _disc_skip_reason(df, score_col: str, target_col: str) -> str | None:
    """credit discrimination/calibration 사전 조건 점검.

    df 가 비었거나 score 에 NaN/Inf, target 에 단일 클래스만 있으면 산식이
    의미가 없거나 발산한다. 이 경우 handler 는 ``skipped`` 로 처리해 인간
    검증자가 입력 데이터 자체를 재확인하도록 한다 (HITL — fail 로 처리하면
    escalation 이 자동 발동되어 무의미한 MRMC 통지가 발생).
    """
    import numpy as np

    if len(df) == 0:
        return "df 비어있음"
    if score_col not in df.columns or target_col not in df.columns:
        return f"필수 컬럼 누락 (score_col={score_col}, target_col={target_col})"
    s = df[score_col].to_numpy()
    y = df[target_col].to_numpy()
    if np.isnan(s.astype(float, copy=False)).any():
        return "score 에 NaN 포함"
    if np.isinf(s.astype(float, copy=False)).any():
        return "score 에 Inf 포함"
    uniq = set(np.unique(y).tolist())
    if not uniq.issubset({0, 1}):
        return f"target 이 0/1 binary 가 아님 (관측={sorted(uniq)})"
    if len(uniq) < 2:
        return "target 단일 클래스 (KS/AUROC 정의 불가)"
    return None


# ---------- 신용 부문 (credit metrics) ----------

def credit_discrimination_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """KS / AUROC / Gini. df + score_col + target_col 필요."""

    from tools.metric_ks_auc import calculate_auc_gini, calculate_ks

    df = req.get("df")
    if df is None:
        return StepResult("3.disc", "skipped", {}, "df 미제공")
    skip = _disc_skip_reason(df, req["score_col"], req["target_col"])
    if skip:
        return StepResult("3.disc", "skipped", {}, skip)
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

    import numpy as np

    df = req.get("df")
    set_col = req.get("set_col")
    if df is None or not set_col:
        return StepResult("3.psi", "skipped", {}, "df/set_col 미제공")
    if set_col not in df.columns or req["score_col"] not in df.columns:
        return StepResult("3.psi", "skipped", {}, "set/score 컬럼 누락")
    dev = df.loc[df[set_col] == "dev", req["score_col"]].to_numpy()
    oot = df.loc[df[set_col] == "oot", req["score_col"]].to_numpy()
    if len(dev) < 100 or len(oot) < 100:
        return StepResult("3.psi", "skipped", {}, "dev/oot 표본 < 100")
    if np.isnan(dev.astype(float, copy=False)).any() or np.isnan(oot.astype(float, copy=False)).any():
        return StepResult("3.psi", "skipped", {}, "score NaN 포함 → PSI 정의 불가")
    if np.isinf(dev.astype(float, copy=False)).any() or np.isinf(oot.astype(float, copy=False)).any():
        return StepResult("3.psi", "skipped", {}, "score Inf 포함 → PSI 정의 불가")
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
    if len(df) == 0:
        return StepResult("3.cal", "skipped", {}, "df 비어있음")
    for col in (grade_col, pd_col, req["target_col"]):
        if col not in df.columns:
            return StepResult("3.cal", "skipped", {}, f"필수 컬럼 누락: {col}")
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
    # NaN/Inf 가 들어오면 산식이 정의되지 않거나 silent OK 로 통과 — 자본 점검은
    # 즉시 인간 검증자에게 입력 재확인 요청
    nan_fields = [
        k for k in ("capital_cet1", "capital_tier1", "capital_total",
                    "capital_leverage", "capital_ccyb", "capital_dsib")
        if req.get(k) is not None and _bad_scalar(req[k])
    ]
    if nan_fields:
        return StepResult(
            "3.capital", "skipped", {"bad_fields": nan_fields},
            f"자본 입력에 NaN/Inf: {nan_fields}",
        )
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
    # outflow=0 도 _has 로 점검 (기존 truthy 체크는 0 을 누락 → "유동성 미제공"
    # 으로 잘못 분류). NaN/Inf 도 skip.
    if _has(req, "liquidity_hqla") and req.get("liquidity_outflow") is not None:
        if _bad_scalar(req["liquidity_hqla"], req["liquidity_outflow"]):
            return StepResult("3.liquidity", "skipped", {},
                              "LCR 입력에 NaN/Inf")
        if float(req["liquidity_outflow"]) == 0.0:
            return StepResult("3.liquidity", "skipped", {},
                              "outflow=0 → LCR 정의 불가 (분모 0)")
        lcr = liquidity.check_lcr(req["liquidity_hqla"], req["liquidity_outflow"])
        out["lcr"] = lcr
        detail.append(f"LCR {lcr['ratio']:.3f} ({lcr['status']})")
        if lcr["status"] == "below_min":
            status = "fail"
        elif lcr["status"] == "warning" and status == "ok":
            status = "warning"
    if _has(req, "liquidity_asf") and req.get("liquidity_rsf") is not None:
        if _bad_scalar(req["liquidity_asf"], req["liquidity_rsf"]):
            return StepResult("3.liquidity", "skipped", {},
                              "NSFR 입력에 NaN/Inf")
        if float(req["liquidity_rsf"]) == 0.0:
            return StepResult("3.liquidity", "skipped", {},
                              "rsf=0 → NSFR 정의 불가 (분모 0)")
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

    exc = req.get("market_var_exceptions")
    if exc is None:
        return StepResult("3.market", "skipped", {}, "VaR exceptions 미제공")
    if _bad_scalar(exc) or int(exc) < 0:
        return StepResult("3.market", "skipped", {},
                          f"market_var_exceptions 비정상 ({exc})")
    tl = market.var_backtest_traffic_light(int(exc))
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
    if not eve:
        return StepResult("3.irrbb", "skipped", {},
                          "irrbb_delta_eve_by_scenario 비어있음")
    if _bad_scalar(tier1) or float(tier1) <= 0:
        return StepResult("3.irrbb", "skipped", {},
                          f"irrbb_tier1 비정상 ({tier1}); ratio 분모 정의 불가")
    if any(_bad_scalar(v) for v in eve.values()):
        return StepResult("3.irrbb", "skipped", {},
                          "ΔEVE scenario 값에 NaN/Inf")
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

    import math

    series = req.get("macro_series")
    if series is None:
        return StepResult("3.macro", "skipped", {}, "macro_series 미제공")
    series_list = list(series)
    if len(series_list) < 10:
        return StepResult("3.macro", "skipped",
                          {"n": len(series_list)},
                          f"macro_series 표본 {len(series_list)} < 10 (ADF 정의 불가)")
    if any(v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))
           for v in series_list):
        return StepResult("3.macro", "skipped", {},
                          "macro_series 에 NaN/Inf 포함")
    try:
        summary = stationarity_summary(series_list)
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
    if len(panel) == 0:
        return StepResult("3.weights", "skipped", {}, "panel 비어있음")
    period_col = req.get("scenario_weight_period_col", "period")
    scenario_col = req.get("scenario_weight_scenario_col", "scenario")
    weight_col = req.get("scenario_weight_value_col", "weight")
    missing = [c for c in (period_col, scenario_col, weight_col)
               if c not in panel.columns]
    if missing:
        return StepResult("3.weights", "skipped", {},
                          f"panel 컬럼 누락: {missing}")
    out = check_weight_panel(
        panel,
        period_col=period_col,
        scenario_col=scenario_col,
        weight_col=weight_col,
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
    if _bad_scalar(bi) or float(bi) < 0:
        return StepResult("3.operational", "skipped", {},
                          f"BI 비정상 ({bi}) — NaN/Inf/음수")
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
        if not inputs:
            return StepResult("3.cva", "skipped", {},
                              "cva_counterparty_inputs 비어있음")
        # cva.compute_ba_cva 계약: 각 counterparty 는 {"name", "scva"} 키
        for i, cp in enumerate(inputs):
            if not isinstance(cp, Mapping):
                return StepResult("3.cva", "skipped", {},
                                  f"counterparty[{i}] 가 dict 가 아님")
            if "scva" not in cp:
                return StepResult("3.cva", "skipped", {},
                                  f"counterparty[{i}] 필수 키 누락: ['scva']")
            if _bad_scalar(cp["scva"]):
                return StepResult("3.cva", "skipped", {},
                                  f"counterparty[{i}] scva 에 NaN/Inf")
            if float(cp["scva"]) < 0:
                return StepResult("3.cva", "skipped", {},
                                  f"counterparty[{i}] scva 음수")
        ba = cva.compute_ba_cva(inputs)
        out["ba_cva"] = ba["ba_cva"]
        detail.append(f"BA-CVA={ba['ba_cva']:.4f} (n={ba['n_counterparties']})")
    if book is not None:
        if _bad_scalar(book) or float(book) < 0:
            return StepResult("3.cva", "skipped", {},
                              f"cva_trading_book_size 비정상 ({book})")
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
    # NaN/Inf RC/PFE → EAD=NaN/Inf 가 자본 계산 오염 위험 (가장 치명적인 silent fail)
    if _bad_scalar(rc, pfe):
        return StepResult("3.ccr", "skipped", {},
                          f"RC/PFE 에 NaN/Inf (RC={rc}, PFE={pfe})")
    if float(rc) < 0 or float(pfe) < 0:
        return StepResult("3.ccr", "skipped", {},
                          f"RC/PFE 음수 (RC={rc}, PFE={pfe})")
    out = ccr.compute_ead(replacement_cost=rc, pfe=pfe)
    return StepResult(
        "3.ccr", "ok",
        {"alpha": out["alpha"], "ead": out["ead"]},
        f"EAD={out['ead']:.4f} (α={out['alpha']}, RC={rc}, PFE={pfe})",
    )


def concentration_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """신용집중리스크 (Basel LEX + 은행법 35조 한도 + HHI)."""
    from tools.risk_checks.concentration import check_concentration

    exposures = req.get("concentration_exposures")
    tier1 = req.get("concentration_tier1")
    if not exposures or tier1 is None:
        return StepResult("3.conc", "skipped", {}, "집중리스크 입력 미제공")
    if _bad_scalar(tier1) or float(tier1) <= 0:
        return StepResult("3.conc", "skipped", {}, f"tier1 비정상 ({tier1})")
    equity = req.get("concentration_equity")
    if equity is not None and (_bad_scalar(equity) or float(equity) <= 0):
        return StepResult("3.conc", "skipped", {}, f"equity 비정상 ({equity})")
    out = check_concentration(exposures, float(tier1), equity=equity)
    if not out["passed"]:
        status = "fail"
    elif out["hhi_band"] == "high":
        status = "warning"
    else:
        status = "ok"
    return StepResult(
        "3.conc", status,
        {"hhi": out["hhi"], "hhi_band": out["hhi_band"],
         "n_large": len(out["large_exposures"]),
         "n_breaches": len(out["limit_breaches"]),
         "breaches": out["limit_breaches"]},
        f"HHI={out['hhi']:.4f} ({out['hhi_band']}), "
        f"거액 {len(out['large_exposures'])}건, 한도위반 {len(out['limit_breaches'])}건",
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


# ---------- 1. 요청 재구성 ----------

def request_reconstruction_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """입력 request 의 메타데이터 정규화 + 가용 부문 카탈로그."""
    title = req.get("title", "(untitled)")
    domains = []
    if any(k in req for k in ("df", "score_col", "target_col")):
        domains.append("credit")
    if any(k.startswith("capital_") for k in req):
        domains.append("capital")
    if "scenario_weight_panel" in req:
        domains.append("ifrs9_weights")
    if "macro_series" in req or "macro_features" in req:
        domains.append("macro")
    if any(k in req for k in ("liquidity_hqla", "liquidity_asf")):
        domains.append("liquidity")
    if "market_var_exceptions" in req:
        domains.append("market")
    if "op_business_indicator_eur_bn" in req:
        domains.append("operational")
    if "irrbb_delta_eve_by_scenario" in req:
        domains.append("irrbb")
    if any(k in req for k in ("cva_counterparty_inputs", "cva_trading_book_size_eur_bn")):
        domains.append("cva")
    if any(k in req for k in ("ccr_rc", "ccr_pfe")):
        domains.append("ccr")
    return StepResult(
        "1.req", "ok",
        {"title": title, "n_keys": len(req.keys()), "domains": domains},
        f"title={title!r}, domains={domains}",
    )


# ---------- 2.0 스키마 점검 ----------

def schema_check_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    df = req.get("df")
    if df is None:
        return StepResult("2.schema", "ok", {}, "df 미제공 — skip")
    score_col = req.get("score_col")
    target_col = req.get("target_col")
    if not (score_col and target_col):
        return StepResult("2.schema", "warning", {}, "score/target col 미제공")
    from middleware.schema_guard import check_schema, credit_scoring_schema

    schema = credit_scoring_schema(
        score_col=score_col, target_col=target_col,
        set_col=req.get("set_col"), grade_col=req.get("grade_col"),
        pd_col=req.get("pd_col"), date_col=req.get("date_col"),
    )
    out = check_schema(df, schema)
    status = "ok" if out["passed"] else "fail"
    return StepResult(
        "2.schema", status,
        {"passed": out["passed"], "violations": len(out["violations"])},
        f"schema passed={out['passed']}, violations={len(out['violations'])}",
    )


# ---------- 2.1 데이터 안전 점검 ----------

def safety_check_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    df = req.get("df")
    if df is None:
        return StepResult("2.safety", "ok", {}, "df 미제공 — skip")
    from middleware.data_safety_guard import scan_dataframe

    out = scan_dataframe(df)
    status = "ok" if out["clean"] else "fail"
    return StepResult(
        "2.safety", status,
        {"clean": out["clean"], "n_findings": len(out["findings"])},
        f"safety clean={out['clean']}, findings={len(out['findings'])}",
    )


# ---------- 2.2 누수 점검 ----------

def leakage_check_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    features = req.get("feature_names")
    if not features:
        return StepResult("2.leakage", "ok", {}, "feature_names 미제공 — skip")
    from middleware.leakage_guard import check_leakage

    out = check_leakage(features, target_name=req.get("target_col", "target"))
    status = "ok" if out["passed"] else "fail"
    return StepResult(
        "2.leakage", status,
        {"passed": out["passed"], "leaked": len(out["leaked"])},
        f"leakage passed={out['passed']}, leaked={len(out['leaked'])}",
    )


# ---------- 2.3 기간 누락 점검 ----------

def date_coverage_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    df = req.get("df")
    date_col = req.get("date_col")
    if df is None or not date_col or date_col not in df.columns:
        return StepResult("2.date", "ok", {}, "date_col 미제공/부재 — skip")
    from tools.data_profile import check_date_coverage

    out = check_date_coverage(df, date_col)
    missing = out.get("missing_months", [])
    status = "ok" if not missing else "warning"
    return StepResult(
        "2.date", status,
        {"min_date": out["min_date"], "max_date": out["max_date"],
         "missing_months": len(missing)},
        f"date coverage {out['min_date']}~{out['max_date']}, missing={len(missing)}",
    )


# ---------- 2.4 중복 점검 ----------

def duplicates_check_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    df = req.get("df")
    key_cols = req.get("key_cols")
    if df is None or not key_cols:
        return StepResult("2.dup", "ok", {}, "key_cols 미제공 — skip")
    from tools.data_profile import check_duplicates

    out = check_duplicates(df, list(key_cols))
    status = "ok" if out["duplicate_count"] == 0 else "warning"
    return StepResult(
        "2.dup", status, {"duplicate_count": out["duplicate_count"]},
        f"duplicates={out['duplicate_count']}",
    )


# ---------- 6. 변경 이력 기록 (검토 권고) ----------

def audit_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """매니페스트 자동 promote 는 인간 권한이므로 권고만 한다."""
    fails = sum(1 for r in ctx.results.values() if r.status == "fail")
    warns = sum(1 for r in ctx.results.values() if r.status == "warning")
    status = "warning" if (fails or warns) else "ok"
    return StepResult(
        "6.audit", status,
        {"fails": fails, "warnings": warns,
         "manifest_action": "tools.manifest add (manual)"},
        f"manifest 기록 권고: fail={fails}, warning={warns}. "
        "`tools.manifest add` 로 CHG 항목 추가 후 검증팀장 승인 (HITL).",
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


def icaap_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """내부자본 적정성 (ICAAP / Pillar 2)."""
    from tools.risk_checks.icaap import check_internal_capital

    available = req.get("icaap_available_capital")
    required = req.get("icaap_required_by_risk")
    if available is None or not required:
        return StepResult("3.icaap", "skipped", {}, "ICAAP 입력 미제공")
    if _bad_scalar(available) or float(available) < 0:
        return StepResult("3.icaap", "skipped", {},
                          f"available_capital 비정상 ({available})")
    bad = [k for k, v in required.items() if _bad_scalar(v) or float(v) < 0]
    if bad:
        return StepResult("3.icaap", "skipped", {},
                          f"required_by_risk 비정상 항목: {bad}")
    out = check_internal_capital(
        float(available), required,
        diversification_benefit=float(req.get("icaap_diversification", 0.0)),
        post_stress_available=req.get("icaap_post_stress_available"),
    )
    if not out["passed"]:
        status = "fail"
    elif out["level"] == "warning" or out["post_stress_level"] == "warning" or out["findings"]:
        status = "warning"
    else:
        status = "ok"
    post = (f", post-stress {out['post_stress_ratio']:.3f}"
            if out["post_stress_ratio"] is not None else "")
    return StepResult(
        "3.icaap", status,
        {"ratio": out["ratio"], "post_stress_ratio": out["post_stress_ratio"],
         "post_stress_level": out["post_stress_level"],
         "required_total": out["required_total"],
         "risk_shares": out["risk_shares"],
         "missing_risk_types": out["missing_risk_types"],
         "findings": out["findings"]},
        f"내부자본비율 {out['ratio']:.3f} ({out['level']}){post}, "
        f"findings={len(out['findings'])}",
    )


def alm_handler(req: Mapping[str, Any], ctx: WorkflowContext) -> StepResult:
    """ALM 관리지표 (만기 갭 / 자금조달 집중 / 예대율)."""
    from tools.risk_checks.alm import (
        check_funding_concentration,
        check_loan_to_deposit,
        check_maturity_gap,
    )

    out: dict[str, Any] = {}
    detail = []
    status = "ok"

    def _worse(new: str) -> None:
        nonlocal status
        order = {"ok": 0, "warning": 1, "fail": 2}
        if order[new] > order[status]:
            status = new

    gaps = req.get("alm_gaps_by_bucket")
    total_assets = req.get("alm_total_assets")
    if gaps and total_assets is not None:
        if _bad_scalar(total_assets) or float(total_assets) <= 0:
            return StepResult("3.alm", "skipped", {},
                              f"total_assets 비정상 ({total_assets})")
        gap = check_maturity_gap(gaps, float(total_assets))
        out["maturity_gap"] = gap
        detail.append(f"만기갭 worst {gap['worst_ratio']:.1%}@{gap['worst_bucket']} ({gap['level']})")
        _worse("fail" if gap["level"] == "below_min"
               else "warning" if gap["level"] == "warning" else "ok")

    funding = req.get("alm_funding_by_provider")
    if funding:
        fc = check_funding_concentration(funding)
        out["funding_concentration"] = fc
        detail.append(f"조달집중 top1 {fc['top1_share']:.1%} ({fc['level']})")
        _worse(fc["level"] if fc["level"] in ("ok", "warning") else "ok")

    loans = req.get("alm_loans")
    deposits = req.get("alm_deposits")
    if loans is not None and deposits is not None:
        if _bad_scalar(loans, deposits) or float(deposits) <= 0:
            return StepResult("3.alm", "skipped", {}, "예대율 입력 비정상")
        ltd = check_loan_to_deposit(float(loans), float(deposits))
        out["loan_to_deposit"] = ltd
        detail.append(f"예대율 {ltd['ratio']:.1%} ({ltd['level']})")
        _worse("fail" if ltd["level"] == "below_min"
               else "warning" if ltd["level"] == "warning" else "ok")

    if not out:
        return StepResult("3.alm", "skipped", {}, "ALM 입력 미제공")
    return StepResult("3.alm", status, out, "; ".join(detail))


_DEFAULT = {
    "1.req": request_reconstruction_handler,
    "2.schema": schema_check_handler,
    "2.safety": safety_check_handler,
    "2.leakage": leakage_check_handler,
    "2.date": date_coverage_handler,
    "2.dup": duplicates_check_handler,
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
    "3.conc": concentration_handler,
    "3.icaap": icaap_handler,
    "3.alm": alm_handler,
    "4.report": report_handler,
    "5.complete": completeness_handler,
    "5.cite": citation_handler,
    "5.watermark": watermark_handler,
    "6.audit": audit_handler,
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
