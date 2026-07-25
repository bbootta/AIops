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

    def df(self, t: float) -> float:
        """로그선형 보간 할인계수 (구간 밖은 평탄 외삽)."""
        if t <= 0:
            return 1.0
        logdf = np.interp(t, self.tenors, np.log(self.discount_factors))
        return float(np.exp(logdf))

    def calibration_passes(self, tol_bps: float = CURVE_REPRICING_TOL_BPS) -> bool:
        return self.max_repricing_error_bps <= tol_bps

    def is_arbitrage_free(self) -> bool:
        """할인계수는 만기에 대해 단조감소해야 한다 (양의 forward 금리)."""
        return bool(np.all(np.diff(self.discount_factors) < 1e-12))


def bootstrap_zero_curve(tenors, par_rates, *,
                         snapshot: MarketDataSnapshot | None = None) -> ZeroCurve:
    """연 1회 지급 par swap 금리에서 제로커브를 부트스트랩한다.

        S_n · Σ_{i≤n} DF_i + DF_n = 1
        ⇒ DF_n = (1 − S_n · Σ_{i<n} DF_i) / (1 + S_n)

    입력 par 금리를 커브로 재산출해 오차(bp)를 함께 반환한다 — 재현하지 못하는
    커브는 calibration 실패다.
    """
    t = np.asarray(tenors, dtype=float)
    s = np.asarray(par_rates, dtype=float)
    if t.ndim != 1 or t.shape != s.shape:
        raise MarketDataError("만기와 par 금리의 길이가 다르다")
    if np.any(np.diff(t) <= 0):
        raise MarketDataError("만기는 증가 순이어야 한다")
    if np.any(t <= 0):
        raise MarketDataError("만기는 양수여야 한다")

    dfs = np.empty_like(t)
    running = 0.0
    for i in range(len(t)):
        dfs[i] = (1.0 - s[i] * running) / (1.0 + s[i])
        if dfs[i] <= 0:
            raise MarketDataError(
                f"만기 {t[i]}년에서 할인계수가 비양수 — par 금리 {s[i]:.4%} 확인 필요")
        running += dfs[i]

    zero = -np.log(dfs) / t

    # 재산출: annuity로 par 금리를 되돌린다.
    annuity = np.cumsum(dfs)
    repriced = (1.0 - dfs) / annuity
    err_bps = float(np.max(np.abs(repriced - s)) * 10_000)

    return ZeroCurve(tenors=t, discount_factors=dfs, zero_rates=zero,
                     par_input=s, par_repriced=repriced,
                     max_repricing_error_bps=err_bps, snapshot=snapshot)


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
        row = self.params.iloc[int(np.argmin(np.abs(self.expiries - T)))]
        return float(row["a"] + row["b"] * k + row["c"] * k * k)

    def implied_vol(self, k: float, T: float) -> float:
        w = max(self.total_variance(k, T), 1e-12)
        return float(np.sqrt(w / T))

    def fit_passes(self, tol: float = VOL_FIT_RMSE_TOL) -> bool:
        return self.rmse <= tol

    # ---- 무차익 ----
    def butterfly_violations(self) -> list[str]:
        """볼록성 — c < 0 이면 나비 차익거래가 존재한다."""
        return [f"T={row['expiry']:.2f}: c={row['c']:.5f} < 0 (볼록성 위반)"
                for _, row in self.params.iterrows() if row["c"] < 0]

    def calendar_violations(self, k_grid=(-0.2, -0.1, 0.0, 0.1, 0.2)) -> list[str]:
        """만기가 길수록 total variance가 커야 한다 (달력 차익 방지)."""
        out = []
        srt = self.params.sort_values("expiry")
        for k in k_grid:
            w = [float(r["a"] + r["b"] * k + r["c"] * k * k)
                 for _, r in srt.iterrows()]
            for i in range(1, len(w)):
                if w[i] < w[i - 1] - 1e-12:
                    out.append(
                        f"k={k:+.2f}: T={srt.iloc[i]['expiry']:.2f} total variance "
                        f"{w[i]:.5f} < T={srt.iloc[i-1]['expiry']:.2f} {w[i-1]:.5f}")
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
