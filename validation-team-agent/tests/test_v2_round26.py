"""Round 26 — CCR / CVA handler robustness.

Round 24/25 가 credit + 7 개 부문 handler 의 NaN/Inf/0-분모/empty 를 다뤘다.
본 라운드는 CCR (CRE52 SA-CCR) 과 CVA (MAR50) 두 handler 의 동일 패턴을
다룬다 — CCR 는 silent NaN/Inf EAD 가 자본 산식 직접 오염하는 가장 치명적
실패 경로다.
"""

from __future__ import annotations

import pytest

from tools.handlers import ccr_handler, cva_handler
from tools.workflow import WorkflowContext


def _ctx(req):
    return WorkflowContext(req)


# ---------- ccr_handler ----------

def test_ccr_skips_when_rc_nan():
    """기존엔 EAD=nan 으로 ok 통과 — 자본 산식 NaN 오염."""
    req = {"ccr_rc": float("nan"), "ccr_pfe": 10.0}
    r = ccr_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "NaN/Inf" in r.detail


def test_ccr_skips_when_pfe_nan():
    req = {"ccr_rc": 5.0, "ccr_pfe": float("nan")}
    r = ccr_handler(req, _ctx(req))
    assert r.status == "skipped"


def test_ccr_skips_when_rc_inf():
    """기존엔 EAD=inf 로 ok 통과."""
    req = {"ccr_rc": float("inf"), "ccr_pfe": 5.0}
    r = ccr_handler(req, _ctx(req))
    assert r.status == "skipped"


def test_ccr_skips_when_rc_negative():
    req = {"ccr_rc": -5.0, "ccr_pfe": 10.0}
    r = ccr_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "음수" in r.detail


def test_ccr_skips_when_pfe_negative():
    req = {"ccr_rc": 5.0, "ccr_pfe": -1.0}
    r = ccr_handler(req, _ctx(req))
    assert r.status == "skipped"


def test_ccr_healthy_still_runs():
    """회귀 방지."""
    req = {"ccr_rc": 5.0, "ccr_pfe": 10.0}
    r = ccr_handler(req, _ctx(req))
    assert r.status == "ok"
    assert r.outputs["ead"] > 0


# ---------- cva_handler ----------

def test_cva_skips_when_book_nan():
    """기존엔 book=NaN 으로 SA-CVA required=False 잘못 분류."""
    req = {"cva_counterparty_inputs": None,
           "cva_trading_book_size_eur_bn": float("nan")}
    r = cva_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "book_size" in r.detail


def test_cva_skips_when_book_inf():
    req = {"cva_counterparty_inputs": None,
           "cva_trading_book_size_eur_bn": float("inf")}
    r = cva_handler(req, _ctx(req))
    assert r.status == "skipped"


def test_cva_skips_when_book_negative():
    req = {"cva_counterparty_inputs": None,
           "cva_trading_book_size_eur_bn": -10.0}
    r = cva_handler(req, _ctx(req))
    assert r.status == "skipped"


def test_cva_skips_when_inputs_empty():
    req = {"cva_counterparty_inputs": [],
           "cva_trading_book_size_eur_bn": 50.0}
    r = cva_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "비어" in r.detail


def test_cva_skips_when_required_key_missing():
    """scva 누락 → 기존 KeyError CRASH → 엔진 fail → 자동 escalation."""
    req = {
        "cva_counterparty_inputs": [{"name": "CP000"}],  # scva 없음
        "cva_trading_book_size_eur_bn": 50.0,
    }
    r = cva_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "scva" in r.detail


def test_cva_skips_when_scva_nan():
    req = {
        "cva_counterparty_inputs": [{"name": "CP", "scva": float("nan")}],
        "cva_trading_book_size_eur_bn": 50.0,
    }
    r = cva_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "NaN/Inf" in r.detail


def test_cva_skips_when_scva_negative():
    req = {
        "cva_counterparty_inputs": [{"name": "CP", "scva": -1.0}],
        "cva_trading_book_size_eur_bn": 50.0,
    }
    r = cva_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "음수" in r.detail


def test_cva_skips_when_counterparty_not_dict():
    req = {
        "cva_counterparty_inputs": ["not a dict"],
        "cva_trading_book_size_eur_bn": 50.0,
    }
    r = cva_handler(req, _ctx(req))
    assert r.status == "skipped"
    assert "dict" in r.detail


def test_cva_healthy_book_only_runs():
    """회귀 방지 — inputs 없이 book 만 정상이면 ok."""
    req = {"cva_counterparty_inputs": None,
           "cva_trading_book_size_eur_bn": 30.0}
    r = cva_handler(req, _ctx(req))
    assert r.status == "ok"
    assert "sa_cva_required" in r.outputs
