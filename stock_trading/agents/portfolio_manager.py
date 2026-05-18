"""Portfolio Manager specialist agent — allocation, diversification, and rebalancing."""

import json
import anthropic
from anthropic import beta_tool
from stock_trading import tools

_client = anthropic.Anthropic()

_SYSTEM = """\
You are a senior Portfolio Manager at a quantitative hedge fund. Your role is to evaluate \
whether proposed trades align with portfolio construction goals: diversification, \
sector balance, and long-term return objectives.

Always:
- Assess the trade's impact on overall portfolio composition
- Consider sector concentration and correlation risk
- Evaluate whether the trade improves or degrades the portfolio's risk-adjusted return profile
- Recommend position sizing adjustments if the proposed size is suboptimal

Output format:
## Current Portfolio State
[Allocation breakdown, sector exposure]

## Trade Impact Analysis
[How the trade changes concentration, diversification, expected return contribution]

## Portfolio Construction Verdict
PROCEED | ADJUST | DECLINE
[Recommendation with target size if adjustment needed]\
"""


@beta_tool
def get_portfolio_state() -> str:
    """Get current portfolio holdings, market values, and allocation percentages."""
    port = tools.get_portfolio()
    total = port["total_value"]
    if total > 0:
        for sym, pos in port["positions"].items():
            pos["allocation_pct"] = round(pos["market_value"] / total * 100, 2)
        port["cash_pct"] = round(port["cash"] / total * 100, 2)
    return json.dumps(port, indent=2)


@beta_tool
def analyze_trade_impact(symbol: str, shares: int, side: str) -> str:
    """Simulate the portfolio impact of executing a trade without placing the order.

    Args:
        symbol: Stock ticker symbol.
        shares: Number of shares to trade.
        side: Trade direction — 'buy' or 'sell'.
    """
    limits = tools.check_limits(symbol, shares, side)
    price_info = tools.get_price(symbol)
    return json.dumps({
        "trade": {"symbol": symbol, "shares": shares, "side": side},
        "current_price": price_info.get("price"),
        "trade_value": round(price_info.get("price", 0) * shares, 2),
        "limit_analysis": limits,
    }, indent=2)


def review(query: str) -> str:
    """Run the portfolio manager agent on the given query and return its review."""
    texts: list[str] = []
    for msg in _client.beta.messages.tool_runner(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[get_portfolio_state, analyze_trade_impact],
        messages=[{"role": "user", "content": query}],
    ):
        for block in msg.content:
            if block.type == "text" and block.text:
                texts.append(block.text)
    return "\n".join(texts) or "No portfolio review produced."
