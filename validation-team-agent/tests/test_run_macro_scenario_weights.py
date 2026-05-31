import pandas as pd

from tools.run_macro_validation import _build_demo_request, run


def test_macro_scenario_weights_omitted_by_default(tmp_path):
    out = run(_build_demo_request(), log_dir=tmp_path)
    assert out["diagnostics"]["scenario_weights"] is None


def test_macro_scenario_weights_runs_when_panel_given(tmp_path):
    req = _build_demo_request()
    req.scenario_weight_panel = pd.DataFrame(
        {
            "period": ["P1"] * 3,
            "scenario": ["base", "adverse", "severe"],
            "weight": [0.5, 0.3, 0.2],
        }
    )
    out = run(req, log_dir=tmp_path)
    sw = out["diagnostics"]["scenario_weights"]
    assert sw is not None
    assert int((~sw["passed"]).sum()) == 0
    assert "시나리오 가중치" in out["report_md"]
