"""시장데이터 거버넌스 · Curve/Vol calibration — SEC-PRC-001 · SEC-PRC-004.

IPV(66)의 상류 의존성이다. 독립 가격을 만들려면 그 가격이 딛고 선 커브와
변동성면부터 통제돼야 한다 — 출처를 모르거나 오래됐거나 차익거래가 존재하는
곡선 위에서 산출한 "독립 가격"은 검증 근거가 되지 못한다.

통제 축:

  출처·스냅샷 (SEC-PRC-001)
      모든 시장데이터 점은 소스·스냅샷 시각·버전을 갖는다. 스냅샷 지문이
      바뀌면 그 위에서 산출한 모든 가격이 다른 값이 된다.

  Staleness
      기준일 대비 경과가 허용치를 넘은 데이터는 평가에 쓸 수 없다.
      "오래됐지만 없는 것보단 낫다"는 판단은 담당자가 아니라 정책이 한다.

  Calibration 품질 (SEC-PRC-004)
      부트스트랩된 제로커브가 시장 par 금리를 재현하는지, 변동성면이 시장
      호가를 RMSE 임계 내로 적합하는지 검증한다.

  무차익 (No-arbitrage)
      할인계수 단조감소 · 변동성면의 butterfly(볼록성) · calendar(만기 간
      total variance 비감소). 위반은 곧 모형이 만들어낸 가짜 기회다.

**주의**: 허용 경과일·RMSE 임계는 상품·시장·평가정책으로 통제되는 승인값이며,
본 모듈 기본값은 구조 시연용이다.

참조: RYNTA BRD SEC-PRC-001/004 · GOV-006, BCBS Prudent valuation,
      Gatheral & Jacquier (2014) — arbitrage-free implied volatility surfaces.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

# 소스 등급 — IPV의 SOURCE_RANK와 정합.
CURVE_SOURCES = ("consensus", "exchange", "broker", "internal")

# 데이터 종류별 허용 경과(일). 초과 시 평가 사용 불가.
MAX_STALENESS_DAYS: dict[str, int] = {
    "ir_curve": 1,        # 금리커브 — 일일 갱신
    "credit_curve": 3,    # 신용스프레드 — 유동성 낮음
    "vol_surface": 1,
    "fx": 1,
    "equity": 1,
}
DEFAULT_MAX_STALENESS = 5

# Calibration 품질 임계.
CURVE_REPRICING_TOL_BPS = 0.5     # 부트스트랩 커브의 par 금리 재현 오차
VOL_FIT_RMSE_TOL = 0.0050         # 변동성면 적합 RMSE (vol point, 50bp)


class MarketDataError(ValueError):
    """시장데이터 통제 위반."""


# ---------------------------------------------------------------- 스냅샷

@dataclass
class MarketDataSnapshot:
    """시장데이터 스냅샷 — 출처와 시점이 없는 데이터는 쓰지 않는다."""
    name: str
    data_type: str                 # ir_curve · vol_surface · credit_curve …
    source: str
    snapshot_date: str             # ISO date
    quotes: pd.DataFrame           # tenor/strike 등 + quote
    version: str = "1"

    def age_days(self, asof: str | date) -> int:
        a = asof if isinstance(asof, str) else asof.isoformat()
        return (date.fromisoformat(a) - date.fromisoformat(self.snapshot_date)).days

    def max_age(self) -> int:
        return MAX_STALENESS_DAYS.get(self.data_type, DEFAULT_MAX_STALENESS)

    def is_stale(self, asof: str | date) -> bool:
        return self.age_days(asof) > self.max_age()

    def violations(self, asof: str | date) -> list[str]:
        v = []
        if self.source not in CURVE_SOURCES:
            v.append(f"미등록 소스: {self.source}")
        if self.source == "internal":
            v.append("내부 소스 단독 — 독립 검증 소스 확보 필요")
        age = self.age_days(asof)
        if age < 0:
            v.append(f"미래 스냅샷 ({self.snapshot_date} > {asof})")
        elif self.is_stale(asof):
            v.append(f"Staleness 초과: {age}일 경과 (허용 {self.max_age()}일)")
        if self.quotes.empty:
            v.append("호가 없음")
        return v

    def fingerprint(self) -> str:
        """스냅샷 지문 — 데이터가 바뀌면 그 위의 모든 가격이 달라진다."""
        payload = {
            "name": self.name, "type": self.data_type, "source": self.source,
            "date": self.snapshot_date, "version": self.version,
            "quotes": self.quotes.round(10).to_dict(orient="records"),
        }
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 금리커브

@dataclass
class ZeroCurve:
    """부트스트랩된 제로커브."""
    tenors: np.ndarray             # 연 단위
    discount_factors: np.ndarray
    zero_rates: np.ndarray         # 연속복리
    par_input: np.ndarray          # 입력 par 금리
    par_repriced: np.ndarray       # 커브로 재산출한 par 금리
    max_repricing_error_bps: float
    snapshot: MarketDataSnapshot | None = None
    freq: int = 1

    def df(self, t: float) -> float:
        """로그선형 보간 할인계수 — 부트스트랩과 동일한 보간 규약."""
        return _df_interp(float(t), [float(x) for x in self.tenors],
                          [float(x) for x in np.log(self.discount_factors)])

    def calibration_passes(self, tol_bps: float = CURVE_REPRICING_TOL_BPS) -> bool:
        return self.max_repricing_error_bps <= tol_bps

    def is_arbitrage_free(self) -> bool:
        """할인계수는 만기에 대해 단조감소해야 한다 (양의 forward 금리)."""
        return bool(np.all(np.diff(self.discount_factors) < 1e-12))


def _coupon_schedule(maturity: float, freq: int = 1) -> list[float]:
    """만기까지의 쿠폰일 목록 (연 단위). 잔여 stub은 첫 쿠폰으로 둔다."""
    tau = 1.0 / freq
    n = int(round(maturity * freq))
    if abs(maturity * freq - n) < 1e-9 and n >= 1:
        return [i * tau for i in range(1, n + 1)]
    # 비정수 만기: stub + 정규 쿠폰
    times, t_i = [], maturity
    while t_i > 1e-9:
        times.append(t_i)
        t_i -= tau
    return sorted(x for x in times if x > 1e-9)


def _df_interp(t_query: float, nodes_t: list[float],
               nodes_logdf: list[float]) -> float:
    """로그선형 보간 할인계수. 첫 노드 이전 구간은 원점(DF=1)과 보간한다."""
    if t_query <= 1e-12:
        return 1.0
    tt = [0.0] + nodes_t
    ll = [0.0] + nodes_logdf
    return float(np.exp(np.interp(t_query, tt, ll)))


def reprice_par_rates(node_tenors, node_dfs, tenors, *, freq: int = 1):
    """주어진 할인커브로 par swap 금리를 재산출한다 (독립 검증용).

    부트스트랩 점화식의 역산이 아니라 **할인계수로부터 다시 가격을 계산**하는
    경로다. 따라서 커브가 틀리면(외부 공급·섭동·보간 규약 불일치) 재산출값이
    입력 par 금리에서 벗어나고 calibration 게이트가 발동한다 — 역산 방식은
    어떤 커브에도 오차 0을 내므로 통제가 되지 못한다.
    """
    nt = [float(x) for x in np.asarray(node_tenors, dtype=float)]
    nl = [float(x) for x in np.log(np.asarray(node_dfs, dtype=float))]
    tau = 1.0 / freq
    out = np.empty(len(tenors), dtype=float)
    for i, t_i in enumerate(np.asarray(tenors, dtype=float)):
        df_T = _df_interp(float(t_i), nt, nl)
        if t_i <= tau + 1e-12:
            out[i] = (1.0 / df_T - 1.0) / t_i
        else:
            ann = sum(tau * _df_interp(c, nt, nl)
                      for c in _coupon_schedule(float(t_i), freq))
            out[i] = (1.0 - df_T) / ann
    return out


def bootstrap_zero_curve(tenors, par_rates, *, freq: int = 1,
                         snapshot: MarketDataSnapshot | None = None) -> ZeroCurve:
    """par swap 금리에서 제로커브를 부트스트랩한다 (만기 간격을 실제로 반영).

    - 만기 ≤ 1/freq: 단리 예치 관행 ``DF = 1/(1 + s·t)``
    - 그 외: 실제 쿠폰 스케줄 [1/freq, 2/freq, …, T] 전체에 대해
      ``s·Σ τ·DF(t_i) + DF(T) = 1`` 을 만족하는 DF(T)를 이분법으로 구한다.
      중간 쿠폰일의 DF는 이미 확정된 노드에서 로그선형 보간한다.

    호가 만기가 비등간격(0.5·1·2·3·5·7·10·…)이어도 annuity가 실제 쿠폰 수를
    반영한다 — 호가점만 더하면 30년 스왑의 annuity가 10개 쿠폰으로 계산돼
    할인계수가 배로 틀린다.

    재산출 검증은 **부트스트랩 점화식의 역산이 아니라** 얻어진 커브로 실제
    쿠폰 스케줄을 다시 할인해 par 금리를 구하는 방식이다 — 역산은 어떤
    입력에도 오차 0을 내는 항등식이라 통제가 되지 못한다.
    """
    t = np.asarray(tenors, dtype=float)
    s = np.asarray(par_rates, dtype=float)
    if t.ndim != 1 or t.shape != s.shape:
        raise MarketDataError("만기와 par 금리의 길이가 다르다")
    if np.any(np.diff(t) <= 0):
        raise MarketDataError("만기는 증가 순이어야 한다")
    if np.any(t <= 0):
        raise MarketDataError("만기는 양수여야 한다")
    if freq < 1:
        raise MarketDataError("지급 빈도는 1 이상이어야 한다")

    tau = 1.0 / freq
    nodes_t: list[float] = []
    nodes_logdf: list[float] = []

    for t_i, s_i in zip(t, s):
        if t_i <= tau + 1e-12:
            df_i = 1.0 / (1.0 + s_i * t_i)          # 단리 예치
            if df_i <= 0:
                raise MarketDataError(
                    f"만기 {t_i}년에서 할인계수가 비양수 — par 금리 {s_i:.4%} 확인 필요")
        else:
            sched = _coupon_schedule(float(t_i), freq)

            def pv(df_guess: float) -> float:
                tt = nodes_t + [float(t_i)]
                ll = nodes_logdf + [float(np.log(df_guess))]
                ann = sum(tau * _df_interp(c, tt, ll) for c in sched)
                return s_i * ann + _df_interp(float(t_i), tt, ll) - 1.0

            lo, hi = 1e-12, 1.0
            if pv(lo) * pv(hi) > 0:
                raise MarketDataError(
                    f"만기 {t_i}년에서 부트스트랩 해가 존재하지 않는다 "
                    f"— par 금리 {s_i:.4%} 확인 필요")
            for _ in range(200):                      # 이분법 (scipy 비의존)
                mid = 0.5 * (lo + hi)
                if pv(lo) * pv(mid) <= 0:
                    hi = mid
                else:
                    lo = mid
            df_i = 0.5 * (lo + hi)

        nodes_t.append(float(t_i))
        nodes_logdf.append(float(np.log(df_i)))

    dfs = np.exp(np.asarray(nodes_logdf))
    zero = -np.asarray(nodes_logdf) / t

    # ---- 독립 재산출: 얻어진 커브로 par 금리를 다시 구한다 ----
    repriced = reprice_par_rates(np.asarray(nodes_t), np.exp(nodes_logdf),
                                 t, freq=freq)
    err_bps = float(np.max(np.abs(repriced - s)) * 10_000)

    return ZeroCurve(tenors=t, discount_factors=dfs, zero_rates=zero,
                     par_input=s, par_repriced=repriced,
                     max_repricing_error_bps=err_bps, snapshot=snapshot,
                     freq=freq)


# ---------------------------------------------------------------- 변동성면

@dataclass
class VolSurface:
    """만기별 total variance 이차 적합 (log-moneyness 기준).

        w(k, T) = a_T + b_T·k + c_T·k²      (w = σ²T, k = ln(K/F))
    """
    expiries: np.ndarray
    params: pd.DataFrame           # expiry, a, b, c, rmse, n_quotes
    rmse: float                    # 전체 RMSE (vol 단위)
    snapshot: MarketDataSnapshot | None = None

    def total_variance(self, k: float, T: float) -> float:
        """만기 간 total variance **선형보간** (nearest 사용 시 노드 사이
        내재변동성이 크게 틀리고 기간구조가 비단조가 된다). total variance에
        대한 선형보간은 calendar 무차익성을 보존한다."""
        ws = np.array([float(r["a"] + r["b"] * k + r["c"] * k * k)
                       for _, r in self.params.sort_values("expiry").iterrows()])
        ts = np.sort(self.expiries)
        return float(np.interp(float(T), ts, ws))

    def implied_vol(self, k: float, T: float) -> float:
        w = max(self.total_variance(k, T), 1e-12)
        return float(np.sqrt(w / T))

    def fit_passes(self, tol: float = VOL_FIT_RMSE_TOL) -> bool:
        return self.rmse <= tol

    # ---- 무차익 ----
    def _g(self, k: float, row) -> float:
        """Gatheral & Jacquier (2014) Lemma 2.2 의 g(k).

            g = (1 − k·w′/(2w))² − (w′²/4)(1/w + 1/4) + w″/2

        w(k)=a+bk+ck² 에서 w′=b+2ck, w″=2c. g(k) ≥ 0 이 나비 차익거래
        부재의 조건이다. **c ≥ 0(볼록성)은 이 조건과 동치가 아니다** —
        볼록해도 스큐가 가파르면 g<0 이 되고, 살짝 오목해도 g≥0 일 수 있다.
        """
        a, b, c = float(row["a"]), float(row["b"]), float(row["c"])
        w = a + b * k + c * k * k
        if w <= 0:
            return -1.0                      # total variance 비양수 자체가 위반
        wp = b + 2.0 * c * k
        wpp = 2.0 * c
        return ((1.0 - k * wp / (2.0 * w)) ** 2
                - (wp * wp / 4.0) * (1.0 / w + 0.25) + wpp / 2.0)

    def _k_grid(self, n: int = 201) -> np.ndarray:
        """적합 구간을 촘촘히 덮는 격자 — 성긴 표본은 구간 내 위반을 놓친다."""
        return np.linspace(-0.4, 0.4, n)

    def butterfly_violations(self, n_grid: int = 201) -> list[str]:
        """g(k) < 0 인 지점 탐색 (Gatheral 조건)."""
        out = []
        for _, row in self.params.iterrows():
            ks = self._k_grid(n_grid)
            gs = np.array([self._g(float(k), row) for k in ks])
            bad = gs < -1e-12
            if bad.any():
                i = int(np.argmin(gs))
                out.append(
                    f"T={row['expiry']:.2f}: g(k)<0 구간 {int(bad.sum())}/{len(ks)}점 "
                    f"(최소 g={gs[i]:.5f} @ k={ks[i]:+.3f}, c={row['c']:+.4f})")
        return out

    def calendar_violations(self, n_grid: int = 201) -> list[str]:
        """만기가 길수록 total variance가 커야 한다 (달력 차익 방지).

        고정 5점 표본은 그 사이 구간의 역전을 놓치므로 촘촘한 격자를 쓴다.
        """
        out = []
        srt = self.params.sort_values("expiry").reset_index(drop=True)
        ks = self._k_grid(n_grid)
        for i in range(1, len(srt)):
            prev, cur = srt.iloc[i - 1], srt.iloc[i]
            w_prev = prev["a"] + prev["b"] * ks + prev["c"] * ks ** 2
            w_cur = cur["a"] + cur["b"] * ks + cur["c"] * ks ** 2
            gap = w_cur - w_prev
            if (gap < -1e-12).any():
                j = int(np.argmin(gap))
                out.append(
                    f"T={cur['expiry']:.2f} vs {prev['expiry']:.2f}: "
                    f"total variance 역전 {int((gap < -1e-12).sum())}/{len(ks)}점 "
                    f"(최대 역전 {gap[j]:.5f} @ k={ks[j]:+.3f})")
        return out

    def is_arbitrage_free(self) -> bool:
        return not self.butterfly_violations() and not self.calendar_violations()


def calibrate_vol_surface(quotes: pd.DataFrame, *,
                          snapshot: MarketDataSnapshot | None = None) -> VolSurface:
    """만기별 total variance를 log-moneyness의 이차식으로 적합.

    quotes: expiry(연) · log_moneyness · vol 컬럼.
    만기당 호가가 3개 미만이면 이차 적합이 불가능하므로 거부한다 —
    부족한 데이터를 억지로 적합하면 c의 부호가 임의로 정해져 차익거래가 생긴다.
    """
    need = {"expiry", "log_moneyness", "vol"}
    if not need <= set(quotes.columns):
        raise MarketDataError(f"필요 컬럼 누락: {need - set(quotes.columns)}")
    if (quotes["vol"] <= 0).any():
        raise MarketDataError("변동성은 양수여야 한다")

    rows, resid_all = [], []
    for T, g in quotes.groupby("expiry"):
        if len(g) < 3:
            raise MarketDataError(
                f"만기 {T}년 호가 {len(g)}개 — 이차 적합에 최소 3개 필요")
        k = g["log_moneyness"].to_numpy(dtype=float)
        w = (g["vol"].to_numpy(dtype=float) ** 2) * float(T)
        c, b, a = np.polyfit(k, w, 2)
        w_hat = a + b * k + c * k * k
        vol_hat = np.sqrt(np.maximum(w_hat, 1e-12) / float(T))
        resid = vol_hat - g["vol"].to_numpy(dtype=float)
        resid_all.append(resid)
        rows.append({"expiry": float(T), "a": float(a), "b": float(b),
                     "c": float(c),
                     "rmse": float(np.sqrt(np.mean(resid ** 2))),
                     "n_quotes": int(len(g))})

    params = pd.DataFrame(rows).sort_values("expiry").reset_index(drop=True)
    rmse = float(np.sqrt(np.mean(np.concatenate(resid_all) ** 2)))
    return VolSurface(expiries=params["expiry"].to_numpy(),
                      params=params, rmse=rmse, snapshot=snapshot)


# ---------------------------------------------------------------- 거버넌스 판정

@dataclass
class MarketDataGovernance:
    """스냅샷·calibration·무차익을 한 번에 판정한 결과."""
    snapshots: pd.DataFrame        # 스냅샷별 통제 결과
    curve: ZeroCurve
    vol: VolSurface
    violations: list[str] = field(default_factory=list)

    def passes(self) -> bool:
        return not self.violations


def assess(snapshots: list[MarketDataSnapshot], curve: ZeroCurve,
           vol: VolSurface, *, asof: str | date) -> MarketDataGovernance:
    """시장데이터 거버넌스 종합 판정."""
    rows, viol = [], []
    for s in snapshots:
        sv = s.violations(asof)
        rows.append({
            "name": s.name, "type": s.data_type, "source": s.source,
            "snapshot_date": s.snapshot_date, "age_days": s.age_days(asof),
            "max_age": s.max_age(), "stale": s.is_stale(asof),
            "fingerprint": s.fingerprint()[:16],
            "status": "OK" if not sv else "위반",
            "detail": " · ".join(sv) or "—",
        })
        viol.extend(f"[{s.name}] {x}" for x in sv)

    if not curve.calibration_passes():
        viol.append(f"[금리커브] par 재현 오차 "
                    f"{curve.max_repricing_error_bps:.2f}bp > "
                    f"{CURVE_REPRICING_TOL_BPS}bp")
    if not curve.is_arbitrage_free():
        viol.append("[금리커브] 할인계수 비단조 — 음의 forward 금리")
    if not vol.fit_passes():
        viol.append(f"[변동성면] 적합 RMSE {vol.rmse:.4f} > {VOL_FIT_RMSE_TOL}")
    viol.extend(f"[변동성면] butterfly {x}" for x in vol.butterfly_violations())
    viol.extend(f"[변동성면] calendar {x}" for x in vol.calendar_violations())

    return MarketDataGovernance(snapshots=pd.DataFrame(rows), curve=curve,
                                vol=vol, violations=viol)


# ---------------------------------------------------------------- 데모 데이터

def demo_market_data(*, asof: str, seed: int = 42
                     ) -> tuple[list[MarketDataSnapshot], ZeroCurve, VolSurface]:
    """통제 시연용 시장데이터 — **예시**. 실제 피드로 교체가 전제."""
    rng = np.random.default_rng(seed + 909)
    asof_d = date.fromisoformat(asof)

    # 금리커브 — 우상향 par 금리
    tenors = np.array([0.5, 1, 2, 3, 5, 7, 10, 15, 20, 30], dtype=float)
    par = 0.028 + 0.010 * (1 - np.exp(-tenors / 6.0))
    curve_snap = MarketDataSnapshot(
        name="KRW IRS par curve", data_type="ir_curve", source="consensus",
        snapshot_date=asof,
        quotes=pd.DataFrame({"tenor": tenors, "quote": par}))
    curve = bootstrap_zero_curve(tenors, par, snapshot=curve_snap)

    # 변동성면 — 스마일(볼록) + 만기 증가에 따른 total variance 증가
    expiries = np.array([0.25, 0.5, 1.0, 2.0])
    ks = np.array([-0.25, -0.15, -0.05, 0.0, 0.05, 0.15, 0.25])
    rec = []
    for T in expiries:
        base = 0.18 + 0.02 * np.sqrt(T)          # ATM vol, 만기와 함께 상승
        for k in ks:
            v = base + 0.35 * k * k - 0.05 * k   # 볼록 + 약한 스큐
            v += rng.normal(0.0, 0.0008)         # 호가 잡음 (RMSE 임계 이내)
            rec.append({"expiry": float(T), "log_moneyness": float(k),
                        "vol": float(v)})
    vol_quotes = pd.DataFrame(rec)
    vol_snap = MarketDataSnapshot(
        name="KOSPI200 vol surface", data_type="vol_surface", source="exchange",
        snapshot_date=asof, quotes=vol_quotes)
    vol = calibrate_vol_surface(vol_quotes, snapshot=vol_snap)

    # 신용커브 — 3일 지연(허용 이내), FX — 6일 지연(위반 시연)
    credit_snap = MarketDataSnapshot(
        name="CDS spread curve", data_type="credit_curve", source="broker",
        snapshot_date=(asof_d.fromordinal(asof_d.toordinal() - 3)).isoformat(),
        quotes=pd.DataFrame({"tenor": [1, 3, 5, 10],
                             "quote": [65.0, 95.0, 120.0, 155.0]}))
    fx_snap = MarketDataSnapshot(
        name="USD/KRW spot·forward", data_type="fx", source="broker",
        snapshot_date=(asof_d.fromordinal(asof_d.toordinal() - 6)).isoformat(),
        quotes=pd.DataFrame({"tenor": [0.0, 0.25, 0.5, 1.0],
                             "quote": [1350.0, 1352.0, 1355.0, 1361.0]}))

    return [curve_snap, vol_snap, credit_snap, fx_snap], curve, vol


def assess_from_result(result) -> MarketDataGovernance:
    asof = result.meta.get("asof", date.today().isoformat())
    snaps, curve, vol = demo_market_data(
        asof=asof, seed=result.meta.get("seed", 42))
    return assess(snaps, curve, vol, asof=asof)
