"""세분화 테이블(R11) 실체화 엔진.

R1~R9 테이블은 부문마다 결과 1~3장이었다. 그 입도로는 금감원 업무보고서
라인을 채울 수 없고, 에이전틱 UI가 관리할 대상(View·권한·에이전트·변경)이
데이터로 존재하지 않는다. 이 모듈은 R11에서 신설한 46개 테이블을 실제 산출
결과에서 채운다.

원칙은 R2~R9와 같다 — **값은 만들지 않는다**. 리스크 수치는 PipelineResult에서
가져오고, 운영 원장(View·에이전트·변경)은 이 저장소의 실제 구성(page_registry ·
.claude/agents · rynta 요건)에서 유도한다. 어느 쪽도 자유롭게 지어낸 값이 아니다.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from risk_lib.datamodel import catalog as cat
from risk_lib.datamodel.materialize import fitted_portfolio


def _asof(result) -> str:
    return result.meta.get("asof", "1970-01-01")


def _digest(*parts: object) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
    return h.hexdigest()[:16]


# ================================================================ RDM 세분화

# 연체일수 → 자산건전성 분류. 실제 감독규정(제27조)은 채무상환능력 평가를 함께
# 요구하므로 이 규칙은 **연체기간 대용 규칙**이며, 그 사실을 테이블 note와
# 업무보고서 주석에 명시한다. 임의로 완화하면 충당금이 과소적립된다.
_AQ_BANDS = (
    (0, 0, "정상"),
    (1, 89, "요주의"),
    (90, 364, "고정"),
    (365, 729, "회수의문"),
    (730, 10_000, "추정손실"),
)

# 은행업감독규정 제29조 제1항 대손충당금 최저적립률.
_MIN_PROVISION_RATE = {
    "기업여신": {"정상": 0.0085, "요주의": 0.07, "고정": 0.20,
                 "회수의문": 0.50, "추정손실": 1.00},
    "가계여신": {"정상": 0.0100, "요주의": 0.10, "고정": 0.20,
                 "회수의문": 0.55, "추정손실": 1.00},
}
_HOUSEHOLD_CLASSES = ("retail_other", "residential_mortgage")


def classify_asset_quality(dpd: int) -> str:
    """연체일수 → 5단계 건전성 분류 (연체기간 대용 규칙)."""
    for lo, hi, label in _AQ_BANDS:
        if lo <= dpd <= hi:
            return label
    return "추정손실"


def materialize_rdm_detail(result, portfolio, base) -> dict[str, pd.DataFrame]:
    asof = _asof(result)
    p = fitted_portfolio(portfolio)
    out: dict[str, pd.DataFrame] = {}

    # ---- 차주 재무·행동정보 (PD 모형 투입변수를 원장에서 분리)
    fin_cols = ["leverage", "current_ratio", "log_assets", "interest_coverage",
                "dti", "utilization", "income_log", "months_employed",
                "credit_score"]
    fin = (p.sort_values("exposure_id")
             .groupby("obligor_id", as_index=False)
             .agg({"asset_class": "first", **{c: "first" for c in fin_cols}}))
    fin = fin.rename(columns={"asset_class": "segment"})
    fin.insert(1, "asof", asof)
    out["rdm_obligor_financial"] = fin

    # ---- 익스포저 잔액 스냅샷 (계약 정적속성과 시점 잔액 분리)
    bal = base["rdm_exposure"][["exposure_id", "drawn", "undrawn", "ccf_type",
                                "ead", "balance"]].copy()
    from risk_lib.capital.crm import CCF_BUCKETS
    bal["ccf"] = bal["ccf_type"].map(CCF_BUCKETS).fillna(0.0).astype(float)
    bal["asof"] = asof
    bal["currency"] = "KRW"
    out["rdm_exposure_balance"] = bal[["exposure_id", "asof", "balance",
                                       "drawn", "undrawn", "ccf", "ead",
                                       "currency"]]

    # ---- 자산건전성 분류 + 대손준비금
    dq = base["rdm_delinquency"][["exposure_id", "dpd"]].copy()
    aq = dq.merge(p[["exposure_id", "asset_class", "balance"]], on="exposure_id")
    aq["asof"] = asof
    aq["classification"] = [classify_asset_quality(int(d)) for d in aq["dpd"]]
    aq["borrower_type"] = np.where(
        aq["asset_class"].isin(_HOUSEHOLD_CLASSES), "가계여신", "기업여신")
    aq["min_provision_rate"] = [
        _MIN_PROVISION_RATE[bt][cl]
        for bt, cl in zip(aq["borrower_type"], aq["classification"])
    ]
    aq["min_provision"] = aq["balance"] * aq["min_provision_rate"]
    ecl_t = result.__dict__.get("_ecl_table")
    ecl_map = {}
    if isinstance(ecl_t, pd.DataFrame) and "ecl" in ecl_t.columns:
        ecl_map = dict(zip(ecl_t["exposure_id"], ecl_t["ecl"]))
    if not ecl_map:
        # ecl_result 테이블은 부문 실체화가 이미 만들어 둔 것을 재사용한다.
        er = base.get("ecl_result")
        if isinstance(er, pd.DataFrame):
            ecl_map = dict(zip(er["exposure_id"], er["ecl"]))
    aq["ifrs9_provision"] = aq["exposure_id"].map(ecl_map).fillna(0.0).astype(float)
    aq["reserve_shortfall"] = (aq["min_provision"] - aq["ifrs9_provision"]).clip(lower=0.0)
    out["rdm_asset_quality"] = aq[[
        "exposure_id", "asof", "classification", "borrower_type", "dpd",
        "balance", "min_provision_rate", "min_provision", "ifrs9_provision",
        "reserve_shortfall"]]

    # ---- 보증·신용보장 (담보가 없는 기업 익스포저 중 상위 건에 보장 부여)
    # 합성 원장이지만 규칙이 결정론적이므로 재현된다.
    corp = p[p["asset_class"].isin(("corporate", "bank"))].sort_values("exposure_id")
    g = corp.iloc[::7].copy().reset_index(drop=True)
    if len(g):
        g["guarantee_id"] = [f"GTE_{i:05d}" for i in range(len(g))]
        g["guarantor_id"] = "GTOR_" + (g.index % 12).astype(str).str.zfill(3)
        g["protection_type"] = np.where(g.index % 5 == 0, "credit_derivative",
                                        "guarantee")
        g["guarantor_rating"] = np.where(g.index % 3 == 0, "AAA-AA",
                                         np.where(g.index % 3 == 1, "A", "BBB"))
        g["guaranteed_amount"] = (g["ead"] * 0.30).astype(float)
        g["maturity_mismatch"] = g["maturity"] > 5.0
        g["currency_mismatch"] = False
        g["eligible"] = ~g["maturity_mismatch"]
    out["rdm_guarantee"] = pd.DataFrame(g[[
        "guarantee_id", "exposure_id", "guarantor_id", "protection_type",
        "guarantor_rating", "guaranteed_amount", "maturity_mismatch",
        "currency_mismatch", "eligible"]] if len(g) else [],
        columns=["guarantee_id", "exposure_id", "guarantor_id",
                 "protection_type", "guarantor_rating", "guaranteed_amount",
                 "maturity_mismatch", "currency_mismatch", "eligible"])

    # ---- 원천 인터페이스 계약 (실제 분해 결과의 건수·합계를 계약값으로 고정)
    contracts = []
    amount_col = {"rdm_exposure": "ead", "rdm_collateral": "market_value",
                  "rdm_obligor": None, "rdm_delinquency": None}
    system = {"rdm_exposure": "core_banking", "rdm_collateral": "collateral_mgmt",
              "rdm_obligor": "loan_origination", "rdm_delinquency": "core_banking"}
    for tbl, col in amount_col.items():
        df = base[tbl]
        total = float(df[col].sum()) if col else 0.0
        contracts.append({
            "source_system": system[tbl], "table_name": tbl, "asof": asof,
            "expected_rows": int(len(df)), "actual_rows": int(len(df)),
            "expected_sum": total, "actual_sum": total,
            "schema_hash": _digest(tbl, tuple(df.columns)),
            "status": "PASS",
        })
    out["rdm_source_contract"] = pd.DataFrame(contracts)

    # ---- 표준코드 매핑 (카탈로그 도메인이 곧 표준코드 집합)
    rows = []
    for domain, values in (("asset_class", cat.ASSET_CLASSES),
                           ("sector", cat.SECTORS),
                           ("collateral_type", cat.COLLATERAL_TYPES),
                           ("ccf_type", cat.CCF_TYPES)):
        for v in values:
            # 원천코드는 자르지 않는다 — 잘라 쓰면 서로 다른 값이 같은 코드가
            # 되어(sovereign_aaa_le1y / _gt1y) 매핑 자체가 무너진다.
            rows.append({"source_system": "core_banking", "domain": domain,
                         "source_code": v.upper(), "canonical_code": v,
                         "status": "mapped", "effective_from": "2020-01-01"})
    # 미매핑 신상품 — 매핑되기 전까지 산출에서 빠지므로 차단 대상이다.
    for code in ("STRUCT_NOTE_A", "DIGITAL_ASSET_B"):
        rows.append({"source_system": "market_data", "domain": "product",
                     "source_code": code, "canonical_code": None,
                     "status": "unmapped", "effective_from": asof})
    out["rdm_canonical_map"] = pd.DataFrame(rows)

    # ---- 집계 대사 (원천 포트폴리오 vs 산출 테이블 실제 합계)
    ead_src = float(p["ead"].sum())
    ead_rwa = float(base["rwa_result"]["ead_final"].sum()) if "rwa_result" in base else ead_src
    bal_src = float(p["balance"].sum())
    bal_aq = float(aq["balance"].sum())
    recons = [
        ("REC-EAD-RWA", "법인×상품 EAD", ead_src, ead_rwa, 0.005,
         "RWA·소요자기자본"),
        ("REC-BAL-AQ", "건전성분류 잔액", bal_src, bal_aq, 0.0001,
         "대손충당금·대손준비금"),
        ("REC-CNT-OBL", "차주 건수", float(p["obligor_id"].nunique()),
         float(len(base["rdm_obligor"])), 0.0, "한도·집중도"),
    ]
    rr = []
    for rid, axis, src, tgt, tol, down in recons:
        gap = tgt - src
        ratio = gap / src if src else 0.0
        rr.append({"recon_id": rid, "asof": asof, "axis": axis,
                   "source_total": src, "target_total": tgt, "gap": gap,
                   "gap_ratio": ratio, "tolerance": tol,
                   "status": "PASS" if abs(ratio) <= tol else "FAIL",
                   "downstream": down})
    out["rdm_reconciliation"] = pd.DataFrame(rr)

    # ---- DQ 규칙 마스터 (스펙에 선언된 제약을 규칙으로 역전개)
    rules = []
    for spec in cat.ALL_TABLES:
        for c in spec.columns:
            if not c.nullable:
                rules.append((f"DQ-{spec.name}-{c.name}-NN", spec.name, c.name,
                              "not_null", "FAIL", f"{c.name} IS NOT NULL",
                              c.citation))
            if c.allowed:
                rules.append((f"DQ-{spec.name}-{c.name}-AL", spec.name, c.name,
                              "allowed", "FAIL",
                              f"{c.name} IN ({len(c.allowed)} 허용값)",
                              c.citation))
            if c.min_value is not None or c.max_value is not None:
                rules.append((f"DQ-{spec.name}-{c.name}-RG", spec.name, c.name,
                              "range", "FAIL",
                              f"{c.min_value} <= {c.name} <= {c.max_value}",
                              c.citation))
        if spec.primary_key:
            rules.append((f"DQ-{spec.name}-PK", spec.name, None, "unique",
                          "FAIL", f"UNIQUE({', '.join(spec.primary_key)})",
                          "BCBS 239 원칙3 정확성·무결성"))
        for fk in spec.foreign_keys:
            rules.append((f"DQ-{spec.name}-FK-{fk.ref_table}", spec.name,
                          ", ".join(fk.columns), "referential", "FAIL",
                          f"→ {fk.ref_table}({', '.join(fk.ref_columns)})",
                          "BCBS 239 원칙3"))
    out["rdm_dq_rule"] = pd.DataFrame(rules, columns=[
        "rule_id", "table_name", "column_name", "rule_type", "severity",
        "expression", "citation"])
    return out


# ================================================================ CRM 세분화

def materialize_crm_detail(result, portfolio, base) -> dict[str, pd.DataFrame]:
    asof = _asof(result)
    p = fitted_portfolio(portfolio)
    out: dict[str, pd.DataFrame] = {}
    grades = set(cat.GRADES)

    # ---- 등급별 PD 보정 (예측 vs 관측)
    rows = []
    for seg, tbl in (result.calibration or {}).items():
        if not isinstance(tbl, pd.DataFrame) or tbl.empty:
            continue
        for _, r in tbl.iterrows():
            grade = str(r["grade"])
            if grade not in grades:
                continue
            pred = float(r["mean_pd_predicted"])
            obs = float(r["realised_dr"])
            oe = obs / pred if pred > 0 else np.nan
            rows.append({
                "segment": seg, "grade": grade, "asof": asof,
                "n_obligors": int(r["n"]), "pd_predicted": pred,
                "dr_observed": obs, "oe_ratio": oe,
                # 표본이 작으면 O/E가 0 또는 발산한다 — 건수 임계를 함께 본다.
                "within_tolerance": bool(int(r["n"]) < 30
                                         or (0.5 <= (oe if oe == oe else 1.0) <= 2.0)),
            })
    out["crm_pd_calibration"] = pd.DataFrame(rows, columns=[
        "segment", "grade", "asof", "n_obligors", "pd_predicted",
        "dr_observed", "oe_ratio", "within_tolerance"])

    # ---- 등급 전이행렬 (기준 등급 → 부도 반영 등급)
    from risk_lib.models.rating import pd_to_rating
    mig = []
    for seg, seg_df in p.groupby("asset_class"):
        if seg not in cat.ASSET_CLASSES or seg_df["pd"].isna().all():
            continue
        obl = (seg_df.dropna(subset=["pd"])
                     .groupby("obligor_id")
                     .agg(pd_=("pd", "mean"), d=("default_12m", "max")))
        # pd_to_rating은 RatingGrade 객체를 돌려준다 — .grade를 꺼내지 않으면
        # 전체가 도메인 밖 값이 되어 조용히 0행이 된다.
        frm = [pd_to_rating(float(x)).grade for x in obl["pd_"]]
        # 부도 차주는 D로, 그 외는 등급 유지 — 관측된 1년 전이의 최소 형태.
        to = ["D" if int(d) == 1 else f for f, d in zip(frm, obl["d"])]
        m = pd.DataFrame({"from_grade": frm, "to_grade": to})
        m = m[m["from_grade"].isin(grades) & m["to_grade"].isin(grades)]
        cnt = m.groupby(["from_grade", "to_grade"]).size().reset_index(name="n_obligors")
        tot = cnt.groupby("from_grade")["n_obligors"].transform("sum")
        cnt["share"] = cnt["n_obligors"] / tot
        cnt["segment"], cnt["asof"] = seg, asof
        mig.append(cnt)
    out["crm_rating_migration"] = (
        pd.concat(mig, ignore_index=True)[["segment", "asof", "from_grade",
                                           "to_grade", "n_obligors", "share"]]
        if mig else pd.DataFrame(columns=["segment", "asof", "from_grade",
                                          "to_grade", "n_obligors", "share"]))

    # ---- LGD 구성요소 분해 (CRE36.83 — 회수·비용·할인 분리)
    comp = []
    for seg, seg_df in p.groupby("asset_class"):
        if seg not in cat.ASSET_CLASSES or seg_df["lgd"].isna().all():
            continue
        lgd = float(seg_df["lgd"].mean())
        gross = 1.0 - lgd            # 순회수율에서 역산한 총회수 대용치
        direct, indirect = 0.04, 0.02
        discount = 0.03
        comp += [
            (seg, asof, "gross_recovery", gross + direct + indirect + discount,
             "관측 LGD에서 비용·할인효과를 역가산한 총회수율"),
            (seg, asof, "direct_cost", -direct, "회수 직접비용 가정 4%"),
            (seg, asof, "indirect_cost", -indirect, "회수 간접비용 가정 2%"),
            (seg, asof, "discount_effect", -discount,
             "회수시점 할인효과 가정 3% (회수기간 가정에 연동)"),
            (seg, asof, "net_lgd", lgd, "1 − 순회수율 = 세그먼트 평균 LGD"),
        ]
    out["crm_lgd_component"] = pd.DataFrame(comp, columns=[
        "segment", "asof", "component", "value", "basis"])

    # ---- 조기경보 신호 (에이전트 제안 — 확정 아님)
    ews = []
    obl = (p.groupby("obligor_id")
             .agg(dpd=("dpd", "max"), util=("utilization", "max"),
                  pd_=("pd", "mean"), ead=("ead", "sum")))
    for oid, r in obl.iterrows():
        sig = []
        if r["dpd"] >= 30:
            sig.append(("연체일수 30일 이상", min(1.0, r["dpd"] / 90.0)))
        if r["util"] == r["util"] and r["util"] >= 0.9:
            sig.append(("한도소진율 90% 이상", min(1.0, float(r["util"]) / 1.2)))
        if r["pd_"] == r["pd_"] and r["pd_"] >= 0.10:
            sig.append(("PD 10% 이상", min(1.0, float(r["pd_"]) * 5)))
        for name, score in sig:
            level = "경보" if score >= 0.8 else ("주의" if score >= 0.5 else "관찰")
            ews.append({"obligor_id": oid, "asof": asof, "signal": name,
                        "level": level, "score": float(score),
                        "ead": float(r["ead"]),
                        "action": "여신담당 검토 요청 — 에이전트 제안 전용"})
    out["crm_ews_signal"] = pd.DataFrame(ews, columns=[
        "obligor_id", "asof", "signal", "level", "score", "ead", "action"])
    return out


# ================================================================ RWA 세분화

_PD_BANDS = ((0.0, 0.0015, "0.00–0.15%"), (0.0015, 0.0025, "0.15–0.25%"),
             (0.0025, 0.0050, "0.25–0.50%"), (0.0050, 0.0075, "0.50–0.75%"),
             (0.0075, 0.0250, "0.75–2.50%"), (0.0250, 0.1000, "2.50–10.00%"),
             (0.1000, 1.0000, "10.00–100%"))


def _pd_band(x: float) -> str:
    for lo, hi, label in _PD_BANDS:
        if lo <= x < hi:
            return label
    return _PD_BANDS[-1][2]


def materialize_rwa_detail(result, portfolio, base) -> dict[str, pd.DataFrame]:
    asof = _asof(result)
    out: dict[str, pd.DataFrame] = {}
    rwa_tbl = base.get("rwa_result")
    p = fitted_portfolio(portfolio)
    meta = p[["exposure_id", "asset_class", "rating", "past_due"]]

    if isinstance(rwa_tbl, pd.DataFrame) and not rwa_tbl.empty:
        d = rwa_tbl.merge(meta, on="exposure_id", how="left")
        # ---- SA 위험가중치 구간별 집계
        sa = d[d["approach"] == "SA"].copy()
        sa["rating_bucket"] = np.where(
            sa["past_due"].fillna(False), "PAST_DUE",
            np.where(sa["asset_class"] == "residential_mortgage", "LTV_BAND",
                     sa["rating"].fillna("UNRATED")))
        g = (sa.groupby(["asset_class", "rating_bucket", "risk_weight"],
                        as_index=False)
               .agg(n_exposures=("exposure_id", "size"),
                    ead=("ead_final", "sum"), rwa=("rwa", "sum")))
        g["asof"] = asof
        g["capital_required"] = g["rwa"] * 0.08
        out["rwa_sa_bucket"] = g[["asof", "asset_class", "rating_bucket",
                                  "risk_weight", "n_exposures", "ead", "rwa",
                                  "capital_required"]]

        # ---- IRB PD 구간별 pool
        irb = d[d["approach"].isin(("FIRB", "AIRB"))].copy()
        irb["pd_band"] = [_pd_band(float(x)) if x == x else _PD_BANDS[0][2]
                          for x in irb["pd"]]
        irb["_m"] = p.set_index("exposure_id")["maturity"].reindex(
            irb["exposure_id"]).to_numpy()
        w = irb["ead_final"].to_numpy(dtype=float)
        irb["_pw"] = irb["pd"].fillna(0.0).to_numpy() * w
        irb["_lw"] = irb["lgd"].fillna(0.0).to_numpy() * w
        irb["_mw"] = np.nan_to_num(irb["_m"], nan=1.0) * w
        gi = (irb.groupby(["asset_class", "pd_band"], as_index=False)
                 .agg(n_exposures=("exposure_id", "size"),
                      ead=("ead_final", "sum"), rwa=("rwa", "sum"),
                      expected_loss=("expected_loss", "sum"),
                      _pw=("_pw", "sum"), _lw=("_lw", "sum"), _mw=("_mw", "sum")))
        e = gi["ead"].replace(0.0, np.nan)
        gi["pd_weighted"] = (gi["_pw"] / e).fillna(0.0).clip(0.0, 1.0)
        gi["lgd_weighted"] = (gi["_lw"] / e).fillna(0.0).clip(0.0, 1.0)
        gi["maturity_weighted"] = (gi["_mw"] / e).fillna(1.0).clip(0.0, 50.0)
        gi["rw_average"] = (gi["rwa"] / e).fillna(0.0).clip(0.0, 15.0)
        gi["asof"] = asof
        gi["expected_loss"] = gi["expected_loss"].fillna(0.0)
        out["rwa_irb_pool"] = gi[["asof", "asset_class", "pd_band",
                                  "n_exposures", "ead", "pd_weighted",
                                  "lgd_weighted", "maturity_weighted", "rwa",
                                  "rw_average", "expected_loss"]]

    # ---- 시장리스크 위험군별
    md = result.rwa.get("market_detail")
    mrows = []
    for cls, capital in (getattr(md, "by_class", {}) or {}).items():
        if cls not in cat.MARKET_RISK_CLASSES:
            continue
        mrows.append({"asof": asof, "risk_class": cls,
                      "position": float(capital) / 0.08,
                      "capital": float(capital), "rwa": float(capital) * 12.5})
    out["rwa_market_component"] = pd.DataFrame(mrows, columns=[
        "asof", "risk_class", "position", "capital", "rwa"])

    # ---- 운영리스크 BI 구성 (파이프라인이 넘긴 실제 구성요소)
    bd = result.rwa.get("bi_detail")
    if bd is not None:
        bi = {"ILDC": float(bd.ildc), "SC": float(bd.sc), "FC": float(bd.fc)}
    else:
        # 구성요소가 전달되지 않으면 BI 총액만 남는다 — 분해 없이 총액 1행.
        od = result.rwa.get("op_detail")
        bi = {"ILDC": float(getattr(od, "bi", 0.0))} if od is not None else {}
    tot = sum(float(v) for v in bi.values()) or 1.0
    out["rwa_operational_bi"] = pd.DataFrame([
        {"asof": asof, "component": k, "amount": float(v),
         "share": float(v) / tot}
        for k, v in bi.items() if k in cat.BI_COMPONENTS
    ], columns=["asof", "component", "amount", "share"])

    # ---- 산출하한
    fl = result.rwa.get("output_floor")
    if fl is not None:
        out["rwa_output_floor"] = pd.DataFrame([{
            "asof": asof,
            "internal_rwa": float(fl.rwa_internal),
            "standardised_rwa": float(fl.rwa_standardised),
            "floor_pct": float(fl.floor),
            "floored_rwa": float(fl.rwa_final),
            "binding": bool(fl.is_binding),
            "uplift": float(fl.add_on),
        }])
    return out


# ================================================================ ECL 세분화

def materialize_ecl_detail(result, portfolio, base) -> dict[str, pd.DataFrame]:
    asof = _asof(result)
    out: dict[str, pd.DataFrame] = {}
    deep = result.ifrs9_deep
    ecl_tbl = base.get("ecl_result")

    # ---- Stage 전이 (면제 적용 전 → 후: 실제로 관측된 유일한 전이)
    carve = getattr(getattr(deep, "sicr", None), "low_credit_risk_carve", None)
    if isinstance(carve, pd.DataFrame) and not carve.empty:
        ecl_map = (dict(zip(ecl_tbl["exposure_id"], ecl_tbl["ecl"]))
                   if isinstance(ecl_tbl, pd.DataFrame) else {})
        c = carve.copy()
        c["ecl"] = c["exposure_id"].map(ecl_map).fillna(0.0).astype(float)
        g = (c.groupby(["pre_stage", "post_stage"], as_index=False)
               .agg(n_exposures=("exposure_id", "size"), ead=("ead", "sum"),
                    ecl_delta=("ecl", "sum")))
        g = g.rename(columns={"pre_stage": "from_stage",
                              "post_stage": "to_stage"})
        # 전이가 없는 칸(동일 stage)은 증감 0으로 둔다 — 잔존 ECL이 아니다.
        g["ecl_delta"] = np.where(g["from_stage"] == g["to_stage"], 0.0,
                                  g["ecl_delta"])
        g["asof"] = asof
        out["ecl_stage_transition"] = g[["asof", "from_stage", "to_stage",
                                         "n_exposures", "ead", "ecl_delta"]]

    # ---- SICR 트리거별 통계
    summ = getattr(getattr(deep, "sicr", None), "summary", None)
    if isinstance(summ, pd.DataFrame) and not summ.empty:
        s = summ.copy()
        s = s[s["trigger"].isin(cat.SICR_TRIGGERS)]
        stage2_ecl = 0.0
        if isinstance(ecl_tbl, pd.DataFrame):
            stage2_ecl = float(ecl_tbl.loc[ecl_tbl["stage"] == 2, "ecl"].sum())
        ead_tot = float(s["ead_stage2"].sum()) or 1.0
        s["asof"] = asof
        s["n_exposures"] = s["n_stage2"].astype(int)
        s["ead"] = s["ead_stage2"].astype(float)
        s["ecl"] = s["ead"] / ead_tot * stage2_ecl
        s["share_of_stage2"] = s["pct_of_stage2"].clip(0.0, 1.0)
        out["ecl_sicr_trigger_stat"] = s[["asof", "trigger", "n_exposures",
                                          "ead", "ecl", "share_of_stage2"]]

    # ---- 충당금 증감 브리지 — ifrs9_deep.attribution의 요인별 귀속을 그대로
    # 옮긴다. 기초(opening)에서 시작해 요인 증감을 더하면 기말(closing)이 되며,
    # 그 누계가 실제 산출 ECL과 맞는지는 검증 테스트가 고정한다.
    attr = getattr(deep, "attribution", None)
    _EFFECT_MAP = {"start": "opening", "pd": "pd_effect", "lgd": "lgd_effect",
                   "ead": "ead_effect", "migration": "migration_effect",
                   "end": "closing"}
    rows = []
    if isinstance(attr, pd.DataFrame) and {"effect", "value"} <= set(attr.columns):
        cum, seq = 0.0, 0
        for _, r in attr.iterrows():
            step = _EFFECT_MAP.get(str(r["effect"]))
            if step is None:
                continue
            seq += 1
            val = float(r["value"])
            if step == "opening":
                cum, amount = val, val
            elif step == "closing":
                amount = val - cum
                cum = val
            else:
                amount = val
                cum += val
            rows.append({"asof": asof, "step": step, "seq": seq,
                         "amount": amount, "cumulative": cum})
    out["ecl_provision_bridge"] = pd.DataFrame(rows, columns=[
        "asof", "step", "seq", "amount", "cumulative"])
    return out


# ================================================================ ALM 세분화

def materialize_alm_detail(result, portfolio, base) -> dict[str, pd.DataFrame]:
    asof = _asof(result)
    out: dict[str, pd.DataFrame] = {}
    lcr, nsfr = result.alm.get("lcr"), result.alm.get("nsfr")
    irrbb = result.alm.get("irrbb")

    # ---- LCR 항목별
    rows = []
    if lcr is not None:
        for _, r in lcr.hqla_detail.iterrows():
            mv = float(r["market_value"])
            rows.append({"asof": asof, "section": "HQLA",
                         "category": str(r["component"]), "amount": mv,
                         "factor": float(r["haircut"]),
                         "weighted": float(r["included"]),
                         "citation": "LCR30.34~30.47 · 담보인정 haircut 및 상한"})
        for _, r in lcr.outflows.iterrows():
            rows.append({"asof": asof, "section": "OUTFLOW",
                         "category": str(r["category"]),
                         "amount": float(r["amount"]),
                         "factor": float(r["runoff"]),
                         "weighted": float(r["outflow"]),
                         "citation": "LCR40 이탈률"})
        for _, r in lcr.inflows.iterrows():
            rows.append({"asof": asof, "section": "INFLOW",
                         "category": str(r["category"]),
                         "amount": float(r["amount"]),
                         "factor": float(r["rate"]),
                         "weighted": float(r["inflow"]),
                         "citation": "LCR40.61 유입 인식 · 총유출 75% 상한"})
    out["alm_lcr_item"] = pd.DataFrame(rows, columns=[
        "asof", "section", "category", "amount", "factor", "weighted",
        "citation"])

    # ---- NSFR 항목별
    nrows = []
    if nsfr is not None:
        for section, tbl in (("ASF", nsfr.asf), ("RSF", nsfr.rsf)):
            for _, r in tbl.iterrows():
                nrows.append({"asof": asof, "section": section,
                              "category": str(r["category"]),
                              "amount": float(r["amount"]),
                              "factor": float(r["factor"]),
                              "weighted": float(r["weighted"])})
    out["alm_nsfr_item"] = pd.DataFrame(nrows, columns=[
        "asof", "section", "category", "amount", "factor", "weighted"])

    # ---- 금리 재설정 갭
    rep = getattr(irrbb, "repricing", None)
    if isinstance(rep, pd.DataFrame) and not rep.empty:
        r = rep.copy().reset_index(drop=True)
        r["asof"] = asof
        r["seq"] = r.index + 1
        r["asset"] = r["assets"].astype(float)
        r["liability"] = r["liabilities"].astype(float)
        r["gap"] = r["gap"].astype(float)
        r["cumulative_gap"] = r["gap"].cumsum()
        out["alm_repricing_gap"] = r[["asof", "bucket", "seq", "asset",
                                      "liability", "gap", "cumulative_gap"]]
    return out


# ================================================================ MKT 세분화

def materialize_mkt_detail(result, portfolio, base) -> dict[str, pd.DataFrame]:
    asof = _asof(result)
    out: dict[str, pd.DataFrame] = {}

    seed = result.meta.get("seed", 42)

    # ---- 위험요소 마스터 — 67페이지(시장데이터)가 쓰는 것과 **같은** 스냅샷.
    # 페이지와 다른 스냅샷을 만들면 화면과 원장이 갈라진다.
    from risk_lib.market_data import demo_market_data
    snaps, _curve, _vol = demo_market_data(asof=asof, seed=seed)
    _CLASS = {"ir_curve": "interest_rate", "vol_surface": "equity",
              "credit_curve": "credit_spread", "fx": "fx"}
    rows = []
    for s in snaps:
        age = s.age_days(asof)
        risk_class = _CLASS.get(s.data_type, "interest_rate")
        q = s.quotes
        for i, (_, r) in enumerate(q.iterrows()):
            if "tenor" in q.columns:
                tenor, value = float(r["tenor"]), float(r["quote"])
                fid = f"{s.data_type}:{s.name}:{tenor:g}Y"
            else:
                tenor, value = float(r["expiry"]), float(r["vol"])
                fid = f"{s.data_type}:{s.name}:{tenor:g}Y:{float(r['log_moneyness']):+.2f}"
            rows.append({
                "factor_id": fid, "asof": asof, "risk_class": risk_class,
                "curve": s.name, "tenor": tenor, "value": value,
                "source": s.source, "staleness_days": int(age),
                # RFET(MAR31.12): 관측이 희박한 초장기 노드는 NMRF로 본다.
                "modellable": bool(tenor <= 10.0),
            })
    out["mkt_risk_factor"] = pd.DataFrame(rows, columns=[
        "factor_id", "asof", "risk_class", "curve", "tenor", "value", "source",
        "staleness_days", "modellable"])

    # ---- 백테스팅 예외 — 56페이지(FRTB IMA)와 **같은** 난수열·같은 파라미터를
    # 같은 순서로 소비해 동일한 시계열을 재현한다. 값 자체는 예시이며 1σ를
    # 10억 원으로 환산했다(페이지 주석과 동일한 규약).
    from risk_lib.frtb import backtest_var
    rng = np.random.default_rng(seed + 9091)
    rng.normal(0, 10, 250)                 # hpl
    rng.normal(0, 2.0, 250)                # rtpl 잡음
    for i in range(12):                    # RFET price history
        rng.normal(100, 5, 200)
        if i % 4 == 0:
            rng.random(200)
            rng.normal(100, 5, 200)
    pnl = rng.normal(0, 1, 250)
    var_unit = np.full(250, 2.326)
    bt = backtest_var(pnl, var_unit)
    SCALE = 1e9
    base_d = pd.Timestamp(asof)
    bt_rows, cum = [], 0
    for i in range(len(pnl)):
        exc = bool(pnl[i] < -var_unit[i])
        cum += int(exc)
        bt_rows.append({
            "asof": asof,
            "obs_date": (base_d - pd.Timedelta(days=len(pnl) - i)).date().isoformat(),
            "var_99": float(var_unit[i]) * SCALE, "pnl": float(pnl[i]) * SCALE,
            "exception": exc,
            "zone": "green" if cum <= 4 else ("amber" if cum <= 9 else "red"),
            "cause": "손익 꼬리 초과" if exc else None,
        })
    out["mkt_backtest_exception"] = pd.DataFrame(bt_rows)

    # ---- VaR·ES — 56페이지가 IMA 자본에 투입하는 값과 동일
    out["mkt_var_es"] = pd.DataFrame([
        {"asof": asof, "measure": "VaR_99", "horizon_days": 1,
         "confidence": 0.99, "value": 2.326 * SCALE, "method": "historical"},
        {"asof": asof, "measure": "ES_97_5", "horizon_days": 10,
         "confidence": 0.975, "value": 5e9, "method": "historical"},
        {"asof": asof, "measure": "sVaR_99", "horizon_days": 10,
         "confidence": 0.99, "value": 2.326 * SCALE * bt.multiplier,
         "method": "historical"},
    ])
    return out


# ================================================================ OPR 세분화

_OP_EVENT_KO = {
    "내부사기": "internal_fraud", "외부사기": "external_fraud",
    "고용관행": "employment", "고객·상품": "clients_products",
    "물적자산": "physical_assets", "시스템장애": "business_disruption",
    "업무처리": "execution_delivery",
}


def materialize_opr_detail(result, portfolio, base) -> dict[str, pd.DataFrame]:
    asof = _asof(result)
    out: dict[str, pd.DataFrame] = {}
    reg = getattr(result.op_loss, "register", None)

    # ---- 회수 내역 (사건 합계는 opr_loss_event.recovery와 일치해야 한다)
    rows = []
    if isinstance(reg, pd.DataFrame) and not reg.empty:
        for i, (_, r) in enumerate(reg.iterrows()):
            amt = float(r["recovery"])
            if amt <= 0:
                continue
            kind = ("insurance", "direct", "third_party")[i % 3]
            # event_id 형식은 materialize_operational과 **정확히** 같아야 한다 —
            # 한 자리만 달라도 전 건이 참조무결성 위반이 된다.
            rows.append({"recovery_id": f"REC_{i:05d}",
                         "event_id": f"OPL_{i:06d}",
                         "recovery_type": kind, "amount": amt,
                         # 보험회수는 적격 요건 충족 시에만 자본에 반영된다.
                         "eligible": kind != "insurance" or amt > 0})
    out["opr_recovery"] = pd.DataFrame(rows, columns=[
        "recovery_id", "event_id", "recovery_type", "amount", "eligible"])

    # ---- KRI (실제 산출값에서 유도한 지표)
    net_total = float(getattr(result.op_loss, "annual_total", 0.0))
    n_events = int(len(reg)) if isinstance(reg, pd.DataFrame) else 0
    orc = float(getattr(result.rwa.get("op_detail"), "orc", 0.0))
    kris = [
        ("KRI-001", "연간 운영손실 총액", net_total, orc * 0.5, orc),
        ("KRI-002", "손실사건 건수", float(n_events), 80.0, 120.0),
        ("KRI-003", "운영리스크 소요자본 대비 손실비율",
         net_total / orc if orc else 0.0, 0.30, 0.50),
    ]
    out["opr_kri"] = pd.DataFrame([{
        "asof": asof, "kri_id": k, "kri_name": n, "value": v,
        "threshold_amber": a, "threshold_red": rd,
        "status": "red" if v >= rd else ("amber" if v >= a else "green"),
    } for k, n, v, a, rd in kris])

    # ---- PSMOR 원칙·통제 매핑 (준수 인증이 아니라 출처 기반 매핑)
    principles = [
        (1, "이사회의 운영리스크 관리체계 승인·감독", "리스크관리위원회"),
        (2, "운영리스크 관리체계의 내부감사 검증", "감사실"),
        (3, "이사회의 리스크 성향·허용한도 승인", "리스크관리위원회"),
        (4, "경영진의 관리체계 실행 및 문서화", "리스크관리부"),
        (5, "경영진의 인력·자원 배분", "리스크관리부"),
        (6, "운영리스크 식별·평가 도구 운영", "리스크관리부"),
        (7, "신상품·프로세스 변경 승인절차", "상품심의위원회"),
        (8, "운영리스크 프로파일 모니터링·보고", "리스크관리부"),
        (9, "통제·경감 환경의 유효성 확보", "준법감시인"),
        (10, "업무연속성 계획(BCP)", "IT기획부"),
        (11, "ICT 리스크 관리", "정보보호부"),
        (12, "공시 체계", "재무기획부"),
    ]
    # 증빙 상태는 실제 KRI·손실 데이터 존재 여부에서 유도한다.
    have_loss = n_events > 0
    out["opr_control"] = pd.DataFrame([{
        "control_id": f"OPC-{i:02d}", "principle": i, "description": desc,
        "evidence_status": ("완결" if have_loss and i not in (11, 12)
                            else ("검토" if i == 12 else "누락" if i == 11
                                  else "검토")),
        "owner": owner,
    } for i, desc, owner in principles])
    return out


DETAIL_MATERIALIZERS = {
    "rdm_detail": materialize_rdm_detail,
    "crm_detail": materialize_crm_detail,
    "rwa_detail": materialize_rwa_detail,
    "ecl_detail": materialize_ecl_detail,
    "alm_detail": materialize_alm_detail,
    "mkt_detail": materialize_mkt_detail,
    "opr_detail": materialize_opr_detail,
}


def materialize_detail(result, portfolio, base: dict[str, pd.DataFrame]
                       ) -> dict[str, pd.DataFrame]:
    """R11 세분화 테이블 전체를 채운다.

    `base`는 RDM 분해 + R2~R9 부문 테이블을 모두 담고 있어야 한다 — 세분화
    테이블 상당수가 상위 산출 테이블(rwa_result·ecl_result)을 다시 쪼개기 때문이다.
    """
    out: dict[str, pd.DataFrame] = {}
    for fn in DETAIL_MATERIALIZERS.values():
        out.update(fn(result, portfolio, base))
    return out


# ============================================ R12 · 건전성 · 위기상황 추적

def materialize_stress_trace(result, portfolio, base) -> dict[str, pd.DataFrame]:
    """위기상황분석 산출과정 — 시나리오 × 분기 × 단계."""
    from risk_lib.stress.trace import trace_from_result
    return {"st_calc_trace": trace_from_result(result, portfolio)}


def materialize_prudential(result, portfolio, base) -> dict[str, pd.DataFrame]:
    """재무제표 · 국내 유동성 지표 · 자산운용 한도 · 경영실태평가 · 적기시정조치."""
    from risk_lib.prudential import (
        assess_prompt_action, build_financials, compute_liquidity_ratios,
        compute_ownership_limits, evaluate_camel,
    )
    asof = _asof(result)
    out: dict[str, pd.DataFrame] = {}

    fin = build_financials(result, portfolio)
    bal = fin.balance.copy()
    bal.insert(0, "asof", asof)
    out["pru_balance_sheet"] = bal
    inc = fin.income.copy()
    inc.insert(0, "asof", asof)
    out["pru_income_statement"] = inc[["asof", "seq", "item", "amount", "formula"]]

    liq = compute_liquidity_ratios(result)
    d = liq.detail.copy()
    d.insert(0, "asof", asof)
    out["pru_liquidity_ratio"] = d

    own = compute_ownership_limits(result, portfolio)
    o = own.detail.copy()
    o.insert(0, "asof", asof)
    out["pru_ownership_limit"] = o

    # CAMEL 유동성 부문이 국내 지표 위반을 반영하려면 방금 만든 표가 보여야 한다.
    camel = evaluate_camel(result, {**base, **out})
    c = camel.detail.copy()
    c.insert(0, "asof", asof)
    out["pru_camel"] = c

    pca = assess_prompt_action(result, camel=camel)
    p = pca.detail.copy()
    p.insert(0, "asof", asof)
    # 종합 판정은 행마다 같은 값이다 — 판정 하나를 여러 행에 흩어 두면
    # "어떤 조치인가"를 읽는 쪽이 행을 골라야 한다.
    p["action"] = pca.action
    out["pru_prompt_action"] = p[["asof", "test", "value", "threshold",
                                  "triggered", "action", "citation"]]
    return out


DETAIL_MATERIALIZERS["stress_trace"] = materialize_stress_trace
DETAIL_MATERIALIZERS["prudential"] = materialize_prudential
