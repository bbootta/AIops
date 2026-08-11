"""Same-seed determinism for runners and core metrics.

KS / AUROC / PSI 같은 결정론적 함수와 thin runner의 산출물이 동일 입력으로
두 번 실행 시 동일해야 한다. 시간 stamp 같은 비결정 필드는 비교에서 제외.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from tools.metric_ks_auc import calculate_auc_gini, calculate_ks
from tools.metric_psi import calculate_psi
from tools.run_validation import _build_demo_request, run


def _strip_volatile(md: str) -> str:
    """보고서에서 시간/run_id 등 비결정 필드를 제거한다."""
    md = re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", "<TS>", md)
    md = re.sub(r"duration_sec\s*[:=]\s*[0-9.]+", "duration_sec=<DUR>", md)
    return md


def test_metrics_are_deterministic():
    rng = np.random.default_rng(99)
    y = rng.integers(0, 2, size=500).astype(int)
    s = rng.normal(size=500) + y * 1.0
    a = calculate_ks(y, s)
    b = calculate_ks(y, s)
    assert a == b
    assert calculate_auc_gini(y, s) == calculate_auc_gini(y, s)
    e = rng.normal(size=2000)
    out1 = calculate_psi(e, e + 0.5, bins=10)
    out2 = calculate_psi(e, e + 0.5, bins=10)
    assert out1["psi"] == out2["psi"]
    assert out1["expected_pct"] == out2["expected_pct"]


def test_run_validation_is_deterministic(tmp_path):
    req1 = _build_demo_request()
    req2 = _build_demo_request()
    pd.testing.assert_frame_equal(req1.df, req2.df)

    out1 = run(req1, log_dir=tmp_path / "a")
    out2 = run(req2, log_dir=tmp_path / "b")
    assert _strip_volatile(out1["report_md"]) == _strip_volatile(out2["report_md"])
    assert out1["quant"]["ks"] == out2["quant"]["ks"]
    assert out1["quant"]["auc_gini"] == out2["quant"]["auc_gini"]
    if out1["quant"].get("calibration") is not None:
        pd.testing.assert_frame_equal(out1["quant"]["calibration"], out2["quant"]["calibration"])
