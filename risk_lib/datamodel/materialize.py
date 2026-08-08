"""PipelineResult → 정규 도메인 테이블 실체화 엔진 (R2~R9).

카탈로그가 스펙만 있으면 산출값과 스키마가 갈라진다. 이 엔진은 실제 산출
결과를 정규 테이블로 채우고, 그 결과가 스펙 검증과 참조무결성을 통과하는지
테스트로 고정한다 — 데이터모델이 살아 있는 계약이 되게 하는 두 번째 장치.

각 부문 함수는 (result, portfolio, base_tables) → dict[table_name, DataFrame].
base_tables는 RDM 분해 결과이며, FK가 실제로 연결되는지 확인하는 데 쓰인다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from risk_lib.datamodel import catalog as cat


def _asof(result) -> str:
    return result.meta.get("asof", "1970-01-01")



def fitted_portfolio(portfolio: pd.DataFrame) -> pd.DataFrame:
    """파이프라인이 실제로 산출에 쓴 포트폴리오를 재현한다.

    run_pipeline은 `_fit_segment_pd`로 세그먼트별 PD 모형을 적합하고 그 결과를
    **포트폴리오에 덮어쓴 뒤** RWA·ECL을 계산한다. 따라서 입력 포트폴리오로
    직접 재계산하면 공표값과 어긋난다(IRB RWA 약 12%). 대사를 하려면 같은
    변환을 거쳐야 하며, 이 함수가 그 사실을 코드로 명시한다.

    `_fit_segment_pd`는 결정론적이므로 같은 입력에서 같은 결과를 낸다.
    """
    from risk_lib.pipeline import _fill_sa_parameters, _fit_segment_pd
    fitted, *_ = _fit_segment_pd(portfolio.copy())
    # SA북 파라미터 충전까지가 '실제로 쓴' 포트폴리오다 — ECL이 전 포트폴리오
    # 대상이 되면서(재구조), 충전 전 본으로 재계산하면 SA북 충당금 30.2억이
    # 다시 사라진다.
    return _fill_sa_parameters(fitted)


# ---------------------------------------------------------------- R2 · CRM

def materialize_crm(result, portfolio, base: dict[str, pd.DataFrame]
                    ) -> dict[str, pd.DataFrame]:
    """모형 인벤토리 · 등급/PD 이력 · 성능 지표."""
    asof = _asof(result)
    import dataclasses
    from risk_lib.model_inventory import build_standard_inventory

    # 모형 인벤토리 — 세그먼트는 모형명에서 유도한다(원본에 세그먼트 필드 없음).
    # 자산군 세그먼트는 **신용 모형에만** 있는 축이다. 시장 VaR·IRRBB·LCR·
    # 기후·RAF 에 "corporate"를 붙이면 그 모형이 기업 자산군에 적용된다고
    # 주장하는 것이 되는데, 사실이 아니라 기본값일 뿐이다. 없는 축은 비운다.
    def _segment(name: str, domain: str) -> str | None:
        if domain != "신용":
            return None
        if "주담대" in name:
            return "residential_mortgage"
        if "가계" in name:
            return "retail_other"
        return "corporate"

    # 모형 원장은 **전 도메인**이다 — PD/LGD 만이 아니라 VaR·IRRBB·LCR·
    # 스트레스·XVA·기후·RAF 까지. 인벤토리에 이미 있던 목적·의존성·한계·
    # 경과일을 원장에서 잘라내면 모형 거버넌스 화면이 그것을 다시 만들게 된다.
    def _domain(mid: str) -> str:
        head = mid.split("_")[0]
        return {"PD": "신용", "LGD": "신용", "ECL": "신용", "VINTAGE": "신용",
                "VAR": "시장", "XVA": "시장", "IRRBB": "ALM", "LCR": "ALM",
                "STRESS": "위기상황", "CLIMATE": "기후", "RAF": "전사",
                }.get(head, "기타")

    inv = build_standard_inventory()
    model = pd.DataFrame([{
        "model_id": e.model_id,
        "model_name": e.name,
        "domain": _domain(e.model_id),
        "segment": _segment(e.name, _domain(e.model_id)),
        "purpose": e.purpose,
        "tier": int(e.tier),
        "status": e.status,
        "last_validation": e.last_validation,
        "next_due": e.next_due,
        # days_overdue·is_overdue 는 기준일을 받는 **메서드**다. 인자 없이
        # 참조하면 bound method 가 그대로 담겨 int() 에서 터진다 — 여기서
        # 터지는 편이 낫다. 조용히 문자열로 담겼으면 화면에 함수 주소가 뜬다.
        "days_overdue": int(e.days_overdue(asof)),
        "is_overdue": bool(e.is_overdue(asof)),
        "dependencies": " · ".join(e.dependencies) if e.dependencies else "—",
        "known_limitations": (" · ".join(e.known_limitations)
                              if e.known_limitations else "—"),
        "owner": e.owner,
    } for e in inv])
    model = model[model["status"].isin(cat.MODEL_STATUS)].reset_index(drop=True)

    # 등급·PD 이력 — 차주 단위로 집약 (익스포저 다건 → 대표 PD는 EAD 가중).
    # 적합 후 PD를 써야 보고서의 등급 분포와 일치한다.
    p = fitted_portfolio(portfolio)
    p["_w"] = p["ead"].astype(float)
    g = (p.dropna(subset=["pd"])
           .assign(_pw=lambda d: d["pd"] * d["_w"])
           .groupby("obligor_id", as_index=False)
           .agg(pd_w=("_pw", "sum"), w=("_w", "sum")))
    g["pd"] = (g["pd_w"] / g["w"]).clip(0.0, 1.0)
    from risk_lib.models.rating import pd_to_rating
    # pd_to_rating은 스칼라 API — 벡터를 넘기면 조용히 틀리는 게 아니라
    # 예외가 나므로 명시적으로 매핑한다.
    # `.grade`를 꺼내지 않으면 RatingGrade 데이터클래스가 그대로 열에 들어간다.
    # 카탈로그는 이 열을 string·allowed=GRADES로 선언하는데 그 상태로 통과했다.
    # 저장소의 다른 호출부 8곳은 전부 `.grade`를 꺼낸다 — 여기만 빠져 있었다.
    g["grade"] = [pd_to_rating(float(x)).grade for x in g["pd"]]
    rating = pd.DataFrame({
        "obligor_id": g["obligor_id"],
        "asof": asof,
        "model_id": np.where(
            g["obligor_id"].str.contains("CORP"), "PD_CORP",
            np.where(g["obligor_id"].str.contains("MORT"),
                     "PD_MORTGAGE", "PD_RETAIL")),
        "pd": g["pd"],
        "grade": g["grade"],
        "override_flag": 0,
    })
    known = set(model["model_id"])
    rating["model_id"] = rating["model_id"].where(
        rating["model_id"].isin(known), list(known)[0] if known else "PD_CORP")

    # 성능 지표 — 파이프라인의 pd_metrics
    perf_rows = []
    for seg, m in (result.pd_metrics or {}).items():
        if seg not in cat.ASSET_CLASSES:
            continue
        perf_rows.append({
            "model_id": ("PD_CORP" if seg == "corporate" else
                         "PD_MORTGAGE" if seg == "residential_mortgage"
                         else "PD_RETAIL"),
            "segment": seg, "asof": asof,
            "gini": float(m.get("gini", 0.0)),
            "ks": float(m.get("ks")) if m.get("ks") is not None else None,
            "psi": float(m.get("psi")) if m.get("psi") is not None else None,
            "n_obs": int(m.get("n", 0)),
        })
    perf = pd.DataFrame(perf_rows, columns=cat.MODEL_PERFORMANCE.column_names)
    if not perf.empty:
        perf = perf[perf["model_id"].isin(known)].reset_index(drop=True)
    # None을 섞으면 컬럼이 object dtype이 되어 이후 수치 연산이 조용히 깨진다.
    for c in ("gini", "ks", "psi"):
        perf[c] = pd.to_numeric(perf[c], errors="coerce").astype("float64")
    perf["n_obs"] = pd.to_numeric(perf["n_obs"], errors="coerce").fillna(0).astype("int64")
    return {"crm_model": model, "crm_rating": rating, "crm_performance": perf}


# ---------------------------------------------------------------- R3 · RWA

def materialize_rwa(result, portfolio, base: dict[str, pd.DataFrame]
                    ) -> dict[str, pd.DataFrame]:
    """RWA 산출 결과 · CRM 배분."""
    asof = _asof(result)
    from risk_lib.capital.rwa_sa import compute_rwa_sa
    from risk_lib.capital.rwa_irb import compute_rwa_irb

    # 책 분할은 **파이프라인과 동일 기준**(자산군만)을 쓴다. 여기서 조건을 하나만
    # 달리해도 테이블 합계가 공표 RWA와 어긋나 대사가 깨진다 (RDM-005).
    #
    # 주의: 파이프라인은 RWA 산출 전에 apply_crm을 호출하지 않는다. 따라서 이
    # 테이블도 CRM 적용 전 EAD를 쓴다 — 담보 효과는 rwa_crm_allocation에
    # "적용했다면 어땠을지"로만 남으며, 실제 RWA에는 반영돼 있지 않다.
    # 데이터모델이 임의로 CRM을 적용하면 보고서에 서로 다른 RWA가 두 개 생긴다.
    p = fitted_portfolio(portfolio)
    sa_book = p[p["asset_class"].isin(["sovereign", "bank"])].copy()
    irb_book = p[p["asset_class"].isin(
        ["corporate", "retail_other", "residential_mortgage"])].copy()

    frames = []
    if len(sa_book):
        sa = compute_rwa_sa(sa_book)
        frames.append(pd.DataFrame({
            "exposure_id": sa["exposure_id"], "asof": asof, "approach": "SA",
            "ead_final": sa["ead"].astype(float),
            "pd": np.nan, "lgd": np.nan,
            "risk_weight": (sa["rwa"] / sa["ead"].replace(0, np.nan)).fillna(0.0),
            "rwa": sa["rwa"].astype(float), "expected_loss": np.nan,
        }))
    if len(irb_book):
        irb = compute_rwa_irb(irb_book)
        el = (np.nan_to_num(irb_book["pd"].to_numpy(dtype=float))
              * np.nan_to_num(irb_book["lgd"].to_numpy(dtype=float))
              * irb_book["ead"].to_numpy(dtype=float))
        frames.append(pd.DataFrame({
            "exposure_id": irb["exposure_id"], "asof": asof, "approach": "AIRB",
            "ead_final": irb["ead"].astype(float),
            "pd": np.clip(irb_book["pd"].to_numpy(dtype=float), 0.0, 1.0),
            "lgd": np.clip(irb_book["lgd"].to_numpy(dtype=float), 0.0, 1.0),
            "risk_weight": (irb["rwa"] / irb["ead"].replace(0, np.nan)).fillna(0.0),
            "rwa": irb["rwa"].astype(float),
            "expected_loss": np.clip(el, 0.0, None),
        }))
    rwa = (pd.concat(frames, ignore_index=True) if frames
           else pd.DataFrame(columns=cat.RWA_RESULT.column_names))

    # CRM 배분 — 담보 원장과 조인
    coll = base["rdm_collateral"]
    ex = base["rdm_exposure"].set_index("exposure_id")["ead"]
    eligible = coll["market_value"] * (1.0 - coll["haircut"])
    gross = coll["exposure_id"].map(ex).astype(float)
    allocated = np.minimum(eligible, gross)
    alloc = pd.DataFrame({
        "exposure_id": coll["exposure_id"], "collateral_id": coll["collateral_id"],
        "asof": asof,
        "eligible_value": eligible.astype(float),
        "allocated": allocated.astype(float),
        "secured_ead": allocated.astype(float),
        "unsecured_ead": np.maximum(gross - allocated, 0.0),
    })
    return {"rwa_result": rwa, "rwa_crm_allocation": alloc}


# ---------------------------------------------------------------- R4 · ECL

def materialize_ecl(result, portfolio, base: dict[str, pd.DataFrame]
                    ) -> dict[str, pd.DataFrame]:
    """ECL 산출 결과 · 거시 시나리오."""
    asof = _asof(result)
    from risk_lib.provisioning.ecl import compute_ecl

    # ECL 원장은 **전 포트폴리오**다 (재구조 — ECL이 신용 EAD보다 먼저,
    # SA북 포함). IRB만 재계산하면 파이프라인 공표 총액과 원장이 갈라진다.
    book = fitted_portfolio(portfolio)
    e = compute_ecl(book)
    dpd = book["dpd"].to_numpy(dtype=int)
    stage = e["stage"].to_numpy(dtype=int)
    trigger = np.where(stage == 3, "abs_pd",
                       np.where(dpd >= 30, "dpd30",
                                np.where(stage == 2, "pd_ratio", "none")))
    ead = e["ead"].to_numpy(dtype=float)
    ecl = e["ecl"].to_numpy(dtype=float)
    ecl_df = pd.DataFrame({
        "exposure_id": e["exposure_id"], "asof": asof,
        "stage": stage, "sicr_trigger": trigger,
        "pd_pit": np.nan_to_num(np.clip(book["pd"].to_numpy(dtype=float), 0.0, 1.0)),
        "lgd": np.nan_to_num(np.clip(book["lgd"].to_numpy(dtype=float), 0.0, 1.0)),
        "ead": ead, "ecl": np.clip(ecl, 0.0, None),
        "coverage_ratio": np.clip(np.divide(ecl, ead, out=np.zeros_like(ecl),
                                            where=ead > 0), 0.0, 1.0),
    })

    # 거시 시나리오 — 가중치 합이 1이 되도록 정규화 (편향 방지)
    quarters = result.meta.get("quarters", [])
    scen_w = {"baseline": 0.50, "downside": 0.30, "severe": 0.20}
    rows = []
    for name, w in scen_w.items():
        for i, q in enumerate(quarters):
            shock = {"baseline": 0.0, "downside": -0.02, "severe": -0.05}[name]
            decay = 1.0 - 0.06 * i
            rows.append({
                "scenario": name, "quarter": q, "weight": w,
                "gdp_growth": float(np.clip(0.022 + shock * decay, -0.5, 0.5)),
                "unemployment": float(np.clip(
                    0.035 - shock * 0.8 * decay, 0.0, 0.5)),
                "pd_multiplier": float(np.exp(max(0.0, -shock * decay) * 10)),
            })
    macro = pd.DataFrame(rows, columns=cat.MACRO_SCENARIO.column_names)
    return {"ecl_result": ecl_df, "ecl_macro_scenario": macro}



# ---------------------------------------------------------------- R5 · ST/CAP

def materialize_stress_capital(result, portfolio, base) -> dict[str, pd.DataFrame]:
    """스트레스 자본경로 · 자본 스택."""
    asof = _asof(result)
    sp = result.stress_path
    path = pd.DataFrame({
        "scenario": sp["scenario"], "quarter": sp["quarter"],
        "severity": sp["severity"].astype(float).abs(),
        "rwa_total": sp["rwa_total"].astype(float),
        "ecl": sp["ecl"].astype(float),
        "cet1_ratio": sp["cet1_ratio"].astype(float),
        "tier1_ratio": sp["tier1_ratio"].astype(float),
        "total_ratio": sp["total_ratio"].astype(float),
        "binding": sp["binding"],
        "passes": sp["passes"].astype(bool),
    })

    bis, capm = result.bis, result.meta["capital"]
    amounts = {"CET1": float(capm.cet1),
               "AT1": float(capm.additional_t1),
               "T2": float(capm.tier2)}
    ratios = {"CET1": float(bis.cet1_ratio), "AT1": float(bis.tier1_ratio),
              "T2": float(bis.total_ratio)}
    req = {"CET1": float(bis.required["cet1"]), "AT1": float(bis.required["tier1"]),
           "T2": float(bis.required["total"])}
    sur = {"CET1": float(bis.surplus_shortfall["cet1"]),
           "AT1": float(bis.surplus_shortfall["tier1"]),
           "T2": float(bis.surplus_shortfall["total"])}
    stack = pd.DataFrame([{
        "asof": asof, "tier": k, "amount": amounts[k], "ratio": ratios[k],
        "required": req[k], "surplus": sur[k],
    } for k in cat.CAPITAL_TIERS])
    return {"st_capital_path": path, "cap_stack": stack}


# ---------------------------------------------------------------- R6 · ALM

def materialize_alm(result, portfolio, base) -> dict[str, pd.DataFrame]:
    """LCR·NSFR·IRRBB 지표와 충격 시나리오 + ALM 원장 23장.

    원장은 파이프라인이 이미 세운 것(`result.alm_tables`)을 그대로 받는다.
    여기서 다시 만들면 자본비율·서식이 쓴 산출과 화면이 두 벌이 된다 —
    구조화 원장이 같은 이유로 이미 이 규약을 쓰고 있다.
    """
    asof = _asof(result)
    from risk_lib.references import LCR_MIN, NSFR_MIN
    lcr, nsfr, irrbb = result.alm["lcr"], result.alm["nsfr"], result.alm["irrbb"]
    nii = result.alm.get("nii")

    rows = [
        {"asof": asof, "metric": "LCR", "value": float(lcr.lcr),
         "minimum": float(LCR_MIN), "numerator": float(lcr.hqla_total),
         "denominator": float(lcr.net_outflow), "passes": bool(lcr.passes())},
        {"asof": asof, "metric": "NSFR", "value": float(nsfr.nsfr),
         "minimum": float(NSFR_MIN), "numerator": float(nsfr.asf_total),
         "denominator": float(nsfr.rsf_total), "passes": bool(nsfr.passes())},
        {"asof": asof, "metric": "IRRBB_EVE",
         "value": float(irrbb.worst_pct_tier1), "minimum": None,
         "numerator": float(irrbb.worst_eve_decline),
         "denominator": float(irrbb.tier1), "passes": bool(not irrbb.outlier())},
    ]
    if nii is not None and not nii.result.empty:
        # `ALM_METRICS`가 선언만 하고 어디에서도 만들지 않던 행이다.
        # 판정 기준(ΔNII 한도)은 1차자료를 확인하지 못했으므로 passes는 NULL —
        # 기준 없이 True/False를 적으면 없는 판정을 한 것이 된다.
        w = nii.result.loc[nii.result["delta_nii"].idxmin()]
        rows.append({
            "asof": asof, "metric": "IRRBB_NII",
            "value": float(w["delta_nii"] / w["nii_base"]), "minimum": None,
            "numerator": float(w["delta_nii"]),
            "denominator": float(w["nii_base"]), "passes": None})
    alm = pd.DataFrame(rows, columns=cat.ALM_RESULT.column_names)

    # IRRBB 6개 표준 충격 — 헤드라인 산출기준의 시나리오별 뷰.
    shocks = irrbb.by_scenario
    srows = [{"asof": asof, "scenario": str(r_["scenario"]),
              "delta_eve": float(r_["delta_eve"]),
              "pct_tier1": float(r_["pct_tier1"])}
             for _, r_ in shocks.iterrows()]

    out = {"alm_result": alm,
           "alm_irrbb_shock": pd.DataFrame(srows,
                                           columns=cat.IRRBB_SHOCK.column_names)}
    out.update(getattr(result, "alm_tables", {}) or {})
    return out


# ---------------------------------------------------------------- R7 · MKT/NCR

def materialize_market(result, portfolio, base) -> dict[str, pd.DataFrame]:
    """트레이딩북 포지션 · IPV 결과 · NCR 구성요소."""
    asof = _asof(result)
    seed = result.meta.get("seed", 42)
    from risk_lib.sensitivities import synthesise_trading_book
    from risk_lib.ipv import run_ipv
    from risk_lib.ncr import compute_ncr_from_result

    bank = portfolio[portfolio["asset_class"] == "bank"]
    book = synthesise_trading_book(bank, seed=seed)
    tr = book.trades.reset_index(drop=True)
    trade_ids = [f"TRD_{i:06d}" for i in range(len(tr))]
    trade = pd.DataFrame({
        "trade_id": trade_ids,
        "counterparty": tr["counterparty"].astype(str),
        "kind": tr["kind"].astype(str),
        "notional": tr["notional"].astype(float),
        "maturity": tr["maturity"].astype(float),
        "fo_value": np.where(tr["price"].to_numpy(dtype=float) != 0.0,
                             tr["price"].to_numpy(dtype=float)
                             * tr["notional"].to_numpy(dtype=float) / 100.0,
                             tr["notional"].to_numpy(dtype=float) * 0.01),
        "delta": tr["delta"].astype(float),
        "vega": tr["vega"].astype(float),
        "dv01": tr["dv01"].astype(float),
        "cs01": tr["cs01"].astype(float),
    })

    ipv_res = run_ipv(tr, seed=seed)
    pos = ipv_res.positions.reset_index(drop=True)
    ipv = pd.DataFrame({
        "trade_id": trade_ids, "asof": asof,
        "source": pos["source"].astype(str),
        "fo_value": pos["fo_price"].astype(float),
        "benchmark_value": pos["benchmark_price"].astype(float),
        "diff": pos["diff"].astype(float),
        "limit": pos["limit"].astype(float),
        "verified": pos["verified"].astype(bool),
        "is_break": pos["is_break"].astype(bool),
        "days_open": pos["days_open"].astype(int),
    })

    n = compute_ncr_from_result(result, seed=seed)
    rows = [{"asof": asof, "component": "자산총액", "category": "영업용순자본",
             "amount": n.noc.total_assets, "citation": "제3-6조"},
            {"asof": asof, "component": "부채총액", "category": "영업용순자본",
             "amount": -n.noc.total_liabilities, "citation": "제3-6조"},
            {"asof": asof, "component": "차감항목", "category": "영업용순자본",
             "amount": -n.noc.total_deduction, "citation": "제3-11조"},
            {"asof": asof, "component": "가산항목", "category": "영업용순자본",
             "amount": n.noc.total_addition, "citation": "제3-14조"}]
    for _, r_ in n.risk.by_component.iterrows():
        rows.append({"asof": asof, "component": r_["component"],
                     "category": "총위험액", "amount": float(r_["amount"]),
                     "citation": "제3-21조"})
    rows.append({"asof": asof, "component": "필요유지자기자본",
                 "category": "필요유지자기자본",
                 "amount": n.required_capital, "citation": "제3-6조 (최저×70%)"})
    ncr = pd.DataFrame(rows, columns=cat.NCR_COMPONENT.column_names)
    return {"mkt_trade": trade, "mkt_ipv": ipv, "ncr_component": ncr}



# ---------------------------------------------------------------- R8 · OPR

def materialize_operational(result, portfolio, base) -> dict[str, pd.DataFrame]:
    """운영손실 사건 원장 · 운영리스크 자본."""
    asof = _asof(result)
    ol = result.op_loss
    reg = ol.register.reset_index(drop=True)
    # 사건유형 표기를 규정 7개 유형으로 정규화 (원본은 한글/약칭 혼재 가능)
    known = set(cat.OP_EVENT_TYPES)
    et = reg["event_type"].astype(str)
    events = pd.DataFrame({
        "event_id": [f"OPL_{i:06d}" for i in range(len(reg))],
        "event_date": pd.to_datetime(reg["date"]).dt.strftime("%Y-%m-%d")
        if "date" in reg else asof,
        "event_type": np.where(et.isin(list(known)), et, "execution_delivery"),
        "gross_loss": reg["gross"].astype(float),
        "recovery": reg["recovery"].astype(float),
        "net_loss": reg["net"].astype(float),
    })

    rwa_op = float(result.rwa["op"])
    cap = pd.DataFrame([
        {"asof": asof, "method": "SMA", "capital": rwa_op / 12.5,
         "rwa": rwa_op, "var_999": None},
        {"asof": asof, "method": "LDA",
         "capital": float(ol.var_99_9), "rwa": float(ol.var_99_9) * 12.5,
         "var_999": float(ol.var_99_9)},
    ], columns=cat.OP_CAPITAL.column_names)
    cap["var_999"] = pd.to_numeric(cap["var_999"], errors="coerce").astype("float64")
    return {"opr_loss_event": events, "opr_capital": cap}


# ---------------------------------------------------------------- R9 · AIG/VAL

def materialize_governance(result, portfolio, base) -> dict[str, pd.DataFrame]:
    """자체검증 결과 · 산출 근거 원장 · 수동조정 원장."""
    asof = _asof(result)
    from risk_lib.audit_trail import build_ledger_from_result
    from risk_lib.adjustments import demo_ledger

    checks = pd.DataFrame([{
        "asof": asof, "check_name": c.name, "status": c.status,
        "detail": c.detail, "domain": c.name.split("_")[0],
    } for c in result.validation.checks],
        columns=cat.VALIDATION_RESULT.column_names)

    led = build_ledger_from_result(result)
    audit = pd.DataFrame([{
        "figure_id": e.figure_id, "label": e.label,
        "value": float(e.value) if isinstance(e.value, (int, float)) else None,
        "code_module": e.code_module, "code_function": e.code_function,
        "citation": e.citation,
    } for e in led.entries], columns=cat.AUDIT_LEDGER.column_names)
    audit["value"] = pd.to_numeric(audit["value"], errors="coerce").astype("float64")

    adj_led = demo_ledger(result, asof=asof)
    adj = pd.DataFrame([{
        "adjustment_id": a.adjustment_id, "figure_id": a.figure_id,
        "base_value": a.base_value, "adjusted_value": a.adjusted_value,
        "delta": a.delta, "requester": a.requester, "approver": a.approver,
        "senior_approval": a.senior_approval or None,
        "status": a.status, "expires_on": a.expires_on,
        "evidence_ref": a.evidence_ref,
    } for a in adj_led.adjustments], columns=cat.ADJUSTMENT.column_names)
    return {"val_check": checks, "val_audit_ledger": audit,
            "aig_adjustment": adj}


# ---------------------------------------------------------------- 통합

_MATERIALIZERS = {
    "PRD-CRM": materialize_crm,
    "PRD-RWA": materialize_rwa,
    "PRD-ECL": materialize_ecl,
    "PRD-ST":  materialize_stress_capital,
    "PRD-ALM": materialize_alm,
    "PRD-MKT": materialize_market,
    "PRD-OPR": materialize_operational,
    "PRD-VAL": materialize_governance,
}


def materialize_all(result, portfolio, base: dict[str, pd.DataFrame] | None = None
                    ) -> dict[str, pd.DataFrame]:
    """RDM 분해 + 등록된 모든 부문 엔진을 실행해 전체 테이블을 만든다."""
    from risk_lib.datamodel.decompose import decompose
    if base is None:
        base = decompose(portfolio, asof=_asof(result),
                         seed=result.meta.get("seed", 42))
    out = dict(base)
    for fn in _MATERIALIZERS.values():
        out.update(fn(result, portfolio, base))
    return out
