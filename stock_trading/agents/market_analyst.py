"""Market Analyst specialist agent — technical and fundamental analysis."""

import json
import anthropic
from anthropic import beta_tool
from stock_trading import tools

_client = anthropic.Anthropic()

_SYSTEM = """\
You are a senior market analyst at a quantitative hedge fund. Your role is to provide \
rigorous technical and fundamental analysis to support trading decisions.

Always:
- Cite specific price levels, indicator values, and news catalysts
- Flag any conflicting signals between technical and fundamental data
- Give a clear directional bias (bullish / bearish / neutral) with reasoning
- State your confidence level (high / medium / low)

Output format:
## Technical Analysis
[RSI, MACD, Bollinger Bands, moving averages]

## Fundamental / News
[Recent headlines and their implications]

## Price Action
[Current price, trend, support/resistance levels]

## Conclusion
[Directional bias | Confidence | Key risks]\
"""


@beta_tool
def get_stock_price(symbol: str) -> str:
    """Get current stock price and daily change.

    Args:
        symbol: Stock ticker symbol (e.g., AAPL, MSFT, GOOGL).
    """
    return json.dumps(tools.get_price(symbol), indent=2)


@beta_tool
def get_price_history(symbol: str, days: int = 30) -> str:
    """Get historical daily closing prices.

    Args:
        symbol: Stock ticker symbol.
        days: Number of trading days of history (default 30).
    """
    return json.dumps(tools.get_history(symbol, days), indent=2)


@beta_tool
def get_technical_indicators(symbol: str) -> str:
    """Get technical indicators: RSI, MACD, Bollinger Bands, and moving averages.

    Args:
        symbol: Stock ticker symbol.
    """
    return json.dumps(tools.get_technicals(symbol), indent=2)


@beta_tool
def get_market_news(symbol: str) -> str:
    """Get recent news headlines for a stock.

    Args:
        symbol: Stock ticker symbol.
    """
    return json.dumps(tools.get_news(symbol), indent=2)


def analyze(query: str) -> str:
    """Run the market analyst agent on the given query and return its analysis."""
    texts: list[str] = []
    for msg in _client.beta.messages.tool_runner(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[get_stock_price, get_price_history, get_technical_indicators, get_market_news],
        messages=[{"role": "user", "content": query}],
    ):
        for block in msg.content:
            if block.type == "text" and block.text:
                texts.append(block.text)
    return "\n".join(texts) or "No analysis produced."
