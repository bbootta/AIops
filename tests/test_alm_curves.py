"""금리 시나리오 원장 + 충격곡선 — 불변식 고정.

이 파일의 규칙: **통과만으로는 통제가 아니다.** 각 검사는 결함을 되돌렸을 때
실제로 실패해야 한다.

현행 원문 두 종([별표 9-1] 개정 2026.1.29, BCBS d578 2024.7)을 확보해
`docs/primary_sources/IRRBB_원문발췌.md`에 발췌했다. 그 반영으로 이 파일에서
바뀐 것:

  · 헤드라인 계정이 `d368_2016`에서 `별표9의1_2026`으로 바뀌었다. KRW 충격폭
    고정값은 300/400/200에서 **225/350/225**가 됐다. 앞의 값은 d578이 대체한
    폐지값이고, 검사는 계정별로 나눠 두 값을 각각 고정한다.
  · **충격후 하한이 0이다.** [별표 9-1] 제12항 다가 "충격후 금리의 하한은
    0으로 한다"고 명시한다. 직전 회차는 "국내도 하한을 규정하지 않는다"고 보고
    하한을 적용하지 않았는데 그것은 2014년 폐지본을 읽은 결과였다. 국제기준
    계정(d368·d578)만 여전히 재량·미규정이다.
  · 계정 상태(`status`) 검사가 늘었다. 폐지 계정(별표9의1_2014)을 고르면
    산출이 침묵하지 않고 폐지 사유를 낸다.
  · 모수 하·상한(100~400 등) clip 검사는 여전히 없다. 그 경계는 표의 열별
    최소·최대였을 뿐 규정이 아니다. clip 기능 자체는 남아 있으므로 하·상한을
    넣은 원장으로 따로 검사한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib.alm.curves import (
    CURVE_TABLES, HEADLINE_FRAMEWORK_VERSION, Curve, base_curve,
    build_curve_ledgers, build_post_shock_floor, build_rate_shock_param,
    build_scenario_def, discount_factors, framework_status, nii_scenarios,
    shocked_curve,
)
from risk_lib.datamodel.spec import validate
from risk_lib.market_data import demo_market_data

ASOF = "2026-08-08"
SEED = 42
# 헤드라인 계정. 이름을 여기 문자열로 다시 적으면 계정 전환이 원장과 검사에서
# 따로 일어난다.
FW = HEADLINE_FRAMEWORK_VERSION
FW_D368 = "d368_2016"
FW_REPEALED = "별표9의1_2014"


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
           shock_param=None, floor=None):
    sp, sd, fl = _ledgers()
    return shocked_curve(
        base, scenario, ccy=ccy, framework_version=FW,
        shock_param=sp if shock_param is None else shock_param,
        scenario_def=sd, floor=fl if floor is None else floor)


def _sloped_floor(framework_version: str = FW, floor_on_bp: int = -100,
                  slope: int = 5, terminal: float = 20.0) -> pd.DataFrame:
    """만기에 따라 올라가는 음수 하한을 넣은 원장 — 산식 검사용.

    배포 원장의 국내 하한은 전 만기 0이라 `min(0, ·)`·`terminal` 가지가
    실행되지 않는다. 산식이 살아 있는지는 기울기가 있는 값으로만 확인된다.
    """
    fl = build_post_shock_floor()
    m = fl["framework_version"] == framework_version
    fl.loc[m, "floor_on_bp"] = floor_on_bp
    fl.loc[m, "slope_bp_per_year"] = slope
    fl.loc[m, "terminal_tenor_years"] = float(terminal)
    fl.loc[m, "evidence_status"] = "원문확인"
    return fl


# ---------------------------------------------------------------- 원장

def test_ledgers_satisfy_their_specs():
    frames = build_curve_ledgers()
    for spec in CURVE_TABLES:
        bad = [v for v in validate(frames[spec.name], spec) if v.severity == "FAIL"]
        assert not bad, f"{spec.name}: {[str(v) for v in bad]}"


def test_table5_is_loaded_for_all_21_currencies():
    """[별표 9-1] <표5> 전건 적재. 한 통화만 넣으면 그 통화의 원장이 아니라
    그 통화의 예외가 된다."""
    sp = build_rate_shock_param()
    cur = sp[sp["framework_version"] == FW]
    assert len(set(cur["ccy"])) == 21
    assert len(cur) == 21 * 3
    assert set(cur["evidence_status"]) == {"원문확인"}
    assert set(cur["effective_from"]) == {"2026-01-29"}
    # 원문 표의 다섯 지점. KRW는 축마다 개정 방향이 달라 한 축만 보면 완화로
    # 오독된다 — 평행 −75bp · 단기 −50bp · **장기 +25bp**다.
    want = {"KRW": (225, 350, 225), "USD": (200, 300, 225),
            "JPY": (100, 100, 100), "IDR": (400, 500, 300),
            "MXN": (400, 500, 200)}
    for ccy, (par, sht, lng) in want.items():
        row = cur[cur["ccy"] == ccy].set_index("shock_type")["shock_bp"]
        assert (int(row["parallel"]), int(row["short"]), int(row["long"])) == \
            (par, sht, lng), ccy


def test_the_two_current_accounts_agree_on_every_cell():
    """국내가 d578을 수치 조정 없이 채택했다는 사실을 63칸으로 고정한다.

    한 칸이라도 달라지면 국내 산출과 국제 비교치가 갈라진다.
    """
    sp = build_rate_shock_param()
    key = ["ccy", "shock_type"]
    kr = sp[sp["framework_version"] == FW].set_index(key)["shock_bp"]
    bcbs = sp[sp["framework_version"] == "d578_2024"].set_index(key)["shock_bp"]
    assert len(kr) == 63
    assert kr.sort_index().equals(bcbs.sort_index())


def test_the_repealed_krw_calibration_is_confined_to_the_previous_account():
    """KRW 300/400/200은 d578이 대체한 값이다 — 현행 계정에 남아 있으면 안 된다.

    직전 회차가 이 값을 헤드라인으로 적재해 두었다. 회귀 검사로 못박는다.
    """
    sp = build_rate_shock_param()
    prev = sp[(sp["framework_version"] == FW_D368) & (sp["ccy"] == "KRW")]
    got = prev.set_index("shock_type")["shock_bp"]
    assert (int(got["parallel"]), int(got["short"]), int(got["long"])) == \
        (300, 400, 200)
    assert set(prev["status"]) == {"직전"}
    assert set(prev["superseded_by"]) == {"d578_2024"}

    cur = sp[(sp["framework_version"] == FW) & (sp["ccy"] == "KRW")]
    assert set(cur["status"]) == {"현행"}
    assert cur["superseded_by"].isna().all()


def test_no_row_borrows_another_currency():
    """프록시 경로 제거의 회귀 검사 — 원장에 대용 지정이 하나도 없어야 한다."""
    sp = build_rate_shock_param()
    assert sp["proxy_for_ccy"].isna().all()


def test_the_repealed_2014_account_carries_no_shock_table():
    """폐지 계정은 값이 아니라 폐지 사실을 담는다.

    2014년판은 금리 EaR·VaR 체계라 통화별 충격표가 존재하지 않는다. 행을
    남기는 것은 시계열 단절을 설명하기 위해서이고, 값을 채우면 없는 표를
    만드는 것이 된다.
    """
    sp = build_rate_shock_param()
    old = sp[sp["framework_version"] == FW_REPEALED]
    assert not old.empty and old["shock_bp"].isna().all()
    assert set(old["status"]) == {"폐지"}
    assert set(old["superseded_by"]) == {FW}
    assert set(old["effective_to"]) == {"2019-11-29"}
    # 계정 존재와 폐지 사실은 원문에서 읽었다 — 값이 비었다고 미확인이 아니다.
    assert set(old["evidence_status"]) == {"원문확인"}
    assert framework_status(sp, FW_REPEALED) == ("폐지", FW)
    assert framework_status(sp, FW) == ("현행", None)


def test_shock_bounds_are_not_invented():
    """모수 하·상한은 d368 Annex 2에 없다 — 비어 있어야 한다.

    앞선 회차의 long 상한 300은 IDR의 원문값 350을 잘랐다. 경계를 지어내면
    원문확인 값이 조용히 바뀐다.
    """
    sp = build_rate_shock_param()
    assert sp["floor_bp"].isna().all() and sp["cap_bp"].isna().all()


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
    assert set(sd["evidence_status"]) == {"원문확인"}


def test_rotation_scenarios_reproduce_the_source_worked_example():
    """원문의 검산 예시를 그대로 고정한다 ([별표 9-1] 제12항 나 = d578 SRP31.91).

    t=3.5Y, R_short=R_long=100bp, S_short(3.5)=e^{−3.5/4}=0.417일 때
      steepener = −0.65·100·0.417 + 0.90·100·(1−0.417) = +25.4bp
      flattener = +0.80·100·0.417 − 0.60·100·(1−0.417) = −1.6bp
    계수 네 개와 감쇠 x 중 어느 하나만 틀려도 이 두 값이 어긋난다. 통화 원장
    값과 무관하게 구성식만 보려고 100/100/100짜리 시험 통화를 만든다.
    """
    t = np.array([3.5])
    zero = Curve(label="Δr 산출용 0커브", asof=ASOF, tenors=t,
                 zero_rates=np.zeros_like(t))
    sp = pd.DataFrame([{
        "framework_version": FW, "ccy": "TST", "shock_type": st,
        "status": "현행", "superseded_by": None,
        "effective_from": None, "effective_to": None, "shock_bp": 100,
        "floor_bp": None, "cap_bp": None, "proxy_for_ccy": None,
        "source_ref": "검산용", "evidence_status": "원문확인",
    } for st in ("parallel", "short", "long")]).astype(
        {"shock_bp": "Int64", "floor_bp": "Int64", "cap_bp": "Int64"})

    st_c, _w = _shock(zero, "steepener", ccy="TST", shock_param=sp)
    fl_c, _w = _shock(zero, "flattener", ccy="TST", shock_param=sp)
    assert float(st_c.shift[0]) * 1e4 == pytest.approx(25.4, abs=0.05)
    assert float(fl_c.shift[0]) * 1e4 == pytest.approx(-1.6, abs=0.05)


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

def test_d368_floor_row_carries_no_numbers_and_is_not_applied():
    """d368은 하한을 각국 재량으로 넘기고 수치를 주지 않는다(1차자료 §A-4).

    앞선 회차가 넣었던 −100bp + 5bp/년은 원문에 없는 값이라 뺐다. 행을 지우지
    않는 이유는 "규정이 값을 정하지 않는다"와 "규정을 못 읽었다"가 다른
    사건이기 때문이고, 그 구분이 evidence_status에 남는다.
    """
    fl = build_post_shock_floor()
    assert len(fl) == 1
    assert fl.iloc[0]["evidence_status"] == "재량·미규정"
    assert fl[["floor_on_bp", "slope_bp_per_year",
               "terminal_tenor_years"]].isna().all().all()

    sc, warns = _shock(_flat_curve(0.005), "parallel_down")
    assert not sc.floor_applied
    assert any(w.model == "POST_SHOCK_FLOOR" for w in warns)
    # 하한 미적용의 귀결이 보인다 — 0.5% 커브에 300bp 하락이면 음수로 간다.
    assert (sc.curve.zero_rates < 0.0).any()


def test_post_shock_floor_binds_in_the_short_end():
    """감독당국이 하한을 고시하면 산식이 그대로 물어야 한다.

    평평한 0.5% 커브에 parallel_down 300bp — 하한이 없으면 −2.5%가 된다.
    """
    base = _flat_curve(0.005)
    sc, _w = _shock(base, "parallel_down", floor=_supervisory_floor())
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
    """데모 커브(2.8%)에서는 고시 하한이 물지 않는다 — 결과를 왜곡하지 않는다."""
    base = base_curve(_risk_factor(), asof=ASOF)
    sc, _w = _shock(base, "parallel_down", floor=_supervisory_floor())
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
    # KRW 원문값: R_short=400bp, R_long=200bp (Annex 2 Table 1).
    want = (-0.65 * 0.04 * s_short) + (0.90 * 0.02 * (1.0 - s_short))
    assert sc.shift == pytest.approx(want)
    assert sc.shock_bp == {"short": 400, "long": 200}
    assert sc.shock_source == "직접"


def test_parallel_shock_needs_only_the_parallel_parameter():
    """계수가 0인 축의 모수는 요구하지 않는다 — 없는 모수를 요구하면 과잉차단이다."""
    sp = build_rate_shock_param()
    sp = sp[~((sp["ccy"] == "KRW") & (sp["shock_type"].isin(["short", "long"])))]
    sc, _w = _shock(_flat_curve(0.03), "parallel_up", shock_param=sp)
    assert sc is not None and sc.shift == pytest.approx(0.03)


# ---------------------------------------------------------------- 모수 clip

def test_shock_bp_is_used_verbatim_when_no_bounds_are_set():
    """하·상한이 비어 있으면 자르지 않는다 — 자르면 원문값이 조용히 바뀐다.

    IDR long 350이 그 증거다. 앞선 회차의 상한 300은 이 값을 300으로 잘랐다.
    """
    sp = build_rate_shock_param()
    sc, _w = _shock(_flat_curve(0.05), "short_up", ccy="IDR", shock_param=sp)
    assert sc.shock_bp["short"] == 500
    sc, _w = _shock(_flat_curve(0.05), "steepener", ccy="IDR", shock_param=sp)
    assert sc.shock_bp["long"] == 350


@pytest.mark.parametrize("raw, want", [
    (50, 100),      # 하한 100bp
    (100, 100),     # 경계 — 그대로
    (400, 400),     # 상한 경계 — 그대로
    (600, 400),     # 상한 초과
])
def test_shock_bp_is_clipped_when_the_ledger_carries_bounds(raw, want):
    """감독당국이 모수 하·상한을 두면 엔진이 강제한다.

    배포 원장에는 하·상한이 없지만 기능은 살아 있어야 한다 — 없앴다가 나중에
    고시가 나오면 원장을 채워도 아무 일이 일어나지 않는다.
    """
    sp = build_rate_shock_param()
    m = (sp["ccy"] == "KRW") & (sp["shock_type"] == "parallel")
    sp.loc[m, "shock_bp"] = raw
    sp.loc[m, "floor_bp"] = 100
    sp.loc[m, "cap_bp"] = 400
    sc, _w = _shock(_flat_curve(0.05), "parallel_up", shock_param=sp)
    assert sc.shock_bp["parallel"] == want
    assert sc.shift == pytest.approx(want / 10_000.0)


def test_one_sided_bound_clips_only_that_side():
    sp = build_rate_shock_param()
    m = (sp["ccy"] == "KRW") & (sp["shock_type"] == "parallel")
    sp.loc[m, "shock_bp"] = 900
    sp.loc[m, "cap_bp"] = 500                 # floor_bp는 비어 있다
    sc, _w = _shock(_flat_curve(0.05), "parallel_up", shock_param=sp)
    assert sc.shock_bp["parallel"] == 500


# ---------------------------------------------------------------- 빈 모수

def test_null_shock_bp_yields_a_warning_and_no_curve():
    """모수가 비어 있으면 채우지 않고 건너뛴다 — 값을 지어내지 않는다."""
    sp = build_rate_shock_param()
    sp.loc[sp["ccy"] == "KRW", "shock_bp"] = pd.NA
    base = base_curve(_risk_factor(), asof=ASOF)
    sc, warns = _shock(base, "parallel_up", ccy="KRW", shock_param=sp)
    assert sc is None
    assert warns and all(w.model == "RATE_SHOCK" for w in warns)
    assert any("shock_bp가 비어 있다" in w.reason for w in warns)


def test_currency_absent_from_the_ledger_is_skipped_not_borrowed():
    """원장에 없는 통화에 다른 통화 값을 붙이지 않는다 — 프록시 제거의 핵심."""
    base = base_curve(_risk_factor(), asof=ASOF)
    sc, warns = _shock(base, "parallel_up", ccy="XXX")
    assert sc is None
    assert any("해당 통화 행이 원장에 없다" in w.reason for w in warns)


def test_d578_account_produces_nothing():
    """신 계정은 시행일만 있고 값이 없다."""
    sp, sd, fl = _ledgers()
    sc, warns = shocked_curve(
        _flat_curve(0.03), "parallel_up", ccy="KRW",
        framework_version="d578_2024", shock_param=sp, scenario_def=sd,
        floor=fl)
    assert sc is None
    assert any("shock_bp가 비어 있다" in w.reason for w in warns)


def test_allow_proxy_is_ignored_and_says_so():
    """계승 호출부가 남긴 인자다. 조용히 무시하면 그 호출부가 안 고쳐진다."""
    base = base_curve(_risk_factor(), asof=ASOF)
    sp, sd, fl = _ledgers()
    sc, warns = shocked_curve(
        base, "parallel_up", ccy="KRW", framework_version=FW,
        shock_param=sp, scenario_def=sd, floor=fl, allow_proxy=True)
    assert sc is not None and sc.shock_source == "직접"
    assert any(w.param == "allow_proxy" for w in warns)


def test_unknown_scenario_is_rejected():
    with pytest.raises(ValueError, match="alm_scenario_def에 없는"):
        _shock(_flat_curve(0.03), "twist")
