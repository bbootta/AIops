"""신용위험경감 배분의 자체 정합성 검사 (2선).

검사는 **위반을 만들면 실제로 FAIL해야** 통제다. 항등식을 다시 쓴 검사는
언제나 통과하므로 아무것도 지키지 못한다. 아래 각 함수의 docstring에
"이 검사를 FAIL시키려면 무엇이 깨져야 하는가"를 적었고,
`tests/test_crm_allocation.py`가 검사마다 위반을 주입해 FAIL이 뜨는지 확인한다.

허용오차는 절대 1e-6 KRW에 규모 비례 1e-9를 더한다. 원화 잔액은 1e8 규모라
비례항이 없으면 순수 부동소수 잔차가 위반으로 잡힌다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from risk_lib.crm.link import derive_graph
from risk_lib.validation.consistency import ConsistencyCheck, ValidationReport

__all__ = [
    "ATOL", "RTOL", "tol",
    "check_collateral_cap", "check_exposure_cap", "check_link_cap",
    "check_ead_conservation", "check_pool_conservation",
    "check_relation_type", "check_pool_partition",
    "check_unit_columns_uniform", "check_rule_sensitivity",
    "check_rwa_reconciliation", "run_crm_allocation_checks",
]

ATOL = 1e-6
RTOL = 1e-9


def tol(scale) -> np.ndarray | float:
    """규모 비례 허용오차."""
    return ATOL + RTOL * np.abs(scale)


def _pass(report, name, detail, metric=0.0):
    report.add(ConsistencyCheck(name, "PASS", detail, metric=metric))


def _fail(report, name, detail, metric):
    report.add(ConsistencyCheck(name, "FAIL", detail, metric=float(metric)))


# ---------------------------------------------------------------- 보존식

def check_collateral_cap(alloc: pd.DataFrame, report: ValidationReport) -> None:
    """담보 초과배분 금지. Σ_i a[i][j] ≤ C_adj[j].

    FAIL 조건: 배분 엔진이 한 담보를 여러 익스포저에 나누면서 잔여를 차감하지
    않으면(예: 링크별로 min(C_adj, E)를 독립 계산) 합이 담보가치를 넘는다.
    1:1만 있을 때는 절대 드러나지 않고 1:N에서만 드러나는 결함이다.
    """
    if alloc.empty:
        return
    g = alloc.groupby(["asof", "alloc_rule", "collateral_id"], as_index=False).agg(
        allocated=("allocated_amount", "sum"),
        c_adj=("collateral_value_adj", "max"))
    over = g[g["allocated"] > g["c_adj"] + tol(g["c_adj"])]
    if len(over):
        worst = float((over["allocated"] - over["c_adj"]).max())
        _fail(report, "crm_alloc_collateral_cap",
              f"담보 {len(over)}건에서 배분합이 조정 담보가치를 초과 "
              f"(최대 {worst:,.2f} KRW)", worst)
    else:
        _pass(report, "crm_alloc_collateral_cap",
              f"담보 {len(g)}건 전건 배분합 ≤ 조정 담보가치")


def check_exposure_cap(alloc: pd.DataFrame, report: ValidationReport) -> None:
    """익스포저 초과충당 금지. Σ_j a[i][j] ≤ E_adj[i].

    FAIL 조건: M:1에서 담보 여러 건이 같은 익스포저를 덮을 때 각 담보가 서로의
    배분을 모르면 합이 익스포저액을 넘는다. [별표 3] 62.의 E* = max{0, ...}는
    담보가 익스포저를 넘어도 초과분에 경감효과를 주지 않는다는 뜻이다.
    """
    if alloc.empty:
        return
    g = alloc.groupby(["asof", "alloc_rule", "exposure_id"], as_index=False).agg(
        allocated=("allocated_amount", "sum"),
        e_adj=("exposure_ead", "max"))
    over = g[g["allocated"] > g["e_adj"] + tol(g["e_adj"])]
    if len(over):
        worst = float((over["allocated"] - over["e_adj"]).max())
        _fail(report, "crm_alloc_exposure_cap",
              f"익스포저 {len(over)}건에서 배분합이 조정 익스포저액을 초과 "
              f"(최대 {worst:,.2f} KRW)", worst)
    else:
        _pass(report, "crm_alloc_exposure_cap",
              f"익스포저 {len(g)}건 전건 배분합 ≤ 조정 익스포저액")


def check_link_cap(alloc: pd.DataFrame, report: ValidationReport) -> None:
    """링크별 설정 비율 상한. a[i][j] ≤ coverage_ratio × C_adj[j].

    FAIL 조건: 엔진이 `coverage_ratio`를 읽지 않고 담보 전액을 한 링크에 몰면
    계약상 설정하지 않은 담보를 인정한 것이 된다.
    """
    if alloc.empty:
        return
    cap = alloc["coverage_ratio"].to_numpy(float) * \
        alloc["collateral_value_adj"].to_numpy(float)
    amt = alloc["allocated_amount"].to_numpy(float)
    bad = amt > cap + tol(cap)
    if bad.any():
        worst = float((amt - cap)[bad].max())
        _fail(report, "crm_alloc_link_cap",
              f"링크 {int(bad.sum())}건에서 설정 비율 상한 초과 "
              f"(최대 {worst:,.2f} KRW)", worst)
    else:
        _pass(report, "crm_alloc_link_cap", f"링크 {len(alloc)}건 전건 상한 이내")


def check_ead_conservation(alloc: pd.DataFrame, exposure_terms: pd.DataFrame,
                           report: ValidationReport) -> None:
    """총량 보존. 보전분 + 무보전분 = 조정 익스포저액, 그리고 조정 익스포저액이
    익스포저 조건 원장의 E×(1+He)와 같은가.

    FAIL 조건: 배분액과 잔여를 따로 계산해 둘이 어긋나면 잡힌다. 두 번째 대조는
    **다른 원장**(`crm_exposure_terms`)과 맞추므로, 배분 원장 안에서만 아귀가
    맞는 자기충족적 숫자를 걸러낸다.
    """
    if alloc.empty:
        return
    g = alloc.groupby(["asof", "alloc_rule", "exposure_id"], as_index=False).agg(
        secured=("allocated_amount", "sum"),
        residual=("residual_exposure", "max"),
        e_adj=("exposure_ead", "max"))
    gap = (g["secured"] + g["residual"] - g["e_adj"]).abs()
    bad = g[gap > tol(g["e_adj"])]
    if len(bad):
        _fail(report, "crm_alloc_ead_conservation",
              f"익스포저 {len(bad)}건에서 보전분+무보전분 ≠ 조정 익스포저액 "
              f"(최대 괴리 {float(gap.max()):,.2f} KRW)", float(gap.max()))
        return

    et = exposure_terms.copy()
    et["expected"] = et["ead"].astype(float) * (1.0 + et["exposure_haircut"].astype(float))
    m = g.merge(et[["asof", "exposure_id", "expected"]],
                on=["asof", "exposure_id"], how="left")
    miss = int(m["expected"].isna().sum())
    if miss:
        _fail(report, "crm_alloc_ead_conservation",
              f"배분 원장의 익스포저 {miss}건이 익스포저 조건 원장에 없다", miss)
        return
    gap2 = (m["e_adj"] - m["expected"]).abs()
    bad2 = gap2 > tol(m["expected"])
    if bad2.any():
        _fail(report, "crm_alloc_ead_conservation",
              f"익스포저 {int(bad2.sum())}건에서 조정 익스포저액이 조건 원장의 "
              f"E×(1+He)와 불일치 (최대 {float(gap2.max()):,.2f} KRW)",
              float(gap2.max()))
    else:
        _pass(report, "crm_alloc_ead_conservation",
              f"익스포저 {len(g)}건 총량 보존 및 조건 원장 일치")


def check_pool_conservation(alloc: pd.DataFrame, report: ValidationReport) -> None:
    """연결 성분별 보존. 풀 배분합 ≤ min(Σ C_adj, Σ E_adj), 담보 잔여 일치.

    FAIL 조건: 성분을 잘못 잘라 같은 담보를 두 풀에서 각각 쓰면 풀 합계가
    공급을 넘는다. 담보 잔여 대조는 `residual_collateral`이 배분액과 따로
    계산돼 어긋나는 경우를 잡는다.
    """
    if alloc.empty:
        return
    keys = ["asof", "alloc_rule", "pool_id"]
    supply = (alloc.drop_duplicates(keys + ["collateral_id"])
              .groupby(keys, as_index=False)["collateral_value_adj"].sum()
              .rename(columns={"collateral_value_adj": "c_sum"}))
    demand = (alloc.drop_duplicates(keys + ["exposure_id"])
              .groupby(keys, as_index=False)["exposure_ead"].sum()
              .rename(columns={"exposure_ead": "e_sum"}))
    used = alloc.groupby(keys, as_index=False)["allocated_amount"].sum()
    m = used.merge(supply, on=keys).merge(demand, on=keys)
    limit = np.minimum(m["c_sum"], m["e_sum"])
    over = m[m["allocated_amount"] > limit + tol(limit)]
    if len(over):
        worst = float((over["allocated_amount"] - np.minimum(
            over["c_sum"], over["e_sum"])).max())
        _fail(report, "crm_alloc_pool_conservation",
              f"풀 {len(over)}개에서 배분합이 공급·수요 하한을 초과 "
              f"(최대 {worst:,.2f} KRW)", worst)
        return

    gc = alloc.groupby(["asof", "alloc_rule", "collateral_id"], as_index=False).agg(
        allocated=("allocated_amount", "sum"),
        c_adj=("collateral_value_adj", "max"),
        residual=("residual_collateral", "max"))
    gap = (gc["allocated"] + gc["residual"] - gc["c_adj"]).abs()
    bad = gap > tol(gc["c_adj"])
    if bad.any():
        _fail(report, "crm_alloc_pool_conservation",
              f"담보 {int(bad.sum())}건에서 배분합+담보잔여 ≠ 조정 담보가치 "
              f"(최대 {float(gap.max()):,.2f} KRW)", float(gap.max()))
    else:
        _pass(report, "crm_alloc_pool_conservation",
              f"풀 {len(m)}개 · 담보 {len(gc)}건 보존")


# ---------------------------------------------------------------- 그래프

def check_relation_type(links: pd.DataFrame, report: ValidationReport) -> None:
    """relation_type 라벨과 실제 링크 차수의 일치.

    FAIL 조건: 합성기나 수기 입력이 "이건 M:N"이라고 적었는데 실제 담보 차수가
    1이면 잡힌다. 라벨이 틀리면 케이스별 집계·화면·검증이 전부 다른 모집단을
    센다.
    """
    if links.empty:
        return
    for asof, g in links.groupby("asof", sort=True):
        deg_c = g["collateral_id"].map(g["collateral_id"].value_counts())
        deg_e = g["exposure_id"].map(g["exposure_id"].value_counts())
        expect = np.where(
            (deg_c > 1) & (deg_e > 1), "M:N",
            np.where(deg_c > 1, "1:N", np.where(deg_e > 1, "M:1", "1:1")))
        bad = int((g["relation_type"].to_numpy() != expect).sum())
        name = f"crm_link_relation_type_{asof}"
        if bad:
            _fail(report, name,
                  f"링크 {bad}건의 relation_type이 실제 차수와 불일치", bad)
        else:
            counts = pd.Series(expect).value_counts().to_dict()
            _pass(report, name,
                  f"링크 {len(g)}건 라벨 일치 (" +
                  " · ".join(f"{k} {counts.get(k, 0)}건"
                             for k in ("1:1", "1:N", "M:1", "M:N")) + ")")


def check_pool_partition(links: pd.DataFrame, report: ValidationReport) -> None:
    """pool_id가 실제 연결 성분과 같은 분할인가.

    FAIL 조건: 교차담보 풀을 성분이 아닌 다른 기준(차주·상품 등)으로 매기면
    한 성분이 두 풀로 갈리거나 두 성분이 한 풀로 합쳐진다. 갈리면 배분이
    성분 단위로 풀리지 않아 초과배분이 생긴다.
    """
    if links.empty:
        return
    for asof, g in links.groupby("asof", sort=True):
        derived = derive_graph(g)
        pairs = list(zip(g["collateral_id"].astype(str),
                         g["exposure_id"].astype(str)))
        got = {frozenset(p for p, k in zip(pairs, g["pool_id"]) if k == key)
               for key in set(g["pool_id"])}
        want = {frozenset(p for p, k in zip(pairs, derived["pool_id"]) if k == key)
                for key in set(derived["pool_id"])}
        name = f"crm_link_pool_partition_{asof}"
        if got != want:
            _fail(report, name,
                  f"pool_id 분할이 연결 성분과 다르다 "
                  f"(원장 {len(got)}개 · 성분 {len(want)}개)",
                  abs(len(got) - len(want)))
        else:
            _pass(report, name, f"연결 성분 {len(want)}개와 pool_id 분할 일치")


def check_unit_columns_uniform(alloc: pd.DataFrame,
                               report: ValidationReport) -> None:
    """같은 담보가 익스포저마다 다른 차감률을 받지 않는가.

    FAIL 조건: 적격성 조정을 배분 **뒤에** 적용하면 같은 담보의
    `haircut_total`·`maturity_mismatch_factor`·`collateral_value_adj`가 링크마다
    갈린다. [별표 3] 62.의 C(1-Hc-Hfx)는 담보 하나에 대한 값이므로 갈리면 안 된다.
    """
    if alloc.empty:
        return
    cols = ("haircut_total", "ccy_mismatch_haircut", "maturity_mismatch_factor",
            "collateral_value_adj", "residual_collateral")
    keys = ["asof", "alloc_rule", "collateral_id"]
    offenders = {}
    for col in cols:
        spread = alloc.groupby(keys)[col].agg(lambda s: float(s.max() - s.min()))
        n = int((spread > tol(alloc.groupby(keys)[col].max())).sum())
        if n:
            offenders[col] = n
    if offenders:
        _fail(report, "crm_alloc_collateral_unit_uniform",
              "담보 단위 값이 링크마다 갈린다: " +
              ", ".join(f"{k} {v}건" for k, v in offenders.items()),
              sum(offenders.values()))
    else:
        _pass(report, "crm_alloc_collateral_unit_uniform",
              f"담보 단위 컬럼 {len(cols)}개 전건 일치")


# ---------------------------------------------------------------- 규칙·RWA

def check_rule_sensitivity(alloc: pd.DataFrame, report: ValidationReport) -> None:
    """배분규칙을 바꾸면 배분이 실제로 달라지는가.

    FAIL 조건: 엔진이 `alloc_rule` 인자를 받고도 쓰지 않으면(예: 항상 pro-rata로
    분기) 모든 규칙의 배분 벡터가 같아진다. 인자만 원장에 적히고 산출은 하나인
    상태가 감독당국 관점에서 가장 나쁘다.

    비교 대상은 **규칙이 결과를 바꿀 수 있는 링크**로 좁힌다. 익스포저가 하나뿐인
    풀이나 담보가 남아도는 풀은 어떤 규칙을 써도 같은 답이 나오므로, 거기서
    같다는 것은 결함의 증거가 아니다.
    """
    name = "crm_alloc_rule_sensitivity"
    if alloc.empty:
        return
    rules = sorted(alloc["alloc_rule"].unique())
    if len(rules) < 2:
        report.add(ConsistencyCheck(
            name, "WARN",
            f"배분규칙이 {len(rules)}개뿐이라 민감도를 검증할 수 없다",
            metric=float(len(rules))))
        return

    keys = ["asof", "alloc_rule", "pool_id"]
    supply = (alloc.drop_duplicates(keys + ["collateral_id"])
              .groupby(keys, as_index=False)["collateral_value_adj"].sum())
    demand = (alloc.drop_duplicates(keys + ["exposure_id"])
              .groupby(keys, as_index=False)["exposure_ead"].sum())
    n_exp = (alloc.drop_duplicates(keys + ["exposure_id"])
             .groupby(keys, as_index=False)["exposure_id"].count()
             .rename(columns={"exposure_id": "n_exp"}))
    pools = supply.merge(demand, on=keys).merge(n_exp, on=keys)
    scarce = pools[(pools["n_exp"] >= 2)
                   & (pools["collateral_value_adj"] < pools["exposure_ead"])]
    eligible = set(zip(scarce["asof"], scarce["pool_id"]))
    if not eligible:
        report.add(ConsistencyCheck(
            name, "WARN",
            "규칙이 결과를 바꿀 수 있는 풀(익스포저 2건 이상 · 담보 부족)이 없다",
            metric=0.0))
        return

    sub = alloc[[(a, p) in eligible
                 for a, p in zip(alloc["asof"], alloc["pool_id"])]]
    vectors = {}
    for rule in rules:
        r = sub[sub["alloc_rule"] == rule].sort_values(
            ["asof", "collateral_id", "exposure_id"])
        vectors[rule] = tuple(np.round(
            r["allocated_amount"].to_numpy(float), 3).tolist())
    if len(set(vectors.values())) == 1:
        _fail(report, name,
              f"규칙 {len(rules)}종이 대상 링크 {len(vectors[rules[0]])}건에서 "
              "완전히 같은 배분을 낸다. alloc_rule이 산출에 반영되지 않는다", 0.0)
        return
    same = [f"{a}={b}" for i, a in enumerate(rules) for b in rules[i + 1:]
            if vectors[a] == vectors[b]]
    detail = (f"규칙 {len(rules)}종 · 대상 링크 {len(vectors[rules[0]])}건에서 배분이 갈린다")
    if same:
        report.add(ConsistencyCheck(name, "WARN",
                                    detail + f" (다만 동일 쌍: {', '.join(same)})",
                                    metric=float(len(same))))
    else:
        _pass(report, name, detail, metric=float(len(rules)))


def check_rwa_reconciliation(alloc: pd.DataFrame, exposure_terms: pd.DataFrame,
                             report: ValidationReport,
                             rwa_result: pd.DataFrame | None = None) -> None:
    """RWA 대사. 배분 결과로 재산출한 신용 RWA가 설명 가능한 차이만 갖는가.

    세 다리로 본다. 무엇이 깨져야 FAIL하는지가 다리마다 다르다.

    1. 위험가중 항등: (E_adj - 무보전 - 보전) × RW = 0. 익스포저 단위 보존이
       깨지면 FAIL한다. 총량 검사와 달리 위험가중치가 곱해지므로 익스포저 A를
       과대·B를 과소로 상쇄해 총액만 맞춘 조작도 두 익스포저의 위험가중치가
       다르면 남는다.
    2. CRM 전 RWA가 기존 산출(`rwa_result`)과 같은가. 배분 원장·조건 원장·
       RWA 원장 셋을 맞물리므로, 조건 원장의 위험가중치나 모집단이 기존 산출과
       어긋나면 FAIL한다. 이 다리가 없으면 배분 원장 안에서만 아귀가 맞는
       숫자가 통과한다.
    3. CRM 적용 후 RWA가 적용 전보다 크면 FAIL한다. 경감이 가중으로 뒤집히는
       부호 오류를 잡는다.
    """
    name = "crm_alloc_rwa_recon"
    if alloc.empty:
        return
    g = alloc.groupby(["asof", "alloc_rule", "exposure_id"], as_index=False).agg(
        secured=("allocated_amount", "sum"),
        residual=("residual_exposure", "max"),
        e_adj=("exposure_ead", "max"))
    m = g.merge(exposure_terms[["asof", "exposure_id", "risk_weight"]],
                on=["asof", "exposure_id"], how="left")
    if m["risk_weight"].isna().any():
        _fail(report, name,
              f"익스포저 {int(m['risk_weight'].isna().sum())}건의 위험가중치를 "
              "조건 원장에서 찾지 못했다", int(m["risk_weight"].isna().sum()))
        return

    rw = m["risk_weight"].to_numpy(float)
    before = m["e_adj"].to_numpy(float) * rw
    after = m["residual"].to_numpy(float) * rw
    reduction = m["secured"].to_numpy(float) * rw
    gap = np.abs(before - after - reduction)
    limit = tol(before)
    if (gap > limit).any():
        _fail(report, name,
              f"익스포저 {int((gap > limit).sum())}건에서 RWA 절감액이 배분액과 "
              f"맞지 않는다 (최대 {float(gap.max()):,.2f} KRW)", float(gap.max()))
        return
    if (after > before + tol(before)).any():
        _fail(report, name, "CRM 적용 후 RWA가 적용 전보다 큰 익스포저가 있다",
              float((after - before).max()))
        return

    detail = (f"CRM 전 RWA {before.sum():,.0f} → 후 {after.sum():,.0f} · "
              f"절감 {reduction.sum():,.0f} KRW (규칙 "
              f"{len(alloc['alloc_rule'].unique())}종 합산)")
    if rwa_result is not None and len(rwa_result):
        base = rwa_result.drop_duplicates(subset=["exposure_id"])
        base = base[base["exposure_id"].isin(set(m["exposure_id"]))]
        # 기존 산출은 규칙 구분이 없으므로 규칙 1종만 뽑아 대조한다.
        one = m[m["alloc_rule"] == sorted(m["alloc_rule"].unique())[0]]
        theirs = float(base["rwa"].sum())
        ours = float((one["e_adj"].to_numpy(float)
                      * one["risk_weight"].to_numpy(float)).sum())
        if abs(theirs - ours) > tol(max(abs(theirs), abs(ours))):
            _fail(report, name,
                  f"CRM 전 RWA가 기존 산출과 다르다 "
                  f"(기존 {theirs:,.0f} · 조건 원장 {ours:,.0f} KRW)",
                  abs(theirs - ours))
            return
        detail += f" · 기존 산출 대조 일치 ({theirs:,.0f} KRW)"
    _pass(report, name, detail, metric=float(reduction.sum()))


# ---------------------------------------------------------------- 묶음

def run_crm_allocation_checks(
    *,
    links: pd.DataFrame,
    alloc: pd.DataFrame,
    exposure_terms: pd.DataFrame,
    rwa_result: pd.DataFrame | None = None,
    report: ValidationReport | None = None,
) -> ValidationReport:
    """CRM 배분 검사 묶음. 기존 리포트에 이어 붙이려면 `report`를 넘긴다."""
    rep = report if report is not None else ValidationReport()
    check_relation_type(links, rep)
    check_pool_partition(links, rep)
    check_collateral_cap(alloc, rep)
    check_exposure_cap(alloc, rep)
    check_link_cap(alloc, rep)
    check_ead_conservation(alloc, exposure_terms, rep)
    check_pool_conservation(alloc, rep)
    check_unit_columns_uniform(alloc, rep)
    check_rule_sensitivity(alloc, rep)
    check_rwa_reconciliation(alloc, exposure_terms, rep, rwa_result)
    return rep
