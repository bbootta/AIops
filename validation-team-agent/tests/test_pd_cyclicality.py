"""PD 설계 구분(TTC·PIT) 검증 도구 검사.

판정이 **실패할 수 있는지**를 함께 고정한다 (ADV-CALC-06). PIT 자료를 TTC 로
주장하는 표본을 넣었을 때 실제로 걸리지 않으면 이 통제는 통제가 아니다.
"""

from __future__ import annotations

import json
import math

import pytest

from tools import pd_cyclicality as pdc


@pytest.fixture(scope="module")
def th():
    return pdc.load_thresholds()


# ---- 단일요인 변환

def test_roundtrip_restores_the_original(th):
    tol = th["conversion"]["roundtrip_tolerance"]
    for pd_ in (0.0005, 0.01, 0.05, 0.2):
        for rho in (0.03, 0.15, 0.24):
            for z in (-2.5, -1.0, 0.0, 1.0, 2.5):
                r = pdc.roundtrip(pd_, rho, z, tol)
                assert r["passed"], (pd_, rho, z, r["diff"])


def test_phase_sign_holds_in_both_directions():
    ttc = 0.01
    down = pdc.ttc_to_pit(ttc, 0.15, -2.0)
    up = pdc.ttc_to_pit(ttc, 0.15, 2.0)
    assert down > ttc, "침체에서는 PIT 가 TTC 보다 커야 한다"
    assert up < ttc, "호황에서는 PIT 가 TTC 보다 작아야 한다"
    assert pdc.phase_sign(ttc, down, -2.0)["passed"]
    assert pdc.phase_sign(ttc, up, 2.0)["passed"]


def test_phase_sign_detects_a_reversed_relation():
    """부호가 뒤집힌 값을 넣으면 잡혀야 한다."""
    assert not pdc.phase_sign(0.01, 0.004, -2.0)["passed"]


def test_conversion_rejects_out_of_range_inputs():
    for bad in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError):
            pdc.ttc_to_pit(bad, 0.15, 0.0)
    with pytest.raises(ValueError):
        pdc.ttc_to_pit(0.01, 1.0, 0.0)


# ---- 분해

def test_decomposition_reconciles_with_the_total():
    panel = pdc.synthetic_panel("TTC", seed=7)
    d = pdc.mix_level_decomposition(panel["observations"])
    assert d["available"]
    assert d["reconciles"], "이동분 + 수준분 + 교차 가 총 변동과 대사되어야 한다"
    assert math.isclose(d["mix_effect"] + d["level_effect"] + d["interaction"],
                        d["total_delta"], abs_tol=1e-12)


def test_decomposition_needs_two_periods():
    obs = [{"period": "2020", "grade": "A", "predicted_pd": 0.01, "n": 100,
            "defaults": 1}]
    assert pdc.mix_level_decomposition(obs)["available"] is False


# ---- 설계 판정

def test_ttc_design_passes_as_ttc():
    res = pdc.classify(pdc.synthetic_panel("TTC", seed=42))
    assert res["verdict"] == "정합", res["findings"]


def test_pit_design_passes_as_pit():
    res = pdc.classify(pdc.synthetic_panel("PIT", seed=42))
    assert res["verdict"] == "정합", res["findings"]


def test_classify_rejects_an_unknown_design():
    panel = pdc.synthetic_panel("TTC")
    panel["claimed_design"] = "HYBRID"
    with pytest.raises(ValueError):
        pdc.classify(panel)


# ---- 음성 통제: 통제가 실패할 수 있는가

def test_pit_data_claimed_as_ttc_is_detected():
    """자료는 시점 조건부인데 TTC 라고 주장하면 잡혀야 한다."""
    res = pdc.classify(pdc.synthetic_panel("PIT", seed=42, mislabel=True))
    assert res["verdict"] == "불일치"
    joined = " ".join(res["findings"])
    assert "변동계수" in joined, "등급별 PD 가 움직이는 것을 잡아야 한다"
    assert "등급 이동으로 설명되지 않는다" in joined, "수준분 지배를 잡아야 한다"
    assert "거시변수와 유의하게 상관" in joined, "거시 반응을 잡아야 한다"


def test_short_observation_period_is_detected(th):
    """5년 미만 관측기간은 세칙 별표 3 인용값에 걸린다."""
    short = th["ttc"]["min_observation_years"] - 2
    res = pdc.classify(pdc.synthetic_panel("TTC", seed=42, years=short))
    assert res["verdict"] == "불일치"
    assert any("관측기간" in f for f in res["findings"])


def test_flat_prediction_claimed_as_pit_is_detected():
    """예측 PD 가 시점에 반응하지 않는데 PIT 라고 주장하면 잡혀야 한다."""
    panel = pdc.synthetic_panel("TTC", seed=42)
    panel["claimed_design"] = "PIT"
    res = pdc.classify(panel)
    assert res["verdict"] == "불일치"
    assert any("추종" in f or "평균절대편차" in f for f in res["findings"])


# ---- 임계 SSoT

def test_thresholds_are_declared_not_hardcoded(th):
    for key in ("min_observation_years", "grade_pd_cv_max",
                "macro_correlation_abs_max", "mix_effect_share_min"):
        assert key in th["ttc"], key
    for key in ("tracking_correlation_min", "tracking_mad_max",
                "direction_agreement_min"):
        assert key in th["pit"], key
    assert th["ttc"]["min_observation_years"] == 5, "세칙 별표 3 인용값"


def test_observation_period_threshold_is_cross_checked_against_the_source():
    """관측기간 5년은 규제 임계 대조 대상에 등재돼 있어야 한다."""
    from tools import regulatory_criteria as rc
    cat = rc.load()
    hit = [t for t in cat["thresholds"] if t["key"] == "pd_min_observation_years"]
    assert hit, "임계 원장에 등재되어야 원문 대조를 받는다"
    t = hit[0]
    assert t["source_key"] == "세칙"
    assert t["harness_file"] == "harness/pd_design_thresholds.json"
    assert t["status"] == "ok"


def test_report_runs_without_error(capsys):
    res = pdc.classify(pdc.synthetic_panel("TTC", seed=1))
    pdc._print_report(res)
    out = capsys.readouterr().out
    assert "PD 설계 판정" in out
    assert "평균 PD 변동 분해" in out


def test_analyse_cli_returns_nonzero_on_mismatch(tmp_path):
    panel = pdc.synthetic_panel("PIT", seed=42, mislabel=True)
    f = tmp_path / "panel.json"
    f.write_text(json.dumps(panel, ensure_ascii=False), encoding="utf-8")
    assert pdc.main(["analyse", "--panel", str(f), "--json"]) == 1
