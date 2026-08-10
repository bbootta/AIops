"""신용위험경감 배분 (1:1 · 1:N · M:1 · M:N).

검사마다 두 벌을 쓴다: 정상 케이스가 통과하는가, 그리고 **위반을 주입하면
실제로 FAIL이 뜨는가**. 뒤쪽이 없으면 그 검사는 항등식일 수 있고, 항등식은
아무것도 지키지 못한다.
"""

from __future__ import annotations

import types

import numpy as np
import pandas as pd
import pytest

from risk_lib.crm import (
    ALLOC_RULES, ALLOCATION, COLLATERAL_LINK, COLLATERAL_TERMS, EXPOSURE_TERMS,
    MITIGATION_PARAM, allocate_crm, build_baseline_links,
    build_crm_link_universe, build_crm_mitigation_param, derive_graph,
)
from risk_lib.crm import consistency as cc
from risk_lib.crm.params import param_value
from risk_lib.datamodel.decompose import decompose
from risk_lib.datamodel.materialize import materialize_rwa
from risk_lib.datamodel.spec import check_refs, validate
from risk_lib.data_gen import generate_portfolio
from risk_lib.validation.consistency import ValidationReport

ASOF = "2026-06-30"
SEED = 42


# ---------------------------------------------------------------- 픽스처

@pytest.fixture(scope="module")
def base_tables():
    p = generate_portfolio(seed=SEED)
    base = decompose(p, asof=ASOF, seed=SEED)
    rwa = materialize_rwa(types.SimpleNamespace(meta={"asof": ASOF}), p, base)
    return base, rwa["rwa_result"]


@pytest.fixture(scope="module")
def universe(base_tables):
    base, rwa = base_tables
    return build_crm_link_universe(base["rdm_exposure"], base["rdm_collateral"],
                                   rwa, asof=ASOF, seed=SEED)


@pytest.fixture(scope="module")
def param():
    return build_crm_mitigation_param()


@pytest.fixture(scope="module")
def allocations(universe, param):
    frames = []
    for rule in ALLOC_RULES:
        df, _ = allocate_crm(universe["crm_collateral_link"],
                             universe["crm_collateral_terms"],
                             universe["crm_exposure_terms"], param,
                             asof=ASOF, alloc_rule=rule)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def _report() -> ValidationReport:
    return ValidationReport()


def _status(rep: ValidationReport, prefix: str) -> str:
    hits = [c for c in rep.checks if c.name.startswith(prefix)]
    assert hits, f"{prefix} 검사가 등록되지 않았다"
    return "FAIL" if any(c.status == "FAIL" for c in hits) else hits[0].status


# ---------------------------------------------------------------- 계수 원장

def test_param_ledger_matches_spec(param):
    assert validate(param, MITIGATION_PARAM) == []


def test_regulatory_params_are_primary_sourced(param):
    """[별표 3] 원문에서 읽은 값은 원문확인이어야 한다."""
    confirmed = param[param["evidence_status"] == "원문확인"]
    assert set(confirmed["param_code"]) == {
        "ccy_mismatch_haircut", "maturity_min_original_years",
        "maturity_min_residual_years", "maturity_offset_years",
        "maturity_cap_years"}
    assert param_value(param, "ccy_mismatch_haircut") == pytest.approx(0.08)
    assert param_value(param, "maturity_offset_years") == pytest.approx(0.25)
    assert param_value(param, "maturity_cap_years") == pytest.approx(5.0)


def test_default_alloc_rule_is_empty_in_the_ledger(param):
    """규정이 배분 순서를 정하지 않는다는 사실이 원장에 NULL로 남아 있어야
    엔진이 규칙을 필수 인자로 받는 근거가 된다."""
    row = param[param["param_code"] == "alloc_rule_default"].iloc[0]
    assert pd.isna(row["param_value"])
    assert row["evidence_status"] == "재량·미규정"


def test_alloc_rule_has_no_default(universe, param):
    with pytest.raises(TypeError):
        allocate_crm(universe["crm_collateral_link"],
                     universe["crm_collateral_terms"],
                     universe["crm_exposure_terms"], param, asof=ASOF)
    with pytest.raises(ValueError):
        allocate_crm(universe["crm_collateral_link"],
                     universe["crm_collateral_terms"],
                     universe["crm_exposure_terms"], param,
                     asof=ASOF, alloc_rule="아무거나")


def test_missing_param_row_raises_not_silently_skips(param):
    """행 자체가 없으면 원장 결함이므로 멈춘다. NULL(정하지 않음)과 다른 사건이다."""
    with pytest.raises(KeyError):
        param_value(param, "존재하지_않는_계수")


# ---------------------------------------------------------------- 합성 그래프

def test_universe_matches_specs(universe, base_tables, param, allocations):
    base, _ = base_tables
    tables = dict(universe)
    tables["crm_allocation"] = allocations[allocations["alloc_rule"] == "pro_rata"]
    tables["crm_mitigation_param"] = param
    specs = {s.name: s for s in (MITIGATION_PARAM, COLLATERAL_TERMS,
                                 EXPOSURE_TERMS, COLLATERAL_LINK, ALLOCATION)}
    for name, spec in specs.items():
        assert validate(tables[name], spec) == [], name
    tables["rdm_collateral"] = base["rdm_collateral"]
    tables["rdm_exposure"] = base["rdm_exposure"]
    tables["crm_collateral_link"] = universe["crm_collateral_link"]
    assert check_refs(tables, specs) == []


def test_all_four_relation_cases_are_present(universe):
    counts = universe["crm_collateral_link"]["relation_type"].value_counts()
    for case in ("1:1", "1:N", "M:1", "M:N"):
        assert counts.get(case, 0) >= 30, f"{case} 링크가 {counts.get(case, 0)}건뿐"


def test_mn_pools_are_single_connected_components(universe):
    """교차담보 풀이 실제로 연결 성분을 이루는지 BFS로 직접 확인한다.

    유도 함수(union-find)와 다른 경로로 세야 유도 자체의 결함이 잡힌다.
    """
    lk = universe["crm_collateral_link"]
    mn_pools = sorted(set(lk.loc[lk["relation_type"] == "M:N", "pool_id"]))
    assert len(mn_pools) >= 30
    for pool in mn_pools[:50]:
        g = lk[lk["pool_id"] == pool]
        adj: dict[str, set[str]] = {}
        for c, e in zip(g["collateral_id"], g["exposure_id"]):
            adj.setdefault(f"C:{c}", set()).add(f"E:{e}")
            adj.setdefault(f"E:{e}", set()).add(f"C:{c}")
        start = next(iter(adj))
        seen, stack = {start}, [start]
        while stack:
            for nxt in adj[stack.pop()]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        assert seen == set(adj), f"{pool}이 연결 성분 하나가 아니다"


def test_universe_is_deterministic(base_tables):
    base, rwa = base_tables
    a = build_crm_link_universe(base["rdm_exposure"], base["rdm_collateral"],
                                rwa, asof=ASOF, seed=SEED)
    b = build_crm_link_universe(base["rdm_exposure"], base["rdm_collateral"],
                                rwa, asof=ASOF, seed=SEED)
    for key in a:
        pd.testing.assert_frame_equal(a[key], b[key])
    c = build_crm_link_universe(base["rdm_exposure"], base["rdm_collateral"],
                                rwa, asof=ASOF, seed=SEED + 1)
    assert not a["crm_collateral_terms"].equals(c["crm_collateral_terms"])


def test_relation_type_is_derived_from_the_graph_not_the_label():
    """합성기가 붙인 라벨을 믿지 않는다는 것이 유도의 요점이다."""
    links = pd.DataFrame({
        "asof": ASOF,
        "collateral_id": ["C1", "C1", "C2"],
        "exposure_id": ["E1", "E2", "E3"],
        "relation_type": ["M:N", "M:N", "M:N"],     # 전부 틀린 라벨
        "pool_id": ["POOLX", "POOLX", "POOLX"],     # 실제로는 두 성분이다
        "priority": [1, 2, 1],
        "coverage_ratio": [1.0, 1.0, 1.0],
        "source": "synthetic",
    })
    out = derive_graph(links)
    assert list(out["relation_type"]) == ["1:N", "1:N", "1:1"]
    assert out["pool_id"].nunique() == 2


def test_relation_type_is_derived_per_asof():
    """기준일마다 따로 유도해야 한다.

    같은 담보-익스포저 쌍이 두 기준일에 각각 1행씩 있으면 기준일 안에서는
    1:1이다. 기준일을 섞어 차수를 세면 담보 차수·익스포저 차수가 모두 2가 되어
    M:N으로 유도되고 두 기준일이 한 풀로 합쳐진다. 배분은 풀 단위로 풀리므로
    그 상태로는 다른 기준일의 담보가 서로의 배분을 깎는다.
    """
    links = pd.DataFrame({
        "asof": ["2026-03-31", "2026-06-30"],
        "collateral_id": ["C1", "C1"],
        "exposure_id": ["E1", "E1"],
        "priority": [1, 1],
        "coverage_ratio": [1.0, 1.0],
        "source": "synthetic",
    })
    out = derive_graph(links)
    assert list(out["relation_type"]) == ["1:1", "1:1"]
    # 기준일별로 성분을 매기므로 두 행은 서로 다른 (asof, pool_id) 키를 갖는다
    assert out[["asof", "pool_id"]].drop_duplicates().shape[0] == 2

    # 두 검사 모두 기준일마다 1건씩 등록하므로 2기준일 × 2검사 = 4건이다
    rep = _report()
    cc.check_relation_type(out, rep)
    cc.check_pool_partition(out, rep)
    assert [c.status for c in rep.checks] == ["PASS"] * 4


# ---------------------------------------------------------------- 손계산 케이스

def _tiny(pairs, *, coll, exp, coverage=None, priority=None):
    """손계산용 소형 우주. pairs는 (담보, 익스포저) 목록이다."""
    links = pd.DataFrame({
        "asof": ASOF,
        "collateral_id": [c for c, _ in pairs],
        "exposure_id": [e for _, e in pairs],
        "priority": priority or [1] * len(pairs),
        "coverage_ratio": coverage or [1.0] * len(pairs),
        "source": "synthetic",
    })
    links = derive_graph(links)[list(COLLATERAL_LINK.column_names)]
    ct = pd.DataFrame([{
        "asof": ASOF, "collateral_id": cid, "collateral_type": "cash",
        "ccy": v.get("ccy", "KRW"), "market_value": v["mv"],
        "haircut": v.get("hc", 0.0),
        "original_maturity_years": v.get("orig", 10.0),
        "residual_maturity_years": v.get("resid", 10.0),
        "source": "synthetic"} for cid, v in coll.items()])
    et = pd.DataFrame([{
        "asof": ASOF, "exposure_id": eid, "ccy": v.get("ccy", "KRW"),
        "ead": v["ead"], "exposure_haircut": 0.0,
        "maturity_years": v.get("maturity", 3.0),
        "risk_weight": v.get("rw", 1.0), "source": "synthetic"}
        for eid, v in exp.items()])
    return links, ct, et


def test_one_to_one_is_capped_by_both_sides(param):
    """1:1 케이스. 담보가 익스포저보다 크면 익스포저에서 잘린다([별표 3] 62. max{0,…})."""
    links, ct, et = _tiny([("C1", "E1"), ("C2", "E2")],
                          coll={"C1": {"mv": 300.0}, "C2": {"mv": 50.0}},
                          exp={"E1": {"ead": 100.0}, "E2": {"ead": 100.0}})
    out, _ = allocate_crm(links, ct, et, param, asof=ASOF, alloc_rule="pro_rata")
    got = dict(zip(out["collateral_id"], out["allocated_amount"]))
    assert got["C1"] == pytest.approx(100.0)     # 익스포저에서 잘린다
    assert got["C2"] == pytest.approx(50.0)      # 담보에서 잘린다


def test_one_to_many_splits_a_single_collateral(param):
    """1:N 케이스. 담보 1건이 익스포저 3건을 덮어도 배분합은 담보가치를 못 넘는다."""
    links, ct, et = _tiny([("C1", "E1"), ("C1", "E2"), ("C1", "E3")],
                          coll={"C1": {"mv": 120.0}},
                          exp={e: {"ead": 100.0} for e in ("E1", "E2", "E3")})
    out, _ = allocate_crm(links, ct, et, param, asof=ASOF, alloc_rule="pro_rata")
    assert out["allocated_amount"].sum() == pytest.approx(120.0)
    # 잔여 필요액이 같으므로 균등 분할된다
    assert out["allocated_amount"].to_numpy() == pytest.approx([40.0] * 3)


def test_many_to_one_stacks_collaterals_on_one_exposure(param):
    """M:1 케이스. 담보 3건 합이 익스포저를 넘어도 초과분은 인정되지 않는다."""
    links, ct, et = _tiny([("C1", "E1"), ("C2", "E1"), ("C3", "E1")],
                          coll={c: {"mv": 60.0} for c in ("C1", "C2", "C3")},
                          exp={"E1": {"ead": 100.0}},
                          priority=[1, 2, 3])
    out, _ = allocate_crm(links, ct, et, param, asof=ASOF,
                          alloc_rule="risk_weight_desc")
    assert out["allocated_amount"].sum() == pytest.approx(100.0)
    got = dict(zip(out["collateral_id"], out["allocated_amount"]))
    assert got["C1"] == pytest.approx(60.0)   # 선순위부터 채운다
    assert got["C2"] == pytest.approx(40.0)
    assert got["C3"] == pytest.approx(0.0)


def test_many_to_many_solves_per_connected_component(param):
    """M:N 케이스. 사다리로 얽힌 풀에서도 양쪽 보존식이 모두 성립한다."""
    pairs = [("C1", "E1"), ("C1", "E2"), ("C2", "E2"), ("C2", "E3"),
             ("C3", "E3"), ("C3", "E1")]
    links, ct, et = _tiny(pairs,
                          coll={c: {"mv": 90.0} for c in ("C1", "C2", "C3")},
                          exp={e: {"ead": 100.0} for e in ("E1", "E2", "E3")})
    assert set(links["relation_type"]) == {"M:N"}
    assert links["pool_id"].nunique() == 1
    out, _ = allocate_crm(links, ct, et, param, asof=ASOF, alloc_rule="pro_rata")
    per_c = out.groupby("collateral_id")["allocated_amount"].sum()
    per_e = out.groupby("exposure_id")["allocated_amount"].sum()
    assert (per_c <= 90.0 + 1e-9).all()
    assert (per_e <= 100.0 + 1e-9).all()
    assert out["allocated_amount"].sum() == pytest.approx(270.0)


def test_risk_weight_desc_serves_the_high_risk_exposure_first(param):
    links, ct, et = _tiny([("C1", "E1"), ("C1", "E2")],
                          coll={"C1": {"mv": 100.0}},
                          exp={"E1": {"ead": 100.0, "rw": 0.5},
                               "E2": {"ead": 100.0, "rw": 1.5}})
    out, _ = allocate_crm(links, ct, et, param, asof=ASOF,
                          alloc_rule="risk_weight_desc")
    got = dict(zip(out["exposure_id"], out["allocated_amount"]))
    assert got["E2"] == pytest.approx(100.0)
    assert got["E1"] == pytest.approx(0.0)


def test_maturity_asc_serves_the_short_exposure_first(param):
    links, ct, et = _tiny([("C1", "E1"), ("C1", "E2")],
                          coll={"C1": {"mv": 100.0}},
                          exp={"E1": {"ead": 100.0, "maturity": 4.0},
                               "E2": {"ead": 100.0, "maturity": 1.0}})
    out, _ = allocate_crm(links, ct, et, param, asof=ASOF,
                          alloc_rule="maturity_asc")
    got = dict(zip(out["exposure_id"], out["allocated_amount"]))
    assert got["E2"] == pytest.approx(100.0)
    assert got["E1"] == pytest.approx(0.0)


# ---------------------------------------------------------------- 적격성 조정

def test_ccy_mismatch_haircut_follows_the_regulation(param):
    """[별표 3] 65.나. 통화가 다르면 Hfx 8%."""
    links, ct, et = _tiny([("C1", "E1"), ("C2", "E2")],
                          coll={"C1": {"mv": 100.0, "ccy": "USD"},
                                "C2": {"mv": 100.0, "ccy": "KRW"}},
                          exp={"E1": {"ead": 500.0}, "E2": {"ead": 500.0}})
    out, _ = allocate_crm(links, ct, et, param, asof=ASOF, alloc_rule="pro_rata")
    got = out.set_index("collateral_id")
    assert got.at["C1", "ccy_mismatch_haircut"] == pytest.approx(0.08)
    assert got.at["C1", "allocated_amount"] == pytest.approx(92.0)
    assert got.at["C2", "ccy_mismatch_haircut"] == pytest.approx(0.0)
    assert got.at["C2", "allocated_amount"] == pytest.approx(100.0)


def test_one_collateral_gets_one_haircut_across_exposures(param):
    """규약 4. 적격성 조정은 배분 전에 담보 단위로 끝난다. 통화가 다른
    익스포저가 하나라도 섞이면 그 담보 전체에 Hfx를 적용한다(보수적)."""
    links, ct, et = _tiny([("C1", "E1"), ("C1", "E2")],
                          coll={"C1": {"mv": 100.0, "ccy": "KRW"}},
                          exp={"E1": {"ead": 500.0, "ccy": "KRW"},
                               "E2": {"ead": 500.0, "ccy": "USD"}})
    out, _ = allocate_crm(links, ct, et, param, asof=ASOF, alloc_rule="pro_rata")
    assert out["haircut_total"].to_numpy() == pytest.approx([0.08, 0.08])
    assert out["allocated_amount"].sum() == pytest.approx(92.0)


def test_maturity_mismatch_formula(param):
    """[별표 3] 101. Pa = P × (t-0.25)/(T-0.25), t=Min[T, 담보 잔존], T=Min[5, 익스포저 잔존]."""
    links, ct, et = _tiny([("C1", "E1")],
                          coll={"C1": {"mv": 100.0, "orig": 3.0, "resid": 2.0}},
                          exp={"E1": {"ead": 500.0, "maturity": 4.0}})
    out, _ = allocate_crm(links, ct, et, param, asof=ASOF, alloc_rule="pro_rata")
    expected = (2.0 - 0.25) / (4.0 - 0.25)
    assert out.at[0, "maturity_mismatch_factor"] == pytest.approx(expected)
    assert out.at[0, "allocated_amount"] == pytest.approx(100.0 * expected)


def test_maturity_cap_is_five_years(param):
    """T는 5년에서 잘린다. 익스포저 잔존 8년이어도 T=5."""
    links, ct, et = _tiny([("C1", "E1")],
                          coll={"C1": {"mv": 100.0, "orig": 3.0, "resid": 2.0}},
                          exp={"E1": {"ead": 500.0, "maturity": 8.0}})
    out, _ = allocate_crm(links, ct, et, param, asof=ASOF, alloc_rule="pro_rata")
    assert out.at[0, "maturity_mismatch_factor"] == pytest.approx(
        (2.0 - 0.25) / (5.0 - 0.25))


def test_maturity_floors_bar_recognition(param):
    """[별표 3] 100. 원만기 1년 미만, 잔존만기 3개월 이하는 경감효과 불인정."""
    links, ct, et = _tiny([("C1", "E1"), ("C2", "E2")],
                          coll={"C1": {"mv": 100.0, "orig": 0.8, "resid": 0.5},
                                "C2": {"mv": 100.0, "orig": 3.0, "resid": 0.25}},
                          exp={"E1": {"ead": 500.0}, "E2": {"ead": 500.0}})
    out, _ = allocate_crm(links, ct, et, param, asof=ASOF, alloc_rule="pro_rata")
    assert set(out["maturity_mismatch_factor"]) == {0.0}
    assert out["allocated_amount"].sum() == pytest.approx(0.0)


def test_empty_param_skips_the_adjustment_and_warns(param):
    """계수가 비면 조용히 기본값을 쓰지 않고 경고를 남기고 건너뛴다."""
    blank = param.copy()
    blank.loc[blank["param_code"] == "ccy_mismatch_haircut", "param_value"] = np.nan
    blank.loc[blank["param_code"] == "maturity_cap_years", "param_value"] = np.nan
    links, ct, et = _tiny([("C1", "E1")],
                          coll={"C1": {"mv": 100.0, "ccy": "USD",
                                       "orig": 3.0, "resid": 2.0}},
                          exp={"E1": {"ead": 500.0, "maturity": 4.0}})
    out, warns = allocate_crm(links, ct, et, blank, asof=ASOF,
                              alloc_rule="pro_rata")
    params = {w.param for w in warns}
    assert params == {"ccy_mismatch_haircut", "maturity_mismatch"}
    assert out.at[0, "ccy_mismatch_haircut"] == 0.0
    assert out.at[0, "maturity_mismatch_factor"] == 1.0
    assert out.at[0, "allocated_amount"] == pytest.approx(100.0)


# ---------------------------------------------------------------- 1:1 회귀

def test_baseline_one_to_one_reproduces_the_existing_allocation(base_tables, param):
    """관계 원장을 rdm_collateral의 1:1 매핑으로 되돌리면 현행 산출
    (`materialize_rwa`의 rwa_crm_allocation)과 같은 배분이 나와야 한다."""
    base, _ = base_tables
    coll = base["rdm_collateral"]
    links = build_baseline_links(coll, asof=ASOF)
    assert set(links["relation_type"]) == {"1:1"}

    ct = pd.DataFrame({
        "asof": ASOF, "collateral_id": coll["collateral_id"].astype(str),
        "collateral_type": coll["collateral_type"].astype(str),
        "ccy": "KRW", "market_value": coll["market_value"].astype(float),
        "haircut": coll["haircut"].astype(float),
        "original_maturity_years": 10.0, "residual_maturity_years": 10.0,
        "source": "collateral_mgmt"})
    ex = base["rdm_exposure"]
    et = pd.DataFrame({
        "asof": ASOF, "exposure_id": ex["exposure_id"].astype(str), "ccy": "KRW",
        "ead": ex["ead"].astype(float), "exposure_haircut": 0.0,
        "maturity_years": ex["maturity"].astype(float), "risk_weight": 1.0,
        "source": "core_banking"})
    et = et[et["exposure_id"].isin(set(links["exposure_id"]))]

    out, warns = allocate_crm(links, ct, et, param, asof=ASOF,
                              alloc_rule="pro_rata")
    assert warns == []

    eligible = coll["market_value"].astype(float) * (1.0 - coll["haircut"].astype(float))
    gross = coll["exposure_id"].astype(str).map(
        ex.set_index(ex["exposure_id"].astype(str))["ead"].astype(float))
    expected = pd.Series(np.minimum(eligible, gross).to_numpy(),
                         index=coll["collateral_id"].astype(str)).sort_index()
    got = out.set_index("collateral_id")["allocated_amount"].sort_index()
    # 허용오차는 상대값으로 준다. 잔액이 1e10 규모라 절대 1e-6은 부동소수
    # 마지막 자리보다 좁아 항상 실패한다.
    pd.testing.assert_series_equal(got, expected, check_names=False, rtol=1e-12)


# ---------------------------------------------------------------- 정합성 검사

def test_all_checks_pass_on_the_clean_ledger(universe, allocations, base_tables):
    _, rwa = base_tables
    rep = cc.run_crm_allocation_checks(
        links=universe["crm_collateral_link"], alloc=allocations,
        exposure_terms=universe["crm_exposure_terms"], rwa_result=rwa)
    fails = [str(c) for c in rep.checks if c.status == "FAIL"]
    assert not fails, fails
    assert len(rep.checks) == 12


def _noop(alloc: pd.DataFrame) -> pd.DataFrame:
    """아무것도 배분하지 않는 엔진의 산출물. 잔여는 공급 그대로 적는다."""
    bad = alloc.copy()
    bad["allocated_amount"] = 0.0
    bad["residual_collateral"] = bad["collateral_value_adj"]
    bad["residual_exposure"] = bad["exposure_ead"]
    return bad


def test_conservation_checks_alone_do_not_catch_a_do_nothing_engine(
        universe, allocations, base_tables):
    """보존식이 전부 부등식(≤)이라 무배분 산출물이 그 검사들을 통과한다.

    최대성 검사가 왜 따로 필요한지가 이 사실이다. 아래 검사가 PASS를 낸다는 것
    자체를 기록으로 남긴다.
    """
    bad = _noop(allocations)
    rep = _report()
    cc.check_collateral_cap(bad, rep)
    cc.check_exposure_cap(bad, rep)
    cc.check_link_cap(bad, rep)
    cc.check_ead_conservation(bad, universe["crm_exposure_terms"], rep)
    cc.check_pool_conservation(bad, rep)
    assert [c.status for c in rep.checks] == ["PASS"] * 5


def test_maximality_fails_on_a_do_nothing_engine(allocations):
    rep = _report()
    cc.check_allocation_maximality(_noop(allocations), rep)
    assert _status(rep, "crm_alloc_maximality") == "FAIL"


def test_maximality_fails_when_one_link_is_left_unfilled(allocations):
    """연결 성분을 끝까지 풀지 않고 멈춘 상태. 링크 1건만 되돌린다."""
    bad = allocations[(allocations["alloc_rule"] == "pro_rata")
                      & (allocations["allocated_amount"] > 1.0)].copy()
    bad = bad.reset_index(drop=True)
    idx = 0
    amount = float(bad.loc[idx, "allocated_amount"])
    cid, eid = bad.loc[idx, "collateral_id"], bad.loc[idx, "exposure_id"]
    bad.loc[idx, "allocated_amount"] = 0.0
    # 잔여는 담보·익스포저 단위 값이므로 해당 담보·익스포저의 모든 행을 올린다
    bad.loc[bad["collateral_id"] == cid, "residual_collateral"] += amount
    bad.loc[bad["exposure_id"] == eid, "residual_exposure"] += amount
    rep = _report()
    cc.check_allocation_maximality(bad, rep)
    assert _status(rep, "crm_alloc_maximality") == "FAIL"


def test_maximality_passes_when_both_sides_are_exhausted(param):
    """담보가 익스포저에서 잘려 여력이 없는 정상 상태는 통과해야 한다.

    최대성 검사가 정상 산출을 FAIL시키면 쓸 수 없다.
    """
    links, ct, et = _tiny([("C1", "E1"), ("C1", "E2")],
                          coll={"C1": {"mv": 50.0}},
                          exp={"E1": {"ead": 100.0}, "E2": {"ead": 100.0}})
    out, _ = allocate_crm(links, ct, et, param, asof=ASOF, alloc_rule="pro_rata")
    rep = _report()
    cc.check_allocation_maximality(out, rep)
    assert _status(rep, "crm_alloc_maximality") == "PASS"


def test_link_completeness_fails_when_the_hard_cases_are_dropped(
        universe, allocations):
    """M:N 링크를 통째로 버린 엔진. 남은 링크만 보면 보존식은 전부 성립한다."""
    dropped = allocations[allocations["relation_type"] != "M:N"]
    assert len(dropped) < len(allocations)
    rep = _report()
    cc.check_link_completeness(universe["crm_collateral_link"], dropped, rep)
    assert _status(rep, "crm_alloc_link_completeness") == "FAIL"


def test_other_checks_alone_do_not_catch_dropped_links(
        universe, allocations, base_tables):
    """링크 누락은 최대성·완전성 두 검사 밖에서는 드러나지 않는다."""
    _, rwa = base_tables
    dropped = allocations[allocations["relation_type"] != "M:N"]
    rep = _report()
    for fn in (cc.check_collateral_cap, cc.check_exposure_cap, cc.check_link_cap,
               cc.check_pool_conservation, cc.check_unit_columns_uniform):
        fn(dropped, rep)
    cc.check_ead_conservation(dropped, universe["crm_exposure_terms"], rep)
    cc.check_rwa_reconciliation(dropped, universe["crm_exposure_terms"], rep, rwa)
    assert [c.status for c in rep.checks if c.status == "FAIL"] == []


def test_link_completeness_fails_on_a_phantom_link(universe, allocations):
    """관계 원장에 없는 링크를 배분 원장이 들고 있는 반대 방향."""
    bad = allocations.copy()
    bad.loc[bad.index[0], "collateral_id"] = "C_존재하지_않음"
    rep = _report()
    cc.check_link_completeness(universe["crm_collateral_link"], bad, rep)
    assert _status(rep, "crm_alloc_link_completeness") == "FAIL"


def test_link_completeness_fails_on_an_empty_allocation(universe):
    rep = _report()
    cc.check_link_completeness(universe["crm_collateral_link"],
                               pd.DataFrame(columns=list(ALLOCATION.column_names)),
                               rep)
    assert _status(rep, "crm_alloc_link_completeness") == "FAIL"


def test_collateral_cap_fails_on_over_allocation(allocations):
    bad = allocations.copy()
    bad.loc[0, "allocated_amount"] = bad.loc[0, "collateral_value_adj"] * 2 + 1.0
    rep = _report()
    cc.check_collateral_cap(bad, rep)
    assert _status(rep, "crm_alloc_collateral_cap") == "FAIL"


def test_exposure_cap_fails_on_over_coverage(allocations):
    bad = allocations.copy()
    bad.loc[0, "allocated_amount"] = bad.loc[0, "exposure_ead"] * 2 + 1.0
    rep = _report()
    cc.check_exposure_cap(bad, rep)
    assert _status(rep, "crm_alloc_exposure_cap") == "FAIL"


def test_link_cap_fails_when_coverage_ratio_is_ignored(allocations):
    bad = allocations[allocations["allocated_amount"] > 0].copy().reset_index(drop=True)
    bad.loc[0, "coverage_ratio"] = 0.0
    rep = _report()
    cc.check_link_cap(bad, rep)
    assert _status(rep, "crm_alloc_link_cap") == "FAIL"


def test_ead_conservation_fails_when_residual_drifts(allocations):
    bad = allocations.copy()
    bad.loc[0, "residual_exposure"] = bad.loc[0, "residual_exposure"] + 1_000.0
    rep = _report()
    cc.check_ead_conservation(bad, pd.DataFrame(columns=[
        "asof", "exposure_id", "ead", "exposure_haircut"]), rep)
    assert _status(rep, "crm_alloc_ead_conservation") == "FAIL"


def test_ead_conservation_fails_when_terms_ledger_disagrees(allocations, universe):
    bad_terms = universe["crm_exposure_terms"].copy()
    bad_terms.loc[0, "ead"] = bad_terms.loc[0, "ead"] * 1.5 + 1.0
    rep = _report()
    cc.check_ead_conservation(allocations, bad_terms, rep)
    assert _status(rep, "crm_alloc_ead_conservation") == "FAIL"


def test_pool_conservation_fails_when_supply_is_understated(allocations):
    bad = allocations.copy()
    victim = bad.loc[bad["allocated_amount"] > 0, "collateral_id"].iloc[0]
    bad.loc[bad["collateral_id"] == victim, "collateral_value_adj"] = 0.0
    rep = _report()
    cc.check_pool_conservation(bad, rep)
    assert _status(rep, "crm_alloc_pool_conservation") == "FAIL"


def test_pool_conservation_fails_when_collateral_residual_drifts(allocations):
    bad = allocations.copy()
    victim = bad["collateral_id"].iloc[0]
    bad.loc[bad["collateral_id"] == victim, "residual_collateral"] += 1_000.0
    rep = _report()
    cc.check_pool_conservation(bad, rep)
    assert _status(rep, "crm_alloc_pool_conservation") == "FAIL"


def test_relation_type_check_fails_on_a_wrong_label(universe):
    bad = universe["crm_collateral_link"].copy()
    idx = bad.index[bad["relation_type"] == "1:1"][0]
    bad.loc[idx, "relation_type"] = "M:N"
    rep = _report()
    cc.check_relation_type(bad, rep)
    assert _status(rep, "crm_link_relation_type") == "FAIL"


def test_pool_partition_check_fails_when_a_component_is_split(universe):
    bad = universe["crm_collateral_link"].copy()
    victim = bad.loc[bad["relation_type"] == "M:N", "pool_id"].iloc[0]
    idx = bad.index[bad["pool_id"] == victim][0]
    bad.loc[idx, "pool_id"] = "POOL_별개"
    rep = _report()
    cc.check_pool_partition(bad, rep)
    assert _status(rep, "crm_link_pool_partition") == "FAIL"


def test_unit_uniform_check_fails_when_a_haircut_splits(allocations):
    """같은 담보가 익스포저마다 다른 차감률을 받는 상태 = 배분 뒤 조정."""
    bad = allocations.copy()
    multi = (bad.groupby(["alloc_rule", "collateral_id"]).size()
             .loc[lambda s: s > 1].index[0])
    mask = (bad["alloc_rule"] == multi[0]) & (bad["collateral_id"] == multi[1])
    idx = bad.index[mask][0]
    bad.loc[idx, "haircut_total"] = bad.loc[idx, "haircut_total"] + 0.05
    rep = _report()
    cc.check_unit_columns_uniform(bad, rep)
    assert _status(rep, "crm_alloc_collateral_unit_uniform") == "FAIL"


def test_rule_sensitivity_fails_when_the_rule_is_ignored(allocations):
    """규칙 인자를 받고도 쓰지 않으면 모든 규칙의 배분 벡터가 같아진다."""
    one = allocations[allocations["alloc_rule"] == "pro_rata"]
    faked = pd.concat([one.assign(alloc_rule=r) for r in ALLOC_RULES],
                      ignore_index=True)
    rep = _report()
    cc.check_rule_sensitivity(faked, rep)
    assert _status(rep, "crm_alloc_rule_sensitivity") == "FAIL"


def test_rule_sensitivity_warns_with_a_single_rule(allocations):
    rep = _report()
    cc.check_rule_sensitivity(allocations[allocations["alloc_rule"] == "pro_rata"],
                              rep)
    assert _status(rep, "crm_alloc_rule_sensitivity") == "WARN"


def test_rwa_recon_fails_when_exposure_conservation_breaks(allocations, universe):
    bad = allocations.copy()
    bad.loc[0, "residual_exposure"] = bad.loc[0, "residual_exposure"] + 5_000.0
    rep = _report()
    cc.check_rwa_reconciliation(bad, universe["crm_exposure_terms"], rep)
    assert _status(rep, "crm_alloc_rwa_recon") == "FAIL"


def test_rwa_recon_fails_when_the_terms_risk_weight_drifts(
        allocations, universe, base_tables):
    """조건 원장의 위험가중치가 기존 RWA 산출과 어긋나면 잡힌다."""
    _, rwa = base_tables
    bad_terms = universe["crm_exposure_terms"].copy()
    bad_terms["risk_weight"] = bad_terms["risk_weight"] * 1.2
    rep = _report()
    cc.check_rwa_reconciliation(allocations, bad_terms, rep, rwa)
    assert _status(rep, "crm_alloc_rwa_recon") == "FAIL"


def test_rwa_recon_fails_when_crm_increases_rwa(allocations, universe):
    bad = allocations.copy()
    bad["residual_exposure"] = bad["exposure_ead"] * 2.0
    bad["allocated_amount"] = -bad["exposure_ead"]
    rep = _report()
    cc.check_rwa_reconciliation(bad, universe["crm_exposure_terms"], rep)
    assert _status(rep, "crm_alloc_rwa_recon") == "FAIL"
