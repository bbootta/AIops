"""Risk Manager specialist agent — VaR, position limits, and risk assessment."""

import json
import anthropic
from anthropic import beta_tool
from stock_trading import tools

_client = anthropic.Anthropic()

_SYSTEM = """\
You are the Chief Risk Officer at a quantitative hedge fund. Your role is to evaluate \
proposed trades against risk limits and portfolio constraints.

Risk limits you enforce:
- Maximum single-stock position: 20% of total portfolio value
- Minimum cash reserve: 10% of total portfolio value
- No trade proceeds if VaR (95%, 1-day) exceeds 3% of total portfolio value

Always:
- Calculate actual VaR for the proposed position size
- Check all position and cash limits
- Provide a clear APPROVED / REJECTED / CONDITIONAL verdict

Output format:
## Risk Metrics
[VaR, position sizing, volatility]

## Limit Check
[Each limit with pass/fail status]

## Verdict
APPROVED | REJECTED | CONDITIONAL
[Reason and any conditions or suggested adjustments]\
"""


@beta_tool
def calculate_var(symbol: str, shares: int) -> str:
    """Calculate Value at Risk for a given position.

    Args:
        symbol: Stock ticker symbol.
        shares: Number of shares in the position.
    """
    return json.dumps(tools.compute_var(symbol, shares), indent=2)


@beta_tool
def check_position_limits(symbol: str, shares: int, side: str) -> str:
    """Check if a trade would breach position concentration or cash reserve limits.

    Args:
        symbol: Stock ticker symbol.
        shares: Number of shares to trade.
        side: Trade direction — 'buy' or 'sell'.
    """
    return json.dumps(tools.check_limits(symbol, shares, side), indent=2)


@beta_tool
def get_portfolio_snapshot() -> str:
    """Get the current portfolio state including cash, positions, and market values."""
    return json.dumps(tools.get_portfolio(), indent=2)


def assess(query: str) -> str:
    """Run the risk manager agent on the given query and return its assessment."""
    texts: list[str] = []
    for msg in _client.beta.messages.tool_runner(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[calculate_var, check_position_limits, get_portfolio_snapshot],
        messages=[{"role": "user", "content": query}],
    ):
        for block in msg.content:
            if block.type == "text" and block.text:
                texts.append(block.text)
    return "\n".join(texts) or "No risk assessment produced."
