"""Round 24 — handler robustness: 빈 df / NaN / Inf / 단일 클래스.

CLAUDE.md HITL 원칙: pathological input 은 fail(자동 escalation 발동) 이 아니라
skipped 로 처리해 인간 검증자가 입력 자체를 재확인하도록 한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tools.handlers import (
    credit_calibration_handler,
    credit_discrimination_handler,
    credit_psi_handler,
)
from tools.workflow import WorkflowContext


def _ctx(req):
    return WorkflowContext(req)


# ---------- credit_discrimination_handler ----------

def test_disc_skips_when_df_empty():
    df = pd.DataFrame({"score": [], "target": []})
    req = {"df": df, "score_col": "score", "target_col": "target"}
    r = credit_discrimination_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "비어" in r.detail


def test_disc_skips_when_score_nan():
    df = pd.DataFrame({"score": [np.nan] * 10, "target": [0, 1] * 5})
    req = {"df": df, "score_col": "score", "target_col": "target"}
    r = credit_discrimination_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "NaN" in r.detail


def test_disc_skips_when_score_inf():
    df = pd.DataFrame({
        "score": [np.inf] * 50 + [-np.inf] * 50,
        "target": [0, 1] * 50,
    })
    req = {"df": df, "score_col": "score", "target_col": "target"}
    r = credit_discrimination_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "Inf" in r.detail


def test_disc_skips_when_single_class():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"score": rng.random(100), "target": [0] * 100})
    req = {"df": df, "score_col": "score", "target_col": "target"}
    r = credit_discrimination_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "단일 클래스" in r.detail


def test_disc_skips_when_target_not_binary():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"score": rng.random(100), "target": [2] * 50 + [3] * 50})
    req = {"df": df, "score_col": "score", "target_col": "target"}
    r = credit_discrimination_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "binary" in r.detail


def test_disc_skips_when_columns_missing():
    df = pd.DataFrame({"a": [1, 2, 3]})
    req = {"df": df, "score_col": "score", "target_col": "target"}
    r = credit_discrimination_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "컬럼" in r.detail


def test_disc_still_runs_on_healthy_input():
    """healthy input 에선 robustness 가드가 정상 경로를 막지 않는다 — 회귀 방지."""
    rng = np.random.default_rng(42)
    n = 500
    target = rng.integers(0, 2, n)
    score = target * 0.6 + rng.normal(0, 0.4, n)
    df = pd.DataFrame({"score": score, "target": target})
    req = {"df": df, "score_col": "score", "target_col": "target"}
    r = credit_discrimination_handler(req, _ctx(req))
    assert r.status in {"ok", "warning"}
    assert r.outputs["n"] == n


# ---------- credit_psi_handler ----------

def test_psi_skips_when_score_nan_in_dev():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "score": [np.nan] * 100 + list(rng.random(100)),
        "set": ["dev"] * 100 + ["oot"] * 100,
    })
    req = {"df": df, "score_col": "score", "set_col": "set"}
    r = credit_psi_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "NaN" in r.detail


def test_psi_skips_when_score_inf_in_oot():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "score": list(rng.random(100)) + [np.inf] * 100,
        "set": ["dev"] * 100 + ["oot"] * 100,
    })
    req = {"df": df, "score_col": "score", "set_col": "set"}
    r = credit_psi_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "Inf" in r.detail


def test_psi_skips_when_columns_missing():
    df = pd.DataFrame({"a": [1, 2, 3]})
    req = {"df": df, "score_col": "score", "set_col": "set"}
    r = credit_psi_handler(req, _ctx(req))
    assert r.status == "skipped"


# ---------- credit_calibration_handler ----------

def test_cal_skips_when_df_empty():
    df = pd.DataFrame({"grade": [], "pd": [], "target": []})
    req = {
        "df": df, "grade_col": "grade", "pd_col": "pd", "target_col": "target",
    }
    r = credit_calibration_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "비어" in r.detail


def test_cal_skips_when_column_missing():
    df = pd.DataFrame({"grade": ["A"] * 10, "pd": [0.05] * 10})
    req = {
        "df": df, "grade_col": "grade", "pd_col": "pd", "target_col": "target",
    }
    r = credit_calibration_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "target" in r.detail


# ---------- workflow engine 통합: skipped 는 escalation 발동 안 함 ----------

def test_workflow_skips_disc_without_triggering_escalation(tmp_path):
    """빈 df 가 들어와도 escalation step 이 동적 추가되지 않아야 한다."""
    from tools.handlers import register_default_handlers
    from tools.workflow import WorkflowEngine

    eng = WorkflowEngine()
    register_default_handlers(eng)
    req = {
        "df": pd.DataFrame({"score": [], "target": [], "set": [],
                            "grade": [], "pd": [], "obs_date": [],
                            "customer_id": []}),
        "score_col": "score", "target_col": "target", "set_col": "set",
        "grade_col": "grade", "pd_col": "pd",
        "date_col": "obs_date", "key_cols": ["customer_id", "obs_date"],
        "feature_names": ["score"],
        # 자본 입력은 정상 → escalation 발동 안 함
        "capital_cet1": 0.13, "capital_tier1": 0.14,
        "capital_total": 0.16, "capital_leverage": 0.05,
    }
    run = eng.run(req, log_dir=tmp_path)
    disc = run.context.results.get("3.disc")
    assert disc is not None
    assert disc.status == "skipped"
    # escalation 이 발동되지 않았어야 한다 (3.disc fail 시 9.escalate 자동 삽입)
    assert "9.escalate" not in run.executed_order
