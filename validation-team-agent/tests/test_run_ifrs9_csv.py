from pathlib import Path

import pandas as pd
import pytest

from tools.run_ifrs9_validation import _load_request_from_csv, main


def _write_csvs(tmp_path: Path) -> dict[str, Path]:
    weights = pd.DataFrame(
        {
            "period": ["P1", "P1", "P1", "P2", "P2", "P2"],
            "scenario": ["base", "adverse", "severe"] * 2,
            "weight": [0.5, 0.3, 0.2, 0.5, 0.3, 0.2],
        }
    )
    pd_long = pd.DataFrame(
        {
            "scenario": ["base", "base", "adverse", "adverse", "severe", "severe"],
            "pd": [0.01, 0.02, 0.015, 0.025, 0.025, 0.04],
        }
    )
    multipliers = pd.DataFrame(
        {
            "scenario": ["base", "base", "adverse", "adverse", "severe", "severe"],
            "multiplier": [1.0, 1.0, 1.5, 1.4, 2.5, 2.0],
        }
    )
    cal = pd.DataFrame(
        {
            "grade": ["A", "B"],
            "pd_estimated": [0.01, 0.05],
            "default_count": [12, 55],
            "exposure_count": [1000, 1000],
        }
    )
    paths = {
        "weights": tmp_path / "w.csv",
        "pd": tmp_path / "p.csv",
        "mul": tmp_path / "m.csv",
        "cal": tmp_path / "c.csv",
    }
    weights.to_csv(paths["weights"], index=False)
    pd_long.to_csv(paths["pd"], index=False)
    multipliers.to_csv(paths["mul"], index=False)
    cal.to_csv(paths["cal"], index=False)
    return paths


class _Args:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_load_request_from_csv_round_trip(tmp_path):
    paths = _write_csvs(tmp_path)
    args = _Args(
        title="t",
        weights_csv=str(paths["weights"]),
        pd_csv=str(paths["pd"]),
        multipliers_csv=str(paths["mul"]),
        calibration_csv=str(paths["cal"]),
        weight_period_col="period",
        weight_scenario_col="scenario",
        weight_value_col="weight",
    )
    req = _load_request_from_csv(args)
    assert set(req.pd_by_scenario) == {"base", "adverse", "severe"}
    assert set(req.pd_multipliers) == {"base", "adverse", "severe"}
    assert len(req.grade_calibration) == 2


def test_load_request_minimal(tmp_path):
    paths = _write_csvs(tmp_path)
    args = _Args(
        title="t",
        weights_csv=str(paths["weights"]),
        pd_csv=None,
        multipliers_csv=None,
        calibration_csv=None,
        weight_period_col="period",
        weight_scenario_col="scenario",
        weight_value_col="weight",
    )
    req = _load_request_from_csv(args)
    assert req.pd_by_scenario is None
    assert req.pd_multipliers is None
    assert req.grade_calibration is None


def test_main_with_weights_csv(tmp_path):
    paths = _write_csvs(tmp_path)
    out_path = tmp_path / "out.md"
    rc = main([
        "--weights-csv", str(paths["weights"]),
        "--out", str(out_path),
        "--title", "Test From CSV",
    ])
    assert rc == 0
    content = out_path.read_text(encoding="utf-8")
    assert "Test From CSV" in content
    assert "## 1. 요약" in content


def test_main_demo_and_csv_mutually_exclusive(tmp_path):
    paths = _write_csvs(tmp_path)
    with pytest.raises(SystemExit):
        main(["--demo", "--weights-csv", str(paths["weights"])])


def test_main_requires_weights_csv_or_demo():
    with pytest.raises(SystemExit):
        main([])
