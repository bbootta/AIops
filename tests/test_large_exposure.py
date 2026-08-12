"""거액익스포져 엔진·원장 테스트.

검사는 **위반을 주입하면 실제로 FAIL해야** 통제다. 항등식을 다시 쓴 검사는 언제나
통과하므로 아무것도 지키지 못한다. 아래 검사 7종마다 정상 통과 1건과 위반 주입 1건을
짝으로 둔다. 위반은 엔진이 실제로 저지를 수 있는 결함의 형태로 만든다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib.data_gen import generate_portfolio
from risk_lib.datamodel.spec import TableSpec, validate as validate_spec
from risk_lib.limits.large_exposure import (
    AGGREGATE, CONNECTED_GROUP, EXEMPTION, EXPOSURE_MEASURE, LEX_TABLES,
    LOOKTHROUGH, POSITION, SETTING, SUBSTITUTION, UNKNOWN_CLIENT_ID,
    apply_exemptions, apply_lookthrough, apply_substitution,
    build_lex_inputs, build_lex_setting, check_aggregate_numerator,
    check_exemption_conservation, check_group_additivity,
    check_group_ratio_dominance, check_lookthrough_conservation,
    check_reporting_completeness, check_substitution_conservation,
    compute_aggregate, compute_large_exposure, compute_positions,
    measure_exposures, resolve_connected_groups, setting_value,
)
from risk_lib.validation.consistency import ValidationReport

ASOF = "2026-06-30"
TIER1 = 2.0e13
OWN_FUNDS = 2.6e13


# ---------------------------------------------------------------- fixtures

@pytest.fixture(scope="module")
def setting():
    return build_lex_setting(
        ASOF, bank_is_gsib=False, lookthrough_small_to_structure=True,
        input_by="한도관리담당", approved_by="리스크관리부장",
        approved_at="2026-07-05")


@pytest.fixture(scope="module")
def inputs():
    return build_lex_inputs(generate_portfolio(seed=42), asof=ASOF,
                            tier1=TIER1, seed=42)


@pytest.fixture(scope="module")
def result(inputs, setting):
    return compute_large_exposure(inputs, setting, asof=ASOF, tier1=TIER1,
                                  own_funds=OWN_FUNDS)


def _status(report: ValidationReport, name: str) -> str:
    hit = [c for c in report.checks if c.name == name]
    assert hit, f"{name} 검사가 실행되지 않았다"
    return hit[0].status


# ---------------------------------------------------------------- 설정 원장

def test_setting_carries_primary_source_values(setting):
    """한도율·보고기준이 원문 값과 같고 근거 상태가 원문확인이다."""
    assert setting_value(setting, "감독규정26조_기본자본", "limit_general") == 0.25
    assert setting_value(setting, "감독규정26조_기본자본", "limit_sib") == 0.20
    assert setting_value(
        setting, "감독규정26조_기본자본", "limit_gsib_to_gsib") == 0.15
    assert setting_value(
        setting, "감독규정26조_기본자본", "reporting_threshold") == 0.10
    assert setting_value(
        setting, "감독규정26조_기본자본", "lookthrough_threshold") == 0.0025
    assert setting_value(setting, "감독규정26조_기본자본", "ccf_floor") == 0.10
    assert setting_value(setting, "은행법35조_동일차주", "limit_general") == 0.25
    assert setting_value(setting, "은행법35조_동일인", "limit_general") == 0.20
    assert setting_value(setting, "은행법35조_동일차주", "aggregate_limit") == 5.0
    reg = setting[setting["framework"] == "감독규정26조_기본자본"]
    limits = reg[reg["param_code"].isin(
        ("limit_general", "limit_sib", "limit_gsib_to_gsib"))]
    assert (limits["evidence_status"] == "원문확인").all()


def test_denominators_differ_between_frameworks(setting):
    """감독규정은 기본자본, 은행법은 자기자본. 섞으면 안 된다."""
    reg = setting[setting["framework"] == "감독규정26조_기본자본"]
    act = setting[setting["framework"].str.startswith("은행법")]
    assert set(reg["denominator_basis"]) == {"tier1"}
    assert set(act["denominator_basis"]) == {"own_funds"}


def test_unconfirmed_source_stays_null(setting):
    """원문을 못 본 값은 NULL + 미확인이다. 기억으로 채우지 않는다."""
    d283 = setting[setting["framework"] == "BCBS_d283_2014"]
    assert len(d283) > 0
    assert d283["param_value"].isna().all()
    assert (d283["evidence_status"] == "미확인").all()
    scope = setting[setting["param_code"] == "credit_extension_scope"]
    assert scope["param_value"].isna().all()
    assert (scope["evidence_status"] == "미확인").all()


def test_null_limit_framework_produces_no_position(result):
    """값이 비어 있는 체계는 산출되지 않고 경고가 남는다."""
    assert "BCBS_d283_2014" not in set(result.position["framework"])
    assert any(w.scope == "BCBS_d283_2014" and w.param == "limit_general"
               for w in result.warnings)


def test_setting_override_flows_into_position(inputs, setting):
    """화면에서 설정을 바꾸면 원장이 바뀌고 산출이 따라간다."""
    tightened = build_lex_setting(
        ASOF, bank_is_gsib=False, lookthrough_small_to_structure=True,
        input_by="한도관리담당", approved_by="리스크관리부장",
        approved_at="2026-07-05",
        overrides={("감독규정26조_기본자본", "limit_general"): 0.10},
        override_reason="내부한도 강화")
    row = tightened[(tightened["framework"] == "감독규정26조_기본자본")
                    & (tightened["param_code"] == "limit_general")].iloc[0]
    assert row["is_overridden"] is True or row["is_overridden"] == True  # noqa: E712
    assert row["override_reason"] == "내부한도 강화"
    base = compute_large_exposure(inputs, setting, asof=ASOF, tier1=TIER1,
                                  own_funds=OWN_FUNDS)
    tight = compute_large_exposure(inputs, tightened, asof=ASOF, tier1=TIER1,
                                   own_funds=OWN_FUNDS)
    hb = base.position[base.position["framework"] == "감독규정26조_기본자본"]
    ht = tight.position[tight.position["framework"] == "감독규정26조_기본자본"]
    assert int(ht["breach"].sum()) > int(hb["breach"].sum())


def test_no_hardcoded_limits_in_engine(setting):
    """엔진은 원장만 읽는다. 한도율을 비우면 그 체계 산출이 사라진다."""
    stripped = setting.copy()
    stripped.loc[(stripped["framework"] == "감독규정26조_기본자본")
                 & (stripped["param_code"] == "limit_general"),
                 "param_value"] = np.nan
    pos, warns = compute_positions(
        pd.Series({"A": 1.0}), pd.Series({"A": 1.0}), pd.Series({"A": 1.0}),
        pd.Series(dtype=float),
        pd.DataFrame({"group_id": ["G"], "counterparty_id": ["A"]}),
        pd.DataFrame({"counterparty_id": ["A"], "counterparty_class": ["일반"]}),
        stripped, asof=ASOF, tier1=TIER1, own_funds=OWN_FUNDS,
        frameworks=("감독규정26조_기본자본",))
    assert pos.empty
    assert any(w.param == "limit_general" for w in warns)


# ---------------------------------------------------------------- 측정

def test_measure_rules_per_exposure_type(setting):
    """유형별 측정식이 별표 3-12 제3절과 같다."""
    uni = pd.DataFrame([
        # 14. 난내 = 장부가액 − 고정이하 대손충당금
        dict(asof=ASOF, exposure_id="E1", counterparty_id="A",
             exposure_type="은행계정_난내", gross_amount=1000.0,
             deduction_amount=120.0, conversion_factor=np.nan,
             measured_override=np.nan),
        # 17. 부외 = 계약금액 × max(CCF, 10%) — 입력 CCF가 하한 미만이다
        dict(asof=ASOF, exposure_id="E2", counterparty_id="B",
             exposure_type="부외", gross_amount=1000.0, deduction_amount=0.0,
             conversion_factor=0.0, measured_override=np.nan),
        # 42. 커버드본드 = max(명목 − 기초자산, 명목 × 20%)
        dict(asof=ASOF, exposure_id="E3", counterparty_id="C",
             exposure_type="이중상환청구권부채권", gross_amount=1000.0,
             deduction_amount=950.0, conversion_factor=np.nan,
             measured_override=np.nan),
        # 15. 파생 = SA-CCR EAD
        dict(asof=ASOF, exposure_id="E4", counterparty_id="D",
             exposure_type="장외파생_SACCR", gross_amount=1000.0,
             deduction_amount=0.0, conversion_factor=np.nan,
             measured_override=333.0),
    ])
    m, warns = measure_exposures(uni, setting)
    got = dict(zip(m["counterparty_id"], m["measured_amount"]))
    assert got["A"] == pytest.approx(880.0)
    assert got["B"] == pytest.approx(100.0)     # 하한 10%가 걸린다
    assert got["C"] == pytest.approx(200.0)     # 20% 하한이 50보다 크다
    assert got["D"] == pytest.approx(333.0)
    assert not [w for w in warns if w.param == "measured_amount"]


def test_missing_measure_input_is_not_silently_zero(setting):
    """SA-CCR 값이 없으면 0으로 만들지 않고 측정불가로 두고 경고를 남긴다."""
    uni = pd.DataFrame([dict(
        asof=ASOF, exposure_id="E1", counterparty_id="A",
        exposure_type="장외파생_SACCR", gross_amount=1000.0,
        deduction_amount=0.0, conversion_factor=np.nan,
        measured_override=np.nan)])
    m, warns = measure_exposures(uni, setting)
    assert m["measure_status"].iloc[0] == "측정불가"
    assert pd.isna(m["measured_amount"].iloc[0])
    assert any(w.param == "measured_amount" for w in warns)


def test_measure_basis_is_recorded(result):
    """어느 조문으로 잰 금액인지가 원장에 남는다."""
    assert (result.exposure_measure["measure_basis"].str.len() > 0).all()
    onb = result.exposure_measure[
        result.exposure_measure["exposure_type"] == "은행계정_난내"]
    assert onb["measure_basis"].iloc[0].find("14.") >= 0


# ---------------------------------------------------------------- 대체

def _sub_case():
    """차주 A에 대한 익스포저를 보장제공자 B가 전부 보장한 최소 사례."""
    measure = pd.DataFrame([
        dict(asof=ASOF, counterparty_id="A", exposure_type="은행계정_난내",
             gross_amount=1000.0, deduction_amount=0.0,
             conversion_factor=np.nan, measured_amount=1000.0,
             measure_basis="14.", n_exposures=1, measure_status="측정"),
        dict(asof=ASOF, counterparty_id="B", exposure_type="은행계정_난내",
             gross_amount=500.0, deduction_amount=0.0,
             conversion_factor=np.nan, measured_amount=500.0,
             measure_basis="14.", n_exposures=1, measure_status="측정"),
    ])
    guar = pd.DataFrame([dict(
        asof=ASOF, original_counterparty_id="A", exposure_type="은행계정_난내",
        protection_provider_id="B", protection_type="보증",
        covered_amount=600.0, original_maturity_years=3.0,
        residual_maturity_years=2.0, provider_is_financial=True,
        reference_is_financial=True, ccr_exposure_amount=np.nan)])
    return measure, guar


def test_substitution_moves_exposure_to_provider(setting):
    """23. 차감액은 소멸하지 않고 보장제공자 익스포저로 더해진다."""
    measure, guar = _sub_case()
    sub, post, _ = apply_substitution(measure, guar, setting)
    got = post.groupby("counterparty_id")["measured_amount"].sum()
    assert got["A"] == pytest.approx(400.0)      # 1000 − 600
    assert got["B"] == pytest.approx(1100.0)     # 500 + 600
    assert float(post["measured_amount"].sum()) == pytest.approx(1500.0)
    assert sub["exposure_before"].iloc[0] == pytest.approx(1000.0)
    assert sub["exposure_after"].iloc[0] == pytest.approx(400.0)


def test_substitution_can_push_provider_over_limit(setting):
    """대체로 보장제공자가 새로 한도를 넘길 수 있다. 이 규제의 요점이다."""
    measure, guar = _sub_case()
    sub, post, _ = apply_substitution(measure, guar, setting)
    included = post.groupby("counterparty_id")["measured_amount"].sum()
    cp = pd.DataFrame({"counterparty_id": ["A", "B"],
                       "counterparty_class": ["일반", "일반"]})
    grp = pd.DataFrame({"group_id": ["GA", "GB"], "counterparty_id": ["A", "B"]})
    pos, _ = compute_positions(
        included, included, included, pd.Series(dtype=float), grp, cp, setting,
        asof=ASOF, tier1=4000.0, own_funds=4000.0,
        frameworks=("감독규정26조_기본자본",))
    by = pos.set_index("group_id")
    # 한도 = 4000 × 25% = 1000. B는 대체 전 500(위반 아님) → 대체 후 1100(위반).
    assert bool(by.loc["GB", "breach"]) is True
    assert bool(by.loc["GA", "breach"]) is False


def test_maturity_mismatch_blocks_substitution(setting):
    """20.가 원만기 1년 미만 또는 잔존만기 3개월 미만이면 경감기법을 못 쓴다."""
    measure, guar = _sub_case()
    guar.loc[0, "original_maturity_years"] = 0.5
    sub, post, _ = apply_substitution(measure, guar, setting)
    assert sub["substituted_amount"].iloc[0] == 0.0
    assert bool(sub["maturity_mismatch_eligible"].iloc[0]) is False
    assert "20.가" in sub["eligibility_reason"].iloc[0]
    got = post.groupby("counterparty_id")["measured_amount"].sum()
    assert got["A"] == pytest.approx(1000.0)


def test_substitution_capped_by_original_exposure(setting):
    """차감액은 원 거래상대방 잔액을 넘을 수 없다. 넘으면 익스포저가 소멸한다."""
    measure, guar = _sub_case()
    guar.loc[0, "covered_amount"] = 5000.0
    sub, post, _ = apply_substitution(measure, guar, setting)
    assert sub["substituted_amount"].iloc[0] == pytest.approx(1000.0)
    assert float(post["measured_amount"].sum()) == pytest.approx(1500.0)


def test_cds_exception_without_ccr_amount_warns(setting):
    """34. 예외 대상인데 SA-CCR 값이 없으면 0으로 만들지 않고 비워 두고 경고한다."""
    measure, guar = _sub_case()
    guar.loc[0, "protection_type"] = "신용부도스왑"
    guar.loc[0, "provider_is_financial"] = False
    guar.loc[0, "reference_is_financial"] = False
    sub, post, warns = apply_substitution(measure, guar, setting)
    assert bool(sub["cds_exception_applied"].iloc[0]) is True
    assert pd.isna(sub["provider_recognised_amount"].iloc[0])
    assert any(w.param == "ccr_exposure_amount" for w in warns)


def test_check_substitution_conservation_passes(result):
    assert _status(result.report, "lex_substitution_conservation") == "PASS"


def test_check_substitution_conservation_fails_when_provider_side_dropped(result):
    """대체를 '익스포저 감소'로 잘못 구현하면 보장제공자 가산이 빠진다."""
    broken = result.exposure_measure[
        result.exposure_measure["exposure_type"] != "신용위험경감_대체분"]
    rep = ValidationReport()
    check_substitution_conservation(
        result.exposure_measure_pre_crm, broken, result.substitution, rep)
    assert _status(rep, "lex_substitution_conservation") == "FAIL"


# ---------------------------------------------------------------- 면제

def test_exemption_records_amount_and_basis(result):
    """면제액과 근거가 원장에 남는다. 조용히 빼지 않는다."""
    ex = result.exemption
    assert len(ex) > 0
    assert (ex["exempt_amount"] >= 0).all()
    assert (ex["citation"].str.len() > 0).all()
    assert float(ex["exempt_amount"].sum()) > 0


def test_intraday_exemption_is_not_reportable(result):
    """38. 면제해도 보고대상이며 은행 간 일중 거래만 제외한다."""
    ex = result.exemption
    intraday = ex[ex["exemption_type"] == "은행간_일중"]
    assert len(intraday) > 0
    assert not intraday["reportable"].any()
    other = ex[ex["exemption_type"] != "은행간_일중"]
    assert other["reportable"].all()


def test_exemption_cannot_exceed_measured():
    """면제비율이 100%를 넘어도 산입액이 음수가 되지 않는다."""
    measure = pd.DataFrame([dict(
        asof=ASOF, counterparty_id="A", exposure_type="은행계정_난내",
        gross_amount=100.0, deduction_amount=0.0, conversion_factor=np.nan,
        measured_amount=100.0, measure_basis="14.", n_exposures=1,
        measure_status="측정")])
    rules = pd.DataFrame([
        dict(asof=ASOF, counterparty_id="A", exemption_type="국가등",
             exempt_ratio=0.8, basis="x"),
        dict(asof=ASOF, counterparty_id="A", exemption_type="은행그룹내부",
             exempt_ratio=0.8, basis="y"),
    ])
    ex, included, _ = apply_exemptions(measure, rules)
    assert float(ex["exempt_amount"].sum()) == pytest.approx(100.0)
    assert float(included["A"]) == pytest.approx(0.0)


def test_check_exemption_conservation_passes(result):
    assert _status(result.report, "lex_exemption_conservation") == "PASS"


def test_check_exemption_conservation_fails_on_double_deduction(result):
    """같은 금액을 두 번 빼면 면제액 + 산입액이 측정 총액을 넘는다."""
    broken = result.exemption.copy()
    broken.loc[broken.index[0], "exempt_amount"] *= 2.0
    broken.loc[broken.index[0], "exempt_amount"] += 1e9
    rep = ValidationReport()
    check_exemption_conservation(broken, result.exposure_measure, rep)
    assert _status(rep, "lex_exemption_conservation") == "FAIL"


# ---------------------------------------------------------------- look-through

def test_unknown_client_bucket_collects_unlookable(result):
    """44.다 후단 — 관통 불가분이 하나의 가상 차주에 모인다."""
    lt = result.lookthrough
    unknown = lt[lt["attribution_type"] == "무명고객"]
    assert len(unknown) > 0
    assert set(unknown["attributed_to"]) == {UNKNOWN_CLIENT_ID}
    # 여러 구조화상품에서 온 금액이 한 차주로 합쳐진다.
    assert unknown["structure_id"].nunique() > 1
    bucket = result.exposure_measure[
        result.exposure_measure["counterparty_id"] == UNKNOWN_CLIENT_ID]
    assert len(bucket) == 1
    assert float(bucket["measured_amount"].iloc[0]) == pytest.approx(
        float(unknown["attributed_amount"].sum()))


def test_unknown_client_can_breach_limit(result):
    """무명고객 버킷도 한도 판정을 받는다."""
    head = result.position[
        result.position["framework"] == "감독규정26조_기본자본"]
    grp = result.connected_group
    gid = grp.loc[grp["counterparty_id"] == UNKNOWN_CLIENT_ID,
                  "group_id"].iloc[0]
    row = head[head["group_id"] == gid].iloc[0]
    assert row["counterparty_class"] == "무명고객"
    assert row["ratio"] > 0
    assert row["limit_pct"] == 0.25


def test_lookthrough_small_holding_becomes_structure_itself(setting):
    """44.가 — 투자 총액이 기본자본의 0.25% 미만이면 상품 자체가 거래상대방이다."""
    measure = pd.DataFrame([dict(
        asof=ASOF, counterparty_id="FUND_X", exposure_type="구조화상품",
        gross_amount=10.0, deduction_amount=0.0, conversion_factor=np.nan,
        measured_amount=10.0, measure_basis="46.다", n_exposures=1,
        measure_status="측정")])
    under = pd.DataFrame([dict(
        asof=ASOF, structure_id="FUND_X", underlying_counterparty_id="U1",
        underlying_notional=100.0, structure_total=100.0,
        can_look_through=True, seniority_equal=True, tranche_amount=0.0)])
    lt, post, _ = apply_lookthrough(
        measure, under, pd.DataFrame(columns=["structure_id", "third_party_id",
                                              "role"]),
        setting, tier1=100000.0)
    assert lt["attribution_type"].iloc[0] == "구조화상품자체"
    assert lt["attributed_to"].iloc[0] == "FUND_X"


def test_lookthrough_attributes_to_real_counterparties(setting):
    """46.가 — 보유비율 × 기초자산가치로 실질 차주에 귀속된다."""
    measure = pd.DataFrame([dict(
        asof=ASOF, counterparty_id="FUND_X", exposure_type="구조화상품",
        gross_amount=1000.0, deduction_amount=0.0, conversion_factor=np.nan,
        measured_amount=1000.0, measure_basis="46.다", n_exposures=1,
        measure_status="측정")])
    under = pd.DataFrame([
        dict(asof=ASOF, structure_id="FUND_X", underlying_counterparty_id="U1",
             underlying_notional=3000.0, structure_total=4000.0,
             can_look_through=True, seniority_equal=True, tranche_amount=0.0),
        dict(asof=ASOF, structure_id="FUND_X", underlying_counterparty_id="U2",
             underlying_notional=1000.0, structure_total=4000.0,
             can_look_through=True, seniority_equal=True, tranche_amount=0.0),
    ])
    lt, post, _ = apply_lookthrough(
        measure, under, pd.DataFrame(columns=["structure_id", "third_party_id",
                                              "role"]),
        setting, tier1=100.0)
    got = dict(zip(lt["attributed_to"], lt["attributed_amount"]))
    assert got["U1"] == pytest.approx(750.0)    # 1000/4000 × 3000
    assert got["U2"] == pytest.approx(250.0)
    assert float(lt["attributed_amount"].sum()) == pytest.approx(1000.0)


def test_tranche_attribution_is_not_capped_at_holding(setting):
    """46.나 주7) — (투자금액/트렌치) × min(기초자산, 트렌치).

    선순위 트렌치는 어느 기초자산에서도 트렌치 규모까지 손실을 볼 수 있다는
    가정이라 귀속액 합이 보유액을 넘는다. 보수적 과다귀속이므로 보유액에 맞춰
    깎으면 안 된다. 깎으면 원문에 없는 상한을 만드는 것이다.
    """
    measure = pd.DataFrame([dict(
        asof=ASOF, counterparty_id="ABS_X", exposure_type="구조화상품",
        gross_amount=100.0, deduction_amount=0.0, conversion_factor=np.nan,
        measured_amount=100.0, measure_basis="46.다", n_exposures=1,
        measure_status="측정")])
    under = pd.DataFrame([
        dict(asof=ASOF, structure_id="ABS_X", underlying_counterparty_id=f"U{i}",
             underlying_notional=150.0, structure_total=1000.0,
             can_look_through=True, seniority_equal=False, tranche_amount=200.0)
        for i in range(4)])
    lt, post, _ = apply_lookthrough(
        measure, under, pd.DataFrame(columns=["structure_id", "third_party_id",
                                              "role"]),
        setting, tier1=100.0)
    # 투자 100 / 트렌치 200 = 0.5, min(150, 200) = 150 → 건별 75
    assert set(lt["attributed_amount"]) == {75.0}
    assert float(lt["attributed_amount"].sum()) == pytest.approx(300.0)
    assert not lt["attribution_additive"].any()
    # 비가산 행만 있으면 보존식 검사는 대상 없음으로 통과한다.
    rep = ValidationReport()
    check_lookthrough_conservation(lt, rep)
    assert _status(rep, "lex_lookthrough_conservation") == "PASS"


def test_repeated_underlying_counterparty_is_aggregated(setting):
    """같은 차주가 한 풀에 두 번 들어오면 합산된다 (44.나).

    합치지 않으면 기본키가 깨지고 한도 판정이 같은 차주를 두 건으로 센다.
    """
    measure = pd.DataFrame([dict(
        asof=ASOF, counterparty_id="FUND_Y", exposure_type="구조화상품",
        gross_amount=1000.0, deduction_amount=0.0, conversion_factor=np.nan,
        measured_amount=1000.0, measure_basis="46.다", n_exposures=1,
        measure_status="측정")])
    under = pd.DataFrame([
        dict(asof=ASOF, structure_id="FUND_Y", underlying_counterparty_id="U1",
             underlying_notional=1000.0, structure_total=4000.0,
             can_look_through=True, seniority_equal=True, tranche_amount=0.0),
        dict(asof=ASOF, structure_id="FUND_Y", underlying_counterparty_id="U1",
             underlying_notional=3000.0, structure_total=4000.0,
             can_look_through=True, seniority_equal=True, tranche_amount=0.0),
    ])
    lt, post, _ = apply_lookthrough(
        measure, under, pd.DataFrame(columns=["structure_id", "third_party_id",
                                              "role"]),
        setting, tier1=100.0)
    u1 = lt[lt["attributed_to"] == "U1"]
    assert len(u1) == 1
    assert float(u1["attributed_amount"].iloc[0]) == pytest.approx(1000.0)


def test_check_lookthrough_conservation_passes(result):
    assert _status(result.report, "lex_lookthrough_conservation") == "PASS"


def test_check_lookthrough_conservation_fails_when_residual_dropped(result):
    """미식별 잔여를 무명고객으로 보내지 않고 버리면 익스포저가 소멸한다."""
    lt = result.lookthrough
    drop = lt[(lt["attribution_type"] == "무명고객")
              & (lt["method"].str.contains("미식별"))]
    assert len(drop) > 0, "미식별 잔여 행이 표본에 있어야 이 대조가 의미 있다"
    broken = lt.drop(index=drop.index)
    rep = ValidationReport()
    check_lookthrough_conservation(broken, rep)
    assert _status(rep, "lex_lookthrough_conservation") == "FAIL"


def test_third_party_risk_excluded_from_conservation(result):
    """47.은 '별도로' 산출하므로 보유액 보존식에 들어가지 않는다."""
    lt = result.lookthrough
    tp = lt[lt["is_additional_risk"]]
    assert len(tp) > 0
    assert (tp["attribution_type"] == "제3자추가리스크").all()
    assert _status(result.report, "lex_lookthrough_conservation") == "PASS"


# ---------------------------------------------------------------- 연결차주

def test_connected_groups_form_multi_member_clusters(result):
    """판정 결과가 그래프이므로 1:1이 아닌 군집이 나온다."""
    g = result.connected_group
    sizes = g.drop_duplicates("group_id")["n_members"]
    assert (sizes > 1).sum() > 0
    assert sizes.max() >= 3          # 사슬로 이어진 성분이 3개 이상 묶인다
    assert set(g["connection_basis"]) >= {"지배관계", "경제적상호의존", "단독"}


def test_control_and_interdependence_merge_into_one_component(setting):
    """지배관계와 경제적 상호의존이 한 연결 성분 안에서 섞인다."""
    cp = pd.DataFrame({"counterparty_id": ["A", "B", "C", "D"],
                       "counterparty_class": ["일반"] * 4})
    ctrl = pd.DataFrame([dict(asof=ASOF, parent_id="A", child_id="B",
                              voting_share=0.6, control_basis="과반수의결권",
                              excluded=False, exclusion_approved_by=None)])
    inter = pd.DataFrame([dict(asof=ASOF, counterparty_a="B",
                               counterparty_b="C", criterion="수입지출50%",
                               metric_value=0.7, excluded=False,
                               exclusion_approved_by=None)])
    g, _ = resolve_connected_groups(
        cp, ctrl, inter, setting, asof=ASOF,
        exposure_by_counterparty=pd.Series({"A": 1.0}), tier1=TIER1)
    by = g.set_index("counterparty_id")
    assert by.loc["A", "group_id"] == by.loc["B", "group_id"]
    assert by.loc["B", "group_id"] == by.loc["C", "group_id"]
    assert by.loc["D", "group_id"] != by.loc["A", "group_id"]
    assert by.loc["A", "n_members"] == 3


def test_interdependence_below_threshold_makes_no_group(setting):
    """10.가는 '50% 이상'이다. 미달이면 그룹을 만들지 않는다."""
    cp = pd.DataFrame({"counterparty_id": ["A", "B"],
                       "counterparty_class": ["일반", "일반"]})
    inter = pd.DataFrame([dict(asof=ASOF, counterparty_a="A",
                               counterparty_b="B", criterion="수입지출50%",
                               metric_value=0.49, excluded=False,
                               exclusion_approved_by=None)])
    g, _ = resolve_connected_groups(
        cp, pd.DataFrame(columns=["asof", "parent_id", "child_id",
                                  "voting_share", "control_basis"]),
        inter, setting, asof=ASOF,
        exposure_by_counterparty=pd.Series(dtype=float), tier1=TIER1)
    assert g["group_id"].nunique() == 2


def test_group_exclusion_requires_approver(setting):
    """11. 그룹 제외는 판단이 개입한다. 승인자가 없으면 반영하지 않는다."""
    cp = pd.DataFrame({"counterparty_id": ["A", "B"],
                       "counterparty_class": ["일반", "일반"]})
    ctrl = pd.DataFrame([dict(asof=ASOF, parent_id="A", child_id="B",
                              voting_share=0.6, control_basis="과반수의결권",
                              excluded=True, exclusion_approved_by=None)])
    empty = pd.DataFrame(columns=["asof", "counterparty_a", "counterparty_b",
                                  "criterion", "metric_value"])
    g, warns = resolve_connected_groups(
        cp, ctrl, empty, setting, asof=ASOF,
        exposure_by_counterparty=pd.Series(dtype=float), tier1=TIER1)
    assert g["group_id"].nunique() == 1        # 제외가 반영되지 않았다
    assert any(w.param == "exclusion_approved_by" for w in warns)

    ctrl.loc[0, "exclusion_approved_by"] = "리스크관리부장"
    g2, _ = resolve_connected_groups(
        cp, ctrl, empty, setting, asof=ASOF,
        exposure_by_counterparty=pd.Series(dtype=float), tier1=TIER1)
    assert g2["group_id"].nunique() == 2


def test_ccp_never_grouped(setting):
    """50. 청산 관련 중앙청산소 익스포저에는 연계 개념을 적용하지 않는다."""
    cp = pd.DataFrame({
        "counterparty_id": ["CCP", "A"],
        "counterparty_class": ["적격CCP", "일반"]})
    ctrl = pd.DataFrame([dict(asof=ASOF, parent_id="CCP", child_id="A",
                              voting_share=0.9, control_basis="과반수의결권",
                              excluded=False, exclusion_approved_by=None)])
    empty = pd.DataFrame(columns=["asof", "counterparty_a", "counterparty_b",
                                  "criterion", "metric_value"])
    g, _ = resolve_connected_groups(
        cp, ctrl, empty, setting, asof=ASOF,
        exposure_by_counterparty=pd.Series(dtype=float), tier1=TIER1)
    assert g["group_id"].nunique() == 2


def test_interdependence_review_flag_uses_5pct(setting):
    """10. 기본자본 5% 초과 차주는 상호의존성 평가 의무 대상이다."""
    cp = pd.DataFrame({"counterparty_id": ["BIG", "SMALL"],
                       "counterparty_class": ["일반", "일반"]})
    empty_c = pd.DataFrame(columns=["asof", "parent_id", "child_id",
                                    "voting_share", "control_basis"])
    empty_i = pd.DataFrame(columns=["asof", "counterparty_a", "counterparty_b",
                                    "criterion", "metric_value"])
    exp = pd.Series({"BIG": TIER1 * 0.06, "SMALL": TIER1 * 0.04})
    g, _ = resolve_connected_groups(
        cp, empty_c, empty_i, setting, asof=ASOF,
        exposure_by_counterparty=exp, tier1=TIER1)
    by = g.set_index("counterparty_id")
    assert bool(by.loc["BIG", "interdep_review_required"]) is True
    assert bool(by.loc["SMALL", "interdep_review_required"]) is False


def test_group_id_is_deterministic(inputs, setting):
    """구성원 집합이 같으면 언제 돌려도 같은 그룹 식별자가 나온다."""
    kw = dict(asof=ASOF, exposure_by_counterparty=pd.Series(dtype=float),
              tier1=TIER1)
    a, _ = resolve_connected_groups(
        inputs.counterparty, inputs.control_link, inputs.interdep_link,
        setting, **kw)
    b, _ = resolve_connected_groups(
        inputs.counterparty, inputs.control_link.iloc[::-1],
        inputs.interdep_link.iloc[::-1], setting, **kw)
    pd.testing.assert_frame_equal(
        a.sort_values(["group_id", "counterparty_id"])[
            ["group_id", "counterparty_id"]].reset_index(drop=True),
        b.sort_values(["group_id", "counterparty_id"])[
            ["group_id", "counterparty_id"]].reset_index(drop=True))


def test_check_group_additivity_passes(result):
    assert _status(result.report, "lex_group_additivity") == "PASS"


def test_check_group_additivity_fails_when_member_dropped(result):
    """구성원을 빠뜨리면 그룹 합계와 차주 합계가 어긋난다."""
    multi = result.connected_group[result.connected_group["n_members"] > 1]
    broken = result.connected_group.drop(index=multi.index[:1])
    included = result.position[
        result.position["aggregation_unit"] == "개별차주"].set_index(
        "group_id")["exposure_included"]
    rep = ValidationReport()
    check_group_additivity(result.position, broken, included, rep)
    assert _status(rep, "lex_group_additivity") == "FAIL"


# ---------------------------------------------------------------- 한도·보고

def test_two_frameworks_computed_side_by_side(result):
    """감독규정(기본자본)과 은행법(자기자본)이 나란히 산출되고 섞이지 않는다."""
    fws = set(result.position["framework"])
    assert fws == {"감독규정26조_기본자본", "은행법35조_동일차주", "은행법35조_동일인"}
    reg = result.position[result.position["framework"] == "감독규정26조_기본자본"]
    act = result.position[result.position["framework"] == "은행법35조_동일차주"]
    assert set(reg["denominator_basis"]) == {"tier1"}
    assert set(act["denominator_basis"]) == {"own_funds"}
    assert float(reg["denominator_amount"].iloc[0]) == TIER1
    assert float(act["denominator_amount"].iloc[0]) == OWN_FUNDS


def test_sib_counterparty_gets_tighter_limit(result):
    """상대방이 D-SIB·G-SIB이면 20%가 걸린다."""
    reg = result.position[result.position["framework"] == "감독규정26조_기본자본"]
    sib = reg[reg["counterparty_class"].isin(("D-SIB", "G-SIB"))]
    assert len(sib) > 0
    assert set(sib["limit_pct"]) == {0.20}
    normal = reg[reg["counterparty_class"] == "일반"]
    assert set(normal["limit_pct"]) == {0.25}


def test_gsib_to_gsib_limit_requires_bank_to_be_gsib(inputs):
    """감독규정 §26의2⑩의 15%는 본 은행이 G-SIB일 때만 걸린다."""
    as_gsib = build_lex_setting(
        ASOF, bank_is_gsib=True, lookthrough_small_to_structure=True,
        input_by="a", approved_by="b", approved_at="2026-07-05")
    r = compute_large_exposure(inputs, as_gsib, asof=ASOF, tier1=TIER1,
                               own_funds=OWN_FUNDS)
    reg = r.position[r.position["framework"] == "감독규정26조_기본자본"]
    assert set(reg.loc[reg["counterparty_class"] == "G-SIB", "limit_pct"]) == {0.15}
    assert set(reg.loc[reg["counterparty_class"] == "D-SIB", "limit_pct"]) == {0.20}


def test_pre_and_post_crm_reporting_both_present(result):
    """7.가(1)(2) — CRM 미적용분과 적용분을 둘 다 보고해야 한다."""
    p = result.position
    assert "exposure_pre_crm" in p.columns
    assert "reportable_pre_crm" in p.columns
    assert float(p["exposure_pre_crm"].sum()) > 0


def test_check_reporting_completeness_passes(result):
    assert _status(result.report, "lex_reporting_completeness") == "PASS"


def test_check_reporting_completeness_fails_when_flag_dropped(result):
    """보고 플래그를 빠뜨리면 기준 이상인 건이 보고에서 사라진다."""
    broken = result.position.copy()
    hit = broken[broken["reportable"]].index[:1]
    assert len(hit) > 0
    broken.loc[hit, "reportable"] = False
    rep = ValidationReport()
    check_reporting_completeness(broken, result.setting, rep)
    assert _status(rep, "lex_reporting_completeness") == "FAIL"


# ---------------------------------------------------------------- 총액

def test_aggregate_only_for_frameworks_with_limit(result):
    """감독규정 §26에는 총액한도가 없다. 은행법 §35④에만 5배 한도가 있다."""
    a = result.aggregate.set_index("framework")
    assert pd.isna(a.loc["감독규정26조_기본자본", "aggregate_limit_pct"])
    assert a.loc["은행법35조_동일차주", "aggregate_limit_pct"] == 5.0
    assert bool(a.loc["감독규정26조_기본자본", "breach"]) is False


def test_aggregate_numerator_excludes_small_exposures():
    """분자는 전체 합이 아니라 분모의 10%를 초과하는 건들의 합이다."""
    setting = build_lex_setting(
        ASOF, bank_is_gsib=False, lookthrough_small_to_structure=True,
        input_by="a", approved_by="b", approved_at="2026-07-05")
    pos = pd.DataFrame([
        dict(asof=ASOF, framework="은행법35조_동일차주", group_id="G1",
             aggregation_unit="거래상대방그룹", n_members=1,
             denominator_basis="own_funds", denominator_amount=1000.0,
             exposure_pre_crm=200.0, exposure_measured=200.0,
             exposure_exempt=0.0, exposure_included=200.0, ratio=0.20,
             counterparty_class="일반", limit_pct=0.25, limit_amount=250.0,
             utilisation=0.8, headroom=50.0, reportable=True,
             reportable_pre_crm=True, breach=False, limit_citation="x",
             measure_evidence_status="미확인"),
        dict(asof=ASOF, framework="은행법35조_동일차주", group_id="G2",
             aggregation_unit="거래상대방그룹", n_members=1,
             denominator_basis="own_funds", denominator_amount=1000.0,
             exposure_pre_crm=50.0, exposure_measured=50.0,
             exposure_exempt=0.0, exposure_included=50.0, ratio=0.05,
             counterparty_class="일반", limit_pct=0.25, limit_amount=250.0,
             utilisation=0.2, headroom=200.0, reportable=False,
             reportable_pre_crm=False, breach=False, limit_citation="x",
             measure_evidence_status="미확인"),
    ])
    agg, _ = compute_aggregate(pos, setting, asof=ASOF)
    row = agg.iloc[0]
    assert row["aggregate_numerator"] == pytest.approx(200.0)   # 250이 아니다
    assert row["n_large_credits"] == 1
    assert row["aggregate_limit_amount"] == pytest.approx(5000.0)


def test_check_aggregate_numerator_passes(result):
    assert _status(result.report, "lex_aggregate_numerator") == "PASS"


def test_check_aggregate_numerator_fails_on_total_sum(result):
    """분자에 전체 합을 넣는 흔한 오독을 잡는다."""
    broken = result.aggregate.copy()
    fw = broken["framework"].iloc[0]
    total = float(result.position.loc[
        result.position["framework"] == fw, "exposure_included"].sum())
    broken.loc[broken.index[0], "aggregate_numerator"] = total
    rep = ValidationReport()
    check_aggregate_numerator(broken, result.position, rep)
    assert _status(rep, "lex_aggregate_numerator") == "FAIL"


# ---------------------------------------------------------------- 지배관계 비율

def test_check_group_ratio_dominance_passes(result):
    assert _status(result.report, "lex_group_ratio_dominance") == "PASS"


def test_check_group_ratio_dominance_fails_when_group_understated(result):
    """그룹 단계에서 상계를 한 번 더 하면 그룹 비율이 최대 구성원보다 작아진다."""
    broken = result.position.copy()
    grp = broken[(broken["aggregation_unit"] == "거래상대방그룹")
                 & (broken["n_members"] > 1)]
    assert len(grp) > 0
    broken.loc[grp.index, "ratio"] = 0.0
    rep = ValidationReport()
    check_group_ratio_dominance(broken, result.connected_group, rep)
    assert _status(rep, "lex_group_ratio_dominance") == "FAIL"


# ---------------------------------------------------------------- 원장 스펙

@pytest.mark.parametrize("spec", LEX_TABLES, ids=lambda s: s.name)
def test_table_spec_quality(spec: TableSpec):
    """grain·PK 필수, float 컬럼 unit 필수."""
    assert spec.grain.strip()
    assert spec.primary_key
    for col in spec.columns:
        if col.dtype == "float":
            assert col.unit, f"{spec.name}.{col.name}: float인데 unit이 없다"


@pytest.mark.parametrize(
    "spec,frame_attr",
    [(SETTING, "setting"), (EXPOSURE_MEASURE, "exposure_measure"),
     (LOOKTHROUGH, "lookthrough"), (SUBSTITUTION, "substitution"),
     (CONNECTED_GROUP, "connected_group"), (EXEMPTION, "exemption"),
     (POSITION, "position"), (AGGREGATE, "aggregate")],
    ids=lambda x: getattr(x, "name", x))
def test_ledger_matches_spec(result, spec: TableSpec, frame_attr: str):
    """산출 프레임이 스펙과 맞고 기본키가 유일하다."""
    df = getattr(result, frame_attr)
    assert list(df.columns) == list(spec.column_names), spec.name
    assert not df.duplicated(subset=list(spec.primary_key)).any(), spec.name
    fatal = [v for v in validate_spec(df, spec) if v.severity != "WARN"]
    assert not fatal, f"{spec.name}: {fatal[:5]}"


# ---------------------------------------------------------------- 결정론

def test_deterministic_for_fixed_seed_and_asof(setting):
    """(asof, seed) 고정이면 같은 결과가 나온다."""
    p = generate_portfolio(seed=42)
    a = compute_large_exposure(
        build_lex_inputs(p, asof=ASOF, tier1=TIER1, seed=7), setting,
        asof=ASOF, tier1=TIER1, own_funds=OWN_FUNDS)
    b = compute_large_exposure(
        build_lex_inputs(p, asof=ASOF, tier1=TIER1, seed=7), setting,
        asof=ASOF, tier1=TIER1, own_funds=OWN_FUNDS)
    pd.testing.assert_frame_equal(a.position, b.position)
    pd.testing.assert_frame_equal(a.exposure_measure, b.exposure_measure)
    assert a.summary["max_ratio"] == b.summary["max_ratio"]


def test_all_checks_pass_on_clean_run(result):
    assert result.report.passes()
    assert result.report.summary().get("FAIL", 0) == 0
    assert result.report.summary()["PASS"] == 7
