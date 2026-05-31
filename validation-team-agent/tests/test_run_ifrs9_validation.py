import numpy as np
import pandas as pd

from tools.run_ifrs9_validation import IFRS9ValidationRequest, _build_demo_request, run


def test_demo_run_produces_full_report(tmp_path):
    req = _build_demo_request()
    out = run(req, log_dir=tmp_path)
    md = out["report_md"]
    assert "## 1. 요약" in md
    assert "## 10. 감사추적 및 변경 이력" in md
    assert out["completeness"]["passed"] is True
    assert out["citations"]["passed"] is True
    assert out["watermarks"]["passed"] is True


def test_demo_run_diagnoses_calibration_and_floors(tmp_path):
    req = _build_demo_request()
    out = run(req, log_dir=tmp_path)
    diag = out["diagnostics"]
    assert diag["calibration"] is not None
    assert "B" in set(diag["calibration"]["grade"])
    assert "severe" in diag["floors"]
    assert diag["scenario_order"]["passed"] is True


def test_weight_violation_surfaces_in_anomalies(tmp_path):
    panel = pd.DataFrame(
        {
            "period": ["P1"] * 3 + ["P2"] * 3,
            "scenario": ["base", "adverse", "severe"] * 2,
            "weight": [0.5, 0.3, 0.2, 0.4, 0.4, 0.4],  # P2 sums to 1.2
        }
    )
    req = IFRS9ValidationRequest(title="Bad weights", weight_panel=panel)
    out = run(req, log_dir=tmp_path)
    assert int((~out["diagnostics"]["weights"]["passed"]).sum()) >= 1
    assert "위반" in out["report_md"] or "violation" in out["report_md"]


def test_runs_without_optional_inputs(tmp_path):
    panel = pd.DataFrame(
        {
            "period": ["P1"] * 3,
            "scenario": ["base", "adverse", "severe"],
            "weight": [0.5, 0.3, 0.2],
        }
    )
    req = IFRS9ValidationRequest(title="Minimal", weight_panel=panel)
    out = run(req, log_dir=tmp_path)
    assert out["diagnostics"]["scenario_order"] is None
    assert out["diagnostics"]["floors"] is None
    assert out["diagnostics"]["calibration"] is None
