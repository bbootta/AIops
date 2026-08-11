import numpy as np
import pandas as pd

from tools.run_macro_validation import MacroValidationRequest, _build_demo_request, run


def test_demo_macro_run_completes_with_full_report(tmp_path):
    req = _build_demo_request()
    out = run(req, log_dir=tmp_path)
    md = out["report_md"]
    assert "## 1. 요약" in md
    assert "## 10. 감사추적 및 변경 이력" in md
    assert out["completeness"]["passed"] is True
    assert out["citations"]["passed"] is True


def test_macro_diagnostics_contains_expected_keys(tmp_path):
    req = _build_demo_request()
    out = run(req, log_dir=tmp_path)
    diag = out["diagnostics"]
    assert "series" in diag
    for col in (req.target_col, *req.feature_cols):
        assert col in diag["series"]
        assert "label" in diag["series"][col]


def test_macro_handles_short_series(tmp_path):
    df = pd.DataFrame(
        {
            "target_macro": np.linspace(0, 1, 5),
            "gdp_growth": np.linspace(0, 1, 5),
            "unemployment": np.linspace(4, 5, 5),
        }
    )
    req = MacroValidationRequest(
        title="Tiny",
        df=df,
        target_col="target_macro",
        feature_cols=["gdp_growth", "unemployment"],
    )
    out = run(req, log_dir=tmp_path)
    assert out["diagnostics"]["series"]["target_macro"]["label"] == "too_short"
