"""Tests for the PR #2 safety fixes: trader gate, DRY_RUN, lock, iter cap, news envelope."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from stock_trading import harness, tools
from stock_trading.agents import risk_manager


# ---------------------------------------------------------------------------
# CRITICAL-1: in-code trader approval gate
# ---------------------------------------------------------------------------

def test_instruct_trader_blocked_without_approvals():
    """instruct_trader must refuse to execute when consult_* approvals are missing."""
    consulted = {"analyst": False, "risk": False, "portfolio_manager": False}
    built = harness._build_tools(consulted, include_trader=True)
    # Last tool is instruct_trader (see _build_tools).
    instruct_trader = built[-1]

    # BetaFunctionTool is directly callable; delegates to the original function.
    result = instruct_trader(query="Execute a buy of 100 AAPL")

    assert "approvals_missing" in str(result)
    # Every key should be in the missing list — none were approved.
    for key in ("analyst", "risk", "portfolio_manager"):
        assert key in str(result)


# ---------------------------------------------------------------------------
# CRITICAL-2a: DRY_RUN is the default for place_order
# ---------------------------------------------------------------------------

def test_place_order_dry_run_default(monkeypatch):
    """Without STOCK_TRADING_LIVE=1, place_order must NOT mutate the portfolio."""
    monkeypatch.delenv("STOCK_TRADING_LIVE", raising=False)

    cash_before = tools._PORTFOLIO["cash"]
    orders_before = len(tools._ORDERS)

    result = tools.place_order("AAPL", "buy", 10)

    assert result["status"] == "DRY_RUN"
    assert "would_have" in result
    assert result["would_have"]["symbol"] == "AAPL"
    assert result["would_have"]["shares"] == 10
    # No state mutation should have happened.
    assert tools._PORTFOLIO["cash"] == cash_before
    assert len(tools._ORDERS) == orders_before


# ---------------------------------------------------------------------------
# CRITICAL-2b: _PORTFOLIO_LOCK serializes concurrent writes
# ---------------------------------------------------------------------------

def test_place_order_lock_serializes_concurrent_writes(monkeypatch):
    """10 concurrent buys must leave cash == initial - sum(total_value) and produce 10 unique orders."""
    monkeypatch.setenv("STOCK_TRADING_LIVE", "1")

    # Snapshot + reset state so the test is deterministic regardless of test order.
    original_portfolio = {
        "cash": tools._PORTFOLIO["cash"],
        "positions": {k: dict(v) for k, v in tools._PORTFOLIO["positions"].items()},
    }
    original_orders = list(tools._ORDERS)
    tools._PORTFOLIO["cash"] = 1_000_000.0
    tools._PORTFOLIO["positions"] = {}
    tools._ORDERS.clear()

    try:
        initial_cash = tools._PORTFOLIO["cash"]

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(tools.place_order, "AAPL", "buy", 1) for _ in range(10)]
            results = [f.result() for f in futures]

        # All 10 should have filled (we sized cash to be plenty).
        filled = [r for r in results if r.get("status") == "FILLED"]
        assert len(filled) == 10

        # Unique order IDs (no collisions from a racey len(_ORDERS)).
        ids = {r["order_id"] for r in filled}
        assert len(ids) == 10

        # Cash equation must hold exactly. If the read-modify-write were racey,
        # one writer's decrement would clobber another's and final cash would
        # be higher than expected.
        total_spent = sum(r["total_value"] for r in filled)
        assert tools._PORTFOLIO["cash"] == pytest.approx(initial_cash - total_spent)
    finally:
        tools._PORTFOLIO["cash"] = original_portfolio["cash"]
        tools._PORTFOLIO["positions"] = original_portfolio["positions"]
        tools._ORDERS[:] = original_orders


# ---------------------------------------------------------------------------
# HIGH-3: tool_runner iteration cap
# ---------------------------------------------------------------------------

def test_tool_runner_iteration_cap():
    """The agent's tool_runner loop must halt at MAX_ITERS even if the API yields forever."""

    def infinite_messages(*_args, **_kwargs):
        # Each yielded message has a single text block.
        text_block = SimpleNamespace(type="text", text="VERDICT: NEEDS_REVIEW\nthinking...")
        while True:
            yield SimpleNamespace(content=[text_block])

    with patch.object(
        risk_manager._client.beta.messages,
        "tool_runner",
        side_effect=infinite_messages,
    ):
        result = risk_manager.assess("Assess buying 100 AAPL")

    assert "iteration_cap_reached" in result
    assert str(risk_manager.MAX_ITERS) in result


# ---------------------------------------------------------------------------
# HIGH-4: news is wrapped in <untrusted_news_item> envelopes
# ---------------------------------------------------------------------------

def test_news_wrapped_in_untrusted_envelope():
    """Every returned headline must be wrapped in an <untrusted_news_item> tag."""
    result = tools.get_news("AAPL")

    assert result["symbol"] == "AAPL"
    assert result["headlines"], "expected at least one headline"
    for h in result["headlines"]:
        assert h.startswith("<untrusted_news_item")
        assert h.rstrip().endswith("</untrusted_news_item>")
        # The raw inner content should still be present.
        assert "Apple" in h or "AAPL" in h or "Analysts" in h

    # And the analyst tool's JSON output should also carry the wrappers
    # through to whatever the model sees.
    from stock_trading.agents.market_analyst import get_market_news
    as_json = get_market_news(symbol="AAPL")
    assert "<untrusted_news_item" in as_json
    # Should be valid JSON.
    parsed = json.loads(as_json)
    assert parsed["symbol"] == "AAPL"
