"""시장데이터 거버넌스 · Curve/Vol calibration 테스트 — SEC-PRC-001 · SEC-PRC-004."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib.market_data import (
    MarketDataSnapshot, MarketDataError, bootstrap_zero_curve,
    calibrate_vol_surface, assess, assess_from_result, demo_market_data,
    MAX_STALENESS_DAYS, CURVE_REPRICING_TOL_BPS, VOL_FIT_RMSE_TOL,
)

ASOF = "2026-06-11"


def _snap(**kw) -> MarketDataSnapshot:
    base = dict(name="테스트", data_type="ir_curve", source="consensus",
                snapshot_date=ASOF,
                quotes=pd.DataFrame({"tenor": [1.0], "quote": [0.03]}))
    base.update(kw)
    return MarketDataSnapshot(**base)


# ----- 스냅샷 통제 (SEC-PRC-001) ---------------------------------------------

def test_staleness_by_data_type():
    """허용 경과는 데이터 종류별로 다르다."""
    fresh = _snap(data_type="ir_curve", snapshot_date="2026-06-11")
    assert not fresh.is_stale(ASOF)
    stale = _snap(data_type="ir_curve", snapshot_date="2026-06-09")   # 2일
    assert stale.is_stale(ASOF)
    # 신용커브는 3일까지 허용
    credit = _snap(data_type="credit_curve", snapshot_date="2026-06-08")
    assert credit.age_days(ASOF) == 3 and not credit.is_stale(ASOF)
    assert _snap(data_type="credit_curve",
                 snapshot_date="2026-06-07").is_stale(ASOF)


def test_staleness_boundary_is_inclusive():
    """허용치와 같은 날은 통과, 하루라도 넘으면 위반."""
    n = MAX_STALENESS_DAYS["ir_curve"]
    ok = _snap(snapshot_date="2026-06-10")           # 1일 = 허용치
    assert ok.age_days(ASOF) == n and not ok.is_stale(ASOF)
    bad = _snap(snapshot_date="2026-06-09")
    assert bad.is_stale(ASOF)


def test_future_snapshot_is_a_violation():
    v = _snap(snapshot_date="2026-06-20").violations(ASOF)
    assert any("미래 스냅샷" in x for x in v)


def test_internal_only_source_is_a_violation():
    """내부 소스 단독은 독립 검증 소스가 아니다."""
    v = _snap(source="internal").violations(ASOF)
    assert any("내부 소스 단독" in x for x in v)


def test_unknown_source_and_empty_quotes_rejected():
    assert any("미등록 소스" in x for x in _snap(source="어디선가").violations(ASOF))
    empty = _snap(quotes=pd.DataFrame())
    assert any("호가 없음" in x for x in empty.violations(ASOF))


def test_snapshot_fingerprint_reacts_to_data_change():
    a = _snap()
    b = _snap(quotes=pd.DataFrame({"tenor": [1.0], "quote": [0.031]}))
    assert a.fingerprint() != b.fingerprint()
    assert a.fingerprint() == _snap().fingerprint()


# ----- 커브 부트스트랩 (SEC-PRC-004) -----------------------------------------

def test_bootstrap_reprices_par_rates_exactly():
    """부트스트랩 커브는 입력 par 금리를 재현해야 한다 — 못하면 calibration 실패."""
    t = np.array([1, 2, 3, 5, 7, 10.0])
    s = np.array([0.030, 0.032, 0.034, 0.036, 0.037, 0.038])
    c = bootstrap_zero_curve(t, s)
    np.testing.assert_allclose(c.par_repriced, s, atol=1e-12)
    assert c.max_repricing_error_bps < 1e-6
    assert c.calibration_passes()


def test_bootstrap_identity_holds_per_tenor():
    """S_n · Σ_(i≤n) DF_i + DF_n = 1 이 만기마다 성립해야 한다."""
    t = np.array([1, 2, 3, 5.0])
    s = np.array([0.03, 0.033, 0.035, 0.037])
    c = bootstrap_zero_curve(t, s)
    for i in range(len(t)):
        annuity = c.discount_factors[: i + 1].sum()
        assert s[i] * annuity + c.discount_factors[i] == pytest.approx(1.0,
                                                                      abs=1e-12)


def test_discount_factors_monotone_decreasing():
    t = np.array([0.5, 1, 2, 5, 10, 30.0])
    s = 0.028 + 0.010 * (1 - np.exp(-t / 6.0))
    c = bootstrap_zero_curve(t, s)
    assert c.is_arbitrage_free()
    assert np.all(np.diff(c.discount_factors) < 0)


def test_zero_rate_reproduces_discount_factor():
    c = bootstrap_zero_curve([1, 2, 3.0], [0.03, 0.032, 0.034])
    np.testing.assert_allclose(np.exp(-c.zero_rates * c.tenors),
                               c.discount_factors, rtol=1e-12)


def test_df_interpolation_is_between_nodes():
    c = bootstrap_zero_curve([1, 2, 3.0], [0.03, 0.032, 0.034])
    mid = c.df(1.5)
    assert c.discount_factors[1] < mid < c.discount_factors[0]
    assert c.df(0.0) == 1.0


def test_bootstrap_rejects_bad_inputs():
    with pytest.raises(MarketDataError, match="길이가 다르다"):
        bootstrap_zero_curve([1, 2], [0.03])
    with pytest.raises(MarketDataError, match="증가 순"):
        bootstrap_zero_curve([2, 1], [0.03, 0.03])
    with pytest.raises(MarketDataError, match="양수"):
        bootstrap_zero_curve([0, 1], [0.03, 0.03])
    # 비현실적으로 큰 par 금리는 할인계수를 비양수로 만든다 → 거부
    with pytest.raises(MarketDataError, match="비양수"):
        bootstrap_zero_curve([1, 2, 3.0], [0.5, 0.9, 5.0])


# ----- 변동성면 적합 · 무차익 -------------------------------------------------

def _vol_quotes(expiries=(0.25, 0.5, 1.0, 2.0), c=0.35, skew=-0.05):
    ks = np.array([-0.25, -0.15, -0.05, 0.0, 0.05, 0.15, 0.25])
    rec = []
    for T in expiries:
        base = 0.18 + 0.02 * np.sqrt(T)
        for k in ks:
            rec.append({"expiry": float(T), "log_moneyness": float(k),
                        "vol": float(base + c * k * k + skew * k)})
    return pd.DataFrame(rec)


def test_vol_surface_fits_within_tolerance():
    s = calibrate_vol_surface(_vol_quotes())
    assert s.fit_passes()
    assert s.rmse < VOL_FIT_RMSE_TOL
    assert len(s.params) == 4


def test_convex_smile_has_no_butterfly_violation():
    s = calibrate_vol_surface(_vol_quotes(c=0.35))
    assert s.butterfly_violations() == []
    assert (s.params["c"] > 0).all()


def test_concave_smile_flags_butterfly_arbitrage():
    """c < 0 (오목한 스마일)이면 나비 차익거래가 존재한다 — 반드시 잡혀야 한다."""
    s = calibrate_vol_surface(_vol_quotes(c=-0.40))
    assert s.butterfly_violations(), "볼록성 위반이 탐지되지 않았다"
    assert not s.is_arbitrage_free()


def test_decreasing_total_variance_flags_calendar_arbitrage():
    """만기가 길수록 total variance가 작아지면 달력 차익거래."""
    rec = []
    ks = np.array([-0.2, -0.1, 0.0, 0.1, 0.2])
    for T, v in ((0.5, 0.30), (1.0, 0.18), (2.0, 0.10)):   # w = v²T 감소
        for k in ks:
            rec.append({"expiry": T, "log_moneyness": float(k),
                        "vol": float(v + 0.3 * k * k)})
    s = calibrate_vol_surface(pd.DataFrame(rec))
    assert s.calendar_violations(), "달력 차익이 탐지되지 않았다"
    assert not s.is_arbitrage_free()


def test_insufficient_quotes_rejected_not_fudged():
    """만기당 3개 미만이면 적합을 거부한다 — 억지 적합은 가짜 차익을 만든다."""
    thin = pd.DataFrame([
        {"expiry": 1.0, "log_moneyness": -0.1, "vol": 0.2},
        {"expiry": 1.0, "log_moneyness": 0.1, "vol": 0.21},
    ])
    with pytest.raises(MarketDataError, match="최소 3개"):
        calibrate_vol_surface(thin)


def test_vol_surface_rejects_bad_inputs():
    with pytest.raises(MarketDataError, match="필요 컬럼"):
        calibrate_vol_surface(pd.DataFrame({"expiry": [1.0]}))
    bad = _vol_quotes()
    bad.loc[0, "vol"] = -0.1
    with pytest.raises(MarketDataError, match="양수"):
        calibrate_vol_surface(bad)


def test_implied_vol_roundtrip():
    s = calibrate_vol_surface(_vol_quotes())
    v = s.implied_vol(0.0, 1.0)
    assert 0.10 < v < 0.35
    assert s.total_variance(0.0, 1.0) == pytest.approx(v ** 2 * 1.0, rel=1e-9)


# ----- 종합 판정 -------------------------------------------------------------

def test_assess_collects_all_violations(result):
    g = assess_from_result(result)
    # 데모 데이터는 FX 스냅샷이 6일 경과 → 위반 1건이 반드시 잡혀야 한다
    assert not g.passes()
    assert any("Staleness" in v for v in g.violations)
    assert g.snapshots["stale"].sum() == 1
    # 커브·변동성면 자체는 통과
    assert g.curve.calibration_passes() and g.curve.is_arbitrage_free()
    assert g.vol.fit_passes() and g.vol.is_arbitrage_free()


def test_assess_passes_when_all_fresh():
    """모든 스냅샷이 신선하면 통과 — 위반 탐지가 상시 True가 아님을 확인."""
    snaps, curve, vol = demo_market_data(asof=ASOF)
    fresh = [MarketDataSnapshot(
        name=s.name, data_type=s.data_type,
        source="consensus" if s.source == "internal" else s.source,
        snapshot_date=ASOF, quotes=s.quotes, version=s.version)
        for s in snaps]
    g = assess(fresh, curve, vol, asof=ASOF)
    assert g.passes(), f"신선한 데이터에서 위반: {g.violations}"


def test_assess_flags_bad_calibration():
    snaps, curve, vol = demo_market_data(asof=ASOF)
    curve.max_repricing_error_bps = CURVE_REPRICING_TOL_BPS * 10
    g = assess(snaps, curve, vol, asof=ASOF)
    assert any("par 재현 오차" in v for v in g.violations)


def test_determinism(result):
    a = assess_from_result(result)
    b = assess_from_result(result)
    assert a.violations == b.violations
    assert a.curve.max_repricing_error_bps == pytest.approx(
        b.curve.max_repricing_error_bps)


# ----- 보고서 · 커버리지 -----------------------------------------------------

def test_market_data_page_renders(result):
    from risk_lib.ops_pages.market_trading import page_market_data
    html = page_market_data(result)
    assert "시장데이터 거버넌스" in html
    assert "butterfly" in html and "calendar" in html
    # 정책이 판단한다는 원칙이 명시돼야 한다
    assert "정책이 합니다" in html
    # stale 위반이 숨겨지지 않고 노출
    assert "Staleness 초과" in html


def test_market_data_page_registered():
    from risk_lib.page_registry import PAGES
    specs = [p for p in PAGES if p.filename == "67_market_data.html"]
    assert len(specs) == 1
    assert callable(specs[0].resolve())


def test_coverage_marks_market_data_requirements():
    from risk_lib import rynta
    df = rynta.coverage_frame().set_index("id")
    for rid in ("SEC-PRC-001", "SEC-PRC-004"):
        assert df.loc[rid, "status"] == "covered"
        assert "market_data" in df.loc[rid, "modules"]
        assert df.loc[rid, "owner"] == "market-risk-analyst"
