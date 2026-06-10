"""Round 25 — basel / liquidity / market / irrbb / macro / weights / operational
handler robustness. Round 24 가 credit 3 개를 다뤘다면, 본 라운드는 나머지
주요 handler 의 NaN / Inf / 0-분모 / 음수 / 빈 컨테이너 경계를 다룬다.

원칙 (CLAUDE.md HITL):
- 산식이 정의되지 않거나 silent OK 로 통과하는 입력은 fail (자동 escalation)
  이 아니라 skipped 로 처리해 인간 검증자에게 입력 재확인 요청한다.
"""

from __future__ import annotations


import pandas as pd

from tools.handlers import (
    capital_handler,
    irrbb_handler,
    liquidity_handler,
    macro_handler,
    market_handler,
    operational_handler,
    scenario_weights_handler,
)
from tools.workflow import WorkflowContext


def _ctx(req):
    return WorkflowContext(req)


# ---------- capital_handler ----------

def test_capital_skips_when_cet1_nan():
    req = {"capital_cet1": float("nan"), "capital_leverage": 0.05}
    r = capital_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "capital_cet1" in r.outputs["bad_fields"]


def test_capital_skips_when_leverage_inf():
    req = {"capital_cet1": 0.13, "capital_leverage": float("inf")}
    r = capital_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "capital_leverage" in r.outputs["bad_fields"]


def test_capital_healthy_still_passes():
    """회귀 방지 — 정상 입력은 ok."""
    req = {
        "capital_cet1": 0.13, "capital_tier1": 0.14,
        "capital_total": 0.16, "capital_leverage": 0.05,
    }
    r = capital_handler(req, _ctx(req))
    assert r.status == "ok"


# ---------- liquidity_handler ----------

def test_liquidity_skips_when_outflow_zero():
    """outflow=0 은 LCR 분모 = 0. 기존 truthy 체크는 이를 '미제공' 으로 잘못 분류."""
    req = {"liquidity_hqla": 100.0, "liquidity_outflow": 0.0}
    r = liquidity_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "분모" in r.detail


def test_liquidity_skips_when_hqla_nan():
    req = {"liquidity_hqla": float("nan"), "liquidity_outflow": 100.0}
    r = liquidity_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "NaN/Inf" in r.detail


def test_liquidity_skips_when_rsf_zero():
    req = {"liquidity_asf": 1000.0, "liquidity_rsf": 0.0}
    r = liquidity_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "rsf=0" in r.detail or "분모" in r.detail


def test_liquidity_healthy_still_runs():
    req = {"liquidity_hqla": 120.0, "liquidity_outflow": 100.0}
    r = liquidity_handler(req, _ctx(req))
    assert r.status in {"ok", "warning"}


# ---------- market_handler ----------

def test_market_skips_when_exceptions_negative():
    req = {"market_var_exceptions": -1}
    r = market_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "비정상" in r.detail


def test_market_skips_when_exceptions_nan():
    req = {"market_var_exceptions": float("nan")}
    r = market_handler(req, _ctx(req))
    assert r.status == "skipped"


def test_market_healthy_still_runs():
    req = {"market_var_exceptions": 2}
    r = market_handler(req, _ctx(req))
    assert r.status == "ok"


# ---------- irrbb_handler ----------

def test_irrbb_skips_when_tier1_zero():
    req = {
        "irrbb_delta_eve_by_scenario": {"parallel_up": -1000},
        "irrbb_tier1": 0,
    }
    r = irrbb_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "tier1" in r.detail.lower() or "분모" in r.detail


def test_irrbb_skips_when_eve_empty():
    req = {
        "irrbb_delta_eve_by_scenario": {},
        "irrbb_tier1": 1_000_000,
    }
    r = irrbb_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "비어" in r.detail


def test_irrbb_skips_when_eve_value_nan():
    req = {
        "irrbb_delta_eve_by_scenario": {"parallel_up": float("nan")},
        "irrbb_tier1": 1_000_000,
    }
    r = irrbb_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "NaN/Inf" in r.detail


# ---------- operational_handler ----------

def test_operational_skips_when_bi_negative():
    req = {"op_business_indicator_eur_bn": -1.0}
    r = operational_handler(req, _ctx(req))
    assert r.status == "skipped"


def test_operational_skips_when_bi_nan():
    """기존엔 silent BI=NaN → BIC=0 으로 통과해 자본 산식 오염 위험."""
    req = {"op_business_indicator_eur_bn": float("nan")}
    r = operational_handler(req, _ctx(req))
    assert r.status == "skipped"


def test_operational_healthy_still_runs():
    req = {"op_business_indicator_eur_bn": 5.0}
    r = operational_handler(req, _ctx(req))
    assert r.status == "ok"


# ---------- macro_handler ----------

def test_macro_skips_when_series_too_short():
    req = {"macro_series": [1.0, 2.0, 3.0]}  # 10 미만 → ADF 정의 불가
    r = macro_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "표본" in r.detail


def test_macro_skips_when_series_has_nan():
    req = {"macro_series": [1.0, 2.0, float("nan")] + [3.0] * 12}
    r = macro_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "NaN/Inf" in r.detail


def test_macro_skips_when_series_has_inf():
    req = {"macro_series": [1.0, 2.0, float("inf")] + [3.0] * 12}
    r = macro_handler(req, _ctx(req))
    assert r.status == "skipped"


# ---------- scenario_weights_handler ----------

def test_weights_skips_when_panel_empty():
    req = {"scenario_weight_panel": pd.DataFrame()}
    r = scenario_weights_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "비어" in r.detail


def test_weights_skips_when_column_missing():
    req = {"scenario_weight_panel": pd.DataFrame({"period": ["2025Q1"]})}
    r = scenario_weights_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "컬럼 누락" in r.detail


# ---------- _bad_scalar helper ----------

def test_bad_scalar_helper():
    from tools.handlers import _bad_scalar

    assert _bad_scalar(float("nan")) is True
    assert _bad_scalar(float("inf")) is True
    assert _bad_scalar(float("-inf")) is True
    assert _bad_scalar(None) is True
    assert _bad_scalar("abc") is True  # not coercible
    assert _bad_scalar(0.0) is False
    assert _bad_scalar(1.0, 2.0, 3.0) is False
    assert _bad_scalar(1.0, float("nan")) is True  # any
