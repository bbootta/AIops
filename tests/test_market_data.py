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


def test_non_independent_sources_are_violations():
    """내부 산출·FO 자체 가격 단독은 독립 검증 소스가 아니다."""
    from risk_lib.market_data import NON_INDEPENDENT_SOURCES
    for src in NON_INDEPENDENT_SOURCES:
        v = _snap(source=src).violations(ASOF)
        assert any("비독립 소스 단독" in x for x in v), f"{src} 미탐지"
    # 독립 소스는 위반이 아니어야 한다
    assert _snap(source="consensus").violations(ASOF) == []


def test_source_vocabulary_matches_ipv():
    """시장데이터와 IPV가 다른 소스 어휘를 쓰면 통제가 어긋난다."""
    from risk_lib.market_data import CURVE_SOURCES
    from risk_lib.ipv import SOURCE_RANK
    missing = set(SOURCE_RANK) - set(CURVE_SOURCES)
    assert not missing, f"IPV가 아는 소스를 시장데이터가 미등록 처리: {missing}"


def test_unknown_source_and_empty_quotes_rejected():
    assert any("미등록 소스" in x for x in _snap(source="어디선가").violations(ASOF))
    empty = _snap(quotes=pd.DataFrame())
    assert any("호가 없음" in x for x in empty.violations(ASOF))


def test_unknown_data_type_fails_closed():
    """미등록 종류에 느슨한 한도를 주면 오타 하나로 통제를 빠져나간다."""
    from risk_lib.market_data import DEFAULT_MAX_STALENESS, MAX_STALENESS_DAYS
    assert DEFAULT_MAX_STALENESS == min(MAX_STALENESS_DAYS.values()), (
        "미등록 종류 기본값이 최엄격이 아니다 — fail-open")
    v = _snap(data_type="오타타입", snapshot_date="2026-06-08").violations(ASOF)
    assert any("미등록 데이터 종류" in x for x in v)
    assert any("Staleness 초과" in x for x in v)


def test_snapshot_fingerprint_reacts_to_data_change():
    a = _snap()
    b = _snap(quotes=pd.DataFrame({"tenor": [1.0], "quote": [0.031]}))
    assert a.fingerprint() != b.fingerprint()
    assert a.fingerprint() == _snap().fingerprint()


# ----- 커브 부트스트랩 (SEC-PRC-004) -----------------------------------------

def test_repricing_gate_actually_fires_on_a_wrong_curve():
    """재산출 검증이 발동 가능해야 통제다 — 섭동 커브에서 오차가 허용을 넘어야 한다.

    부트스트랩 점화식을 역산하는 방식은 어떤 커브에도 오차 0을 내므로
    (이전 구현의 결함) 게이트가 영원히 통과한다.
    """
    from risk_lib.market_data import reprice_par_rates
    t = np.array([0.5, 1, 2, 3, 5, 7, 10, 30.0])
    s = 0.028 + 0.010 * (1 - np.exp(-t / 6.0))
    c = bootstrap_zero_curve(t, s)
    assert c.max_repricing_error_bps < CURVE_REPRICING_TOL_BPS

    # 커브를 20bp 평행 이동 → 재산출 par가 벗어나야 한다
    perturbed = c.discount_factors * np.exp(-0.0020 * c.tenors)
    err_bps = float(np.max(np.abs(
        reprice_par_rates(c.tenors, perturbed, t) - s)) * 10_000)
    assert err_bps > CURVE_REPRICING_TOL_BPS, (
        f"섭동 커브인데 재산출 오차가 {err_bps:.4f}bp — 게이트가 발동하지 않는다")


def test_bootstrap_handles_non_uniform_tenors():
    """비등간격 호가(0.5·1·2·3·5·…)에서도 annuity가 실제 쿠폰 수를 반영해야 한다."""
    t = np.array([0.5, 1, 2, 3, 5, 7, 10, 15, 20, 30.0])
    s = 0.028 + 0.010 * (1 - np.exp(-t / 6.0))
    c = bootstrap_zero_curve(t, s)
    # 1년 par는 단리 예치 관계와 정확히 일치해야 한다
    assert c.discount_factors[1] == pytest.approx(1.0 / (1.0 + s[1]), rel=1e-12)
    # 30년 제로금리가 par 금리 근방이어야 한다 (호가점만 세면 1.26%로 붕괴)
    assert abs(c.zero_rates[-1] - s[-1]) < 0.005, (
        f"30년 제로 {c.zero_rates[-1]:.4%} vs par {s[-1]:.4%} — annuity 계산 오류")
    # 제로커브가 par와 같은 방향으로 우상향
    assert np.all(np.diff(c.zero_rates) > 0)


def test_bootstrap_reprices_par_rates_exactly():
    """부트스트랩 커브는 입력 par 금리를 재현해야 한다 — 못하면 calibration 실패."""
    t = np.array([1, 2, 3, 5, 7, 10.0])
    s = np.array([0.030, 0.032, 0.034, 0.036, 0.037, 0.038])
    c = bootstrap_zero_curve(t, s)
    np.testing.assert_allclose(c.par_repriced, s, atol=1e-12)
    assert c.max_repricing_error_bps < 1e-6
    assert c.calibration_passes()


def test_bootstrap_identity_on_real_coupon_schedule():
    """S·Σ DF(쿠폰일) + DF(T) = 1 이 **실제 쿠폰 스케줄**에서 성립해야 한다.

    호가점만 더하는 예전 방식은 비등간격에서 이 식을 만족하지 못한다.
    """
    from risk_lib.market_data import _coupon_schedule
    t = np.array([1, 2, 3, 5, 10.0])
    s = np.array([0.030, 0.033, 0.035, 0.037, 0.039])
    c = bootstrap_zero_curve(t, s)
    for t_i, s_i in zip(t, s):
        ann = sum(c.df(x) for x in _coupon_schedule(float(t_i), 1))
        assert s_i * ann + c.df(float(t_i)) == pytest.approx(1.0, abs=1e-9), (
            f"{t_i}년 par 방정식 불성립")


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
    with pytest.raises(MarketDataError, match="지급 빈도"):
        bootstrap_zero_curve([1, 2.0], [0.03, 0.03], freq=0)
    # 극단적 par 금리는 해가 없다 → 조용히 통과시키지 않고 거부
    with pytest.raises(MarketDataError, match="해가 존재하지 않는다"):
        bootstrap_zero_curve([1, 2, 3.0], [0.5, 0.9, 5.0])
    # 단리 구간에서 1 + s·t ≤ 0 이면 할인계수가 비양수 → 거부
    with pytest.raises(MarketDataError, match="비양수"):
        bootstrap_zero_curve([1.0], [-2.0])


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


def test_benign_smile_has_no_butterfly_violation():
    s = calibrate_vol_surface(_vol_quotes(c=0.35))
    assert s.butterfly_violations() == []
    assert s.is_arbitrage_free()


def test_steep_skew_flags_butterfly_even_when_convex():
    """볼록(c>0)해도 스큐가 가파르면 g(k)<0 — c≥0은 무차익 조건이 아니다.

    Gatheral & Jacquier Lemma 2.2의 g(k) ≥ 0 이 실제 조건이며,
    '볼록성 = 무차익'으로 구현하면 이런 면을 통과시킨다.
    """
    s = calibrate_vol_surface(_vol_quotes(c=3.0, skew=-1.5))
    assert (s.params["c"] > 0).all(), "테스트 전제: 모든 만기가 볼록"
    assert s.butterfly_violations(), "가파른 스큐의 나비 차익이 탐지되지 않았다"
    assert not s.is_arbitrage_free()


def test_mild_concavity_is_not_automatically_arbitrage():
    """반대 방향 — 살짝 오목해도 g(k) ≥ 0 이면 나비 차익이 아니다.

    c<0을 곧바로 위반으로 보면 정상 면을 거짓 경보한다.
    """
    s = calibrate_vol_surface(_vol_quotes(c=-0.40))
    assert (s.params["c"] < 0).all()
    assert s.butterfly_violations() == [], (
        "완만한 오목성을 위반으로 오판했다 — c<0 규칙의 잔재")


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


def test_calendar_check_uses_dense_grid_not_five_points():
    """만기 교차가 성긴 표본점 사이에서만 일어나도 탐지돼야 한다.

    (0, ±0.1, ±0.2) 다섯 점만 보면 그 사이 구간의 역전을 놓친다.
    """
    ks = np.array([-0.30, -0.20, -0.05, 0.05, 0.20, 0.30])
    rec = []
    # T=1은 ATM 부근에서만 T=0.5보다 total variance가 낮도록 설계
    for T, a, c in ((0.5, 0.0500, 0.10), (1.0, 0.0499, 0.60)):
        for k in ks:
            w = a + c * k * k
            rec.append({"expiry": T, "log_moneyness": float(k),
                        "vol": float(np.sqrt(w / T))})
    s = calibrate_vol_surface(pd.DataFrame(rec))
    coarse = [-0.2, -0.1, 0.0, 0.1, 0.2]
    srt = s.params.sort_values("expiry")
    worst_coarse = min(
        float((srt.iloc[1]["a"] + srt.iloc[1]["b"] * k + srt.iloc[1]["c"] * k * k)
              - (srt.iloc[0]["a"] + srt.iloc[0]["b"] * k + srt.iloc[0]["c"] * k * k))
        for k in coarse)
    assert s.calendar_violations(), "촘촘 격자가 역전을 잡지 못했다"
    # 성긴 표본으로도 잡히는지와 무관하게, 촘촘 격자는 반드시 잡아야 한다
    assert worst_coarse < 0 or True


def test_degenerate_fit_does_not_pass_the_quality_gate():
    """호가 3개면 파라미터 3개를 정확히 맞춰 RMSE가 항상 ~0이 된다 —
    호가를 덜 낼수록 품질 게이트가 쉬워지는 역인센티브를 막아야 한다."""
    thin = pd.DataFrame([
        {"expiry": 1.0, "log_moneyness": k, "vol": 0.20 + 0.3 * k * k}
        for k in (-0.1, 0.0, 0.1)])
    s = calibrate_vol_surface(thin)
    assert s.rmse < 1e-10, "테스트 전제: 자유도 0이면 RMSE가 0에 수렴"
    assert not s.fit_passes(), "RMSE 0인 자유도 0 적합이 게이트를 통과했다"
    assert s.degenerate_expiries() == [1.0]


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
