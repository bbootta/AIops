"""Trader specialist agent — order execution with slippage minimization."""

import json
import anthropic
from anthropic import beta_tool
from stock_trading import tools

_client = anthropic.Anthropic()

_SYSTEM = """\
You are a senior execution trader at a quantitative hedge fund. Your role is to execute \
approved orders with minimal market impact and slippage.

You only execute trades that have been explicitly approved by both the Risk Manager \
and Portfolio Manager. Never execute a trade that lacks prior approval.

Always:
- Confirm the current price before executing
- Report the exact execution price, slippage in basis points, and total value
- Confirm the updated portfolio state after execution

Output format:
## Pre-Trade Check
[Current price, bid/ask context]

## Execution Report
Order ID | Symbol | Side | Shares | Exec Price | Slippage (bps) | Total Value | Status

## Post-Trade Portfolio
[Updated positions and cash balance]\
"""


@beta_tool
def get_current_price(symbol: str) -> str:
    """Get the live quote for a symbol before placing an order.

    Args:
        symbol: Stock ticker symbol.
    """
    return json.dumps(tools.get_price(symbol), indent=2)


@beta_tool
def execute_order(symbol: str, side: str, shares: int) -> str:
    """Execute a market order for the given symbol and quantity.

    Args:
        symbol: Stock ticker symbol.
        side: Order direction — 'buy' or 'sell'.
        shares: Number of shares to trade.
    """
    return json.dumps(tools.place_order(symbol, side, shares), indent=2)


@beta_tool
def get_post_trade_portfolio() -> str:
    """Get the current portfolio state after execution to confirm the trade settled correctly."""
    return json.dumps(tools.get_portfolio(), indent=2)


def execute(query: str) -> str:
    """Run the trader agent on the given query and return the execution report."""
    texts: list[str] = []
    for msg in _client.beta.messages.tool_runner(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[get_current_price, execute_order, get_post_trade_portfolio],
        messages=[{"role": "user", "content": query}],
    ):
        for block in msg.content:
            if block.type == "text" and block.text:
                texts.append(block.text)
    return "\n".join(texts) or "No execution report produced."
