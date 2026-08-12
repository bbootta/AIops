"""독립가격검증(IPV) 테스트 — SEC-PRC-005 · MR-F003 · GOV-006."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib.ipv import (
    price_break, tolerance_for, is_independent, run_ipv, run_ipv_from_result,
    SOURCE_RANK, DEFAULT_TOLERANCE, INDEPENDENT_SOURCES,
)


# ----- MR-F003 가격차이 판정 -------------------------------------------------

def test_mrf003_applies_both_tolerances():
    """한도 = max(절대, |기준가| × 상대). 둘 다 넘어야 통과, 하나만 넘어도 BREAK."""
    # 절대는 크고 상대는 작은 경우 → 절대가 한도를 지배
    assert not price_break(1_050_000, 1_000_000, 100_000, 0.001)   # 차이 5만 < 10만
    assert price_break(1_200_000, 1_000_000, 100_000, 0.001)       # 차이 20만 > 10만
    # 상대가 지배하는 경우 (대액)
    assert not price_break(1.02e9, 1.0e9, 100_000, 0.05)           # 한도 5천만
    assert price_break(1.20e9, 1.0e9, 100_000, 0.05)               # 차이 2억 > 5천만


def test_mrf003_single_tolerance_would_misjudge():
    """절대만 쓰면 대액 미탐지, 상대만 쓰면 소액 과다탐지 — max()가 둘을 막는다."""
    # 대액: 상대 없이 절대(10만)만 쓰면 1% 차이(1천만)를 BREAK로 보지만
    # 실제로는 한도가 상대 기준 5천만이므로 정상
    assert not price_break(1.01e9, 1.0e9, 100_000, 0.05)
    # 소액: 상대만 쓰면 한도가 0.5원이라 1원 차이도 BREAK, 절대 하한이 막아준다
    assert not price_break(101.0, 100.0, 50.0, 0.005)


def test_price_break_is_symmetric_and_rejects_negative_tolerance():
    assert price_break(120, 100, 5, 0.01) == price_break(80, 100, 5, 0.01)
    with pytest.raises(ValueError, match="음수"):
        price_break(100, 100, -1, 0.01)


def test_tolerance_lookup_has_fallback():
    assert tolerance_for("swap") == DEFAULT_TOLERANCE["swap"]
    assert tolerance_for("미등록상품") == (100_000.0, 0.010)


# ----- 소스 위계 -------------------------------------------------------------

def test_front_office_is_not_independent():
    """자기 가격을 자기가 확인하는 것은 독립검증이 아니다."""
    assert not is_independent("front_office")
    assert "front_office" not in INDEPENDENT_SOURCES
    for s in ("consensus", "broker", "exchange", "model"):
        assert is_independent(s)


def test_source_hierarchy_ordering():
    assert SOURCE_RANK["consensus"] < SOURCE_RANK["broker"]
    assert SOURCE_RANK["broker"] < SOURCE_RANK["model"]
    assert SOURCE_RANK["model"] < SOURCE_RANK["front_office"]


# ----- IPV 실행 --------------------------------------------------------------

@pytest.fixture(scope="module")
def ipv(result):
    return run_ipv_from_result(result, seed=42)


def test_ipv_runs_and_is_deterministic(result):
    a = run_ipv_from_result(result, seed=42)
    b = run_ipv_from_result(result, seed=42)
    assert a.n_positions == b.n_positions
    assert a.n_breaks == b.n_breaks
    assert a.total_adjustment == pytest.approx(b.total_adjustment, rel=1e-12)


def test_unverified_positions_are_not_counted_as_passing(ipv):
    """FO 소스 포지션은 검증에서 제외되며 BREAK 판정 대상이 아니다."""
    pos = ipv.positions
    fo = pos[pos["source"] == "front_office"]
    if not fo.empty:
        assert not fo["verified"].any()
        assert not fo["is_break"].any(), "미검증 건이 BREAK로 잡혔다"
    # 커버리지 = 검증 건수 / 전체
    assert ipv.coverage == pytest.approx(ipv.n_verified / ipv.n_positions)
    assert ipv.n_verified == int(pos["verified"].sum())


def test_break_rate_is_over_verified_not_total(ipv):
    """BREAK율 분모는 검증 건수 — 미검증을 분모에 넣으면 비율이 희석된다."""
    assert ipv.break_rate == pytest.approx(ipv.n_breaks / ipv.n_verified)
    assert ipv.break_rate <= 1.0


def test_breaks_exceed_their_own_limit(ipv):
    """BREAK로 표기된 건은 실제로 한도를 초과해야 한다."""
    b = ipv.breaks
    if not b.empty:
        assert (b["abs_diff"] > b["limit"]).all()
    # 반대로 non-break 검증분은 한도 이내
    ok = ipv.positions[ipv.positions["verified"] & ~ipv.positions["is_break"]]
    assert (ok["abs_diff"] <= ok["limit"]).all()


def test_gate_requires_both_break_rate_and_coverage(ipv):
    """게이트는 두 조건을 동시에 요구한다 — 하나만 충족하면 미통과."""
    assert ipv.passes(max_break_rate=1.0, min_coverage=0.0) is True
    # 커버리지 조건만 불가능하게
    assert ipv.passes(max_break_rate=1.0, min_coverage=1.01) is False
    # BREAK율 조건만 불가능하게
    assert ipv.passes(max_break_rate=-0.01, min_coverage=0.0) is False


def test_adjustments_are_all_non_negative(ipv):
    """신중한 평가 — 조정은 가치 차감 방향으로만 작동한다."""
    assert (ipv.adjustments["금액"] >= -1e-9).all()
    assert ipv.total_adjustment == pytest.approx(ipv.adjustments["금액"].sum())
    assert len(ipv.adjustments) == 5


def test_confirmed_break_amount_flows_into_adjustments(ipv):
    """확인된 BREAK 금액이 평가조정 항목에 그대로 반영된다."""
    row = ipv.adjustments.set_index("항목").loc["확인된 가격차이", "금액"]
    assert row == pytest.approx(float(ipv.breaks["abs_diff"].sum()))


def test_aging_buckets_partition_all_breaks(ipv):
    """aging 버킷의 건수 합계가 전체 BREAK 건수와 일치해야 한다 (누락 없음)."""
    assert int(ipv.aging["n"].sum()) == ipv.n_breaks
    assert float(ipv.aging["amount"].sum()) == pytest.approx(
        float(ipv.breaks["abs_diff"].sum()))
    # 오래된 버킷일수록 강한 조치
    assert ipv.aging.iloc[0]["escalation"] == "정상"
    assert "즉시" in ipv.aging.iloc[-1]["escalation"]


def test_empty_book_rejected():
    with pytest.raises(ValueError, match="비어 있다"):
        run_ipv(pd.DataFrame(columns=["kind", "notional", "price"]))


def test_tighter_tolerance_produces_more_breaks(result):
    """허용오차를 좁히면 BREAK가 늘어야 한다 — 판정이 실제로 오차에 반응하는지."""
    from risk_lib.sensitivities import synthesise_trading_book
    from risk_lib.data_gen import generate_portfolio
    book = synthesise_trading_book(
        generate_portfolio(seed=42).query("asset_class == 'bank'"), seed=42)
    loose = run_ipv(book.trades, seed=42,
                    tolerances={k: (a * 10, r * 10)
                                for k, (a, r) in DEFAULT_TOLERANCE.items()})
    tight = run_ipv(book.trades, seed=42,
                    tolerances={k: (a * 0.1, r * 0.1)
                                for k, (a, r) in DEFAULT_TOLERANCE.items()})
    assert tight.n_breaks > loose.n_breaks


# ----- 보고서 · 커버리지 -----------------------------------------------------

def test_ipv_page_renders_gate_and_source_hierarchy(result):
    from risk_lib.ops_pages.market_trading import page_ipv
    html = page_ipv(result)
    assert "독립가격검증" in html
    assert "IPV 게이트" in html
    # FO 자체 가격 불인정 원칙이 페이지에 명시돼야 한다
    assert "인정하지 않습니다" in html
    assert "Prudent Valuation" in html


def test_ipv_page_registered():
    from risk_lib.page_registry import PAGES
    specs = [p for p in PAGES if p.filename == "66_ipv.html"]
    assert len(specs) == 1
    assert callable(specs[0].resolve())


def test_coverage_marks_ipv_requirements():
    from risk_lib import rynta
    df = rynta.coverage_frame().set_index("id")
    assert df.loc["SEC-PRC-005", "status"] == "covered"
    assert df.loc["GOV-006", "status"] == "covered"
    assert "ipv" in df.loc["SEC-PRC-005", "modules"]
    # 담당은 시장리스크 에이전트
    assert df.loc["SEC-PRC-005", "owner"] == "market-risk-analyst"
