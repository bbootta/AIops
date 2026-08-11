"""부도자산 PLGD 시험 ([별표 3] 185.바 후단).

시험의 축은 다섯이다.

1. **결정.** 시뮬레이션이 실제로 분모와 DSF 반영형태를 갈라내는가. 갈라내지
   못하는 조건(할인율 0)에서는 판정불가가 나오는가.
2. **비어 있음.** 신뢰수준 q가 승인되기 전에는 PLGD가 산출되지 않고, 승인 기록
   없이 값만 넣으면 거부되는가.
3. **민감도.** q가 자본을 움직이고 충당금은 움직이지 않는가. 꼬리 표본이 q와
   함께 마르는가.
4. **음성 대조.** 검사에 위반을 주입하면 실제로 FAIL·WARN이 뜨는가.
5. **결정론.** 같은 (asof, seed)면 별도 프로세스에서도 결과가 같은가.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import warnings

import numpy as np
import pandas as pd
import pytest

from risk_lib.datamodel.spec import check_refs, validate
from risk_lib.models.estimation.history import build_history_ledgers
from risk_lib.models.estimation.lgd_est import (
    DEFAULTED_LGD, build_defaulted_lgd, estimate_lgd,
)
from risk_lib.models.estimation.params import (
    ParamWarning, approve_discount_rate, build_estimation_param_ledgers,
)
from risk_lib.models.estimation.plgd import (
    BEEL_CURVE, BEEL_DENOMINATORS, PLGD, PLGD_SENSITIVITY, PLGD_TABLES,
    SENSITIVITY_Q_GRID, beel_by_default, build_crm_beel_curve, build_crm_plgd,
    build_crm_plgd_sensitivity, build_plgd_ledgers, check_beel_monotonicity,
    check_plgd_not_below_elbe, check_plgd_provision_justification,
    decide_beel_denominator, decide_dsf_form, defaulted_capital_requirement,
    run_plgd_checks,
)
from risk_lib.validation.consistency import ValidationReport

ASOF = "2026-06-30"
SEED = 42
# 시험용 승인 기록이다. 규정 수치가 아니고 저장소 산출물의 기본값도 아니다.
_TEST_DISCOUNT_RATE = 0.11
_TEST_Q = 0.95
_APPROVER = "시험 모형위원회"
_APPROVAL_DATE = "2026-03-01"


def _rates(rate: float = _TEST_DISCOUNT_RATE) -> pd.DataFrame:
    r = build_estimation_param_ledgers(ASOF)["crm_lgd_discount_rate"]
    for seg in ("corporate", "retail_other", "residential_mortgage"):
        r = approve_discount_rate(r, asof=ASOF, segment=seg,
                                  recovery_scope="전체", rate=rate,
                                  basis="자기자본비용", approved_by="시험",
                                  approval_date="2026-01-01")
    return r


@pytest.fixture(scope="module")
def recovery() -> pd.DataFrame:
    return build_history_ledgers(asof=ASOF, seed=SEED,
                                 years=8)["crm_recovery_history"]


@pytest.fixture(scope="module")
def curve(recovery) -> pd.DataFrame:
    return build_crm_beel_curve(recovery, asof=ASOF, rates=_rates(),
                                confidence_q=_TEST_Q)


@pytest.fixture(scope="module")
def ledgers(recovery) -> dict[str, pd.DataFrame]:
    return build_plgd_ledgers(recovery, asof=ASOF, rates=_rates(),
                              confidence_q=_TEST_Q, approved_by=_APPROVER,
                              approval_date=_APPROVAL_DATE)


# ---------------------------------------------------------------- 원장 스펙

def test_ledgers_pass_spec(ledgers):
    """원장 석 장이 자기 스펙을 통과하고 FK 대상이 존재한다."""
    for name, spec in PLGD_TABLES.items():
        assert name in ledgers, f"{name} 산출 누락"
        violations = validate(ledgers[name], spec)
        assert not violations, f"{name}: {[str(v) for v in violations]}"
    assert not check_refs(ledgers, PLGD_TABLES)


def test_both_denominators_are_produced(curve):
    """분모 두 후보의 곡선이 모두 있고 적용 분모는 하나다."""
    assert set(curve["beel_denominator"]) == set(BEEL_DENOMINATORS)
    applied = set(curve.loc[curve["is_applied_denominator"].astype(bool),
                            "beel_denominator"])
    assert len(applied) == 1


# ---------------------------------------------------------------- 분모 결정

def test_denominator_decided_by_monotonicity(curve):
    """부도시익스포저 분모가 전 세그먼트에서 우상향을 만든다.

    잔여익스포저 분모는 회수가 큰 세그먼트(주거용주택담보)에서 우상향이 깨진다.
    분자의 미래 회수가 줄어드는 효과와 할인 되감기가 반대 방향으로 작용하는데,
    손실률이 낮을수록 되감기가 이긴다.
    """
    per_seg = (curve.groupby(["beel_denominator", "segment"])
               ["monotonicity_rho"].first())
    for seg in ("corporate", "retail_other", "residential_mortgage"):
        assert per_seg[("부도시익스포저", seg)] > 0.9, seg
    assert per_seg[("잔여익스포저", "residential_mortgage")] < 0.0

    decision = decide_beel_denominator(curve)
    assert decision["verdict"] == "판정완료"
    assert decision["denominator"] == "부도시익스포저"
    assert decision["detail"]["부도시익스포저"]["n_monotone"] == 3
    assert decision["detail"]["잔여익스포저"]["n_monotone"] == 2


def test_denominator_undecided_without_discounting(recovery):
    """할인율이 0이면 두 분모 모두 우상향해 판정이 갈리지 않는다.

    분모 판정이 할인 되감기에 기대고 있다는 사실을 드러낸다. 갈리지 않는 상태를
    한쪽으로 밀지 않고 판정불가로 남기는지도 함께 본다.
    """
    c = build_crm_beel_curve(recovery, asof=ASOF, rates=_rates(0.0))
    per_seg = (c.groupby(["beel_denominator", "segment"])
               ["monotonicity_verdict"].first())
    assert set(per_seg) == {"단조증가"}
    decision = decide_beel_denominator(c)
    assert decision["verdict"] == "판정불가"
    assert decision["denominator"] is None
    assert not c["is_applied_denominator"].any()


def test_undecided_denominator_produces_no_plgd(recovery):
    """판정하지 못하면 PLGD 원장을 만들지 않는다. 한쪽으로 밀지 않는다."""
    out = build_plgd_ledgers(recovery, asof=ASOF, rates=_rates(0.0),
                             confidence_q=_TEST_Q, approved_by=_APPROVER,
                             approval_date=_APPROVAL_DATE)
    assert out[PLGD.name].empty
    assert out[PLGD_SENSITIVITY.name].empty
    assert not out[BEEL_CURVE.name].empty


# ---------------------------------------------------------------- DSF 형태

def test_dsf_form_is_multiplicative(curve):
    """경과월에 걸친 변동계수가 승산 쪽에서 작다.

    교안은 'Downturn Scaling Factor를 반영'이라고만 적어 승산·가산이 갈리지
    않는다. 분위수와 평균의 비(比)가 차(差)보다 경과월에 걸쳐 안정적이면 승산이
    자연스러운 형태다.
    """
    form = decide_dsf_form(curve, confidence_q=_TEST_Q,
                           denominator="부도시익스포저")
    assert form["verdict"] == "판정완료"
    assert form["form"] == "승산"
    for seg, d in form["detail"].items():
        assert d["cv_승산_전구간"] < d["cv_가산_전구간"], seg


def test_dsf_recorded_only_with_its_form(ledgers):
    """DSF 값과 반영형태는 같이 있거나 같이 없다. 단위가 형태에 매여 있다."""
    p = ledgers[PLGD.name]
    both = p["dsf"].notna() == p["dsf_form"].notna()
    assert both.all()
    seg = p[p["segment"] == "corporate"].iloc[0]
    if seg["dsf_form"] == "승산":
        assert seg["dsf"] == pytest.approx(seg["plgd"] / seg["elbe"])


# ---------------------------------------------------------------- 신뢰수준

def test_plgd_blocked_without_approved_q(recovery, curve):
    """q가 승인되기 전에는 PLGD를 계산하지 않고 ELBE만 남긴다."""
    c = build_crm_beel_curve(recovery, asof=ASOF, rates=_rates())
    assert c["beel_q"].isna().all()
    p = build_crm_plgd(recovery, c, asof=ASOF, denominator="부도시익스포저")
    assert p["plgd"].isna().all()
    assert p["elbe"].notna().all()
    assert (p["confidence_q_status"] == "미승인").all()
    assert (p["method"] == "미산출").all()
    assert (p["status"].str.startswith("산출불가(신뢰수준미승인)")).all()


def test_q_requires_approval_record(recovery, curve):
    """승인자·승인일 없이 q만 넣으면 거부한다."""
    with pytest.raises(ValueError, match="승인자"):
        build_crm_plgd(recovery, curve, asof=ASOF,
                       denominator="부도시익스포저", confidence_q=_TEST_Q)
    with pytest.raises(ValueError):
        build_crm_plgd(recovery, curve, asof=ASOF,
                       denominator="부도시익스포저", confidence_q=1.5,
                       approved_by=_APPROVER, approval_date=_APPROVAL_DATE)


def test_approved_q_is_recorded_on_the_row(ledgers):
    """승인된 q와 승인 기록이 원장에 함께 남는다."""
    p = ledgers[PLGD.name]
    assert (p["confidence_q"] == _TEST_Q).all()
    assert (p["approved_by"] == _APPROVER).all()
    assert (p["approval_date"] == _APPROVAL_DATE).all()
    assert (p["evidence_status"] == "추론").all()


# ---------------------------------------------------------------- 민감도

def test_sensitivity_moves_capital_not_provisions(ledgers):
    """q는 자본을 움직이고 충당금은 움직이지 않는다.

    120.가(2) 주4)가 부도자산의 EL을 185.바의 최적추정치로 정하므로 q가 바뀌어도
    EL은 ELBE 그대로다. 움직이는 것은 max(0, PLGD − ELBE)뿐이다.
    """
    s = ledgers[PLGD_SENSITIVITY.name]
    assert sorted(set(s["confidence_q"])) == sorted(SENSITIVITY_Q_GRID)
    for seg, g in s.groupby("segment"):
        g = g.sort_values("confidence_q")
        assert g["plgd"].is_monotonic_increasing, seg
        assert g["capital_requirement_k"].is_monotonic_increasing, seg
        assert g["rwa"].is_monotonic_increasing, seg
        assert g["rwa"].iloc[-1] > g["rwa"].iloc[0] * 1.2, seg
        assert (g["provision_delta_vs_lowest_q"] == 0.0).all(), seg
        assert g["elbe"].nunique() == 1, seg


def test_sensitivity_tail_support_dries_up(ledgers):
    """q가 오를수록 분위수를 받치는 꼬리 표본이 줄고 어딘가는 0이 된다."""
    s = ledgers[PLGD_SENSITIVITY.name]
    for seg, g in s.groupby("segment"):
        g = g.sort_values("confidence_q")
        assert g["min_tail_observations"].is_monotonic_decreasing, seg
    top = s[s["confidence_q"] == max(SENSITIVITY_Q_GRID)]
    assert (top["min_tail_observations"] == 0).any(), (
        "가장 높은 후보에서도 꼬리 표본이 남으면 이 시험이 아무것도 지키지 않는다")


def test_rwa_uses_regulatory_multiplier(ledgers):
    """RWA = 소요자기자본율 × 배수 × 익스포저. 배수는 원장 컬럼이다."""
    s = ledgers[PLGD_SENSITIVITY.name].dropna(subset=["rwa"])
    assert not s.empty
    expect = (s["capital_requirement_k"] * s["rwa_multiplier"]
              * s["ead_at_default_open"])
    assert np.allclose(s["rwa"].to_numpy(), expect.to_numpy())
    assert s["rwa_multiplier"].nunique() == 1


def test_capital_requirement_floors_at_zero():
    """K = max(0, LGD_in_default − ELBE). 120.가(2) 주1)의 0 하한."""
    assert defaulted_capital_requirement(0.80, 0.50) == pytest.approx(0.30)
    assert defaulted_capital_requirement(0.40, 0.50) == 0.0
    assert defaulted_capital_requirement(None, 0.5) is None
    assert defaulted_capital_requirement(0.5, None) is None


# ---------------------------------------------------------------- 관측중단

def test_censored_workouts_are_counted_not_averaged(curve, recovery):
    """미종결 부도는 평균에서 빼고 건수로 남긴다. 포함 평균도 함께 낸다."""
    c = curve[curve["beel_denominator"] == "부도시익스포저"]
    assert c["observation_censored"].sum() > 0
    short = c[c["months_since_default"] <= 12]
    assert short["observation_censored"].sum() > 0, (
        "경과월이 짧은 구간에 관측중단이 없으면 편의를 보일 수 없다")
    both = c.dropna(subset=["beel_mean", "beel_mean_incl_censored"])
    assert np.allclose(
        both["censoring_impact"].to_numpy(),
        (both["beel_mean_incl_censored"] - both["beel_mean"]).to_numpy())
    with_cens = both[both["observation_censored"] > 0]
    assert (with_cens["censoring_impact"] > 0).mean() > 0.5, (
        "미종결 건을 넣었는데 평균이 낮아지는 쪽이 다수면 관측중단 처리가 "
        "보수 방향이라는 설명이 성립하지 않는다")


def test_open_workouts_are_excluded_from_the_curve_mean(recovery):
    """곡선 평균은 회수종결 건만 쓴다."""
    per = beel_by_default(recovery[recovery["segment"] == "corporate"],
                          discount_rate=_TEST_DISCOUNT_RATE, asof=ASOF)
    assert per["workout_open"].any()
    c = build_crm_beel_curve(recovery, asof=ASOF, rates=_rates(),
                             confidence_q=_TEST_Q)
    row = c[(c["segment"] == "corporate")
            & (c["beel_denominator"] == "부도시익스포저")
            & (c["months_since_default"] == 6)].iloc[0]
    sub = per[per["months_since_default"] == 6]
    closed = sub[~sub["workout_open"].astype(bool)]
    assert row["n_defaults"] == len(closed)
    assert row["beel_mean"] == pytest.approx(
        float(closed["beel_부도시익스포저"].mean()))


# ---------------------------------------------------------------- 185.바

def test_provision_comparison_is_asymmetric(recovery, curve):
    """ELBE가 충당금+상각보다 작을 때만 입증책임이 붙는다."""
    big = pd.DataFrame({"segment": ["corporate"],
                        "specific_provision": [1e13],
                        "partial_writeoff": [0.0]})
    p = build_crm_plgd(recovery, curve, asof=ASOF,
                       denominator="부도시익스포저", confidence_q=_TEST_Q,
                       approved_by=_APPROVER, approval_date=_APPROVAL_DATE,
                       provisions=big)
    row = p[p["segment"] == "corporate"].iloc[0]
    assert row["shortfall"] > 0
    assert bool(row["justification_required"]) is True

    small = pd.DataFrame({"segment": ["corporate"],
                          "specific_provision": [1.0],
                          "partial_writeoff": [0.0]})
    p2 = build_crm_plgd(recovery, curve, asof=ASOF,
                        denominator="부도시익스포저", confidence_q=_TEST_Q,
                        approved_by=_APPROVER, approval_date=_APPROVAL_DATE,
                        provisions=small)
    row2 = p2[p2["segment"] == "corporate"].iloc[0]
    assert row2["shortfall"] < 0
    assert bool(row2["justification_required"]) is False
    # 충당금 자료가 없는 세그먼트는 판정하지 않는다. False가 아니다.
    other = p2[p2["segment"] == "retail_other"].iloc[0]
    assert pd.isna(other["justification_required"])


def _status(fn, *args) -> str:
    rep = ValidationReport()
    fn(*args, rep)
    return rep.checks[-1].status


def test_check_provision_justification_fails_on_violation(ledgers):
    """입증이 필요한데 문서가 없으면 FAIL."""
    p = ledgers[PLGD.name]
    assert _status(check_plgd_provision_justification, p) == "PASS"
    bad = p.copy()
    bad.loc[bad.index[0], "justification_required"] = True
    bad.loc[bad.index[0], "justification_ref"] = None
    assert _status(check_plgd_provision_justification, bad) == "FAIL"
    ok = bad.copy()
    ok.loc[ok.index[0], "justification_ref"] = "모형위원회 2026-03 의결"
    assert _status(check_plgd_provision_justification, ok) == "PASS"


def test_check_addon_sign_fails_on_violation(ledgers):
    """PLGD가 ELBE보다 작으면 FAIL. 조문은 '추가' 반영을 요구한다."""
    p = ledgers[PLGD.name]
    assert _status(check_plgd_not_below_elbe, p) == "PASS"
    bad = p.copy()
    bad.loc[bad.index[0], "plgd"] = float(bad.loc[bad.index[0], "elbe"]) - 0.01
    assert _status(check_plgd_not_below_elbe, bad) == "FAIL"


def test_check_monotonicity_warns_on_violation(ledgers):
    """적용 분모 곡선이 우상향하지 않으면 WARN. 데이터 품질 신호다."""
    c = ledgers[BEEL_CURVE.name]
    assert _status(check_beel_monotonicity, c) == "PASS"
    bad = c.copy()
    bad.loc[bad["is_applied_denominator"].astype(bool)
            & (bad["segment"] == "corporate"),
            "monotonicity_verdict"] = "단조증가아님"
    assert _status(check_beel_monotonicity, bad) == "WARN"


def test_check_suite_has_no_failures(ledgers):
    rep = run_plgd_checks(ledgers)
    fails = [c for c in rep.checks if c.status == "FAIL"]
    assert not fails, [str(c) for c in fails]
    assert len(rep.checks) >= 3


# ---------------------------------------------------------------- 배선

def test_defaulted_lgd_picks_up_plgd(recovery, ledgers):
    """crm_defaulted_lgd가 PLGD를 받아 추가분과 적용 LGD를 채운다."""
    params = build_estimation_param_ledgers(ASOF)
    dh = build_history_ledgers(asof=ASOF, seed=SEED,
                               years=8)["crm_default_history"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        est = estimate_lgd(recovery, dh, floors=params["crm_input_floor"],
                           param=params["crm_estimation_param"],
                           rates=_rates(), asof=ASOF)["crm_lgd_estimate"]
    plain = build_defaulted_lgd(recovery, est, asof=ASOF)
    assert (plain["addon_status"] == "미산출(근거미확인)").all()
    assert plain["unexpected_loss_addon"].isna().all()

    wired = build_defaulted_lgd(recovery, est, asof=ASOF,
                                plgd=ledgers[PLGD.name])
    assert (wired["addon_status"] == "산출완료").all()
    assert wired["unexpected_loss_addon"].notna().all()
    # 한 행 안에서 항등식이 닫힌다. ELBE도 곡선 기준으로 바뀌어야 닫힌다.
    assert np.allclose(
        (wired["lgd_in_default"] - wired["elbe"]).to_numpy(),
        wired["unexpected_loss_addon"].to_numpy())
    assert not validate(wired, DEFAULTED_LGD)


def test_defaulted_lgd_keeps_unapproved_q_visible(recovery):
    """q 미승인 crm_plgd를 받으면 추가분은 NULL이고 사유가 남는다."""
    params = build_estimation_param_ledgers(ASOF)
    dh = build_history_ledgers(asof=ASOF, seed=SEED,
                               years=8)["crm_default_history"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        est = estimate_lgd(recovery, dh, floors=params["crm_input_floor"],
                           param=params["crm_estimation_param"],
                           rates=_rates(), asof=ASOF)["crm_lgd_estimate"]
    unapproved = build_plgd_ledgers(recovery, asof=ASOF,
                                    rates=_rates())[PLGD.name]
    out = build_defaulted_lgd(recovery, est, asof=ASOF, plgd=unapproved)
    assert (out["addon_status"] == "미산출(신뢰수준미승인)").all()
    assert out["unexpected_loss_addon"].isna().all()
    assert out["lgd_in_default"].isna().all()
    assert out["elbe"].notna().all()


# ---------------------------------------------------------------- 할인율

def test_no_discount_rate_blocks_the_curve(recovery):
    """할인율이 승인 전이면 곡선을 만들지 않고 경고를 남긴다."""
    blank = build_estimation_param_ledgers(ASOF)["crm_lgd_discount_rate"]
    with pytest.warns(ParamWarning):
        c = build_crm_beel_curve(recovery, asof=ASOF, rates=blank)
    assert (c["status"] == "산출불가(할인율미승인)").all()
    assert c["beel_mean"].isna().all()
    assert (c["monotonicity_verdict"] == "판정불가").all()


# ---------------------------------------------------------------- 결정론

def _fingerprint(ledgers: dict[str, pd.DataFrame]) -> str:
    h = hashlib.sha256()
    for name in sorted(ledgers):
        df = ledgers[name]
        h.update(name.encode())
        h.update(",".join(map(str, df.columns)).encode())
        h.update(pd.util.hash_pandas_object(df.astype(str),
                                            index=True).values.tobytes())
    return h.hexdigest()


def test_deterministic_same_process(recovery):
    a = build_plgd_ledgers(recovery, asof=ASOF, rates=_rates(),
                           confidence_q=_TEST_Q, approved_by=_APPROVER,
                           approval_date=_APPROVAL_DATE)
    b = build_plgd_ledgers(recovery, asof=ASOF, rates=_rates(),
                           confidence_q=_TEST_Q, approved_by=_APPROVER,
                           approval_date=_APPROVAL_DATE)
    assert _fingerprint(a) == _fingerprint(b)
    other = build_history_ledgers(asof=ASOF, seed=SEED + 1,
                                  years=8)["crm_recovery_history"]
    c = build_plgd_ledgers(other, asof=ASOF, rates=_rates(),
                           confidence_q=_TEST_Q, approved_by=_APPROVER,
                           approval_date=_APPROVAL_DATE)
    assert _fingerprint(a) != _fingerprint(c)


def test_deterministic_across_processes(recovery):
    """별도 프로세스에서도 지문이 같다. 내장 hash()나 벽시계가 섞이면 깨진다."""
    code = (
        "import warnings, hashlib, pandas as pd;"
        "warnings.simplefilter('ignore');"
        "from risk_lib.models.estimation.history import build_history_ledgers;"
        "from risk_lib.models.estimation.params import "
        "build_estimation_param_ledgers, approve_discount_rate;"
        "from risk_lib.models.estimation.plgd import build_plgd_ledgers;"
        f"A='{ASOF}';"
        f"H=build_history_ledgers(asof=A, seed={SEED}, years=8);"
        "R=build_estimation_param_ledgers(A)['crm_lgd_discount_rate'];"
        "R=[R:=approve_discount_rate(R, asof=A, segment=s, "
        f"recovery_scope='전체', rate={_TEST_DISCOUNT_RATE}, "
        "basis='자기자본비용', approved_by='시험', approval_date='2026-01-01')"
        " for s in ('corporate','retail_other','residential_mortgage')][-1];"
        "L=build_plgd_ledgers(H['crm_recovery_history'], asof=A, rates=R, "
        f"confidence_q={_TEST_Q}, approved_by='{_APPROVER}', "
        f"approval_date='{_APPROVAL_DATE}');"
        "h=hashlib.sha256();"
        "[ (h.update(k.encode()), h.update(','.join(map(str,L[k].columns)).encode()),"
        "   h.update(pd.util.hash_pandas_object(L[k].astype(str), index=True).values.tobytes()))"
        "  for k in sorted(L)];"
        "print(h.hexdigest())")
    outs = []
    for _ in range(2):
        r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, timeout=600)
        assert r.returncode == 0, r.stderr[-2000:]
        outs.append(r.stdout.strip())
    local = _fingerprint(build_plgd_ledgers(
        recovery, asof=ASOF, rates=_rates(), confidence_q=_TEST_Q,
        approved_by=_APPROVER, approval_date=_APPROVAL_DATE))
    assert outs[0] == outs[1] == local


# ---------------------------------------------------------------- 표본

def test_thin_segments_are_flagged(ledgers):
    """부도상태 건이 적은 세그먼트는 표본부족 표시를 단다."""
    p = ledgers[PLGD.name]
    thin = p[p["insufficient_sample"].astype(bool)]
    assert not thin.empty
    assert (thin["n_defaulted_open"] < 30).all()
    assert thin["status"].str.contains("표본부족").all()


def test_sensitivity_grid_is_not_an_applied_value(recovery):
    """민감도 격자의 q는 crm_plgd로 넘어가지 않는다."""
    s = build_crm_plgd_sensitivity(recovery, asof=ASOF, rates=_rates(),
                                   denominator="부도시익스포저")
    assert sorted(set(s["confidence_q"])) == sorted(SENSITIVITY_Q_GRID)
    p = build_crm_plgd(
        recovery,
        build_crm_beel_curve(recovery, asof=ASOF, rates=_rates()),
        asof=ASOF, denominator="부도시익스포저")
    assert p["confidence_q"].isna().all()
