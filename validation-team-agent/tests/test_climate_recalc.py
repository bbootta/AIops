"""기후리스크 합성 사례 독립 재계산 (CLR-18-02).

문서가 공표한 기대값 21건과 대조하고, 계약 위반(Stage 3·가중치 합·경계 PD·
범위 밖 비율)을 실제로 거부하는지 음성 통제로 고정한다.
"""

from __future__ import annotations

import copy
from fractions import Fraction

import pytest

from tools import climate_recalc as cr


def test_published_values_are_reproduced():
    rows = cr.compare(cr.run(cr.DEMO_FIXTURE), cr.PUBLISHED)
    assert len(rows) == 21
    bad = [r for r in rows if r["status"] == "breach"]
    assert not bad, bad


def test_reproducibility_same_fixture_same_result():
    assert cr.run(cr.DEMO_FIXTURE) == cr.run(copy.deepcopy(cr.DEMO_FIXTURE))


def test_stage_1_takes_only_the_first_year_and_stage_2_the_full_term():
    total2, rows = cr.ecl_term_structure([".1", ".2"], [1, 1], [100, 100], 0, 2)
    assert total2 == 28 and rows[1]["marginal_pd"] == Fraction("0.18")
    total1, _ = cr.ecl_term_structure([".1", ".2"], [1, 1], [100, 100], 0, 1)
    assert total1 == 10


def test_compound_damage_uses_sequential_survival_not_a_plain_sum():
    assert cr.compound_damage(100, [".2", ".1"]) == 28


def test_insurance_recovery_contract():
    assert cr.insurance_recovery("1500000000", "200000000", "800000000", "0.9") == Fraction(720_000_000)
    assert cr.insurance_recovery(100, 0, 100, 1, valid=False) == 0
    assert cr.insurance_recovery(1, 2, 9, 1) == 0


def test_expired_insurance_cascades_into_pd_and_ecl():
    """보험 무효 → 회수 0 → 잔여피해 15억 → PD·ECL 연쇄 변동 (문서 샘플 케이스)."""
    f = copy.deepcopy(cr.DEMO_FIXTURE)
    f["insurance_valid"] = False
    r = cr.run(f)
    base = cr.run(cr.DEMO_FIXTURE)
    assert r["amounts_krw"]["net_direct_damage"] == 1_500_000_000
    assert r["ratios"]["pd_stress"] > base["ratios"]["pd_stress"]
    assert r["amounts_krw"]["ecl_s2_weighted"] > base["amounts_krw"]["ecl_s2_weighted"]


def test_round_half_up_only_on_final_amounts():
    assert cr.round_half_up(Fraction(3, 2)) == 2
    assert cr.round_half_up(Fraction(-3, 2)) == -2
    exact = cr.run(cr.DEMO_FIXTURE)["amounts_exact"]["interruption_margin_loss"]
    assert "/" in exact, "중간값은 유리수 그대로 보존된다"


# ---- 음성 통제: 계약 위반은 거부돼야 한다

@pytest.mark.parametrize("call", [
    lambda: cr.ecl_term_structure([".1"], [".4"], [100], ".05", 3),        # STAGE3
    lambda: cr.ecl_term_structure([".1"], [".4", ".5"], [100], ".05", 2),  # TERM_SHAPE
    lambda: cr.ecl_term_structure([".1"], [".4"], [100], -1, 2),           # EIR
    lambda: cr.scenario_weighted([10, 20], [".7", ".2"]),                  # WEIGHT_SUM
    lambda: cr.pd_logit_shift(1, ".2", 2),                                 # PD boundary
    lambda: cr.pd_logit_shift(0, ".2", 2),
    lambda: cr.insurance_recovery(100, 0, 100, "1.0001"),                  # RATIO_RANGE
    lambda: cr.carbon_cost(-1, 0, 10, 0),                                  # AMOUNT_NEGATIVE
    lambda: cr.business_interruption(100, 400, 365, ".3"),                 # DAY_RANGE
    lambda: cr.compound_damage(100, []),
])
def test_contract_violations_are_rejected(call):
    with pytest.raises(cr.ClimateRecalcError):
        call()


def test_non_sample_profile_is_refused():
    f = copy.deepcopy(cr.DEMO_FIXTURE)
    f["classification"] = "PRODUCTION"
    with pytest.raises(cr.ClimateRecalcError, match="SAMPLE_PROFILE_ONLY"):
        cr.run(f)


def test_pd_shift_is_monotonic_in_the_ebitda_reduction():
    assert cr.pd_logit_shift(".01", ".3", 2) > cr.pd_logit_shift(".01", ".1", 2)


def test_compare_flags_a_tampered_claim():
    claimed = copy.deepcopy(cr.PUBLISHED)
    claimed["cet1_end"] += 1
    claimed["ratios"]["pd_stress"] = 0.02
    rows = cr.compare(cr.run(cr.DEMO_FIXTURE), claimed)
    bad = {r["key"] for r in rows if r["status"] == "breach"}
    assert bad == {"cet1_end", "pd_stress"}


def test_capital_bridge_does_not_subtract_lifetime_ecl():
    """충당금 비용은 별도 입력이다: ECL 합계를 넣어도 산식이 그것을 빼지 않는다."""
    assert cr.capital_bridge(1200, 80, 30, 20, -5) == 1225


def test_cli_self_test_passes_and_run_detects_breach(tmp_path, capsys):
    assert cr.main(["self-test"]) == 0
    import json
    claimed = copy.deepcopy(cr.PUBLISHED)
    claimed["net_direct_damage"] = 1
    p = tmp_path / "claimed.json"
    p.write_text(json.dumps(claimed), encoding="utf-8")
    assert cr.main(["run", "--claimed", str(p)]) == 1
    assert "불일치" in capsys.readouterr().out
