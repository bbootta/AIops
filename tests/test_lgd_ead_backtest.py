"""LGD·EAD(CCF) 실측 모니터링·검증 원장 테스트.

확인 대상
  * 원장 넉 장이 TableSpec 검증과 참조무결성을 통과한다
  * 판정기준이 미승인·미정이면 통과여부를 찍지 않는다
  * 관측중단 건이 검정 표본에서 빠지고 n_censored로 남는다
  * 실측 CCF가 정의식대로 나온다
  * (asof, seed) 고정에서 결과가 같다
"""

import warnings

import numpy as np
import pandas as pd
import pytest

from risk_lib.capital.crm import CCF_BUCKETS
from risk_lib.data_gen import generate_portfolio
from risk_lib.datamodel import catalog as cat
from risk_lib.datamodel.decompose import decompose
from risk_lib.datamodel.spec import check_refs, validate
from risk_lib.models import lgd_ead_backtest as bt


ASOF = "2026-06-30"


@pytest.fixture(scope="module")
def rdm():
    p = generate_portfolio()
    return p, decompose(p, asof=ASOF)


@pytest.fixture(scope="module")
def approved_criteria():
    return bt.approve_criteria(
        bt.build_backtest_criteria(), approved_by="리스크관리부장",
        approved_on="2026-07-15", approval_body="모형위원회")


def _param(criteria, criteria_set_id, param):
    """판정기준 값은 원장에서 읽는다. 테스트가 임계를 다시 적으면 사본이 갈라진다."""
    row = criteria[(criteria["criteria_set_id"] == criteria_set_id)
                   & (criteria["param"] == param)]
    return float(row["param_value"].iloc[0])


def _ledgers(rdm, criteria=None):
    p, base = rdm
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", bt.BacktestLedgerWarning)
        return bt.build_lgd_ead_backtest_ledgers(
            p, base["rdm_exposure"], asof=ASOF, criteria=criteria,
            collateral=base["rdm_collateral"])


# -------------------------------------------------- 판정기준 원장


def test_criteria_ships_unapproved_internal_rows():
    """규정 수치를 확인하지 못했으므로 전건이 내부기준·미승인이어야 한다."""
    c = bt.build_backtest_criteria()
    assert not c.empty
    assert (c["basis"] == "내부기준").all()
    assert (c["evidence_status"] == "미확인").all()
    assert c["approved_by"].isna().all()
    assert c["approved_on"].isna().all()
    assert len(bt.unapproved_criteria(c)) == len(c)


def test_criteria_spec_and_pk():
    c = bt.build_backtest_criteria()
    assert [str(v) for v in validate(c, bt.BACKTEST_CRITERIA)] == []
    assert not c.duplicated(subset=["criteria_set_id", "param"]).any()


def test_load_criteria_status_transitions(approved_criteria):
    """임계 미입력은 기준미정, 값은 있고 승인이 없으면 기준미승인."""
    c = bt.build_backtest_criteria()
    with pytest.warns(bt.BacktestLedgerWarning):
        _, status = bt.load_criteria(c, bt.LGD_CRITERIA_SET,
                                     gating=("mae_tolerance",))
    assert status == "기준미승인"

    blank = c.copy()
    blank.loc[blank["param"] == "mae_tolerance", "param_value"] = np.nan
    with pytest.warns(bt.BacktestLedgerWarning):
        values, status = bt.load_criteria(blank, bt.LGD_CRITERIA_SET,
                                          gating=("mae_tolerance",))
    assert status == "기준미정" and values["mae_tolerance"] is None

    values, status = bt.load_criteria(
        approved_criteria, bt.LGD_CRITERIA_SET, gating=("mae_tolerance",))
    assert status == "판정완료" and values["mae_tolerance"] == pytest.approx(0.10)


def test_approve_criteria_rejects_unknown_body():
    with pytest.raises(ValueError):
        bt.approve_criteria(bt.build_backtest_criteria(),
                            approved_by="갑", approved_on="2026-07-15",
                            approval_body="사장님")


def test_approve_criteria_scoped_to_one_set(approved_criteria):
    c = bt.approve_criteria(bt.build_backtest_criteria(), approved_by="갑",
                            approved_on="2026-07-15",
                            approval_body="리스크관리위원회",
                            criteria_set_id=bt.CCF_CRITERIA_SET)
    left = bt.unapproved_criteria(c)
    assert set(left["criteria_set_id"]) == {bt.LGD_CRITERIA_SET}
    assert bt.unapproved_criteria(approved_criteria).empty


# -------------------------------------------------- 원장 스펙·참조무결성


def test_all_four_ledgers_pass_spec(rdm, approved_criteria):
    t = _ledgers(rdm, approved_criteria)
    for spec in bt.BACKTEST_TABLES:
        assert [str(v) for v in validate(t[spec.name], spec)] == [], spec.name


def test_foreign_keys_resolve(rdm, approved_criteria):
    _, base = rdm
    t = _ledgers(rdm, approved_criteria)
    tables = dict(base)
    tables.update(t)
    specs = {s.name: s for s in bt.BACKTEST_TABLES}
    assert [str(v) for v in check_refs(tables, specs)] == []


def test_ledger_grains_are_unique(rdm, approved_criteria):
    t = _ledgers(rdm, approved_criteria)
    for spec in bt.BACKTEST_TABLES:
        df = t[spec.name]
        assert not df.duplicated(subset=list(spec.primary_key)).any(), spec.name


def test_determinism(rdm, approved_criteria):
    a = _ledgers(rdm, approved_criteria)
    b = _ledgers(rdm, approved_criteria)
    for name in a:
        pd.testing.assert_frame_equal(a[name], b[name])


# -------------------------------------------------- 관측원장·관측중단


def test_observation_covers_every_default(rdm, approved_criteria):
    p, _ = rdm
    t = _ledgers(rdm, approved_criteria)
    obs = t["crm_default_observation"]
    assert len(obs) == int(p["default_12m"].sum())
    assert set(obs["exposure_id"]) == set(
        p.loc[p["default_12m"] == 1, "exposure_id"])
    assert (obs["source_system"] == "synthetic").all()


def test_censoring_splits_by_workout_period(rdm, approved_criteria):
    t = _ledgers(rdm, approved_criteria)
    obs = t["crm_default_observation"]
    period = float(obs["workout_period_months"].iloc[0])
    done = obs["months_since_default"] >= period
    assert (obs.loc[done, "censoring_status"] == "회수종료").all()
    assert (obs.loc[~done, "censoring_status"] == "관측중단").all()
    # 두 상태가 모두 나와야 관측중단 처리가 실제로 작동하는지 확인된다.
    assert done.any() and (~done).any()


def test_censored_defaults_excluded_from_test_sample(rdm, approved_criteria):
    t = _ledgers(rdm, approved_criteria)
    obs, lgd = t["crm_default_observation"], t["crm_lgd_backtest"]
    seg = lgd[lgd["segment_axis"] == "segment"]
    assert int(seg["n_defaults"].sum()) == int(
        (obs["censoring_status"] == "회수종료").sum())
    assert int(seg["n_censored"].sum()) == int(
        (obs["censoring_status"] == "관측중단").sum())


def test_missing_workout_period_blocks_censoring_judgment(rdm):
    """회수기간 기준이 비면 관측중단을 판정하지 않고 검정도 하지 않는다."""
    c = bt.build_backtest_criteria()
    c.loc[c["param"] == "workout_period_months", "param_value"] = np.nan
    t = _ledgers(rdm, c)
    obs, lgd = t["crm_default_observation"], t["crm_lgd_backtest"]
    assert (obs["censoring_status"] == "판정불가").all()
    assert obs["workout_complete"].isna().all()
    assert set(lgd["judgment_status"]) == {"기준미정"}
    assert lgd["pass_flag"].isna().all()
    assert int(lgd["n_defaults"].sum()) == 0


def test_observation_warns_when_criteria_blank(rdm):
    p, base = rdm
    c = bt.build_backtest_criteria()
    c.loc[c["param"] == "workout_period_months", "param_value"] = np.nan
    with pytest.warns(bt.BacktestLedgerWarning):
        bt.build_default_observation(p, base["rdm_exposure"], asof=ASOF,
                                     criteria=c)


def test_observation_requires_source_columns(rdm):
    p, base = rdm
    with pytest.raises(ValueError):
        bt.build_default_observation(p.drop(columns=["lgd_realized"]),
                                     base["rdm_exposure"], asof=ASOF)
    with pytest.raises(ValueError):
        bt.build_default_observation(p, base["rdm_exposure"].drop(
            columns=["undrawn"]), asof=ASOF)


# -------------------------------------------------- LGD 백테스트


def test_lgd_bias_and_error_match_definition(rdm, approved_criteria):
    t = _ledgers(rdm, approved_criteria)
    obs, lgd = t["crm_default_observation"], t["crm_lgd_backtest"]
    done = obs[obs["censoring_status"] == "회수종료"]
    row = lgd[(lgd["segment_axis"] == "segment")
              & (lgd["segment_value"] == "retail_other")].iloc[0]
    cell = done[done["segment"] == "retail_other"]
    d = (cell["lgd_realized"] - cell["lgd_estimated"]).to_numpy()
    assert row["bias"] == pytest.approx(float(np.mean(d)))
    assert row["mae"] == pytest.approx(float(np.mean(np.abs(d))))
    assert row["rmse"] == pytest.approx(float(np.sqrt(np.mean(d ** 2))))
    assert row["lgd_realized_mean"] - row["lgd_estimated_mean"] == \
        pytest.approx(row["bias"])


def test_lgd_drops_defaults_without_a_realised_value(rdm, approved_criteria):
    """실현 LGD가 비면 편의를 만들 수 없으므로 평균과 검정에서 함께 빠진다."""
    t = _ledgers(rdm, approved_criteria)
    obs = t["crm_default_observation"].copy()
    done = obs["censoring_status"] == "회수종료"
    target = obs.index[done & (obs["segment"] == "retail_other")][:5]
    obs.loc[target, "lgd_realized"] = np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", bt.BacktestLedgerWarning)
        holed = bt.build_lgd_backtest(obs, approved_criteria, asof=ASOF)
    full = t["crm_lgd_backtest"]

    def _row(df):
        return df[(df["segment_axis"] == "segment")
                  & (df["segment_value"] == "retail_other")].iloc[0]

    assert _row(holed)["n_defaults"] == _row(full)["n_defaults"] - len(target)
    kept = obs.loc[done & (obs["segment"] == "retail_other")
                   & obs["lgd_realized"].notna()]
    assert _row(holed)["lgd_estimated_mean"] == pytest.approx(
        float(kept["lgd_estimated"].mean()))


def test_lgd_confidence_interval_brackets_bias(rdm, approved_criteria):
    t = _ledgers(rdm, approved_criteria)
    lgd = t["crm_lgd_backtest"]
    ok = lgd[lgd["ci_low"].notna()]
    assert not ok.empty
    assert (ok["ci_low"] <= ok["bias"]).all()
    assert (ok["bias"] <= ok["ci_high"]).all()


def test_lgd_axes_are_marginal_slices(rdm, approved_criteria):
    t = _ledgers(rdm, approved_criteria)
    lgd = t["crm_lgd_backtest"]
    assert set(lgd["segment_axis"]) <= set(bt.LGD_SEGMENT_AXES)
    # 축마다 같은 모집단을 다르게 자른 것이므로 검정 표본 합이 일치해야 한다.
    totals = lgd.groupby("segment_axis")["n_defaults"].sum()
    assert totals.nunique() == 1


def test_unapproved_criteria_leave_pass_flag_empty(rdm):
    t = _ledgers(rdm)          # 기본 원장은 미승인 상태다
    for name in ("crm_lgd_backtest", "crm_ccf_backtest"):
        df = t[name]
        assert df["pass_flag"].isna().all(), name
        assert set(df["judgment_status"]) == {"기준미승인"}, name


def test_small_cells_are_not_judged(rdm, approved_criteria):
    t = _ledgers(rdm, approved_criteria)
    lgd = t["crm_lgd_backtest"]
    min_n = _param(approved_criteria, bt.LGD_CRITERIA_SET, "min_n_defaults")
    small = lgd[lgd["n_defaults"] < min_n]
    assert not small.empty
    assert small["pass_flag"].isna().all()
    assert set(small["judgment_status"]) == {"표본부족"}


def test_lgd_pass_flag_follows_criteria(rdm, approved_criteria):
    t = _ledgers(rdm, approved_criteria)
    lgd = t["crm_lgd_backtest"]
    alpha = _param(approved_criteria, bt.LGD_CRITERIA_SET, "significance_level")
    mae_tol = _param(approved_criteria, bt.LGD_CRITERIA_SET, "mae_tolerance")
    judged = lgd[lgd["judgment_status"] == "판정완료"]
    assert not judged.empty
    expected = (judged["p_value"] >= alpha) & (judged["mae"] <= mae_tol)
    assert (judged["pass_flag"].astype(bool) == expected).all()


def test_tight_mae_tolerance_flips_pass_to_fail(rdm, approved_criteria):
    """임계가 산출을 실제로 가르는지 확인한다."""
    loose = _ledgers(rdm, approved_criteria)["crm_lgd_backtest"]
    tight = approved_criteria.copy()
    tight.loc[tight["param"] == "mae_tolerance", "param_value"] = 0.0
    strict = _ledgers(rdm, tight)["crm_lgd_backtest"]
    judged = strict["judgment_status"] == "판정완료"
    assert judged.any()
    assert not strict.loc[judged, "pass_flag"].astype(bool).any()
    assert loose.loc[loose["judgment_status"] == "판정완료",
                     "pass_flag"].astype(bool).any()


# -------------------------------------------------- CCF 백테스트


def test_ccf_realized_matches_definition(rdm, approved_criteria):
    """실측 CCF = (부도시 인출액 − 기준시 인출액) / 기준시 미인출액."""
    t = _ledgers(rdm, approved_criteria)
    obs, ccf = t["crm_default_observation"], t["crm_ccf_backtest"]
    row = ccf.iloc[0]
    cell = obs[(obs["ccf_type"] == row["ccf_type"])
               & (obs["grade_band"] == row["grade_band"])
               & (obs["undrawn_at_ref"] > 0)]
    assert int(len(cell)) == int(row["n_facilities"])
    assert row["undrawn_at_ref"] == pytest.approx(
        float(cell["undrawn_at_ref"].sum()))
    assert row["drawn_at_default"] == pytest.approx(
        float(cell["drawn_at_default"].sum()))
    assert row["ccf_realized"] == pytest.approx(
        (row["drawn_at_default"] - row["drawn_at_ref"]) / row["undrawn_at_ref"])
    assert row["ccf_realized_mean"] == pytest.approx(
        float(cell["ccf_realized"].mean()))
    assert row["bias"] == pytest.approx(
        row["ccf_realized_mean"] - row["ccf_applied"])


def test_ccf_applied_comes_from_the_regulatory_table(rdm, approved_criteria):
    """적용 CCF는 저장소의 CCF_BUCKETS 한 곳에서만 온다."""
    t = _ledgers(rdm, approved_criteria)
    ccf = t["crm_ccf_backtest"]
    for _, r in ccf.iterrows():
        assert r["ccf_applied"] == pytest.approx(CCF_BUCKETS[r["ccf_type"]])
    assert set(ccf["ccf_type"]) <= set(cat.CCF_TYPES)
    assert set(ccf["grade_band"]) <= set(bt.GRADE_BANDS)


def test_ccf_population_is_defaults_with_commitments(rdm, approved_criteria):
    t = _ledgers(rdm, approved_criteria)
    obs, ccf = t["crm_default_observation"], t["crm_ccf_backtest"]
    eligible = obs[obs["ccf_type"].notna() & (obs["undrawn_at_ref"] > 0)]
    assert int(ccf["n_facilities"].sum()) == len(eligible)
    # 미인출액이 없는 부도건은 분모가 없어 실측 CCF가 정의되지 않는다.
    assert obs.loc[obs["undrawn_at_ref"] <= 0, "ccf_realized"].isna().all()


def test_ccf_drawdown_stays_within_the_committed_limit(rdm, approved_criteria):
    t = _ledgers(rdm, approved_criteria)
    obs = t["crm_default_observation"]
    limit = obs["drawn_at_ref"] + obs["undrawn_at_ref"]
    assert (obs["drawn_at_default"] <= limit + 1e-6).all()
    assert (obs["drawn_at_default"] >= -1e-6).all()


def test_ccf_pass_flag_follows_criteria(rdm, approved_criteria):
    t = _ledgers(rdm, approved_criteria)
    ccf = t["crm_ccf_backtest"]
    alpha = _param(approved_criteria, bt.CCF_CRITERIA_SET, "significance_level")
    bias_tol = _param(approved_criteria, bt.CCF_CRITERIA_SET, "bias_tolerance")
    judged = ccf[ccf["judgment_status"] == "판정완료"]
    assert not judged.empty
    expected = (judged["p_value"] >= alpha) & (judged["bias"].abs() <= bias_tol)
    assert (judged["pass_flag"].astype(bool) == expected).all()


# -------------------------------------------------- 경계


def test_empty_default_population_returns_empty_ledgers(rdm):
    p, base = rdm
    clean = p.copy()
    clean["default_12m"] = 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", bt.BacktestLedgerWarning)
        t = bt.build_lgd_ead_backtest_ledgers(
            clean, base["rdm_exposure"], asof=ASOF,
            collateral=base["rdm_collateral"])
    specs = {s.name: s for s in bt.BACKTEST_TABLES}
    for name in ("crm_default_observation", "crm_lgd_backtest",
                 "crm_ccf_backtest"):
        assert t[name].empty, name
        # 부도가 없는 기준일에도 원장은 스펙을 통과해야 한다.
        assert [str(v) for v in validate(t[name], specs[name])] == [], name
    assert list(t["crm_lgd_backtest"].columns) == list(
        bt.LGD_BACKTEST.column_names)


def test_missing_collateral_ledger_falls_back_to_unsecured(rdm):
    p, base = rdm
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", bt.BacktestLedgerWarning)
        obs = bt.build_default_observation(p, base["rdm_exposure"], asof=ASOF)
    assert (obs["collateral_type"] == "무담보").all()


def test_lookback_months_must_be_positive(rdm):
    p, base = rdm
    with pytest.raises(ValueError):
        bt.build_default_observation(p, base["rdm_exposure"], asof=ASOF,
                                     lookback_months=0)
