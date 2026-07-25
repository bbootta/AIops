"""독립가격검증(IPV) · 평가조정 — SEC-PRC-005 · MR-F003 · GOV-006.

Front Office가 산출한 가격을 독립 소스로 재검증하고, 검증 결과를 재무제표에
반영하기 위한 평가조정(Valuation Adjustment)을 산출한다.

핵심 통제:

  가격차이 판정 (MR-F003)
      Break = |P_front − P_bench| > max(T_abs, |P_bench| × T_rel)
      **절대·상대 허용오차를 동시에 적용**한다. 하나만 쓰면 소액 상품에서
      과다 BREAK, 대액 상품에서 미탐지가 발생한다.

  소스 위계 (Price Source Hierarchy)
      consensus > broker > model. Front Office 자체 모형만으로 검증된
      포지션은 "독립검증 미완"이며, 커버리지에서 제외된다 — 자기 가격을
      자기가 확인하는 것은 독립검증이 아니다.

  평가조정 (Prudent Valuation 계열)
      bid-offer spread · 모형 불확실성 · 집중도 · Day-1 P&L 이연.
      IPV에서 확인된 차이는 조정으로 반영되며, 미해소 BREAK는 aging된다.

**주의**: 허용오차·조정 계수는 상품·유동성·평가정책으로 통제되는 승인값이다.
본 모듈의 기본값은 구조 시연용이며 기관 승인 사양으로 교체가 전제다.

참조: BCBS Prudent valuation guidance, CRR Art.105 (신중한 평가),
      RYNTA 수식랩 MR-F003 · BRD SEC-PRC-003/005 · GOV-006.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# 소스 위계 — 숫자가 낮을수록 독립성이 높다.
SOURCE_RANK: dict[str, int] = {
    "consensus": 1,      # 컨센서스 서비스 (Markit/Totem 등)
    "broker": 2,         # 브로커 호가
    "exchange": 2,       # 거래소 종가
    "model": 3,          # 독립 검증모형 (FO 모형과 분리된 것)
    "front_office": 9,   # FO 자체 — 독립검증으로 인정하지 않음
}
INDEPENDENT_SOURCES = tuple(k for k, v in SOURCE_RANK.items() if v <= 3)

# 허용오차 기본값 (상품군별) — (절대, 상대). 승인값으로 교체 대상.
DEFAULT_TOLERANCE: dict[str, tuple[float, float]] = {
    "option": (50_000.0, 0.010),
    "swap":   (100_000.0, 0.005),
    "cds":    (75_000.0, 0.008),
}
FALLBACK_TOLERANCE = (100_000.0, 0.010)

# 평가조정 계수 — 신중한 평가(prudent valuation) 방향으로만 작동(가치 차감).
BID_OFFER_FRAC = 0.0005          # 명목 대비 절반스프레드
MODEL_UNCERTAINTY_FRAC = 0.0010  # 모형 불확실성 (검증소스가 model인 건에 한함)
CONCENTRATION_THRESHOLD = 0.15   # 단일 상품군 비중 초과분에 부과
CONCENTRATION_FRAC = 0.0008
DAY1_DEFERRAL_FRAC = 0.25        # 미검증 포지션의 Day-1 손익 이연 비율

BREAK_AGING_BUCKETS = ((0, 5), (6, 30), (31, 90), (91, 10_000))


@dataclass
class IPVResult:
    """IPV 실행 결과."""
    positions: pd.DataFrame       # 포지션별 검증 결과
    breaks: pd.DataFrame          # BREAK 건만
    adjustments: pd.DataFrame     # 평가조정 항목별
    aging: pd.DataFrame           # 미해소 BREAK aging
    n_positions: int
    n_verified: int               # 독립 소스로 검증된 건수
    coverage: float               # 독립검증 커버리지 (건수 기준)
    coverage_by_notional: float   # 명목 기준 커버리지
    n_breaks: int
    break_rate: float
    gross_diff: float             # |차이| 합계
    total_adjustment: float       # 평가조정 합계 (양수 = 가치 차감)

    def passes(self, *, max_break_rate: float = 0.05,
               min_coverage: float = 0.90) -> bool:
        """IPV 게이트 — BREAK율과 커버리지를 동시에 충족해야 통과."""
        return self.break_rate <= max_break_rate and self.coverage >= min_coverage


# ---------------------------------------------------------------- 가격차이

def price_break(front: float, benchmark: float,
                tol_abs: float, tol_rel: float) -> bool:
    """MR-F003 — 절대·상대 허용오차를 **동시에** 적용한 BREAK 판정.

    허용 한도 = max(절대허용, |기준가| × 상대허용). 차이가 이를 초과하면 BREAK.
    """
    if tol_abs < 0 or tol_rel < 0:
        raise ValueError("허용오차는 음수일 수 없다")
    limit = max(tol_abs, abs(benchmark) * tol_rel)
    return abs(front - benchmark) > limit


def tolerance_for(kind: str) -> tuple[float, float]:
    return DEFAULT_TOLERANCE.get(kind, FALLBACK_TOLERANCE)


def is_independent(source: str) -> bool:
    """FO 자체 가격은 독립검증이 아니다."""
    return SOURCE_RANK.get(source, 99) <= 3


# ---------------------------------------------------------------- IPV 실행

def run_ipv(trades: pd.DataFrame, *, seed: int = 42,
            tolerances: dict[str, tuple[float, float]] | None = None,
            asof_day: int = 0) -> IPVResult:
    """트레이딩북에 IPV를 수행한다.

    trades: `sensitivities.synthesise_trading_book().trades` 형식
            (kind · notional · price 컬럼 필요)
    독립 소스 가격과 미해소 기간은 seed 고정으로 합성한다 — 실제 운영에서는
    컨센서스·브로커 피드로 대체된다.
    """
    if trades.empty:
        raise ValueError("트레이딩북이 비어 있다 — IPV 대상 없음")
    rng = np.random.default_rng(seed + 4242)
    tolerances = tolerances or {}

    n = len(trades)
    kinds = trades["kind"].to_numpy()
    notional = trades["notional"].to_numpy(dtype=float)

    # FO 평가액(원) — 옵션은 단위가격×명목, 그 외는 명목 기준 평가액 대용.
    # 단위가격과 금액을 섞으면 공통 절대 허용오차가 옵션에는 사실상 무한대가
    # 되어 어떤 오평가도 BREAK가 나지 않는다 — 전부 '금액' 단위로 통일한다.
    unit_price = trades["price"].to_numpy(dtype=float)
    fo_price = np.where(unit_price != 0.0,
                        unit_price * notional / 100.0,   # 옵션: 명목 대비 평가액
                        notional * 0.01)

    # 독립 소스 배정 — 유동성이 높은 상품일수록 상위 소스 확보 확률이 높다.
    src_choices = np.array(["consensus", "broker", "exchange",
                            "model", "front_office"])
    src_p = {"option": [0.30, 0.30, 0.10, 0.20, 0.10],
             "swap":   [0.40, 0.30, 0.05, 0.20, 0.05],
             "cds":    [0.20, 0.35, 0.00, 0.30, 0.15]}
    sources = np.array([
        rng.choice(src_choices, p=src_p.get(k, [0.2, 0.3, 0.1, 0.3, 0.1]))
        for k in kinds])

    # 독립 가격 = FO 가격 ± 잡음 (소스가 독립적일수록 잡음 작음).
    # 잡음 폭은 허용오차(0.5~1.0%)보다 작게 잡아 BREAK가 예외로 나타나게 한다 —
    # 정상 운영에서 BREAK는 소수여야 하고, 다수면 허용오차나 소스가 문제다.
    # FO 소스에도 잠재 오차를 부여한다: 검증되지 않았을 뿐 가격이 맞다는 뜻은
    # 아니며, 이 값이 Day-1 이연 조정의 근거가 된다.
    noise_scale = np.array([
        {"consensus": 0.0015, "broker": 0.0030, "exchange": 0.0010,
         "model": 0.0060, "front_office": 0.0080}[s] for s in sources])
    bench = fo_price * (1.0 + rng.normal(0.0, 1.0, n) * noise_scale)

    tol_abs = np.empty(n)
    tol_rel = np.empty(n)
    for i, k in enumerate(kinds):
        a, r = tolerances.get(k, tolerance_for(k))
        tol_abs[i], tol_rel[i] = a, r

    diff = fo_price - bench
    limit = np.maximum(tol_abs, np.abs(bench) * tol_rel)
    verified = np.array([is_independent(s) for s in sources])
    # 미검증 건은 BREAK 판정 자체가 불가 — 통과로 세지 않는다.
    # (diff는 계산되지만 판정 근거로 쓰지 않고, Day-1 이연 조정의 크기로만 쓴다.)
    is_break = verified & (np.abs(diff) > limit)

    days_open = np.where(is_break, rng.integers(1, 120, n), 0)

    pos = pd.DataFrame({
        "kind": kinds, "notional": notional,
        "fo_price": fo_price, "source": sources,
        "benchmark_price": bench, "diff": diff, "abs_diff": np.abs(diff),
        "tol_abs": tol_abs, "tol_rel": tol_rel, "limit": limit,
        "verified": verified, "is_break": is_break, "days_open": days_open,
    })

    breaks = pos[pos["is_break"]].copy().sort_values("abs_diff", ascending=False)

    # ---- 평가조정 (신중한 평가 방향 = 가치 차감) ----
    total_notional = float(notional.sum())
    model_notional = float(notional[sources == "model"].sum())

    kind_share = pd.Series(notional).groupby(pd.Series(kinds)).sum() / total_notional
    conc_excess = float(
        sum(max(0.0, s - CONCENTRATION_THRESHOLD) for s in kind_share)) * total_notional

    adj_rows = [
        ("Bid-offer spread", total_notional * BID_OFFER_FRAC,
         "전 포지션 명목 대비 절반스프레드"),
        ("모형 불확실성", model_notional * MODEL_UNCERTAINTY_FRAC,
         "독립 검증소스가 모형인 포지션"),
        ("집중도", conc_excess * CONCENTRATION_FRAC,
         f"단일 상품군 비중 {CONCENTRATION_THRESHOLD:.0%} 초과분"),
        ("Day-1 P&L 이연", float(np.abs(diff)[~verified].sum()) * DAY1_DEFERRAL_FRAC,
         "독립검증 미완 포지션의 초기 손익 이연"),
        ("확인된 가격차이", float(breaks["abs_diff"].sum()),
         "IPV BREAK 금액 — 해소 전까지 조정 유지"),
    ]
    adjustments = pd.DataFrame(adj_rows, columns=["항목", "금액", "근거"])

    # ---- BREAK aging ----
    aging_rows = []
    for lo, hi in BREAK_AGING_BUCKETS:
        sel = breaks[(breaks["days_open"] >= lo) & (breaks["days_open"] <= hi)]
        label = f"{lo}~{hi}일" if hi < 10_000 else f"{lo}일 이상"
        aging_rows.append({
            "bucket": label, "n": int(len(sel)),
            "amount": float(sel["abs_diff"].sum()),
            "escalation": ("정상" if hi <= 5 else
                           "부서장 검토" if hi <= 30 else
                           "리스크위원회 보고" if hi <= 90 else
                           "즉시 조치 필요"),
        })
    aging = pd.DataFrame(aging_rows)

    n_verified = int(verified.sum())
    return IPVResult(
        positions=pos, breaks=breaks, adjustments=adjustments, aging=aging,
        n_positions=n, n_verified=n_verified,
        coverage=n_verified / n,
        coverage_by_notional=float(notional[verified].sum()) / total_notional,
        n_breaks=int(is_break.sum()),
        break_rate=float(is_break.sum()) / max(n_verified, 1),
        gross_diff=float(np.abs(diff)[verified].sum()),
        total_adjustment=float(adjustments["금액"].sum()),
    )


def run_ipv_from_result(result, *, seed: int | None = None) -> IPVResult:
    """PipelineResult의 은행 북에서 트레이딩북을 합성해 IPV 실행."""
    from risk_lib.sensitivities import synthesise_trading_book
    seed = seed if seed is not None else result.meta.get("seed", 42)
    # 파이프라인이 보유한 포트폴리오 요약만으로는 부족하므로 데모 북을 재생성.
    from risk_lib.data_gen import generate_portfolio
    book = synthesise_trading_book(
        generate_portfolio(seed=seed).query("asset_class == 'bank'"), seed=seed)
    return run_ipv(book.trades, seed=seed)
