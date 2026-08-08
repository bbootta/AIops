"""금리 시나리오 원장 + 충격곡선 — 불변식 고정.

이 파일의 규칙: **통과만으로는 통제가 아니다.** 각 검사는 결함을 되돌렸을 때
실제로 실패해야 한다. 특히 하한 검사는 기저 금리가 충분히 낮은 커브에서만
발동하므로(현행 데모 커브는 2.8%라 200bp 하락에도 하한이 물지 않는다) 하한이
무는 커브를 만들어 놓고, 하한을 끄면 음수가 나온다는 것까지 함께 확인한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib.alm.curves import (
    CURVE_TABLES, Curve, base_curve, build_curve_ledgers,
    build_post_shock_floor, build_rate_shock_param, build_scenario_def,
    discount_factors, nii_scenarios, shocked_curve,
)
from risk_lib.datamodel.spec import validate
from risk_lib.market_data import demo_market_data

ASOF = "2026-08-08"
SEED = 42
FW = "d368_2016"


# ---------------------------------------------------------------- 도우미

def _risk_factor(asof: str = ASOF, seed: int = SEED) -> pd.DataFrame:
    """`mkt_risk_factor` 금리 행 — materialize_mkt_detail과 같은 스냅샷."""
    snaps, _curve, _vol = demo_market_data(asof=asof, seed=seed)
    snap = next(s for s in snaps if s.data_type == "ir_curve")
    return pd.DataFrame([{
        "factor_id": f"ir_curve:{snap.name}:{float(r['tenor']):g}Y",
        "asof": asof, "risk_class": "interest_rate", "curve": snap.name,
        "tenor": float(r["tenor"]), "value": float(r["quote"]),
        "source": snap.source, "staleness_days": 0, "modellable": True,
    } for _, r in snap.quotes.iterrows()])


def _flat_curve(level: float, tenors=(0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0)) -> Curve:
    """평평한 저금리 커브 — 하한이 실제로 무는 구간을 만들기 위한 검사용 입력."""
    t = np.asarray(tenors, dtype=float)
    return Curve(label="검사용 평평커브", asof=ASOF, tenors=t,
                 zero_rates=np.full_like(t, float(level)))


def _ledgers():
    L = build_curve_ledgers()
    return (L["alm_rate_shock_param"], L["alm_scenario_def"],
            L["alm_post_shock_floor"])


def _shock(base: Curve, scenario: str, *, ccy: str = "KRW",
           allow_proxy: bool = True, shock_param=None, floor=None):
    sp, sd, fl = _ledgers()
    return shocked_curve(
        base, scenario, ccy=ccy, framework_version=FW,
        shock_param=sp if shock_param is None else shock_param,
        scenario_def=sd, floor=fl if floor is None else floor,
        allow_proxy=allow_proxy)


# ---------------------------------------------------------------- 원장

def test_ledgers_satisfy_their_specs():
    frames = build_curve_ledgers()
    for spec in CURVE_TABLES:
        bad = [v for v in validate(frames[spec.name], spec) if v.severity == "FAIL"]
        assert not bad, f"{spec.name}: {[str(v) for v in bad]}"


def test_krw_shock_bp_is_empty_and_usd_row_declares_the_proxy():
    """값을 지어내지 않았다는 것 자체가 산출물이다 — 비어 있음이 원장에 보인다."""
    sp = build_rate_shock_param()
    krw = sp[(sp["framework_version"] == FW) & (sp["ccy"] == "KRW")]
    assert len(krw) == 3
    assert krw["shock_bp"].isna().all()
    assert set(krw["evidence_status"]) == {"미확인"}
    assert krw["source_ref"].str.contains("450").any()      # 불일치가 기록돼 있다

    usd = sp[(sp["framework_version"] == FW) & (sp["ccy"] == "USD")]
    assert dict(zip(usd["shock_type"], usd["shock_bp"])) == {
        "parallel": 200, "short": 300, "long": 150}
    assert set(usd["proxy_for_ccy"]) == {"KRW"}
    assert set(usd["evidence_status"]) == {"원문미확인·현행계승"}

    # 신 계정도 행은 존재하되 비어 있다 — 부재와 공란은 다른 사건이다.
    d578 = sp[sp["framework_version"] == "d578_2024"]
    assert len(d578) == 3 and d578["shock_bp"].isna().all()
    assert set(d578["effective_from"]) == {"2026-01-01"}


def test_nii_applies_to_parallel_shocks_only():
    """ΔNII 시나리오 목록이 코드 튜플이 아니라 원장에서 나온다."""
    assert nii_scenarios(build_scenario_def()) == ("parallel_up", "parallel_down")


def test_scenario_def_carries_the_coefficients_that_were_in_the_function_body():
    sd = build_scenario_def().set_index("scenario")
    assert (sd.loc["steepener", "short_coef"],
            sd.loc["steepener", "long_coef"]) == (-0.65, 0.90)
    assert (sd.loc["flattener", "short_coef"],
            sd.loc["flattener", "long_coef"]) == (0.80, -0.60)
    assert set(sd["decay_x"]) == {4.0}


# ---------------------------------------------------------------- 기저커브

def test_base_curve_reproduces_the_market_data_bootstrap():
    """커브가 두 벌이 되면 시장리스크와 ALM이 다른 할인율로 같은 지표를 만든다."""
    _snaps, mkt, _vol = demo_market_data(asof=ASOF, seed=SEED)
    c = base_curve(_risk_factor(), asof=ASOF)
    assert np.array_equal(c.tenors, np.asarray(mkt.tenors, dtype=float))
    assert np.array_equal(c.zero_rates, np.asarray(mkt.zero_rates, dtype=float))
    # 할인계수 규약도 같아야 한다 — 노드 사이(3.7년)에서 확인한다.
    assert float(discount_factors(c, 3.7)) == pytest.approx(mkt.df(3.7), abs=1e-12)


def test_base_curve_is_byte_identical_for_the_same_asof_and_seed():
    a = base_curve(_risk_factor(ASOF, SEED), asof=ASOF)
    b = base_curve(_risk_factor(ASOF, SEED), asof=ASOF)
    assert a.zero_rates.tobytes() == b.zero_rates.tobytes()
    assert a.tenors.tobytes() == b.tenors.tobytes()
    # 충격곡선까지 결정론이어야 재현성 digest가 성립한다.
    sa, _ = _shock(a, "steepener")
    sb, _ = _shock(b, "steepener")
    assert sa.curve.zero_rates.tobytes() == sb.curve.zero_rates.tobytes()


def test_base_curve_refuses_to_guess_between_two_curves():
    rf = pd.concat([_risk_factor(), _risk_factor().assign(curve="다른 커브")])
    with pytest.raises(ValueError, match="금리커브가 여럿"):
        base_curve(rf, asof=ASOF)


def test_discount_factors_are_continuous_compounding():
    c = _flat_curve(0.03)
    t = np.array([0.5, 2.0, 10.0])
    assert discount_factors(c, t) == pytest.approx(np.exp(-0.03 * t))


def test_rate_and_df_are_the_same_convention():
    """소비자가 금리와 할인계수를 서로 다른 규약에서 가져오면 ΔEVE에 오차가 섞인다."""
    c = base_curve(_risk_factor(), asof=ASOF)
    assert c.rate(c.tenors) == pytest.approx(c.zero_rates)      # 노드에서 일치
    t = 3.7                                                     # 노드 사이
    assert float(c.rate(t)) == pytest.approx(
        -np.log(float(discount_factors(c, t))) / t)


# ---------------------------------------------------------------- 하한

def test_post_shock_floor_binds_in_the_short_end():
    """평평한 0.5% 커브에 parallel_down 200bp — 하한이 없으면 −1.5%가 된다."""
    base = _flat_curve(0.005)
    sc, _w = _shock(base, "parallel_down")
    assert sc.floor_applied
    t = sc.curve.tenors
    expected_floor = np.minimum(0.0, (-100.0 + 5.0 * t) / 10_000.0)
    # 하한 아래로 내려간 노드가 없다.
    assert np.all(sc.curve.zero_rates >= expected_floor - 1e-15)
    # 그리고 하한이 실제로 물었다 — 물지 않으면 이 검사는 아무것도 지키지 못한다.
    assert sc.floor_binding[:4].all()
    assert np.all(sc.base_rates + sc.shift < 0.0)
    # 20년 노드의 하한은 0이다 (min(0, −0.01+0.0005·20) = 0).
    assert expected_floor[-1] == 0.0 and sc.curve.zero_rates[-1] == 0.0


def test_floor_is_skipped_with_a_warning_when_the_framework_row_is_missing():
    """하한 원장이 비면 조용히 하한 없는 커브를 만들지 않는다 — 사실을 남긴다."""
    empty = build_post_shock_floor().iloc[0:0]
    sc, warns = _shock(_flat_curve(0.005), "parallel_down", floor=empty)
    assert not sc.floor_applied
    assert any(w.model == "POST_SHOCK_FLOOR" for w in warns)
    assert (sc.curve.zero_rates < 0.0).any()      # 하한 미적용의 귀결이 보인다


def test_high_curve_is_untouched_by_the_floor():
    """데모 커브(2.8%)에서는 하한이 물지 않는다 — 하한이 결과를 왜곡하지 않는다."""
    base = base_curve(_risk_factor(), asof=ASOF)
    sc, _w = _shock(base, "parallel_down")
    assert not sc.floor_binding.any()


# ---------------------------------------------------------------- 시나리오 형태

def test_steepener_and_flattener_flip_sign_between_short_and_long_end():
    base = base_curve(_risk_factor(), asof=ASOF)
    st, _ = _shock(base, "steepener")
    fl, _ = _shock(base, "flattener")
    t = base.tenors
    short_i, long_i = int(np.argmin(t)), int(np.argmax(t))

    assert st.shift[short_i] < 0.0 < st.shift[long_i]     # 단기 하락·장기 상승
    assert fl.shift[long_i] < 0.0 < fl.shift[short_i]     # 단기 상승·장기 하락
    # 두 시나리오는 서로 반대 방향이다.
    assert np.sign(st.shift[short_i]) == -np.sign(fl.shift[short_i])
    assert np.sign(st.shift[long_i]) == -np.sign(fl.shift[long_i])


def test_scenario_shift_matches_the_ledger_formula():
    """Δr(t) = Σ coef·R·S(t) — 계수가 원장에서 오는지 값으로 확인한다."""
    base = _flat_curve(0.03)
    sc, _w = _shock(base, "steepener")
    t, x = base.tenors, 4.0
    s_short = np.exp(-t / x)
    want = (-0.65 * 0.03 * s_short) + (0.90 * 0.015 * (1.0 - s_short))
    assert sc.shift == pytest.approx(want)          # R_s=300bp, R_l=150bp (프록시)
    assert sc.shock_bp == {"short": 300, "long": 150}


def test_parallel_shock_needs_only_the_parallel_parameter():
    """계수가 0인 축의 모수는 요구하지 않는다 — 없는 모수를 요구하면 과잉차단이다."""
    sp = build_rate_shock_param()
    sp = sp[~((sp["ccy"] == "USD") & (sp["shock_type"].isin(["short", "long"])))]
    sc, _w = _shock(_flat_curve(0.03), "parallel_up", shock_param=sp)
    assert sc is not None and sc.shift == pytest.approx(0.02)


# ---------------------------------------------------------------- 모수 clip

@pytest.mark.parametrize("raw, want", [
    (50, 100),      # 하한 100bp
    (100, 100),     # 경계 — 그대로
    (400, 400),     # parallel 상한 경계 — 그대로
    (600, 400),     # 상한 초과
])
def test_parallel_shock_bp_is_clipped_at_the_bounds(raw, want):
    sp = build_rate_shock_param()
    m = (sp["ccy"] == "USD") & (sp["shock_type"] == "parallel")
    sp.loc[m, "shock_bp"] = raw
    sc, _w = _shock(_flat_curve(0.05), "parallel_up", shock_param=sp)
    assert sc.shock_bp["parallel"] == want
    assert sc.shift == pytest.approx(want / 10_000.0)


@pytest.mark.parametrize("shock_type, raw, want", [
    ("short", 900, 500),      # short 상한 500bp
    ("long", 900, 300),       # long 상한 300bp
])
def test_short_and_long_caps_differ_from_parallel(shock_type, raw, want):
    sp = build_rate_shock_param()
    m = (sp["ccy"] == "USD") & (sp["shock_type"] == shock_type)
    sp.loc[m, "shock_bp"] = raw
    scenario = "short_up" if shock_type == "short" else "steepener"
    sc, _w = _shock(_flat_curve(0.05), scenario, shock_param=sp)
    assert sc.shock_bp[shock_type] == want


def test_missing_bounds_block_the_scenario():
    """상·하한이 비면 clip을 검증할 수 없다 — clip 없이 통과시키지 않는다."""
    sp = build_rate_shock_param()
    m = (sp["ccy"] == "USD") & (sp["shock_type"] == "parallel")
    sp.loc[m, "cap_bp"] = pd.NA
    sc, warns = _shock(_flat_curve(0.03), "parallel_up", shock_param=sp)
    assert sc is None
    assert any("상·하한" in w.reason for w in warns)


# ---------------------------------------------------------------- 빈 모수

def test_null_shock_bp_yields_a_warning_and_no_curve():
    """KRW 모수는 비어 있다 — 프록시를 허용하지 않으면 산출이 없어야 한다."""
    base = base_curve(_risk_factor(), asof=ASOF)
    sc, warns = _shock(base, "parallel_up", ccy="KRW", allow_proxy=False)
    assert sc is None
    assert warns and all(w.model == "RATE_SHOCK" for w in warns)
    assert any("allow_proxy" in w.reason for w in warns)


def test_d578_account_produces_nothing_even_with_proxy():
    """신 계정은 모수도 프록시 행도 없다 — 시행일만 있고 값이 없는 상태."""
    sp, sd, fl = _ledgers()
    sc, warns = shocked_curve(
        _flat_curve(0.03), "parallel_up", ccy="KRW",
        framework_version="d578_2024", shock_param=sp, scenario_def=sd,
        floor=fl, allow_proxy=True)
    assert sc is None
    assert any(w.param == "proxy_for_ccy" for w in warns)


def test_proxy_use_is_recorded_on_the_result_and_in_a_warning():
    """프록시 사용이 조용히 지나가면 이 설계의 목적이 사라진다."""
    base = base_curve(_risk_factor(), asof=ASOF)
    sc, warns = _shock(base, "parallel_up", ccy="KRW", allow_proxy=True)
    assert sc is not None
    assert sc.shock_source == "프록시(USD)"
    assert any("프록시로 사용" in w.reason for w in warns)


def test_unknown_scenario_is_rejected():
    with pytest.raises(ValueError, match="alm_scenario_def에 없는"):
        _shock(_flat_curve(0.03), "twist")
