"""Round 84 — 독립 재계산 + 차이 원인 분해 (VAL-007/008)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools.independent_recalc import (
    ATTRIBUTION_KINDS,
    RECALCULATORS,
    RecalcError,
    decompose,
    recalculate,
    render,
    to_finding,
)

ROOT = Path(__file__).resolve().parent.parent


# ---------- 독립성 (핵심) ----------

def test_recalculators_do_not_import_domain_modules():
    """같은 코드를 다시 부르면 재계산이 아니라 동어반복이다."""
    src = (ROOT / "tools" / "independent_recalc.py").read_text(encoding="utf-8")
    forbidden = ("vta.domains", "vta.handlers", "tools.risk_checks",
                 "tools.handlers", "run_workflow_demo")
    for mod in forbidden:
        assert mod not in src, f"독립 계산기가 {mod} 를 참조한다"


def test_recalculators_are_pure_functions():
    """계산기는 입력만으로 결과를 낸다 (외부 상태·파일 접근 없음)."""
    for name, (fn, desc, ref) in RECALCULATORS.items():
        assert desc.strip() and ref.strip(), name
        assert fn.__module__ == "tools.independent_recalc"


def test_registry_covers_expected_targets():
    assert {"lcr", "nsfr", "cet1_ratio", "leverage_ratio", "icaap_ratio",
            "portfolio_default_rate"} <= set(RECALCULATORS)


# ---------- 계산 정확성 ----------

@pytest.mark.parametrize("target,inputs,expected", [
    ("lcr", {"hqla": 130.0, "net_outflow": 100.0}, 1.30),
    ("nsfr", {"available_stable_funding": 110.0,
              "required_stable_funding": 100.0}, 1.10),
    ("cet1_ratio", {"cet1_capital": 13.5, "rwa": 100.0}, 0.135),
    ("leverage_ratio", {"tier1_capital": 4.9, "total_exposure": 100.0}, 0.049),
    ("portfolio_default_rate", {"default_count": 25.0,
                                "obligor_count": 1000.0}, 0.025),
])
def test_recalculation_values(target, inputs, expected):
    r = recalculate(target, claimed=expected, inputs_operational=inputs,
                    tolerance=1e-9)
    assert r["recalculated"] == pytest.approx(expected)
    assert r["status"] == "ok"


def test_icaap_applies_diversification_benefit():
    r = recalculate("icaap_ratio", claimed=1.0,
                    inputs_operational={"available_capital": 110.0,
                                        "required_gross": 100.0,
                                        "diversification_benefit": 0.2},
                    tolerance=1e-9)
    assert r["recalculated"] == pytest.approx(110.0 / 80.0)


# ---------- 입력 검증 ----------

def test_zero_denominator_rejected():
    with pytest.raises(RecalcError, match="분모가 0"):
        recalculate("lcr", claimed=1.0,
                    inputs_operational={"hqla": 100.0, "net_outflow": 0.0})


def test_missing_input_rejected():
    with pytest.raises(RecalcError, match="필수 입력 누락"):
        recalculate("lcr", claimed=1.0, inputs_operational={"hqla": 100.0})


def test_non_numeric_and_bool_rejected():
    with pytest.raises(RecalcError, match="수치가 아니다"):
        recalculate("lcr", claimed=1.0,
                    inputs_operational={"hqla": "많음", "net_outflow": 100.0})
    with pytest.raises(RecalcError, match="수치가 아니다"):
        recalculate("lcr", claimed=1.0,
                    inputs_operational={"hqla": True, "net_outflow": 100.0})


def test_contradictory_default_counts_rejected():
    with pytest.raises(RecalcError, match="입력 모순"):
        recalculate("portfolio_default_rate", claimed=0.1,
                    inputs_operational={"default_count": 50.0,
                                        "obligor_count": 10.0})


def test_out_of_range_diversification_rejected():
    with pytest.raises(RecalcError, match="범위 밖"):
        recalculate("icaap_ratio", claimed=1.0,
                    inputs_operational={"available_capital": 100.0,
                                        "required_gross": 100.0,
                                        "diversification_benefit": 1.5})


def test_unknown_target_rejected():
    with pytest.raises(RecalcError, match="등록되지 않은"):
        recalculate("frtb_ima", claimed=1.0, inputs_operational={})


# ---------- 허용오차 대조 ----------

def test_within_tolerance_is_ok():
    r = recalculate("lcr", claimed=1.3005,
                    inputs_operational={"hqla": 130.0, "net_outflow": 100.0},
                    tolerance=0.001)
    assert r["status"] == "ok"


def test_boundary_variance_equals_tolerance_is_ok():
    r = recalculate("lcr", claimed=1.29,
                    inputs_operational={"hqla": 130.0, "net_outflow": 100.0},
                    tolerance=0.01)
    assert r["variance"] == pytest.approx(0.01)
    assert r["status"] == "ok"


def test_beyond_tolerance_is_breach():
    r = recalculate("lcr", claimed=1.25,
                    inputs_operational={"hqla": 130.0, "net_outflow": 100.0},
                    tolerance=0.01)
    assert r["status"] == "breach"


# ---------- 차이 원인 분해 (VAL-008) ----------

def test_components_reconcile_to_total():
    """수용기준: 원인별 기여도의 합이 총 차이와 대사된다."""
    r = recalculate(
        "lcr", claimed=1.30,
        inputs_operational={"hqla": 126.0, "net_outflow": 100.0},
        inputs_validation={"hqla": 126.0, "net_outflow": 105.0},
        tolerance=0.01)
    a = r["attribution"]
    assert a["reconciled"]
    assert sum(c["contribution"] for c in a["components"]) == pytest.approx(
        a["total_variance"])
    assert a["total_variance"] == pytest.approx(r["variance"])


def test_data_contribution_isolated():
    """산식이 같고 입력만 다르면 전부 데이터 기여."""
    r = recalculate(
        "lcr", claimed=1.30,
        inputs_operational={"hqla": 130.0, "net_outflow": 100.0},
        inputs_validation={"hqla": 120.0, "net_outflow": 100.0},
        tolerance=0.0)
    comps = {c["kind"]: c["contribution"] for c in r["attribution"]["components"]}
    assert comps["data"] == pytest.approx(-0.10)
    assert comps["implementation"] == pytest.approx(0.0)


def test_implementation_contribution_isolated():
    """입력이 같은데 주장값이 다르면 구현 기여."""
    r = recalculate("lcr", claimed=1.40,
                    inputs_operational={"hqla": 130.0, "net_outflow": 100.0},
                    tolerance=0.0)
    comps = {c["kind"]: c["contribution"] for c in r["attribution"]["components"]}
    assert comps["implementation"] == pytest.approx(-0.10)
    assert comps["data"] == pytest.approx(0.0)


@pytest.mark.parametrize("meta,expected", [
    ({"model_version_operational": "m1", "model_version_validation": "m2"},
     "model"),
    ({"formula_version_operational": "f1", "formula_version_validation": "f2"},
     "formula"),
    ({}, "implementation"),
])
def test_non_data_attribution_by_metadata(meta, expected):
    r = recalculate("lcr", claimed=1.40,
                    inputs_operational={"hqla": 130.0, "net_outflow": 100.0},
                    tolerance=0.0, metadata=meta)
    kinds = {c["kind"] for c in r["attribution"]["components"]}
    assert expected in kinds


def test_model_version_takes_precedence_over_formula():
    r = recalculate("lcr", claimed=1.40,
                    inputs_operational={"hqla": 130.0, "net_outflow": 100.0},
                    tolerance=0.0,
                    metadata={"model_version_operational": "m1",
                              "model_version_validation": "m2",
                              "formula_version_operational": "f1",
                              "formula_version_validation": "f2"})
    kinds = {c["kind"] for c in r["attribution"]["components"]}
    assert "model" in kinds and "formula" not in kinds


def test_attribution_kinds_align_with_finding_root_causes():
    from tools.validation_finding import ROOT_CAUSES

    assert set(ATTRIBUTION_KINDS) <= set(ROOT_CAUSES)


def test_decompose_direct():
    d = decompose(claimed=1.0, value_operational_inputs=1.1,
                  value_validation_inputs=1.3)
    assert d["total_variance"] == pytest.approx(0.3)
    assert d["reconciled"]


# ---------- 독립 입력 사용 여부 표기 ----------

def test_flags_when_validation_inputs_absent():
    """운영 입력만 쓴 재계산은 입력을 검증하지 못했음을 드러내야 한다."""
    r = recalculate("lcr", claimed=1.3,
                    inputs_operational={"hqla": 130.0, "net_outflow": 100.0})
    assert r["independent_inputs_used"] is False
    assert "아니오" in render(r)


def test_flags_when_validation_inputs_present():
    r = recalculate("lcr", claimed=1.3,
                    inputs_operational={"hqla": 130.0, "net_outflow": 100.0},
                    inputs_validation={"hqla": 130.0, "net_outflow": 100.0})
    assert r["independent_inputs_used"] is True


# ---------- Finding 전환 (VAL-007 → VAL-013) ----------

def test_breach_converts_to_finding_kwargs():
    r = recalculate(
        "lcr", claimed=1.30,
        inputs_operational={"hqla": 130.0, "net_outflow": 100.0},
        inputs_validation={"hqla": 120.0, "net_outflow": 100.0},
        tolerance=0.01)
    kw = to_finding(r, domain="liquidity", owner_role="alm_owner")
    assert kw["root_cause"] == "data"
    assert kw["target"] == "lcr"
    assert "lcr" in kw["title"]

    from tools.validation_finding import ROOT_CAUSES, SEVERITY_ORDER

    assert kw["root_cause"] in ROOT_CAUSES
    assert kw["severity"] in SEVERITY_ORDER


def test_ok_result_is_not_converted():
    r = recalculate("lcr", claimed=1.30,
                    inputs_operational={"hqla": 130.0, "net_outflow": 100.0},
                    tolerance=0.01)
    with pytest.raises(RecalcError, match="전환하지 않는다"):
        to_finding(r, domain="liquidity", owner_role="alm_owner")


# ---------- 보고 / CLI ----------

def test_render_shows_reconciliation_and_hitl():
    r = recalculate("lcr", claimed=1.25,
                    inputs_operational={"hqla": 130.0, "net_outflow": 100.0},
                    tolerance=0.01)
    text = render(r)
    assert "합계 대사" in text and "PASS" in text
    assert "독립 검증자가 판단" in text
    assert re.search(r"차이 [+-]0\.05", text)


def test_cli_exit_codes():
    from tools.independent_recalc import main

    assert main(["run", "--target", "lcr", "--claimed", "1.3",
                 "--inputs", '{"hqla":130,"net_outflow":100}',
                 "--tolerance", "0.001"]) == 0
    assert main(["run", "--target", "lcr", "--claimed", "1.5",
                 "--inputs", '{"hqla":130,"net_outflow":100}',
                 "--tolerance", "0.001"]) == 1
    assert main(["run", "--target", "lcr", "--claimed", "1.5",
                 "--inputs", '{"hqla":130}', "--tolerance", "0.001"]) == 2


def test_cli_list():
    from tools.independent_recalc import main

    assert main(["list"]) == 0


def test_catalog_sync():
    from tools.cli_index import CLI_MODULES
    from vta.cli.__main__ import _DISPATCH

    assert "tools.independent_recalc" in {m for m, _ in CLI_MODULES}
    assert ("recalc",) in _DISPATCH
