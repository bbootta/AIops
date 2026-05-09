import pandas as pd

from tools.run_validation import ValidationRequest, _build_demo_request, run


def test_scenario_weights_runs_when_panel_provided(tmp_path):
    req = _build_demo_request()
    req.scenario_weight_panel = pd.DataFrame(
        {
            "period": ["P1"] * 3,
            "scenario": ["base", "adverse", "severe"],
            "weight": [0.5, 0.3, 0.2],
        }
    )
    out = run(req, log_dir=tmp_path)
    sw = out["quant"]["scenario_weights"]
    assert sw is not None
    assert int((~sw["passed"]).sum()) == 0


def test_scenario_weights_omitted_by_default(tmp_path):
    req = _build_demo_request()
    out = run(req, log_dir=tmp_path)
    assert out["quant"]["scenario_weights"] is None


def test_scenario_weights_violation_surfaces_in_report(tmp_path):
    req = _build_demo_request()
    req.scenario_weight_panel = pd.DataFrame(
        {
            "period": ["P1"] * 3,
            "scenario": ["base", "adverse", "severe"],
            "weight": [0.5, 0.3, 0.5],  # sum = 1.3
        }
    )
    out = run(req, log_dir=tmp_path)
    assert "시나리오 가중치" in out["report_md"]
    assert "1건" in out["report_md"] or "위반 1건" in out["report_md"]
