"""합계형 독립 재계산: RWA 합계와 산출하한 · 총자본비율 · ECL 합계 · 대손준비금.

18차 검수에서 요청서 재계산 대상 중 이 네 가지를 하니스 밖에서 손으로 다시
계산했다. 여기 없으면 다음 회차에도 손으로 한다.
"""

from __future__ import annotations

import pytest

from tools.independent_recalc import (
    RECALCULATORS,
    RecalcError,
    recalculate,
    reserve_shortfall_forms,
)


def test_registry_covers_the_request_composites():
    assert {"rwa_final_total", "total_ratio", "ecl_total",
            "reserve_shortfall"} <= set(RECALCULATORS)


# ---- RWA 합계와 산출하한

RWA_PARTS = {"credit_rwa": 7_573.18, "ccr_rwa": 19.46, "market_rwa": 720.64,
             "operational_rwa": 1_037.01, "fund_rwa": 3_331.23,
             "securitisation_rwa": 797.11}


def test_rwa_total_is_the_component_sum_when_floor_does_not_bind():
    inputs = {**RWA_PARTS, "floor_factor": 0.725,
              "standardised_rwa_total": 11_408.97}
    r = recalculate("rwa_final_total", claimed=sum(RWA_PARTS.values()),
                    inputs_operational=inputs, tolerance=1e-9)
    assert r["status"] == "ok"


def test_rwa_total_binds_to_the_floor_when_standardised_is_large():
    inputs = {**RWA_PARTS, "floor_factor": 0.725,
              "standardised_rwa_total": 30_000.0}
    r = recalculate("rwa_final_total", claimed=sum(RWA_PARTS.values()),
                    inputs_operational=inputs, tolerance=1e-9)
    assert r["status"] == "breach"
    assert r["recalculated"] == pytest.approx(0.725 * 30_000.0)


def test_rwa_total_without_floor_inputs_is_the_plain_sum():
    r = recalculate("rwa_final_total", claimed=sum(RWA_PARTS.values()),
                    inputs_operational=RWA_PARTS, tolerance=1e-9)
    assert r["status"] == "ok"


def test_rwa_total_rejects_a_half_specified_floor():
    with pytest.raises(RecalcError):
        recalculate("rwa_final_total", claimed=1.0,
                    inputs_operational={**RWA_PARTS, "floor_factor": 0.725})


def test_rwa_total_detects_a_dropped_component():
    """구조화(펀드·유동화)를 분모에서 빠뜨린 주장값은 걸려야 한다."""
    claimed_without_structured = (sum(RWA_PARTS.values())
                                  - RWA_PARTS["fund_rwa"]
                                  - RWA_PARTS["securitisation_rwa"])
    r = recalculate("rwa_final_total", claimed=claimed_without_structured,
                    inputs_operational=RWA_PARTS, tolerance=1e-9)
    assert r["status"] == "breach"


# ---- 총자본비율

def test_total_ratio_sums_all_three_tiers():
    inputs = {"cet1_capital": 1_094.37, "at1_capital": 140.0,
              "tier2_capital": 240.0, "rwa": 13_478.63}
    expected = (1_094.37 + 140.0 + 240.0) / 13_478.63
    r = recalculate("total_ratio", claimed=expected, inputs_operational=inputs,
                    tolerance=1e-12)
    assert r["status"] == "ok"


def test_total_ratio_detects_tier2_omission():
    inputs = {"cet1_capital": 1_094.37, "at1_capital": 140.0,
              "tier2_capital": 240.0, "rwa": 13_478.63}
    r = recalculate("total_ratio", claimed=(1_094.37 + 140.0) / 13_478.63,
                    inputs_operational=inputs, tolerance=1e-12)
    assert r["status"] == "breach"


# ---- ECL 합계

def test_ecl_total_is_the_stage_sum():
    inputs = {"ecl_by_stage": {"1": 30.0, "2": 25.5, "3": 42.0}}
    r = recalculate("ecl_total", claimed=97.5, inputs_operational=inputs,
                    tolerance=1e-12)
    assert r["status"] == "ok"


def test_ecl_total_requires_all_three_stages():
    with pytest.raises(RecalcError):
        recalculate("ecl_total", claimed=1.0,
                    inputs_operational={"ecl_by_stage": {"1": 1.0, "2": 2.0}})


# ---- 대손준비금 소요액: 합계 기준 vs 건별 clip 합산

LINES = [
    {"min_provision": 100.0, "ifrs9_provision": 40.0},   # 부족 60
    {"min_provision": 50.0, "ifrs9_provision": 90.0},    # 초과 40
    {"min_provision": 20.0, "ifrs9_provision": 20.0},    # 일치
]


def test_reserve_shortfall_uses_the_aggregate_form():
    forms = reserve_shortfall_forms(LINES)
    assert forms["aggregate"] == pytest.approx(20.0)        # 170 − 150
    assert forms["per_line_clip_sum"] == pytest.approx(60.0)
    r = recalculate("reserve_shortfall", claimed=20.0,
                    inputs_operational={"lines": LINES}, tolerance=1e-12)
    assert r["status"] == "ok"


def test_reserve_shortfall_flags_the_per_line_clip_form_as_a_breach():
    """건별 부족분만 잘라 더한 값(60)을 주장하면 걸려야 한다 (규정 제29조 제2항은 합계 대비)."""
    r = recalculate("reserve_shortfall", claimed=60.0,
                    inputs_operational={"lines": LINES}, tolerance=1e-12)
    assert r["status"] == "breach"
    assert r["variance"] == pytest.approx(-40.0)


def test_reserve_shortfall_accepts_totals_directly_and_floors_at_zero():
    r = recalculate("reserve_shortfall", claimed=0.0,
                    inputs_operational={"min_provision_total": 100.0,
                                        "ifrs9_provision_total": 150.0},
                    tolerance=1e-12)
    assert r["status"] == "ok"
    assert r["recalculated"] == 0.0


def test_reserve_shortfall_rejects_empty_lines():
    with pytest.raises(RecalcError):
        reserve_shortfall_forms([])
