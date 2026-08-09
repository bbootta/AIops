"""신용평가시스템 원장·엔진 테스트 (BNK-CRM-002·003·004·006·007·008·009).

검증의 초점은 두 가지다. 규정 수치가 엔진 본문이 아니라 원장에서 오는가
(원장을 바꾸면 산출이 따라 움직이는가), 그리고 판정하지 못한 것을 통과로
접지 않는가.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib.credit_rating import override as ovr
from risk_lib.credit_rating import requirements as req
from risk_lib.credit_rating import sample as smp
from risk_lib.credit_rating import scorecard as sc
from risk_lib.credit_rating.build import (
    CORPORATE_MODEL_ID, FINANCIAL_FACTORS, build_credit_rating,
)
from risk_lib.datamodel.spec import validate
from risk_lib.models.pd_model import gini

ASOF = "2026-06-11"
SEED = 42

_SPECS = {s.name: s for s in (req.REQUIREMENT_TABLES + smp.SAMPLE_TABLES
                              + sc.SCORECARD_TABLES + ovr.OVERRIDE_TABLES)}


@pytest.fixture(scope="module")
def models() -> pd.DataFrame:
    """crm_model 원장의 최소 형태. 시장 모형을 일부러 섞는다."""
    return pd.DataFrame([
        {"model_id": "PD_CORP", "domain": "신용", "segment": "corporate"},
        {"model_id": "PD_RETAIL", "domain": "신용", "segment": "retail_other"},
        {"model_id": "PD_MORTGAGE", "domain": "신용",
         "segment": "residential_mortgage"},
        # 같은 원장에 있으나 등급을 부여하지 않는 모형 둘.
        {"model_id": "LGD_CORP", "domain": "신용", "segment": "corporate"},
        {"model_id": "VAR_MARKET", "domain": "시장", "segment": None},
    ])


@pytest.fixture(scope="module")
def built(portfolio, models):
    return build_credit_rating(portfolio, models, asof=ASOF, seed=SEED)


@pytest.fixture(scope="module")
def corp(portfolio):
    return portfolio[portfolio["asset_class"] == "corporate"].reset_index(drop=True)


# ----- 요건 원장 --------------------------------------------------------------

def test_every_requirement_row_cites_the_current_source_version():
    r = req.build_rating_requirements()
    assert len(r) == len(r["requirement_code"].unique())
    assert (r["evidence_status"] == "원문확인").all()
    assert (r["source_version"] == req.SOURCE_VERSION).all()
    assert r["citation"].str.startswith("[별표 3]").all()


def test_requirement_ledger_refs_point_at_real_tables():
    """이행 원장 이름이 실재해야 요건추적이 빈 참조로 부풀지 않는다."""
    from risk_lib.datamodel import catalog as cat
    known = {s.name for s in cat.ALL_TABLES} | set(_SPECS)
    r = req.build_rating_requirements()
    refs = r["ledger_ref"].dropna()
    missing = sorted(set(refs) - known)
    assert not missing, f"실재하지 않는 이행 원장 참조: {missing}"


def test_clauses_without_a_stated_period_stay_null():
    """156.과 158.(6)은 '정기적'이라고만 적는다. 12개월을 지어 넣지 않는다."""
    r = req.build_rating_requirements().set_index("requirement_code")
    for code in ("CRS-156", "CRS-158-6"):
        assert pd.isna(r.loc[code, "review_months"])
    # 반대로 연 1회를 명시한 조문은 값이 있어야 한다.
    for code in ("CRS-163-A", "CRS-179-B", "CRS-203-A"):
        assert int(r.loc[code, "review_months"]) == 12


# ----- 생애주기 판정 ----------------------------------------------------------

def test_lifecycle_status_covers_overdue_and_unassessable(built):
    c = built.tables["crm_lifecycle_compliance"]
    seen = set(c["status"])
    assert "주기미규정" in seen, "주기가 없는 요건이 판정된 것처럼 접혔다"
    assert {"이행", "기한초과"} & seen, "기한 판정이 하나도 나오지 않았다"
    # 판정하지 못한 행은 경과일이 비어 있어야 한다.
    unknown = c[c["status"].isin(["주기미규정", "증적없음"])]
    assert unknown["days_overdue"].isna().all()
    assert unknown["next_due"].isna().all()


def test_lifecycle_deadline_follows_the_requirement_ledger(models):
    """주기를 원장에서 12개월에서 6개월로 바꾸면 기한이 앞당겨진다."""
    r = req.build_rating_requirements()
    events = req.build_lifecycle_events(models, r, asof=ASOF, seed=SEED)
    base = req.assess_lifecycle(models, r, events, asof=ASOF)

    r2 = r.copy()
    mask = r2["review_months"].notna()
    r2.loc[mask, "review_months"] = 6
    tightened = req.assess_lifecycle(models, r2, events, asof=ASOF)

    key = ["model_id", "requirement_code"]
    j = base.merge(tightened, on=key, suffixes=("_a", "_b"))
    j = j[j["next_due_a"].notna() & j["next_due_b"].notna()]
    assert not j.empty
    assert (pd.to_datetime(j["next_due_b"]) < pd.to_datetime(j["next_due_a"])).all()
    assert (tightened["status"] == "기한초과").sum() >= (
        base["status"] == "기한초과").sum()


def test_only_grade_assigning_models_carry_rating_system_requirements(built):
    """시장 모형과 LGD 모형에는 등급체계 요건이 걸리지 않는다."""
    c = built.tables["crm_lifecycle_compliance"]
    assert set(c["model_id"]) == {"PD_CORP", "PD_RETAIL", "PD_MORTGAGE"}


def test_retail_only_clauses_do_not_reach_corporate_models(built):
    c = built.tables["crm_lifecycle_compliance"]
    corp_rows = c[c["model_id"] == "PD_CORP"]
    assert "CRS-164-A" not in set(corp_rows["requirement_code"])
    assert "CRS-163-A" in set(corp_rows["requirement_code"])


# ----- 등급구조 (151.나) ------------------------------------------------------

def test_grade_structure_check_reads_the_threshold_from_the_ledger():
    r = req.build_rating_requirements()
    out = req.check_grade_structure(sc.non_default_grades(), ["D"], r)
    by = {o["requirement_code"]: o for o in out}
    assert by["CRS-151-NB"]["required"] == 7.0
    assert by["CRS-151-NB"]["meets"] is True
    assert by["CRS-151-D"]["meets"] is True
    # 요건 행이 없으면 통과가 아니라 미판정이다.
    dropped = r[r["requirement_code"] != "CRS-151-NB"]
    out2 = {o["requirement_code"]: o
            for o in req.check_grade_structure(["A", "B"], ["D"], dropped)}
    assert out2["CRS-151-NB"]["meets"] is None
    # 등급이 모자라면 실제로 실패해야 한다.
    out3 = {o["requirement_code"]: o
            for o in req.check_grade_structure(["A", "B"], ["D"], r)}
    assert out3["CRS-151-NB"]["meets"] is False


# ----- 개발표본·대표성 --------------------------------------------------------

def test_dev_sample_fails_the_five_year_observation_requirement(built):
    d = built.tables["crm_dev_sample"]
    assert set(d["segment"]) == {"corporate", "retail_other",
                                 "residential_mortgage"}
    assert (d["min_observation_years"] == 5.0).all()
    assert (d["meets_minimum"] == "부적합").all(), (
        "합성 포트폴리오는 24개월 코호트뿐이므로 5년 요건을 채울 수 없다")
    assert (d["dpd_trigger_days"] == 90).all()
    # 소매는 174.나 단서로 거래 기준 판단이 허용된다.
    retail = d[d["segment"] == "retail_other"].iloc[0]
    assert retail["target_basis"] == "거래기준"
    assert d[d["segment"] == "corporate"].iloc[0]["target_basis"] == "차주기준"


def test_dev_sample_does_not_judge_when_the_requirement_row_is_missing(portfolio):
    r = req.build_rating_requirements()
    r = r[~r["requirement_code"].isin(["CRS-182-D", "CRS-183-B"])]
    d = smp.build_dev_sample(portfolio, r, model_map={"corporate": "PD_CORP"},
                             asof=ASOF, observation_months=24,
                             holdout_share=0.3, scope_map=req.SEGMENT_SCOPE)
    assert d["min_observation_years"].isna().all()
    assert (d["meets_minimum"] == "미판정").all()


def test_representativeness_reports_psi_without_inventing_a_threshold(built):
    t = built.tables["crm_sample_representativeness"]
    assert not t.empty
    assert t["threshold"].isna().all()
    assert (t["assessment"] == "미판정").all()
    assert (t["psi"] >= 0).all()
    assert set(t["feature"]) >= {f for f, _, _ in FINANCIAL_FACTORS}


# ----- 스코어카드 -------------------------------------------------------------

def test_engine_refuses_to_run_without_the_parameter_ledger(corp):
    """모수가 없으면 조용히 기본값을 쓰지 않고 멈춘다."""
    params = sc.build_scorecard_param(CORPORATE_MODEL_ID)
    broken = params[params["parameter"] != "n_bins"]
    with pytest.raises(ValueError, match="n_bins"):
        sc.fit_scorecard(corp, {"leverage": "재무"}, {"leverage": "부채비율"},
                         {"leverage": "증가"}, target="default_12m",
                         params=broken, model_id=CORPORATE_MODEL_ID, seed=SEED)


def test_design_parameters_are_recorded_as_unapproved(built):
    p = built.tables["crm_scorecard_param"]
    assert set(p["parameter"]) == set(sc.PARAM_NAMES)
    assert (p["evidence_status"] == "재량·미규정").all()
    assert (p["approval_status"] == "미승인").all()
    assert p["approved_by"].isna().all()
    # 미승인 모수로 산출된 등급은 산출 원장에서도 미승인이다.
    assert (built.tables["crm_obligor_score"]["param_approval"] == "미승인").all()


def test_bin_count_follows_the_parameter_ledger(corp):
    """구간 수를 원장에서 바꾸면 배점표의 구간 수가 따라 바뀐다."""
    factors = {f: "재무" for f, _, _ in FINANCIAL_FACTORS}
    korean = {f: k for f, k, _ in FINANCIAL_FACTORS}
    expected = {f: s for f, _, s in FINANCIAL_FACTORS}
    counts = {}
    for n_bins in (3, 8):
        p = sc.build_scorecard_param(CORPORATE_MODEL_ID)
        p.loc[p["parameter"] == "n_bins", "value"] = float(n_bins)
        p.loc[p["parameter"] == "min_bin_share", "value"] = 0.01
        fit = sc.fit_scorecard(corp, factors, korean, expected,
                               target="default_12m", params=p,
                               model_id=CORPORATE_MODEL_ID, seed=SEED)
        counts[n_bins] = int(fit.bins[fit.bins["factor"] == "leverage"].shape[0])
    assert counts[3] < counts[8]


def test_thin_bins_are_merged_to_the_minimum_share(built):
    b = built.tables["crm_scorecard_bin"]
    p = built.tables["crm_scorecard_param"]
    min_share = float(p[p["parameter"] == "min_bin_share"]["value"].iloc[0])
    # 병합 후에도 남을 수 있는 마지막 구간을 감안해 근소한 오차를 허용한다.
    assert (b["share"] >= min_share - 1e-9).all()


def test_score_scale_is_a_linear_transform_that_leaves_pd_unchanged(corp):
    """배점 원점·PDO를 바꿔도 PD와 등급은 같아야 한다."""
    factors = {f: "재무" for f, _, _ in FINANCIAL_FACTORS}
    korean = {f: k for f, k, _ in FINANCIAL_FACTORS}
    expected = {f: s for f, _, s in FINANCIAL_FACTORS}
    out = []
    for base, pdo in ((600.0, 20.0), (1000.0, 40.0)):
        p = sc.build_scorecard_param(CORPORATE_MODEL_ID)
        p.loc[p["parameter"] == "base_points", "value"] = base
        p.loc[p["parameter"] == "pdo", "value"] = pdo
        fit = sc.fit_scorecard(corp, factors, korean, expected,
                               target="default_12m", params=p,
                               model_id=CORPORATE_MODEL_ID, seed=SEED)
        s, _ = sc.score_obligors(fit, corp, params=p, asof=ASOF)
        out.append(s)
    assert np.allclose(out[0]["model_pd"], out[1]["model_pd"], atol=1e-9)
    assert list(out[0]["model_grade"]) == list(out[1]["model_grade"])
    assert not np.allclose(out[0]["total_score"], out[1]["total_score"])


def test_axis_weights_come_from_the_fit_and_sum_to_one(built):
    a = built.tables["crm_scorecard_axis"]
    assert set(a["axis"]) == set(sc.AXES)
    assert a["weight"].sum() == pytest.approx(1.0)
    assert (a["n_factors"] > 0).all()
    assert (a["score_std"] > 0).all()


def test_scorecard_separates_defaulters(built, corp):
    s = built.tables["crm_obligor_score"].merge(
        corp[["obligor_id", "default_12m"]], on="obligor_id")
    assert gini(s["default_12m"].to_numpy(), s["model_pd"].to_numpy()) > 0.3
    # 점수는 높을수록 우량이어야 한다.
    assert (s[s["default_12m"] == 1]["total_score"].mean()
            < s[s["default_12m"] == 0]["total_score"].mean())


def test_axis_scores_cover_every_obligor_on_every_axis(built, corp):
    a = built.tables["crm_obligor_axis_score"]
    assert len(a) == len(corp) * len(sc.AXES)
    assert set(a["axis"]) == set(sc.AXES)


def test_qualitative_assessment_stays_inside_the_declared_scale(built, corp):
    items = built.tables["crm_qualitative_item"]
    q = built.tables["crm_qualitative_assessment"]
    assert len(q) == len(corp) * len(items)
    lo = int(items["scale_min"].min())
    hi = int(items["scale_max"].max())
    assert q["score"].between(lo, hi).all()
    assert (q["recorded_by"] == "synthetic").all(), (
        "합성 평가를 실제 심사 기록처럼 표시하면 증적이 아니다")


def test_qualitative_axes_are_used_in_the_scorecard(built):
    f = built.tables["crm_scorecard_factor"]
    assert set(f[f["axis"] == "비재무"]["factor"])
    assert set(f[f["axis"] == "대표자"]["factor"])
    assert (f["iv"] >= 0).all()


# ----- 등급변경 ---------------------------------------------------------------

def test_override_range_is_not_judged_without_an_approved_limit(built):
    o = built.tables["crm_override"]
    reasons = built.tables["crm_override_reason"]
    assert reasons["max_notch"].isna().all()
    assert (o["within_policy_range"] == "미판정").all()
    assert any("165.가(2)" in w for w in built.warnings)


def test_override_range_is_judged_once_the_limit_is_recorded(built):
    o = built.tables["crm_override"]
    reasons = built.tables["crm_override_reason"].copy()
    reasons["max_notch"] = 1.0
    judged, warns = ovr.assess_override_range(o, reasons)
    assert not warns
    assert set(judged["within_policy_range"]) <= {"적합", "초과"}
    assert (judged["within_policy_range"] == "초과").any(), (
        "1단계 상한이면 2단계 이상 조정은 초과로 잡혀야 한다")


def test_override_changes_the_grade_and_the_pd(built):
    o = built.tables["crm_override"]
    assert not o.empty
    assert (o["notch_delta"] != 0).all()
    moved = o[o["model_grade"] != o["final_grade"]]
    assert not moved.empty
    assert (moved["model_pd"] != moved["final_pd"]).all()


def test_override_performance_counts_unapproved_changes(built):
    p = built.tables["crm_override_performance"]
    o = built.tables["crm_override"]
    assert p["n_overrides"].sum() == len(o)
    assert p["n_unapproved"].sum() == int(o["approved_by"].isna().sum())
    assert p["n_unapproved"].sum() > 0, "승인 누락을 잡을 수 없는 원장이다"
    assert (p["assessment"] == "미판정").all()
    assert any("165.가(3)" in w for w in built.warnings)


def test_override_flag_reconciliation_finds_a_split_ledger(built):
    o = built.tables["crm_override"]
    rating = pd.DataFrame({
        "obligor_id": o["obligor_id"],
        "asof": o["asof"],
        "override_flag": 0,          # 등급 이력이 변경을 반영하지 않은 상태
    })
    bad = ovr.reconcile_override_flag(rating, o)
    assert len(bad) == len(o)
    rating["override_flag"] = 1
    assert ovr.reconcile_override_flag(rating, o).empty


# ----- 전체 -------------------------------------------------------------------

def test_every_ledger_validates_against_its_spec(built):
    for name, df in built.tables.items():
        assert name in _SPECS, f"스펙 없는 원장 {name}"
        violations = validate(df, _SPECS[name])
        assert not violations, f"{name}: {violations[:5]}"


def test_foreign_keys_resolve_against_the_upstream_ledgers(built, portfolio,
                                                           models):
    """차주·모형·사유코드 참조가 실제로 걸린다. 고아 행이 있으면 여기서 걸린다."""
    from risk_lib.datamodel import catalog as cat
    from risk_lib.datamodel.spec import check_refs

    specs = dict(_SPECS)
    frames = dict(built.tables)
    frames["crm_model"] = models
    frames["rdm_obligor"] = pd.DataFrame(
        {"obligor_id": portfolio["obligor_id"].unique()})
    for name in ("crm_model", "rdm_obligor"):
        specs[name] = next(s for s in cat.ALL_TABLES if s.name == name)
    assert not check_refs(frames, specs)


def test_build_is_deterministic(portfolio, models, built):
    again = build_credit_rating(portfolio, models, asof=ASOF, seed=SEED)
    assert set(again.tables) == set(built.tables)
    for name, df in built.tables.items():
        pd.testing.assert_frame_equal(df, again.tables[name])
    assert again.warnings == built.warnings


def test_warnings_name_the_clause_that_could_not_be_met(built):
    assert built.warnings
    assert all("[별표 3]" in w for w in built.warnings)
