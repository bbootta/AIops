import json
from pathlib import Path

from tools.run_validation import _build_demo_request, run


def test_demo_run_produces_full_report(tmp_path):
    req = _build_demo_request()
    out = run(req, log_dir=tmp_path)
    md = out["report_md"]
    assert "## 1. 요약" in md
    assert "## 10. 감사추적 및 변경 이력" in md
    assert out["completeness"]["passed"] is True
    assert out["citations"]["passed"] is True


def test_demo_run_writes_jsonl_log(tmp_path):
    req = _build_demo_request()
    run(req, log_dir=tmp_path)
    log_path = Path(tmp_path) / "run.jsonl"
    assert log_path.exists()
    lines = [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    events = {l["event"] for l in lines}
    assert "start" in events
    assert "end" in events
    assert any(l["function"] == "run_validation.run" for l in lines)


def test_demo_run_records_sample_size_decision(tmp_path):
    req = _build_demo_request()
    out = run(req, log_dir=tmp_path)
    assert "sample_size" in out["quant"]
    assert isinstance(out["quant"]["sample_size"]["passed"], bool)


def test_calibration_runs_when_grade_and_pd_provided(tmp_path):
    import numpy as np
    import pandas as pd

    from tools.run_validation import ValidationRequest, run

    rng = np.random.default_rng(11)
    n = 1500
    grades = rng.choice(list("ABC"), size=n)
    pd_map = {"A": 0.01, "B": 0.05, "C": 0.10}
    pd_est = np.array([pd_map[g] for g in grades])
    target = (rng.uniform(size=n) < pd_est).astype(int)
    score = rng.normal(0, 1, n) + target * 1.5
    df = pd.DataFrame(
        {
            "score": score,
            "target": target,
            "grade": grades,
            "pd": pd_est,
            "set": ["dev"] * 1000 + ["oot"] * 500,
        }
    )
    req = ValidationRequest(
        title="Calibration Wired",
        df=df,
        score_col="score",
        target_col="target",
        grade_col="grade",
        pd_col="pd",
        set_col="set",
    )
    out = run(req, log_dir=tmp_path)
    cal = out["quant"]["calibration"]
    assert cal is not None
    assert set(cal["grade"]) == set("ABC")
    assert "등급별 캘리브레이션" in out["report_md"]
    assert out["completeness"]["passed"] is True
    assert out["citations"]["passed"] is True
