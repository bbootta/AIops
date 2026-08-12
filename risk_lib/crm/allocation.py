"""신용위험경감 배분 엔진 (1:1 · 1:N · M:1 · M:N).

**배분이 지켜야 하는 것.**
  1. 담보 초과배분 금지  Σ_i a[i][j] ≤ C_adj[j]
  2. 익스포저 초과충당 금지  Σ_j a[i][j] ≤ E_adj[i]
  3. 총량 보존  보전분 + 무보전분 = 조정 익스포저액
  4. 적격성 조정은 배분 **전에** 담보 단위로 끝낸다
  5. 어떤 배분규칙을 썼는지가 원장에 남는다

**4번을 담보 단위로 끝내는 이유.** 차감률을 배분 뒤에 적용하면 같은 담보가
익스포저마다 다른 차감률을 받는다. [별표 3] 62.의 C(1-Hc-Hfx)는 담보 하나에
대한 값이지 담보-익스포저 쌍마다 다시 정의되는 값이 아니다.

통화불일치(65.나)는 원래 담보-익스포저 쌍의 성질이다. 담보 1건이 여러
익스포저를 덮으면 쌍마다 판정이 갈릴 수 있으므로, 이 엔진은 **연결된
익스포저 중 하나라도 통화가 다르면 그 담보에 Hfx를 적용한다.** 담보가치를
낮추는 쪽이므로 감독 방향으로 보수적이고, 같은 담보가 두 차감률을 갖는 일이
생기지 않는다. 이 판정 규약은 원문이 정한 것이 아니라 이 엔진의 규약이다.

만기불일치(101.)의 T = Min[5, 익스포저 잔존만기]도 원래 쌍의 성질이다. 같은
이유로 **연결된 익스포저 중 잔존만기가 가장 긴 것**으로 T를 잡는다. T가 클수록
(t-0.25)/(T-0.25)가 작아지므로 이쪽도 보수적이다.

**배분규칙에 기본값을 두지 않는다.** 규칙을 바꾸면 위험가중치 절감액이 바뀌고
따라서 RWA가 바뀐다. 감독당국이 묻는 지점이므로 호출자가 매번 명시해야 하고,
쓴 규칙은 원장 컬럼으로 남는다. [별표 3] 제2장 제6절이 배분 순서를 정하지
않는다는 사실은 `crm_mitigation_param.alloc_rule_default` 행에 NULL로 적혀 있다.
"""

from __future__ import annotations

import pandas as pd

from risk_lib.alm.behaviour import ParamWarning
from risk_lib.crm.params import param_value
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

__all__ = ["ALLOC_RULES", "ALLOCATION", "allocate_crm"]

ALLOC_RULES: tuple[str, ...] = ("pro_rata", "risk_weight_desc", "maturity_asc")

# 비례배분 수렴 상한. 한 순회에서 각 담보는 소진되거나 수요가 0이 되므로 보통
# 1회에 끝난다. 상한을 두는 것은 부동소수 잔여가 끝없이 도는 것을 막기 위해서다.
_MAX_ROUNDS = 8
_EPS = 1e-9


ALLOCATION = TableSpec(
    name="crm_allocation", korean="신용위험경감 배분", product="PRD-RWA",
    grain="기준일 × 배분규칙 × 담보 × 익스포저 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("alloc_rule", "string", "배분규칙", nullable=False, allowed=ALLOC_RULES,
          citation="[별표 3] 제2장 제6절은 배분 순서를 정하지 않는다 "
                   "(crm_mitigation_param.alloc_rule_default = NULL). "
                   "규칙을 바꾸면 RWA가 바뀌므로 무엇을 썼는지가 원장에 남는다"),
        C("collateral_id", "string", "담보 식별자", nullable=False),
        C("exposure_id", "string", "익스포저 식별자", nullable=False),
        C("pool_id", "string", "교차담보 풀", nullable=False,
          note="배분은 이 단위로 푼다. 풀 단위 보존 검사의 집계 키다"),
        C("relation_type", "string", "관계 유형", nullable=False),
        C("collateral_value_adj", "float", "조정 담보가치", nullable=False,
          unit="KRW", min_value=0.0,
          citation="[별표 3] 62. C×(1-Hc-Hfx) 에 101. 만기불일치 조정을 곱한 값",
          note="담보 단위 값이 링크마다 반복된다. 합산하면 중복이다"),
        C("exposure_ead", "float", "조정 익스포저액", nullable=False, unit="KRW",
          min_value=0.0, citation="[별표 3] 62. E×(1+He)",
          note="익스포저 단위 값이 링크마다 반복된다. 합산하면 중복이다"),
        C("allocated_amount", "float", "배분액", nullable=False, unit="KRW",
          min_value=0.0),
        C("residual_collateral", "float", "담보 잔여", nullable=False, unit="KRW",
          min_value=0.0, note="담보 단위 값. 링크마다 반복된다"),
        C("residual_exposure", "float", "무보전 익스포저", nullable=False,
          unit="KRW", min_value=0.0, note="익스포저 단위 값. 링크마다 반복된다"),
        C("haircut_total", "float", "총 차감률(Hc+Hfx)", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0,
          note="담보 단위. 같은 담보가 익스포저마다 다른 값을 가지면 배분 뒤에 "
               "차감률을 적용한 것이다"),
        C("ccy_mismatch_haircut", "float", "통화불일치 차감률(Hfx)", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0,
          citation="[별표 3] 65.나"),
        C("maturity_mismatch_factor", "float", "만기불일치 조정계수", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0,
          citation="[별표 3] 100. · 101. 적용. 불인정이면 0, 불일치 없으면 1"),
        C("coverage_ratio", "float", "설정 비율", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
    ),
    primary_key=("asof", "alloc_rule", "collateral_id", "exposure_id"),
    foreign_keys=(FK(("asof", "collateral_id", "exposure_id"),
                     "crm_collateral_link",
                     ("asof", "collateral_id", "exposure_id")),),
    note="배분규칙이 기본키에 들어간다. 여러 규칙의 결과가 한 표에 공존해야 "
         "'규칙을 바꾸면 얼마가 달라지는가'를 화면과 검증이 볼 수 있다.",
)


def _order_key(rule: str, terms: dict[str, dict]):
    """순차 배분의 익스포저 정렬 키. 동점은 식별자로 깨서 결정론을 지킨다."""
    if rule == "risk_weight_desc":
        return lambda e: (-terms[e]["risk_weight"], e)
    if rule == "maturity_asc":
        return lambda e: (terms[e]["maturity_years"], e)
    raise ValueError(f"순차 배분 규칙이 아니다: {rule!r}")


def allocate_crm(
    links: pd.DataFrame,
    collateral_terms: pd.DataFrame,
    exposure_terms: pd.DataFrame,
    param: pd.DataFrame,
    *,
    asof: str,
    alloc_rule: str,
) -> tuple[pd.DataFrame, list[ParamWarning]]:
    """관계 그래프를 연결 성분 단위로 풀어 `crm_allocation` 원장을 만든다.

    `alloc_rule`은 기본값이 없다. 넘기지 않으면 TypeError로 멈춘다.

    반환은 (원장, 파라미터 경고 목록)이다. 계수 원장의 칸이 비어 있으면 엔진은
    그 조정을 건너뛰고 경고를 남긴다. 조용히 1.0을 쓰면 "조정을 안 했다"가
    산출물에서 사라진다.
    """
    if alloc_rule not in ALLOC_RULES:
        raise ValueError(f"알 수 없는 배분규칙: {alloc_rule!r} (가능: {ALLOC_RULES})")

    warns: list[ParamWarning] = []
    hfx = param_value(param, "ccy_mismatch_haircut")
    min_orig = param_value(param, "maturity_min_original_years")
    min_resid = param_value(param, "maturity_min_residual_years")
    offset = param_value(param, "maturity_offset_years")
    cap_years = param_value(param, "maturity_cap_years")

    if hfx is None:
        warns.append(ParamWarning(
            model="crm_allocation", scope="전체", param="ccy_mismatch_haircut",
            reason="계수가 비어 있어 통화불일치 차감을 건너뛴다"))
    maturity_ready = None not in (min_orig, min_resid, offset, cap_years)
    if not maturity_ready:
        warns.append(ParamWarning(
            model="crm_allocation", scope="전체", param="maturity_mismatch",
            reason="계수가 비어 있어 만기불일치 조정을 건너뛴다"))

    lk = links[links["asof"] == asof].copy()
    ct = collateral_terms[collateral_terms["asof"] == asof].set_index("collateral_id")
    et = exposure_terms[exposure_terms["asof"] == asof].set_index("exposure_id")

    missing_c = sorted(set(lk["collateral_id"]) - set(ct.index))
    missing_e = sorted(set(lk["exposure_id"]) - set(et.index))
    if missing_c or missing_e:
        raise KeyError(
            f"계약조건 원장에 없는 참조. 담보 {missing_c[:3]} 익스포저 {missing_e[:3]}")

    exp_terms = {
        e: {"ead": float(et.at[e, "ead"]),
            "he": float(et.at[e, "exposure_haircut"]),
            "maturity_years": float(et.at[e, "maturity_years"]),
            "risk_weight": float(et.at[e, "risk_weight"]),
            "ccy": str(et.at[e, "ccy"])}
        for e in et.index
    }

    # ---- 1. 담보 단위 적격성 조정 (배분 전에 끝낸다) ----------------------
    nbr_e: dict[str, list[str]] = {}
    for cid, eid in zip(lk["collateral_id"], lk["exposure_id"]):
        nbr_e.setdefault(cid, []).append(eid)

    c_adj: dict[str, float] = {}
    hfx_of: dict[str, float] = {}
    mmf_of: dict[str, float] = {}
    hc_of: dict[str, float] = {}
    for cid, linked in nbr_e.items():
        mv = float(ct.at[cid, "market_value"])
        hc = float(ct.at[cid, "haircut"])
        ccy = str(ct.at[cid, "ccy"])
        mismatch = any(exp_terms[e]["ccy"] != ccy for e in linked)
        h_fx = (hfx if (mismatch and hfx is not None) else 0.0)

        if maturity_ready:
            orig = ct.at[cid, "original_maturity_years"]
            resid = ct.at[cid, "residual_maturity_years"]
            if pd.isna(orig) or pd.isna(resid):
                mmf = 1.0
                warns.append(ParamWarning(
                    model="crm_allocation", scope=f"담보 {cid}",
                    param="collateral_maturity",
                    reason="담보 만기가 비어 있어 만기불일치 조정을 건너뛴다"))
            elif float(orig) < min_orig or float(resid) <= min_resid:
                # 100.에 따라 원만기 1년 미만이거나 잔존만기 3개월 이하면 불인정
                mmf = 0.0
            else:
                big_t = min(cap_years,
                            max(exp_terms[e]["maturity_years"] for e in linked))
                if float(resid) >= big_t or big_t <= offset:
                    mmf = 1.0          # 만기불일치가 없다
                else:
                    mmf = (float(resid) - offset) / (big_t - offset)
                    mmf = float(min(max(mmf, 0.0), 1.0))
        else:
            mmf = 1.0

        hc_of[cid] = hc
        hfx_of[cid] = h_fx
        mmf_of[cid] = mmf
        c_adj[cid] = max(0.0, mv * (1.0 - hc - h_fx)) * mmf

    e_adj = {e: exp_terms[e]["ead"] * (1.0 + exp_terms[e]["he"]) for e in exp_terms}

    # ---- 2. 연결 성분 단위 배분 ------------------------------------------
    link_cap: dict[tuple[str, str], float] = {}
    prio: dict[tuple[str, str], int] = {}
    cov: dict[tuple[str, str], float] = {}
    pool_of: dict[tuple[str, str], str] = {}
    rel_of: dict[tuple[str, str], str] = {}
    by_pool: dict[str, list[tuple[str, str]]] = {}
    for row in lk.itertuples(index=False):
        key = (row.collateral_id, row.exposure_id)
        cov[key] = float(row.coverage_ratio)
        link_cap[key] = float(row.coverage_ratio) * c_adj[row.collateral_id]
        prio[key] = int(row.priority)
        pool_of[key] = str(row.pool_id)
        rel_of[key] = str(row.relation_type)
        by_pool.setdefault(str(row.pool_id), []).append(key)

    alloc = {k: 0.0 for k in link_cap}
    rem_c = dict(c_adj)
    rem_e = {e: e_adj[e] for e in e_adj}

    for pool in sorted(by_pool):
        pairs = sorted(by_pool[pool])
        if alloc_rule == "pro_rata":
            colls = sorted({c for c, _ in pairs})
            for _ in range(_MAX_ROUNDS):
                moved = 0.0
                for c in colls:
                    if rem_c[c] <= _EPS:
                        continue
                    demand = {}
                    for e in sorted(x for cc, x in pairs if cc == c):
                        d = min(rem_e[e], link_cap[(c, e)] - alloc[(c, e)])
                        if d > _EPS:
                            demand[e] = d
                    total = sum(demand.values())
                    if total <= _EPS:
                        continue
                    give = min(rem_c[c], total)
                    for e, d in demand.items():
                        x = give * d / total
                        alloc[(c, e)] += x
                        rem_c[c] -= x
                        rem_e[e] -= x
                    moved += give
                if moved <= _EPS:
                    break
        else:
            key_fn = _order_key(alloc_rule, exp_terms)
            for e in sorted({x for _, x in pairs}, key=key_fn):
                for c in sorted((cc for cc, x in pairs if x == e),
                                key=lambda cc: (prio[(cc, e)], cc)):
                    x = min(rem_c[c], rem_e[e], link_cap[(c, e)] - alloc[(c, e)])
                    if x > _EPS:
                        alloc[(c, e)] += x
                        rem_c[c] -= x
                        rem_e[e] -= x

    # ---- 3. 원장 ---------------------------------------------------------
    rows = []
    for (c, e), amount in sorted(alloc.items()):
        rows.append({
            "asof": asof, "alloc_rule": alloc_rule,
            "collateral_id": c, "exposure_id": e,
            "pool_id": pool_of[(c, e)], "relation_type": rel_of[(c, e)],
            "collateral_value_adj": c_adj[c],
            "exposure_ead": e_adj[e],
            "allocated_amount": max(0.0, amount),
            "residual_collateral": max(0.0, rem_c[c]),
            "residual_exposure": max(0.0, rem_e[e]),
            "haircut_total": hc_of[c] + hfx_of[c],
            "ccy_mismatch_haircut": hfx_of[c],
            "maturity_mismatch_factor": mmf_of[c],
            "coverage_ratio": cov[(c, e)],
        })
    out = pd.DataFrame(rows, columns=list(ALLOCATION.column_names))
    if out.empty:
        out = out.astype({c.name: "float64" for c in ALLOCATION.columns
                          if c.dtype == "float"})
    return out, warns
