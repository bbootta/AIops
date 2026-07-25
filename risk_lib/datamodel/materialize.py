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
    from risk_lib.pipeline import _fit_segment_pd
    fitted, *_ = _fit_segment_pd(portfolio.copy())
    return fitted


# ---------------------------------------------------------------- R2 · CRM

def materialize_crm(result, portfolio, base: dict[str, pd.DataFrame]
                    ) -> dict[str, pd.DataFrame]:
    """모형 인벤토리 · 등급/PD 이력 · 성능 지표."""
    asof = _asof(result)
    import dataclasses
    from risk_lib.model_inventory import build_standard_inventory

    # 모형 인벤토리 — 세그먼트는 모형명에서 유도한다(원본에 세그먼트 필드 없음).
    def _segment(name: str) -> str:
        if "주담대" in name:
            return "residential_mortgage"
        if "가계" in name:
            return "retail_other"
        return "corporate"

    inv = build_standard_inventory()
    model = pd.DataFrame([{
        "model_id": e.model_id,
        "model_name": e.name,
        "segment": _segment(e.name),
        "tier": int(e.tier),
        "status": e.status,
        "last_validation": e.last_validation,
        "next_due": e.next_due,
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
    g["grade"] = [pd_to_rating(float(x)) for x in g["pd"]]
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

    # 파이프라인과 동일한 IRB 북 (자산군 기준만) — 필터를 하나 더 걸면
    # 충당금 합계가 공표값과 어긋난다.
    fp = fitted_portfolio(portfolio)
    irb = fp[fp["asset_class"].isin(
        ["corporate", "retail_other", "residential_mortgage"])].copy()
    e = compute_ecl(irb)
    dpd = irb["dpd"].to_numpy(dtype=int)
    stage = e["stage"].to_numpy(dtype=int)
    trigger = np.where(stage == 3, "abs_pd",
                       np.where(dpd >= 30, "dpd30",
                                np.where(stage == 2, "pd_ratio", "none")))
    ead = e["ead"].to_numpy(dtype=float)
    ecl = e["ecl"].to_numpy(dtype=float)
    ecl_df = pd.DataFrame({
        "exposure_id": e["exposure_id"], "asof": asof,
        "stage": stage, "sicr_trigger": trigger,
        "pd_pit": np.nan_to_num(np.clip(irb["pd"].to_numpy(dtype=float), 0.0, 1.0)),
        "lgd": np.nan_to_num(np.clip(irb["lgd"].to_numpy(dtype=float), 0.0, 1.0)),
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


# ---------------------------------------------------------------- 통합

_MATERIALIZERS = {
    "PRD-CRM": materialize_crm,
    "PRD-RWA": materialize_rwa,
    "PRD-ECL": materialize_ecl,
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
