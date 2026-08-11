"""Round 45 — CVA / Market backtest / Op scenario / Macroprudential overlay."""

from __future__ import annotations

import pytest


# ---------- sample generators ----------

def test_market_var_pnl_panel_deterministic():
    from tools.sample_generators import market_var_pnl_panel

    a = market_var_pnl_panel(seed=41)
    b = market_var_pnl_panel(seed=41)
    assert a == b
    assert len(a) == 250
    assert all(set(r) == {"day", "pnl", "var_99", "exception"} for r in a)


def test_market_var_panel_marks_exceptions():
    from tools.sample_generators import market_var_pnl_panel

    p = market_var_pnl_panel()
    # 최소 1건은 예외 (stress idx 주입)
    assert any(r["exception"] for r in p)
    # exception 일자는 pnl < var_99
    for r in p:
        if r["exception"]:
            assert r["pnl"] < r["var_99"]


def test_op_loss_scenarios_covers_basel_event_classes():
    from tools.sample_generators import operational_loss_scenarios

    s = operational_loss_scenarios()
    classes = {x["basel_event_class"] for x in s}
    # 7개 BCBS event class 중 최소 5개 cover (모든 7개 enforce 는 과적합)
    expected = {
        "Internal Fraud", "External Fraud", "Business Disruption",
        "Damage to Physical Assets",
        "Clients/Products & Business Practices",
        "Execution, Delivery & Process Management",
    }
    assert len(classes & expected) >= 5


def test_op_scenarios_have_99_severity():
    from tools.sample_generators import operational_loss_scenarios

    for s in operational_loss_scenarios():
        # 99% 손실 > mean
        assert s["severity_99_bn"] > s["severity_mean_bn"]


def test_macroprudential_overlay_has_ccyb_dsr_ltv():
    from tools.sample_generators import macroprudential_overlay

    m = macroprudential_overlay()
    for key in ("ccyb_required_pct", "dti_household_ratio",
                "ltv_residential_avg", "syrb_required_pct"):
        assert key in m
    # 정책 출처가 명시되어 있음
    assert m["framework_versions"]["ccyb"]
    assert m["framework_versions"]["ltv_dsr"]


# ---------- pack ----------

@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r45")
    demo = run_demo(2_000, True, 42, out / "logs")
    request = build_request(2_000, stress=True, seed=42)
    prov = build_provenance(request, n=2_000, seed=42, stress=True)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_four_new_pages_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    for new_page in ("cva_deep.html", "market_backtest_deep.html",
                     "op_scenario_deep.html", "macro_overlay.html"):
        assert new_page in names


def test_cva_deep_shows_ba_sa_thresholds(pack):
    out, _ = pack
    text = (out / "cva_deep.html").read_text(encoding="utf-8")
    assert "BA-CVA" in text
    assert "SA-CVA" in text
    assert "MAR50" in text
    assert "Wrong-Way Risk" in text


def test_cva_deep_shows_top_counterparties(pack):
    out, _ = pack
    text = (out / "cva_deep.html").read_text(encoding="utf-8")
    assert "Top " in text
    assert "CP0" in text  # cva_counterparty_sample 의 이름 prefix


def test_market_backtest_deep_shows_traffic_light(pack):
    out, _ = pack
    text = (out / "market_backtest_deep.html").read_text(encoding="utf-8")
    for label in ("MAR99", "green", "yellow", "red", "예외 일자"):
        assert label in text


def test_market_backtest_lists_exception_days(pack):
    out, _ = pack
    text = (out / "market_backtest_deep.html").read_text(encoding="utf-8")
    # 예외 일자 표 — D+숫자 형태가 등장 (panel 에 stress 일자 주입)
    assert "D+" in text


def test_op_scenario_deep_lists_basel_classes(pack):
    out, _ = pack
    text = (out / "op_scenario_deep.html").read_text(encoding="utf-8")
    for cls in ("Internal Fraud", "External Fraud", "Business Disruption"):
        assert cls in text
    assert "ILM" in text and "ILDC" in text


def test_macro_overlay_shows_required_indicators(pack):
    out, _ = pack
    text = (out / "macro_overlay.html").read_text(encoding="utf-8")
    for key in ("CCyB", "SyRB", "DSR", "LTV"):
        assert key in text
    assert "BCBS" in text and "시행세칙" in text


def test_all_new_pages_self_contained_and_draft(pack):
    out, _ = pack
    for name in ("cva_deep.html", "market_backtest_deep.html",
                 "op_scenario_deep.html", "macro_overlay.html"):
        text = (out / name).read_text(encoding="utf-8")
        assert "https://" not in text
        assert "<script" not in text
        assert "[DRAFT" in text
        assert "Reproducibility" in text


def test_market_ops_links_to_new_deep_pages(pack):
    out, _ = pack
    text = (out / "market_ops.html").read_text(encoding="utf-8")
    assert 'href="market_backtest_deep.html"' in text
    assert 'href="cva_deep.html"' in text
    assert 'href="op_scenario_deep.html"' in text


def test_executive_links_to_macro_overlay(pack):
    out, _ = pack
    text = (out / "executive.html").read_text(encoding="utf-8")
    assert 'href="macro_overlay.html"' in text


def test_index_links_to_all_new(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    for name in ("market_backtest_deep.html", "op_scenario_deep.html",
                 "cva_deep.html", "macro_overlay.html"):
        assert f'href="{name}"' in idx
